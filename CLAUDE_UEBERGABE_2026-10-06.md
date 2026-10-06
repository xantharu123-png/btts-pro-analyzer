# BetBoy – Zusammenfassung, To-do und Übergabe an Claude

Stand: 06.10.2026, Europe/Zurich; nach ausdrücklicher Designfreigabe und Umsetzung.
Diese Übergabe ist der aktuelle Einstieg.
Ältere Abschnitte in `TODO_AKTUELL.md` und `PC_WECHSEL_UEBERGABE.md` sind
historische Belege, keine gleichzeitig gültigen Fertigmeldungen.

## 1. Auftrag und nächste Aktion

Nach der vorbereiteten Übergabe gab der Nutzer den kombinierten Entwurf mit
„ja genau so bitte umsetzten diese landigpage passt“ frei. Die Landingpage ist
jetzt im vorhandenen Django-Portal umgesetzt, getestet und auf GitHub gepusht.
Kein Sport-/API-Scan, Backup, echter Kauf oder VPS-Deployment gestartet.

Aktueller Produktfokus: eine verkaufsstarke BetBoy-Landingpage mit Login und
bezahltem Kundenzugang. Keine kostenlose bedienbare Vorschau auf der Landingpage;
statische Produktbilder sind ausdrücklich erwünscht.

**Als Erstes:** den aktuellen TODO-Block und [Design-QA](design-qa.md) lesen,
den Code-/Remote-/VPS-Stand für die nächste beauftragte Arbeit neu abgleichen.
LAND-01/02 sind erledigt: nicht erneut Varianten oder dieselbe Freigabe anfordern.
Eine separate spätere Verkaufs-/Bereitstellungsaufgabe betrifft Stripe/SMTP/
Recht/Proxy und echtes E2E, nicht einen Neubau der Landingpage. Den bisherigen
Wettfinder-Exit 1 als separate offene P0 führen, nicht durch Zusatzscan/Reset verdecken.

## 2. Tatsächlich geprüfter technischer Stand

Repository: `C:\Projekt\BetBoy\betboy-app`, Branch `main`.
Remote: `https://github.com/xantharu123-png/btts-pro-analyzer.git`.
Nicht den Projektordner darüber oder einen alten Worktree als aktuellen Code nehmen.

Vor der Designarbeit standen am 06.10. um 07:11 lokal, GitHub `main` und VPS auf:

`5a5e1b1a6b18d93211164b96193c7d909564af8b`

Der anschließende Landingpage-Produktcode ist
`a8188f800ceaa7fd4655ea7d40ca93d9c7216e6e`, auf GitHub `main` gepusht.
Danach folgt ein Dokumentationscommit für diese Übergabe. Die Differenz zum VPS
enthält jetzt echten **Portalcode**, nicht nur Dokumentation. Der Portalservice
war dort noch nicht eingerichtet; **kein VPS-Deployment in dieser Designarbeit**.
Den früheren Streamlit-Produktionsstand nicht mit dem lokalen Kundenportal gleichsetzen.
Aktuelle Revisionen vor weiterer Arbeit erneut abgleichen, nicht ungefragt verkaufen.

Frisch geprüft: **43 Portaltests bestanden** (15 neue Landing-Verträge), unabhängiges
Review ohne offene P1/P2 im Scope. Responsive DE/EN mit lokalisierten WebP-Motiven,
Navigation/Menü/Fokus/Sprachwechsel und Tarif-/Login-GETs im internen Browser geprüft.
Keine echten Kundenkonten oder Zahlungen erzeugt. Browser-/Promptbelege lokal unter
`output/landing-20261006/`, ungetrackt. Neue Laufzeitassets 1.128.615 Bytes insgesamt.
Vorschau <http://127.0.0.1:8010/de/> / <http://127.0.0.1:8010/en/>.
Reproduzierbare Start-/QA-Befehle und Assetquellen:
[Umsetzungsdokument](docs/design/landingpage-20261006/implementation.md).

### Historischer VPS-Gegencheck am 06.10., ungefähr 07:11 CEST

