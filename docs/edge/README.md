# Edge-Architektur: Tournament Core und Tisch-Controller

Erweiterung der Cloud-Plattform um sensorbasierte Spieltische und einen optionalen Rechner vor Ort
(Studienarbeit). Leitfrage: *Wie lässt sich die bestehende Plattform um Sensorik und Edge-Betrieb erweitern, ohne den
reinen Cloud-Betrieb einzuschränken?*

## Grundprinzip: ein Code, zwei Rollen

Der **Tournament Core** ist keine zweite Anwendung. Er ist dieselbe API (`apps/api`) und dieselbe Web-App (`apps/web`)
aus denselben Docker-Images wie in der Cloud, gestartet mit anderer Konfiguration:

| Einstellung | Cloud | Tournament Core |
|---|---|---|
| `NODE_ROLE` | `cloud` | `edge` |
| `MQTT_URL` | leer: kein Listener | `mqtt://mqtt:1883`: hört den Tischen zu |
| Datenbank | zentrale Postgres | lokale Postgres auf dem Core |
| Zusatzdienste | – | Mosquitto (MQTT-Broker) |

Damit bleibt der Cloud-Betrieb unverändert: Ohne `MQTT_URL` startet kein Listener, die neuen Tabellen bleiben leer,
`GET /tournaments/{id}/sensors` liefert `[]`. Turnierlogik, Rechte, Live-Updates (SSE) und Ergebnisregeln gibt es nur
einmal.

```
            Cloud (API + Web + Postgres)
                       ^
                       |  Sync (Phase 3)
                       v
   PWA  <---->  Tournament Core (API + Web + Postgres + Mosquitto)
                       ^
                       |  MQTT  tables/{device}/state
          +------------+------------+
          |            |            |
     ESP32+RFID   Pi+Kamera   Simulator
```

## Repo-Struktur

```
apps/
  api/                     FastAPI, läuft als Cloud oder als Core (NODE_ROLE)
    app/schemas/table_state.py      MQTT-Vertrag v1 (Pydantic, Quelle der Wahrheit)
    app/models/station_device.py    Controller + Messwert-Log
    app/services/sensor_service.py  Zuordnung Messwert -> Station -> Spiel, Ergebnisvorschlag
    app/services/table_listener.py  MQTT-Client (nur mit MQTT_URL), reconnectet selbst
    app/routers/sensors.py          /devices, /tournaments/{id}/sensors, Zuordnung
    scripts/simulate_table.py       Tisch-Controller ohne Hardware
  web/                     unverändert (Phase 2: Sensoranzeige, Vorschlag übernehmen, Discovery)
edge/
  docker-compose.yml       der komplette Core vor Ort
  mosquitto/mosquitto.conf Broker-Konfiguration
  .env.example
firmware/                  (Phase 2) esp32-rfid/ (PlatformIO), vision-pi/ (Python)
docs/edge/
  README.md                dieses Dokument
  protocol.md              MQTT-Vertrag für Firmware-Entwickler
  adr/                     Architekturentscheidungen
```

Firmware liegt im selben Repo, weil sie denselben Vertrag implementiert: Eine Änderung an `protocol.md` und an
`table_state.py` gehört mit der Firmware in denselben PR.

## Backend-Integration (umgesetzt, Phase 1)

1. **Ein Vertrag für alle Sensoren** ([protocol.md](protocol.md)): Ein Controller meldet nur `leftCups` und
   `rightCups`. Ob RFID, Kamera oder Hall-Sensor zählt, steht höchstens informativ im Feld `sensor`.
2. **Controller melden sich selbst an**: Die erste Nachricht legt den Controller an (`station_devices`).
   Ein Manager ordnet ihn einer Spielstätte zu (`PUT /tournaments/{id}/stations/{sid}/device`). Ein physischer Tisch
   dient Turnier für Turnier, die Zuordnung wandert mit.
3. **Messwert → Spiel**: Der Core kennt über den Stationsplaner das Spiel, das gerade an der Station läuft. Jeder
   geänderte Stand wird mit Spiel-ID protokolliert (`sensor_readings`). Wiederholungen (gleiche `seq`, MQTT QoS 1)
   und Heartbeats (gleicher Stand) erzeugen keinen Eintrag.
