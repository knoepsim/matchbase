# MatchBase Edge: Abwägungen, Entscheidungen und Umsetzungsplan

Grundlage für die schriftliche Ausarbeitung der Studienarbeit (DHBW Karlsruhe, TINF24B5, Modul T3_3101).
Dieses Dokument hält fest, **welche Alternativen betrachtet wurden, nach welchen Kriterien abgewogen wurde und warum
die Entscheidung so gefallen ist**. Es ist bewusst kein Implementierungsbericht: Für jede Entscheidung stehen die
verworfenen Varianten mit Begründung daneben.

Stand: 23.10.2026. Ergebnis mehrerer Iterationen (siehe Kapitel 11, Entscheidungsverlauf).

---

## 1. Rahmen der Arbeit

**Titel (Themenmitteilung vom 07.10.2026):** Konzeption und prototypische Realisierung einer hybriden
Edge-Cloud-Architektur zur sensorbasierten Zustandserfassung in cyber-physischen Turniersystemen.

**Problemstellung:** Bindet man lokale Sensorik direkt an die Cloud an, entstehen Probleme bei Latenz,
Netzwerkstabilität und Offline-Fähigkeit. Untersucht wird, mit welchen Architekturkonzepten (z. B. einer Edge-Ebene)
sich diese lösen lassen, **ohne den bestehenden reinen Cloud-Betrieb einzuschränken**.

**Erwartetes Ergebnis:**

- systematische Evaluation von Architektur- und Kommunikationskonzepten
- darauf aufbauend eine hybride Lösungsarchitektur
- ein Proof of Concept (exemplarische Sensor-Hardware plus lokale Verarbeitungsebene)
- parallel ein konzeptioneller Vergleich von Sensoransätzen

**Geplantes Vorgehen (Themenmitteilung):**
1. Anforderungsanalyse
2. Evaluation und Konzeption der Architektur (Architekturmuster, Protokolle wie HTTP vs. MQTT)
3. Evaluation der Sensorik (konzeptionell: Integrationsaufwand, Fehleranfälligkeit)
4. Prototypische Realisierung und Validierung

**Methodischer Rahmen: Design Science Research** (Hevner et al. 2004; Hevner & Chatterjee 2010):

- Das Artefakt sind die Architektur und der PoC.
- Die Relevanz kommt aus einem realen Einsatzkontext (Turniere am Tuniberg).
- Die Rigorosität kommt aus der Abwägung gegen explizite Kriterien und Literatur.
- Die Evaluation erfolgt szenario- und messbasiert.
- Die Iterationen (Kapitel 11) sind die Build-Evaluate-Zyklen des DSR-Prozesses.

**Abgrenzung:** Die Turnierlogik selbst ist nicht Gegenstand der Arbeit. Sie existiert produktiv und wird wiederverwendet.

---

## 2. Begriffe

| Begriff | Bedeutung in dieser Arbeit |
|---|---|
| **MatchBase App** | Die PWA (Next.js-Frontend), die Nutzer im Browser öffnen. Dieselbe App läuft gegen Cloud und Edge. |
| **MatchBase Cloud** | Zentral deployte Webapp + Backend (FastAPI, Postgres). Bisher der einzige Betriebsort. |
| **MatchBase Edge** | Alles, was vor Ort beim Turnier steht: Edge-Knoten plus Tisch-Controller mit Sensorik. |
| **Edge-Knoten** | Der Rechner vor Ort ("Box"), der das Turnier lokal führt. Er betreibt dieselbe Software wie die Cloud im Edge-Modus, dazu MQTT-Broker und lokale Datenbank. |
| **Tisch-Controller** | Gerät am Spieltisch (ESP32 + RFID, Pi + Kamera, …). Es zählt Becher pro Seite und meldet den Stand per MQTT. |
| **Monitor** | Bildschirm am Edge-Knoten: Dashboard (welches Spiel an welchem Tisch), Status online/offline, QR-Code. |
| **Touch-Display** | Bedienplatz an der Box für die Turnierleitung. Fest als Gerät angemeldet, optional mit PIN. |
| **Schreiber** | Der Rechner, der die Daten eines Turniers ändern darf. Alle anderen lesen nur. |
| **Single Writer** | Genau ein Schreiber pro Turnier zu jedem Zeitpunkt. |
| **Multi-Master** | Mehrere Rechner dürfen gleichzeitig dasselbe ändern. Konflikte müssen dann aufgelöst werden. |
| **CRDT** | Conflict-free Replicated Data Type. Eine Datenstruktur, deren gleichzeitige Änderungen sich immer automatisch und konfliktfrei zusammenführen lassen (Zähler, Mengen, Text). |
| **Split Brain** | Zwei Knoten halten sich gleichzeitig für den Schreiber, weil sie sich gegenseitig nicht sehen. |
| **I-Konfluenz** | Eine Invariante ist I-konfluent, wenn zwei jeweils gültige, unabhängig entstandene Zustände zusammengeführt wieder gültig sind. Nicht I-konfluente Invarianten brauchen Koordination (Bailis et al. 2015). |
| **Identity Provider (IdP) / Authorization Server** | Stelle, die Nutzer authentifiziert, hier die Cloud. |
| **Relying Party / Client** | Anwendung, die sich auf den IdP verlässt, hier der Edge-Knoten. |
| **OIDC, PKCE** | OpenID Connect (Identitätsschicht auf OAuth 2.0). PKCE schützt den Authorization Code gegen Abfangen (RFC 7636). |
| **Mixed Content** | Eine HTTPS-Seite lädt Inhalte über HTTP. Browser blockieren das für aktive Inhalte (`fetch`). |
| **Local Network Access (LNA)** | Chrome-Mechanismus: Eine öffentliche Website darf Adressen im lokalen Netz erst nach Erlaubnis des Nutzers ansprechen. |
| **Captive Portal** | Ein WLAN, das Endgeräten nach dem Verbinden automatisch eine Seite anzeigt. |

---

## 3. Ausgangslage: was das bestehende System mitbringt

Diese Eigenschaften des Bestandssystems prägen die Abwägungen:

| Eigenschaft | Bedeutung für die Edge-Architektur |
|---|---|
| Ergebnisse sind ein **Ereignis-Log** (`results`: CREATED/MODIFIED/DELETED, nur Anhängen) | Gute Grundlage für Synchronisation (Ereignisse statt Zustände) |
| Jede sichtbare Änderung erhöht `tournaments.revision` und sendet ein Signal über **SSE** | Live-Updates und Änderungserkennung gibt es schon |
| Alle IDs sind **UUIDs** | Edge und Cloud können ohne Absprache Datensätze anlegen |
| **Stationsplaner**: Die API weiß, welches Spiel an welcher Station läuft | Ein Sensorstand lässt sich eindeutig einem Spiel zuordnen |
| **Spiele-Register** (`app/games.py`) mit Regeln je Spiel | Ort für "wann beendet ein Sensorstand das Spiel" |
| **Teams und Nutzer sind global** (ein Team spielt in mehreren Turnieren) | Das Edge darf nur turnierbezogene Daten zurückschreiben (Kapitel 8.6) |
| Login per **SMS-Code**, Access-Token **HS256** mit `SECRET_KEY`, Refresh-Token in der Cloud-DB | Ein Edge mit demselben Schlüssel könnte Cloud-Tokens fälschen: Auth muss neu gedacht werden (Kapitel 8.5) |
| Telefonnummer und E-Mail gibt die API nur dem Nutzer selbst aus, nicht in Team- oder Turnierantworten | Basis für die Datensparsamkeit gegenüber dem Edge |
| **Kein Service Worker**, Next.js mit Server-Rendering | Die Cloud-PWA lädt ohne Internet nicht; Offline-Fähigkeit "im Browser" ist nicht vorhanden |
| Cloud-Betrieb produktiv, Deployment per Docker-Images (GHCR) | Gleiche Images für Edge möglich |

---

## 4. Praxisrandbedingungen (Einsatzkontext)

Diese Beobachtungen aus dem realen Betrieb fließen als Annahmen in die Anforderungen ein:

- **Ort:** ländliche Region (Tuniberg), Mobilfunk nicht überall stabil.
- **Uplink vor Ort:** drei SIM-Karten verschiedener Netzbetreiber. Ausfälle sind selten und dauerten bisher 20–30 s.
  Der vollständige Ausfall ist der **theoretische Fall, den die Architektur abdecken soll**. Genau das ist
  Gegenstand der Arbeit.
