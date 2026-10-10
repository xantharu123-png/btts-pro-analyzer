# Hauptnavigation und Manuelle Suche – 10.10.2026

## Freigabe und Umfang

Nach Ablehnung des Bereich-Dropdowns hat der Nutzer die sichtbaren Hauptmenüs
und Filter mit „ja mal machen“ freigegeben. Basis ist `7d8819e4eb07966caf9e4a6dadd1c41b797a5454`.
Geprüfter Ursprung: `https://github.com/xantharu123-png/btts-pro-analyzer.git`.
Commit/Push und VPS-Deployment ohne neue Sicherung sind ausdrücklich autorisiert.

## Umsetzung

- Eine Navigation: Wettfinder / Manuelle Suche / RisikoBet / 3 a day / 15K /
  Live / Meine Tipps. Bestehende interne Schlüssel, Routing und Zugangskontrollen
  bleiben erhalten. React-Aria und älteres BaseWeb werden gezielt unterstützt;
  nur dekorative Radiokreise verschwinden, echte Eingaben/Fokus bleiben zugänglich.
- Gemeinsamer unveränderlicher Filtervertrag für Wahrscheinlichkeit (0–100 %),
  Quotenbereich ab 1,20 und vorhandene Wettarten. Inklusive Grenzen; ausschließliche
  Vergleichstoleranz 1e-12 gegen binäre Gleitkomma-Randfälle, keine Modellrundung.
- Fußball filtert den vollständigen kohärenten Marktkatalog vor Kartenbegrenzung.
  Eine explizite manuelle Suche lädt Preise gruppiert mit vorhandener Kontingent-
  und Ereignisprüfung. Widget-/Bereichsänderungen verwenden den Ergebnisbestand.
- Tennis projiziert die neueste native Revision, einschließlich gewählter
  Favoritenseite, und liest gebundene native Siegerpreise. Beobachtungs- und
  Abrufzeit werden getrennt geprüft; kein späterer Fehlversuch erneuert eine Quote.
- E-Sport verwendet vorhandene Kandidaten und exakt gebundene gecachte Preise.
  Keine neue Quote, Wahrscheinlichkeit oder Historie wird erfunden.
- Andere reine Spielplanpfade bestehen einen aktiven Prozent-/Preisfilter ohne
  entsprechende Daten nicht. Cricket wurde nicht um ein Modell erweitert.
- Keine Modellberechnung, Rangfolge, gespeicherte Prognose, finanzielle Buchung,
  Entitlement-Regel, Migration oder Produktions-API-Abfrage durch die QA geändert.

## Tests und unabhängige Gegenprüfung

Test-first: gemeinsame Filter und Integrationen zuerst rot, danach grün.
Unabhängiger Review fand einen echten 58-%-Grenzfehler bei `1 - 0.42`;
Reproduktion und Vergleichskorrektur sind separat grün. Abschlussreview ohne
weitere konkrete P1/P2. Separater Release-Guard-Review ohne Blocker.

Final frisch ausgeführt, 316 bestanden in 38,11 Sekunden:

```text
tests/test_manual_search_integration.py
tests/test_manual_search_filters.py
tests/test_unified_navigation.py
tests/test_workflow_integrity.py
tests/test_sports_editorial.py
tests/test_manual_football_filters.py
tests/test_manual_tennis_filters.py
tests/test_market_scope.py
tests/test_tennis_tab.py
tests/test_multi_sport_recommendations.py
tests/test_manual_selection_coherence.py
```

Zusätzliche echte Sammler-/Kartenkompatibilität: 65 Tests aus
`tests/test_context_football_capture.py` und `tests/test_tennis_customer_facts.py`
bestanden in 10,58 Sekunden. Kein Produktions-Netzwerkabruf dabei.

Ein zusätzlicher Regressionstest verwendet echte temporäre native Tennis-
Kontextdaten: empfangener Teilnehmerwechsel entfernt die Paarung aus der
aktuellen Ansicht, lässt die historische Ansicht und beide Datenbanken
unverändert. Netz-/Migrationsaufrufe sind beim Lesen verboten. Ein isolierter
Gegentest ohne Verfügbarkeitsprüfung scheitert genau an dieser Zusicherung.
Finale gemeinsame Runde einschließlich beider Zusatzdateien und neuem Test:
**382 bestanden in 36,82 Sekunden**.

Die breitere Vollsuite läuft separat. Sie begann vor dem letzten CSS-only-Fix
und der Vergleichstoleranz; die obige frische Runde enthält beide Änderungen.
Keinen unvollständigen Lauf als grüne Vollsuite ausgeben.

