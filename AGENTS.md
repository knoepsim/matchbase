# AGENTS.md

## Setup
- Test-Turniere mit Dummy-Spielern/-Teams (bleiben in der DB, werden wiederverwendet): `uv run python -m scripts.seed_dummy_tournaments create --teams 28 --state running` (apps/api; `--state registration|checkin|both|fresh|running|finished`, `--game beerpong|football`, `--mode single_elimination|round_robin|groups_knockout` (mit `--groups N --advance K`), `seed` erzeugt je ein Turnier pro Phase, `delete` entfernt nur die Dummy-Turniere, `token N` gibt ein Bearer-Token von Dummy Spieler N aus; im lokalen Netz (Handy): `CORS_ORIGINS=http://localhost:3000,http://<IP>:3000` in apps/api/.env und `ALLOWED_DEV_ORIGINS=<IP>` in apps/web/.env.local, dann beide Server neu starten; Dummy-Login in der App: `+49 158 99000001`, SMS-Code `123456`; unter Windows die API mit `PYTHONUTF8=1` starten, wenn ihre Ausgabe umgeleitet wird, sonst kann die Konsole das "→" der Dummy-SMS nicht ausgeben)
- Edge/Sensorik (Studienarbeit, `docs/edge/README.md`): Broker mit `docker compose -f docker-compose.dev.yml up -d mqtt`, Tisch ohne Hardware: `uv run python -m scripts.simulate_table --device sim-1` (apps/api); der MQTT-Listener der API läuft nur mit `MQTT_URL` und nicht unter Windows (Proactor-Loop), den Core dafür in Docker (`edge/docker-compose.yml`) starten

## Tests (müssen vor PR grün sein)
- Unit: `pnpm test` (Vitest)
- E2E: `pnpm test:e2e` (Playwright)
- Alle Changes müssen lokal verifiziert sein, bevor ein PR erstellt wird — kein "hoffentlich funktioniert's"

## Branch/Commit Rules
- Nie direkt auf main pushen, immer Feature-Branch + PR
- Commits nach Conventional Commits (feat, fix, chore, docs, refactor, test, ci, perf, style)
- main = immer deploybar, Publish nur bei git tag v*.*.*

## Code-Qualität
- Best Practices statt Quick-Fixes: etablierte Patterns der jeweiligen Sprache/Frameworks nutzen (React, FastAPI, TypeScript-Konventionen), keine Eigenkonstruktionen ohne Grund
- Wiederverwendbarkeit vor Duplikation: gemeinsame Logik in Hooks, Utils, Shared-Modules auslagern statt Copy-Paste
- Allgemeine Lösungen bevorzugen: keine Hardcoded-Edge-Cases oder Nischenlösungen für einzelne Sonderfälle — wenn ein Problem generisch lösbar ist, generisch lösen
- Vor jedem Fix: bestehenden Code hinterfragen, nicht nur Code addieren
  - Frage dich: Ist der Fix ein Symptom eines strukturellen Problems?
  - Gibt es eine Stelle im bestehenden Code, die durch Umbau statt Erweiterung das Problem eliminiert?
  - Wächst die Codebase nur, weil an der falschen Stelle gepatcht wird?
  - Bevorzuge Refactoring/Vereinfachung über additive Patches, wenn beides möglich ist
- Bevor du einen Fix implementierst, beschreibe kurz im PR/Commit, warum du dich für Patch vs. Refactor entschieden hast

## UI/UX
Regeln für jede Frontend-Änderung: siehe `apps/web/AGENTS.md`.

## Do not
- Keine Secrets committen
- Docker-Publish-Workflow nicht manuell antriggern
