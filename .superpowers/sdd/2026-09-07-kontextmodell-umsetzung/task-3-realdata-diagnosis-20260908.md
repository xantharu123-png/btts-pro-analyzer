# Task 3 / A3 - Diagnose des realen ATP-Offline-Buildfehlers

Stand: 8. September 2026. Diagnosebereich: versionierte ATP-Seeds und der
isolierte Runtime-Klon unter
`.pytest_tmp/tour-offline-realdata-20260908-01`. Es wurden keine Quellen,
Produktionsdatenbanken, Modelle oder Source-Dateien veraendert und keinerlei
Netzwerk-, Provider-, VPS-, Push- oder Deploy-Zugriffe ausgefuehrt.

## Ergebnis

Der Fehler ist **keine Float-Rundung und kein Fehler der
Decay-Akkumulationsformel**. Primaere Ursache ist eine belegte Inkonsistenz bzw.
fehlende Game-Denominatorik in den versionierten ManTennisData-Zeilen:
`*_service_games_played` und `*_return_games_played` sind 0, obwohl dieselben
Zeilen positive Breakpoint-, Punkt- und Matchscore-Daten enthalten. Eine
sekundaere Robustheitsluecke im Reader laesst diese unmoeglichen, aber nicht
`None` gesetzten Werte als "usable box score" in den Serve-Akkumulator.

Der kleinste belegte Fehler ist **eine einzige Zeile und ein einziges Update**:

- Match-ID `2018-560-v717-f974-Q1`, US Open Q1, Turnierstart-Proxy
  `2018-08-27`, Hard/Outdoor, Kategorie `gs`, Alexey Vatutin gegen Tom Fawcett.
- Matchscore `64 36 61`; Gewinner-/Verlierer-Games 15/11; Serve-Point-Totals
  74/81. Die Zeile ist damit kein leerer Match-Platzhalter.
- Game-Denominatoren fuer beide Spieler: Service 0/0 und Return 0/0.
- Konvertierte Breakpoints: Vatutin 6, Fawcett 4; Return-Breakpoint-Totals 8/5.
- Fuer Fawcett ist dies der einzige bis zum Diagnose-Cutoff zugelassene
  Tour-Level-Serve-Datensatz. Aus leerem Zustand wird daher sowohl in `Hard`
  als auch `__overall__` exakt `ret_gms=0.0`, `ret_breaks=4.0`. Bereits der
  isolierte Aufruf `ServeReturnModel.update_from_match_row(row); to_payload()`
  endet mit `ValueError: serve breaks cannot exceed return games`.

Da kein frueherer Wert, kein Decay und kein spaeteres Fawcett-Update beteiligt
ist und die Differenz exakt 4.0 betraegt, ist Rundung als Ursache ausgeschlossen.
`_add_player` rechnet den uebergebenen Datensatz korrekt als
`d_ret + ret_gms = 0 + 0` und `d_brk + breaks_made = 0 + 4`; falsch ist die
Zulassung des widerspruechlichen Inputs, nicht diese Addition.

## Exakte Provenienz

Der Stats-Loader beschreibt die Modellquelle als ManTennisData
(`github.com/msolonskyi/ManTennisData`, MIT-lizenzierter Scrape von
`atptour.com`) und verwendet ausschliesslich die odds-blinde Allowlist. Der
konkrete Seed-Nachweis:

- `tennis/data/atp_matches_2018.csv`, Git-Blob
  `ac4206f79d71007ad6e41c5fba80dcf2c765ee5a`, physische Zeile 9119.
- SHA-256 von Paket-Seed und isolierter Runtime-Kopie ist identisch:
  `BDAE4FBE4060EA8CE4A1CDEBF1EE37D38E76D5FBC33BD11F3B66B4D144106982`.
- Das Feld `stats_url` der Zeile benennt die ATP-Identitaet
  `/en/scores/2018/560/QS094/match-stats?isLive=False`; sie wurde in dieser
  Diagnose nicht abgerufen.
