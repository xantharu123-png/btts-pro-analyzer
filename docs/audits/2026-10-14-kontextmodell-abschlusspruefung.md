# Kontextmodell: tatsächliche Restarbeiten, 14. Oktober 2026

Ausgang: autoritative Arbeitskopie `.worktrees/audit-repairs-20261013`,
lokal/GitHub/VPS `242093feda28a31bb8729e31529032ee059b570a`.
Der Hauptcheckout mit geerbten Änderungen bleibt unberührt.

## Neuester Stand der Fortsetzung

**Aktueller Abschluss:** QA04 hat den unveränderten ursprünglichen Speichertest
und sämtliche alten Tests bestanden: 14.035 PASS, 98 Skips, 147 PASS-Untertests,
beide Shards Exit 0. Alle 14.133 IDs exakt einmal, alle 13.922 alten + 211 neuen
erhalten; 97 alte Skip-IDs identisch. Neuer realer Symlinktest ist allein wegen
Windows WinError 1314 übersprungen, auch nach scoped Dateisystemretry.
21 eingefrorene Source-/Testhashes und zehn Root-WIP-Codehashes anschließend
identisch. Nativer Footprint-Pfad vermeidet die kausal nachgewiesene Intern-Dict-
Allokation; ursprünglicher kombinierter Peak 7.720.933 → 30.604 Bytes, keine
Grenzanhebung/Warmups/GC/Testverkürzung. Alte Path-Rückgabe, vollständige
Admission, Fehlerpolitik, zweite stat-Raceprüfung und alle SQL-Budgets erhalten.
Gezielte unabhängige Reviews ohne offene Befunde. Quellen-Release steht jetzt
an; kein numerischer Effekt oder besseres Wetter-/Verletzungsmodell daraus.

Nutzerentscheidung: nur vorhandene und kostenlose Quellen. ATP-/WTA-Dauer ist
bereits vorhanden, wo geliefert, aber ohne automatisch belegte individuelle
Spielendzeit/native Bindung/damalige Veröffentlichung. Native Fußballminuten,
vor Anpfiff empfangene Wetterprognosen und getrennte belegte Tennismerkmale
zuerst verwenden. Neue kostenpflichtige Tarife werden nicht eingerichtet.
Realer Quellenanschluss, qualifizierte Kohorten und öffentliche Anwendung
bleiben offen. Kein historischer Winner wird in einen Same-call-POINT-Capture
umbenannt; WTA mit Serve-Gewicht null ist keine Joint-Baseline.

Die nachfolgenden QA03-/QA02-Status sind erhaltene Fehlerhistorie, nicht der
aktuelle Release-Status. Belege: root `output/context-completion-20261014/qa-final-04`
und `native-footprint/parent-combined.xml`.

QA03 ist vollständig abgeschlossen:13.980PASS/1FAIL/97 unveränderteSkips und
147PASSUntertests. JUnit-Abgleich14.078Items exakt einmal; keine fehlenden,
doppelten oder unerwarteten Fälle. Einziger FAIL: ursprünglicher Speicher-
grenzentest7.720.876Bytes bei unverändert524.288. Ein voll gesammelter A-Kontroll-
prozess mit ausschließlich diesem diagnostisch selektierten Knoten bestand
mit461.173Bytes. Sammlung allein ist daher keine belegte Ursache. Scoped
AllocationGREEN unten ist kein abgeschlossener breiter Speicherfix. Die frühere
Vermutung eines Player-Load-Stillstands war nicht aus dem Fortschrittsmarker
beweisbar; die Vollgruppen endeten regulär nach3105,87/3044,42s.
Kein Veröffentlichungsgate erfüllt; weitere begrenzte Kausaldiagnose statt
neuer Vollsuite. Die anschließende Beschreibung der laufenden QA03 ist historisch.

Zwei weitere konkrete Fehler sind jetzt lokal repariert und unabhängig geprüft:
die unnötige Zwischentupel-Allokation im Speicherprüfpfad und der geschützte
Ergebniszugriff in der neuen POINT-D4-Nachrechnung. Der originale Cold512KiBTest
und das gesamte unveränderte Refchunksmodul bestehen; alle sechs gültigen
Limitänderungen bleiben erkannt. Finaler POINT-Schutzlauf93PASS/26neueFälle;
ursprüngliche volle Gegenprobe ohne Labelzugriff und ohne Datenänderung.
Direkte Ergebnisleser und sämtliche alten Quellenfamilien bleiben unverändert.

