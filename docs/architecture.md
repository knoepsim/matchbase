# System-Architektur & CI/CD Pipeline

Dieses Projekt nutzt eine moderne, entkoppelte Monorepo-Architektur, um Frontend und Backend effizient nebeneinander zu betreiben.

## 🏗️ Monorepo Struktur

- **Frontend (`apps/web`):** 
  - Framework: Next.js (React) mit TypeScript
  - Styling: Tailwind CSS & Shadcn/UI
  - Package Manager: `pnpm`
- **Backend (`apps/api`):** 
  - Framework: FastAPI (Python)
  - Package Manager: `uv` (extrem schneller Resolver für Python)
- **Containerisierung:**
  - Jede App besitzt ein eigenes `Dockerfile` (Multi-Stage Builds basierend auf Alpine)
  - Entwicklung: `docker-compose.dev.yml` (DB, MQTT, optional Caddy); Betrieb: `deploy/cloud`, `deploy/edge` ([deploy/README.md](../deploy/README.md))

---

## 🚦 CI/CD Pipeline

Das Projekt nutzt GitHub Actions für Continuous Integration (CI) und Continuous Deployment (CD). Die Pipeline ist auf höchste Stabilität ausgelegt.

### 1. Pull Request Gates (`scan.yml`)

Jeder Pull Request (PR) gegen den `main`-Branch wird automatisch geprüft. Ohne grüne Checks gibt es keinen Merge.

```mermaid
graph TD
    PR[Pull Request auf main] --> GL[Gitleaks Scanner]
    PR --> UT[Vitest Unit Tests & Coverage]
    PR --> E2E[Playwright E2E Tests]
    PR --> DB[Docker Build Check]
    
    UT --> SC[SonarCloud Quality Gate]
    
    GL --> MERGE{Alle Checks grün?}
    E2E --> MERGE
    SC --> MERGE
    DB --> MERGE
    
    MERGE -- Ja --> M[Merge erlaubt]
    MERGE -- Nein --> B[Merge blockiert]
```

*Hinweis: Der Docker Build Check simuliert einen Container-Build (Dry-Run), schiebt aber keine Images in die Registry.*

### 2. Release & Publish (`docker-publish.yml`)

Releases in die Container-Registry (GHCR) erfolgen nicht automatisch bei einem Merge, sondern explizit über **Git Tags**.

```mermaid
graph LR
    TAG[git tag v1.0.0] --> PUSH[git push origin v1.0.0]
    PUSH --> META[Extrahiere Metadata]
    META --> BUILD[Build Docker Images]
    BUILD --> GHCR[Push to GHCR]
    
    GHCR --> TAG1[:v1.0.0]
    GHCR --> TAG2[:latest]
```