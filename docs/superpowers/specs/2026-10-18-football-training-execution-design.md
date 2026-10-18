# Fußball: echter Trainingslauf ohne Kopie der Originaldaten

Stand: 18.10.2026, Ausgangscode `e59bda1`.
**Vorschlag zur schriftlichen Freigabe; noch keine Umsetzungsfreigabe.**

Ergänzt den [Speichervertrag](2026-10-18-football-stream-dataset-design.md),
ersetzt ihn nicht stillschweigend. Ziel ist der vollständige Fußballpfad für
Verletzungs-/Kader-, Wetter- und Belastungseffekte, nicht eine weitere UI-Reparatur.
Vorhandene und kostenlose Quellen; kein neues Abo, Backup oder Datenbankexport.

## 1. Verifizierter Ausgangspunkt

- Vier Besitzer halten derzeit wieder vollständige Fälle: Readiness, Dataset,
  Trainingsassembler und Fitter. Der Speichervertrag löst dies durch gemeinsame
  Quellenmitgliedschaft und fallweise physische Projektion.
- Vorbereitung, Experiment und Testöffnung schreiben heute in dieselbe SQLite-
  Datenbank wie die Originale. Der vorhandene CLI sperrt Produktionspfade.
  Eine neue leere Zieldatenbank allein behebt diese gekoppelten Zugriffe nicht.
- Vorbereitungs-Readiness decodiert derzeit auch finale Ergebnis-Körper. Im neuen
  Pfad dürfen diese erst nach dauerhaft reservierter Testöffnung gelesen werden.
- Bisheriges D2 prüft den ganzen Quellspeicher einschließlich verwaister Inhalte.
  Eine Prüfung nur der leeren Zieldatenbank wäre keine gleichwertige Prüfung.
- V1/V2-Erfassung von Kader und Wetter ist bereits angeschlossen. V3 kann
  vorhandene Spielerbelastung nutzen, übernimmt aber nicht die V1/V2-Kaderspalten;
  spätere V3-Entscheidungen sind absichtlich nicht freigegeben.
- Aktuelle reine Metadatenprobe auf dem VPS: 124 Original-Bindungen; keine
  gespeicherten Dataset-, Trainingsfall-, Effekt-, Experiment-, Testöffnungs-
  oder Freigabeartefakte in den geprüften Arten und keine V2-Headerinventare.
  124 Bindungen sind keine nachgewiesenen 124 unabhängigen, vollständigen Fälle.
  Der 25.201.233-Byte-Tagesbericht wurde nicht vollständig geladen.
  Beleg extern: `output/football-training-20261018/metadata-live-02.log`.

## 2. Empfohlener Weg und verworfene Abkürzungen

Empfohlen: bestehende Originale ausschließlich lesend verwenden; neue kleine
Trainingsartefakte in genau einem dauerhaften, getrennten Trainingsregister
speichern. Die bestehenden Validatoren und numerischen Kerne bleiben zuständig.
Kein allgemeines Datenbank-Routingframework, kein neuer Dienst oder Zeitplan.

Nur den Speicherpatch auszurollen wäre kleiner, ließe den echten Lauf jedoch
gesperrt. Eine komplette Datenbankkopie oder das Entfernen der Produktionssperre
würde den Auftrag beziehungsweise den bisherigen Datenvertrag verletzen.

## 3. Besitzer und begrenzte Speicherung

- Quelle: existierende Originale, Beobachtungen, Revisionen und Inventare in
  einem gehaltenen echten read-only SQLite-Snapshot; keine neuen Quellschreibvorgänge.
- Ziel: Identitätsabbildung, Fallheader, kompakte Dataset-Mitgliedschaften,
  Fit-Kandidaten, Experiment, Testöffnungen und Prüfberichte im Trainingsregister.
  Keine Kopie historischer Quellkörper; kein ATTACH, Export oder Memory-Overlay.
- Genau ein konfiguriertes dauerhaftes Register. Ein neuer Dateiname darf keinen
  bereits geöffneten Testbestand wieder als unangetastet erscheinen lassen.
  Vorhandene Testöffnungen der Quelle gehören zur Wiederverwendungsprüfung.
- Explizite getrennte Quellen-/Artefaktleser; ein gleichnamiger Digest im Ziel
  darf niemals ein Original oder dessen Herkunft verdecken.
- Vorhandene Fallgrenzen bleiben: maximal 1.024 explizite Events, Katalog und
  jeweiliger Quellenumfang maximal 100.000 Referenzen; pro Fall 128 MiB physische
  und expandierte Quellnutzdaten, pro Zweig 4 MiB/4.096 Receipts. Zurückbehaltene
  Dataset-/Mitgliedschafts-/Projektionsdaten zusammen maximal 128 MiB.
- Das Register erhält eine eigene Gesamtgrenze von 128 MiB kanonischen Artefakt-
  Nutzdaten. Bei Erreichen stoppen, niemals alte Testöffnungen zur Freigabe löschen.
  SQLite-Dateigröße, RSS und Nutzdaten werden getrennt ausgewiesen.

## 4. Ausdrücklich neuer Prüfbereich für den echten Lauf

