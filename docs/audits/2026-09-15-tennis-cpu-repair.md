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

Nachprüfung: der Workspace-Test setzte bei zwei schnellen gleich großen NTFS-
Schreibvorgängen unzulässig verschiedene Zeitstempel voraus. Sein ausdrücklich
nur Metadaten prüfender, extern versiegelte Dateien voraussetzender Owner bleibt
unverändert; die Fixture setzt jetzt deterministisch den geänderten Zeitstempel.
Die Linux-DAC-Simulation des engen Aufräumtests wird auch beim tatsächlichen
`fstat` konsistent simuliert, nicht nur beim Pfadstat. Kein Produktivschutz
geändert. QA-Archive werden mit `git -c core.autocrlf=false archive` erzeugt:
sonst konvertiert der Windows-Export Pythondateien und verletzt die unveränderten
Pins der Linux-Helfer. Die tatsächlichen installierten Pins waren korrekt.

Gemeinsamer echter ATP-/WTA-Reader: 596.934 Zeilen, 220.488 ATP- und 302.279
WTA-Referenzen in 258,05 s; 1.136.808 KiB Peak-RSS im isolierten Messprozess.
Die WTA-Referenz- und Projektionsprüfsummen stimmen exakt mit dem separaten
Reader überein. Dies ist kein MemoryPeak des gesamten produktiven Tageslaufs.

## Echter Lauf und abschließender Terminfehler

`fcc451f` wurde auf main gepusht und regulär deployed. Der explizite Tageslauf
für den 15. September verarbeitete anschließend 58/58 Einträge in 778 s unter
der unveränderten 900-s-Grenze. 56 frische Revisionen wurden gespeichert; zwei
geänderte Gegnerzuordnungen blieben als Datenkonflikt mit Exit 1 sichtbar.
Original 1419 und seine einzige Revision sind bytegleich zum Vorlauf. Kein
vollständig gültiger Datenlauf, aber kein Timeout mehr. 733 gezielte Linux-
Tests bestanden vor diesem Release; Zahlen nicht zu einer Vollsuite addieren.

Die danach ausgeführte normale Wettfinder-Runde zeigte einen weiteren engen
Fehlalarm: `football:1549774`, API-Football, Teams 1138/1126, hatte gespeicherte
Anstoßzeiten 13.09. 01:15 UTC und 15.09. 01:00 UTC. Die Gruppierung behandelte
diese reine Terminänderung als uneindeutige Spielidentität. Sie meldet jetzt
auch hier `schedule_revision_unresolved`, wie beim schon vorhandenen Vergleich
mit einer neuen Provider-Antwort. Voraussetzung: Alle übrigen Identitätsfelder
stimmen exakt überein. Kein Ergebnis wird geraten/geschrieben; andere Spiele
bleiben unabhängig abrechenbar. Veränderte Teams, Ausrichtung oder Provider-ID
bleiben operative Fehler. Zwei neue Tests vor Änderung rot, anschließend 207
gezielte Abrechnungs-/Wettfinder-Tests bestanden. Tatsächlichen Folge-Deploy im
Releasebericht prüfen, nicht allein aus diesem lokalen Nachweis ableiten.
