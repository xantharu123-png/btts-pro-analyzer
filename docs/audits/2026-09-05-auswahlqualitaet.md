# Audit: Warum BetBoy unbrauchbare oder einseitige Auswahlen zeigt

Stand: 05.09.2026. Geprüfter Commit: `511e1535e835c264c434db67663b769f63761232`.

## Urteil und Umfang

Die Kritik hat konkrete Ursachen in Auswahlregeln, Datenversorgung, Aktualisierung und der Bedeutung der angezeigten Kennzahlen. Ein gesundes Deployment und bestandene Funktionstests belegen keine fachlich nützliche oder profitable Auswahl. Der aktuelle Stand erfüllt insbesondere die gewünschte kontextsensitive Außenseiteranalyse über sechs Sportarten nicht vollständig.

Nicht nachgewiesen ist, dass alle angezeigten Prognosen falsch sind oder die App einen bestimmten Verlust verursacht. Dazu fehlt eine hinreichende, zeitkorrekte und quotengebundene Ergebnisauswertung. Eine verlorene Einzelwette widerlegt ebenso wenig eine Wahrscheinlichkeit wie eine gewonnene sie bestätigt.

Prüfung: Übergabedokumente, Nutzeranhang, aktueller Code, drei unabhängige Teilprüfungen, isolierte Offline-Reproduktionen, lesende VPS-Prüfung und gerenderte Produktionsoberfläche. Keine neuen Sportdaten-Providerabrufe, keine Konto-/Ticketänderungen, keine Codeänderungen, kein Push oder Deployment. Dieser Bericht ist das einzige neu angelegte Projektartefakt.

## Frisch erhobener Produktionsstand

Lokal, GitHub `main` (direkt mit `git ls-remote`) und VPS stehen auf demselben vollständigen Commit. App und Caddy sind aktiv, interner Healthcheck `ok`, sieben BetBoy-Timer sind geplant. Das Problem ist kein fehlender Pull. Die Timer berechnen beziehungsweise sichern Daten, deployen aber keinen Code.

Stichprobe: veröffentlichter Lauf vom 05.09.2026, 13:37 Uhr Zürich / 11:37 UTC. Das sind Momentaufnahmen, keine unveränderlichen Gesamtbestände.

| Beobachtung | Messwert |
| --- | --- |
| Fußballspiele gefunden / modelliert | 159 / 104 |
| Normale sichtbare Prognosen | 21: 15 Fußball, 3 Tennis, 3 E-Sport |
| Fußball-Markttypen in diesen 15 Karten | ausschließlich Teamtore oder Teamecken |
| Vergleichsquote in den 21 Karten | bei allen nicht verfügbar |
| Kontextalter der 15 Fußballkarten | alle als veraltet markiert; geprüft um 00:14 Uhr |
| RisikoBet | 187 Kandidaten; Oberfläche: 100 Events |
| RisikoBet-Sportarten mit Kandidaten | Fußball 172, Tennis 11, E-Sport 4 |
| RisikoBet-Kontext | 69 teilweise, 118 offen; keine vollständig frischen Kandidaten |
| Modellzeit der RisikoBet-Tennisprognosen | 04.09.2026, 05:17 UTC, trotz neuem Lauf |

Beispiel im echten Browser: RisikoBet führt Persija über 1,5 Tore als Top-Szenario mit Modell 33,2 %, vorsichtig 7,7 %. Unter „Spricht dafür“ stehen unter anderem eine zu kleine H2H-Stichprobe und „Wetter: geprüft“. Das sind keine nachgewiesenen sportlichen Vorteile dieses Szenarios.

## Befunde

### F1 — P1: Der normale Wettfinder übernimmt weiterhin die 15K-Untergrenzen

`challenge_engine.py:2126–2133` sperrt Modellwahrscheinlichkeiten unter 58 % und vorsichtige Wahrscheinlichkeiten unter 55 %. Der normale Scanner setzt in `wettfinder_automation.py:2126` lediglich `allow_above_challenge_probability=True`: Das hebt die obere 92-%-Grenze auf, nicht die unteren Grenzen. `challenge_engine.py:3176` verwirft Kandidaten mit Sperrgründen auch für den normalen Katalog.