- `atp_tournaments.csv` ordnet `2018-560` in physischer Zeile 4277 dem US Open,
  `Hard`, `Outdoor`, `gs` und Start `20180827` zu. Paket-Seed und Runtime-Kopie
  haben beide SHA-256
  `8EBFB9697B648217639B712DFC9ACC8121D4F77BFC3CF995402C495700C1BF3E`.

Die bestehende Source-Pruefung in `tennis/data_loader.py` verlangt fuer ATP nur
Tabelle, IDs und benannte Teilnehmer; sie prueft keine Plausibilitaet der
Boxscore-Denominatoren. Danach passiert die Zeile alle produktiven A3-Filter:
vollstaendige Spielernamen, nicht retired, datiert vor Cutoff und durch `gs`
als Tour-Level klassifiziert.

## Reproduktion und Messwerte

Controller-Reproduktion mit isoliertem Runtime-Root und explizit gesperrtem
Netzwerk:

```text
rebuild_state.py --force --no-refresh-data
WTA: published, coverage 2026-07-26
ATP: failed, ValueError

output/context-evaluation/tour_atp_diagnose.py
build_tour_state -> encode_state -> state.serve.to_payload
ValueError: serve breaks cannot exceed return games
```

Die eigene Read-only-Diagnose hat mit demselben Runtime-Root
`load_atp_stats(range(2010, 2027), refresh_current=False,
current_year=2026)` geladen, exakt wie `build_tour_state` nach Datum sortiert,
Namen normalisiert und dieselben retired-/Tour-Level-Filter angewendet. Nur der
Serve-Zweig wurde wiederholt; die Modell-/DB-Publikation blieb unberuehrt.

```text
cutoff 2026-09-08T16:55:27.890975+00:00
loaded rows 203159; tour-level serve updates 64610; accumulator rows 8202
eligible source rows with at least one breaks > return-games side: 225
eligible violating player sides: 394
final invalid accumulator rows: 5
```

Die 225 Zeilen liegen in drei klar begrenzten Eventgruppen:

| Turnier | Datum | Kategorie | Zeilen | Gewinnerseite | Verliererseite |
|---|---:|---|---:|---:|---:|
| `2016-96` | 2016-08-04 | `og` | 60 | 60 | 48 |
| `2018-560` | 2018-08-27 | `gs` | 112 | 109 | 91 |
| `2024-96` | 2024-07-27 | `og` | 53 | 53 | 33 |

Alle 394 verletzenden Seiten haben exakt `return_games_played=0`; auch die
jeweilige eigene und gegnerische Service-Games-Angabe ist 0. Es gibt daher
keinen vorhandenen symmetrischen Game-Wert, aus dem der Reader den fehlenden
Return-Denominator verlustfrei uebernehmen koennte.

Im fertig akkumulierten Serve-Modell bleiben in Payload-Reihenfolge diese fuenf
Verletzungen:

```text
fawcett t / Hard:        ret_gms 0.0, ret_breaks 4.0
fawcett t / __overall__: ret_gms 0.0, ret_breaks 4.0
griekspoor s / Hard:     ret_gms 0.0, ret_breaks 2.0
redlicki m / Hard:       ret_gms 0.0, ret_breaks 3.0
redlicki m / __overall__:ret_gms 0.0, ret_breaks 3.0
```

Andere betroffene Spieler werden durch spaetere gueltige Daten teilweise ueber
die nackte Endinvariante gehoben; das macht die urspruenglichen schlechten
Updates nicht valide. Der Serializer stoppt fail-closed an der ersten
verbleibenden Verletzung (`fawcett t / Hard`).

## Owning-Code und Fehlerklasse

- `tennis/data_loader.py:_validate_atp_matches` / `_completed_atp_rows`:
  strukturelle Aufnahme ohne Boxscore-Invarianten.
- `tennis/serve_model.py:is_tour_level`: `gs` und `og` sind absichtlich
  Tour-Level, daher werden die drei Eventgruppen nicht herausgefiltert.
