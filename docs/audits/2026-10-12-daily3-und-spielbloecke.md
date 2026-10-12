# 12.10.2026 – Daily3 und geöffnete Spielblöcke

## Auftrag und belegte Ursachen

Der Nutzerauftrag „alles beheben“ bezieht sich in dieser Fortsetzung auf die
uneinheitlich geöffneten Spielblöcke und leere Daily3-Anzeige trotz vorhandenem
Scan. Die unfertigen, bereits lokalen Kontextmodell-Arbeiten vom 11.10. bleiben
unverändert und ausdrücklich nicht Bestandteil dieses Releases.

Nur lesend verifiziert: Wettfinder 12.10. 03:35–04:11, Tennis 00:05–00:31,
beide Exit 0. VPS vor Release `e9eea811b85b124b797c0d995b6cdbbe8187c6b5`;
lokal/GitHub Dokumentationsstand `b5f1285d2afbf1664806427f3fbcf8bf82a875f3`.
Um 12:57 Zürich enthielt der gespeicherte Pool noch 100 Fußball-, eine
Tennis-, zwei E-Sport- und zwei Hockeyprognosen, Daily3 jedoch null Auswahlen.
Das reine Lesen ließ den SHA-256 des bestehenden Laufdokuments unverändert.
15K und RisikoBet waren bei der vorherigen Liveprüfung befüllt; eine leere
Daily3-Teilmenge bedeutet nicht, dass der Gesamtpool leer oder der Scan defekt ist.

Die Öffnung war von TOP-Mitgliedschaft abhängig, obwohl die sichtbare Liste
chronologisch sortiert war. Daily3 verlangte außerdem mindestens +2 Prozentpunkte
Form-/Belagänderung trotz defensiver Modellvarianten, verwendete für tägliche
Fußballbeobachtungen die 75-Minuten-TOP-Frist und reservierte Zeit für alle noch
unbekannten Restwetten. Die Auswahl des spätesten höchsten Modells konnte dann
frühere qualifizierte Spiele verdrängen.

## Begrenzte Korrektur

- Die ersten drei sichtbaren Spielblöcke jeder geordneten Seite öffnen initial;
  der Rest bleibt geschlossen. Explizite Nutzerwahl hängt weiterhin an der
  Partie, über Sortierung, Filter und Seitenwechsel hinweg. Ein zusätzlich
  reproduzierter Streamlit-Remount benötigte Wiederherstellung vor Registrierung.
- Daily3 behält exakt gebundene, historisch qualifizierte Fußball-/ATP-Vergleiche
  und mindestens 70 % in sämtlichen drei realen Varianten. Nur der pauschale
  positive 2pp-Bonus entfällt. Die normale TOP-Vergleichsregel bleibt unverändert.
- Automatische tägliche Fußballbeobachtungen dürfen bis 24 Stunden alt sein,
  unter ihren wirklichen Originalzeiten. Manuelle Modelle behalten ihre bisherigen
  Fristen. Fehlende, ungültige, zukünftige, explizit veraltete oder widersprüchliche
  Informationen und echte Vetos werden nicht als gültige Beobachtung umgedeutet.
- Die früheste qualifizierte Partie beginnt die tatsächliche Tagesfolge. Bei
  gleichem Beginn priorisiert Daily3 den defensiven Variantenboden. Der Zeitpuffer
  gilt pro echter Partie (3h Fußball/Basketball/Hockey, 4h Tennis/E-Sport), ohne
  zusätzliche Phantomzeit für unbekannte spätere Wetten.
- Preisprüfversuch und exakt bekannte Untergrenze 1,20 bleiben bestehen. Preise,
  heuristische Abschläge, Gewinnziel und Kontogeld verändern keine Wahrscheinlichkeit.
- Leermeldung nennt nicht mehr für jeden Ablehnungsgrund fälschlich ein Zeitproblem.
  Negative Form-/Belagänderungen werden mit tatsächlichem Vorzeichen angezeigt.
- CHF-50-Budget, Erfassung, Identitäts-/Dublettenschutz, erneute Prüfung vor
  Vormerkung und tatsächliche Abrechnung bleiben unverändert.

## Tatsächliche QA

Die folgenden Runden überschneiden sich; nicht als Gesamtzahl addieren.

- TDD RED: Root-Auswahlregression 7 fehlgeschlagen/5 bestanden; neutraler
  UI-Leerzustand 1 fehlgeschlagen/2 bestanden. Phantomzeit-Owner 18/8 RED;
  Accordion-Owner 5/17 sowie separat Nutzerwahl-Remount 1/1 RED.
- Root-Integration zehn betroffene/benachbarte Dateien: **325 bestanden**, 20,30s,
  `C:/Projekt/BetBoy/output/daily3-accordion-20261012/focused.xml`.
- Unabhängiger sauberer Reviewer: **407 bestanden**, keine neuen Findings in
  Produktivcode, exakte Preisgrenze und Geldregeln geprüft. Browser-/VPS-Abnahme
  sind davon getrennt, nicht durch diese Tests bewiesen.
- Quellenbindung/TOP-/Preisnachbarn: **89 bestanden**, 9,30s; danach isolierte
  Kontextgrenzen einschließlich frischem Modell bei originalem Kontext genau
  24h bzw. 24h+1s: **51 bestanden**, 8,61s.
- Portal mit eigenem dokumentierten Django-Harness: **47 bestanden**, 12,32s.
- Unbegrenzter `pytest`-Projektaufruf in Hauptvenv konnte wegen dort fehlendem
  Django nicht sammeln; Portal wurde deshalb über seinen eigenen Harness geprüft.
