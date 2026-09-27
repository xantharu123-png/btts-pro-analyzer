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
