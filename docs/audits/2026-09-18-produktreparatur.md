# Produktreparatur nach dem Auswahl-Audit

Ausgangsstand: c64218bdf6bb81dfa1a107e2da13de2a35178935. Nutzerauftrag: alle bestätigten Reparaturen umsetzen, anschließend committen und pushen. Bestehender isolierter Worktree bleibt erhalten. Keine neue Serverbereinigung und kein automatisches Deployment durch Timer.

## Status während der Umsetzung

| Audit | Reparatur | Stand |
| --- | --- | --- |
| F7/F9 | Daily3-Preiswarnung, keine behauptete tatsächliche Erholung aus Ergebnisempfang | f844f05 lokal committed; 4 erwartete RED-Fehler, anschließend 4 neue und 75 Verbraucher-Tests bestanden; unabhängiges Spec-/Code-Review bestanden. |
| F1/F2/F4/F5 | gemeinsame Auswahlrichtung, belegte Hervorhebung, echte Modell-/Datenfrische, sportgerechte Erklärung | c953d46 und 9467148; 455 fokussierte Tests bestanden, unabhängiges Nachreview SPEC/QUALITY PASS. Keine pauschale Markt-Hervorhebungssperre; Ergebnisrichtung und Darstellung getrennt. |
| F3 | gemeinsame kalibrierte Verteilung und versionsgleiche historische Prüfung | f42e264 lokal committed; 709 betroffene Tests und 97 Untertests bestanden, unabhängiges SPEC/QUALITY PASS. Neue Rechenregel benötigt eigene historische Qualifikation. |
| F6 | vollständige bestehende Basketball-/Eishockey-Prognose gemeinsam konsumieren | fdd04bf plus 423e888; 468 betroffene Tests plus 26 Untertests, Fixrunde 275 plus 26 Untertests. Unabhängiges Nachreview schließt den Befund nachträglich veränderbarer ModelSignal-Belege. Bestehende Berechnung einmal nutzen, ursprüngliche Zeiten bewahren, keine erfundenen Sicherheitswerte oder Freigaben. |
| F8 Teil | echte TennisAbstract-Dauer nicht mehr verwerfen | 534d27d plus2d92eb9 lokal committed; 360 betroffene Tests bestanden, 3 Skips; zusätzlich92 Modell-/Tour-Tests. Unabhängiges Nachreview schließt alle3 Befunde. Dauer ist weder tatsächliche Endzeit noch aktivierter Müdigkeitseffekt. |
| F8 Gesamt | numerisch angewendete, empirisch bestätigte Verletzungs-/Müdigkeitswirkung | nicht abgeschlossen; separate Daten-, Integrations- und Qualifikationsschritte erforderlich. |

Plan-/Taskbelege liegen in `docs/superpowers/plans/2026-09-18-{price-recovery-truth,shared-forecast-selection,coherent-market-calibration,team-sport-forecast-bridge,tennis-duration-preservation}.md` und den jeweiligen lokalen SDD-Ledgern. Die früheren vollständigen Testergebnisse für c64218b sind keine Belege für diesen neuen Gesamtstand.

## Nicht durch Softwaretests ersetzbare Abnahme

Die bisherige Fußball-Kontextwirkung arbeitet mit dem ausdrücklich rohen Poisson-Ratenvertrag `football-goals-raw-reference-v1`. Ein neues gemeinsam kalibriertes Modell darf nicht unter diesem alten Vertrag eingeschleust oder mit dessen bisheriger Freigabe versehen werden. Notwendig bleiben ein versionsgleicher kausaler ORIGINAL/B1-Anschluss, Wirkungsadapter, Scorer und geeignete reale Trainings-/Testkohorten.

Eine neu gespeicherte heutige Beobachtung wird nicht zu einem früher verfügbaren Beleg. Matchdauer ist keine gemessene Endzeit; Ergebnisempfang ist keine vollständige Erholungshistorie. Mindestens 200 unabhängige unbenutzte Testevents in drei Zeitblöcken sowie die freigegebenen Brier-/HAC-/FDR-/Logloss-Regeln bleiben unverändert. Keine vermeintlich besseren Tipps durch erfundene Zahlen oder gelockerte Prüfungen.

Die neue gemeinsame Verteilung benötigt im begrenzten synthetischen 1.200-Spiel-Test 46,63 statt 30,51 Sekunden für die historische Prüfung. Das ist kein gemessener VPS-Gesamtlauf. Die Prüfung berechnet nur die tatsächlich ausgewertete aktive Variante; normale Prognosen behalten sämtliche Varianten. Kalter Produktionsdurchlauf und neue Modellqualifikation bleiben getrennte Betriebsabnahmen.