| Bereich | Gelesener Produktionsstatus |
| --- | --- |
| App / Caddy | beide `active/running` |
| Interner / öffentlicher Healthcheck | beide `ok` |
| Wettfinder | 03:35:02–04:02:17 CEST, `Result=exit-code`, Exit **1** |
| Tennis | 00:05:31–00:30:21 CEST, `Result=success`, Exit **0** |
| E-Sport | 03:10:31–03:10:45 CEST, `Result=success`, Exit **0** |
| Football Shadow | letzter Lauf 07:02:21 CEST, technisch Exit **0** |
| Kundendienst | `betboy-portal.service`: `LoadState=not-found` |
| Portal-Konfiguration | `/etc/betboy/portal.env` fehlt |
| Freier VPS-Platz | 23.508.914.176 Bytes zum Prüfzeitpunkt |

Ein technischer Exit 0 beweist weder verwertbare Daten noch bessere Wettqualität.
Die genaue Ursache des heutigen Wettfinder-Exit 1 wurde in dieser Übergabe nicht
neu diagnostiziert. Die letzte Vollsuite wurde nicht erneut gestartet.

Sieben Timer waren geplant: Tennis, E-Sport, Wettfinder, Football Shadow,
Redcard History, Redcard Settlement und Backup Retention. Tennis täglich 00:05,
E-Sport 03:10, Wettfinder 03:35; Football Shadow nächster Termin 07:12 und damit
aktuell im Zehn-Minuten-Rhythmus. Das sind Berechnungs-/Wartungsdienste, keine
automatischen Git-Pulls. Timer unverändert lassen, bis eine konkrete Änderung
beauftragt und geprüft ist.

Historischer Testnachweis auf Codefreeze `ecda9e9` vom 04.10.:
12.474 bestandene Haupttests, 97 Skips, 111 bestandene Untertests;
`output/playwright/full-continuation-20261004.xml`. Diese Mengen nicht addieren
oder als frische Prüfung des heutigen Tages ausgeben. Details im älteren TODO-Block.

### Sichere reine Lesechecks

```powershell
Set-Location C:\Projekt\BetBoy\betboy-app
git status --short
git branch --show-current
git rev-parse HEAD
git ls-remote origin refs/heads/main
ssh -F C:\Users\miros\.ssh\config -o BatchMode=yes -o ConnectTimeout=10 betboy-vps 'sudo -n git -c safe.directory=/opt/betboy/app -C /opt/betboy/app rev-parse HEAD'
```

Der normale SSH-Nutzer darf `/opt/betboy/app` nicht direkt lesen. Root-Git benötigt
hier für den Lesecheck die **nur für diesen Aufruf** gesetzte `safe.directory`.
Nicht globale Git-/Dateirechte ändern und nicht Geheimnisse ausgeben.

## 3. Gewählte Landingpage – exaktes Design und Status

Die fünf erzeugten Bildvarianten waren in der sichtbaren Reihenfolge:
1. Creme/Dunkelgrün, Sports Editorial;
2. dunkles Stadion/Neon-Grün;
3. Blau/Koralle, Sportkampagne;
4. Creme/Bordeaux, Sportmagazin;
5. Weiß/Schwarz/Orange, minimaler Sport-Look.
Die zwei zuvor angesehenen kleinen App-Screenshots waren nur Referenzen.

**Nutzerentscheidung:** Variante 1. Das Handy war zu langgezogen. Danach aus
Variante 3 die Schritte und den Monatsbilanz-Abschnitt übernehmen.

### Verbindliche Reihenfolge

1. Kopfzeile und Hero von Variante 1: Creme, Dunkelgrün, Lime-Akzente,
   Sport-Editorial-Typografie, Stadion-/Tennisbild; Headline
   **„Weniger Bauchgefühl. Mehr Spielverständnis.“**
2. Smartphone mit natürlichen Proportionen, ungefähr Breite:Höhe 1:2,05;
   vollständig sichtbar, nicht vertikal strecken oder unten abschneiden.
