# Fußball- und Tennis-Aktualisierung: tatsächliche Fehler und Reparatur

## Ausgangslage

Am 20.09.2026 standen Worktree, lokales main, GitHub und VPS auf
`0a25fec1f6a5cfc3c6513d92b442c58039305446`. Der gemeinsame Lauf meldete
16 Fußballprobleme und acht Tennis-Prognosen mit `ContextIntegrityError`.
Zusätzlich war der vollständige Tennis-Tages-Scan am Morgen nach 900 s
abgebrochen. Gesunde App-Healthchecks beweisen keinen erfolgreichen Datenlauf.

## 1. Fußball: zulässige historische Gegner wurden verworfen

Der CSV-Loader ordnet nur die aktuellen Teams ihren positiven API-IDs zu.
Andere historische Gegner erhalten eine deterministische negative Modell-ID.
Der API-Ergebnistail verwendet bei solchen Gegnern dieselbe Zuordnung.
Die nachgelagerte Historiengrenze verlangte dagegen durchgehend positive IDs.
Damit verschwanden gerade die nötigen Vergleiche gegen andere Mannschaften.

Korrektur: negative IDs nur für die beiden bestehenden historischen Quellen
und nur bei exakter Übereinstimmung von normalisiertem Namen und deterministischer
ID zulassen. Native kommende Events bleiben auf positive IDs beschränkt.
Datum, Liga, beendeter Status, Duplikate und historisches Mengenlimit unverändert.

Echter read-only VPS-Vergleich für Fixture 1557411 / Liga 39: von 420 empfangenen
CSV-Ergebnissen ließ der alte Filter nur **2** durch; der korrigierte **420**.
Keine Quotenabfrage oder Datenbankänderung in diesem Vergleich.

## 2. Tennis: bestätigte Terminänderungen wurden als Identitätsbruch behandelt

Alle acht Fälle 1523–1530 betrafen weiterhin dieselben Spieler, Tour und
Wettbewerb. Die neueste ESPN-Beobachtung änderte ausschließlich den Spielbeginn
(teilweise von 21. auf 22. September). Der Refresh verlangte fälschlich den
unveränderten alten Zeitstempel.

Korrektur: zuerst unverändertes gespeichertes Original und Kontext prüfen;
dann eine neue aktuelle Spielkopie aus der bestätigten nativen Terminrevision
binden. Nur Beginn/Terminrevision dürfen abweichen. Die neue Modellrevision
wird angehängt; alte Revisionen bleiben unverändert. Optimistische
Schreibbedingungen beziehen sich weiterhin auf die tatsächlich gelesene alte
Revision. Bereits gestartete neue Termine werden übersprungen.

Eine spielbezogene Vorprüfung ersetzt nicht die vollständige Endprüfung.
Diese prüft weiterhin das gesamte frisch eingefrorene Inventar einschließlich
fremder, späterer oder zwischenzeitlich manipulierter physischer Zeilen.
Die bisher doppelte vollständige Historienlesung entfällt.

Echte read-only Bindungsprüfung: alle acht Fälle erfolgreich, korrekte neue
Termine, unveränderte Eingabezeilen. Dauer etwa 4,4–4,6 s pro Bindung.

## 3. Zusätzlich gemessene wiederholte Tennis-Prüfarbeit

Ein begrenzter read-only Profilvergleich an einem echten Spiel enthielt 7.659
bereits vollständig geprüfte Datensätze. Unter cProfile lagen 4,00 von 4,13 s
erneut in der Prüfung dieser Datensätze vor der eigentlichen Featurebildung.

Die veröffentlichte Folgekorrektur besitzt ausschließlich die unveränderlichen Bytes
einer vollständig geprüften Historie. Nur exakt passende, von diesem Bereich
selbst erzeugte JSON-Objekte dürfen die Wiederholungsprüfung auslassen.
Änderungen, Typ-Aliase, fremde Kopien, ersetzte interne Speicherung und Nutzung
nach Abschluss gehen wieder durch den bisherigen Prüfer. Keine Kürzung von
Historie, Referenzen, Terminkorrekturen, Marktberechnungen oder Zeitgrenzen.