Ein sporadischer Fehler beim parallelen Anlegen zweier15K-Tickets wurde deterministisch reproduziert: mehrere Leseabfragen konnten gültige unterschiedliche Datenbankstände vermischen. Reparatur5ff08a9 hält die zusammengehörenden Leseprüfungen in einem Snapshot; 217 betroffene Tests plus85 Untertests bestanden, unabhängiges SPEC/QUALITY-Review ohne blockierenden Befund. Geld-, HMAC-, Einsatz- und Writer-Regeln bleiben unverändert.

Die Browserprüfung deckte zusätzlich eine Rundungskante auf: ein tatsächlicher synthetischer Modellwert 0.9999999876421013 wurde als 100.0 % dargestellt. a322430 zeigt stattdessen >99.9 % (und sehr kleine positive Werte <0.1 %) in Karte, Erklärung und Daily3; tatsächliche Modellwerte, Sortierung und Preise bleiben unverändert. Vier Formatter-RED-Fehler und ein echter Daily3-Renderer-RED-Fall reproduziert, anschließend 160 betroffene Tests bestanden. Exakte mathematische Werte 0/1 bleiben als solche darstellbar. Unabhängige Abschlussprüfung steht noch aus.

## Dokumentierte technische Entscheidungen

- Finanz-Lesevorprüfung und Sportbrücke liefen parallel bei getrenntem Dateibesitz; Integritäts-/Writer-Regeln durften nicht gelockert werden. Beide Aufgaben wurden unabhängig geprüft.
- Ein ungültiger Dauerbeleg wird nicht durch eine andere gültige Beobachtung stillschweigend geheilt. Die vier Dauerzustände bleiben sichtbar; daraus wird weder eine Endzeit noch ein aktiver Müdigkeitseffekt erfunden.
- Zusätzliche Fußball-Originalpublikation wird nur mit ausdrücklichen endlichen Budgets angeboten und bleibt standardmäßig aus, bis echte Tageszuwachs-/Retention-/Kapazitätsprüfung abgeschlossen ist. Ein begrenzter Einzelaufruf ist keine Betriebsfreigabe für wiederholte Läufe.
- Der neue Ausführungsfingerabdruck ist ein geschlossen versionierter Beleg der erfassten Quellen-/Laufzeitidentität, kein replay-fähiges vollständiges C1-Codepaket und keine Effektqualifikation. Alte Raw-Law-Replay-Verbraucher müssen diesen neuen Typ ablehnen. Ein künftiger qualifizierter Replaypfad braucht seinen eigenen überprüften Vertrag.
- Die konkrete Entscheidungsbindung bleibt vorerst vollständig und ihr gemessener Platzbedarf wird in die Grenzen eingerechnet. Keine zusätzliche Deduplizierungsarchitektur nur wegen rund68KiB wiederholter Bindungsmetadaten; die standardmäßig ausgeschaltete Betriebsprüfung entscheidet über den echten Tagesbedarf.

## Abschlussschritte

Finale Quellbasis `f6f62a5f0bc3282a9290ee9585398ff3f2e7aa3d` ist eingefroren. Seit19.09., ca.00:40CEST läuft die vollständige Regression in Sitzung67284: `pytest tests -q --tb=short --durations=15 -W error::DeprecationWarning -p no:cacheprovider`, isolierterPfad `C:/Projekt/BetBoy/.qa-product-final-20260919-f6f62a5`; Log/JUnit `output/playwright/product-full-suite-20260919-f6f62a5.{log,xml}`. Noch kein Ergebnis behaupten und währenddessen keine Quellen/Tests ändern.

`f6f62a5` implementiert den ausgeschalteten Fußball-Live-/Originalanschluss. Betroffener Tasklauf590bestanden/4Skips/32Untertests; unabhängiger Taskreview läuft. Konkrete Wiederholung im380-Zeilen-SQLite-Test68108Nutzbytes einschließlichBindung; kein Betriebsstandard daraus abgeleitet.

- Aufgaben jeweils mit RED/GREEN, unabhängigem Review und fokussiertem Commit abschließen.
- Eine breite Suite auf eingefrorenem finalem Quellstand; unabhängiges Gesamt-Diffreview.
- Tatsächliche Desktop-/Mobilansicht mit klar bezeichneten lokalen Prüfdaten prüfen.
- Nur eigene Quellen, Tests, Pläne und Übergabedokumente integrieren; fremde/ungetrackte Ausgabe- und QA-Dateien erhalten.
- GitHub-main frisch prüfen, lokales main nur fast-forwarden und regulär pushen. Commit, Push und VPS-Deployment getrennt berichten.