3. **„In drei Schritten zu deinem Überblick.“**
   - Spiele entdecken – Finde interessante Partien.
   - Form vergleichen – Sieh Form und Gegner im Vergleich.
   - Auswahl verstehen – Erkenne die Gründe für eine Auswahl.
4. **„Monatsbilanz · September 2026“**, vor den Abos.
5. Drei Abostufen, Plus hervorgehoben.
6. Kurzer Abschluss-CTA und Footer.

### Dauerhaft verfügbare Bildreferenzen

- [Kombinierter Entwurf, maßgeblicher nächster Prüfschritt](docs/design/landingpage-20261006/selected-remix.png)
- [Gewählte Ausgangsvariante 1](docs/design/landingpage-20261006/variant-1-sports-editorial.png)
- [Variante 3, nur Strukturreferenz](docs/design/landingpage-20261006/variant-3-structure-reference.png)

Die drei PNGs sind zusammen 5.485.849 Bytes. Es sind Dokumentationsreferenzen,
keine zusätzlichen Laufzeitbilder oder Store-Pakete. Die Originale unter
`C:\Users\miros\.codex\generated_images\019fef37-33e4-76c0-9b0e-3f9017bd9162`
blieben erhalten. Der Remix hat SHA256
`fb8575117221e43fad0fa3ec4c0f88e673d757d8dee3894880ba06013b377024`.

**Status:** ausdrücklich freigegeben und als semantisches responsives HTML/CSS
mit echten Links umgesetzt; nicht die ganze Vorlage als Websitebild eingebunden.
Lokale Vorschau läuft. Generierte Kampagnenbilder mit fiktiven Club-/Spielerscreens,
lizenzierte Fonts/Icons, keine realen Kundendaten. Smartphone vollständig und
natürlich proportioniert. Bilddarstellung ausdrücklich illustrativ; keine belegten
Sportstatistiken oder angeblich echten Spielerfotos. Lizenz-/Assetbelege im
Umsetzungsdokument; echter Verkaufsstart bleibt separat offen.

## 4. Ergebniswerbung – keine erfundenen 74 Prozent

Der Nutzer möchte eine Werbeseite, auf der belegte Ergebnisse überzeugen.
„74 % Trefferquote letzten Monat“ war sein Beispiel, keine nachgewiesene Zahl.
Im Remix steht deshalb `Platzhalter im Entwurf`; Kennzahlen sind Striche.

Eine vollständig verifizierte öffentliche September-2026-Monatsbilanz wurde nicht
gefunden. Nicht 74 % einsetzen, keine künstlichen Bewertungen/Kundenzahlen oder
Gewinnversprechen. Eine interne Kandidatenbilanz ist keine Kunden-Tippbilanz.

Vorhandener Bericht `docs/audits/2026-10-03-auswahlbilanz.md` betrifft ausschließlich
30.09.–02.10.: 181 deduplizierte interne Prognosen aus 91 Spielen, 107 gewonnen,
71 verloren, 3 offen. Das ist **kein Monatsbericht**, kein belegter Echtgeldgewinn
und keine damalige veröffentlichte Kunden-Tippliste. Mehrere Märkte eines Spiels
sind nicht unabhängige Testspiele. Eine nachträgliche Kundenhistorie nicht erfinden.

Für echte veröffentlichte Auswahlen bestehen `consumer_tip_history.py` und
`consumer_tip_performance.py`; der interne Pool wird separat in
`selection_performance.py` ausgewertet. Vorhandene read-only Auswertung verwenden,
kein neues Statistiksystem bauen. Zeitraum und Kohorte vorab festlegen, Gewinne,
Verluste, offene Ergebnisse und Stornos getrennt nennen. Bei fehlenden Daten
Ergebniswerbung weglassen oder einen ehrlichen nichtnumerischen Abschnitt nutzen;
keine Entwurfs-Striche als angeblich fertige Leistungsbilanz veröffentlichen.

## 5. Abos, Portal, Stripe und Stores

### Bereits vom Nutzer bestätigte monatliche CHF-Tarife