Reproduktion mit echten Funktionen, erfolgreicher injizierter Validierung, Evidenz 100 und identischen Saison-/Formmodellen:

| Markt | Modell | Vorsichtig, angezeigt | Im normalen Katalog |
| --- | ---: | ---: | ---: |
| BTTS Ja | 57 % | 52 % | nein |
| BTTS Ja | 60 % | 55 % | nein |
| BTTS Ja | 61 % | 56 % | ja |
| Auswärtsteam unter 2,5 | 94 % | 89 % | ja |

Folge: Ausgeglichene Märkte, viele Remis und Außenseiter werden vor der normalen Auswahl entfernt. Hohe Eintrittswahrscheinlichkeit wird strukturell bevorzugt. Das beweist nicht, dass jede verworfene Wette gut wäre; es erklärt aber den einseitigen Katalog.

Zusätzlicher P2-Grenzfehler: `0.60 - 0.05` liegt in binärer Gleitkommaarithmetik knapp unter `0.55`. Deshalb kann die Anzeige 55,0 % lauten und die Prüfung trotzdem „unter 55 %“ melden.

### F2 — P1: Die Kürzung entfernt Alternativen vor der Marktvielfalt-Auswahl

`wettfinder_automation.py:759–805` bricht am Kataloglimit ab. `build_daily_forecast_catalog` in derselben Datei, Zeilen 842–867, begrenzt Fußball auf 15 Einträge und bewahrt deren vorherige Reihenfolge. Erst anschließend diversifiziert `wettfinder_surface.py:452–475` die Topkarten nach Event/Marktfamilie.

Reproduktion: 15 zulässige `HOME_OVER_1_5` für unterschiedliche Spiele, danach ein zulässiger BTTS-Markt. BTTS an Position 16 verschwindet. Die tatsächliche Oberflächenkomposition liefert dann nur eine Topkarte; mit allen 16 Eingangskandidaten liefert sie zwei unterschiedliche Topkarten.

Folge: Eine nachgelagerte UX-Regel kann verlorene Alternativen nicht wiederherstellen. Das erklärt wiederholte Teamtor-Karten, ohne irgendeine Wettart pauschal verbieten zu müssen. Die künstliche Eingabereihenfolge isoliert den Fehler; sie ist kein behaupteter vollständiger Replay des heutigen Laufs.

### F3 — P1: Beim 220. Saisonspiel bricht die verfügbare Historie ein

`challenge_15k.py:726–744` ergänzt die Vorsaison nur, solange die aktuelle Historie weniger als 220 Spiele enthält. Das unverändert aus dem Code extrahierte Verfahren wurde mit kontrollierten Daten ausgeführt:

- 219 aktuelle + 380 vorherige Spiele: 599 historische Spiele.
- 220 aktuelle + 380 vorherige Spiele: nur noch 220 historische Spiele.

`challenge_engine.py:50` verlangt mindestens 24 vorherige Spiele zur Modellierung, `:68` mindestens 200 Validierungsbeobachtungen. Mit nur 220 Rohspielen bleiben nach dem Mindestvorlauf höchstens 196 Beobachtungen; ein echter Walk-forward-Lauf auf dem vorhandenen synthetischen Testdatensatz ergab sogar nur 180.

Folge: Eine Liga kann gerade durch ein zusätzliches Ergebnis sämtliche ausreichend belegten Marktfreigaben verlieren. Die heutige Zahl gesperrter Kandidaten allein beweist nicht, wie viele davon durch genau diese Schwelle verursacht wurden; die Fehlfunktion selbst ist reproduziert.

### F4 — P1: Versprochener Kontext wird überwiegend angezeigt statt eingerechnet

Fußball: `challenge_engine.py:2676–2718` setzt für die numerische Kontextwirkung ausdrücklich `applied=False`, `adjustment_pp=0.0`. Wetter, Ausfälle und Aufstellungen dienen Verfügbarkeit, Hinweisen und möglichen Vetos. Sie verschieben nicht die ausgewiesene Ergebniswahrscheinlichkeit.

RisikoBet: `riskobet_candidates.py:573–587` kennzeichnet Kontext als `DISPLAY_ONLY`, übernimmt aber auch neutrale beziehungsweise lediglich beobachtete Informationen in die Pro-Liste. „Keine Gegenindikation“ oder „Wetter geprüft“ ist kein Beleg für eine erhöhte Außenseiterchance.

