# BetBoy – Scanner-Tiefenaudit und Account-Fortsetzung, 02.10.2026

## Ergebnis und Grenzen

**Fortsetzung übernommen; die App ist nicht fachlich fertig.** Der Abgleich fand
keinen aktuellen, durch Tokenabbruch verlorenen unveröffentlichten Code. Das Audit
reproduzierte aber **16 Befunde: 8 P1 und 8 P2** in den bestehenden aktiven Pfaden.
P1 bedeutet hier hohe funktionale Priorität, nicht automatisch einen beobachteten
Produktionsschaden oder eine Geldbuchungsmanipulation.

Geprüfte Codebasis: `bfb934422e960dd18128cb7e1519b1301c098cdc`, funktionaler Stand
`1ae37d9ac0736bfeaf76e511c9602ab32b1c4d37`. Lokal, GitHub-main und VPS waren beim
Abgleich identisch. Zwischen diesen Ständen unterscheiden sich die Pythonquellen
nicht. Dieser Bericht dokumentiert ein **Audit, keine implementierten Reparaturen**.

Keine zusätzlichen Sport-, Modell-, Quoten- oder API-Scans; keine Sicherung,
Bereinigung, Migration, Timeränderung oder Produktionscodeänderung. Offline-Repros
verwenden gemockte Anbieter, reine Funktionen oder isolierte/In-Memory-Datenbanken.
Bestehende ungetrackte Audit-/Browserdateien wurden erhalten.

## Frischer Produktionsnachweis

Read-only geprüft am 02.10.2026, ungefähr 07:08–07:25 CEST:

- `betboy-app.service` und Caddy aktiv; interner und öffentlicher Healthcheck `ok`.
- Tennis: 00:05:17–00:26:56 CEST, `Result=success`, `ExecMainStatus=0`.
- Wettfinder: 03:35:03–04:03:08 CEST, Erfolg/Exit 0; E-Sport 03:10:11–03:10:27,
  ebenfalls Erfolg/Exit 0. Fußball-Shadow 07:02:06–07:02:07: `idle/no_shadow_work_due`.
  Ein erfolgreicher Idle-Aufruf ist kein zusätzlicher Spiel-/Kontextscan.
- Sieben Timer geplant: Fußball-Shadow alle zehn Minuten, Tennis 00:05,
  E-Sport 03:10, Wettfinder 03:35, Retention 04:22 mit Zufallsverzögerung,
  Rotkarten-Historie 05:41, Rotkarten-Abrechnung 06:05.
- Fünf bereits dokumentierte fehlgeschlagene Wartungsunits vom 18./19.09. sind
  historische Fehlstatus, kein nachgewiesener heutiger App-Ausfall. Nicht neu gestartet.

Der bestehende Wettfinder-Schnappschuss ist 4.060.315 Bytes groß und trägt
`generated_at=2026-10-02T01:56:29.249111+00:00`, Version 19, Auswahlpolitik v15.
Er meldet `run_status=completed`, `operational_error_count=0`:

- 87 Modellkandidaten: 68 Fußball, 8 Tennis, 11 E-Sport. Die alten Felder
  `candidates=0` und `challenge_release_candidates=0` zählen strengere Freigaben,
  **nicht** alle in der Kundenansicht vorhandenen Modell-Auswahlen.
- Reine Leser auf diesem Schnappschuss, ohne Sportabfrage: 84 zukünftige Kandidaten,
  79 nach Kohärenzauswahl, **68 nach bekanntem exaktem 1,20-Quotenfilter**
  (52 Fußball, 5 Tennis, 11 E-Sport). Das ist kein neuer Browser-/Rendernachweis.
- Accountlose Daily3-Modellvorschau: null Auswahlen. Kein Geldkonto, Schlüssel,
  Schema oder produktiver Daily3-Datensatz wurde dafür erzeugt.
- Fußball: 12 Spiele gefunden, 11 modelliert; 11 Kontextprüfungen, null technische
  Aktualisierungsfehler, Suchumfang 52 Ligen. xG-Abdeckung bleibt teils schwach.
- Tennis: 55 vorbereitete/aktualisierte Events; der Tagesdienst speicherte 33 neue
  Prognosen. Die verwendeten ATP-/WTA-Modellartefakte stammen weiter vom 27.09.
  und werden innerhalb der vorgesehenen Sieben-Tage-Frist wiederverwendet.
  Eine neue Prognoseberechnung bedeutet nicht automatisch neue historische Formdaten.
