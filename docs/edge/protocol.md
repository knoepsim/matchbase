# MQTT-Vertrag Tisch-Controller → Tournament Core (v1)

Quelle der Wahrheit im Code: `apps/api/app/schemas/table_state.py`. Wer hier etwas ändert, ändert es dort mit.

## Topic

```
tables/{deviceId}/state
```

- `deviceId`: vom Controller gewählt, eindeutig, `[A-Za-z0-9_-]{1,64}`, z. B. `t3-rfid` oder die MAC-Adresse.
- Die Identität steckt im Topic, nicht in der Nachricht. Mit Broker-ACLs (Phase 2) darf jeder Controller nur unter
  seinem eigenen Topic schreiben. So kann er sich nicht als ein anderer Tisch ausgeben.
- Welcher Tisch (Spielstätte) das ist, entscheidet der Core über die Zuordnung, nicht der Controller. Ein Controller
  kennt weder Turnier noch Spiel noch Teams.

## Nachricht

JSON, UTF-8, QoS 1, `retain: true`.

```json
{ "v": 1, "leftCups": 4, "rightCups": 2, "seq": 118, "sensor": "rfid" }
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `v` | nein (Standard 1) | Version des Vertrags |
| `leftCups` | ja | Becher, die auf der linken Tischhälfte stehen, 0–99 |
| `rightCups` | ja | Becher, die auf der rechten Tischhälfte stehen, 0–99 |
| `seq` | empfohlen | zählt mit jeder Nachricht hoch, beginnt nach einem Neustart neu |
| `sensor` | empfohlen | Technik dahinter: `rfid`, `vision`, `hall`, `sim` (nur für die Auswertung) |

Unbekannte Felder werden ignoriert (z. B. `tableId` aus frühen Entwürfen, `confidence`). So bleibt ein neuer Controller
mit einem alten Core kompatibel.

## Wann senden

- **Bei jeder Änderung** des Standes, sofort.
- **Heartbeat**: denselben Stand mindestens alle 10 s erneut (mit neuer `seq`). Nach 30 s Stille gilt der Controller
  als offline (`SENSOR_OFFLINE_SECONDS`).
- `retain: true`: Startet der Core neu, bekommt er vom Broker sofort den letzten Stand jedes Tisches. Der Core erkennt
  die schon verarbeitete `seq` und legt keinen doppelten Messwert an.

## Was der Controller nicht tut

Er entscheidet nicht, wer gewonnen hat, und er kennt keine Spielregeln. Ob ein Stand das Spiel beendet, entscheidet
der Core über die Regel des Spiels (`app/games.py`, `sensed_end`).

## Später (nicht in v1)

- `tables/{deviceId}/health`: Firmware-Version, Signalstärke, Temperatur, Fehlerzähler.
- `tables/{deviceId}/config` (Core → Controller): Anzahl Becher pro Seite, Kalibrierung.
