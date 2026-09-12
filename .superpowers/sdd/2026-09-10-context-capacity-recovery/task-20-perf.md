# Task 20 - lokale synthetische C2/C2b-Performanceprobe

12. September 2026, Start 09:23:35 UTC. **Messung abgeschlossen, alle vollständigen
Wert-/Byte-/Hashvergleiche PASS. Keine native C-Abnahme oder Produktänderung.**

## Gemessene API-Zeiten

Sekunden, jeweils **eigene process_time-CPU / Wandzeit**. Ein echter neuer
5.000er- und 50.000er-Refset, jeweils genau eine Messung pro aufgeführter API;
kein Hochrechnen auf Sportprofile, sieben Tage oder Abnahmegrenzen.

| Synthetische Referenzen | put_refset CPU / Wand | vollständiges iter_refset CPU / Wand | vollständiges iter_snapshot_bytes CPU / Wand |
| ---: | ---: | ---: | ---: |
| 5.000 | 0,031250 / 0,030414 | 0,093750 / 0,091890 | 0,171875 / 0,178091 |
| 50.000 | 0,250000 / 0,273406 | 0,890625 / 0,887509 | 2,765625 / 2,787310 |

Der ebenfalls echte, separat erfasste `put_snapshot_parts`-Aufbau benötigte
0,171875 / 0,180238 s beziehungsweise 2,671875 / 2,671622 s. Commits sind im JSON
separat erfasst und nicht in den API-Zeilen versteckt. Der gemessene Instrumentrumpf
einschließlich Fixtureaufbau, Nebenphasen und SQL-Zählrunden benötigte insgesamt
9,156250 CPU- / 9,326290 Wandsekunden; Import/Prozessstart und das abschließende
JSON-Schreiben liegen außerhalb dieses Gesamttimers.

## Was wirklich erzeugt und verglichen wurde

Referenzen sind fortlaufende Integer als 64-stellige lowercase Hexstrings,
vollständig rückwärts an `put_refset` geliefert. Das ist kein Sportdatensatz.
Der Snapshot besitzt einen ausdrücklich nichtfachlichen, 312 Byte großen
Finite-JSON-Transportheader mit `semantic_model_validated=false`. Der echte
C2b-Aufbau bindet die vollständigen ursprünglich geschriebenen Canonicalbytes,
ihren SHA256 sowie den unveränderten alten `{key,payload}`-Digest. Der alte
Finite-JSON-Snapshotdecoder wurde zusätzlich auf dem vollständigen Output geprüft;
eine Modell-/Quellenvalidierung wurde nicht behauptet.

| Referenzen | Canonical-Refbytes, Quelle = Output | Snapshotbytes, Quelle = Output | tatsächlich angelegte SQLite-Datei | davon Freelist nach Commit |
| ---: | ---: | ---: | ---: | ---: |
| 5.000 | 335.001 | 335.333 | 880.640 | 684.032 |
| 50.000 | 3.350.001 | 3.350.333 | 8.695.808 | 7.057.408 |

Alle Referenzwerte, Reihenfolge, vollständigen Canonicalbytes und SHA256 stimmen
exakt; auch beide Snapshotdigests stimmen. Jeweils tatsächlich vorhanden:
ein Refset, ein Refblock, eine Mitgliedschaft, ein Header, ein Snapshot-Part,
null Stagingzeilen. Bei unverändertem 16-MiB-Blocklimit passen beide Sets in je
einen Block (160.000 / 1.600.000 Binärbytes). Snapshotausgabe: 6 / 52 Chunks,
je höchstens 65.536 Byte. Dies ist insbesondere **kein** gemessener Kompressions-
nachweis eines vollständigen migrierten Bestands; die SQLite-Freelist zählt mit.

Der neu angelegte Messworkspace enthält abschließend 15 benannte Dateien mit
24.346.050 Bytes, einschließlich beider Quellen, Vergleichsausgaben, Datenbanken
und JSON-Berichte. Keine dortige Datei wurde wiederverwendet oder überschrieben.
Das ist eine lokale Dateisumme, keine globale/nativ durchgesetzte Plattenquota.

## Konkreter Zählbefund und Semantikgrenze