Tennis: `tennis/predict.py:109–174` enthält Belag, Elo, Best-of, Indoor und Serve-Werte. Akute Verletzung, Ruhetage, Reise und Dauer/Satzzahl des vorherigen Matches fehlen als Modelleingaben. Die vorhandene `match_duration`-Spalte im Datenloader wird hierfür nicht genutzt. „Der Favorit spielte gestern fünf Sätze“ hat daher keinen eigenen berechneten Effekt. Belag ist hingegen tatsächlich berücksichtigt.

Produktursache: Die Spezifikation (`docs/superpowers/specs/2026-09-01-riskobet-design.md:18–23`) verbietet richtigerweise erfundene, unvalidierte Kontext-Prozentpunkte. Daraus folgt aber nicht, dass die gewünschte validierte Kontextmodellierung fertig wäre. Die bisherige Umsetzung liefert vielfach einen Katalog vorhandener Wahrscheinlichkeiten statt der verlangten konkreten Matchup-Analyse.

### F5 — P1: Drei Sportfilter haben im Standardlauf keine historische Datenanbindung

`wettfinder_automation.py:2398–2424` sucht `get_completed_games`, `get_completed_nhl_games`, `get_completed_matches`. Diese Methoden existieren in den tatsächlich verwendeten Basketball-/Cricket-Scannern nicht. Ohne zusätzlich injizierten Historienloader bleibt `history=()` (`:2466–2482`); genau das ist der Standardpfad der drei Quellen.

Reproduktion mit eindeutiger Spielidentität und leerer Historie: Basketball, Eishockey und Cricket liefern jeweils `model_probability=None`.

Folge: Auch ein funktionierender Cricket-Schlüssel allein würde keine fundierte Prognose ermöglichen. Die frühere Aussage „nur Cricket-Zugangsdaten fehlen noch“ war zu weitgehend. Sechs Filter sind nicht sechs vollständig angebundene Modelle.

Zusätzlich verwenden die drei Adapter bei verfügbarer Historie denselben generischen Siegquoten-/Log5-Ansatz (`riskobet_candidates.py:1701–1711`, `1798–1812`) und jeweils einen Siegermarkt. Beispiel 2/8 gegen 6/8 Siege: in allen drei Sportarten identisch 20 % Modell und 0 % vorsichtig. Heimvorteil, Gegnerstärke, Punkte/Tore, Goalie oder Pitch sind dabei keine eigenen numerischen Eingaben. Das ist eine begrenzte Forschungsbasis, kein ausgereifter sportspezifischer Wettfinder.

### F6 — P1: Aktualisierung berücksichtigt neue Spieltermine und -status nicht zuverlässig

`challenge_15k.py:2736` lädt frische Spielinformationen. Zeilen 2769–2785 übernehmen daraus Aufstellungen/Wetter, aber weder das neue `fixture.date` noch `fixture.status` in den behaltenen Kandidaten.

Reproduktion mit der echten Refresh-Funktion: gespeicherter Kandidat heute 12:50, frische Providerantwort morgen 12:00. Für die Statuswerte `NS`, `PST` und `CANC` blieb jeweils eine normale Auswahl sowie ein strenger Shortlist-Eintrag mit `release_eligible=true` und der alten Uhrzeit bestehen. Andere Kontextdaten waren vollständig.

Folge: Verschobene oder abgesagte Events können in der falschen Tagesauswahl bleiben. Nicht bewiesen ist eine daraus entstandene platzierte Wette; spätere exakte Quoten-/Eventbindung kann weiterhin ablehnen. Dieser Befund betrifft fachliche Eventkorrektheit, keine künstliche Sperre wegen einer Quote.

### F7 — P1/P2: Frischer Lauf bedeutet nicht frische Modellprognose

Tennis: `scripts/tennis_daily.py:631–648` kann neu rechnen. `tennis/shadow.py:734–754` aktualisiert bei einer schon vorhandenen Zeile aber nur Termin-/Providerdaten; `p_cal`, `markets_json`, `created_utc` bleiben eingefroren. RisikoBet liest genau diese erste Prognose (`riskobet_candidates.py:1092–1115`); eine zusätzliche aktuelle Modellrevision fehlt in diesem Pfad. Das passt zum frisch erhobenen Modellstand von gestern trotz aktuellem Lauf.