- Basketball hat sechs Szenarien ohne nutzbare Basiswahrscheinlichkeit; Eishockey
  keinen aktuellen Schnappschuss. Cricket bleibt ohne validiertes Modell/konfigurierten
  Zugang und außerhalb der vereinbarten Implementierung. Keine Ersatzdaten erfunden.

### Der offene Gegenpreis-Nachweis ist jetzt erbracht

`tennis_price_observations` enthält **16 echte Seitenpreise aus acht Ereignissen**
der regulär empfangenen Anbieterantworten. Beide Seiten wurden separat gespeichert,
unter anderem Gea 2,32 / Hurkacz 1,75, Djokovic 1,31 / Bu 4,20 und
Carreño Busta 5,20 / Medvedev 1,24. Keine neue HTTP-Abfrage für diesen Audit.

Der reine RisikoBet-Overlay-Leser liefert fünf exakt passende Siegerpreise für
die vorhandenen Kandidaten: Darderi 1,78, Hurkacz 1,75, Tiafoe 3,40,
Carreño Busta 5,20, Bu 4,20. Die Belege sind beim morgendlichen Audit nicht mehr
ausführungsfrisch und werden nicht als aktuelle Buchmacherangebote ausgegeben.
Ein Siegerpreis wird nicht auf einen Satzmarkt oder den anderen Spieler übertragen.
Die acht Ereignisse belegen die reale Befüllung, nicht die vollständige Marktdeckung.

Die bekannte 1,20-Untergrenze verwendet bewusst exakt gebundene beobachtete
Konsenspreise bis 24 Stunden, getrennt von der kürzeren Ausführungsfrische. Deshalb
sind ältere Preisstatus im Schnappschuss **für sich allein kein Filterfehler**.
Unbekannte Preise werden weiterhin nicht als niedrige Preise erfunden. Diese
verbleibende Produktgrenze ist nicht mit vollständig belegter Marktverfügbarkeit
gleichzusetzen; Quote beeinflusst weder Modellwahrscheinlichkeit noch Modellrang.

### Offene Ergebnisse und Qualität

Der Tennis-Kontextbericht führt jetzt fünf ungeklärte Ergebnisse:
ATP **183397, 183448, 186254**, WTA **184266, 186216**. Gegenüber der Übergabe ist
ATP 183448 hinzugekommen. WTA 183992 ist nativ nicht verfügbar; WTA
183831/183844/183854 sind als Aufgabe separat behandelt. Keinen Zusammenhang
mit einem neuen Codebefund ohne ereignisspezifischen Nachweis behaupten.

Tennis-Shadow: 1.646 Prognosen, 1.349 abgerechnet, 297 offen; 1.314 Brierfälle,
Brier 0,2325. **Null Benchmarkfälle**, ROI/CLV nicht verfügbar. Ein Brierwert allein
belegt keinen Vorteil gegenüber einfachen Referenzen oder dem Wettmarkt.
Der vorhandene Kalibrierungswatch vom **28.09.**, nicht eine neue 02.10.-Messung,
meldet Drift: `set_b_2_0` 6,33 Prozentpunkte mittleren Bias, `over_21_5_games`
5,20 pp, jeweils gegen 5,00 pp Grenze. Keine Schwelle verändert.

RisikoBet-Abrechnung: 422 fällige Kandidaten in 70 Ereignissen, 88 terminal,
334 ungeklärt. Vorhandene Meldungen umfassen widersprüchliche Revisionen,
wiederverwendete Tennis-IDs, fehlende native Zuordnung und nicht belegten
Fußball-Regulationsstand. Diese Datenlücken sind getrennt von Exit 0 zu führen.

## Geprüfte aktive Pfade und Reichweite

- **Fußball:** `challenge_engine` über automatische/manuelle Auswahl, alternative
  Märkte, 15K und RisikoBet; Football-Shadow samt Tagesmarker/Exitvertrag;
  aktiver Live-Scanner inklusive Rotkarten-Abrechnung und Expositionsbericht.
  Der Live-Prematch-Prior liest zusätzlich `AdvancedBTTSAnalyzer`-Torwerte,
  nicht dessen Random-Forest-BTTS-Wahrscheinlichkeit. Dieser separate Pfad
  wurde zusätzlich auf Cachefrische, Merkmals-/Trainingsvertrag und taggleiche
  Ergebnisleckage geprüft, nicht mit den Challenge-Engine-Prüfungen gleichgesetzt.
