# Kontextmodell: tatsächliche Restarbeiten, 14. Oktober 2026

Ausgang: autoritative Arbeitskopie `.worktrees/audit-repairs-20261013`,
lokal/GitHub/VPS `242093feda28a31bb8729e31529032ee059b570a`.
Der Hauptcheckout mit geerbten Änderungen bleibt unberührt.

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
