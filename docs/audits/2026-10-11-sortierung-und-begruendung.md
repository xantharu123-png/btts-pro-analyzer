# BetBoy: Sortierung, Modellbegründung und kausale Ergebniszuordnung

Stand: 11.10.2026, Abschluss nach 10 Uhr Europe/Zurich.
Codecommit `5467b888b38fe0ed3b350471511d8bf2245351cc`, Ausgang
`8052ff916add24b27f5e517513b610490b5dae62`. Kein zusätzlicher Sport-/API-Scan,
Backup, Datenbankarchiv oder Eingriff in alte Prognosen/Geldbuchungen.

## Umgesetzt

1. Ein reiner Anzeigeordner verwendet tatsächliche, zeitzonengebundene
   Startzeiten und ursprüngliche Ereignisidentitäten. Nächste Spiele zuerst;
   alternativ größte sichtbare Modellchance pro Spiel. Prozentwerte der
   RecommendationCandidate-Schnittstelle werden ausdrücklich in Brüche
   umgerechnet. Fehlende IDs verbinden nicht versehentlich fremde Spiele.
   Spielblöcke bleiben zusammen; Selektion/Kohärenzprüfung passieren vorher.
   Daily3 behält die zeitliche Roll-over-Folge. Rohe Spielpläne erhalten keine
   erfundene Wahrscheinlichkeitsrangliste.
2. Hockey: Angriffsdifferenz, umgekehrte Conceded-/Defensivdifferenz und
   Spielort summieren sich zum Log-Verhältnis der gefitteten Heim/Gast-Torraten.
   Basketball: Gegnerstärken- und Spielortdifferenz summieren sich zur Marge.
   Alle Komponenten kommen vom gleichen bereits vorhandenen Fit; kein
   zweites Modell und keine künstliche Zwei-/Drei-Argumente-Abstimmung.
   Displayparser prüft Format, endliche Werte und Rekonstruktion der tatsächlich
   gespeicherten gerundeten Raten/Marge. Widersprechende Komponenten bleiben
   Gegenargumente, auch bei Auswärtsauswahl. Alte Originalpredictions und
   Vertragshashes bleiben unverändert; nur neue Adapter-Snapshots erhalten
   den zusätzlichen gebundenen Faktenanhang.
3. Die reale Mehrdeutigkeit Veres Rivne/Kudrivka, Fixture 1565480, entstand
   durch zwei eingefrorene Startzeiten (12.09.15:00 UTC / 03.10.10:00 UTC),
   nicht zwei automatisch gleichwertige Ergebnisse. Geteilter Ergebnisabruf
   verlangt jetzt native Fixture-ID, unveränderte Teams, exakte bekannte
   Terminrevision und passende Ergebnisquelle. Der Runner prüft erneut;
   modeled_at und input_cutoff_at müssen vor dem **echten** nativen Start liegen.
   Eine später erstellte Prognose wird nicht rückwirkend als Gewinn gezählt.
   Der nächste reguläre Ergebnisabruf muss das tatsächliche FT belegen.
4. Zehn offene native Tennis-IDs betreffen andere Endspielteilnehmer:
   ATP 183397/183448/186254; WTA 184266/185222/185272/186216/186284/186285/186374.
   Der neue Collector diagnostiziert ausschließlich den belegten Paar-Konflikt.
   Er erfindet keine rechtzeitig bekannte Ersatzpaarung, schreibt kein Outcome
   für das ursprüngliche Spiel und verändert keine Geldbuchung. Fehlende oder
   widersprüchliche Quellen bleiben echte Fehler. Separate Liste
   identity_conflict_outcome_events; Bericht weiterhin partial. Eine technisch
   erfolgreiche Verarbeitung ist nicht vollständige Ergebnisabdeckung.
5. Eigener SQLite-Deadlineabbruch in der Readiness-Diagnose wird als Timeout
   eingeordnet; eine fremde SQLITE_INTERRUPT-Ursache bleibt Integritätsfehler.
   Der Progress-Handler wird vor Rollback/Reader-Abschluss entfernt.

## Prüfung und Veröffentlichung

