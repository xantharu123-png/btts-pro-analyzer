# Multigoal: bezahlte Abdeckung und Abruf – 17.10.2026

## Auftrag und Grenzen

Prüfen, ob API-Football die Bereichsquoten wirklich nicht liefert oder der
BetBoy-Abruf sie verliert. Bestehenden Abruf korrigieren; eine kostenlose
Zusatzquelle nur bei nachgewiesener exakter Abdeckung anbinden. Keine
synthetischen Quoten, keine falsche Marktzuordnung, keine Backups und kein
zusätzlicher Sport-/Modellscan. Basis lokal/main/VPS: `6ff4d260`.

## Echte Quellenprobe

Über den vorhandenen App-Schlüssel und Budget-Wrapper wurden insgesamt 14
begrenzte Status-/Katalog-/Quotenanfragen gestellt. Keine Schlüssel, URL-Secrets,
neuen Ergebnisprognosen oder Datenbankkopien wurden ausgegeben/angelegt.
Die normale Budgetbuchung bleibt wirksam. Status um 13:36 UTC: Pro aktiv,
1.908 von 7.500 Tagesanfragen verbraucht. Das ist ein Zeitpunkt, kein aktueller
Restzähler nach sämtlichen Proben.

1. `/odds/bets`: 338 Definitionen, eine vollständige Seite. Darunter 186
   „Total Goals Number By Ranges“, 223 „Number of Goals In Match (Range)“ und
   254 „Team Performances (Range)“. Katalogeintrag ist kein Angebotsnachweis.
2. Ungefilterte Spielabfragen Betis–Barcelona (1570413), Roma–Genoa (1550148)
   und Fenerbahçe–Alanyaspor (1584434): jeweils eine von einer Seite, sechs
   Buchmacher, keine Anbieterfehler. Keine tatsächlichen Gesamt-/Teamangebote
   1–3, 1–4 oder 2–4 in diesen Antworten. Einzelne exakte Torzahlen und offene
   „more“-Auswahlen sind keine Bereichsquote und werden nicht zusammengezählt.
3. Gültige Datum-/Marktabfragen für 186 und 223, jeweils 17. und 18.10.2026:
   null Ergebnisse, vollständige Seite 1/1, keine Anbieterfehler. 254 am
   17.10. ebenfalls null. Diese begrenzten Abfragen belegen nicht, dass der
   Anbieter solche Quoten grundsätzlich oder an allen Tagen nie liefert.
4. Drei frühere Abfragen nur mit `bet`, ohne Datum/Spiel/Liga, wurden vom
   Anbieter mit HTTP 200 **und Validierungsfehlern** abgelehnt. Diese Antworten
   sind ausdrücklich kein Nachweis fehlender Marktangebote.
5. Roma–Genoa lieferte tatsächlich einen weiteren Bereichsmarkt:
   Bet365 (8), native Markt-ID 349 „Number Of Goals In Match“, Auswahl
   **„2 or 3 goals“ zu 2,00**. Anbieterstand 17.10.2026 09:18:17 UTC,
   Empfang 13:39 UTC, Anstoß 18:45 UTC. Das ist ein erhaltenes Preisangebot
   mit diesem Zeitstand, keine Zusage einer jetzt erhältlichen/frischen Quote.
   Der bestehende 95er-Katalog kennt genau 2–3 Gesamttore noch nicht. Es wäre
   falsch, die Quote einem vorhandenen 1–3-/1–4-/2–4-Markt zuzuordnen.

Originale begrenzte Receipts außerhalb Git:
`C:/Projekt/BetBoy/output/multigoal-quotes-20261017/paid-probe-02.json`,
`paid-probe-03.json`, `paid-probe-04.json`.

## Nachgewiesener Abruffehler

`fetch_football_consensus` las bisher ausschließlich die erste native Seite.
Ein echter zweiter Seiteninhalt wurde nie angefordert. Reproduktion mit
unverändertem Parser: Seite 1 BTTS, Seite 2 nativer Bereich 1–4 zu 1,25;
der alte Fetch meldete den Bereich fälschlich als abwesend. Dies ist ein
zusätzlicher Codefehler, **nicht** die Erklärung der echten einseitigen
Betis-/Roma-/Fenerbahçe-Proben.

Korrektur im vorhandenen Abruf:

- Nur tatsächlich gemeldete Folgeseiten, maximal 20 je Spiel; vorhandenes
  Budget, Priorität, Timeout und Ablaufdeadline bleiben wirksam.
- Native Angebote vor der gemeinsamen Buchmacher-Deduplizierung zusammenführen.
  Gleiches Spiel, Markt, Auswahl, Anstoß und Anbieterstand bleiben gebunden.
- Fehlende/kaputte/widersprüchliche Seiteninformationen, wiederholte Seiten,
  Seitenlimit, Deadline und Transport-/Anbieterfehler nicht als vollständigen
  Beweis für „Markt fehlt“ speichern. Gültig erhaltene Preise bleiben erhalten.