- **Spieler** haben fast immer mobiles Internet und nutzen die App wenig: Spielplan, eigenes Spiel. Sie wechseln
  ungern in ein fremdes WLAN.
- **Staff** (Admin, Manager, Schiedsrichter): wenige, vorher bekannte Personen. Sie schreiben (Ergebnisse, Spiele
  starten).
- **Veranstalter** stehen am Turniertag unter Zeitdruck. Jeder manuelle Einrichtungsschritt ist eine Fehlerquelle.
- **Hardware fällt aus:** Kabel gezogen, Getränk verschüttet, Überhitzung.
- **Spätere Nutzung durch fremde Veranstalter** mit eigenen Edge-Knoten ist geplant. Das Edge ist damit **nicht
  vertrauenswürdig** (Kapitel 8.6).

---

## 5. Anforderungen (Vorschlag für Kapitel "Anforderungsanalyse")

Die Zielwerte sind Vorschläge und in der Arbeit zu begründen. Die IDs dienen der Rückverfolgbarkeit in der Evaluation.

### Funktional

| ID | Anforderung |
|---|---|
| FA-01 | Tisch-Controller melden die Anzahl der Becher je Tischseite. Die Sensortechnik ist für die übrigen Komponenten unsichtbar. |
| FA-02 | Das Edge ordnet einen Stand dem Spiel an der Station zu und leitet daraus einen Ergebnisvorschlag ab, sobald der Stand das Spiel beendet. |
| FA-03 | Ein Mensch mit Rolle bestätigt oder korrigiert den Vorschlag. Das Ergebnis trägt seine Herkunft (`source = sensor/manual`). |
| FA-04 | Fällt der Uplink aus, läuft das Turnier lokal weiter: Ergebnisse eintragen, Stationsplanung, Dashboard, Sensorik. |
| FA-05 | Die Cloud spiegelt den Turnierstand. Bei fehlender Verbindung zum Edge zeigt sie einen Hinweis und sperrt Eingaben. |
| FA-06 | Lokal vor Ort kann jeder das Turnier ohne Anmeldung lesen. |
| FA-07 | Staff meldet sich am Edge über die Cloud an (solange online). Die lokale Session übersteht einen Ausfall. |
| FA-08 | Der Monitor zeigt den Verbindungsstatus und im Offline-Fall einen QR-Code zum lokalen Zugang. |
| FA-09 | Turniere ohne Edge laufen in der Cloud unverändert. |
| FA-10 (später) | Eingaben in der Cloud werden an das Edge weitergeleitet. Die Cloud bestätigt erst nach Rückmeldung des Edge. |
| FA-11 (später) | Fällt der Edge-Knoten aus, kann der Veranstalter das Turnier mit dem letzten synchronisierten Stand in die Cloud zurückholen. |

### Nicht-funktional

| ID | Anforderung | Zielwert (Vorschlag) |
|---|---|---|
| NFA-01 Latenz lokal | Sensorstand → Anzeige am Monitor/Display | ≤ 1 s (p95) |
| NFA-02 Latenz Spiegel | Änderung am Edge → sichtbar in der Cloud (online) | ≤ 5 s (p95) |
| NFA-03 Offline-Dauer | Turnier läuft ohne Uplink weiter | ≥ 60 min ohne Funktionsverlust vor Ort |
| NFA-04 Datenverlust | Bei Uplink-Ausfall gehen keine Ergebnisse oder Messwerte verloren | 0 |
| NFA-05 Wiederanlauf | Nach Rückkehr des Uplinks ist die Cloud aktuell | ≤ 30 s |
| NFA-06 Neustart Edge | Nach Stromausfall bedienbar, ohne Datenverlust | ≤ 2 min |
| NFA-07 Cloud unverändert | Regressionstests der Cloud bleiben grün; ohne Edge kein Verhaltensunterschied | 100 % |
| NFA-08 Datenschutz | Auf dem Edge liegen keine Kontaktdaten (Telefon, E-Mail) | 0 Felder |
| NFA-09 Sicherheit | Ein kompromittiertes Edge kann keine Cloud-Identitäten fälschen und keine fremden Turniere ändern | nachgewiesen per Bedrohungsmodell und Test |
| NFA-10 Einrichtung | Inbetriebnahme durch Veranstalter ohne Terminal | ≤ 15 min |
| NFA-11 Robustheit Sensorik | Erkennungsrate unter Störfaktoren (siehe Kapitel 9) | im Sensorvergleich festzulegen |

---

## 6. Bewertungskriterien

Alle Architekturvarianten werden nach denselben Kriterien bewertet:

1. **Betrieb vor Ort ohne Internet** (FA-04, NFA-03)
2. **Konsistenz des Turnierbaums** (keine widersprüchlichen Ergebnisse)
3. **Cloud-Betrieb unverändert** (FA-09, NFA-07)
4. **Usability für Spieler**: Muss sich ihr Verhalten ändern (WLAN, Adresse, Login)?
5. **Usability für Veranstalter**: Aufbau, Fehlersuche, Verhalten bei Störungen
6. **Verhalten bei Ausfall von Komponenten**: Uplink, Edge-Knoten, Tisch-Controller, Broker
7. **Sicherheit und Datenschutz** bei fremd betriebenen Edge-Knoten
8. **Komplexität und Aufwand** (Implementierung, Betrieb, Updates)
9. **Latenz** Sensor → Anzeige
10. **Eignung als Forschungsbeitrag** (Edge Computing, verteilte Systeme)

---

## 7. Architekturvarianten und Abwägung

### 7.1 Betrachtete Varianten

| ID | Variante | Kurzbeschreibung |
|---|---|---|
| V0 | **Direktanbindung** | Tisch-Controller senden direkt an die Cloud (HTTP/MQTT über Internet). Kein Edge. |
| V1 | **Voller Edge mit Discovery in der Cloud-PWA** (ursprüngliches Konzept) | Die PWA aus der Cloud fragt `http://beerpong.local/api/info` ab und stellt ihre API auf den Edge um. |
| V2 | **Sensor-Gateway** | Das Edge sammelt Tische ein, verarbeitet vor, puffert und sendet an die Cloud. Die Cloud bleibt Schreiber, alle Nutzer arbeiten in der Cloud. |
| V3 | **Offline-first PWA ohne Server vor Ort** (local-first im Browser) | Service Worker + IndexedDB auf jedem Gerät, späterer Abgleich |
| V4 | **Multi-Master mit CRDT/Sync-Engine** | Cloud und Edge schreiben gleichzeitig, Konfliktauflösung automatisch |
| V5 | **Datenbank-Replikation** | Postgres-Replikation zwischen Cloud und Edge |
| V6 | **Edge als Single Writer, Cloud als Spiegel** (gewählt) | Das Edge führt das Turnier (Turnierlogik, Sensorik, Monitor, Display). Die Cloud spiegelt und leitet später Eingaben weiter. |

### 7.2 Bewertung

| Kriterium | V0 | V1 | V2 | V3 | V4 | V5 | **V6** |
|---|---|---|---|---|---|---|---|
| Betrieb ohne Internet | ❌ | ⚠️ technisch blockiert (7.3) | ❌ nur Sensoren puffern | ⚠️ Geräte isoliert | ✅ | ✅ | ✅ |
| Konsistenz Turnierbaum | ✅ | ✅ | ✅ | ❌ | ❌ | ⚠️ Tabellen- statt Turnierebene | ✅ |
| Cloud unverändert | ⚠️ Sensor-Endpunkte | ⚠️ | ✅ | ⚠️ Client-Datenschicht | ❌ Datenschicht neu | ⚠️ Infrastruktur | ✅ zusätzliche Endpunkte, Sperre für Edge-Turniere |
| Spieler-Usability | ✅ | ❌ WLAN/Adresse wechseln | ✅ | ✅ | ⚠️ | ⚠️ | ✅ Cloud wie immer, offline Monitor/QR |
| Veranstalter-Usability | ⚠️ jeder Tisch braucht Internet | ❌ viele Einrichtungsschritte | ✅ | ⚠️ | ❌ Konflikte erklären | ❌ DB-Betrieb | ✅ mit Ersteinrichtung per QR |
| Ausfall Edge-Knoten | – | ❌ | ✅ Rückfall auf manuell | – | ✅ | ⚠️ | ⚠️ Rückholen nötig (FA-11) |
| Ausfall Uplink | ❌ | ✅ | ❌ | ⚠️ | ✅ | ⚠️ | ✅ |
| Sicherheit bei fremden Edges | ⚠️ Geräte-Auth je Tisch im Internet | ⚠️ | ✅ | ✅ | ⚠️ Nutzerdaten repliziert | ❌ ganze DB repliziert | ✅ Datensparsamer Snapshot |
| Aufwand | gering | hoch | gering | mittel | sehr hoch | mittel, Betrieb schwer | mittel–hoch |
| Latenz Sensor → Anzeige | ❌ über Internet | ✅ | ⚠️ über Internet | – | ✅ | ✅ | ✅ lokal |
| Forschungsbeitrag | gering | mittel | mittel | mittel | hoch, sprengt Rahmen | gering | hoch |

