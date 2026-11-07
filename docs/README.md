# Beerpong Webapp Documentation

Willkommen im Dokumentationsverzeichnis! 
Hier werden alle globalen Architektur-Entscheidungen, Anforderungen (Requirements) und Anleitungen gesammelt.

## Struktur

- [**Architektur & CI/CD Pipeline:**](./architecture.md) Beschreibung der Monorepo-Struktur, Containerisierung und Pipelines.
- [**Contributing:**](./CONTRIBUTING.md) GitHub Flow Branching-Modell und Release-Prozess.
- [**Edge-Architektur (Studienarbeit):**](./edge/README.md) Tournament Core vor Ort, Tisch-Controller über MQTT, Sync und Discovery (mit ADRs).
- [**Architekturentscheidungen (ADRs):**](./adr/) nummeriert, mit Status.
- [**MQTT-Vertrag:**](../protocol/README.md) Tisch-Controller ↔ Edge, JSON Schema und Beispielnachrichten.
- [**Betrieb:**](../deploy/README.md) Ein Eingang (Caddy) für Web und API, in Cloud und Edge gleich, TLS über eine Variable.
- **Anforderungen (Requirements):** User Stories, Features und Akzeptanzkriterien.
- **Setup:** Lokale Entwicklungsumgebung und Deployment-Guides.

*(Dieses Verzeichnis dient als Single Source of Truth für das gesamte Projekt)*