Echter VPS-A/B-Vergleich in einem separaten Prozess ohne installierte Änderung:
**2,186 s alt / 0,592 s neu einschließlich Projektion**, Featurebytes identisch.
Das ist ein Nachweis für diesen Rechenschritt, noch kein ganzer Tageslauf.

## 4. WTA: eine leere Final-Platzhalterzeile sperrte das Saisonfile

Der echte Neuaufbau um 22:04 CEST scheiterte separat an `ValueError`: das native
2026-WTA-Ergebnisfile enthielt 2.132 echte Ergebnisse und eine vollständig leere
Ergebniszeile für das SP-Open-Finale. Datum/Turnier/Belag waren vorhanden, aber
beide Spielernamen, Ergebnisstatus, Sätze und Spielstände fehlten. Der bisherige
Validator verwarf deshalb das komplette File und behielt Ergebnisse bis 12.09.

Die Korrektur entfernt ausschließlich diese vollständig leeren Ergebnisplätze
aus Validierung/Training. Jede teilweise gefüllte Ergebniszeile bleibt streng
prüfpflichtig; auch ein numerischer Nullstand ist nicht leer. Die Originaldatei
des Anbieters bleibt unverändert gespeichert. Quoten steuern diese Prüfung nicht.

Die geänderte Loader-Quellkennung ist explizit in der gerichteten Replay-Liste
registriert. Die fünf Prognosemodule und die Namensauflösung sind unverändert.
Gespeicherte ältere Originale werden mit ihren damaligen Modellständen ohne
Download oder Neutraining bytegenau nachgespielt; fremde Quellkennungen bleiben
abgewiesen. Es werden keine alten Prognosen oder Hashes umgeschrieben.

Echter kanonischer VPS-Neuaufbau am **20.09.2026, 22:31:59 CEST**: Exit 0,
ATP `retained_fresh`, WTA `published`, Ergebnisdatum **20.09.2026**,
WTA-Artefakt `e8325052185e6d831d396a37e33a8983f95587878408de9077a03624f1338371`.

## 5. Vollständiger Tages-Scan: gemessene CPU-Kapazität

Der zusätzliche Lauf 22:04–22:19 CEST war noch nicht erfolgreich: 161 Fixtures,
74 vorbereitete Originale und 592.739 WTA-Referenzen. Datenempfang dauerte etwa
90 s, vollständige physische Historienprüfung weitere 462 s. Bei Original 70/74
lief nach 900 s das alte harte Limit ab, noch vor der Veröffentlichung.

Auch die JSON-/Referenzvalidierung hatte bei mehr als 500.000 Werten ihre gesamte
Wiederverwendung abgeschaltet. Große Listen werden nun in maximal 8.192 Werte
großen, wertgebundenen Cacheblöcken verarbeitet; Anzahl der Cacheeinträge bleibt
begrenzt. Alle Werte, Reihenfolgen-, Typ- und Eindeutigkeitsprüfungen bleiben
erhalten. Kein Wegschneiden von Historie und keine neue Speicherstruktur.
Lokale Wiederholungsmessung an 592.739 Referenzen: Key-Bildung 0,689 s vorher,
0,431 s nachher. Kein Anspruch auf diese Beschleunigung für den gesamten Lauf.

Der Tages-Scan erhält zusätzlich ein **endliches 35-Minuten-Budget** statt
15 Minuten. Grundlage sind die obigen tatsächlichen Phasenmessungen, keine
geänderte Qualitätsprüfung. Selbst alle maximalen Montagsschritte bleiben mit
175 Minuten unter dem unveränderten systemd-Gesamtlimit von drei Stunden.
Der neue vollständige Scan lief **22:31:59 bis 23:04:25 CEST**: alle 74
Berechnungen verarbeitet, **66 neue Prognosen** gespeichert, kein Timeout.
Sein Exitcode war dennoch 1, weil die Kontextaufnahme noch `partial` meldete.
Dieser Teilschritt war damit technisch nicht vollständig abgeschlossen.