### 7.3 Begründungen im Einzelnen

**V0 Direktanbindung:** Jeder Tisch braucht eine Internetverbindung. Latenz und Ausfall hängen direkt am Mobilfunk.
Vorverarbeitung (Entprellen, Kamera-Auswertung) müsste auf jedem Controller oder in der Cloud erfolgen.
Widerspricht dem Leitgedanken des Ausgangskonzepts ("nicht Sensor → Cloud, sondern Sensor → Edge → Cloud").

**V1 Discovery in der Cloud-PWA (ursprüngliches Konzept) scheitert an Browserregeln:**
1. **Mixed Content:** Eine Seite von `https://…` darf kein `fetch` an `http://…` machen. Ausgenommen sind nur
   `localhost`/`127.0.0.1`, nicht `.local`.
2. **Local Network Access:** Chrome verlangt eine Nutzererlaubnis, bevor eine öffentliche Seite lokale Adressen
   anspricht.
3. **Cookies:** Session-Cookies der Cloud gelten nicht für eine andere Origin. Cookies einer fremden Origin
   (Third-Party) blockiert Safari vollständig.
4. **Offline:** Ohne Service Worker und bei Server-Rendering lädt die Cloud-PWA ohne Internet gar nicht.
5. **mDNS:** `.local`-Namen lösen auf Android im Browser nicht zuverlässig auf.

Daraus folgt eine Regel: Ein Wechsel zum Edge ist nur als **Navigation auf eine eigene Origin** des Edge robust
umsetzbar, nicht als API-Umschaltung (Kapitel 8.7).

**V2 Sensor-Gateway:** In der Praxis die robusteste Variante. Kein Rollenwechsel, keine Synchronisation, keine
Offline-Auth, und ein Edge-Ausfall fällt sanft auf manuelle Eingabe zurück. Sie erfüllt aber die in der
Problemstellung geforderte **Offline-Fähigkeit nur auf Sensorebene** (puffern und nachreichen). Bei Internetausfall
steht das Turnier. Deshalb nicht gewählt, aber **wichtigste Vergleichsvariante** in der Evaluation. Ihr Prinzip
"Sensorik ist eine Verbesserung, keine Voraussetzung" wird in V6 übernommen: Manuelle Eingabe bleibt immer möglich.

**V3 Offline-first PWA (Kleppmann et al. 2019):** Erfüllt die Local-first-Ideale (Offline, Datenhoheit) am Gerät.
Ein Turnier braucht aber einen **gemeinsamen** Stand für mehrere Schiedsrichter und Sensoren. Ohne Server vor Ort
sehen sich die Geräte offline gegenseitig nicht, und Sensoren brauchen ohnehin einen lokalen Empfänger (Broker).

**V4 Multi-Master/CRDT (Shapiro et al. 2011):** CRDTs garantieren Zusammenführung, aber nicht die Einhaltung
fachlicher Invarianten. Der Turnierbaum hat **nicht I-konfluente Invarianten** (Bailis et al. 2015):
- pro Spiel höchstens ein gültiges Ergebnis
- der Sieger rückt ins Folgespiel
- ein Ergebnis darf nicht geändert werden, wenn das Folgespiel schon entschieden ist

Zwei offline gültige Änderungen ("A gewinnt" an einem Ort, "B gewinnt" am anderen) ergeben zusammengeführt einen
ungültigen Zustand. Ein CRDT löst das, indem es eine Seite verwirft (z. B. Last-Write-Wins): ein Ergebnis verschwindet
stillschweigend, und das Folgespiel wurde womöglich mit dem falschen Team gespielt. **Diese Invarianten brauchen
Koordination. Die einfachste Form davon ist ein einziger Schreiber.**

Anerkennung: Das Ergebnis-Log selbst (nur Anhängen) ist CRDT-artig und passt zu Local-first. Die Ablehnung bezieht
sich auf die Invarianten des Baums, nicht auf Local-first allgemein. Das ist der Kern der wissenschaftlichen
Begründung.

**V5 DB-Replikation:** Repliziert Tabellen statt fachlicher Einheiten (Turniere). Sie würde globale Nutzerdaten mit
Kontaktdaten auf fremde Edges bringen (verletzt NFA-08), braucht eine stabile Verbindung zur Einrichtung und ist im
Störfall schwer bedienbar.

**V6 Edge als Single Writer (gewählt):**
- **Vorteile:**
  - echter Offline-Betrieb vor Ort
  - keine Konflikte
  - Spieler bleiben in der Cloud
  - Latenz lokal
  - starker Forschungsbezug (Edge Computing, Konsistenzmodelle, Offline-first am Edge)
- **Erkaufte Nachteile:**
  - Der Edge-Knoten ist für das laufende Turnier ein **Single Point of Failure**. Gegenmaßnahmen: robuste Hardware,
    lokale Persistenz, Rückholen (FA-11).
  - Cloud-Eingaben gehen nur, solange das Edge erreichbar ist.

### 7.4 CAP-Einordnung

Bei einer Netzpartition zwischen Edge und Cloud (Gilbert & Lynch 2002) wählt V6:

- **vor Ort:** Konsistenz **und** Verfügbarkeit, denn der einzige Schreiber ist lokal
- **in der Cloud:** Konsistenz statt Verfügbarkeit. Die Cloud bleibt lesbar, aber veraltet und gesperrt, mit Hinweis.

Das ist bewusst gewählt: Wer vor Ort ist, braucht das System. Wer fern ist, kann warten.

### 7.5 Szenariobasierte Bewertung (Ausfälle)

Szenarien im Stil einer ATAM-Bewertung (Kazman et al. 2000). V2 und V6 im Vergleich:

| Szenario | V2 Sensor-Gateway | V6 Edge als Single Writer |
|---|---|---|
| Normalbetrieb | alle in der Cloud | für Nutzer gleich; Staff-Eingaben in der Cloud werden an das Edge weitergeleitet (FA-10, später) bzw. im PoC am Edge eingetragen |
| Uplink 30 s weg | Eingaben stocken, Sensoren puffern | vor Ort unbemerkt, Cloud zeigt kurz "offline" |
| Uplink 60 min weg | Turnier steht (Papier) | Turnier läuft lokal weiter (Display, lokale Sessions, Monitor) |
| Uplink wackelt | Eingabe geht, wenn das Handy Netz hat | Cloud-Eingabe mal gesperrt, mal nicht; Display und lokale Sessions immer |
| Edge-Knoten fällt aus | weiter wie heute, nur ohne Sensoren | Turnier steht bis zum Rückholen in die Cloud (FA-11) |
| Tisch-Controller fällt aus | manuelle Eingabe | manuelle Eingabe |
| Broker-Neustart | Controller verbinden neu, letzter Stand per `retain` | gleich |

Das Ergebnis hängt an der Frage, **was wahrscheinlicher ist: Internetausfall oder Ausfall der Box**. Das Internet vor
Ort ist nicht beeinflussbar, die Box schon (Hardware, Strompuffer, Test). Mit FA-11 als Absicherung überwiegen die
Vorteile von V6.

---

## 8. Teilentscheidungen

### 8.1 Kommunikation Tisch-Controller → Edge-Knoten

Kriterien: Ressourcen auf dem Mikrocontroller, Zustellgarantien, Wiederverbindung, letzter Zustand nach Neustart,
Fan-out an mehrere Empfänger, Werkzeugunterstützung (Naik 2017).