Eine **separate zusätzliche** vollständige `iter_refset`-Leserunde mit SQL-Trace
zählte 30.064 beziehungsweise 300.064 tatsächlich ausgeführte SQL-Anweisungen.
Die sechs Generation-PRAGMAs (`data_version`, beide `schema_version`,
`max_page_count`, `cache_size`, `mmap_size`) wurden jeweils 5.006/5.007 bzw.
50.006/50.007-mal ausgeführt. Die Trace-Runden kosteten 0,109375 / 0,104733 s
bzw. 1,750000 / 1,746668 s; **diese beobachterbeeinflussten Zeiten sind nicht die
obigen Baselinezeiten**. Der Zählbefund weist einen konkreten Kandidaten für
spätere Optimierung aus, beweist aber noch keinen bestimmten CPU-Anteil.

Eine mögliche folgende Änderung wäre eine getrennte begrenzte Chunk-Schnittstelle
für interne vollständig gebundene Rekonstruktion. Dabei bleibt die bestehende
Scalar-Schnittstelle unverändert: ihr aktueller Vertrag erkennt Änderungen vor
jedem einzelnen `yield`, auch mitten im Block und am Ende. Die Prüfungen einfach
aus dieser Schleife zu entfernen, wäre eine Semantikänderung. Vor einer neuen
Chunk-API wären vollständige Vorprüfung, Reihenfolge/Bytes, Abbruch/Mutation,
Transaktionsende und Terminalprüfung ausdrücklich zu testen. **Hier wurde keine
solche Optimierung implementiert und kein C-Abnahmefehler aus den Zeiten abgeleitet.**

## Reproduzierbarkeit und Grenzen

Windows 11, Python 3.12.14, SQLite 3.53.1. Tracemalloc war vor jeder Messung
ausgeschaltet und wurde nie gestartet. Beide Fälle benutzen dieselben unveränderten
Default-C-Limits sowie UTF-8, Seiten 4096, Cache -4096 KiB, mmap 0, DELETE/FULL,
temp_store FILE, trusted_schema OFF und max_page_count 1.048.576. Snapshotchunks
sind fest 64 KiB. Leser: dieselbe private Verbindung nach explizitem Commit,
query_only ON und gehaltenes BEGIN; Betriebssystemcaches wurden nicht geleert.

Die Timer enthalten den API-Aufruf und vollständiges `list(...)`-Konsumieren
der begrenzten Fixtures, nicht anschließende Canonicalserialisierung, Vergleichs-
Dateischreibvorgänge oder Commits. Das ist **keine** RAM-Messung und kein Beleg
für corpusgroße Materialisierung im Produkt. Root führte parallel die Vollsuite
aus: die CPU-Zahlen gehören diesem Prozess, die Wandwerte sind kein Benchmark
eines ungestörten nativen VPS. Kleine CPU-Werte sind hier erkennbar quantisiert.

Instrument: `.pytest_tmp/task20-c2-perf-instrument-ccr01.py`, SHA256
`1bf258b16f7ae2d5d13a3fa17c757c3d56886d5ae52ce8f2837cf359c4c6fc0d`.
Vollständiges Ergebnis: `.pytest_tmp/task20-c2-perf-ccr01/result.json`, SHA256
`e57883fc4875869d05d687807b3d43e9ae2479dcd848ba0fce05e2a61ae6c86c`.
Die physischen Quellen und Vergleichsausgaben liegen in dessen beiden Fallordnern;
das JSON enthält sämtliche tatsächlichen Größen, Descriptoren und SHA256.

Geprüfte Module vor und nach der Messung unverändert:
`refs.py` = `e80492be96ea0aacd5bb2038018c90bf8201d3e4a616d2574c456d5f9899cb2b`,
`snapshots.py` = `75bfe759505d7b9a0719844ab397f2a86f0d05cf059d4a93a261f6a961539909`.
Weitere sechs abhängige Codehashes stehen ebenfalls vor/nach identisch im JSON.
Wiederholung erfordert einen neuen, nicht vorhandenen `--workspace` unter genau
diesem Worktree-`.pytest_tmp`; das Instrument verweigert vorhandene Ziele.

Keine Server-/Gitaktion, keine Produktänderung, keine Löschung und keine neuen
Grenzwerte. Native Vollprofile, globale Ressourcenbilanz, B-Prüfung und Release
bleiben außerhalb dieses Messauftrags.