4. **Sensor schlägt vor, Mensch entscheidet** ([ADR 0003](adr/0003-sensor-schlaegt-vor.md)): Beenden die Zählungen das
   Spiel (die Spielregel in `app/games.py` entscheidet, z. B. eine Seite 0 Becher), liefert
   `GET /tournaments/{id}/sensors` einen `suggestion`. Der Schiedsrichter übernimmt ihn über den normalen
   Ergebnis-Endpunkt mit `source: "sensor"`. Alle Ergebnisregeln (Folgespiel, Gruppen fix, Bestätigung) gelten
   unverändert.
5. **Live**: Jede Änderung erhöht die Revision des Turniers mit dem Bereich `sensors`. Die offenen Seiten bekommen das
   über den bestehenden SSE-Kanal.
6. **Discovery-Endpunkt**: `GET /info` sagt, wer antwortet (`role: cloud | edge`).

## Daten für die Evaluation

| Messgröße | Woher |
|---|---|
| Erkennungsrate / Fehlerrate | `results.source = SENSOR`, unverändert übernommen vs. korrigiert; Folge der `sensor_readings` eines Spiels gegen das Endergebnis |
| Reaktionszeit | `sensor_readings.received_at` (Becher weg) bis Vorschlag bzw. Ergebnis (`results.created_at`) |
| Nachrichtenverlust | Lücken in `sensor_readings.seq` |
| Robustheit / Flackern | Zustandswechsel, die innerhalb kurzer Zeit zurückspringen (`simulate_table --flicker` erzeugt sie künstlich) |
| Verfügbarkeit | `station_devices.last_seen_at`, `online` im Sensor-Endpunkt |
| Vergleich der Techniken | `station_devices.sensor` (rfid, vision, hall) |

## Ausprobieren ohne Hardware

```bash
docker compose -f docker-compose.dev.yml up -d db mqtt
cd apps/api
uv run python -m scripts.seed_dummy_tournaments create --teams 8 --state fresh
MQTT_URL=mqtt://localhost:1883 uv run fastapi dev        # unter Windows: siehe unten
uv run python -m scripts.simulate_table --device sim-1   # meldet den Controller an
# Controller zuordnen: PUT /tournaments/{id}/stations/{sid}/device {"device_id": "sim-1"}
uv run python -m scripts.simulate_table --device sim-1 --cups 6 --interval 1
# GET /tournaments/{id}/sensors zeigt Stand und am Ende den Vorschlag
```

Windows: Der MQTT-Client braucht die Selector-Event-Loop, uvicorn nutzt unter Windows die Proactor-Loop. Der Listener
meldet das im Log und bleibt aus. Den Core deshalb in Docker oder unter Linux betreiben (der Simulator setzt die Loop
selbst).

## Phasen

| Phase | Inhalt | Stand |
|---|---|---|
| 1 | Vertrag, Controller-Verwaltung, Messwert-Log, Vorschlag, `/info`, Core-Compose, Simulator | umgesetzt |
| 2 | Web: Sensorstand an der Station, „Vorschlag übernehmen“ im Ergebnis-Dialog, Controller zuordnen; Seitenwahl (welches Team links); Firmware ESP32/RFID; Broker-ACLs pro Controller | offen |
| 3 | Sync Cloud ↔ Core ([ADR 0002](adr/0002-sync-single-writer.md)), Anmeldung am Core ohne SMS | offen |
| 4 | Discovery in der PWA ([ADR 0001](adr/0001-discovery.md)), Offline-Betrieb | offen |

## Offene Punkte

- **Seitenwahl**: Team A steht heute links. Spielen die Teams anders herum, ist der Vorschlag spiegelverkehrt. Lösung in
  Phase 2: `matches.sides_swapped`, gesetzt beim Start des Spiels am Tisch.
- **Entprellung**: Ein Vorschlag entsteht sofort beim ersten Stand mit 0 Bechern. Ob eine Mindest-Standzeit nötig ist,
  soll die Evaluation zeigen (Flackern messen, dann entscheiden).
- **Neustart eines Controllers**: `seq` beginnt wieder bei 0. Nur genau gleiche `seq` wird verworfen, ein Neustart
  geht deshalb nicht verloren. Eine zufällig gleiche `seq` direkt nach dem Neustart würde eine Nachricht verwerfen
  (bei Heartbeats unkritisch).