## Tatsächliche Browserprüfung

Internes QA-Browserfenster; kein externer Benutzerbrowser übernommen.
Vollständige reale Streamlit-Navigation und Suchwidgets mit klar bezeichneten
synthetischen Ergebnissen, keine Sportabfrage/Kontoaktion. Desktop 1440 × 1000,
Mobil 390 × 844 und 320 × 844. 48 Pixel hohe Menüpunkte ohne Textumbruch,
innere horizontale Menüscrollleiste und kein horizontaler Seitenüberlauf.
Tastatur erreicht auch den letzten Menüpunkt. Echter Quotenbereich 1,50–2,00
lässt nur das Beispiel mit 1,80 stehen; ohne Preis kein Treffer. Ungültiges
Von/Bis zeigt einen Fehler statt ungefilterter Ergebnisse. Sportwechsel und
Prozentregler bedienbar. Streamlit-Modulcache erforderte einmaligen Neustart
der rein lokalen Vorschau, damit der letzte CSS-Patch tatsächlich geladen wurde.

Belege außerhalb Git: `C:/Projekt/BetBoy/output/manual-navigation-20261010/`
(`desktop-1440.png`, `mobile-390.png`, `mobile-320.png`, `fullsuite.log`).

## Veröffentlichung / verbleibende Aufgaben

Code `f01e83eb8b5dfcdc5a47cef7075af5042b56fe08` auf GitHub main und VPS
fast-forward veröffentlicht. Deployment mit exakter Revisions-/Dateiliste,
ruhenden Jobs, Timerabstand und beiden Healthchecks; keine neue Sicherung,
Migration oder Bereinigung. Der erste Health-Aufruf wartete auf den gerade
gestarteten Prozess; die Wiederholungen und separate Abschlussprüfung sind `ok`.
Der SSH-stdin-Transport fügte nach dem fertig abgeschlossenen Script eine leere
CR-Zeile an und meldete deshalb Exit 127. Kein Appfehler: vorher bereits
`DEPLOYED`, beide Dienste aktiv, beide Healthchecks und Prüfsummen bestätigt;
danach unabhängig erneut Revision/sauberen Gitstand/Healthchecks geprüft.

Unveränderte SHA-256 vor und nach Deployment und manueller UI-Prüfung:

```text
wettfinder_latest.json a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e
riskobet_latest.json 593846dd998bad9ed2d7503baa710bfb1ef72db65ec38849ea8b18885bb48024
```

Produktionsbrowser nach frischem Reload: echtes neues Hauptmenü, manueller
Quotenbereich und Prozentfilter, alle Sport-/Wettart-/Liga-Controls. Ohne Klick
auf „Tipps finden“, daher kein neuer Sportscan. 1440 × 1000, 390 × 844 und
320 × 844 ohne horizontalen Seitenüberlauf, genau eine Navigation; Mobilmenü
intern scrollbar (361/529 bzw. 289/524 Pixel), 48 Pixel hohe Menüpunkte.
Tastatur bis „Meine Tipps“ und Rückwechsel zur Suche bestanden. Nach Reload
keine neuen Warn-/Fehlerlogs. Belege `production-desktop.png`,
`production-mobile-390.png`, `production-mobile-320.png` im genannten QA-Ordner.
Viewport danach zurückgesetzt; lokale QA-Vorschau beendet.

App und Caddy aktiv; sieben Timer aktiv/geplant. Ergänzende Vollsuite am
10.10. um 12:09 bei 24 %, bislang keine ausgegebenen Fehler; noch kein
Endergebnis. Diese bleibt ein separater offener QA-Nachweis, nicht als bestanden
ausgeben. Die frische gemeinsame 382er-Runde enthält alle finalen Codeänderungen.

Bereits vor diesem Patch war `betboy-wettfinder.service` im Daten-Fehlstatus.
Die SSH-Vorprüfung um 12:06 zeigt auch für den bereits regulär gelaufenen
`betboy-football-shadow.service` einen Fehlstatus; kein Lauf wurde gestartet.
Aktive App/Timer oder erfolgreicher UI-Deploy beheben diesen nicht. Daily3-
Zeitfolge, empirische Verletzungs-/Wetter-/Müdigkeitswirkung, Domainumzug,
Stripe/Stores bleiben außerhalb dieses freigegebenen Patches. Bestandene
Softwaretests sind kein Nachweis besserer Wett-Rendite.
