# BetBoy – Sportarten außerhalb der NHL

Audit am 25.11.2026, Produktionscode `d2d574b`. Vergleichsfenster:
Spielbeginn vom 12. bis 24.11. Zürich, Archivstichtag 25.11. 10:31 CET.
Read-only auf dem VPS, ohne Netzwerk zum Anbieter. Keine Datenbank kopiert,
keinen Dienst gestartet oder geändert.

## Was archiviert ist

| Sport | Belegte erste Hauptkarten Standardübersicht | Erste archivierte Siegerseite je Spiel¹ | Einstiegs-Preispaare¹ |
|---|---:|---:|---:|
| Fußball | 80/102 Treffer (78,4 %, 95 %: 69,5–85,3 %); 1 offen | Separater Katalog mit mehreren Märkten | Nicht vergleichbar mit dem Siegerpool |
| Tennis | 1/1 | 10/11 (90,9 %, 62,3–98,4 %); 1 ungültig | 6 aus 12 |
| E-Sport | 1/1 | 45/72 (62,5 %, 51,0–72,8 %); 4 ungültig | 8 aus 76 |
| Basketball | 0 | EuroLeague: 18/34 (52,9 %, 36,7–68,6 %) | 0 aus 34 |
| Europäisches Eishockey | 0 | 0 belegt | 0 |
| Cricket | 0 | 0 belegt | 0 |

¹ Internes H2H-Archiv, kein Kundentipp-Protokoll. Je Partie, Modellversion
und nativer Quelle die stärkste vorhandene Seite der frühesten gültigen
Prognose; keine Gegenseite ergänzt, keine revidierte Spätprognose
eingetauscht. WIN/LOSS aus exakt gebundenen Ergebnissen; VOID nicht als
Verlust. 156 Rohprognosen, 122 unterschiedliche Spiele, keine Integritäts-
oder Zeitfehler in der ausgewerteten Kohorte. 95-%-Wilson-Intervalle
beschreiben diese Stichprobe, nicht unabhängigen Wettvorteil. Eine
vollständige Preisbeobachtung ist kein eigener Einsatz und kein Closing.

Sportarten ab 70 % Modellchance, getrennt aus dem internen Siegerpool:
Tennis 5/5, drei Preispaare; E-Sport 15/21, vier Preispaare; EuroLeague
9/13, null Preispaare. EuroLeague über alle 34 Fälle: durchschnittlich
68,1 % modelliert gegen 52,9 % erzielt. Wegen n=34 kein endgültiges
Urteil zur Kalibrierung. Für Tennis ist die kleine Stichprobe interessant,
aber nicht repräsentativ für WTA, alle Beläge oder alle Buchmacher.

Im ungefilterten Standardkatalog standen 273 Fußballpartien, 9 Tennis-,
48 E-Sport- und 16 Basketballpartien. Das war noch nicht die erste Seite.
Die dortige ungefilterte `featured`-Markierung ergibt 5/6 für Tennis und
10/13 für E-Sport; diese Zahlen sind keine Belege für die tatsächliche
Tennisbox oder die erste Seite. Im archivierten Doublebet-Standardplan:
12 eindeutige Fußballpartien und in diesem Fenster keine andere Sportart.
Football auf der Standard-Startseite nur für 24.11.: 15/21 (71,4 %);
separater Render-Beleg mit möglicherweise anderer Filter-/Aufrufzeit:
15/19 (78,9 %). Nicht mitteln oder zusammenzählen.

## Befunde nach Ursache

- **Tennis:** Der automatische Siegerpfad prüft u.a. Hartplatz, ATP,
  Spielerdaten und mindestens 60 %; WTA ist dort explizit nicht freigegeben.
  Die Standardübersicht zeigt mindestens gerundete 70 %; bei einer
  Modellchance von mindestens 65 % fehlt ohne passende Quote bei Tennis der
  Preisbeleg für die Mindestuntergrenze. Die Tennisbox wählt nach nächstem
  Start, nicht nach dem besten Modellwert; sie hat keinen eigenen
  Anzeigebeleg. Für die aktuelle Tagesdatei 25.11. wurden fünf
  Tennis-Preisziele geprüft, ohne passende Quote; null automatische
  Tennis-Kandidaten. Der Modellfreigabegrund je Partie wurde hier nicht
  nachträglich bestimmt. Gegenpreise werden schon erfasst: gleiche
  Partie, gleicher Buchmacher, gleicher Quotenstand. Nächster
  Erkenntnisgewinn: gezielter ATP-Bericht nach Belag und Wahrscheinlichkeit
  sowie WTA getrennt im Shadow, ohne neue Anbieterabfrage
  (`ev_signal_sources.py:505`, `tennis/predict.py:276`,
  `market_consensus.py:737`, `forecast_evidence.py:178`).
- **E-Sport:** CS2/LoL/Dota 2/Valorant werden modelliert, aber Menge und
  Kalibrierung sind pro Titel und Turnierstufe nicht nachgewiesen. Die
  dekorative Hervorhebung ist nicht die strenge Empfehlung. Sie ist
  tatsächlich möglich; die strenge Veröffentlichung verlässt sich nicht
  auf diesen Status. OddsPapi kann beide Serien-Siegerquoten liefern, doch
  die Archivzeit ist der Abruf, nicht der eigene Buchmacher-Zeitstempel:
  sieben der acht frischen Fälle sind dennoch technisch als ausführbar
  markiert. Unter `floor` und `gate` lokal reproduzierbar. Zusätzlich
  akzeptiert die Anzeige im Test +2 Minuten Unterschied beim Start, der
  Archivschreiber verwirft ihn. Preisbeleg und Zuordnung angleichen, dann
  nach Disziplin/Serienformat auswerten. „Mindestens eine Map“ besitzt
  keinen passenden H2H-Preis und darf diesen nicht erben
  (`esports_prices.py:77`, `:126`, `forecast_evidence.py:217`,
  `esports_shadow.py:550`, `ev_signal_sources.py:2121`).