| Protokoll | Pro | Contra |
|---|---|---|
| HTTP-Polling (Edge fragt Tische) | einfach, bekannt | Latenz = Poll-Intervall, Last durch leere Anfragen, Edge muss Tische kennen |
| HTTP-Push (Tisch → Edge) | einfach | jede Nachricht eine Verbindung, keine Zustellgarantie, kein "letzter Zustand" für Neustarter |
| WebSocket | bidirektional, geringe Latenz | eigenes Nachrichtenprotokoll nötig, Wiederverbindung selbst bauen |
| CoAP (RFC 7252) | sehr leichtgewichtig, UDP, Observe | weniger verbreitet, Werkzeuge, Broker-Muster fehlt |
| AMQP | mächtige Garantien | schwergewichtig für ESP32 |
| **MQTT** (OASIS 2019) | Publish/Subscribe über Broker, QoS 0/1/2, **Retained Messages** (letzter Stand für Neustarter), Last Will, leichtgewichtig auf ESP32, breite Werkzeugunterstützung | zusätzlicher Broker (Mosquitto) nötig |

**Entscheidung: MQTT** (QoS 1, `retain`). Ausschlaggebend:
- Retained Messages liefern nach einem Neustart des Edge sofort den Stand aller Tische.
- Der Broker entkoppelt Sender und Empfänger.
- Bewährter Standard für IoT-Telemetrie.

**Edge-Knoten → Cloud:** nur **ausgehend über HTTPS bzw. WebSocket auf Port 443**. Das funktioniert hinter jedem NAT
und jeder Firewall, braucht keine offenen Ports und kein Zertifikat für eingehende Verbindungen. Die Cloud spricht das
Edge (Weiterleitung, FA-10) über diese bestehende Verbindung an.

### 8.2 Sensor-Abstraktion (MQTT-Vertrag v1)

- **Topic** `tables/{deviceId}/state`. Die **Identität steckt im Topic**, nicht in der Nachricht. Mit Broker-ACLs darf
  jeder Controller nur unter seinem eigenen Topic schreiben, kann sich also nicht als anderer Tisch ausgeben.
- **Nachricht** `{"v":1,"leftCups":4,"rightCups":2,"seq":118,"sensor":"rfid"}`. Unbekannte Felder werden ignoriert
  (Vorwärtskompatibilität).
- **Kein Spielwissen am Tisch:** Der Controller kennt weder Turnier noch Teams noch Regeln. Ob ein Stand das Spiel
  beendet, entscheidet das Edge über die Spielregel (`sensed_end` in `app/games.py`).
- **Senden** bei jeder Änderung plus Heartbeat (≤ 10 s). Nach 30 s Stille gilt der Controller als offline.
- **Duplikate:** Gleiche `seq` wird verworfen (QoS 1 kann doppelt zustellen). Gleicher Stand wird nicht als neuer
  Messwert protokolliert.
- **Begründung der Abstraktion:** Die Sensortechnik ist austauschbar (RFID, Kamera, Hall). Der Sensorvergleich lässt
  sich mit identischer Verarbeitung durchführen.

### 8.3 Sensor schlägt vor, Mensch bestätigt

- **Alternative "Sensor schreibt Ergebnis automatisch":** verworfen. Ein Fehlstand (umgestoßener Becher, verdeckter
  Sensor, Flackern) würde sofort das falsche Team weiterschicken. Die Korrektur kaskadiert über die Folgespiele.
- **Entscheidung:** Der Sensor liefert einen **Vorschlag**, ein Mensch mit Rolle bestätigt mit einem Tipp. Alle
  Ergebnisregeln gelten unverändert.
- **Nutzen für die Evaluation:**
  - `source = sensor` vs. `manual`
  - unverändert übernommen vs. korrigiert, ergibt die **Erkennungsrate**
  - Zeit vom letzten Becher bis zum Ergebnis, ergibt die **Reaktionszeit**
- **Ausbaustufe:** ein Vollautomatik-Modus pro Turnier ("nach N Sekunden stabil automatisch übernehmen"). Kein Umbau
  nötig.

### 8.4 Konsistenz und Synchronisation

- **Single Writer pro Turnier** (Begründung in 7.3, V4).
- **Übergabepunkte:**
  - Anmeldung und Check-in laufen in der Cloud (Spieler sind online).
  - Beim **Turnierstart** wird das Edge zum Schreiber: Die Auslosung erfolgt auf dem Edge, die Cloud bekommt den
    Snapshot.
  - Am **Turnierende**: letzter Sync, dann Rückgabe an die Cloud als Archiv.
  - Keine Übergabe mitten im Turnier, außer im Notfall (FA-11).
- **Sync Edge → Cloud:**
  - **Outbox** in derselben Transaktion wie die Änderung, mit Revision und in Reihenfolge.
  - Übertragung, sobald online.
  - Die Cloud wendet Ereignisse über dieselben Fachregeln an wie direkte Eingaben.