| Tarif | Preis | Umfang |
| --- | --- | --- |
| Starter | CHF 9.90 / Monat | automatischer Wettfinder, gespeicherte Tipps |
| Plus | CHF 19.90 / Monat | zusätzlich eigene Suche und RisikoBet |
| Pro | CHF 29.90 / Monat | zusätzlich Live, Daily3 und 15K |

Katalog `portal/members/plans.py` ist serverseitig maßgeblich. Gleiche Modellqualität
in allen Stufen; nicht „teurer = sicherere Tipps“ verkaufen. Plus ist das
empfohlene Hauptabo. Jahrespreise CHF 99/199/299 wurden lediglich vorgeschlagen,
nicht bestätigt oder implementiert. Kein Gratis-Testabo beauftragt.

Konkurrenzvergleich vom 05.10., als historischer Preisanker: Forebet kostenlos,
Overlyzer EUR 19/Monat, BetMines EUR 21,99/Monat im niederländischen iOS-Shop,
OddsJam Gold USD 199,99/Monat im US-Google-Play-Angebot. Länder, Kanäle und
Leistungsumfang unterscheiden sich. Keine bewiesene Zahlungsbereitschaft daraus.
Quellen: `https://www.forebet.com/en/`, `https://www.overlyzer.com/de/register`,
`https://apps.apple.com/nl/app/betmines-tips-voorspellingen/id1477625153`,
`https://play.google.com/store/apps/details?hl=en-US&id=com.oddsjam.app`.

### Vorhandener Code, noch kein laufender Verkauf

Eigenständiges Django-Portal im bestehenden Repository: DE/EN-Landingpage und
Kontoabläufe, Registrierung, E-Mail-Aktivierung, Login/Logout, Passwort-Reset,
Stripe Checkout/Billing Portal, signaturgeprüfte Webhooks und serverseitige
Feature-Rechte. Einstieg: `portal/README.md`,
`docs/specs/2026-09-27-kundenportal.md`, `portal/members/`.

**Pre-launch:** kein Portalservice auf dem VPS, keine dortige Portal-Konfiguration,
kein bestätigter Live-Stripe-Kauf oder Mailversand. Vorhandene Portaltests simulieren
Stripe und Mail. Persönliche Streamlit-Nutzung nicht ungefragt auf Kunden-Paywall
umstellen. DE/EN-Kontoflows bedeuten keine vollständige englische Analyse-App.

Offen vor Web-Verkauf: Betreiber/Domain/Support, Rechtstexte und zulässige Länder,
Steuern, tatsächliche Stripe-Kontoeinrichtung, drei Prices, Webhooks, geschützte
Konfiguration, SMTP, kontrollierter systemd/Caddy-Cutover und echtes E2E im
bereitgestellten Aufbau. Ländergrenzen vor Zahlung beachten, damit niemand bezahlt
und danach keinen Zugang erhält. Webhook-Reconciliation/Alarm fehlt; unmittelbare
anteilige Tarifwechsel sind nicht implementiert. Kontotrennung, Refunds, Kündigung,
Replay, abgelaufene Cookies und Bezahlperioden explizit prüfen.

Zusätzlicher enger UI-Restpunkt: `sales_open` in `portal/members/copy.py` hängt nur
an `REGISTRATION_OPEN && LEGAL_READY`; der Vorschauhinweis kann bei Teilkonfiguration
verschwinden, obwohl Mail/Billing/Appzugang nicht bereit sind. Nicht als echten
Launch-Nachweis verwenden; vor Verkauf an vollständigen Status angleichen.

### Apple / Google

Der Nutzer möchte Apps und internationalen Vertrieb. Apple-/Google-Konten wurden
von ihm erwähnt, aktueller Dashboardzugang/Verifizierung ist nicht nachgewiesen.
Kein signiertes natives Android-AAB oder iOS-Archiv, keine Store-Billing-Adapter
oder Store-Freigabe wurden belegt. Responsive Webansicht ist kein natives Release.

