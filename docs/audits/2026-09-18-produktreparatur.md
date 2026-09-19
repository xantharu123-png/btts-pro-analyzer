# Produktreparatur nach dem Auswahl-Audit

Ausgangsstand: c64218bdf6bb81dfa1a107e2da13de2a35178935. Nutzerauftrag: alle bestätigten Reparaturen umsetzen, anschließend committen und pushen. Bestehender isolierter Worktree bleibt erhalten. Keine neue Serverbereinigung und kein automatisches Deployment durch Timer.

## Status während der Umsetzung

**Veröffentlichung bestätigt am19.09.:** Alle unten genannten Reparaturcommits sind Bestandteil von `2cd0a982a96331996955779a8dfff0466ecfb2fd`, per Fast-forward auf main übernommen und regulär auf GitHub-main gepusht; Remote-Hash danach geprüft. Nachfolgende Commits ergänzen nur Abschlussdokumentation. Keine VPS-Auslieferung dieser Runde. Noch offene fachliche Abnahmen bleiben ausdrücklich offen.

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

Die Browserprüfung deckte zusätzlich eine Rundungskante auf: ein tatsächlicher synthetischer Modellwert 0.9999999876421013 wurde als 100.0 % dargestellt. a322430 zeigt stattdessen >99.9 % (und sehr kleine positive Werte <0.1 %) in Karte, Erklärung und Daily3; tatsächliche Modellwerte, Sortierung und Preise bleiben unverändert. Vier Formatter-RED-Fehler und ein echter Daily3-Renderer-RED-Fall reproduziert, anschließend 160 betroffene Tests bestanden. Exakte mathematische Werte 0/1 bleiben als solche darstellbar. Im unabhängigen Gesamt-Diffreview ohne Befund geprüft.

## Dokumentierte technische Entscheidungen

- Finanz-Lesevorprüfung und Sportbrücke liefen parallel bei getrenntem Dateibesitz; Integritäts-/Writer-Regeln durften nicht gelockert werden. Beide Aufgaben wurden unabhängig geprüft.
- Ein ungültiger Dauerbeleg wird nicht durch eine andere gültige Beobachtung stillschweigend geheilt. Die vier Dauerzustände bleiben sichtbar; daraus wird weder eine Endzeit noch ein aktiver Müdigkeitseffekt erfunden.
- Zusätzliche Fußball-Originalpublikation wird nur mit ausdrücklichen endlichen Budgets angeboten und bleibt standardmäßig aus, bis echte Tageszuwachs-/Retention-/Kapazitätsprüfung abgeschlossen ist. Ein begrenzter Einzelaufruf ist keine Betriebsfreigabe für wiederholte Läufe.
- Der neue Ausführungsfingerabdruck ist ein geschlossen versionierter Beleg der erfassten Quellen-/Laufzeitidentität, kein replay-fähiges vollständiges C1-Codepaket und keine Effektqualifikation. Alte Raw-Law-Replay-Verbraucher müssen diesen neuen Typ ablehnen. Ein künftiger qualifizierter Replaypfad braucht seinen eigenen überprüften Vertrag.
- Die konkrete Entscheidungsbindung bleibt vorerst vollständig und ihr gemessener Platzbedarf wird in die Grenzen eingerechnet. Keine zusätzliche Deduplizierungsarchitektur nur wegen rund68KiB wiederholter Bindungsmetadaten; die standardmäßig ausgeschaltete Betriebsprüfung entscheidet über den echten Tagesbedarf.

## Abschlussschritte

**Review abgeschlossen:** Die unabhängige Nachprüfung `bc9e89f..202a965` hat den Modellidentitätsbefund und den administrativen Minor geschlossen; keine neuen Befunde im Fix.