- Gemeinsame frische Offline-Runde: **1517 passed, 1 skipped, 36 subtests passed**,
  106,24 s, Exit 0, 34 Module. Keine Testausfilterung oder abgeschwächte Guards.
  Natives Windows mit privatem TEMP, weil Sandbox-TEMP/Hardlink-Beschränkungen
  die unveränderten Dateirechteprüfungen zuvor störten. Externes Netzwerk gesperrt.
- Unabhängige Review-Gegentests fanden Prozent-/Bruch-Verwechslung und
  nach tatsächlichem Anpfiff gebaute Forecasts. Beide zunächst rot reproduziert,
  korrigiert und unabhängig bestätigt. Kein neuer Vollsuite-PASS behauptet.
- Interner Browser: Startzeit → Wahrscheinlichkeit → Startzeit tatsächlich
  umgeschaltet; Testdaten eindeutig gekennzeichnet. 1280/390/320 px ohne
  horizontalen Überlauf, keine Console-Warnungen/-Fehler. Neue Kontrolloption
  auch auf der frischen Produktionsseite sichtbar. Diese Seite zeigt heute
  weiterhin keine neuen automatischen Ergebnisse, kein erfundener Tageserfolg.
- Geprüfter Fast-forward-Deploy ohne Datenmigration/Backup/Sportlauf, Exit 0;
  Neustart kurzzeitig mit zwei erwarteten Health-Retries, anschließend beide
  Healthchecks ok. App/Caddy aktiv, sieben reguläre Timer aktiv. Laufende
  Worker nicht unterbrochen. Gespeicherte Modell-/RisikoBet-Dateien bytegleich:
  `a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e` /
  `acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`.

Lokale Nachweise (absichtlich außerhalb des Git-Repositories):

- `C:/Projekt/BetBoy/output/combined-final-20261011.xml`
- `C:/Projekt/BetBoy/output/display-order-20261011-integrated-final-02.xml`
- `C:/Projekt/BetBoy/output/settlement-identity-20261011-final2.xml`
- `C:/Projekt/BetBoy/output/settlement-identity-20261011-neighbors.xml`
- `C:/Projekt/BetBoy/output/strength-broad2-20261011.xml`
- `C:/Projekt/BetBoy/output/selection-ui-20261011/desktop1280.jpg`
- `C:/Projekt/BetBoy/output/selection-ui-20261011/mobile390.jpg`
- `C:/Projekt/BetBoy/output/selection-ui-20261011/mobile320.jpg`

## Keine falsche Vollständigkeit

Der heutige reguläre Wettfinder hatte weiterhin einen 45-Minuten-Timeout;
Lookupindex und Diagnosephasen sind repariert, ein erfolgreicher kompletter
Tageslauf steht noch aus. Nächste normale Termine: Tennis 12.10.00:05,
Wettfinder 12.10.03:35 CEST. Kein zusätzlicher Scan wurde gestartet.

Football-Shadow regulär weiter Exit 1: frische Bet365-Quote mit Providerzeit
fehlt. Zwei alte Shadow-Zeilen haben ungültige Opening-/Closing-/Settlement-
Provenienz; diese werden nicht als Qualitätsbeleg gezählt oder rückwirkend
schöngerechnet. Keine Empfangszeit anstelle einer echten Providerzeit verwenden.

Heutige rein lesende VPS-Inventur enthält keine context-effect-v1- oder
context-approval-v1-Artefakte. Vorhandener Quell-/Training-/Registrycode ersetzt
keine zeitgebundene Trainings-/Testkohorte. Verletzungs-, Wetter- und Müdigkeits-
Wirkung sowie bessere aktive Wettqualität sind deshalb weiterhin nicht belegt.
Der frühere 72-Spiele-Fußballvergleich bleibt retrospektiv/offline; alte
football-goals-v1-Rezepte dürfen nicht still neue Parameter übernehmen.

Hockey weiter NHL-only. Native IDs, Historie, REG-/OT-/SO-Verträge für Schweiz/
Top20 fehlen; erweiterte NHL-Kontextverträge sind noch 20252026-gebunden.
Keine andere Liga oder Saison ohne echte Quelle aktivieren. Bestehende
Produktionsdatenbank wurde nicht bereinigt oder kopiert; ausreichend freier
VPS-Speicher (21 GB) war vorhanden. Der App-Quellcode ist nicht die Datenbank.
