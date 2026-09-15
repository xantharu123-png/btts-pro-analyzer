# Tennis-Abschluss: wiederholte CPU-Arbeit

## Nachgewiesener Fehler

Der echte Lauf für den 15.09.2026 auf `ab27535` erreichte das bestehende
900-Sekunden-Limit. Nach 117 gefundenen Spielen und 55 vorbereiteten
Prognosen waren erst acht unabhängige Revisionen gespeichert. Keine OOM-
Beendigung; 747 CPU-Sekunden und 1.733.890.048 Bytes Dienst-MemoryPeak.
Der frühere Statusbericht war deshalb kein Nachweis einer vollständigen
Reparatur. Original und Revision des geänderten Gegners (WTA 183831,
Prognose 1419) blieben unverändert.

## Enger Reparaturumfang

- Exakt gleiche, unveränderliche Referenzwerte dürfen ihre Digest- und
  Ordnungsprüfung wiederverwenden. Zwei Einträge je Operation; keine
  Verwendung einer fremden Hashbehauptung als Validierungsnachweis.
  Geänderte Werte, mutable Objekte und String-Unterklassen bleiben kalt.
  Eingaben über dem Cachelimit werden vollständig geprüft, nicht gekürzt.
- Payloadkopien kopieren alle mutablen Werte; die große Liste bereits
  unveränderlicher Strings braucht keine rekursive Kopie jedes Strings.
- Der vorbereitete Tennis-Reader verbindet den realen physischen Decoder
  unmittelbar mit der vollständigen nativen Quellenprüfung. Kein externer
  `already_validated`-Schalter. Fremde Touren und zukünftige physische
  Beschädigungen werden weiterhin vor der Projektion erkannt.
- Quellenprüfung und physische Prüfung werden nicht nochmals identisch
  wiederholt, bevor derselbe Datensatz unveränderlich indiziert wird.
- ATP und WTA mit identischem Entscheidungszeitpunkt teilen ein einziges
  vollständig geprüftes physisches Eingangsabbild. Getrennte Tourindizes,
  sämtliche Revisionen und Modelle bleiben erhalten; unterschiedliche
  Entscheidungszeitpunkte werden nicht zusammengelegt.
- Der echte Tageslauf protokolliert Historienaufbau, Vorbereitung und
  Veröffentlichungsfortschritt. Ein Gegnerkonflikt bleibt ein sichtbarer
  Teilfehler; andere Integritätsfehler werden nicht verschluckt.

Keine Zeitgrenze, Historienabdeckung, Prognose, Wettart, Quote, Einsätze
oder empirische Modellfreigabe geändert. Cricket bleibt ausgenommen.

## Lokale Nachweise vor Linux-QA

325 gezielte Kontext-/Historientests, 351 weitere Tennis-/Transporttests
und anschließend 31 Tests der finalen Fortschritts- und Konfliktbehandlung
bestanden. Diese Gruppen überlappen und werden nicht zu einer Vollsuite
addiert. Ein erster Lauf hatte ausschließlich Temp-Verzeichnis-
Berechtigungsfehler und wurde mit lokalem, isoliertem Temp-Pfad wiederholt.

Linux-Leistung, tatsächlicher vollständiger Batch und Produktionsfreigabe
sind getrennt nachzuweisen. Der alte Fehlerbericht steht in
`output/playwright/backup-offload-release-20260915.md`.

## Tatsächliche isolierte VPS-Messung

281 Linux-Tests des ersten CPU-Patches bestanden. Ein fest gepinnter echter
Snapshot mit 302.279 Referenzen wurde mit altem und neuem Code verglichen:
Input-Key, Payloadbytes und Consumer-Referenz exakt unverändert. Alter Code
5,264 / 4,561 s, neuer Code 3,470 / 2,209 s (erster / wiederholter Durchlauf).
Der neue Einzel-Tour-Reader verarbeitete 596.934 physische Zeilen in 244,75 s.
Dies motiviert zusätzlich den gemeinsamen ATP-/WTA-Durchlauf, statt den
überwiegenden Teil dieser Arbeit direkt nochmals auszuführen.

Breiter lokaler Kontext-/Tennislauf vor diesem letzten gemeinsamen Reader:
4.330 bestanden, sechs Skips, sieben Fehler. Sechs scheiterten im isolierten
CLI-Unterprozess an fehlenden gebündelten SciPy-Abhängigkeiten (sein `-I`
ignoriert den lokalen PYTHONPATH). Ein weiterer Workspace-Prüffall ist
gesondert zu untersuchen. Nicht als grüne Vollsuite ausweisen.