QA02 wurde für den belegten POINT-Zugriff bei47%A/29%B beendet, ohne Abschluss-
JUnit/ohnePASS. Neue QA03 läuft auf20eingefrorenen Source-/Testdateien und
14.078Items: alle13.922bisherigen plus156neue. Keine Suite wird ausgefiltert.
Main-/VPS-Release erst nach tatsächlichem vollständigem Abschluss.

Die frische vorhandene Winner-Rohinventur14Oct10:36:53UTC zählt5367Publikationen,
1045erste native Ereignisse und936passende normale Ergebnisbindungen:
ATP270/WTA666. Keine geschützten Testplan-/Experiment-/Dataset-Artefakte waren
vor diesem lesenden Inventurlauf vorhanden. Keine Gewinner/Renditen ausgewertet,
Merkmals-/Trainings-/Testqualifikation weiter offen. Die ältere149/312-Zahl
bezieht sich auf Winner-Belege einer POINTmodellGeneration, nicht auf neue
same-call-POINT-Publikationen: deren physischer Katalog ist nochleer. Neue
Capturebelege entstehen erst nach Veröffentlichung und regulärer Berechnung.
Fußball hat107Binding-/Body-/Manifestpublikationen; die früheren8 waren nur
eine ausgewertete Teilmenge. Publikationen sind nochkeine unabhängigen Testfälle.

Aktuelle Kontextdatei7350726656Bytes; SQLite-Seiteninventar1794611*4096,
freelist0. Das sind Dateiseiten, nicht gemessene JSON-/wichtige Modelldatenbytes.
Eine anschließende rein physische BLOB-Längensummenprobe wurde nach8s planmäßig
unterbrochen, vor dem ersten Resultat; daraus keine Payloadsumme, Korruption
oder Aufräumgarantie ableiten. Keine Datei/Datenbank kopiert, gelöscht oder
verkleinert. Das aktuelle C-File-Inputlimit4GiB passt nicht auf diese Datei.
Ein normaler abgeleiteter B1-Suchindex ist ein anderer erreichbarer Kandidat,
aber noch nicht implementiert/installiert: exakte optionale Schemaannahme,
begrenzter atomarer Build und derselbe reale45sGegentest müssen nachgewiesen
werden. Weder ein C-Proofflag noch automatisch unboundedDDL/ANALYZE ist erlaubt.

Die Zahl vorhandener Matches ist daher nicht gleichbedeutend mit fehlenden
oder vorhandenen geeigneten Merkmalen. Tatsächliche Verletzungs-, Wetter- und
Müdigkeitseffekte, ihre Testkohorten und öffentliche Anwendung bleiben offen.
Keine zufälligen Abschläge und keine bessere Wettqualität aus Software-PASS.
Siehe neuestenTODO/SDD task21,task10protected-final,task22history-owner.

## Was als numerischer Abschluss zählt

Eine vorhandene Ausfallliste oder Wetterabfrage ist kein Wahrscheinlichkeitseffekt.
Erforderlich sind die tatsächlichen, zeitlich passenden Eingangsdaten, eine
eindeutig zugehörige gelernte Modellvariante, ihre unabhängige Prüfung und die
Anbindung an die tatsächlich verwendeten zukünftigen Marktwerte. Alte Prognosen
und Geldbuchungen werden nicht nachträglich geändert.

Die bereits freigegebene Spezifikation verlangt mindestens 200 unabhängige,
unberührte Testspiele zusätzlich zu Training und Abstimmung, drei Zeitblöcke,
gepaarte Verbesserung, Kalibrierung und keinen Logloss-Rückschritt. Diese
Prüfung wird nicht durch mehr Softwaretests oder fingierte Spieldauern ersetzt.

## Konkrete technische Lücken

1. Tennis-POINT-Belege: Die tatsächliche gemeinsame Berechnung brauchte eine
   eigene Veröffentlichung und vollständige Nachrechnung einschließlich des
   Sieger-Grundmodells. Historische Siegerbelege dürfen nicht rückwirkend als
   neue POINT-Verteilung umetikettiert werden.
2. Fußball-Spielerbelastung v3: Training und unabhängige Datenauflösung nehmen
   unterschiedliche Quellenpools. Der zusätzliche Nationalteam-Einsatz eines
   Clubspielers muss auf beiden Seiten identisch berücksichtigt werden.
3. Große Fußball-Quellenpools: 7 von 8 zuletzt untersuchten echten Originalen
   scheitern vor der Merkmalsberechnung an der 4-MiB-Gesamtquellen-Grenze. Ein
   Streaming-Umbau darf dieses bestehende Gesamt-I/O-Limit nicht heimlich als
   bloßes RAM-Limit ausgeben. Ein späterer v3-Kontextzeitpunkt benötigt zudem
   einen eigenen Nachweis für die vollständige zusätzliche Spielerhistorie.
