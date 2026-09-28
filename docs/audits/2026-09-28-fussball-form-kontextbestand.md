# Fußballform und Kontextbestand – Fortsetzung am 28.09.2026

Ausgangspunkt: `7d7e0aed8c83cf97687e196c99d231a7ebd3f620`, zu Beginn identisch
lokal, auf GitHub `main` und auf dem VPS. Der vorherige Kundenbegründungs-Patch
ist enthalten; dieser Folgepatch ergänzt insbesondere die noch fehlenden
Fußball-Ergebnislisten. Kein neuer Sport-/API-Scan, keine zusätzliche Sicherung,
keine Aktivierung von Portal/Paywall und keine Cricket-Änderung.

## Implementierung

- Höchstens zehn wirklich vorhandene abgeschlossene Spiele je Team aus der
  ohnehin geladenen Modellhistorie. Fünfer- und Zehnerbilanzen getrennt;
  kleinere Datenmengen ehrlich mit ihrer tatsächlichen Anzahl. Clubs höchstens
  365 Tage, markierte A-Nationalteams höchstens 730 Tage. Keine weitere Abfrage,
  keine nachträgliche Erweiterung des Trainingsbestands.
- Exakte Bindung an Fixture-ID, beide Team-IDs, Heim/Gast, Spieltermin,
  Modellumfang und Erfassungszeit. Keine zukünftigen oder unbekannten Ergebnisse.
  Konflikte, Wiedereröffnung/Verlegung, doppelte Revisionen und widersprüchliche
  gemeinsame Ergebnisse werden ausgeschlossen, unabhängig von der Eingabereihenfolge.
- Kleine reine Anzeigeprojektion im bestehenden Such-/Workerzustand und im
  bestehenden Analysebeleg; kein neues Datenbanksystem. Ein erfolgreicher
  Modellrefresh ersetzt nur die tatsächlich neu berechneten Spiele; reine
  Kontextaktualisierung behält deren bisherige Formzeit bei. Abgesagte Spiele
  behalten nicht versehentlich eine Formkarte im aktuellen Modellpool.
- Wettfinder und Daily3, manuelle Suche sowie RisikoBet verwenden dieselben
  begrenzten Fakten. Ergebnisse, Gegner, Datum, Heim/Gast und Wettbewerb sind
  je Team aufklappbar. Namenskollisionen erhalten in normalen Karten einen
  Heim-/Gast-Zusatz; die bestehende strengere RisikoBet-Identitätsprüfung bleibt.
- Markt- und seitenrichtige Begründung aus den tatsächlichen Modellraten.
  Bessere gegnerische Fünferbilanz ist ein Gegenargument, kein erfundener
  Stärkevergleich. Keine Behauptung über schwierigere Gegner ohne deren
  tatsächlich belegte Stärke. HTML in fremden Namen wird escaped.
- Wahrscheinlichkeiten, Modellreihenfolge, bekannte exakt gebundene
  Quotenuntergrenze und Geldregeln unverändert. RisikoBet-Fakten ausdrücklich
  `DISPLAY_ONLY`, nicht als neues Modellmerkmal oder Rankingbeleg.
- Alte Prognosen, Tickets, Finanz- und Abrechnungshistorie werden nicht umgeschrieben.
  Alte Belege ohne Gegnerliste bekommen keine aus späterem Wissen ergänzte Bilanz.
  Neue Listen entstehen im nächsten regulären Modelllauf, nicht beim Seitenaufruf.

## Software-/Browserprüfung

Rot/grün reproduziert: fehlende Listen, Verlegungs-/Revisionskonflikte außerhalb
des Formfensters, gegensätzliche gemeinsame Endstände, gleichnamige native Teams,
vertauschbare Teamdetails sowie ungewolltes Ranking durch Anzeigefaktoren.
Die Korrekturen sind im unabhängigen Abschlussreview ohne offenen Befund.

- Frischer integrierter Lauf: 752 bestanden, 85 Untertests bestanden,
  162,91 Sekunden. JUnit: `output/playwright/customer-history-context-final-20260928.xml`.
- Abschließende Text-/Tennis-Oracle-/Server-Pin-Regression: 120 bestanden,
  18,88 Sekunden. Zwei zuvor nur im während Änderungen laufenden Prozess
  gemeldete Source-Introspectionprüfungen zusätzlich frisch bestanden.