Vor Einreichung: aktuelle Richtlinien für Sportwetten-Hilfsfunktionen, insbesondere
Daily3/15K mit Einsatzplanung, prüfen; zulässige Länder festlegen. Store-Billing,
native Identität, Receiptprüfung, Serverbenachrichtigungen, Restore, Refund/Ablauf,
Kontolöschung und Doppelabo-Vermeidung sowie echte Geräte-/Signierungs-/Listing-
Nachweise fehlen. Stripe-Webcheckout nicht pauschal als Store-Billing-Ersatz nutzen.
Weltweiter Vertrieb ist eine Absicht, keine bereits erteilte Freigabe.

## 6. Speicherbereinigung – abgeschlossen, nicht erneut blind löschen

Am 05.10. mit konkreter Nutzerfreigabe abgeschlossen:

- Lokal 56 reproduzierbare synthetische Testdateien aus 28 abgeschlossenen
  Testverzeichnissen entfernt: 3.758.096.468 Bytes. Keine ganzen Worktrees gelöscht.
- VPS: 70 genau geprüfte ältere Tages-/Update-ZIPs entfernt: 5.190.707.355 Bytes.
- Neueste reguläre Sicherung behalten und mit installiertem Restore-Verifier geprüft:
  `/var/backups/betboy/betboy-sqlite-20260919T011747Z.zip`, 520.280.579 Bytes,
  SHA256 `96c4e85e30069d62b17529e5f9f3f703517b86c21f84fbb4f3b9ae69e43627cc`.
- Keine Produktions-DB, Ledger/HMAC-Schlüssel, aktiven Modelle, Sportcaches oder
  fremden QA-Wiederherstellungsarchive gelöscht. Keine neue Sicherung erzeugt.
- Täglicher Backup-Timer ist deaktiviert; Retention-Timer bleibt aktiviert.

Belege unter `output/storage-audit-20261005/` sind bewusst ungetrackt:
`storage-findings.json`, `synthetic-fixtures-removed.json`,
`backup-retirement-plan.json`, `backup-retirement-result.json` und die geprüften
Helfer. Die entfernten alten Server-Restorepunkte sind ohne andere bestehende
Kopie nicht wiederherstellbar. Lokale synthetische Fixtures sind aus Tests erzeugbar.

Die früher gemessenen rund 162 GB lokal bestanden überwiegend aus alten Worktree-
und Testkopien, nicht einem Store-Download. Auf dem VPS blieben große tatsächliche
Laufzeitdatenbanken, insbesondere `context_models.db`; nicht als unnötig löschen.
Native Paketgröße ist unbekannt, solange kein Paket gebaut ist. Code/GitHub enthält
nicht automatisch aktuelle Laufzeitdatenbanken. Keine neue pauschale Bereinigung
oder automatische Backups allein aufgrund dieser Übergabe.

## 7. To-do mit Priorität und Abnahmekriterium

