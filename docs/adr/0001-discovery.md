# ADR 0001: Wie findet die PWA den Tournament Core?

Status: vorgeschlagen (Umsetzung Phase 4)

## Kontext

Das Konzept sieht vor, dass die aus der Cloud geladene PWA beim Start `http://beerpong.local/api/info` abfragt und bei
Antwort ihre API auf den Core umstellt. Das scheitert im Browser an vier Stellen:

1. **Mixed Content**: Eine Seite von `https://…` darf kein `fetch` an `http://…` machen. Alle aktuellen Browser
   blockieren das ohne Rückfrage. Ausgenommen sind nur `localhost` und `127.0.0.1`, nicht `.local`.
2. **Zugriff aufs lokale Netz**: Selbst über HTTPS fragt Chrome (Local Network Access) den Nutzer um Erlaubnis, bevor
   eine öffentliche Seite Adressen im lokalen Netz anspricht. Andere Browser verschärfen in die gleiche Richtung.
3. **Sitzung**: Die Session-Cookies gehören zur Cloud-Domain (HttpOnly). Ein Aufruf an eine andere Origin schickt sie
   nicht mit, der Core kennt den Nutzer also nicht.
4. **Offline**: Die Web-App hat keinen Service Worker. Ohne Internet lädt die Cloud-PWA gar nicht, und damit auch keine
   Discovery.

Außerdem löst `.local` (mDNS) nicht auf jedem Gerät auf. Android unterstützt mDNS-Namen im Browser erst spät und
uneinheitlich.

## Entscheidung

Der Core liefert die PWA **selbst** aus (dasselbe Image `beerpong-webapp-web`). Gewechselt wird per **Navigation**,
nicht per `fetch`:

1. Der Core hat einen echten HTTPS-Namen, z. B. `core-1.edge.knoep.de`:
   - Der öffentliche DNS-Eintrag zeigt auf seine lokale IP (z. B. 192.168.10.2).
   - Das Zertifikat kommt per Let's Encrypt **DNS-01**, dafür braucht es keinen offenen Port.
   - Damit gibt es kein Mixed Content und kein `.local`, und das Zertifikat ist gültig.
2. Ist der Core online, meldet er sich bei der Cloud an (Phase 3: `PUT /edge-nodes/{id}` mit seiner lokalen URL und
   den Turnieren, die er führt). Die Turnierseite in der Cloud zeigt dann
   „Dieses Turnier läuft vor Ort: *Zur Turnier-Station wechseln*“ und leitet nach einer erfolgreichen Prüfung weiter
   (`<img>`/`fetch` auf `https://core-1…/api/info`, als Navigation erlaubt). Dabei gibt sie ein einmaliges
   Übergabe-Token mit, mit dem der Core eine eigene Sitzung anlegt.
3. Ohne Internet öffnen Spieler direkt die Core-Adresse. Sie steht als QR-Code an jedem Tisch.
4. `GET /info` (umgesetzt) bleibt der Endpunkt, an dem jede Seite erkennt, wer antwortet. Die Web-App zeigt auf dem
   Core „Vor Ort, offline-fähig“ an.

„Ein Frontend für alle Betriebsmodi“ bleibt erfüllt: gleicher Code und gleicher Build, nur die Origin ist eine andere.

## Verworfen

- **`fetch` auf `http://beerpong.local`**: technisch blockiert, siehe oben.
- **Core im Browser als Proxy-Ziel der Cloud** (Cloud leitet an den Core weiter): funktioniert nicht offline, und der
  Weg geht über das Internet, obwohl Spieler und Core im selben Raum sind.
- **Lokaler DNS-Override** (`beerpong.knoep.de` zeigt im Hallen-WLAN auf den Core): Das Zertifikat der Cloud-Domain müsste
  auf dem Core liegen, und Geräte mit eigenem DNS (DoH, mobile Daten) landen wieder in der Cloud.

## Folgen

- Pro Core ein DNS-Eintrag und ein API-Token für die DNS-01-Challenge (Secret auf dem Core, nicht im Repo).
- Login am Core: SMS geht offline nicht. Deshalb gibt es die Übergabe aus der Cloud (online) und für offline einen
  Turnier-PIN bzw. einen QR-Code am Tisch für Schiedsrichter (Phase 3).