- Die erste breite Runde lief während der Implementierung und ist **kein**
  unveränderter Finalnachweis: 10 Fehler, 11.226 bestanden, 96 Skips,
  111 Untertests. Zwei Fehler waren wechselnde Quellzeilen in bereits geladenem
  Testcode, acht frisch reproduzierte Fehler veraltete Baseline-Erwartungen.
  Diese acht betrafen alten Elo-Kundentext, alte explizite Tennis-Adapterrevision
  und eine absichtlich nicht installierte Portalvorlage. Das eingefrorene Oracle,
  vollständige Modell-/Hash-/ID-Vergleiche und Unit-SHA-Pins blieben erhalten.
- Erste unveränderte Gesamtregression: zwei Fehler, 11.272 bestanden,
  96 Skips, 111 Untertests; 2.371,55 Sekunden. Beide Fehler sind derselbe
  Altformat-Absturz: Eine manuelle Karte ohne native Team-IDs wurde vom
  optionalen Statistikadapter nicht abgefangen. Drei zusätzliche Regressionen
  für fehlende Heim-/Gast-ID oder Termin zusammen mit beiden bestehenden
  Oberflächenfällen vor der Korrektur rot reproduziert. Der Adapter lässt nun
  ausschließlich die optionale Statistik aus, ohne Karte oder Kandidat zu ändern.
  Danach 115 betroffene Tests bestanden, 12,45 Sekunden.
- Erneute unveränderte Gesamtprüfung: alle 11.373 gesammelten Tests aus
  290 Modulen in zwei disjunkten Gruppen von je 145 Modulen, kein ausgelassener
  oder doppelt gezählter Modulbestand. **11.277 bestanden, 96 Skips,
  111 Untertests bestanden, null Fehler.** Gruppe A: 5.105 bestanden, 50 Skips,
  79 Untertests, 1.156,22 Sekunden. Gruppe B: 6.172 bestanden, 46 Skips,
  32 Untertests, 889,78 Sekunden. Neun bekannte `record_property`/xunit2-
  Berichtswarnungen; keine unterdrückten Testfehler. Die 15 Produkt-/Testdateien
  vor und nach beiden Läufen per SHA-256 identisch. JUnit-Belege:
  `output/playwright/customer-final-a-20260928.xml` und
  `output/playwright/customer-final-b-20260928.xml`, nicht in Git.
- Der unabhängige Abschlussreview bestätigt auch den letzten Altformat-Guard:
  drei Missing-field-Fälle, beide ursprünglichen Oberflächenfälle, gültige Karte
  und elf ungültige Identitäts-/Uhrzeitwerte separat ohne offenen Befund geprüft.
  Veröffentlichung erst mit getrenntem Git-/VPS-Nachweis bestätigen.

Interner Browser: echtes Kartenrendering mit klar gekennzeichneten Testspielen,
keine vermeintlichen aktuellen Tipps. 1280 px, 390×844 und 320×740 geprüft;
kein horizontaler Überlauf. Formdetails öffnen nur das gewählte Team und
schließen wieder. Bessere gegnerische Kurzform als Gegenargument sichtbar;
keine Browserfehler und kein durch HTML-Namen eingeschleustes Bild.

Lokale Screenshots, nicht in Git:

- `C:/Users/miros/.codex/visualizations/2026/08/11/019fef37-33e4-76c0-9b0e-3f9017bd9162/football-form-final-desktop-20260928.png`
- `C:/Users/miros/.codex/visualizations/2026/08/11/019fef37-33e4-76c0-9b0e-3f9017bd9162/football-counter-final-mobile-20260928.png`

Die isolierte QA-Fixture zeigt ausdrücklich ein Außenseiter-Szenario mit
21,2 % und dessen Gegenargument, keine Empfehlung. Der frühere Screenshot
verwendete für diese reine Rendering-Fixture versehentlich die Home-Prozentzahl;
die separate QA-Fixture wurde korrigiert. Produktcode und Regressionstestdaten
während der finalen Vollsuite blieben unverändert. Die Escape-Probe erfolgte mit
einem HTML-artigen Gegnernamen; der finale lesbare Screenshot enthält diesen
Prüfstring nicht. Frühere Bilder wurden nicht überschrieben.

## Echte Kontextdaten – Vollbestand, kein Wirkungsnachweis