4. Öffentliche Anwendung: Der Fußballworker erzeugt derzeit nur Experimente;
   die Anbindung einer tatsächlich unabhängig geprüften Modellfreigabe an
   künftige verwendete Marktwerte ist separat zu vervollständigen.
5. Tennis-Rekonstruktion: Die konkrete Teilnehmer-Historienabfrage überschritt
   das begrenzte 45-Sekunden-Prüfbudget vor dem ersten Merkmalsvektor. Dies ist
   eine durch den Prüf-Progresshandler ausgelöste Abfrageunterbrechung und kein
   Nachweis einer beschädigten Datenbank.

## Frische Dateninventur ohne neue Sportabfrage

Read-only VPS-Stichtag `2026-10-14T07:24:41.086527Z`, Laufzeit 1,414 Sekunden.
Die tatsächliche Tennis-POINT-Generation wurde vor der Auswahl des ersten
gültigen Originals je Ereignis bestimmt. Frühere Modellgenerationen werden
nicht als geeignete aktuelle Trainingsfälle gezählt.

| Modellseitig Best-of-3 | ATP | WTA |
| --- | ---: | ---: |
| Eindeutige POINT-Ereignisse | 149 | 312 |
| Passende native Ergebnis-Header | 134 | 248 |

Erste POINT-Stichtage `2026-10-02T22:06:58.708802Z`; keine POINT-Best-of-5-Fälle.
Die Ergebnis-Header sind Obergrenzen vor Quellen-, Merkmals-, Trainings- und
Testprüfung. Es wurden keine Gewinner, Verluste oder Prognosewerte zur Auswahl
eines günstigen Experiments benutzt. Vier vorab zeitlich festgelegte
Merkmalsfälle lieferten wegen des Abfrageengpasses noch keinen Merkmalsvektor.

Ein eigenes kalibriertes Sieger-Modell der POINT-Generation könnte belegte
Erholungsuntergrenzen auswerten. Das identifiziert weder Aufschlagwirkung noch
exakte Spieldauer; Satz-/Game-Modelle bleiben getrennt. Beidseitige Endstände
sind keine Aufschlag-Erfolge/-Versuche. Dieser mögliche nächste Modellvertrag
ist noch nicht implementiert, gelernt oder empirisch freigegeben.

## Aktueller Arbeitspaketstatus

- POINT-Veröffentlichung und owning Replay/D4 lokal umgesetzt: 472 gezielte
  Tests bestanden; separate unveränderte Cache-/Shadow-Prüfung 44 bestanden,
  drei bestehende Plattform-Skips. Zahlen sind überlappend und keine Vollsuite.
  Unabhängiger Review ohne offene Befunde.
- Die zuerst aufgetretenen 19 TEMP-/Hardlink-Sandboxfehler sind erhalten und
  ohne Produktionscodeänderung in korrekter Testumgebung nachgewiesen behoben.
- Fußball-v3-D4-Parität lokal abgeschlossen: finale begrenzte Runde 71 PASS,
  davon 26 neue echte SQLite-Grenzfälle, keine Skips. Unabhängiger Review ohne
  offene Befunde. Die zusätzlich entdeckte Modelltyp-Verwechslung im fünften
  Owner ist korrigiert; I/O-Grenzen und später-v3-Entscheidungsnachweis unverändert.
- Noch keine neue Veröffentlichung, numerische Aktivierung oder Behauptung
  besserer Wettqualität. Finaler Regressionstest und Produktionsnachweis folgen
  erst nach Ende der begrenzten Implementierung.

## Verworfenes Experiment und letzter Reviewfehler

Die lokal schnellere Tennis-Mitgliedschaftsabfrage wurde mit exakt denselben
vier vorab bestimmten Fällen und unverändertem 45s-Gesamtbudget auf dem VPS
geprüft. Bereits die erste Abfrage wurde unterbrochen; kein Merkmalsvektor.
Der Kandidat ist deshalb nicht im Paket. `context_models/tennis_training.py`
ist bytegleich mit der Basis, die 35 Kandidatentests bleiben ausschließlich
als Diagnose außerhalb der aktiven Testcollection erhalten. Keine alte
Test-ID wurde dafür entfernt, und kein Laufzeitbudget erhöht.

