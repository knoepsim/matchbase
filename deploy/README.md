# Betrieb: ein Eingang für Web und API

Cloud (`cloud/docker-compose.yml`) und Edge (`edge/docker-compose.yml`) starten denselben Proxy mit derselben Datei
[`caddy/Caddyfile`](caddy/Caddyfile). Begründung und Vergleich mit Traefik, nginx und HAProxy:
[studienarbeit-entscheidungen.md, 8.8](../docs/edge/studienarbeit-entscheidungen.md#88-deployment-und-betrieb).

```
Browser ──> Caddy :80/:443 ──/api/* (ohne Präfix)──> api:8000
                          └──alles andere─────────> web:3000
```

Web und API veröffentlichen keine Ports, nur Caddy ist erreichbar.

## Cloud: Instanzen und Host-Dienste

```
deploy/cloud/docker-compose.yml   eine Instanz (DB, API, Web, Caddy), beliebig oft startbar
deploy/cloud/tunnel.yml           Override: erreichbar über cloudflared
deploy/cloud/expose.yml           Override: erreichbar direkt über Port 80/443 (eine Instanz pro Host)
deploy/host/docker-compose.yml    einmal pro Server: cloudflared und Watchtower
```

Jede Instanz hat eine eigene Env-Datei: `INSTANCE` (Projektname, Volumes, Adresse im Tunnel-Netz) und
`MATCHBASE_TAG` (welchem Image-Tag sie folgt). Env-Dateien in `deploy/` werden nicht committet (`deploy/**/*.env`).

### Beispiel: prod und dev auf einem Server, hinter Cloudflare

| Instanz | Domain | `INSTANCE` | `MATCHBASE_TAG` | bekommt |
|---|---|---|---|---|
| prod | `matchbase.cloud` | `matchbase-prod` | `latest` | jedes Release (Tag `vX.Y.Z` auf `main`) |
| dev | `dev.matchbase.cloud` | `matchbase-dev` | `dev` | jeden Merge in `dev` |

1. **Tunnel anlegen:** Cloudflare Zero Trust → Networks → Tunnels → Create a tunnel (Cloudflared), Token kopieren.
   Unter *Public Hostnames* zwei Einträge:
   - `matchbase.cloud` → Service `HTTP`, URL `matchbase-prod:80`
   - `dev.matchbase.cloud` → Service `HTTP`, URL `matchbase-dev:80`

   Das Aufteilen nach `/api` übernimmt Caddy, pro Domain genügt eine Regel.
2. **Host-Dienste** (legen auch das Netz `matchbase-tunnel` an, also zuerst starten):
   ```
   cp deploy/host/.env.example deploy/host/host.env          # TUNNEL_TOKEN eintragen
   docker compose --env-file deploy/host/host.env -f deploy/host/docker-compose.yml up -d
   ```
3. **Instanzen:**
   ```
   cp deploy/cloud/.env.example deploy/cloud/prod.env        # INSTANCE=matchbase-prod, MATCHBASE_TAG=latest, Secrets
   cp deploy/cloud/.env.example deploy/cloud/dev.env         # INSTANCE=matchbase-dev,  MATCHBASE_TAG=dev, eigene Secrets
   docker compose --env-file deploy/cloud/prod.env -f deploy/cloud/docker-compose.yml -f deploy/cloud/tunnel.yml up -d
   docker compose --env-file deploy/cloud/dev.env  -f deploy/cloud/docker-compose.yml -f deploy/cloud/tunnel.yml up -d
   ```

Jede Instanz hat ihre eigene Datenbank. Dev darf also Migrationen fahren, die prod noch nicht kennt. Watchtower prüft
alle 5 Minuten, ob es unter `latest` bzw. `dev` ein neues Image gibt, und startet nur die Container mit dem Label
`com.centurylinklabs.watchtower.enable` neu: API, Web und cloudflared, nie die Datenbanken. Das API-Image bringt beim
Start das Schema selbst auf den neuesten Stand (`alembic upgrade head`).

**Login:** Solange es nur das Dummy-SMS-Backend gibt, startet `ENVIRONMENT=production` absichtlich nicht (jeder Code
wäre `123456`). Mit `ENVIRONMENT=development` läuft die Instanz, aber dann kann sich jeder mit jeder Nummer anmelden,
auch mit der eines Admins. Öffentlich nur mit **Cloudflare Access** davor (Zero Trust → Access → Applications, z. B.
Login per E-Mail-Code für eine Liste von Adressen).

### Ohne Tunnel

Eine Instanz pro Server mit eigenem Zertifikat: `SITE_ADDRESS=matchbase.example.org` in der Env-Datei und `expose.yml`
statt `tunnel.yml`. Ports 80 und 443 müssen aus dem Internet erreichbar sein.

## Edge starten

`deploy/edge/.env.example` nach `deploy/edge/.env`, dann `docker compose -f deploy/edge/docker-compose.yml up -d`.

## TLS: eine Variable

| `SITE_ADDRESS` | Wann |
|---|---|
| `:80` (Standard) | hinter einem Tunnel oder Proxy, der TLS abschließt (Cloudflare Tunnel), oder HTTP im WLAN vor Ort |
| `matchbase.example.org` | Caddy holt und erneuert das Let's-Encrypt-Zertifikat selbst (`expose.yml`) |

### Edge mit HTTPS ohne öffentliche Adresse (Zielbild)

Ein Edge im Hallennetz ist aus dem Internet nicht erreichbar, die normale Prüfung von Let's Encrypt scheitert. Dann
braucht es DNS-01: ein Caddy-Image mit dem Modul des DNS-Anbieters und ein API-Token, das nur auf der Box liegt.

```dockerfile
FROM caddy:2-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/cloudflare

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

Im Caddyfile kommt in den Site-Block `tls { dns cloudflare {env.CF_API_TOKEN} }`. Das ist noch nicht eingebaut; im
PoC läuft das Edge mit `SITE_ADDRESS=:80` im verschlüsselten WLAN.

## Entwicklung

`pnpm dev` leitet `/api` weiter wie bisher (`apps/web/next.config.ts`). Den Proxy gegen die Dev-Server ausprobieren:

```
docker compose -f docker-compose.dev.yml --profile proxy up -d caddy   # dann http://localhost:8080
```

## Hinweise

- Die API vertraut `X-Forwarded-*` von jedem Absender (`FORWARDED_ALLOW_IPS=*`). Das ist nur richtig, weil sie keinen
  Port veröffentlicht. Wer sie direkt erreichbar macht, muss das einschränken.
- Caddy übernimmt `X-Forwarded-For` nur von privaten Adressen (`TRUSTED_PROXIES`, Standard `private_ranges`), also von
  `cloudflared` im Netz `matchbase-tunnel`.
- Der Cookie-Pfad `/api/auth` und die CSP bleiben gültig: Der Browser sieht wie bisher `/api`.