Die ursprüngliche Prognose für eine ehrliche Ergebnishistorie zu erhalten ist richtig. Es fehlt daneben die neueste kausal berechnete Revision für die aktuelle Benutzeransicht, ohne die frühere Historie zu überschreiben.

Fußball: Erfolgreiche Tagessuche wird nicht wiederholt (`wettfinder_automation.py:194–228`); Kontext wird erst innerhalb von zwei Stunden vor Spielbeginn erneut ausgewählt (`:1264–1288`), obwohl er nach 75 Minuten als veraltet gilt (`:115`, `1724–1742`). Reproduktion: Scan 00:05, jetzt 12:00, Spielbeginn 14:01 => keine Tagessuche und kein Kontextrefresh. Das erklärt die 15 alten Kontextstände am frühen Nachmittag. Die Warnung in der Oberfläche ist korrekt; diese Aktualisierung erfüllt dennoch nicht die Erwartung fortlaufend aktueller Analysen.

### F8 — P1: RisikoBet-„Top“ ist primär eine zeitliche Auswahl

`riskobet_automation.py:430–443` sortiert zuerst nach Spielbeginn, Sport und Event-ID; erst danach nach Evidenz, Kontext und Wahrscheinlichkeit. Die Qualitätsfelder können daher verschiedene Events nicht gegeneinander priorisieren. `riskobet_surface.py:539–548` nimmt die ersten nicht einfachen Szenarien verschiedener Events. Bei „Alle“ kommt Sport-Round-Robin hinzu.

Reproduktion mit einem Top-Platz: früheres Szenario 18 % / vorsichtig 3 %, Kontext offen, wird vor späterem 46 % / vorsichtig 39 %, Kontext frisch, angezeigt.

Folge: „Top-Szenarien“ suggeriert eine fachliche Priorisierung, die so nicht existiert. Die Lösung wäre nicht einfach „höchste Wahrscheinlichkeit zuerst“, sondern ein explizites und geprüftes Nützlichkeitsranking mit konkreter sportlicher Evidenz, Modellgüte und Unsicherheit. Die bestehende Preisunabhängigkeit bleibt dabei erhalten.

### F9 — P1: Die „vorsichtige Trefferchance“ ist keine nachgewiesene Untergrenze

Fußball `challenge_engine.py:2101–2113` verwendet vereinfacht:

`min(aktives Modell, Saisonmodell, Formmodell) - heuristischer Abschlag`

Der Abschlag berücksichtigt unter anderem den größten absoluten historischen Kalibrierungsfehler eines Wahrscheinlichkeitsbereichs und ist auf 20 Prozentpunkte begrenzt. Dieser Fehler kann aus einem anderen Bereich stammen und auch Unterprognosen abbilden. Für die fertige vorsichtige Zahl ist im untersuchten Pfad keine validierte Abdeckung als individuelle Wahrscheinlichkeitsuntergrenze nachgewiesen. Bei Tennis-Siegermärkten werden pauschal 15 Prozentpunkte abgezogen, bei den geprüften RisikoBet-Satzmärkten 10 (`riskobet_candidates.py:1213`, `1228`, `1240`).

Reproduktion: Gleiches Fußballmodell 75 %, gleiche sonstige Bedingungen, maximaler Kalibrierungsfehler 5 statt 16 Prozentpunkte => vorsichtig 70 statt 59 %, ohne Änderung der aktuellen Modellwahrscheinlichkeit.

Die Mindestpreisformel in `betting_math.py:130` ist davon getrennt: Sie verwendet die vorsichtige Wahrscheinlichkeit und die festgelegte Zielmarge. Beispielsweise erklären 57,6 % ungefähr `1,03 / 0,576 = 1,79`. Das behauptet nicht, dass ein Buchmacher 1,79 anbieten müsste. Der fachliche Streitpunkt ist die Belastbarkeit der zugrunde gelegten 57,6 % und weshalb diese Auswahl überhaupt prominent erscheint. Nicht die Division selbst.