- Sandbox-Kernversuch durch Windows-TEMP-Schreibrechte gestört und abgebrochen.
  Die Wiederholung mit kanonischer QA-Umgebung und externem Netzwerkblocker
  wurde bei rund23% begrenzt beendet (Exit1 nach Abbruch, kein fertiger
  Gesamtbericht). Keine Behauptung einer vollständig grünen Projekt-Vollsuite.
  Im bis hier ausgewerteten breiten Lauf: vorbestehender AST-Freeze-Test
  `test_basketball_context.py::test_frozen_default_cricket_matches_before_change_on_same_cpu`
  scheitert an bereits committedem Hockey-Season-Zweig `_variant`; alle fünf
  numerischen Cricket-Replays in diesem Test sind bitgleich. Beide Quellen
  unverändert, keine Cricket-Reparatur Bestandteil dieses Auftrags.
  Zwölf alte Daily3-75min-Erwartungen wurden anschließend unter Erhaltung
  normaler TOP-Regeln aktualisiert und mit zusätzlicher 24h-Grenze geprüft.
- Releaseproof aus Git-Archiv **genau des committeden Produktivpatches**, ohne
  fremde dirty/untracked Kontextmodell-Dateien: **500 bestanden**, 21,18s,
  Python3.12.14/SQLite3.53.1 aus `.codex_test_venv`, 15 Release-/Nachbardateien,
  externe Netzwerkzugriffe gesperrt. JUnit:
  `C:/Projekt/BetBoy/output/daily3-accordion-20261012/release-clean.xml`.
  Dies ist ein begrenzter Releaseproof, kein Ersatz für die gesamte App-Vollsuite.

## Release und Grenzen

Produktivpatch `3dea2d327cc47bf0418a607fede229e38221d82c` committed und nach
GitHub-main gepusht. VPS kontrolliert von `e9eea811...` per Fast-forward auf
diesen Commit aktualisiert, zwischen zwei regulären Timern ohne aktiven Worker.
App neu gestartet; lokale und öffentliche Healthchecks **ok**, App/Caddy aktiv.
Alle sieben regulären Timer weiterhin geplant; keine Timeränderung vorgenommen.

Der erste SSH-Wrapper endete nach bereits abgeschlossener Release- und
Hashprüfung mit Exit1 durch eine zusätzliche CR-Zeile aus der lokalen Pipe
(`DEPLOY_FAILURE_STAGE=completed`). Die begrenzte Wiederanlaufprüfung meldete
eine gesunde App. Die eigene Hilfsdatei/Pipe wurde korrigiert. Ein anschließender
unabhängiger, rein lesender SSH-Aufruf endete mit Exit0 und bestätigte Commit,
beide Healthchecks und Dienststatus. Keine Wiederholung des App-Deploys nötig.

Produktionsbeleg am12.10. um13:06 Zürich: dieselbe gespeicherte Laufdatei
ergibt statt null jetzt **eine** Daily3-Auswahl, IF Elfsborg–Halmstad,
19:00 Zürich, `HOME_UNDER_2_5`, Modell0,782623, niedrigste reale Variante0,772995,
Formänderung+0,009628. Der Originalkontext bleibt
`2026-10-12T01:41:38.701616+00:00`, der Preisprüfzeitpunkt
`2026-10-12T02:04:28.636198+00:00`; keine Uhr wurde angehoben.
Unveränderte SHA-256 vor/nach Deployment und Poolauswertung:

- Wettfinder: `fe6650e61c3ff2da718ec1c75264d93ff5356c0df9c6a93e7c408586008140ec`
- RisikoBet: `afab383e3988d1a4a8ad2d0d83bd08911677c452a63c6b7f5921b6291483f4b1`

Interner Browser, eigener Hintergrundtab, echte Live-Seite nach Reload:
initial Vacherot/Paul, Arges/Cluj und VPS/Gnistan offen, folgende Spiele
geschlossen. Vacherot/Paul explizit geschlossen; nach Sortierung auf
Wahrscheinlichkeit und zurück auf Startzeit sowie Navigation zu Daily3 und
zurück weiterhin geschlossen, andere Partien korrekt gemerkt.
Daily3 zeigt eine defensive Auswahl, Modell78,3%, letzte passende Pinnacle-
Quote1,64 mit originalem Preisstand. Kein Tagesbudget bestätigt, keine Wette
erfasst, keine Buchung verändert. Seit Abschluss des Neustarts keine neuen
Consolefehler; vorherige Disconnect/502-Einträge gehören zum App-Neustart.
Desktop-Abnahmen unter normalem1280x720-Viewport; keine neue mobile visuelle
Abnahme dieser Runde behauptet. Screenshots:

- `C:/Projekt/BetBoy/output/daily3-accordion-20261012/live-daily3.jpg`
- `C:/Projekt/BetBoy/output/daily3-accordion-20261012/live-wettfinder.jpg`

Kein neues Backup, keine Bereinigung, kein zusätzlicher Sport-/API-Scan und keine
Neuberechnung oder Umschreibung bestehender Prognosen/Geldbuchungen.

Keine erfundenen qualifizierten Basketball-/Hockey-/E-Sport-Vergleiche zum
Auffüllen von drei Plätzen. Die verbleibenden Kontextmodell-Arbeiten und fehlender
Nachweis besserer Wettqualität bleiben im vorherigen TODO-Block offen.
