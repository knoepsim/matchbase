[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)


# MatchBase

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/brand/logo-horizontal-dark.svg">
  <img alt="MatchBase" src="apps/web/public/brand/logo-horizontal.svg" width="360">
</picture>

Willkommen bei MatchBase, der Turnierplattform! Turniere organisieren und mitspielen: Anmeldung, Check-in, Spielplan und Ergebnisse. Bierpong ist das erste integrierte Spiel, weitere Spiele und Turniermodi folgen.

Dieses Projekt nutzt einen modernen Tech-Stack (Next.js, FastAPI, Docker) in einem Monorepo-Setup.

## Dokumentation

Die ausführliche Dokumentation, Architektur-Beschreibungen und Anforderungen findest du im [`/docs` Verzeichnis](./docs/README.md).

## Struktur

- `apps/web/`: Frontend (Next.js, React, Tailwind, Shadcn)
- `apps/api/`: Backend (FastAPI, Python)
- `docs/`: Projektdokumentation
- `.github/`: CI/CD Workflows

## Lokales Setup

Mit Docker Compose kannst du die komplette Umgebung lokal starten:

```bash
docker-compose up --build
```