- Diagnose enthält ausschließlich begrenzte Seitennummern/Fehlerklassen,
  keine Rohantworten, Schlüssel oder Anbieter-Fehlermeldungen.
- Empfangszeiten bleiben an ihre tatsächliche Seite gebunden. Ein späterer
  Seitenempfang darf eine ältere Beobachtung weder erneuern noch eine beim
  ersten Empfang unzulässige Zukunftsuhr nachträglich legitimieren.

Die Regeln zu exakten Marktpreisen und der Untergrenze 1,20 bleiben unverändert.
Es werden keine Märkte nur zum Erreichen einer gewünschten Verteilung aufgefüllt.

## Kostenlose Alternativen

Keine kostenlose, verfügbare und hinsichtlich dieser exakten Märkte ausreichend
belegte Zusatzquelle gefunden; deshalb kein spekulativer Adapter:

- [The Odds API – unterstützte Märkte](https://the-odds-api.com/sports-odds-data/betting-markets.html):
  dokumentierte alternative Gesamt-/Teamlinien sind Über/Unter, kein belegter
  Multigoal-Ersatz. Bestehende Tennisanbindung bleibt unverändert.
- [API-Football – Tarife](https://www.api-football.com/pricing): der kostenlose
  Tarif nutzt dieselbe Quelle; ein zweiter Schlüssel erzeugt keine neue Abdeckung.
- [Odds-API.io](https://odds-api.io/pricing/free): neue kostenlose Schlüssel
  derzeit pausiert; keine verfügbare verifizierte Rückfallquelle.
- [Krok – API](https://krokodds.com.au/api-access),
  [Bedingungen](https://krokodds.com.au/terms): allgemeiner Range-Hinweis,
  aber keine belegte exakte 1–3-/1–4-/2–4-Abdeckung; Beschränkungen für
  Drittanbieter-Analyseprodukte. Kein Zugriff/Vertrag neu eingerichtet.

Die [offizielle API-Football-Anleitung](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
verlangt ausdrücklich die Beachtung der Pagination. Das wird nun im Fetch
umgesetzt, nicht durch zusätzliche tägliche Sportscans umgangen.

## Prüf-/Veröffentlichungsstand

- Ursprüngliche Pagination-Regressionen tatsächlich RED, anschließend GREEN.
- Diagnosepersistenz tatsächlich RED (fehlende vier begrenzte Fakten),
  anschließend vollständiges Preisrefresh-Modul 24/24 GREEN.
- Drei weitere echte RED-Fälle für fehlerhafte Antwortcontainer; gültige
  Preise aus gemischten Seiten bleiben erhalten.
- Zwischenstand 407 betroffene Tests offline; nach Uhr-/Container-Erweiterung
  und genehmigten Markt-/UI-Ergänzungen zusammengeführte21-Modul-Prüfung:
  **748 PASS, Exit0**. Separate Registry-Prüfung211PASS+6Untertests nativ;
  frühere11 native Temp-/Hardlink-Berechtigungsfehler als Fehlversuch erhalten.
- Voller Endlauf `full-qa-02`: 15.135 PASS, 98 identische Skips, vier disjunkte
  Gruppen mit Exit 0. Alle 15.076 bisherigen IDs plus 157 neue im Endabgleich
  genau einmal enthalten; 810 Quell-/Fixture-Hashes und drei Shell-Hashes.
  Der erste strikte ID-Abgleich fand fünf verschobene automatisch generierte
  Parameter-IDs, keine entfernten Tests. Ausschließlich zwei Parameterlisten im
  Ticket-Verifier-Test wurden umgeordnet, neue Fälle ans Ende gestellt; das
  vollständige Besitzermodul danach erneut 41 PASS. Eine exakte inverse
  Byte-Transformation rekonstruiert dessen Hash aus dem vollen Lauf. Alle
  Produktionsquellen blieben unverändert. Endabgleich: `final-summary.json`;
  ursprünglicher fehlgeschlagener Abgleich und alle Receipts bleiben erhalten.
  `full-qa-01` (15.119) nach ergänzender Nutzerfreigabe kontrolliert unterbrochen,
  ausdrücklich INCOMPLETE, nicht als PASS verwendet. Belege bleiben unverändert.
- Unabhängige Pagination-/Clock-, Registry-/Pin-, Native349-, Anzeige- und
  RisikoBet-Reviews freigegeben. Ein weiterer echter UI-RED8→GREEN4 schützt
  vor mehrfachen Statistikblöcken bei mehreren Märkten desselben Spiels.
- Abschließender unabhängiger Test-ID-/Quellhash-Abgleich ohne Blocker.
  Quellcommit `113744d6fa964de29644826465eba1c56dcc797a` committed, auf main
  gepusht und am 17.10.2026 um 16:53:41 CEST per Fast-Forward auf VPS deployed.
  Keine Behauptung besserer Wettqualität/Rendite aus diesen Tests.

### Produktionsnachweis

Der gesondert geprüfte No-Backup-Releasehelfer lief mit Exit 0 im ruhigen
Timerfenster; keine laufenden Sportdienste angehalten oder neu gestartet.
Offline-VPS-Smoke bestätigt 96 Definitionen, unveränderte 40 Fit-Ziele,
exakte 2–3-Marginale, Seiten-2-Angebote für native 349 und echte gemeinsame
historische Treffer. Alle geänderten Pythondateien sind syntaktisch geprüft.

App-PID 1211028→1215661, App und Caddy aktiv; interner und öffentlicher
Healthcheck jeweils `ok`. Die SHA-256-Fingerprints von `wettfinder_latest.json`
und `riskobet_latest.json` sowie die Startstempel von Wettfinder, Tennis,
E-Sport, Football-Shadow und Quotenjob blieben beim Deployment unverändert.
Backup-Timer weiter disabled/inactive. Kein Backup, zusätzlicher Sportscan,
Modelllauf, Datenbankumbau oder Paketinstallation.

Receipt: `deploy-01.log` im oben genannten Ausgabepfad. Die nachträgliche
Abschlussdokumentation wird mit gesondertem Docs-only-Fast-Forward gezogen;
kein weiterer App-Neustart. Die UI-Nachweise unten sind ausdrücklich lokale
Renderer-Prüfungen, kein behaupteter neuer vollständiger Live-Browserlauf.

## Freigegebene Ergänzungen

Der Nutzer genehmigte Bereiche und Sieg/Torbereich-Kombinationen in der kompakten
Spielstatistik. `TOTAL_RANGE_2_3` ist jetzt die96. Laufzeitdefinition/46.
Torprojektion. Die alten90 Original-/40Fit-Ziele, v14 und sämtliche95 bisherigen
Wahrscheinlichkeiten, gemeinsame Torverteilungen und Abrechnungen sind durch
feste Vergleichstests gegen den vorherigen Quellstand abgesichert. Der neue
Bereich erhält seine eigenen historischen Ergebnisse, keine geerbte Freigabe.

Native349 wird ausschließlich als exakter voller Gesamtbereich erkannt.
Benachbarte „2 or 3 goals“ wird2–3; disjunkte „1 or 3“, offene Under/Over,
Halbzeiten und falsche IDs/Teamrollen werden nicht umgedeutet.

Die zusätzliche Spielstatistik zählt aus den bereits validierten letzten5/10
Ergebnissen, wie oft1–3/1–4/2–3/2–4Gesamttore bzw. eigener Teamsieg gemeinsam
mit diesem Bereich vorkamen. Sie ist eine historische Häufigkeit, keine neue
Modellwahrscheinlichkeit, kein zusammenmultipliziertes Randereignis und keine
erfundene Buchmacherquote. Tatsächliche Teilstichproben behalten ihren Nenner.

Normale Karten/Daily3/15K/manuelle Suche verwenden denselben Formrenderer;
Statistik nur einmal/Spiel. RisikoBet speichert zusätzliche kleine, quell- und
snapshotgebundene DISPLAY_ONLY-Zähler ohne Rankingwirkung. Keine Interpretation
alter Prosa; alte Snapshots ohne Zähler bleiben unverändert. Diese RisikoBet-
Zähler und neue2–3-Prognosen entstehen erst mit dem regulären Lauf oder einer
bewusst angeforderten manuellen Suche. Es wurde dafür kein Lauf gestartet.
Sieg/Bereich-Kombis ohne nachgewiesene eigene Quote sind keine neuen Tipps.

## Gerenderte QA

Browser-Plugin nicht verfügbar; vorhandenes gebündeltes Playwright, headless,
keine Installation und kein Benutzerbrowserzugriff. Ausschließlich localhost
und ausdrücklich synthetische TESTDATEN. Normale und RisikoBet-Renderer geprüft:

| Prüfung |1280px|390px|320px|
|---|---|---|---|
| Richtiger Titel/URL, sinnvoller Inhalt |PASS|PASS|PASS|
| Kein Fehleroverlay, Console-/Pagefehler |PASS|PASS|PASS|
| Acht Bedingungen, ein sichtbarer Block |PASS|PASS|PASS|
|5→10→5 mit Maus, Tastaturumschaltung |PASS|PASS|PASS|
| Kein horizontaler Überlauf |PASS|PASS|PASS|

Screenshots und maschinenlesbare Belege: `browser-01/` und
`browser-riskobet-01/` im oben genannten Ausgabepfad. Beide Vorschauprozesse
anschließend beendet. Das bestätigt den tatsächlichen Renderer mit isolierten
Daten, nicht die vollständige Produktionsseite oder einen echten neuen Sportlauf.