- **Tennis:** regulärer `scripts/tennis_daily.py`-/Pipelinepfad, `tennis.predict`,
  Simulator, Shadow-Abrechnung, native Kontextaufnahme und exakte Siegerpreise.
  `scanners/tennis_scanner.py` ist dagegen Standalone; seine drei Live-
  Wahrscheinlichkeitshooks geben absichtlich `None` zurück. ATP-reguläre
  Freigabe derzeit nur Hard, WTA-Freigabe weiterhin False: nicht alle berechneten
  Beläge/Touren besitzen den gleichen historischen Qualitätsnachweis.
- **Basketball/NHL:** App-Snapshot liefert aktuell Upcoming, nicht Live; die
  generische manuelle Suche erreicht daher die Pre-Match-`no_bet`-Zweige, nicht
  die vorhandenen Live-Wahrscheinlichkeitsfunktionen. Der optionale automatische
  RisikoBet-Prematch-Pfad mit historischen Loadern und `predict_prematch` ist aktiv.
  Neutralflag-/Finalrevisionen wurden an diesen tatsächlichen Grenzen geprüft.
- **E-Sport:** native kommende Serien, deduplizierte Elo-Kernberechnung und
  Serien-/Mapmärkte, Rohhistorien-Stichprobengate, automatischer Shadow und
  RisikoBet-Prematch. Kein belastbarer Kader-/Belastungseffekt aus bloßer Anzeige.
- **Cricket:** optionaler Researchhook vorhanden; fehlender Schlüssel führt zu
  leerem Teilstatus. Generische manuelle Suche liefert `no_bet`, Live-
  Wahrscheinlichkeitshooks `None`. Kein aktuell qualifiziertes Cricket-Modell
  behauptet; keine Anbindung gebaut oder Anbieterabfrage ausgelöst.
- **Jobs/Auswahl:** generationsgebundener Scan-Speicher, Kohärenz derselben Events,
  Daily3 und bekannter exakter 1,20-Filter. Kein neuer Finanz-/Ledgeraudit ausgegeben.
- **Nicht aktive Legacy-Ranker:** Für `scanners/ultra_scanner.py`,
  `smart_bet_finder.py` und `best_bet_finder.py` wurden im aktuellen versionierten
  App-/Worker-Callgraph keine Aufrufer gefunden, nur Reexports/Standalone-Aufrufe.
  `ultra_scanner` verweigert unqualifiziertes Cross-Sport-Ranking ausdrücklich.
  Der dedizierte alte BTTS-Kartenpfad `app.render_matches` ist nicht im aktuellen
  Hauptseiten-Routing erreichbar; sein Analyzer bleibt aber der erwähnte Live-Prior.

Das ist ein technischer/mathematischer Pfadaudit mit begrenzten Repros, **kein
Vollbeweis jedes möglichen Inputs und kein aktueller Renditevergleich aller Sportarten**.

## Befunde mit Reproduktion

### T1 – P1: Der Tennis-Tageslauf entdeckt morgen statt heute

`scripts/tennis_daily.py:125` liefert in `_default_scan_date()` den nächsten lokalen
Kalendertag. `scripts/run_daily_pipeline.py:143` startet den 00:05-Lauf ohne Datum.
Offline mit 02.10.2026 00:05 Zürich ergibt die Funktion **03.10.2026**. Vorhandene
Pending-Events werden aktualisiert, heute neu bekannt gewordene Paarungen dadurch
aber nicht neu entdeckt. Ein bestehender Test verankert sogar den alten Morgen-Vertrag.
Das erklärt mögliche Lücken, beweist nicht, dass sämtliche heutigen Spiele fehlen.

Reparaturgrenze: Tagesvertrag in Zürich explizit machen; regulärer Lauf heute,
ein optionaler Vorab-Lauf morgen nur ausdrücklich. Regression um Mitternacht und
UTC/CEST-Grenze, ohne zweiten täglichen Vollscan zu erfinden.

