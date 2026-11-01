# Tennis-Rückhaltlimit 512 MiB (Live-Vorbereitung, D3 zweiter Teil)

Datum: 01.11.2026. Owner-Entscheid im Chat („Ja, 512 MB“) nach dem Befund unten.

## Befund (nur lesend, `output/release-20261031-2/tennis_nights.sh`, `tennis_impact.sh`)

- Der Tennis-Tagesscan scheiterte am 26.10., 27.10. und 01.11. an `live tennis output/reference retention exceeded`
  (`context_models/tennis_live_source.py`, `LiveTennisReadBudget.check`). Das Limit zählt Planheap und
  vorbereitete Nutzdaten konservativ (geteilte Kinder doppelt) und lag bei 128 MiB.

| Nacht | Fälle gesamt | letzter Fortschritt vor dem Abbruch | Sekunden bis dahin |
|---|---:|---:|---:|
| 26.10. | 112 | 60 | 908 |
| 27.10. | 80 | 70 | 874 |
| 01.11. | 85 | 60 | 811 |

- Folge: `batch.finish()` bricht beim Schritt „gemeinsame Prognosen werden abgeschlossen“ ab, der Scan endet mit
  Exit 1, der Alarm schlägt an. Vom 29. bis 31.10. lief der Scan ohne Vorbereitungsphase durch.
- Der VPS hat 3,8 GB Arbeitsspeicher, davon 3,4 GB verfügbar; die Einheit hat kein Speicherlimit.

## Änderung

`LIVE_OUTPUT_LIMIT = 512*1024**2` ersetzt die 128 MiB an beiden Stellen (Startwert und Obergrenze der
„nur verschärfen“-Prüfung). Bei rund 2 MiB gezählt je Fall reicht das für etwa 250 Fälle; das Fall-Limit bleibt 400.
Alle übrigen Grenzen (Zeit, Fälle, Rohzeilen, Rohbytes, Fall-Rückhalt 256 MiB) und das Fail-closed-Verhalten der
Gesamtgrenzen (Owner 25.10.2026) bleiben.

## Nächster Engpass

Die Live-Vorbereitung hat ein Zeitbudget von 1200 Sekunden (Wand und CPU). Gemessen wurden 10 bis 12 Sekunden je
Fall nach rund 190 Sekunden Anlauf: 85 Fälle brauchen etwa 1100 Sekunden, 112 Fälle wie am 26.10. etwa 1550. An
Tagen mit mehr als rund 90 Fällen bricht der Scan deshalb künftig am Zeitbudget ab
(`live tennis source time budget exhausted`), solange dieses nicht ebenfalls angehoben wird.