| ID | Priorität | Status | Konkreter nächster Schritt / Abnahme |
| --- | --- | --- | --- |
| OPS-01 | P0 | offen | Heutigen Wettfinder-Exit 1 anhand bestehender Berichte/Journal diagnostizieren. Vollständigen Endstatus, Fehlerkohorte und Datenabdeckung unterscheiden; kein Zusatzscan/Reset. |
| LAND-01 | erledigt | ausdrücklich freigegeben | `selected-remix.png` bestätigt; keine erneute Designrunde erforderlich. |
| LAND-02 | erledigt | umgesetzt/getestet/gepusht | Code `a8188f8`, 43 Portaltests, DE/EN/Desktop/Tablet/390/320 px und Navigation geprüft; siehe `design-qa.md`. Nicht auf VPS deployed. |
| LAND-03 | P1 | Daten fehlen | Echte Monatsbilanz veröffentlichter Auswahlen prüfen. Keine 74 %, kein Cherry-Picking, kein interner Modellpool als Kundenerfolg. Ohne vollständige Basis keine Ergebniszahl bewerben. |
| WEB-01 | P1 | Pre-launch | Stripe, SMTP, Recht/Domain/Länder, Proxy, Rechte und echten Checkout-/Webhook-/Mailfluss verifizieren; `sales_open`-Inkonsistenz berücksichtigen. |
| WEB-02 | P1 | offen | Reconciliation/Alarm und vollständige Kundenlebenszyklen vor unbeaufsichtigtem Verkauf. Kein stiller Live-Cutover. |
| MODEL-01 | P1 | offen | Basketball-/Hockey-Ergebnisadapter aus vorhandenen nativen Resultcaches anbinden; IDs, Start, Empfangszeit, Hash und kanonische OT/SO-Regeln prüfen. |
| MODEL-02 | P1 | offen | Vollständige begrenzte Tagesabschlusszähler statt allein `out[-2500:]`; `unresolved_outcome_events`/Modellfehler/Originale vs. Revisionen exakt auseinanderhalten. |
| MODEL-03 | P1 | fachlich offen | Verletzungs-/Wetter-/Müdigkeitsdaten, konsistente Wirkung in den Sportverteilungen und unabhängigen Qualitätsnachweis abschließen. Keine willkürlichen Prozentabschläge. Cricket bleibt ausgenommen. |
| MODEL-04 | P1 | fachlich offen | E-Sport-Gegnerstärke-/historischen Fensterbeleg und publizierte Auswahl-/Ergebnisbindung vervollständigen; keine alte Historie rückdatieren. |
| STORE-01 | P2 | nicht releasebereit | Aktuelle Zulässigkeit, Billing, Kontolöschung, native Builds/Signierung/Gerätetests/Store-Unterlagen und Regionen als getrennte Gates vorbereiten. |

Für MODEL-01 bereits bekannt: `sports_completed_history.db`, Tabelle
`history_result_revisions`; der 04.10.-Lesecheck fand 55 EuroLeague- und 1.620
NHL-Resultversionen. Aktuelle Counts neu prüfen. `CompletedHistoryStore()` schreibt
beim Initialisieren, ist deshalb kein read-only Ergebnisadapter. Kein OT-Endscore
als Hockey-60-Minuten-Ergebnis ausgeben; kein Siegtor künstlich abziehen.
Forecast-/RisikoBet-Resultpfade und alte Veröffentlichungslücken getrennt prüfen.

## 8. Unverändert zu respektierende Produkt- und Arbeitsregeln

- Keine triviale Favoriten-Auswahlflut allein durch hohe Trefferchance. Keine
  pauschalen Marktverbote: auch Team Über 0,5/Unter 1,5/Unter 2,5 können im passenden
  belegten Spiel sinnvoll sein. Marktbegründung und Vergleich müssen passen.
- Keine gegenseitig ausschließenden Empfehlungen für dasselbe Spiel; gemeinsame
  Modellversion und Vereinbarkeit vor Limit/Paginierung prüfen. Spielauswahlen
  gruppieren und zu-/aufklappbar halten.
- Modellwahrscheinlichkeit und Quote getrennt. Die festgelegte Untergrenze ist
  **1,20** bei exakt passender verfügbarer Quote. Fehlende Quote beweist weder einen
  falschen Ausgang noch einen interessanten Wettpreis. Erwartete Tore sind keine Quote.
- Kurzcheck/Form/Gegner/5- und 10-Spiele-Listen kundentauglich; technische
  Modell-/Schema-/Validierungstexte intern. Keine ungedeckten sportlichen Behauptungen.
- Daily3 heißt **„3 a day keeps the job away“**: CHF 50 eigenes Tagesbudget,
  bis zu drei zeitlich sinnvolle Einzelwetten, nur abgerechnete Gewinne weiter,
  kein Nachschuss; CHF 150 ist Ziel, keine Garantie. Keine künstliche Slotfüllung.
- Ausfallliste, Wetterabfrage, Belag-/Elo-Code und bestandene Tests sind nicht gleich
  empirisch aktive Verletzungs-/Müdigkeits-/Wetterwirkung oder bewiesener Wettgewinn.