### T2 – P1: WTA-Grand-Slams übernehmen ATP-Best-of-5

Der ATP-Turnierkatalog in `scripts/tennis_daily.py:135` setzt Grand Slams auf Bo5;
`scan_fixtures()` um Zeile 966 übernimmt dies auch für WTA. Offline wurde ein
WTA-Wimbledon-Event mit `best_of=5` tatsächlich an Predict/Speicherung übergeben.
`tennis/shadow.py:1275` verlangt dann drei gewonnene Sätze. Ein reales 2:0 wird
abgelehnt; der Daily-Abrechner fängt den `ValueError` um Zeile 618 ohne Fehlerbericht ab.

Die Regeln sehen Männer-Hauptfeld Bo5 und sonst grundsätzlich Bo3 vor
([ITF Grand Slam Rulebook 2026, I.L](https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf)).
WTA läuft derzeit ohne Serve-Simulator: Der Siegerwert wird dadurch nicht direkt
auf Bo5 umgerechnet, **Format, Abrechnung und Belastungsbelege bleiben dennoch falsch**.
Kein Nachweis, dass die fünf aktuellen ungeklärten Fälle genau diese Ursache haben.

Reparaturgrenze: Tour und Wettbewerb im Formatvertrag; korrigierte neue Belege,
alte betroffene Events nur anhand ihrer Identität und tatsächlichen Regeln prüfen.
Keine Prognosehistorie oder Geldbuchung pauschal überschreiben.

### T3 – P1: Gesamter Tennis-Anbieterausfall kann erfolgreicher Null-Lauf sein

SofaScore-/ESPN-Fehler werden in `scripts/tennis_daily.py:295` und um Zeile 637
in leere Listen umgewandelt. Ohne empfangene Antwort meldet der Capture
`no_receipts`, aber `issues=[]` (`context_sources/tennis_capture.py:65`). Der Daily-
Rückgabevertrag akzeptiert null Events ohne Modellfehler als Exit 0.

Offline: sämtlicher gemockter Transport wirft HTTP 503; `_run_daily()` endet
trotzdem mit 0, null Fixtures und null gespeicherten Prognosen. Ein legitimer
spielfreier Tag und ein gescheiterter Datenabruf sind nicht unterscheidbar.
Reparatur: gültige leere Antwort von fehlgeschlagener Antwort unterscheiden und
das im bestehenden Berichts-/Exitvertrag abbilden, keine neue Monitoringplattform.

### S1 – P1: Fußball-Shadow schreibt Fertigmarker nach fehlgeschlagenem Spielplan

`shadow_clv_automation.py:830` verarbeitet `fixtures or []`; um Zeile 859 wird der
Tagesmarker auch bei Anbieterantwort `None` geschrieben. In-Memory-Repro:
erster Aufruf null Fixtures plus Marker; zweiter Aufruf null Fixtures, insgesamt
nur **ein** Anbieteraufruf. Der fehlgeschlagene Tag wird nicht erneut entdeckt.
`scripts/run_football_shadow_due.py:24` kann Fehler aus dem Ergebnis ausgeben und
dennoch 0 zurückgeben. Offline reproduziert mit `fixtures HTTP 500`.

Reparatur: Entdeckungsmarker nur nach vollständig erfolgreichem Umfang, Teilstatus
und begrenzte Wiederholung im vorhandenen Budget; Fehler im Exitvertrag erhalten.
Ein heutiger tatsächlicher Anbieterfehler wurde nicht festgestellt.

### L1 – P1: Live-Modell endet pauschal bei Minute 93 und akzeptiert Verlängerung

`scanners/ultra_live_scanner_v3.py:19` setzt `MATCH_END_MINUTE=93`; um Zeile 296
wird Restzeit daraus berechnet. Fixturephase und gemeldete Nachspielzeit ändern
diesen Endpunkt nicht. API-/App-Pfad reicht auch laufende Verlängerung weiter.

Offline: zweite Halbzeit Minute 93 mit acht Minuten Nachspielzeit liefert null
Restzeit / **100 % kein weiteres Tor**, obwohl das Spiel läuft. Verlängerung Minute
91/92 wird wie ein fast beendetes normales Spiel behandelt. Vorhandene
`actionable=False`-/Kalibrierungskennzeichnung korrigiert diese Rechenwerte nicht.
Reparatur: tatsächlich belegte Phase und Zeit; unbekanntes Ende nicht als sichere
Nullrestzeit behandeln, Verlängerung separat modellieren oder nicht als Regulation auswerten.

