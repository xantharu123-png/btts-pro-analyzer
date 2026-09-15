# Tennis: echte Originalprognosen mit dem Kontexttraining verbunden

## Problem und Abgrenzung

Der Live-Pfad speichert `tennis-live-calibrated-winner-v1`, während D1 bisher
sämtliche Tennisfälle wegen einer fehlenden historischen Native-ID/Modellnamen-
Zuordnung ablehnte. Diese fehlende Zuordnung bleibt tatsächlich ungeklärt.
Sie ist aber keine Voraussetzung, um den Fehler der **damals wirklich von der
App berechneten und gespeicherten Prognose** gegen später beobachtete Ergebnisse
zu messen. Das ist ein anderer, ausdrücklich versionierter Vergleich.

Der neue Typ `tennis-live-winner-status-load-antisymmetric-v1` verwendet diese
Originale als Offset. Er behauptet weder einen nativen historischen Modellbau
noch eine bessere Grundprognose. Der alte historische Replay-Pfad bleibt
unverändert gesperrt, solange seine Quellenzuordnung fehlt.

## Unveränderte Produkt- und Qualitätsregeln

- ATP und WTA bleiben getrennte Populationen.
- Native Oberfläche und Halle bleiben bei diesem Originaltyp ausdrücklich
  unbekannt (`null`). Das ist ein eigener Datenumfang, kein Platzhalter für
  beliebige bekannte Beläge. Katalogannahmen werden nicht zu Quellenfakten.
- Beobachtete Erholungs-Untergrenzen bleiben Untergrenzen. Eine Empfangszeit
  wird weder zur tatsächlichen Endzeit noch zu einer Matchdauer umgedeutet.
- Fehlende Sätze, Minuten und Ausfälle werden nicht auf null gesetzt.
- Quoten sind keine Trainingsmerkmale, Sortierkriterien oder Modellsperren.
- Es gibt keine manuell erfundenen Verletzungs-/Müdigkeitsabschläge.
- Keine automatische Aktivierung: unverändert mindestens 200 unabhängige
  Testevents in drei Zeitblöcken, Brier-/Verteilungs-/Kalibrierungsprüfung und
  die bestehende Mehrfachtestkorrektur. Softwaretests sind kein Qualitätsbeleg.
- Cricket, finanzielle Konten, Einsatzregeln und UI bleiben unverändert.

## Technischer Weg

`build_live_training_case` liest vorhandene Originale, ihren tatsächlich
verwendeten Tour-Modellstand, native Status-/Belastungsbelege und genau ein
späteres normales Endergebnis. Die Funktion schreibt keine Datenbank,
lädt keine neuen Quelldaten und veröffentlicht keine Koeffizienten.

Die Originalwahrscheinlichkeit wird mit exakt unterstützten Code-Hashes und
dem alten Modellstand nochmals berechnet. Speicherung nach Spielbeginn,
ein erst später verfügbarer Modellstand, widersprüchliche Teilnehmer oder
abgeänderte Wahrscheinlichkeiten werden abgelehnt.

Der Trainingsdatensatz enthält alle damaligen Revisionen jedes Spiels, das
einem der beiden Spieler zugeordnet war, einschließlich späterer Korrekturen,
die einen Spieler wieder entfernen. Unbeteiligte Tour-Ereignisse werden nicht
tausendfach kopiert. Die Regression vergleicht diese Auswahl mit der vollständigen
v3-Belastungsberechnung. Der Datenbankresolver prüft die Vollständigkeit nochmals.

D1, Datensatzresolver, D2-Evaluation, Transportprüfung und Live-Effektauswahl
erkennen den neuen Modelltyp. Alte Modelltypen bleiben eigenständig. Ein
trainierter, aber nicht empirisch freigegebener Effekt ersetzt die angezeigte
Originalprognose nicht.

## Noch nicht erledigt

Am 15.09.2026 um 21:40 UTC lagen im Live-Kontextspeicher 410 Originalartefakte,
aber noch keine nativen Tennis-Endergebnisbelege dieses neuen Erfassungspfads.
Das ist eine Bestandsaufnahme, keine Qualitätsmessung. Der letzte vollständige
Tennisdienst war morgens fehlgeschlagen. Ein erfolgreicher neuer Tageslauf und
genügend zeitlich getrennte Ergebnisdaten bleiben erforderlich.

Die vollständigen Fußball-Verletzungsmodelle, Tennis-Satz-/Minutenbelastung und
weitere Sportarten sind mit dieser Anbindung ausdrücklich nicht abgeschlossen.
Insbesondere liefert der aktuelle ESPN-Kontext keine tatsächlichen Endzeiten
oder Matchminuten; daraus wird keine angeblich gemessene Fünfsatz-Müdigkeit.
