# Betrieb: ein Eingang für Web und API

Cloud (`docker-compose.yml`) und Edge (`edge/docker-compose.yml`) starten denselben Proxy mit derselben Datei
[`caddy/Caddyfile`](caddy/Caddyfile). Begründung und Vergleich mit Traefik, nginx und HAProxy:
[studienarbeit-entscheidungen.md, 8.8](../docs/edge/studienarbeit-entscheidungen.md#88-deployment-und-betrieb).

```
Browser ──> Caddy :80/:443 ──/api/* (ohne Präfix)──> api:8000
                          └──alles andere─────────> web:3000
```

Web und API veröffentlichen keine Ports, nur Caddy ist erreichbar.

## Cloud starten

```
cp .env.example .env   # POSTGRES_PASSWORD und SECRET_KEY setzen (openssl rand -hex 32)
docker compose up -d
```

Das API-Image bringt beim Start das Datenbankschema selbst auf den neuesten Stand (`alembic upgrade head`) und startet
dann den Server. Das Edge startet genauso: `edge/.env.example` nach `edge/.env`, dann
`docker compose -f edge/docker-compose.yml up -d`.

Solange es nur das Dummy-SMS-Backend gibt, startet `ENVIRONMENT=production` absichtlich nicht (jeder Code wäre
`123456`). Mit `ENVIRONMENT=development` läuft es, ist dann aber nicht für öffentlichen Betrieb geeignet.

## TLS: eine Variable

| `SITE_ADDRESS` | Wann |
|---|---|
| `:80` (Standard) | hinter einem Tunnel oder Proxy, der TLS abschließt (Cloudflare Tunnel), oder HTTP im WLAN vor Ort |
| `matchbase.example.org` | Caddy holt und erneuert das Let's-Encrypt-Zertifikat selbst; Ports 80 und 443 müssen aus dem Internet erreichbar sein |

Mit Cloudflare Tunnel: `cloudflared` in das Netz `beerpong-network` hängen und den Hostnamen auf `http://caddy:80`
zeigen lassen (oder auf Port 80 des Hosts). Eine Regel genügt, das Aufteilen nach `/api` übernimmt Caddy.

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
  `cloudflared` im selben Docker-Netz.
- Der Cookie-Pfad `/api/auth` und die CSP bleiben gültig: Der Browser sieht wie bisher `/api`.