### B1 – P1: Basketball-Neutralspiel verliert sein neutrales Spielfeld

NBA-/EuroLeague-Upcoming-Parser in `basketball_scanner.py:348` bzw. 215 reichen
das vorhandene Neutralflag nicht weiter. `sports_prematch.py:216` interpretiert
fehlend als nicht neutral und addiert um Zeile 412 Heimvorteil.

Offline mit `neutralSite=True` und synthetischer 80-Spiele-Historie: ohne Flag
88,74 %, mit korrekt erhaltenem Flag 49,02 %. **39,72 pp sind die Sensitivität
dieses synthetischen Falls, keine gemessene aktuelle Produktionsabweichung.**
Reparatur: identischer Neutralvertrag für Historie und kommende NBA/EuroLeague-Spiele;
NHL-Upcoming erhält das Flag bereits korrekt.

### H1 – P1: Zurückgezogenes Endergebnis bleibt im aktiven Sporthistorien-Cache

`completed_history.py:282` verwirft eine explizite spätere Nicht-Endstatus-Revision;
`fetch_page()` speichert nur positive Parserresultate. Ein zuvor gespeicherter
Endstand wird dadurch nicht entwertet (`record:183`, Leser:219).

Offline mit echter Cachelogik: Event zunächst final 100:95, dieselbe native ID
später explizit `completed=False`; Parser null neue Finals, Cache liefert weiter
Heimsieg. Der aktive Basketballpfad verwendet diesen Cache im Training.
Ausführbar für ESPN reproduziert; verwandte NHL-/EuroLeague-/Cricketparser haben
das Muster, aber nicht jeder wurde mit einem eigenen Transportfall ausgeführt.
Reparatur: explizite native Rücknahme entwertet aktive Sicht mit erhaltenem Verlauf.
Bloßes Fehlen auf einer anderen Seite darf **keine** Löschung auslösen.

### R1 – P1: Fehlgeschlagener Torabruf wird als „kein Tor“ abgerechnet

Aktiv über `betboy-redcard-settlement.service`. `api_football.py:170` gibt bei
HTTP 503 `{}` plus `last_error` zurück; `redcard_signal_log.py:273` macht daraus
eine leere Eventliste, um Zeile 282 daraus `no_goal` und anschließend `settled`.

Unabhängig zweimal offline reproduziert, einmal mit echtem API-Fehlervertrag:
Signal Minute 60 / 0:0, Endstand 0:1, Torabruf HTTP 503. Ergebnis **settled,
no_goal, Brier 0,78**. Das verfälscht Shadow-Ergebnis-/Kalibrierungsstatistiken;
kein nachgewiesener Echtgeldbuchungsfehler. Produktionsbetroffenheit noch unquantifiziert.
Reparatur: fehlgeschlagene/unvollständige Events offen lassen; gültige leere Antwort
vom Abruffehler unterscheiden, Endstand plausibilisieren. Bestehende Zeilen gezielt
prüfen, nicht löschen oder massenhaft neu abrechnen.

### F1 – P2: Eckball-/Kartenfrische verwendet stattdessen Torhistorienfrische

`challenge_engine.py:2571` bestimmt Alter aus Torspielen. Die Count-Märkte ändern
Mittelwerte/Stichprobe, übernehmen aber dieses Alter (um 2613, 2632, 2660).
Offline: 40 gültige Count-Spiele 60–99 Tage alt plus sechs frische reine Torspiele;
Eckballmärkte erhalten Evidenz 100 und keine Frischesperre bei synthetisch gültiger
Validierung. Reparatur: Frische aus den tatsächlich verwendeten Marktbelegen.

### F2 – P2: Kalibrierungsfehler einer Fußballfamilie sperrt getrennte Familien

