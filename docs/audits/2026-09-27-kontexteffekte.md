# Kontextwirkungen: tatsächlicher Stand am 27.09.2026

## Ergebnis

**Nicht als abgeschlossen melden.** Die Datensammlung und der mathematische
Anschluss an das aktive Fußballmodell hatten konkrete Lücken. Dieser Stand
repariert die Wetteraufnahme und ergänzt den passenden numerischen Rechenweg.
Er schaltet keine ungeprüften Verletzungs-, Wetter- oder Müdigkeitskoeffizienten
ein und belegt noch keine höhere Trefferquote oder Rendite.

Ausgangsstand war `eaf432c4f0baa02be14bb73a0f4b22573b9d645e`.
Cricket, Quotenlogik, Echtgelderfassung und Timerfrequenzen bleiben unverändert.
Keine neue Sicherung, Datenbankkopie oder zusätzlicher Sport-/API-Scan.

## Reparaturen

1. **Echte Wetteraufnahme statt nur Anzeige.** Die bereits angeforderte
   OpenWeather-Antwort wird während des vorhandenen Fußballworkers mit ihrer
   tatsächlichen Empfangszeit und einem vorher bekannten Spiel gespeichert.
   Ein Cachetreffer erhält keinen neuen Zeitstempel. Geänderte Paarung,
   Spieltermin oder Stadt dürfen nicht rückwirkend angeheftet werden.
2. **Passende Wettermerkmale.** Stadtpunkt, Temperatur, Wind und Niederschlag
   sowie Vorhersageversatz und Empfangsalter haben einen eigenen Merkmalsvertrag.
   Das sind keine Stadionmessung und kein Beleg für ein offenes Stadiondach.
   Neuere Teilwerte oder widersprüchliche Antworten werden nicht durch ältere
   passende Werte ersetzt. Fehlende Zahlen bleiben fehlend.
3. **Passende Fußballmathematik.** Das aktive Modell verwendet eine kalibrierte
   gemeinsame Ergebnisverteilung; der vorhandene, nicht aktivierte Kontextadapter
   konnte dagegen nur unabhängige Poisson-Verteilungen berechnen. Der neue
   separate Rechenweg erhält die
   tatsächliche gemeinsame Verteilung: `q(h,a) proportional p(h,a)*exp(dh*h+da*a)`.
   Ohne Änderung bleibt die Originalverteilung exakt erhalten. Alle betroffenen
   Tor-/Ergebnismärkte werden zusammen daraus berechnet; Karten und Ecken bleiben
   unverändert. Die Koeffizienten werden gegen die gekoppelte Likelihood gelernt,
   nicht aus dem alten Poisson-Fit übernommen. Trainingsskalierung wird bewahrt.
   Diese Funktionen sind ausdrücklich numerische Offline-Bausteine, kein
   aktivierter Live-Effekt und kein Ersatz für den quellgebundenen Datensatz.
4. **Getrennte Tennisbestandsprüfung.** Die Diagnose zählt passende Ergebnisse
   nach ATP/WTA und Entscheidungstag. Ein schneller reiner Bestandsmodus erzeugt
   keine Merkmale, öffnet keine Testauswertung und verändert die Datenbank nicht.