- `tennis/serve_model.py:_add_player`: verwirft nur `None`; 0 Game bei positivem
  Break wird aufgenommen. `max(sv_gms - breaks_conceded, 0)` verdeckt parallel
  die analoge Service-Seiten-Inkonsistenz als 0/0-Hold, waehrend Return 4/0
  sichtbar scheitert.
- `tennis/serve_model.py:_validate_serve_payload`: die exakte Invariante
  `ret_breaks <= ret_gms` weist den ungueltigen Zustand korrekt zurueck.

Klassifikation: **Source-Dateninkonsistenz plus fehlende Input-Admission**, nicht
Float und nicht fehlerhafte Akkumulations-/Decay-Arithmetik. Der bestehende
Payload-Validator ist der letzte korrekte Schutz und darf nicht abgeschwaecht
werden.

## Enge Reparaturoptionen und Risiken

1. **Fail-closed pro vollstaendigem Serve-Matchupdate (engste sichere
   Softwareoption).** Vor jeder Mutation beide Spielerseiten atomar auf endliche,
   nichtnegative Werte sowie `breaks_made <= return_games` und
   `breaks_conceded <= service_games` pruefen. Bei Verletzung den kompletten
   Serve-Update dieser Matchzeile ueberspringen; Elo kann die Ergebniszeile
   weiterhin konsumieren. Nicht erst nach einem halbseitigen Update abbrechen.
   Risiko: mindestens 225 Tour-Level-Boxscores liefern keine Serve-Evidenz;
   betroffene Spieler fallen staerker auf Priors/Elo zurueck. Skip-Zaehler und
   Event-/Jahresabdeckung muessen im Buildreport sichtbar werden, und der neue
   ATP-Hash braucht Regression plus empirische Abnahme.

2. **Versionierte Source-Normalisierung/Backfill mit belegter Ersatzquelle
   (fidelste, aber operative Option).** Die betroffenen Eventzeilen aus einer
   vertrauenswuerdigen Boxscorequelle neu beschaffen, mit nativer Match-ID und
   Provenienz versionieren und danach strikt validieren. Risiko: Lizenz,
   Providerverfuegbarkeit, Match-ID-Mapping und Vollstaendigkeit; ausserhalb
   dieser Offline-Diagnose und kein Anlass, bestehende Seeds still umzuschreiben.

3. **Build frueher vollstaendig ablehnen.** Den Source-Validator um dieselben
   Invarianten erweitern und die betroffene Jahresdatei komplett zurueckweisen.
   Das verbessert Fehlerort und Diagnose, stellt aber ohne Backfill weiterhin
   kein ATP-Artefakt her und verliert im Extrem das ganze Jahr. Eher zusaetzlicher
   Integritaetsschutz als alleinige Betriebsreparatur.

Nicht tragfaehig sind: Float-Toleranz/Rundung (die Enddifferenzen sind exakt
2.0 bis 4.0), Clipping von Breaks auf Games (erfindet Statistiken), Ableitung
aus dem gegnerischen Service-Games-Feld (es ist ebenfalls 0), Rekonstruktion
aus dem Matchscore ohne belegten First-Server-/Tiebreakvertrag sowie pauschales
Entfernen von Olympics/Qualifikation/ganzen Turnieren. Diese Varianten wuerden
den Defekt verbergen oder unkontrolliert die Modellpopulation aendern.

## Offene Nachweise nach einer Controller-Entscheidung

Diese Diagnose autorisiert keinen Fix. Nach Wahl einer Option sind mindestens
ein RED/GREEN-Test mit der einzelnen Fawcett-Sequenz, Atomizitaet beider Seiten,
ein frischer isolierter ATP-Build, Payload-Roundtrip, getrennte Publication,
empirische Akzeptanz sowie die bereits separat geforderten Backup-/Restore- und
Produktionsnachweise erforderlich. Die erfolgreiche WTA-Publikation im
Controller-Probe und das unabhaengig freigegebene A4-Softwarecommit belegen
keinen dieser ATP-Gates.