`challenge_engine.py:1886` bildet einen globalen `projection_success` über Tore,
Ecken und Karten; um 2639 sowie im Walk-forward werden alle Familien daran gebunden.
Offline-Fehler-Injektion nur in die Ecken-Diagnose (`success=False`, Rohwert-Fallback),
Tore/Karten erfolgreich; trotzdem `RESULT_HOME` gesperrt. Kein realer Solverausfall
in Produktion festgestellt. Reparatur: Konsistenz strikt **innerhalb** der jeweiligen
Verteilung; Fehler getrennt modellierter/kalibrierter Familien nicht global fortpflanzen.
Eine statistische Unabhängigkeit von Toren, Ecken und Karten wird damit nicht behauptet.

### F3 – P2: Live-Torgrundlage bleibt im dauerhaften Analyzer-Cache veraltet

`app.py:2039` hält den Analyzer als `cache_resource` ohne TTL;
`advanced_analyzer.py:1142` speichert erfolgreiche Saisonstatistiken ohne Ablauf
oder Invalidierung. `scanners/ultra_live_scanner_v3.py:251` liest daraus seine
Prematch-Torerwartungen. Offline über genau diesen Pfad: gemockte Providerwerte
ändern sich von (1,1) auf (4,4), derselbe Analyzer bleibt ohne neue Abfrage bei
(1,1); mit frischem Testcache erhält er (4,4). Minute 30: je 0,677 statt 2,710
erwartete Resttore. **Synthetische Sensitivität, keine Produktionsmessung.**

Root bestätigte den Cachevertrag separat: Anbieter 1→3, zweite Ausgabe weiter 1,
nur ein Abruf. Der Formcache um Zeile 1195 hat dasselbe Problem (20→80 % bleibt
20 %), beeinflusst aber nur BTTS, nicht diese Live-Lambdas. Reparatur: Cachebeleg
mit Datum/Revision und begrenzter Wiederverwendung im bestehenden API-Budget;
keine unbegrenzten Refreshes und kein Cache-Reset auf jedem Seitenrender.

### J1 – P2: Alter manueller Scan kann nach neuer Generation zuletzt persistieren

`scan_jobs.py:190` markiert fertig unter Lock; Persistierung erfolgt danach ohne
erneute Generationsprüfung. Offline kontrollierte Threads: alter Scan blockiert
im Persist-Hook, Job wird gelöscht/neugestartet, neuer schreibt zuerst, alter zuletzt.
Persistfolge **[new, old]**, Speicherregister zeigt weiter new. Ein späterer Leser
kann den alten gespeicherten Stand wiederherstellen. Reparatur: generationsgebundene
Veröffentlichung samt Persistreihenfolge; kein pauschaler globaler Scanner-Lock.

### E1 – P2: Doppelte E-Sport-Historienzeilen erfüllen die 20-Spiele-Grenze

`multi_sport_recommendations.py:749` prüft rohe Listenlänge; dedupliziert wird erst
später in `esports_elo.py:64`. Offline je 20 Kopien eines Siegs/einer Niederlage:
`model_ready=True`, 61,3 %, Historienbeleg 20/20 und 0/20, obwohl Elo nur zwei eindeutige
Spiele verarbeitet. Keine Kunden-UI-Ausgabe dieses Repros gerendert. Derselbe
Auswahlvertrag liegt im E-Sport-Shadowpfad.
Reparatur: native, abgeschlossene, zeitlich zulässige eindeutige Serien **vor**
Stichprobengrenze, Formanzeige und Elo gemeinsam auswählen.

### T4 – P2: Tiebreak verwendet Haltequote als Punktwahrscheinlichkeit

`tennis/simulator.py:86` nutzt `(hold_A + 1-hold_B)/2` für den Tiebreak.
Die vorhandene `hold_to_point_prob()` bleibt ungenutzt. Referenz: gleiche
Spielhalteformel invertieren, alternierende Aufschlagfolge exakt rechnen.
Bei Haltechancen 0,80/0,70: bestehend 65,415 % vs Punktmodell 58,009 %;
0,90/0,60: 88,657 % vs 74,418 %. Einheiten-/Approximationsthema, nicht gemessener ROI.
Reparatur nur mit Modellversion und zeitlich getrenntem Qualitäts-/Kalibrierungstest;
das alternative Punktmodell ist nicht allein wegen seiner Exaktheit empirisch besser.

### T5 – P2: Tennis-Sieger- und Satzwerte entstammen verschiedenen Verteilungen

