# ADR 0003: Der Sensor schlägt das Ergebnis vor, ein Mensch bestätigt

Status: umgesetzt (Phase 1)

## Kontext

Ein Tisch-Controller sieht, wie viele Becher pro Seite stehen. Ein falscher Stand (umgestoßener Becher, verdeckter
Sensor, Flackern) würde als automatisches Ergebnis sofort das falsche Team in die nächste Runde schicken. Das lässt
sich nur durch Löschen und erneutes Eintragen korrigieren.

## Entscheidung

- Der Sensor **schreibt nie ein Ergebnis**. Beenden die Zählungen das Spiel (Regel des Spiels: `sensed_end` in
  `app/games.py`), zeigt der Core das Ergebnis als **Vorschlag** an der Station (`GET /tournaments/{id}/sensors`,
  Feld `suggestion`).
- Ein Schiedsrichter übernimmt es mit einem Tipp über den normalen Ergebnis-Endpunkt mit `source: "sensor"`, oder
  korrigiert es vorher. Alle Regeln und Rechte gelten unverändert.
- Jeder geänderte Stand wird protokolliert (`sensor_readings`). Das ist die Datenbasis der Evaluation und die Spur, wie
  ein Ergebnis zustande kam.

## Folgen

- Messbar wird, wie oft der Vorschlag ohne Änderung übernommen wurde (Erkennungsrate) und wie lange es vom letzten
  Becher bis zum Ergebnis dauerte (Reaktionszeit).
- Ein späterer Vollautomatik-Modus ist eine Einstellung pro Turnier („Vorschläge nach N Sekunden stabil automatisch
  übernehmen“). Er braucht keinen Umbau, sondern denselben Vorschlag und einen Timer im Core.
- Spiele ohne Sensorregel (Fußball) bekommen nie einen Vorschlag.