- **Basketball:** Vier EuroLeague-Modelle ohne Quote in der aktuellen
  Tagesdatei; ein entdecktes NBA-Spiel im RisikoBet-Quellbestand, aber
  kein NBA-Modell dort in der automatischen Tagesdatei. Auch im
  Vergleichsfenster keine NBA-Siegerprognose im Modellarchiv. Der
  Tagesabruf fragt beim ESPN-NBA-Spieltag nur das Zürcher Datum ab,
  filtert dann wiederum auf Zürich; NBA-Partien am frühen Zürcher Morgen
  können im vorigen ESPN-Tagesbucket liegen. Die Vorschau fragt bereits
  zwei Tage ab. Das ist ein Codepfad, nicht der bewiesene Grund für jedes
  fehlende NBA-Modell. Als Erstes Spielplan und Modellübergabe an
  einem vorhandenen NBA-Beispiel über die Zeitzonengrenze prüfen;
  anschließend getrennte NBA-/EuroLeague-Beobachtung und Preise
  (`wettfinder_automation.py:3500`, `:3621`,
  `scanners/basketball_scanner.py:245`).
- **Europäisches Eishockey:** National League, DEL, SHL und Liiga sind im
  Code vorgesehen. Heute sechs entdeckte Spiele (2 DEL, 4 Liiga), aber
  keine veröffentlichte europäische Modellzeile; alle 14 Eishockey-
  Modelle der Tagesdatei sind NHL. Ein damaliger Gratis-Probeabruf
  (16.10.) belegte einen Saisonhistorien-Planfehler für die Schweizer
  Liga, nicht für jede heutige Liga. Erst vorhandene Historie und
  Ablehnung je Liga prüfen, kein Abo auf Verdacht. Doublebet nimmt
  Forschungseishockey im Code über die Sportart an, nicht nur NHL;
  bisher im Fenster kein realer Doublebet-Beleg.
- **Separater Quotenfehler beim europäischen Eishockey:** Eine bereits
  gespeicherte Quote bleibt bei widersprüchlichen Heim-Team-IDs
  (11/33 für dieselbe API-Partie) abrufbar. Unabhängig lokal
  reproduziert: bei einem 1 Stunde alten Abruf wird der Widerspruch
  nicht gemeldet; bei 4 Stunden wird er gemeldet, die alte Quote
  bleibt dennoch. Im synthetischen Test mit der Produktionspreisregel
  reichte dies bis in die normale Kartenausgabe und Doublebet-Planung.
  Ein bereits im Tagesdokument eingebetteter Preis blieb sogar bei
  leerem Cache wirksam. Kein neuer Anbieteraufruf und kein nachgewiesener
  Produktionsfall. Identitätscheck vor dem Cache-Kurzschluss;
  beide Seiten und bereits eingebettete Preise bei Konflikt zurückhalten
  (`team_sport_prices.py:138`, `:423`–`:437`).
- **Cricket:** Automatik meldet kein validiertes Modell; der optionale
  RisikoBet-Datenzugang ist laut aktuellem Produktionsartefakt nicht
  konfiguriert. Kein Trefferurteil und kein Ausbau (bisher ausgenommen).

## Reihenfolge für eine Reparatur

1. Identitätskonflikt im Team-Preis-Cache und Abrufuhr/Archivvertrag der
   E-Sport-Quoten beheben. Keine historischen Preisuhren umschreiben.
2. NBA-Zürich/ESPN-Tagesgrenze und europäische Hockey-Historie anhand
   vorhandener Quellen messen; Übergabe Spielplan → Modell → Preisbeleg
   je Liga sichtbar machen. Keine zusätzlichen Hintergrundläufe nötig.
3. ATP und E-Sport auf vollständigen, zeitgleichen Einstiegs-Preis­paaren
   prüfen; Quote bleibt vom Modell getrennt. Mit 6 bzw. 8 Paaren keine
   Freigabeentscheidung. Basketball/NHL/EU-Hockey nicht als Gruppe
   zusammenlegen. Nutzer-Ansichtsschwellen nicht nach diesen Daten ändern.

Gezielte Offline-Softwaretests: 103 unter `gate` bestanden. Unter
`floor` 98 bestanden, fünf E-Sport-Preisassertionen widersprechen dem
beobachteten Code (vier erwarten `OBSERVED` statt `PLAYABLE`, eine
`executable=0` statt 1); bei unverändertem Produktionsbaum. Das ist
keine Vollsuite. NHL nicht Teil der veröffentlichten Auswertung: Ein
erster breiter Diagnoseabruf enthielt versehentlich aggregierte
Altdaten aus dem NHL-Pilotfenster; die endgültige Abfrage schließt NHL
aus. Kein Ergebnis aus dem registrierten Zukunftsfenster geöffnet,
keine NHL-Hypothese oder Freigabe geändert.
