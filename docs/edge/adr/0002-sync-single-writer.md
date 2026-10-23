# ADR 0002: Synchronisation Cloud ↔ Core: ein Schreiber pro Turnier

Status: vorgeschlagen (Umsetzung Phase 3)

## Kontext

Im Hybrid- und Offline-Betrieb gibt es zwei Datenbanken. Würden beide dasselbe Turnier ändern (Multi-Master), müssten
Konflikte aufgelöst werden. Beispiel: zwei verschiedene Ergebnisse für dasselbe Spiel, während die Verbindung weg war.
Für einen Turnierbaum gibt es dafür keine sinnvolle automatische Regel, denn ein Ergebnis bestimmt die Folgespiele.

## Entscheidung

Ein Turnier hat zu jedem Zeitpunkt **genau einen Schreiber** (Single Writer, Lease):

1. **Auschecken**: Die Orga übergibt ein Turnier vor Ort an einen Core (`POST /tournaments/{id}/handover`). Der Core
   lädt dafür einen vollständigen Snapshot: Turnier, Teams, Mitglieder, Rollen, Stationen, Spiele, Ergebnisse. Ab dann
   steht in der Cloud `hosted_by = core-1` und die Cloud lehnt Änderungen ab (409: „Das Turnier wird vor Ort
   geführt.“).
2. **Spiegeln**: Der Core schreibt jede Änderung in eine **Outbox** (gleiche Transaktion wie die Änderung, Ereignisse in
   Reihenfolge, mit Revision). Ein Sync-Task schiebt sie an die Cloud, sobald Internet da ist. Die Cloud wendet sie an.
   Zuschauer außerhalb der Halle sehen das Turnier also live, sobald Verbindung besteht.
3. **Offline**: Der Core arbeitet uneingeschränkt weiter, die Outbox wächst. Danach wird sie in Reihenfolge abgearbeitet.
   Da nur der Core schreibt, gibt es keine Konflikte, nur Verzögerung.
4. **Zurückgeben**: Am Ende gibt der Core das Turnier zurück (Outbox leer, `hosted_by = null`). Fällt der Core aus, kann
   die Orga das Turnier in der Cloud zurückholen. Das ist eine bewusste, angezeigte Entscheidung, die den Stand des
   letzten Syncs übernimmt.

Die Grundlage ist im Code schon da:

- Ergebnisse sind ein Ereignis-Log (`results`: CREATED/MODIFIED/DELETED), also nur Anhängen.
- Jede sichtbare Änderung erhöht `tournaments.revision` (`app/services/revision.py`).
- Alle IDs sind UUIDs, Core und Cloud können also ohne Absprache Datensätze anlegen.

## Verworfen

- **Multi-Master mit Konfliktauflösung** (Last-Write-Wins, CRDT): Last-Write-Wins verliert stillschweigend Ergebnisse.
  CRDTs passen nicht zu Regeln wie „das Folgespiel hat schon ein Ergebnis“.
- **Datenbank-Replikation** (Postgres logical replication): Sie repliziert Tabellen statt Turniere, braucht eine
  ständige Verbindung zur Einrichtung und ist für den Ausfallfall schwer zu bedienen.

## Folgen

- Nutzerkonten bleiben in der Cloud. Der Core bekommt im Snapshot nur Name und ID der Beteiligten, keine
  Telefonnummern (Datensparsamkeit).
- Ein Turnier kann nicht gleichzeitig in der Cloud und vor Ort geführt werden. Das ist eine bewusste Einschränkung, die
  im CAP-Sinn Konsistenz und Verfügbarkeit vor Ort über Verfügbarkeit in der Cloud stellt.
