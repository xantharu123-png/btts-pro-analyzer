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