Rein lesender VPS-Ablauf: `audit_tennis_readiness` mit festem Stichtag
`2026-09-28T10:32:19.050906Z`; alle 361 passend gebundenen Ereignisse über sechs
disjunkte Bereiche von höchstens 64 Ereignissen. Die Bereichsprüfung hält die
SQL-/Python-Arbeit begrenzt und wiederholt keine bereits ausgewerteten Ereignisse.
Eine DISTINCT-Inhaltsvorselektion spart das wiederholte JSON-Dekodieren identischer
Empfangsrevisionen; tatsächlich verwendete native Bytes und Zeiten werden weiterhin
vollständig durch ihren bisherigen Besitzer geprüft. Keine Zielwahrscheinlichkeiten,
Gewinne, Koeffizienten oder Testverluste bewertet. Laufzeit 1.335,064 Sekunden.

Bestandsidentität:
`7313c124c12badc2699e0cdba10fee220d9f2eee03ac42ebe8b9b767933d21b1`.

- 3.411 Originalpublikationen, 453 eindeutige ursprüngliche Ereignisse,
  19 erst nach Spielbeginn publizierte Originalrevisionen ausgeschlossen.
- 361 eindeutige Ereignisse mit einem genau passenden nativen Endergebnis:
  **72 ATP und 289 WTA**. 89 ohne Endergebnis, drei ohne eindeutigen passenden
  Schlussbeleg. 182 Bindungsabweichungen sind Belegrevisionen, nicht 182 Spiele.
- ATP: keine tatsächlich gemessenen Matchdauern oder nutzbaren Differenzen
  kompletter Drei-Tage-Sätze; null vollständig beidseitige Drei-Tage-Satzhistorien.
  54 beobachtungsgebundene Erholungsuntergrenzen, davon 16 nicht null.
- WTA: keine tatsächlich gemessenen Matchdauern; sechs verfügbare Drei-Tage-
  Satzdifferenzen, davon vier nicht null; sechs verfügbare Drei-Tage-Spieldifferenzen.
  **Zwei** vollständige beidseitige Drei-Tage-Satzhistorien. **250**
  beobachtungsgebundene Erholungsuntergrenzen, davon 132 nicht null im begrenzten
  Statuspfad. Keine als vollständig bekannte Match-Endzeit ausgeben.
- Beide Touren: keine verfügbaren akuten Verletzungsmerkmale. Fehlend heißt
  weder gesund noch ausgeruht. ATP/WTA und unterschiedliche Datenabdeckungen
  bleiben getrennt. 250 WTA-Untergrenzen sind nicht pauschal unbrauchbar, aber
  auch noch kein getrennter Training-/Abstimmung-/200-Testspiele-Nachweis.

Zusätzliche rein lesende Fußballprüfung um 10:35 UTC: 46 Originalbindungen
für 26 native Ereignisse; vier vollständige und 42 partielle Bindungen. Die
ursprünglichen Hindernisse sind 528 fehlende native Verweise und 12.402 durch
das Speicherbudget nicht gehaltene Historienverweise, über diesen Bestand
gezählt. Das sind keine 12.402 neuen Spiele oder heutigen API-Fehler.
Neun tatsächlich gespeicherte OpenWeather-Antworten, die neueste vom
`2026-09-28T01:36:53.202821Z`. Keine Effekt-, Fit-, Freigabe- oder Experiment-
artefakte im produktiven Kontextbestand.

## Verbleibende Grenze

Die Software-/Anzeigekorrektur belegt keine besseren Wetter-, Verletzungs- oder
Müdigkeitseffekte und keine höhere Wettrendite. Für eine Wirkung fehlen noch
die vollständig produktiv verbundenen Vergleichs-/Aktivierungspfade und die
vorgegebene empirische Prüfung auf ausreichend vielen passenden, vorher
unbenutzten Spielen. Insbesondere dürfen die wenigen Dauer-, Satz-, Verletzungs-
und Fußballfälle nicht durch fiktive Nullwerte, zusammengefasste Touren oder
herabgesetzte Abnahmegrenzen als abgeschlossen gelten. Ein gesondert eng
definiertes WTA-Erholungsuntergrenzen-Experiment ist eine verbleibende Möglichkeit,
kein bereits bestätigter Effekt. Basketball, Eishockey und E-Sport erhalten durch
die Formanzeige ebenfalls keine neue numerische Verletzungs-/Belastungsfreigabe.

Es wurde nichts rückdatiert, keine zusätzliche Quelle bezahlt oder abgefragt
und keine historische Geldbewegung geändert. Die berechenbaren Basisprognosen
bleiben davon unabhängig sichtbar.