Der neue versionierte Lauf prüft die vollständige physische Quellenabhängigkeit
der ausdrücklich ausgewählten Fälle, nicht pauschal jeden fremden Inhalt der
großen Produktionsdatenbank. Das ist eine Änderung des Prüfbereichs und braucht
diese Freigabe; alte Schema-1-/D2-Verträge bleiben unverändert.

Der gewählte Bereich enthält alle kausalen Revisionen, Rücknahmen, Konflikte,
Bindungen, Wetter-, Spieler- und Ergebnis-Header der betreffenden Fälle. Nicht
nur verwendete Merkmalswerte oder günstige jüngste Meldungen prüfen. Fehlende
verknüpfte Inhalte müssen scheitern; nicht verknüpfte fremde/verwaiste Inhalte
sind außerhalb dieses neuen Bereichs und werden als solche ausgewiesen.
Eindeutige physische Eingangsbytes der gewählten Gesamtkohorte bleiben auf
128 MiB begrenzt; kumulierte wiederholte Lesearbeit wird getrennt gezählt.
Kein günstiges Teilpräfix auswählen, wenn die vorab erklärte Kohorte nicht passt.

Alle Fall-, Identitäts- und Split-Header prüfen, bevor Trainingslabels gelesen
werden. Finale Ergebnis-Körper bleiben bis zur dauerhaft protokollierten Öffnung
aller erklärten Testevents unzugänglich. Ein nachfolgender Fehler lässt diese
Öffnung bestehen. Physische D2-Wiederprüfung rekonstruiert erneut aus der Quelle
und vergleicht sämtliche Kandidaten, Tuningentscheidungen und Fitbytes.

## 5. Fachliche Effekte ohne erfundene Zuschläge

Bestehende Funktionen für gemeldete Ausfälle/erwartete Einsatzzeit, Stadtwetter
und belegte Spielerminuten/Erholung wiederverwenden. Unbekannt bleibt unbekannt;
Anstoßabstände sind keine gemessenen Spielendzeiten oder tatsächliche Müdigkeit.
Vereins- und Nationalteam-Minuten dürfen nur bei belegter nativer Spieleridentität
verbunden werden; alte Vereinsrollen werden nicht als neue Rollen angenommen.

Für die gemeinsame Nutzung wird ein eigener versionierter Merkmalsvertrag
`football-native-context-exposure-load-v4` benötigt: bestehende Kader- und
Belastungsprojektionen mit genau einer Wetter-/Terminprojektion, ohne doppelte
Spalten. Spätere Belastungsentscheidungen benötigen einen vollständig eingefrorenen
Spieler-/Eventumfang. Alte V2-/V3-Fits werden nicht auf diese Eingänge umetikettiert.
Die eine gemeinsame Torverteilung, der numerische Tilt und die Marktberechnung
bleiben die bestehenden Kerne; alle Wettarten werden daraus konsistent abgeleitet.

## 6. Abnahme und Veröffentlichung

1. Speichervertrag vollständig einschließlich kleiner bytegleicher Legacy-Parität
   und mindestens drei großer Einzel-Fälle im gemeinsamen Batch prüfen.
2. Echte Zwei-Speicher-Kette Prepare → Fit → Freeze → Testöffnung → Evaluate →
   physische Verify-D2 an isolierten Fixtures durchlaufen. Schreibspione belegen:
   keine Quelländerung, keine finalen Körper vor dauerhafter Öffnung.
3. Neustart, paralleler Öffnungsversuch, Quellenkorrektur und fehlgeschlagene
   Auswertung dürfen keine neue unangetastete Testkohorte herstellen.
4. Gemeinsame V4-Projektion gegen ihre vorhandenen Einzelbesitzer prüfen;
   fehlende Daten, widersprüchliche Spieleridentität und verspätete Meldungen
   müssen ohne erfundene Ersatzwerte behandelt werden.
5. Kleine gespeicherte Kohorte real prüfen, danach exakt zählende Readiness für
   Training, Abstimmung und unabhängige Testevents aus bestehenden Originalen.
   Keine synthetischen oder skalaren Shadow-Belege als Kontextfälle umdeklarieren.
6. Freigabe unverändert: mindestens 200 unabhängige unangetastete finale Events
   zusätzlich zu Training/Tuning, drei Zeitblöcke, mindestens 2 % relativer
   gepaarter Brier-Vorteil, HAC/BH, Kalibrierung und kein schlechterer mittlerer
   Verteilungs-Logloss. Erst dann darf der Runtime-Leser den passenden geprüften
   Fit aus dem bezeichneten Register verwenden; keine automatische Aktivierung.

Technisch bestandener Code kann ohne neue Sicherung committed, gepusht und auf
dem VPS deployed werden. Das erzeugt nicht automatisch ausreichende echte Daten
oder einen positiven Qualitätsvergleich. Fehlen diese, bleibt die neue Wirkung
inaktiv; der bestehende reguläre Capture sammelt weiter, ohne zusätzlichen Scan.
Nach schriftlicher Freigabe folgt ein kurzer geprüfter Umsetzungsplan mit dem
bereits gewählten Unteragenten-/Review-Verfahren.
