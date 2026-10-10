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

Noch ausstehend: Vollsuite-Endstand, Narrow Commit/Push, kontrollierter
VPS-Fast-forward und frische Produktionsbrowserprüfung. Deployment prüft
exakte Revisions-/Dateiliste, ruhende Jobs, Timerabstand, beide Healthchecks und
unveränderte Wettfinder-/RisikoBet-Schnappschüsse. Keine neue Sicherung.

Bereits vor diesem Patch war `betboy-wettfinder.service` im Daten-Fehlstatus.
Die SSH-Vorprüfung um 12:06 zeigt auch für den bereits regulär gelaufenen
`betboy-football-shadow.service` einen Fehlstatus; kein Lauf wurde gestartet.
Aktive App/Timer oder erfolgreicher UI-Deploy beheben diesen nicht. Daily3-
Zeitfolge, empirische Verletzungs-/Wetter-/Müdigkeitswirkung, Domainumzug,
Stripe/Stores bleiben außerhalb dieses freigegebenen Patches. Bestandene
Softwaretests sind kein Nachweis besserer Wett-Rendite.