## 6. Tennis: reguläre Turnierplätze verursachten einen falschen Fehlstatus

ESPN liefert in denselben Antworten neben ATP-/WTA-Einzeln auch Doppel,
Einzel der jeweils anderen Tour und noch unbesetzte Turnierplätze (`TBD`).
Die Beobachtungen werden korrekt als nicht modellierbar gespeichert. Die
Aufnahme wertete fehlende Einzelspieler-IDs jedoch auch bei diesen erwarteten
Fällen als allgemeinen Datenfehler. Dadurch blieb der Dienst trotz vollständig
veröffentlichter Prognosen auf Fehler.

Korrektur `7c805aeae0df6b85e68178adc7f40756cf99a06f`: bekannte fremde
Spielarten und ausdrücklich unbesetzte, geplante/abgesagte Turnierplätze
getrennt zählen. Native Statuszeilen, Rücknahmen, Referenzen, Abrechnungsquellen
und Modellierbarkeit bleiben unverändert. Fehlende IDs echter Spieler,
defekte Termine/Statusangaben, fehlende IDs in unbekannten Formaten und unvollständige Endstände
bleiben echte Fehler. Die CLI protokolliert konkrete Aufnahmefehler und die
Zahl erwarteter Ausschlüsse statt nur `partial`.

Read-only Gegenprobe auf dem VPS am **21.09.2026 ca. 00:09 CEST**, mit zwei
echten öffentlichen ESPN-Antworten: **500 Wettbewerbe**, darunter 127 fremde
Spielarten und 89 unbesetzte Turnierplätze. Alt: `invalid-participants`;
neu: keine Aufnahmefehler. Alle erzeugten Beobachtungen und Abrechnungsquellen
zwischen alt/neu exakt identisch. Keine Speicherung und keine Modellfreigabe.

113 gezielte Tests und 418 weitere Tests bestanden (überlappende Teilmengen,
nicht addieren). Drei alte UI-Assertions wurden ausschließlich an die bereits
veröffentlichte knappe Preisanzeige angepasst; Modellwerte bleiben explizit
geprüft. Anschließend komplette Suite auf `7c805ae`: **10.773 bestanden,
96 übersprungen, 111 Untertests bestanden**, Exit 0 nach **2.013,19 s**.
Die Skips benötigen Linux/DAC/FIFO/flock oder auf Windows nicht verfügbare
Symlinkrechte. Neun Warnungen betreffen `record_property` mit JUnit-xunit2,
nicht einen Appfehler. JUnit-Datei unter
`output/playwright/tennis-refresh-20260921-final-junit.xml`, SHA-256
`2f84d8a30a27051e9368e2e66b3613c5bdd8de270d10444c40b90c17bbdebdcc`.
Der XML-Zähler 10.980 enthält auch 111 Untertests und 96 Skips; nicht zusätzlich
zu den pytest-Zählern addieren. Artefakt bleibt lokal, keine Tests auf Produktion
installiert und keine Linux-spezifischen Skips als bestanden ausgeben.
Commit seit **21.09.2026 00:17:09 CEST auch auf dem VPS**. App-Neustart und
beide Healthchecks erfolgreich, alle sieben aktiven Timer wiederhergestellt.
Kanonischer Tennis-Dienst startet 00:17:10, Modellaufbau 00:17:12 mit Exit 0
beendet. Neuer Scan endet **00:50:10 nach 1.979 s** ohne Timeout: **74/74**
berechnet, 74 neue unveränderliche Prognose-Originale. **0 neue Shadow-Zeilen**,
weil diese Partien schon vorhanden sind, also nicht 74 neue Tipps.
Erwartete fremde Spielarten (15.279) und TBD-Plätze (89) erzeugen keine Fehler
mehr. Aufnahme bleibt jedoch `partial` wegen zweier anderer Ergebniskategorien,
siehe Abschnitt 8. Gesamtdienst endet **00:50:26 mit Exit 1**, nicht erfolgreich.
Montags-Kalibrierungsprüfung 00:50:25 Exit 0 (9.864 ausgewertete Spiele,
angebotene Satzmärkte `ok`; separater Referenz-Spieltotalmarkt mit Drift),
Wochenreport 00:50:26 ebenfalls Exit 0. Das ist kein Nachweis besserer
Kontextwirkung oder eines profitablen Wettvorteils.