Der kombinierte Gegenreview fand einen echten P2: Mehr als 500 Empfangsschlüssel
konnten nach erfolgreicher Prognoseveröffentlichung das optionale POINT-
Ergebnislesen und damit den ganzen Abschluss abbrechen. Repariert wurde nur
die begrenzte optionale Admission: vollständige interne Ablehnung bei zu
großer Sammlung, keine Teilmengenkürzung. Integritäts-, Quellen- und Zeitfehler
werden weiterhin nicht unterdrückt. Tatsächliche RED-Runden 4+2 Fehler;
GREEN 9 eigene Fälle, Nachbarn 131 PASS/3 bestehende Windows-Skips. Der
unabhängige Abschlussreview bestätigt null offene Befunde auf diesen Hashes.

Die bereits begonnene kombinierte Vollrunde wurde dafür gezielt beendet und
hat keinen PASS. Neu eingefrorene finale Collection: 14.038 Hauptitems,
darunter alle 13.922 bisherigen IDs und 116 neue. Zwei disjunkte vollständige
Dateigruppen laufen jetzt in `qa-final`; Abschluss-JUnit und exakte
Einmal-Abdeckung sind vor Veröffentlichung noch auszuwerten.

Zusätzlicher begrenzter read-only Abfrageplan (keine Kontextzeilen gelesen):
SQLite benutzt bei der aktuellen Teilnehmerfindung einen vollständigen Scan
des `context_event_receipts`-Indexes und einzelne Inhalts-PK-Lookups. Ein
alternativer Tabellenzugriff (`NOT INDEXED`) wurde nur im Prüfprozess auf
denselben vier Fällen bei unverändertem 45s-Budget versucht. Auch er wurde vor
dem ersten Vektor unterbrochen; ebenfalls keine installierte Änderung. Ein
Indexplan allein ist keine Geschwindigkeits- oder Merkmalsabdeckungsgarantie.
Die erste Planprüfung brach vor Datenbanköffnung an einem Windows-/Linux-
Rohhashvergleich ab; die zweite verglich korrekt den installierten Git-Blob.

Die finale Vollrunde hat bisher einen existierenden unveränderten Streaming-
Speichertest als Fehler gemeldet. Eine gezielte echte Wiederholung bestätigte
645.510 statt weniger als 524.288 gemessenen Python-Bytes. Ursache wird separat
diagnostiziert; Limit und Test-ID unverändert, kein Vollsuite-PASS oder Release.

Endgate: A bei47% angehalten, B bei65% anschließend kontrolliert beendet.
Beide Exit1 ohne Abschluss-JUnit, kein weitererBFehler berichtet, kein PASS.
Die unveränderten Cold-Proben
ergaben zusätzlich641.969/641.984 Bytes. Voll-GC nach der Messung senkt den
aktuellen Bestand, nicht den bereits gemessenen Peak; GC vor Messung allein
und reine Cursor-Schließung beheben ihn nicht. Ein fixer19-Ref-Warmup bestand
isoliert, scheiterte jedoch im vollständigen owning Modul mit993.124 Bytes
(71PASS/1FAIL). Die additive reale1MiB-Negativkontrolle bestand korrekt.
Der Harnesskandidat ist deshalb nicht akzeptiert, Basistest vollständig
hergestellt und Diagnose außerhalb aktiver Collection erhalten. Keine alte
Test-ID/Grenze entfernt oder Quelle zur Erzeugung eines PASS abgeschwächt.
Dies ist kein Beleg eines neuen großen gehaltenen Referenzpuffers und auch
keine native-RSS-Freigabe. Das technische Prerequisite-Paket bleibt lokaler
reviewter Arbeitsfortschritt bis zu tatsächlicher abschließender Regression;
numerische Effekte, empirische Freigabe und Produktion sind nicht abgeschlossen.

Source-Checkpoint `291525211ab0e66591e878a6217b568a739293f8` auf dem bestehenden
Entwicklungsbranch committed/gepusht, ausdrücklich keine main-Integration.
Frische Remote-/read-onlyVPS-Prüfung: main und VPS `242093f`, App/Caddy aktiv,
beide Healthchecks `ok`; letzter Tennisservice Result success/ExecMainStatus0.
Kein neuer Pull oder Restart. Alle17frozenSource- und10inheritedRootHashwerte
unverändert. Alle verworfenen Experimente/RED-Runden erhalten, keine Datenbank-
kopie oder neue API-Sportabfrage; vollständige numerische Ziele bleiben offen.

Belege außerhalb von Git: `C:/Projekt/BetBoy/output/context-completion-20261014`.
Kein neuer API-/Sportscan, Backup, Produktionsdatenbankabzug oder Bereinigung.
Cricket sowie Quoten-/Einsatzregeln bleiben unverändert.