- **Cloud während Edge-Betrieb:** spiegelt lesend. Bei fehlender Verbindung erscheint ein Hinweis ("Turnier läuft vor
  Ort offline weiter, Stand von 14:32"), Eingaben sind gesperrt.
- **Weiterleitung Cloud → Edge (FA-10, später):**
  - synchron: Die Cloud meldet "gespeichert" erst nach Bestätigung des Edge
  - jede Aktion mit eindeutiger ID (idempotent bei Wiederholung)
  - mit Zeitlimit und klarer Fehlermeldung
  - **kein Zwischenpuffer in der Cloud**, sonst gäbe es zwei Schreiber
- **Verworfen: dynamischer Schreiberwechsel** ("online schreibt die Cloud, offline übernimmt das Edge"). Beide Seiten
  würden unabhängig über ihre Rolle entscheiden. Bei einer Teilstörung (das Edge sieht die Cloud nicht, einzelne Handys
  schon) entsteht **Split Brain** mit genau den Konflikten, die der Single Writer verhindern soll.
- **Verworfen: "Cloud nur lesend, Eingaben nur am Edge"** als Dauerlösung. Wenn alle normalerweise die Cloud nutzen,
  wäre der Staff im Normalfall eingeschränkt. Für den PoC ist es zulässig, als Zielbild nicht.

### 8.5 Authentifizierung und Autorisierung

**Problem:**
- Offline ist keine SMS möglich.
- Cloud-Cookies gelten nicht für das Edge.
- Eine Prüfung der HS256-Tokens bräuchte den `SECRET_KEY` auf dem Edge, und damit könnte das Edge Cloud-Tokens
  **fälschen**.

**Wer braucht vor Ort eine Anmeldung?**

| Gruppe | Tätigkeit | Anmeldung |
|---|---|---|
| Zuschauer, Spieler | ansehen | **keine**: lokal sieht jeder das Turnier (physische Anwesenheit) |
| Admin, Manager, Schiedsrichter | schreiben | ja, wenige und vorher bekannte Personen |
| Touch-Display | schreiben | als Gerät ("Turnierleitung (Display)"), optional mit PIN |

**Betrachtete Verfahren:**

| Verfahren | Bewertung |
|---|---|
| A. Gemeinsamer `SECRET_KEY` auf dem Edge | **ausgeschlossen**: Das Edge könnte Cloud-Tokens fälschen. |
| B. Asymmetrisch signierter "Venue-Ausweis" aus der Cloud | offline prüfbar, personenbezogen; Übergabe auf die Edge-Origin umständlich |
| C. Geräte-Kopplung per QR am Display | voll offline; wegen der Vorab-Anmeldung (unten) nicht nötig |
| D. Turnier-PIN | einfach, aber nicht personenbezogen, erratbar, schwer zu wechseln |
| E. Tisch-Tablet als Gerät | passt zum Sensor-Flow, nur tischbezogen |
| F. SMS über GSM-Modem am Edge | Telefonnummern auf dem Edge (verletzt NFA-08), Hardware |
| G. Passkeys (WebAuthn) | sicher, offline prüfbar; Registrierung vorab und Fallback nötig, höherer Aufwand |
| **H. OIDC: Cloud als IdP, Edge als Relying Party** | **gewählt** |

**Entscheidung H:**
1. Staff öffnet die Edge-Seite und klickt "Turnierleitung anmelden". Der Button ist dezent und nicht verpflichtend.
2. Authorization Code Flow mit **PKCE** über die Cloud. Ist der Nutzer dort angemeldet, reicht "Zulassen".
3. Das Edge löst den Code bei der Cloud ein. Das ID-Token ist **asymmetrisch signiert**, das Edge kennt nur den
   öffentlichen Schlüssel (JWKS).
4. Das Edge legt eine **eigene lokale Session** an. Die Rechte prüft es mit den Rollen aus dem Turnier-Snapshot.
5. Offline läuft die Session weiter. **Neue Anmeldungen gibt es nur online.**

**Organisatorische Regel:** Staff meldet sich **vorab** lokal an. Wer eine Funktion hat, ist dafür verantwortlich.
Begleitende Hilfen:
- Das Edge zeigt dem Admin "lokal angemeldet: 2 von 3 Schiedsrichtern".
- Beim Start auf dem Edge erhalten alle mit Rolle eine Erinnerung in der Cloud-App.
- Die Session gilt bis Turnierende plus Puffer und wird offline verlängert.
- Das Touch-Display bleibt als Rückfallebene.

**Externer IdP (Authentik, Keycloak, Zitadel) vs. integrierter Authorization Server:**

| Aspekt | Externer IdP | Integriert in FastAPI |
|---|---|---|
| Passwortloser Login (SMS-/E-Mail-Code) | kein Standardfall, Nachbau in Flows/Erweiterungen | vorhanden |
| Bestandsnutzer | Migration nötig | keine Änderung |
| Login-Oberfläche | IdP-Seiten anpassen | eigene App |
| Betrieb | zusätzlicher Dienst (Server, Worker, DB), Updates, Härtung | nichts Neues |
| Bedarf | SSO, Richtlinien, viele Fremdanwendungen | wenige eigene Clients (Edge-Knoten) |
| Risiko | geprüfte Implementierung | Eigenbau, aber klein und mit festen Regeln |

**Entscheidung: integrierter, schlanker OIDC-Teil in FastAPI.** Er besteht aus:
- `/.well-known/openid-configuration` und `/jwks`
- `/oauth/authorize` (nutzt die bestehende Session)
- `/oauth/token` (Client-Authentisierung mit dem Box-Schlüssel)
- Box-Registry (beanspruchen, sperren)

Feste Regeln:
- PKCE S256 ist Pflicht.
- Die Rücksprungadresse muss exakt passen.
- Der Code gilt nur einmal und höchstens 60 s.
- Der private Schlüssel liegt nur in der Cloud.
- Das ID-Token ist an die Box gebunden (`aud`).

Orientierung bietet RFC 9700 (OAuth 2.0 Security Best Current Practice). **Umkehrbarkeit:** Das Edge spricht nur
Standard-OIDC. Ein späterer Wechsel auf einen externen IdP ändert nur die Cloud-Seite.

**Login-Methode der Cloud:** Für die Edge-Sicherheit ist sie unerheblich, denn das Edge sieht nur das Ergebnis.
- **SMS-Code** (Bestand) und **E-Mail-Code** funktionieren gleichwertig.
- **Magic Link** hat beim Edge-Login eine Tücke: Er öffnet sich oft in einem anderen Browser als dem, der den Flow
  gestartet hat, und dann passen PKCE/State nicht. Ein 6-stelliger Code vermeidet das.
- **Social Login** ist problemlos.
- **Passkeys** sind eine Option für später.

### 8.6 Sicherheit und Datenschutz

**Bedrohungsmodell:** Edge-Knoten werden später von fremden Veranstaltern betrieben. Der Betreiber hat Vollzugriff auf
die Box (Datenbank, Schlüssel, Code). **Grundsatz: Ein böswilliger Betreiber darf nicht mehr sehen oder tun, als er
als Admin seines Turniers in der Cloud ohnehin darf.**

**Daten auf dem Edge:**

| Daten | Edge | Begründung |
|---|---|---|
| Turnier, Spiele, Ergebnisse, Stationen | ✅ | Turnierlogik |
| Teams und Spielernamen dieses Turniers, Nutzer-IDs, Rollen | ✅ | sieht der Admin in der Cloud auch |
| Telefonnummer, E-Mail | ❌ | Datensparsamkeit (NFA-08) |
| andere Turniere, Teams, Nutzer | ❌ | nicht nötig |
| Cloud-Sessions, Refresh-Tokens, Login-Codes | ❌ | der Code-Flow gibt sie nie heraus |
| Signaturschlüssel der Cloud | ❌ | das Edge prüft nur |
| Sensordaten | ✅ | nicht personenbezogen |

**Maßnahmen:**

1. **Snapshot aus denselben Antwortmodellen** wie die Admin-Sicht der Cloud. Nie ein Tabellen-Dump, damit neue
   Spalten nicht unbemerkt mitgehen.
2. **Rechte der Box in der Cloud:**
   - nur übergebene Turniere synchronisieren
   - nur Codes für die eigene Rücksprungadresse einlösen
   - keine Nutzer-Endpunkte, keine fremden Turniere
3. **Nur turnierbezogene Daten zurückschreiben** (Spiele, Ergebnisse, Stationen, Rollen, Teilnahme). Keine
   globalen Teams oder Nutzerprofile, denn eine Box könnte sonst Teams in fremden Turnieren verändern.
4. **Gleiche Fachregeln** für synchronisierte Änderungen wie für direkte Eingaben.
   Restrisiko: Ein Betreiber kann sein **eigenes** Turnier verfälschen. Das darf er als Admin ohnehin.
5. **Login-Phishing verhindern:**
   - Die Cloud stellt Codes nur für Nutzer aus, die eine Rolle in einem Turnier auf dieser Box haben.
   - Die Zustimmungsseite nennt Box und Veranstalter.
   - Das ID-Token enthält nur ID und Name.
6. **ID-Token ist kein Cloud-Zugang:** anderer Typ, anderer Empfänger, die Cloud-API lehnt es ab.
7. **Weiterleitung (FA-10):** Die Cloud schickt nur eine kurzlebige signierte Aussage (Nutzer, Aktion, Aktions-ID,
   Ziel-Box, ≤ 30 s), nie das Token des Nutzers.
8. **Widerruf:** Box in der Cloud sperren. Ihr Schlüssel wird ungültig, und die Ergebnisse des laufenden Turniers
   werden zur Prüfung angezeigt.
9. **Löschen:** Nach der Rückgabe löscht die Box den Snapshot.
10. **Optional:** **paarweise Nutzer-IDs** (OIDC pairwise subject). Dann können Betreiber ihre Daten nicht über IDs
    verknüpfen.
11. **Recht:** Bei fremden Betreibern ist die Verantwortlichkeit zu regeln (Auftragsverarbeitung). Das ist eine
    organisatorische, keine technische Frage.

**Folge eines kompromittierten Edge:**
- **Kann:** das eigene Turnier verfälschen, die Namen der Beteiligten lesen, lokale Sessions missbrauchen.
- **Kann nicht:** Kontaktdaten lesen, sich als Nutzer an der Cloud anmelden, andere Turniere oder globale Teams ändern.

### 8.7 Zugang vor Ort

**Erkennung des Edge durch die PWA, betrachtete Wege:**

| Weg | Bewertung |
|---|---|
| API-Umschaltung in der Cloud-PWA | **verworfen**: Cookies fremder Origin, kein Offline-Laden, LNA (Kapitel 7.3, V1) |
| Navigation mit aktivem Test (`fetch` auf die Edge-Adresse) | LNA-Abfrage in Chrome, CORS, Browser verhalten sich unterschiedlich |
| Hinweis über gleiche öffentliche IP (Cloud vergleicht IP von Nutzer und Edge) | keine Browser-Abfrage, aber unscharf (Carrier-NAT) |
| **QR-Code am Monitor + WLAN** | **gewählt**: robust, offline-fähig, ohne Technikrisiko |

**Entscheidung: kein automatischer Wechsel.** Der Nutzer wechselt bewusst:
- **Normalfall:** Alle nutzen die Cloud.
- **Offline-Fall:** Der Monitor zeigt "Offline – Turnier läuft weiter" mit QR-Code. Bevorzugt als **WLAN-QR**
  (`WIFI:S:…;T:WPA;P:…;;`), dazu ein **Captive Portal**, das im Offline-Fall die Turnierseite von selbst öffnet.
  Online lässt das WLAN die Prüfung der Geräte durch und verhält sich normal.
- **Die Cloud-App** zeigt im Ausfall den Hinweis mit WLAN-Name und dem Verweis auf den Monitor.

Begründung: Eine bewusste Umschaltung ist leichter zu erklären, zu testen und zu betreiben als eine automatische.

**Das Edge bedient genau ein Turnier:**
- Jede Adresse führt zu `/t/<turnier>`.
- Es gibt keine weiteren Bereiche (Profile, Listen).
- Ein Banner zeigt "Lokal verbunden · Box …", dazu ein Link zur Cloud.

Folgen: weniger Angriffsfläche, weniger Code, klares Nutzerverständnis (lokal = dieses Turnier).

**Praktische Einschränkungen, für die Arbeit festzuhalten:**
- **HTTPS am Edge:**
  - Zielbild: echter Name, Zertifikat per DNS-01. Der lokale DNS-Server (Router) löst den Namen offline auf, ein
    öffentlicher Eintrag deckt Geräte mit DNS-over-HTTPS ab.
  - Im PoC genügt HTTP im verschlüsselten WLAN. Das ist eine bewusste Abweichung vom Zielbild, denn RFC 9700 empfiehlt
    HTTPS-Rücksprungadressen.
- **Android und WLAN ohne Internet:** Bei längeren Ausfällen kann Android Daten über Mobilfunk leiten. Dann ist das
  Edge vom Handy aus nicht erreichbar. Gegenmittel: "WLAN beibehalten" bestätigen oder mobile Daten aus. Bei kurzen
  Ausfällen ist das unkritisch.
- **Installierte PWA:** Die Homescreen-App gehört zur Cloud-Origin. Die Edge-Seite öffnet sich darin als fremde Seite.
- **Captive-Portal-Fenster** sind Mini-Browser mit eingeschränkten Cookies. Zum Ansehen genügt das, Staff nutzt den
  normalen Browser.
- **Engpass am Display:** Offline laufen Eingaben über das Display und vorab angemeldete Handys. Bis etwa 10 Tische ist
  das unkritisch, weil der Sensorvorschlag den Aufwand auf einen Tipp reduziert.

### 8.8 Deployment und Betrieb

**Grundsatz:** **dieselben Images** für Cloud und Edge. Die Rolle kommt zur Laufzeit (`NODE_ROLE`, `/info`), nicht
beim Build. Für die Web-App heißt das: keine Rolle in `NEXT_PUBLIC_*`-Variablen.

**Eingang: ein Reverse Proxy vor Web und API, in Cloud und Edge gleich** (`deploy/caddy/Caddyfile`):
- Der Browser sieht nur eine Origin. `/api/*` geht ohne Präfix an die API, alles andere an die Web-App.
- Folgen der gemeinsamen Origin:
  - Session-Cookies sind First-Party und HttpOnly.
  - Es braucht kein CORS, und die CSP kommt mit `connect-src 'self'` aus.
  - Die API ist nie direkt erreichbar.
  - Am Edge genügen eine Adresse und ein Zertifikat. Davon hängen QR-Code, Captive Portal und OIDC-Rücksprungadresse
    ab (8.5, 8.7).
- Bisher leitete Next.js `/api` per `rewrites` weiter. Das bleibt nur für die Entwicklung (`pnpm dev`). Im Betrieb
  hätte es zwei Nachteile, die ein eigener Proxy vermeidet, weil er das Routing von der Anwendung trennt:
  - Jeder API-Aufruf geht über den Node-Prozess der Web-App.
  - Lange Event-Streams (SSE) brauchen eigene Timeouts.
- **Eine Konfiguration für beide Rollen:** Nur `SITE_ADDRESS` unterscheidet die Fälle.
  - `:80` bedeutet HTTP hinter einem Tunnel, der TLS abschließt (Cloudflare Tunnel in der Cloud), oder HTTP im
    PoC-WLAN.
  - Ein Domainname bedeutet: Der Proxy holt das Zertifikat selbst.
  - Das hält Cloud und Edge im Verhalten gleich (NFA Wartbarkeit) und lässt Dritte die Cloud ohne Cloudflare betreiben.

| Proxy | Stärken | Schwächen für diesen Einsatz |
|---|---|---|
| **Caddy** (gewählt) | automatisches TLS inkl. Erneuerung, DNS-01 über Module, SSE ohne Zusatzkonfiguration, kurze Konfiguration mit Umgebungsvariablen, ein statisches Binary | DNS-01 braucht ein eigenes Image mit Provider-Modul (`xcaddy`) |
| Traefik | Routen aus Docker-Labels, Dashboard, ebenfalls ACME | braucht Zugriff auf den Docker-Socket (am Edge eines Dritten ein unnötiges Risiko), Mehrwert erst bei vielen, wechselnden Diensten |
| nginx | verbreitet, sehr performant | Zertifikate nur mit Certbot daneben, SSE braucht `proxy_buffering off` und lange Timeouts, mehr Konfiguration |
| HAProxy | sehr gut für Lastverteilung | kein eingebautes ACME, auf TCP/Lastverteilung ausgerichtet |
| nur Cloudflare Tunnel | kein zusätzlicher Container | an einen Anbieter gebunden, am Edge offline nutzlos, Cloud und Edge wären verschieden aufgebaut |

Begründung Caddy: Am Edge ist automatisches, wartungsfreies TLS das entscheidende Kriterium (NFA-10, Betrieb durch
Veranstalter ohne Technik). Leistung spielt bei einigen hundert Nutzern keine Rolle. Gegen Traefik spricht die
Angriffsfläche durch den Docker-Socket.

**Repo-Struktur (Monorepo, gemeinsame Versionierung):**

```
apps/api/app/{edge,cloud}/   rollenspezifische Module, Turnierlogik gemeinsam
apps/web/                    gleicher Build; Edge-Modus: ein Turnier, /monitor, /display
protocol/                    MQTT-Vertrag als JSON Schema + Beispielnachrichten (Vertragstests)
firmware/table-rfid|table-vision/
deploy/cloud|edge/           Compose, Installer, Boot-Image, Router-Vorlage
tools/simulate-table|eval/   Simulator, Messskripte
docs/                        Architektur, ADRs, Betriebsanleitung
```

Begründung Monorepo: Cloud, Edge und Firmware teilen den Vertrag und müssen versionsgleich sein. Der Text der
Studienarbeit kommt in ein eigenes Repo und verweist auf einen festen Tag des Codes (Reproduzierbarkeit).

**Inbetriebnahme ohne Terminal (NFA-10):**
1. Beim ersten Start erzeugt die Box alle Geheimnisse und ihr Schlüsselpaar selbst.
2. Der Monitor zeigt einen Kopplungs-QR. Der Veranstalter scannt ihn in der Cloud-App, die Box gehört dann seinem
   Konto.
3. Die Konfiguration kommt aus der Cloud: Name, WLAN, DNS, Zertifikat.
4. In der Cloud wird das Turnier der Box zugeordnet.

**Bereitstellungswege:**
- fertiges Edge-Kit (für Veranstalter ohne Technik)
- Boot-Image für Pi 5 / Mini-PC
- Installer für vorhandene Linux-Rechner

**Updates nie während eines Turniers:**
- Kein Watchtower-Automatismus auf dem Edge.
- Versionsprüfung bei der Übergabe.
- Update nur ohne laufendes Turnier.
- Alternative mit Vergleichswert für die Arbeit: Flottenverwaltung wie balenaCloud (Fern-Updates, Geräteübersicht,
  aber Abhängigkeit von einem Drittanbieter).

**Hardware-Trennung:**
- **Router:** OpenWrt mit Multi-SIM/Failover. Er stellt WLAN, DNS-Eintrag und Captive Portal bereit.
- **Edge-Rechner:** API, Web, DB, Broker.
- **PoE-Switch:** versorgt die Tische per Kabel statt WLAN.

Begründung: Mobilfunk-Failover auf dem Edge-Rechner selbst ist fehleranfällig.

**Tisch-Controller:**
- Flashen im Browser (ESP Web Tools, WebSerial)
- ID aus der MAC-Adresse, Tischnummer in der App zuordnen
- Firmware-Update OTA von der Box zwischen Turnieren

**CI/CD:**
- Workflows nach Pfaden
- Multi-Arch-Images (amd64 + arm64)
- ein Release erzeugt Images, Edge-Bundle, Boot-Image und Firmware-Binaries mit Prüfsummen
- Vertragstests gegen `protocol/examples`

---

## 9. Sensorik (konzeptioneller Vergleich)

Gegenstand laut Themenmitteilung: ein **konzeptioneller** Vergleich. Der PoC verwendet **eine** exemplarische
Sensortechnik. Störszenarien werden zusätzlich reproduzierbar mit dem Simulator erzeugt (`--flicker`).

**Messaufgabe:** Becher vorhanden ja/nein je Platz. Keine Treffererkennung, kein Balltracking.

| Ansatz | Pro | Contra | Vorläufige Einschätzung |
|---|---|---|---|
| RFID (Reader unter der Platte, Tag am Becherboden) | Elektronik vor Flüssigkeit geschützt, dünne Tags, unabhängig von Licht, dauerhafte Präsenzerkennung | Kosten, mehr Elektronik, Interferenz benachbarter Reader/Antennen | Favorit für den PoC |
| Hall-Sensor + Magnet | einfach, günstig, robust | Magnet am Becher, Bauhöhe, Becher wird verändert | weniger elegant |
| Kamera (z. B. SICK) | keine Becher-Modifikation, erweiterbar | Licht, Verdeckung durch Spieler, Rechenaufwand (Auswertung am Edge) | Vergleichssystem; passt zum dualen Partner |
| ToF / LiDAR | berührungslos | Reflexion an Flüssigkeit/Bechern, Verdeckung | begründet ausschließen oder kurz bewerten |
| Gewicht | einfache Präsenz | Flüssigkeitsmenge variiert, Kalibrierung, verschüttete Getränke | eher ungeeignet |
| Kapazitiv | günstig | Flüssigkeit und Hände stören | eher ungeeignet |

**Bewertungskriterien:** Erkennungsrate, Fehlerrate, Kosten, Integrationsaufwand, Reaktionszeit, Robustheit.
**Störfaktoren:** schlechte Beleuchtung, verschüttete Getränke, verdeckte Sensoren, schräg stehende Becher.
Quellen: Fraden 2016 (Sensorik), Finkenzeller 2003 (RFID).

---

## 10. Zielarchitektur

```
                      MatchBase Cloud (alle Turniere)
                 Webapp + API + Postgres, OIDC-Provider,
                 Box-Registry, Spiegel der Edge-Turniere
                       ^                        ^
     HTTPS (Spieler,   |                        | ausgehend 443: Sync (Outbox),
     Staff online)     |                        | Login-Codes, später Weiterleitung
                       |                        |
               MatchBase App            MatchBase Edge
               (PWA, Handy)       +--------------------------------+
                       |          | Router (Multi-SIM, WLAN, DNS,  |
     offline: WLAN-QR  +--------->|  Captive Portal)               |
     am Monitor                   | Edge-Knoten: API + Web (ein    |
                                  |  Turnier) + Postgres + MQTT    |
                                  | Monitor (Dashboard, Status, QR)|
                                  | Touch-Display (Turnierleitung) |
                                  +---------------^----------------+
                                                  | MQTT tables/{id}/state
                                                  | (PoE, Kabel)
                                   Tisch-Controller (ESP32 + RFID, …)
```

**Betriebsmodi:**

| Modus | Spieler/Zuschauer | Staff | Cloud |
|---|---|---|---|
| Cloud-only (ohne Edge) | Cloud | Cloud | Schreiber, wie heute |
| Hybrid (Edge online) | Cloud | Cloud (Weiterleitung, später) oder Edge | spiegelt live |
| Offline (Uplink weg) | Monitor oder WLAN-QR → Edge, ohne Login | Display oder vorab angemeldete lokale Session | Hinweis, gesperrt, letzter Stand |

---

## 11. Entscheidungsverlauf (DSR-Iterationen)

Für die Arbeit wertvoll: Die Lösung ist in mehreren Build-Evaluate-Zyklen entstanden, nicht in einem Schritt.

| Iteration | Vorschlag | Erkenntnis aus der Bewertung | Folge |
|---|---|---|---|
| 1 | Ausgangskonzept: Edge mit API-Discovery `http://beerpong.local` aus der Cloud-PWA | Scheitert an Mixed Content, LNA, Cookies, fehlendem Offline-Laden, mDNS | Wechsel nur als Navigation auf eine eigene Edge-Origin denkbar |
| 2 | Voller Edge mit eigener HTTPS-Origin (öffentlicher DNS-Name → lokale IP), Single Writer mit Übergabe | Offline-Auth ungelöst. Öffentlicher DNS offline nicht auflösbar, DNS-Rebind-Schutz der Router. Spieler müssten wechseln. | Praxis-Usability schlecht |
| 3 | Sensor-Gateway (Cloud bleibt Schreiber) | Sehr robust, aber keine Offline-Turnierführung; erfüllt die Problemstellung nur teilweise | als Vergleichsvariante behalten; Prinzip "manuell geht immer" übernommen |
| 4 | Edge als Single Writer + Touch-Display + Monitor, Cloud spiegelt und leitet weiter | Löst Offline. Spieler bleiben in der Cloud, keine Discovery nötig. Risiko: Box als SPOF. | gewählt, mit Rückholen und robuster Hardware |
| 5 | Auth: Login am Edge über die Cloud (OIDC), lokale Session | Offline keine Neuanmeldung | organisatorisch gelöst: Staff meldet sich vorab an, Display als Rückfall |
| 6 | Zugang vor Ort: automatische Erkennung | Unscharf (IP) oder Browserabfrage (LNA) | bewusster Wechsel per Monitor-QR und Captive Portal |
| 7 | Vereinfachung "Cloud nur lesend" | Im Normalfall arbeitet der Staff in der Cloud | Weiterleitung als Zielbild (FA-10), im PoC zurückgestellt |
| 8 | Externer IdP | Passwortloser SMS/E-Mail-Code passt schlecht, Betriebsaufwand | integrierter OIDC-Teil, standardkonform und austauschbar |

---

## 12. Umsetzungsplan

Legende: **PoC** = für den Machbarkeitsnachweis umzusetzen · **Konzept** = in der Arbeit konzipiert und begründet,
Umsetzung optional bzw. später.

### Phase 0 – Struktur (PoC)
- Begriffe im Code und in den Docs vereinheitlichen (MatchBase Cloud/Edge statt "Tournament Core").
- `deploy/` (Compose-Dateien), `protocol/` (JSON Schema, Beispiele), API-Module `app/edge/` und `app/cloud/`.
- Veraltete ADRs anpassen: 0001 Discovery (verworfen, ersetzt durch 8.7), 0002 Sync (präzisiert durch 8.4).

### Phase 1 – Sensorik am Edge (PoC, **umgesetzt** im Branch `feat/edge-core`)
- MQTT-Vertrag v1 (`app/schemas/table_state.py`), Listener (nur mit `MQTT_URL`), Controller-Verwaltung
  (`station_devices`), Messwert-Log (`sensor_readings`).
- Zuordnung Stand → Station → Spiel, Ergebnisvorschlag über die Spielregel, `results.source`.
- `GET /info`, Simulator, Broker in `docker-compose.dev.yml`, Edge-Compose.
- Verifikation: 9 neue Tests, gesamte API-Suite grün; Ende-zu-Ende mit echtem Mosquitto-Broker.
- **Für die Arbeit bemerkenswert:** Der Ende-zu-Ende-Test fand einen Fehler, den die Unit-Tests nicht finden konnten.
  Ein Messwert wurde vor seinem Controller gespeichert, und die Fremdschlüssel-Verletzung trat nur unter Postgres auf,
  weil SQLite in den Tests Fremdschlüssel nicht prüft. Das ist ein Argument für Integrationstests gegen die echte
  Infrastruktur.
- Nachzuziehen:
  - `GET /devices` auf die eigene Box bzw. den Veranstalter beschränken.
  - Seitenwahl (heute: Team A links).

### Phase 2 – Edge-Modus der App (PoC)
- Web im Edge-Modus: nur ein Turnier, lesen ohne Login, dezenter Login-Button für Staff.
- `/monitor`: Dashboard (Spiel ↔ Tisch), Status online/offline, QR im Offline-Fall.
- `/display`: Bedienplatz am Touch-Display, Sensorvorschlag mit einem Tipp übernehmen.
- Automatische Zuordnung Controller → Station über die Tischnummer.

### Phase 3 – Box-Registry, Übergabe und Sync (PoC)
- Ersteinrichtung: Schlüssel selbst erzeugen, Kopplungs-QR, Beanspruchen in der Cloud.
- Übergabe beim Turnierstart (Snapshot aus den Admin-Antwortmodellen), Rückgabe am Ende.
- Outbox und Sync Edge → Cloud. Die Cloud wendet sie über die Fachregeln an, nur turnierbezogene Daten.
- Cloud: Edge-Turniere gesperrt, Hinweis bei fehlender Verbindung.

### Phase 4 – Authentifizierung (PoC)
- Cloud: OIDC-Endpunkte, asymmetrischer Schlüssel, Zustimmungsseite, Rollenprüfung vor der Code-Ausgabe.
- Edge: OIDC-Client, lokale Sessions mit Turnierdauer, Bereitschaftsanzeige "lokal angemeldet".

### Phase 5 – Hardware-Prototyp (PoC)
- ESP32 + RFID-Firmware nach Vertrag v1, PoE.
- Router mit WLAN, lokalem DNS und Captive Portal (Vorlage in `deploy/edge/`).
- Aufbau mit mindestens einem echten Tisch und mehreren simulierten Tischen.

### Phase 6 – Evaluation (PoC)
- Siehe Kapitel 13.

### Später / Konzept
- Weiterleitung Cloud → Edge (FA-10), Rückholen bei Box-Ausfall (FA-11).
- HTTPS am Edge per DNS-01, Multi-Arch-Images, Boot-Image, Installer, OTA für Controller.
- Vision-Tisch (Kamera), Vollautomatik-Modus, paarweise Nutzer-IDs, Passkeys.
- Nebenbefund: Das API-Docker-Image startet mit `python main.py`, ohne Server. Prüfen und beheben (eigene Aufgabe).

---

## 13. Evaluationsplan

Methodenwahl nach Hevner et al. (2004):
- **analytisch:** Architekturbewertung, Bedrohungsmodell
- **experimentell:** kontrollierte Messungen mit Simulator
- **Feldtest:** echtes Turnier
- **deskriptiv:** Argumentation gegen die Literatur

### 13.1 Analytisch
- Bewertung der Varianten V0–V6 gegen die Kriterien aus Kapitel 6 (Tabelle 7.2) und die Szenarien (7.5).
- Bedrohungsmodell für fremd betriebene Edges (8.6): Welche Angriffe sind möglich, welche Maßnahme verhindert sie?
- Nachweis, dass die Invarianten des Turnierbaums unter V6 erhalten bleiben (Single Writer) und unter V4 verletzt
  werden können (Gegenbeispiel).

### 13.2 Experimentell (Labor, reproduzierbar)

| Szenario | Messgröße | Bezug |
|---|---|---|
| Sensorstand ändert sich | Latenz Controller → Edge-DB → Monitor (Zeitstempel, NTP-synchron) | NFA-01 |
| Änderung am Edge | Latenz Edge → Cloud-Spiegel | NFA-02 |
| Uplink 30 s / 10 min / 60 min trennen | Funktionsfähigkeit vor Ort, Datenverlust, Dauer bis Cloud aktuell | FA-04, NFA-03 bis NFA-05 |
| Edge-Knoten hart ausschalten | Wiederanlaufzeit, Datenverlust | NFA-06 |
| Broker-Neustart, Controller-Neustart | Wiederherstellung per `retain`, Umgang mit `seq` | 8.2 |
| Fehlmessungen (`--flicker`) | falsche Vorschläge, Notwendigkeit einer Entprellung | FA-02, NFA-11 |
| Cloud ohne Edge | Regressionstests, Verhaltensvergleich | FA-09, NFA-07 |
| Angriff: Box versucht fremdes Turnier, globales Team, Cloud-API mit ID-Token | Ablehnung durch die Cloud | NFA-08, NFA-09 |

### 13.3 Feldtest (echtes Turnier)
- Erkennungsrate: Anteil der Sensorvorschläge, die unverändert übernommen wurden (`source = sensor`, keine Korrektur).
- Reaktionszeit: letzter Becher bis Ergebnis (`sensor_readings.received_at` → `results.created_at`).
- Nachrichtenverlust: Lücken in `seq`.
- Verfügbarkeit der Controller: `last_seen_at`.
- Einrichtungszeit der Box durch den Veranstalter (NFA-10).
- Qualitativ: kurzes Feedback von Veranstalter und Schiedsrichtern (z. B. leitfadengestützt oder SUS-Fragebogen).

### 13.4 Datenbasis im System
- `sensor_readings`: jeder geänderte Stand mit Controller, Station, Spiel, `seq`, Empfangszeit
- `station_devices.sensor`: Sensortechnik für den Vergleich
- `results.source`: Herkunft des Ergebnisses
- Revisionen und Outbox: Sync-Verzug

---

## 14. Offene Punkte und Risiken

| Punkt | Umgang |
|---|---|
| Seitenwahl: Team A gilt als links | `sides_swapped` je Spiel, gesetzt beim Start am Tisch |
| Entprellung: Der Vorschlag entsteht beim ersten Stand mit 0 Bechern | per Flacker-Messung entscheiden, ob eine Mindeststandzeit nötig ist |
| Neustart Controller: `seq` beginnt neu | nur exakt gleiche `seq` wird verworfen; Restrisiko dokumentieren |
| Box als SPOF | robuste Hardware, Strompuffer, Rückholen (FA-11) |
| Android verlässt WLAN ohne Internet | Hinweis in der Betriebsanleitung, bei kurzen Ausfällen unkritisch |
| Versionsgleichheit Cloud ↔ Edge | Versionsprüfung bei Übergabe, Updates nur ohne Turnier |
| Engpass Display bei vielen Tischen | zusätzliche, vorab angemeldete Staff-Geräte |
| HTTP im PoC | bewusste Abweichung, Zielbild HTTPS mit DNS-01 |
| Listener unter Windows (Proactor-Loop) | Edge läuft unter Linux/Docker; für die Entwicklung dokumentiert |

---

## 15. Vorschlag für die Gliederung der Arbeit

1. Einleitung (Motivation, Problemstellung, Forschungsfrage, Methodik DSR, Aufbau)
2. Grundlagen
   - Edge Computing
   - IoT-Protokolle
   - Konsistenzmodelle (CAP, Koordination, CRDT, Local-first)
   - OAuth 2.0 / OIDC
   - Sensorprinzipien
3. Ausgangssystem und Einsatzkontext (Kapitel 3 und 4)
4. Anforderungsanalyse (Kapitel 5)
5. Evaluation und Konzeption der Architektur
   - Kriterien (6)
   - Varianten und Bewertung (7)
   - Teilentscheidungen (8.1–8.4)
6. Sicherheits- und Zugangskonzept (8.5–8.7)
7. Konzeptioneller Sensorvergleich (9)
8. Prototypische Realisierung
   - Zielarchitektur (10)
   - Umsetzung (12)
   - Deployment (8.8)
9. Validierung und Diskussion (13, 14)
10. Fazit und Ausblick (FA-10, FA-11, Vollautomatik, Passkeys)

Anhang: Entscheidungsverlauf (11), ADRs, MQTT-Vertrag, Messdaten.

---

## 16. Literatur

Aus der Themenmitteilung:
- Hevner, A., Chatterjee, S. (2010). Design Science Research in Information Systems. Springer.
- Shi, W. et al. (2016). Edge Computing: Vision and Challenges. IEEE Internet of Things Journal 3(5).
- Naik, N. (2017). Choice of effective messaging protocols for IoT systems: MQTT, CoAP, AMQP and HTTP. IEEE ISSE.
- Kleppmann, M. et al. (2019). Local-first software: you own your data, in spite of the cloud. Onward! 2019.
- Fraden, J. (2016). Handbook of Modern Sensors. Springer.
- Finkenzeller, K. (2003). RFID Handbook. Wiley.

Ergänzungsvorschläge (bibliografische Angaben vor Verwendung prüfen):
- Hevner, A., March, S., Park, J., Ram, S. (2004). Design Science in Information Systems Research. MIS Quarterly 28(1).
- Peffers, K. et al. (2007). A Design Science Research Methodology for Information Systems Research. JMIS 24(3).
- Bailis, P. et al. (2015). Coordination Avoidance in Database Systems. PVLDB 8(3).
- Shapiro, M. et al. (2011). Conflict-free Replicated Data Types. SSS 2011.
- Gilbert, S., Lynch, N. (2002). Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant
  Web Services. ACM SIGACT News.
- Kazman, R., Klein, M., Clements, P. (2000). ATAM: Method for Architecture Evaluation. CMU/SEI-2000-TR-004.
- OASIS (2019). MQTT Version 5.0.
- RFC 7252 (CoAP), RFC 6749 (OAuth 2.0), RFC 7636 (PKCE), RFC 9700 (OAuth 2.0 Security BCP), OpenID Connect Core 1.0.
- RFC 8908 / RFC 8910 (Captive Portal API / Identifikation).
- W3C Mixed Content; WICG Local Network Access.
