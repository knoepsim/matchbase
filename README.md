# MatchBase

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="apps/web/public/brand/logo-stacked-dark.svg">
    <img alt="MatchBase" src="apps/web/public/brand/logo-stacked.svg" width="260">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/knoepsim/matchbase/actions/workflows/scan.yml"><img alt="Scan" src="https://github.com/knoepsim/matchbase/actions/workflows/scan.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/knoepsim/matchbase/actions/workflows/codeql.yml"><img alt="CodeQL" src="https://github.com/knoepsim/matchbase/actions/workflows/codeql.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/knoepsim/matchbase/actions/workflows/docker-publish.yml"><img alt="Docker" src="https://github.com/knoepsim/matchbase/actions/workflows/docker-publish.yml/badge.svg"></a>
  <a href="https://sonarcloud.io/summary/new_code?id=knoepsim_beerpong-webapp"><img alt="Quality Gate" src="https://sonarcloud.io/api/project_badges/measure?project=knoepsim_beerpong-webapp&metric=alert_status"></a>
  <a href="https://conventionalcommits.org"><img alt="Conventional Commits" src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white"></a>
</p>

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