- Keine zusätzlichen Sport-/API-Scans, neuen Backups, produktiven SQL-Umschreibungen
  oder Bereinigungen für eine Dokumentations-/Designaufgabe. API-Kontingente schonen.
- Nutzer bevorzugt kurze konkrete Antworten; keine endlosen neuen Planungsrunden
  und kein unnötiger Neubau. Bereits vorhandene Spezifikationen/Tests wiederverwenden.
- App-, Daten-/Quellen-, empirische-, Geräte-, Deployment- und Store-Nachweise
  getrennt halten. Ein gestarteter Lauf ist kein beendeter Lauf.
- Git: nur konkret eigene Dateien stage/commit/push; kein `git add .`, `reset --hard`
  oder pauschales `clean`. Geerbte ungetrackte Audits/Browserdateien erhalten.
- Browserprüfungen im internen Browser, nicht im persönlichen Chrome übernehmen.
- Produktionsrelease nur nach konkreter Änderung und Prüfung, mit vorhandenen
  Berechtigungen/ruhenden Schreibern/ff-only und Healthchecks. Standard-Updater
  nicht blind starten, wenn er entgegen der Vorgabe neue Sicherungen erzeugt.
- Secrets ausschließlich aus geschützten lokalen/Serverkonfigurationen beziehen;
  keine Schlüssel, Passwörter oder Kunden-/Geld-DBs in Chat, Git oder Bildreferenzen.

## 9. Wichtige Dateien und erhaltenes WIP

Landing: `portal/templates/landing.html`, `portal/templates/base.html`,
`portal/static/portal/editorial.css`, `portal/static/portal/editorial/`,
`portal/members/copy.py`, `plans.py`, `views.py`, `test_landing_editorial.py`.
Bestehende Authansichten behalten `portal/static/portal/site.css`/`auth.css`.
Portalvertrag: `portal/README.md`, `docs/specs/2026-09-27-kundenportal.md`.
Quellen/Modelle: ältere freigegebene Kontext-Spezifikation und Umsetzung unter
`docs/superpowers/specs/` und `docs/superpowers/plans/`; aktuelle Codes/Belege vor
Änderung lesen, nicht alte offene Checkboxen allein als heutigen Defekt nehmen.

Vor der ursprünglichen Übergabe keine getrackten Änderungen; die eigene neue
Landingpage separat committed. Erhaltenes geerbtes ungetracktes WIP:
`.playwright-cli/`, `AUDIT_BERICHT_2026-08-09.md`,
`AUDIT_BERICHT_2026-09-02_CLAUDE.md`, `UMSETZUNGSPLAN_MARKTBENCHMARK_2026-09-02.md`,
`output/playwright/`, `output/riskobet-preview-state/`,
`output/seed_riskobet_preview.py`, `output/storage-audit-20261005/`.
Nicht als Müll betrachten, nicht ungefragt committen oder löschen.

Lokale Umgebungen `.venv/Scripts/python.exe` und `.portal-venv/Scripts/python.exe`
existieren, ihre Launcher zeigen aber auf einen fehlenden früheren Pythonpfad.
Nicht ungefragt löschen/reinstallieren. Verifizierter Fallback nutzt bereitgestelltes
Python plus vorhandene Portal-site-packages; genaue Befehle im Umsetzungsdokument.
QA mit `siteconfig.qa_settings` nutzt In-memory-DB/simulierte Anbieter. Aus `portal/`
starten; aus Repo-Root entdeckt der nackte Befehl hier null Tests.

**Kurzer Startauftrag für Claude:** Lies diese Datei, den neuen obersten TODO-Block
und `design-qa.md`. Gleiche aktuellen Git-/VPS-Stand ab. Die Landingpage ist umgesetzt
und ihre Freigabe erledigt. Setze nur den nächsten beauftragten Portal-/Verkaufs-
oder Scannerabschnitt fort; starte keine neue Designrunde. Stelle Verkaufsstart,
Wettfinderfehler, native Stores oder tatsächliche Kontexteffekte nicht als erledigt dar.