Die Bedeutung der vorhandenen Wetterfelder folgt der
[OpenWeather-forecast5-Dokumentation](https://openweathermap.org/api/forecast5):
`dt` ist der Gültigkeitszeitpunkt, kein Ausgabezeitpunkt. Fehlende
Niederschlagsphänomene und beschädigte vorhandene Niederschlagsobjekte werden
unterschiedlich behandelt. Keine neue Providerleistung wurde hinzugefügt.

## Lesende Produktionsmessung

Gemessen am 27.09., 08:15–08:27 UTC, ausschließlich an vorhandenen Belegen.

| Bereich | Tatsächlicher Bestand |
| --- | --- |
| Tennis | 3.259 Veröffentlichungen, 377 verschiedene rechtzeitige Originalspiele |
| Passendes normales Tennisfinale | 346 Spiele: 64 ATP, 282 WTA |
| Vollständig quellgebundene gespeicherte Fußballpakete | 3 von 45 Paketen; 42 teilweise |
| Unaufgelöste Fußball-Quellverweise | 12.402 wegen Aufnahmebudget, 528 ohne passenden nativen Beleg |
| Wetterbelege vor dieser Reparatur | 0 |
| Gespeicherte qualifizierte Kontext-Effektartefakte | 0 |

Die Fußballaufnahme ist nicht vollständig ausgeschaltet: Die Zulassungsdatei
hatte am 27.09. 56 MiB reserviert, davon 4 MiB an diesem Tag. Das bestehende
Gesamtlimit beträgt 128 MiB. Diese Grenzen wurden nicht erhöht oder zurückgesetzt.
Die Fehlerzahlen zählen Quellverweise, nicht unabhängige Spiele.
Der vorhandene Wetterschlüssel ist auf dem VPS konfiguriert; dafür wurde nur
sein Vorhandensein geprüft, weder der Schlüssel ausgegeben noch die API aufgerufen.

Zwölf zeitlich gleichmäßig ausgewählte Tennisoriginale wurden zusätzlich auf
Belastungsmerkmale geprüft, ohne Gewinner zu vergleichen oder ein Modell danach
auszuwählen. In allen zwölf fehlten nutzbare Minutendifferenzen. Nur ein Fall
hatte einen Zahlenwert für die Drei-Tage-Satzdifferenz, aber keine vollständige
beidseitige Abdeckung. Zehn Fälle hatten eine beobachtungsgebundene
Erholungsuntergrenze; zwei hatten keine passende Historie einer Seite.
**Das ist eine begrenzte Stichprobe, keine Aussage, dass alle 282 WTA-Fälle
unbrauchbar wären.** 282 Endergebnisse allein beweisen aber keinen Müdigkeitseffekt.

Fünf verschiedene zuletzt gespeicherte Fußballoriginale wurden mit dem neuen
Code rein im Speicher auf dem VPS vollständig numerisch nachgerechnet.
Bei allen fünf stimmen Originalmärkte und kalibrierte Verteilungen exakt;
ein Nulleffekt verändert keinen Markt. Das ist ein numerischer
Produktionsdaten-Test, keine empirische Kontextqualifikation.

## Prüfung

- Wetteraufnahme einschließlich Cache, Spielbindung, späteren Antworten,
  Teilwerten, Konflikten und eigenen Stadtmerkmalen geprüft.
- Gemeinsame Verteilung, Nullidentität, alle Torwetten, unveränderte andere
  Märkte, gekoppelte Gradienten gegen numerische Differenzen, fehlerhafte
  Koeffizienten und Optimierungsabbrüche geprüft.
- 65 gezielte Tests bestanden; anschließend 10 Bestandsprüfungen einschließlich
  ATP und WTA in derselben Datenbank bestanden.
- Letzter gezielter Provider-/Beobachterlauf: 248 Tests und 32 Untertests
  bestanden; zusätzlicher Mathematik-/Bestands-/Wetterlauf: 54 Tests bestanden.
- Breitere Kontext-/Fußball-/Wettfinder-Regression: **5.869 bestanden,
  21 übersprungen, 32 Untertests bestanden**, Laufzeit 23:22 Minuten.
  Auswahl: `test_context_*`, `test_football_*`, `test_openweather_*`,
  `test_challenge_15k.py`, `test_wettfinder_automation.py`,
  `test_workflow_integrity.py`. Keine vollständige Repository-Suite.
  Die abschließenden gezielten Läufe oben decken auch die während der breiten
  Regression ergänzte Beobachter-Isolation und Bestandsdiagnose ab.

## Verbleibende Arbeit – nicht nur auf Daten warten

1. Für Fußball müssen die neuen gemeinsamen Rechengesetze noch an vollständig
   quellgebundene Trainingsfälle und die bestehende Auswertung/Modellanwendung
   angeschlossen werden. Die alten Raw-Poisson-Fälle dürfen dafür nicht umbenannt
   werden. Vollständige Fälle innerhalb des bestehenden Speicherbudgets aufbauen.
2. Entscheidung und Kontext müssen zeitlich zusammenpassen: Nach der
   ursprünglichen Modellberechnung erhaltenes Wetter darf nicht als vorher
   bekannt gelten. Ein Vergleich braucht einen tatsächlich späteren
   Vor-Spiel-Entscheidungszeitpunkt und die unveränderte Originalreferenz.
3. Bei Tennis zunächst den vollständig nutzbaren Bestand pro Merkmal und Tour
   ermitteln; danach Trainings-/Abstimmungsdaten und unbenutzte Testspiele strikt
   trennen. Die bestehende Mindestanforderung von 200 Testspielen pro geprüfter
   Kohorte wird nicht durch Zusammenzählen von ATP und WTA erfüllt.
4. Erst ein vollständig geprüfter echter Vergleich kann zeigen, ob ein Effekt
   überhaupt verbessert. Es ist möglich, dass ein Merkmal keinen Vorteil bringt.
5. Die erste tatsächliche Wetteraufnahme muss im nächsten bestehenden
   planmäßigen Fußballlauf geprüft werden. Kein zusätzlicher Scan dafür.

Die separate Tennis-Dienstnachprüfung am 28.09. um 02:00 CEST bleibt bestehen;
sie ist weder Modelltraining noch ein automatischer Wirkungsnachweis.

## Fortsetzung: quellgebundenes Training am 27.09.

Ausgangscommit dieser Fortsetzung: `5a445235d1aa17cae9491c6d4ce983d69c23d2bc`.
Die Arbeit schließt einen Teil der obigen Restpunkte 1 und 2; nicht den
empirischen Nachweis und nicht den vollständigen Produktivanschluss.

### Implementiert

- `football_training.build_joint_training_case` rekonstruiert einen Fall aus
  vorhandener Originalbindung, Originalfragmenten, nativen Quellrevisionen,
  passendem Endergebnis und nativer Spielidentität. Das erweiterte Original
  entsteht nur im Speicher; kein weiteres Vollpaket wird gespeichert.
- Die Originalberechnung wird einschließlich Kalibrierung, Torverteilung,
  ausgewählter Historie und Quellenzuordnung nachgerechnet. Vertauschte
  Beleglisten zwischen Spielen werden abgelehnt. Verwendete xG brauchen ihre
  tatsächlichen Statistikbelege; eine Zahl aus einem alten Zusatzcache allein
  erhält nicht nachträglich einen zeitlich passenden nativen Beleg.
- Neue Modell-/Merkmalsversionen benutzen den bestehenden D1-/D2-Ablauf:
  gekoppelte Likelihood, feste fünf Regularisierungswerte, Auswahl nur auf
  Abstimmungsdaten, endgültige Testspiele außerhalb des Trainings. Alte
  unabhängige Poisson-Fälle bleiben bei ihrem bisherigen Modellvertrag.
- Marktvergleich und Verteilungsverlust verwenden dieselbe gemeinsame
  Torverteilung. Das vorhandene 25+-Restfach wird als solches bewertet,
  nicht als exaktes Ergebnis 25. Ohne Effekt bleiben alle Torwetten exakt
  identisch; Ecken/Karten werden nicht durch einen Toreffekt verändert.
- Kader-, Stadtwetter- und Terminabstandsmerkmale haben getrennte Gruppen.
  Terminabstände beschreiben nur den beobachteten ursprünglichen Spielpool;
  sie behaupten weder eine vollständige Belastungshistorie noch tatsächliche
  Matchdauer oder Erholung. Fehlende Wetter-/Kaderdaten bleiben fehlend.
- Der vorhandene CPU-Transport berechnet den neuen Vergleich. Ein ungeprüfter
  Effekt bleibt ein Vergleich und ersetzt nicht die benutzte Originalprognose.
  Der neue Pfad ist noch nicht in den regulären Scanner zur Veröffentlichung
  neuer Vergleichs-Snapshots samt vollständigem D4-Quellen-Replay eingebaut.

### Tatsächliche Produktionsprobe

Zwei der drei bisherigen vollständigen Fußballbindungen wurden ohne
Provideranfrage oder Öffnen ihrer Zielergebnisse im Speicher geprüft:

| Native Spiel-ID | Vorhandene Quellrevisionen | Kader | Stadtwetter | Terminabstände |
| --- | ---: | --- | --- | --- |
| 1550978 | 36.111 | 12 fehlend | 6 fehlend | 3 verfügbar |
| 1550979 | 36.105 | 12 fehlend | 6 fehlend | 3 verfügbar |

Die dritte Prüfung wurde von der SQL-Zeitbegrenzung unterbrochen. Die äußere
Leserfunktion meldete dafür generisch `ContextIntegrityError`; die tatsächliche
Ursache war `sqlite3.OperationalError: interrupted`, kein nachgewiesener
Datenbankdefekt. Der SQL-Abbruch begrenzt keine laufende Python-Berechnung;
die Probe dauerte deshalb länger als die eingestellten 180 Sekunden.
Rund 750 MB Spitzen-RSS wurden beim Prüfprozess beobachtet. Dieser vollständige
Offline-Quellenlauf gehört deshalb nicht in den Seitenaufruf oder ungeprüft in
jede Live-Berechnung. Keine neuen Hintergrundjobs oder Speicherbudgets angelegt.

### Lokale Verifikation und verbleibende Abnahme

- Erste Kontext-/Datensatz-/Tennis-/Wetterregression: **589 bestanden**.
- Weitere Modellvertrags-/Transport-/Trainingsregression: **278 bestanden**,
  einschließlich des neuen Ende-zu-Ende-Tests mit sechs ausdrücklich
  synthetischen Quellfällen. Zwei Trainingsspiele, ein Abstimmungsspiel und
  drei getrennte Testspiele führen erwartungsgemäß zu **keiner** Freigabe.
- Ein zusätzlicher Quellen-Gegentest war vor der Korrektur rot: Vertauschte
  Verbrauchslisten konnten trotz unveränderter Gesamtquellenmenge passieren.
  Nach der spielweisen Bindungsprüfung besteht dieser Test.
- Abschließender Lauf des neuen Quell-/Trainingspfads nach den letzten
  Quellen-/xG-Korrekturen: **15 bestanden**; zusätzlich **117 Modellvertragstests**
  nach der Importbegrenzung bestanden. Die Läufe überschneiden sich; ihre
  Testzahlen sind keine Anzahl verschiedener Tests. Keine vollständige
  Repository-Suite oder verbesserte Wettqualität daraus ableiten.
- Veröffentlichung erfolgt separat per Code-only-Deploy ohne neue Sicherung,
  Migration oder Sportabfrage; Commitabgleich und Healthchecks müssen den
  tatsächlich übernommenen Stand bestätigen.

Offen bleiben die vollständige produktive Integration, ausreichend tatsächlich
verfügbare Kader-/Wetter-/Belastungsfälle, eine zeitlich getrennte empirische
Auswertung und die Tennis-/weiteren Sportpfade. Die zwei geprüften Fälle
reichen dafür nicht. Weder zusätzliche Datenabrufe noch Fantasie-Koeffizienten
wurden verwendet, um diese Lücke zu überdecken.