### F10 — P1: Modellvalidierung ist nicht Nachweis nützlicher Wettpreise

Der historische Vergleich in `challenge_engine.py:1811` ist die geglättete Häufigkeit des jeweiligen Ereignisses, keine Buchmacherprognose. `candidate_model_utility` (`:515–527`) nutzt Verbesserung gegenüber diesem Vergleichswert mal Evidenzgewicht.

Damit kann ein Modell gegen eine einfache Basis gut abschneiden, ohne dass seine Auswahl gegenüber angebotenen Preisen besonders interessant wäre. Umgekehrt beweist ein fehlender solcher Vergleich nicht, dass das Modell unwirksam ist. Die bestehende Walk-forward-/HAC-/FDR-Prüfung ist nicht wertlos; ihre Aussage ist enger als „gute Wette“.

Frische, ausschließlich aggregierte Datenbankabfragen auf dem VPS:

| Analysebestand | Umfang | Preise/Ergebnisse |
| --- | ---: | --- |
| `shadow_clv.db` | 1 Prognose | 1 mit Ergebnis, Eingangs- und Schlussquote, versioniert |
| `btts_data_clv.db` | 0 Prognosen | keine |
| Tennis-Shadow | 1.162 Prognosen | 887 abgerechnet; keine Eingangs- oder Schlussquoten in den geprüften Preisfeldern |
| E-Sport-Shadow | 489 Prognosen | 138 abgerechnet, davon 82 Treffer |
| RisikoBet | 1.419 gespeicherte Kandidaten | 171 Ergebnisbuchungen: 42 gewonnen, 128 verloren, 1 void |

Diese Rohzahlen sind kein ROI und kein fairer Qualitätsvergleich: unterschiedliche Märkte/Wahrscheinlichkeiten, Kandidaten desselben Events und Versionen müssen getrennt behandelt werden. Insbesondere ist eine geringe Trefferquote bei Außenseitern nicht automatisch ein Fehler. Der aktuelle Nachweis für einen breiten Vorteil gegenüber tatsächlich angebotenen Preisen reicht nicht aus.

### F11 — P2: Die Preisprüfung deckt nicht den gesamten Suchumfang ab

`wettfinder_automation.py:105–106`, `941–981`, `3207–3215` begrenzt die automatische Preisprüfung auf zehn Spiele und bis zu acht Märkte pro Spiel. Reproduktion mit 90 zulässigen Spielen: 15 veröffentlichte Fußballkarten und zehn preisgeprüfte Spiele. Es gibt in diesem Pfad keine Rotation allein deshalb, weil frühere Spitzenkandidaten keine brauchbaren Vergleichsquoten geliefert haben.

Im beobachteten Lauf: 36 Fußballmärkte aus zehn Spielen preisgeprüft, alle ohne verfügbare Referenzquote. Tennis meldet fehlende Zugangskonfiguration für den Preisprovider, E-Sport keinen verifizierten passenden Quotenprovider. Für Fußball ist mit dieser Prüfung noch nicht vollständig geklärt, ob konkrete Marktverfügbarkeit, Mapping oder Datenversorgung die fehlenden Referenzen verursacht. Es wurden bewusst keine neuen Provideraufrufe ausgelöst.

Das ist eine Kapazitäts-/Abdeckungslücke, nicht der Nachweis einer Quotensperre für sichtbare Prognosen. Die aktuellen Tests und die Live-Oberfläche bestätigen: Fehlende oder niedrige Quoten entfernen die bereits aufgenommenen Modellkarten nicht.

## Einordnung des vorhandenen älteren Audits und Plans

`AUDIT_BERICHT_2026-09-02_CLAUDE.md` und `UMSETZUNGSPLAN_MARKTBENCHMARK_2026-09-02.md` wurden als übernommene, ungetrackte Nutzerartefakte unverändert gelassen. Mehrere Kerndiagnosen sind bestätigt, aber nicht alle Schlussfolgerungen:

- Simulierte Verluste sind keine gemessenen BetBoy-Verluste. Eine bestimmte Modellfamilie ist nicht allein wegen ihrer Einfachheit erwiesenermaßen unprofitabel.
- Andere Torformeln, Dixon–Coles, längere Historie oder Marktgewichtung sind Vergleichskandidaten, keine ohne Evaluation nachgewiesenen Verbesserungen.
- Fréchet behandelt Abhängigkeit, der Vorsichtsabschlag Modellunsicherheit. Beides ohne Prüfung als denselben Fehler zu entfernen wäre nicht gerechtfertigt.
- Der Benchmarkplan zählt neun Märkte, nennt aber acht: drei Resultate, drei Double-Chance und zwei Over/Under. Bei 90 Definitionen bleiben 82 andere.
- Eine aus zwei Siegerquoten berechnete Double-Chance-Quote ist eine synthetische Zwei-Positionen-Strategie, keine beobachtete native Buchmacherquote.
- Ein Backtest mit einer einzelnen historischen Quote bildet die heutige Mehranbieter-/Frische-/Ausführbarkeitsprüfung nicht vollständig nach.
- Modellwissen und Quote müssen zum selben Entscheidungszeitpunkt verfügbar gewesen sein. Eine Montagsquote darf nicht mit einer erst freitags informierten Prognose bewertet werden.
- Der vorgeschlagene neue Marktvergleich als Voraussetzung für Echtgeld-/Ticketfreigabe ist eine zusätzliche Produktregel; er beweist nicht automatisch profitable Auswahl. Der alte Plan lässt Prognosen ausdrücklich sichtbar (Zeilen 166–168); diese Nutzerregel muss erhalten bleiben.

## Sinnvolle Reparaturreihenfolge — noch nicht implementiert

1. **Korrektheit:** aktuellen Eventstatus/Termin übernehmen; Historie an der 220er-Schwelle stetig halten; Rundungsgrenze korrigieren; erste und neueste Tennisrevision sauber trennen.
2. **Auswahlprodukt:** normalen Wettfinder von 15K-Eintrittsgrenzen trennen; den vollständigen geeigneten Pool vor Topauswahl/Diversifizierung behalten; RisikoBet-Top nach expliziter fachlicher Nützlichkeit auswählen oder ehrlich zeitlich benennen. Nicht einfach mehr Karten erzwingen.
3. **Echte sechs Sportarten und Kontext:** historische Datenloader anschließen; sportspezifische Modelle und Kontextmerkmale aufbauen und unabhängig zeitlich testen. Fehlende Daten nicht durch erfundene Wahrscheinlichkeiten oder Effektgewichte ersetzen.
4. **Messbarkeit:** eingefrorene Vorhersagen nach Markt, Modellversion und Entscheidungszeit mit Ergebnissen, passenden Angebotsquoten und späteren Vergleichsquoten auswerten. Prognosegüte und realisierbarer Wettpreis bleiben getrennte Ergebnisse, keine pauschalen Sichtbarkeitssperren.
5. **Abnahme:** kontrollierte Tests für alle oben reproduzierten Fehler; veränderte Auswahl im vollständigen Pool nachweisen; unveränderte Reihenfolge/Sichtbarkeit bei fehlenden oder niedrigen Quoten; keine pauschalen Verbote für Team-Unter-1,5, Team-Über-0,5 oder andere Marktarten; anschließend frische Produktions- und Browserprüfung.

## Prüfnachweise und Grenzen

- Drei unabhängige lesende Codeprüfungen abgeschlossen; zentrale Befunde gegen die tatsächlichen Funktionen beziehungsweise eng isolierte Originalmethoden reproduziert.
- Acht gezielte bestehende Regressionstests bestanden. Sie belegen unter anderem Preisunabhängigkeit; sie beweisen keine Profitabilität.
- Kein neuer vollständiger Suite-Pass behauptet. Die übernommene `.venv` referenziert einen fehlenden alten Python-Pfad; isolierte Prüfungen verwendeten das verfügbare Python und vorhandene Bibliotheken. Eine Methode wurde wegen nicht importierbarer Nebenabhängigkeiten unverändert per AST isoliert.
- Live-Wettfinder und RisikoBet im Browser gelesen, RisikoBet gerendert visuell geprüft. Datenbankabfragen nur im SQLite-Lesemodus und nur auf aggregierte Analysebestände, nicht auf persönliche Konten oder Tickets.
- Kein Fehler wird als bereits behoben bezeichnet. Es wurde nichts committed, gepusht oder auf dem VPS verändert.