- `a927370` bewahrt die tatsächliche Modellidentität in Erzeuger, beiden Lesern und Karte. Fehlende historische Identität bleibt unbekannt, widersprüchliche Aliase werden abgelehnt. Vier RED-Fälle, 337 Tests plus26 Untertests bestanden. Kein dadurch falscher aktueller Tipp war reproduziert; behoben ist eine fehlende Schnittstelleninvariante.
- `202a965` schließt die administrative Statusinkonsistenz: fünf RED-Kombinationen, 190 betroffene Tests bestanden. Vollständig deduplizierte Publikationen dürfen weiterhin0Bytes kosten; ausgeschöpftes Publikationsbudget darf mit vollständig belegten Quellen zusammenfallen.
- `f6f62a5` implementiert den standardmäßig ausgeschalteten Fußball-Live-/Originalanschluss. Tasklauf590bestanden/4Skips/32Untertests, unabhängig SPEC/QUALITY approved. Konkrete Wiederholung im380-Zeilen-SQLite-Test68108Nutzbytes einschließlichBindung; kein täglicher Betriebsstandard daraus abgeleitet. Aktivierung und Empirie bleiben offen.
- Desktop-/Mobilansicht mit echten Renderern und klar synthetischen Daten geprüft; siehe `2026-09-18-product-ui-check.md`. Keine gesamte Produktions-/Echtgeldabnahme daraus ableiten.

**Gesamtregression:** Erster Lauf auf `f6f62a5` bei26% zugunsten der Modellidentitäts-Fixrunde kontrolliert beendet, kein Ergebnis daraus ableiten. Zweiter Lauf auf `202a965` vollständig beendet: 10280 bestanden, 7 fehlgeschlagene Tests, 16 Setupfehler, 96 Skips, 111 Untertests; 1527.92s. Quellen während beider laufender Tests unverändert.

Die sieben fehlgeschlagenen Tests kamen aus zwei nicht an den neuen zwingenden Modellvertrag angepassten Test-Fixtures: `projection_success` fehlte im erfolgreichen Mock, aktuelle `prediction_version` fehlte in einem als aktuell bezeichneten statistischen Prüffall. `d0759b1` ergänzt nur diese Testdaten und fügt explizite negative Versionstests hinzu. Produktionscode, Schwellen, historische Pins und Freigabeprüfungen bleiben unverändert. Unabhängiger Review PASS; alle betroffenen Testdateien plus Kalibrierungsregression:122bestanden.

Die16 E-Sport-Setupfehler waren ausschließlich Git-Ownership-Prüfungen beim Lesen des echten historischen Parent-Commits. Derselbe historische Test läuft mit nur prozesslokaler `safe.directory` für genau diesen Worktree vollständig durch (56bestanden); keine globale Git-Konfiguration, keine Ersatz-Originale.

Finaler Gesamtlauf auf unverändertem Quell-/Teststand `d0759b14aabb5ed3530b83507e251e68bbdd091e` abgeschlossen: **10303 bestanden, 96 Skips, 111 Untertests bestanden, Exit0, 1545.58s**. Neun `record_property`-Hinweise betreffen nur das JUnit-xunit2-Berichtsformat, keine fehlgeschlagenen Tests oder DeprecationWarnings. Belege im Worktree `output/playwright/product-full-suite-20260919-d0759b1.{log,xml}`, isolierterPfad `C:/Projekt/BetBoy/.qa-product-final-20260919-d0759b1`. Die96 Skips betreffen Windows-/Linux-/Symlink- beziehungsweise separate native QA-Voraussetzungen und ersetzen keinen echten Linux-Nachweis.

Danach Hauptcheckout per Fast-forward auf `2cd0a98` aktualisiert: **625 Tests plus79 Untertests bestanden, Exit0,90.16s**, Log im Hauptcheckout `output/playwright/product-main-checkout-20260919-2cd0a98.log`. Getestet: Auswahl/Analyse/Oberfläche/Daily3, Artefaktleser/Teamsport, Modell-/Signifikanz-/Joint-Law-Verträge, Originalpublikation, Finanzintegrität, Tennis-Dauer/Replays/Training und echte historische E-Sport-Parität. Regulärer Push von main erfolgreich, GitHub-Hash per `ls-remote` gleich `2cd0a982a96331996955779a8dfff0466ecfb2fd`. Keine Quell-/Teständerung seit dem Volltest; nur Abschlussdokumentation. Fremde/ungetrackte Dateien und vorhandener Worktree erhalten. VPS-Deployment separat, keine Serverbereinigung oder Produktionsänderung.
