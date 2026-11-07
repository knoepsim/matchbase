# Contributing Guidelines

Zwei langlebige Branches:

- **`main`**: nur Releases. Jeder Stand auf `main` ist eine veröffentlichte oder gleich zu veröffentlichende Version.
- **`dev`**: Integration, Default-Branch auf GitHub. Hier landen alle Features; `dev` muss trotzdem jederzeit
  releasefähig bleiben (unfertige Teile wie das Edge sind per Konfiguration abgeschaltet, z. B. ohne `MQTT_URL`).

```
feat/* ──PR (squash)──> dev ──PR (merge commit)──> main ──tag vX.Y.Z──> Release
                          ^                          │
                          └──── main zurück in dev ──┘   (nach jedem Release und Hotfix)
hotfix/* ──PR (squash)──> main ──tag vX.Y.(Z+1)
```

## 🌿 Branching & Pull Requests

1. **Branch erstellen** von `dev` (Hotfix für ein Release: von `main`)
   Format: `<type>/<kurze-beschreibung>`, Types: feat, fix, refactor, chore, docs, test, ci, hotfix
   Beispiele: `feat/web-slider-component`, `hotfix/api-image-start`. Nur Kleinbuchstaben und Bindestriche.
2. **Commit** nach [Conventional Commits (v1.0.0)](https://www.conventionalcommits.org/de/v1.0.0/)
   (z. B. `feat: add new slider`, `fix: header padding`).
3. **Pull Request** gegen `dev` (GitHub schlägt `dev` als Ziel vor), Merge per **Squash**: ein Commit pro Feature.

## 🔀 Welcher Merge-Button?

| Pull Request | Button | Warum |
|---|---|---|
| Feature/Fix/Chore → `dev` | **Squash and merge** | ein Commit pro Änderung, der PR-Titel wird die Commit-Nachricht (Conventional Commit) |
| Hotfix → `main` | **Squash and merge** | wie oben, nur direkt auf das Release |
| Release `dev` → `main` | **Create a merge commit** | `main` übernimmt die Commits von `dev` unverändert; nur so bleiben beide Branches eine gemeinsame Historie |
| Rückführung `main` → `dev` | **Create a merge commit** | holt Release-Merge und Hotfixes nach `dev`, ohne Commits umzuschreiben |

**Rebase and merge nie verwenden.** GitHub schreibt dabei jeden Commit neu (neue SHA). Bei einem Release-PR hätten
`dev` und `main` danach dieselben Änderungen in verschiedenen Commits, und der nächste Release-PR zeigt Konflikte in
Dateien, die niemand angefasst hat. Bei Feature-PRs bringt Rebase nichts, was Squash nicht besser kann.

Faustregel: **In einen Branch hinein, der ein langlebiger Branch ist (`dev`, `main`), kommt ein Feature per Squash,
ein anderer langlebiger Branch per Merge-Commit.**

## 🔢 Versionen (SemVer)

`MAJOR.MINOR.PATCH`, vor 1.0 bedeutet ein MINOR-Schritt einen Meilenstein, der auch inkompatibel sein darf; PATCH ist
nur Fehlerbehebung. Die Version steht an genau einer Stelle: im Git-Tag. CI gibt sie beim Build in die Images
(`APP_VERSION`, sichtbar unter `GET /api/`); lokal heißt sie `0.0.0-dev`.

| Was | Tag/Branch | Images | Wer bekommt es |
|---|---|---|---|
| Release | Tag `vX.Y.Z` auf `main` | `X.Y.Z`, `X.Y`, `latest` | Produktion (Watchtower folgt `latest`) |
| Testversion | Tag `vX.Y.Z-rc.N` auf `dev` | `X.Y.Z-rc.N` | gezielt, z. B. ein Edge bei einem Testturnier |
| Vorschau | jeder Push auf `dev` | `X.(Y+1).0-dev.<run>`, `dev` | Test-Server, nie Produktion |

Unabhängig davon versioniert: der MQTT-Vertrag (`v` in der Nachricht, `protocol/`) und der API-Vertrag
zwischen Cloud und Edge (`api` in `/info`). Sie ändern sich nur bei inkompatiblen Änderungen.

## 🚧 CI/CD Workflow & PR-Gates

Vor dem Merge in `dev` oder `main` müssen alle **PR-Gates** grün sein:

- **Keine geleakten Secrets:** *Gitleaks* prüft, ob Passwörter oder Tokens eingecheckt wurden.
- **Unit Tests & Coverage:** alle *Vitest*-Tests grün, die Testabdeckung sinkt nicht signifikant.
- **E2E Tests:** die *Playwright*-Tests laufen im Headless-Browser fehlerfrei.
- **API Tests:** *pytest* gegen PostgreSQL, inklusive Migrationen auf einer leeren Datenbank.
- **SonarCloud Quality Gate:** Coverage und Code-Qualität.
- **CodeQL:** statische Sicherheitsanalyse.
- **Docker Build Check:** die Images von `apps/web` und `apps/api` bauen, und *Trivy* findet darin keine hohe oder
  kritische Schwachstelle, für die es einen Fix gibt.
- **Docker Build Check (arm64):** dieselben Images bauen auch für arm64 (Raspberry Pi als Edge).

Außerhalb der PRs:

- **Image Scan** (montags): *Trivy* prüft die Images von `latest` auf neu bekannt gewordene Schwachstellen. Funde
  stehen im Security-Tab; behoben wird per Hotfix-Release.
- **Publish:** Images für amd64 und arm64 unter einem Tag; der Scan des veröffentlichten Images landet ebenfalls im
  Security-Tab.

## 🚀 Release

1. PR `dev` → `main` mit Titel `release: vX.Y.Z`, Merge per **Merge-Commit** (nicht Squash: sonst laufen die
   Historien von `dev` und `main` auseinander und der nächste Release-PR hat Konflikte).
2. Auf `main` taggen:
   ```bash
   git switch main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
   ```
   `docker-publish.yml` baut die Images, Watchtower auf dem Server zieht `latest`.
3. `main` zurück in `dev` (PR `main` → `dev`, Merge-Commit), damit `dev` den Tag kennt.

**Hotfix:** Branch `hotfix/*` von `main`, PR gegen `main`, Tag `vX.Y.(Z+1)`, danach `main` zurück in `dev`.
