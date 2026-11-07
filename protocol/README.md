# MQTT-Vertrag Tisch-Controller → MatchBase Edge (v1)

Quelle der Wahrheit ist dieser Ordner, sprachneutral:

- [`mqtt/table-state.v1.schema.json`](mqtt/table-state.v1.schema.json): JSON Schema der Nachricht
- [`mqtt/examples/valid`](mqtt/examples/valid), [`mqtt/examples/invalid`](mqtt/examples/invalid): Beispielnachrichten,
  die jede Seite annehmen bzw. ablehnen muss

Die API prüft ihr Modell (`apps/api/app/schemas/table_state.py`) in `apps/api/tests/test_protocol.py` gegen Schema und
Beispiele, die Firmware testet gegen dieselben Beispiele. Eine Änderung am Vertrag ändert Schema, Beispiele, API und
Firmware im selben PR. Ein neues Beispiel genügt, um einen Fall für alle Seiten festzuschreiben.

## Topic

```
tables/{deviceId}/state
```

- `deviceId`: vom Controller gewählt, eindeutig, `[A-Za-z0-9_-]{1,64}`, z. B. `t3-rfid` oder die MAC-Adresse.
- Die Identität steckt im Topic, nicht in der Nachricht. Mit Broker-ACLs (Phase 2) darf jeder Controller nur unter
  seinem eigenen Topic schreiben. So kann er sich nicht als ein anderer Tisch ausgeben.
- Welcher Tisch (Spielstätte) das ist, entscheidet das Edge über die Zuordnung, nicht der Controller. Ein Controller
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
mit einem alten Edge kompatibel.

## Wann senden

- **Bei jeder Änderung** des Standes, sofort.
- **Heartbeat**: denselben Stand mindestens alle 10 s erneut (mit neuer `seq`). Nach 30 s Stille gilt der Controller
  als offline (`SENSOR_OFFLINE_SECONDS`).
- `retain: true`: Startet das Edge neu, bekommt er vom Broker sofort den letzten Stand jedes Tisches. Das Edge erkennt
  die schon verarbeitete `seq` und legt keinen doppelten Messwert an.

## Was der Controller nicht tut

Er entscheidet nicht, wer gewonnen hat, und er kennt keine Spielregeln. Ob ein Stand das Spiel beendet, entscheidet
das Edge über die Regel des Spiels (`app/games.py`, `sensed_end`).

## Später (nicht in v1)

- `tables/{deviceId}/health`: Firmware-Version, Signalstärke, Temperatur, Fehlerzähler.
- `tables/{deviceId}/config` (Edge → Controller): Anzahl Becher pro Seite, Kalibrierung.