`tennis/predict.py:200` lässt Satzmärkte in der Serve-Verteilung; um 202 wird der
Sieger separat mit Elo gemischt und kalibriert. Offline gültiges symmetrisches
Serve-Modell plus Elo-Vorsprung: Sieger **82,21 %**, Summe 2:0 + 2:1 **50,00 %**.
Jede Verteilung ist normalisiert; kein Massefehler, sondern uneinheitlicher Modellvertrag.
Reparatur: gemeinsame kohärente Verteilung oder ausdrücklich getrennt qualifizierte
Marktmodelle; niemals beide als identische Vollmodellwahrscheinlichkeit darstellen.

### R2 – P2: Rotkarten-Phasenbericht verliert Expositionsminuten

Aktiv über `betboy-redcard-history.service --report`. Intervalle in
`redcard_pattern_report.py:34` verwenden 0–20, 21–40, 41–200; Exposition um Zeile
113 wird kontinuierlich als obere minus untere Grenze gerechnet. Torzählung ist
dagegen ganzzahlig inklusiv. Rotkarte Minute 43: Modellfenster 50 Minuten,
grobe Phasen zusammen **48**, feine Phasen **46**. Zweifach unabhängig bestätigt.
Reparatur: zusammenhängende Halbintervalle und konsistente Expositions-/Torzuordnung.
Kein Nachweis automatischer Übernahme dieser Berichtsraten als Live-Koeffizienten.

## Gegenprüfungen und nicht bestätigte Verdachtsfälle

- Fußball: 64 Lambda-Paare aus 0/0,05/0,3/1/2/4/6/8; Masse, Komplemente und
  BTTS-Teilmengen korrekt, maximale Abweichung 2,22e-16. Größte abgeschnittene
  Randmasse 3,55e-7, innerhalb des bestehenden Vertrags.
- Tennis: zwölf Bo3-/Bo5-Masse-/Seiten-Symmetrie-Prüfungen bestanden. Das widerlegt
  weder den Tiebreak-Proxy noch unterschiedliche Kalibrierungsmodelle.
- Separater Advanced-BTTS-Pfad: taggleiche Ergebnisänderung verändert die vorher
  erzeugten Eingaben desselben Tages nicht; Skalierung/Fit innerhalb zeitgetrennter
  Folds, gleiche sechs Serving-Merkmale aus maximal 20 Ligaspielen. Kein entsprechender
  Leakage-Befund. 64 Lambda-Paare für die separat angezeigten Dixon-Coles-/Bivariaten-
  Sensitivitäten: geschlossene vs numerische BTTS-Werte bis 0,004571 Prozentpunkte
  truncationsbedingt verschieden. Diese Sensitivitäten bestimmen den Live-Prior nicht.
  `ml_model.pkl` fehlt lokal und beim frischen read-only VPS-Dateicheck; damit fehlt
  ein dateibasierter aktueller RF-Qualifikationsnachweis. Ein etwaiger App-In-Memory-
  Modellzustand wurde nicht inspiziert; Live benötigt diesen RF-Wert ohnehin nicht.
  Live-Lambdas verwenden saisonale Heim-/Auswärtstore, keine numerischen Form-,
  Wetter-, Verletzungs- oder Müdigkeitskorrekturen aus diesem separaten Analyzer.
- Multi-Sport-Gamma-Poisson-/Siegerkomplemente und E-Sport-Serienumkehr im geprüften
  Kern konsistent; neutrale Inputs und historische Revisionen bleiben separate Fehler.