## 7. Separater Fußball-Kontingentengpass beim Tageswechsel

Der reguläre Wettfinder **00:07:18–00:16:48 CEST** endete vor dem letzten
Deployment mit 13 Fußball-Abruffehlern. Diese sind keine Rückkehr der
Identitätsfehler: jede Fehlermeldung stammt aus dem API-Budgetschutz.
Der Hintergrundabruf für Historien/Statistiken stoppt unter 2.500 Restabrufen.
Tennis-Refresh und Fußball-Kontextaufnahme meldeten in diesem Lauf keine Fehler.

Read-only Zählerprüfung 21.09. ca. 00:22 CEST: Tageslimit 7.500,
5.057 abgeschlossene Abrufe am UTC-Tag 20.09. (1.464 background, 3.593
recommendation), Restschätzung 2.443, zuletzt vom Anbieter gemeldet 2.445.
Die Reserveschwelle wurde nicht abgesenkt, keine Sperre umgangen und kein Tarif
geändert. Laut [API-Football-Bedingungen](https://www.api-football.com/terms)
erneuert der direkt angebundene Dashboard-Zugang sein Tageskontingent um
00:00 UTC, aktuell **02:00 CEST**. Der lokale Governor verwendet ebenfalls
UTC-Tage. Bis zum nächsten erfolgreichen Abruf ist der Fußball-Tagesbestand
unvollständig; die alten grünen Läufe ersetzen diesen aktuellen Befund nicht.
Der bestehende Wiederholpfad `football_due` versucht unvollständige Tagesläufe
nach mindestens 25 Minuten erneut. Der aktive halbstündliche Timer sieht nach
dem Reset regulär **02:07 CEST** vor; es ist kein neuer Timer oder manueller
Start nötig. Ein erfolgreicher Nachhollauf ist damit noch nicht bewiesen.

## 8. Verbliebene Ergebniszuordnung: vier echte historische Teilnehmerwechsel

Der volle Neulauf meldet `native-outcome-conflicting` und
`native-outcome-unavailable`. Es sind keine verbliebenen TBD-/Doppel- oder
Timeoutfehler. Die gespeicherten Originals und ihre nativen Ausgangsbelege
sind unverändert prüfbar; die späteren Ergebnisantworten nennen andere Spieler.

Read-only Prüfung der 131 aktuell wieder empfangenen abgeschlossenen Events
mit gespeicherten Originals, danach zwei direkte öffentliche ESPN-Antworten
für 15./16. September. Der unveränderte native Ergebnisadapter bestätigt:

| WTA-Match | Ursprüngliche Paarung (native Spieler-IDs) | Späteres Ergebnis | Aktueller Schutz |
|---|---|---|---|
| 183831 | 17296 / 3641; später auch 17296 / 6769 gespeichert | 17296 / 6769 | Mehrere ursprüngliche Teilnehmeridentitäten: keine automatische Auswahl einer Linie |
| 183854 | 2731 / 6769; später auch 2731 / 2441 gespeichert | 2731 / 2441 | Mehrere ursprüngliche Teilnehmeridentitäten: keine automatische Auswahl einer Linie |
| 183844 | 14460 / 3406 | 14460 / 5626 | Keine passende ursprüngliche Teilnehmerpaarung |
| 183710 | 2752 / 18673 | 5803 / 18673 | Keine passende ursprüngliche Teilnehmerpaarung |

Die Gegenprobe umfasste **540 Wettbewerbe, 124 Original-Events mit möglicher
Ergebnisquelle und 118 Events mit bindbaren Ergebnisbeobachtungen**. Exakt die
vier oben genannten Events meldeten die beiden Fehlerkategorien. Die Differenz
zwischen 124 und 118 beinhaltet weitere zeitlich nicht zulässige Originale,
nicht sechs Fehlermeldungen. Probe vollständig ohne Datenbankänderung.

Ein zunächst zusätzlich auffälliger Fall 183674 enthält eine spätere Prognose
nach dem korrigierten Start, besitzt aber auch ein gültiges früheres Original.
Die tatsächliche Adapterprüfung bindet dessen Ergebnis korrekt; er gehört
**nicht** zu den vier verbleibenden Fehlerfällen.

Der bestehende Vertrag lehnt solche Vermischungen bewusst ab (unter anderem
`test_distinct_native_original_revisions_are_not_silently_joined`). Er wurde
nicht gelockert, keine Originale geändert, keine fremden Gewinner gespeichert,
keine Geldbuchungen korrigiert und kein Dienstfehler manuell zurückgesetzt.

Nutzerentscheidung angefragt: die vier historischen Fälle unverändert als
„nicht auswertbar – Teilnehmer geändert“ getrennt ausweisen, ohne jeden neuen
Tageslauf als technisch fehlgeschlagen zu melden. Das wäre eine ausdrücklich
getrennte Behandlung historischer Ergebnislücken und aktueller Prognosefehler;
keine nachträgliche Tipp-/Effektfreigabe. Bis zur Antwort keine entsprechende
neue Statusregel implementiert. Deshalb **keine Gesamterledigung behaupten**.

## 9. Neue Abschlussausnahme beim parallelen regulären Tennis-Refresh

Der Wettfinder lief 21.09. 00:37–00:56:30 CEST gleichzeitig mit dem Tageslauf.
Sein veröffentlichter Bericht von 00:48:38 enthält beim Tennis-Modellrefresh
`status=failed`, `failure_type=ContextIntegrityError`. Zusätzlich bestehen die
13 Fußball-API-Reservefehler. Der bisherige Catch speicherte weder Nachricht
noch Fehlerort. Daher keine Gleichsetzung mit den vier historischen
Teilnehmerwechseln und keine Behauptung, die genaue Ausnahme sei behoben.

Neue Diagnose `e8f0faf`: nur begrenzte Dateinamen, Zeilen/Funktionsnamen und
höchstens drei explizite Fehlerursachen ins administrative Serverlog. Keine
Exception-Nachrichten oder lokalen Variablen, kein zusätzlicher Fehlertext im
öffentlichen Ergebnis. Test mit privater Haupt- und Ursachenmeldung bestätigt
diese Trennung. **147 Tests** der Worker-/Refresh-Integration bestanden.

Read-only Gegenprobe: alle 74 zukünftigen Prognosen können gebunden und neu
vorbereitet werden. Sie benutzt dieselbe Berechnung mit gesperrtem Netzwerk,
rein lesenden Datenbankverbindungen und einem Abbruch vor Veröffentlichung.
Die erste Probe stoppte am Schreibversuch der bestehenden Schemainitialisierung;
das ist ein Diagnoseharness-Fehler, kein reproduzierter Produktionsfehler.
Die korrigierte Probe verwendet vorhandene Tabellen lesend, reduziert nur die
Anzahl neu zu berechnender Partien auf eine, **nicht** die physisch geprüfte
Historie. Ergebnis: **651.445 WTA-Verweise**, vollständige Historienprüfung,
Modell-/Freigabeinventarprüfung und Vorbereitung dieser Prognose bestanden.
Nach **487,038 s** erreicht sie die Veröffentlichung und bricht dort absichtlich
mit `PreparedWithoutWrites` ab. Keine Daten geschrieben, kein Netzabruf. Das ist
eine erfolgreiche Vorbereitung, **kein** realer Veröffentlichungstest und keine
Reproduktion/Behebung der früheren Ausnahme.

Folgender regulärer Wettfinder **01:07:04–01:16:07 CEST**: Tennis `unchanged`,
keine Fehler, **0 fällige Refreshes**. Damit keine Abnahme des Abschlussfehlers.
Zwölf Fußballfehler durch API-Reserve, Gesamtdienst weiterhin Exit 1.

`e8f0faf4667e7611c16dc27a521da1a803846b63` auf Worktree, lokalem main, GitHub
main und VPS bestätigt. Deployment unter bestehendem Lock bei inaktiven
Schreibdiensten, nur zwei Code-/Testdateien geändert, keine Migration,
Backups oder Bereinigung. App neu gestartet, lokaler und öffentlicher
Healthcheck `ok`, sieben zuvor aktive Timer wieder aktiv. Tagesbackup bleibt
deaktiviert. Die vollständige 10.773er-Suite gilt für `7c805ae`, die zusätzliche
147er-Regressionsrunde für die Diagnoseergänzung; Zähler nicht addieren.

## Prüfung und Veröffentlichung

- Erster Reparaturcommit `e292b108d48c9be19400323f8b46b74ecc24dc39` auf
  lokalem main, GitHub main und VPS am 20.09.2026 um 21:28 CEST bestätigt.
- 849 betroffene Tests, 7 Skips und 32 Untertests vor dem ersten Release grün.
- Zweiter Funktionscommit `eea0703b5dd96b51f458b38c61d82e85ae6d19ea` um
  22:04 CEST deployed: validierte Tennis-Bytes innerhalb eines Batches teilen.
- Dritter Funktionscommit `f6b7c66026e7591449c7722d53640d17a5a88ce2` um
  22:31 CEST auf Worktree, lokalem main, GitHub und VPS bestätigt. Unmittelbar
  davor **1.620 Tests bestanden, 3 Skips**; weitere 124 fokussierte Prüfungen
  grün (überlappende Zählung, nicht addieren). Erster Vollsuite-Lauf erreichte
  7.458 bestandene Tests, bevor eine alte UI-Textassertion scheiterte; kein
  vollständiger Erfolg. Nach Korrektur dieser Tests erneuter kompletter Lauf.
- Einmaliger Wettfinder-Neuberechnungslauf `--force-football`: 21:28:21 bis
  **21:49:09 CEST, Exit 0**. Fußball **0 Aktualisierungsfehler**, 30 Modelle;
  Tennis **8/8 fällige Prognosen aktualisiert, keine Fehler**. Native Termine
  aller acht Datensätze anschließend read-only geprüft.
- Unmittelbar folgender regulärer Wettfinderlauf: **21:49:09 bis 21:54:59 CEST,
  Exit 0**, erneut Fußball/Tennis ohne Aktualisierungsfehler. Weiterer regulärer
  Lauf **22:07 bis 22:13:38 CEST, Exit 0**, beide Quellen weiterhin fehlerfrei.
- Weiterer regulärer Lauf **22:37 bis 22:55:25 CEST, Exit 0**: veröffentlichter
  Status `completed`, **0 technische Fehler insgesamt**, Fußball 30 Modelle,
  Tennis acht vorbereitet, sechs aktualisiert, zwei wegen paralleler Revision
  korrekt nicht überschrieben. WTA nutzt den neuen Ergebnisstand vom 20.09.
- App und lokaler Healthcheck nach Codewechsel gesund. Keine Datenmigration,
  Installation, Bereinigung, Backupaktivierung oder manuellen Datenkorrekturen.
  Die normalen Berechnungen dürfen neue Prognosen/Beobachtungen speichern.

## Abgrenzung

Vollständige native Fußballbezüge und empirisch bestätigte
Verletzungs-/Belastungswirkung sind separate fachliche Themen. Diese Reparatur
erzeugt weder fehlende Daten noch eine Effektfreigabe. Cricket bleibt ausgenommen,
Preisfilter und Geldbuchungen unverändert. Abschluss erst anhand echter
veröffentlichter Laufresultate und des separaten Tennis-Tages-Scans bestätigen.