- Ein Forfeit-Verdacht wurde **nicht** als Produktionsfehler übernommen:
  [PandaScore dokumentiert](https://developers.pandascore.co/docs/matches-lifecycle)
  reguläre Forfeits als canceled ohne Beginn/Ende; diese filtert der Pfad bereits.
  Ein künstlich widersprüchlicher finished+forfeit-Payload ist höchstens zusätzlicher
  Robustheitsbedarf, kein Beweis normaler Forfeit-Verschmutzung.
- Hohe Modellwahrscheinlichkeit ist ohne Kalibrierung/Referenzvergleich kein
  nachgewiesener defensiver Vorteil. Daily3 darf weder drei Plätze künstlich füllen
  noch CHF 150 durch riskantere Auswahl oder höheren Einsatz erzwingen.
- Verletzung, Müdigkeit und Wetter bleiben ohne vollständige Anbindung und
  unabhängige Wirkungsmessung offen. Reale Listen/Beobachtungen sind nicht automatisch
  numerisch belegte Effekte. WTA-/weitere Sport-Daily3-Vergleiche bleiben unvollständig.

## Tests und Handoff-Abgleich

Heute ausgeführte Gruppen, **nicht addieren**, weil teilweise überlappend:

- Auswahlkohärenz, Scan-Jobs, Daily3 und Tennis-Preisbindung: **356 bestanden**.
- Sport-Pre-Match, Completed-History, Foundation und E-Sport-Shadow: **194 bestanden**.
- Tennis-Modell/-Predict/-Metadaten/-Preisbindung/-Pipeline: **166 bestanden**.
- Rotkarten-Log: **19 bestanden**.
- Historische BTTS-Inputs und angrenzende Auditverträge: **9 bestanden**.
- Zusätzliche reine Offline-Repros wie oben; neue Regressionstests noch nicht eingebaut.

Beispielbefehle: `.codex_test_venv\quality\Scripts\python.exe -B -m pytest -q
-p no:cacheprovider --basetemp <frischer Workspace-Temp>` mit den jeweiligen
`tests/test_scan_jobs.py`, `test_selection_coherence.py`, `test_manual_selection_coherence.py`,
`test_forecast_selection.py`, `test_daily3_selection.py`, `test_daily3_math.py`,
`test_riskobet_tennis_prices.py`, `test_sports_prematch.py`,
`test_completed_sports_history.py`, `test_foundation.py`, `test_esports_shadow.py`,
`test_tennis_model.py`, `test_tennis_predict.py`, `test_tennis_fixture_metadata.py`,
`test_tennis_price_observations.py`, `test_tennis_pipeline.py`, `test_freemode_redcard_log.py`,
`test_recent_btts_inputs.py`, `test_audit_fixes.py`.

Die Vollsuite ist **historisch vom 01.10.**, nicht heute erneut ausgeführt:
11.929 bestanden / 97 Skips / 111 Untertests. Das unveränderte eingefrorene JUnit
`output/playwright/full-frozen-1ae37d9-20261001.xml` hat erneut geprüften SHA-256
`088b6e42ac330ffbc61eb3c8918f3e1b5c36143e65991b38cce188597576715b`.
Grüne bestehende Tests zeigen hier ausdrücklich Lücken in den Testverträgen.

Alle **58 registrierten Worktrees** waren vorhanden. Kein neuer Seitenbranch-HEAD
vom 30.09.–02.10. entdeckt. Drei Dirty-Meldungen betrafen ausschließlich
`scripts/stage_runtime_databases.py`; Diffs leer, Roh-/Filter-/HEAD-/Mainblob identisch
`ff16f8a6639a0c166b1eec2a04656c6518bab2b8`, jeweils 19.138 Bytes. Keine Bereinigung.
Damit ist kein aktuelles verlorenes uncommittetes WIP entdeckt; **nicht** behauptet,
dass sämtliche historischen Branch-Commits übernommen oder fachlich vollständig sind.

## Eng begrenzte Reparaturreihenfolge

1. **Wahre Laufzustände und Tagesdeckung:** T1, T3, S1; vorhandene Tages-/Budgetverträge
   erhalten, Fehler nicht in erfolgreiche leere Daten umwandeln.
2. **Falsche Ergebnis-/Modellinputs:** R1, T2, H1, B1, L1; zuerst jeweilige
   reproduzierende Regression, dann kleine Reparatur plus unabhängiger Review.
3. **Frische/Stichprobe/Publikation:** F1, F2, F3, E1, J1 und R2.
4. **Tennis-Modellvertrag:** T4/T5 getrennt versionieren und qualifizieren; nicht nur
   Werte hübscher machen oder Schwellen lockern.
5. **Erst dann Wirkung nachweisen:** Verletzung/Belastung/Wetter aus vorhandenen
   Daten, eingefrorene Hypothese und zeitlich unabhängiger Vergleich gegen Baseline.
   Ein Software-PASS oder mehr sichtbare Tipps ist kein Prognosequalitätsnachweis.

Dieser Audit erteilt keine neue Bereinigungs-, Back-up-, Migrations-, API-Scan- oder
Geldbuchungsautorität. Code-Reparaturen sind noch nicht begonnen.
