# P5a: tatsächliche Fußball-Originalrechnung vor Rundung

## Ergebnis und enge Grenze

Abgegrenzter Implementierungsstand auf Parent
`bb297bbd34ca80eb83129e87cf1559cc44ae20df`, Branch
`codex/kontext-football-original-20260909`. Abschlussprüfung am 10.09.2026;
der Paketname bleibt zur zugehörigen 09.09.-Arbeitsserie konsistent.

Eine optionale Same-call-Aufnahme erhält die tatsächlich ausgeführten,
ungerundeten Tor-/Zählraten und die endgültigen aktiven, Saison- und
Formwahrscheinlichkeiten jedes berechneten Marktes. Sie rekonstruiert sie
nicht aus gerundeten Kandidaten und führt keinen zweiten Fit, keine zweite
Prognose und keine zusätzliche Kalibrierung aus. Die Defaultausgabe bleibt
im direkten Vergleich mit dem echten Parent unverändert.

**Kein abgeschlossener D3-Live-Anschluss:** Kein Scanner übergibt den neuen
Callback in diesem Paket. Keine B1-/A1-Publikation, kein B3-Ergebnis, kein
Consumer-/UI-/D4-Anschluss, keine empirische Freigabe und keine neue
Wahrscheinlichkeitswirkung wurden damit hergestellt. Kein Provideraufruf,
VPS-Zugriff, Push, Paketinstallieren oder vollständiger Repositorytestlauf.
Der Controller führt die integrierte Gesamtregression separat durch.

## Vor Implementierung bestätigte Regeln

Maßgeblich sind die vollständig gelesene freigegebene Spezifikation
`docs/superpowers/specs/2026-09-07-kontextmodell-design.md`, D3-D5 in
`docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md`, der
Gesamtplan sowie die tatsächlich ausgeführten Modell- und Scannerfunktionen.
Der Controller bestätigte zuerst den folgenden Schnittstellenbefund und
anschließend ausdrücklich die kleine owning Kalibrierklassen-Erweiterung:

- `original_capture=None` als optionaler Keyword-only-Callback an beiden
  bestehenden öffentlichen Modellfunktionen. Kein Callback/Clock/IO und
  keine neue Provenienzberechnung im Defaultpfad.
- Tatsächliche Aufnahmezeit UTC separat vom unveränderten logischen
  Historienstichtag des alten Modells. Dieser ist der Spielbeginn, nicht
  ein nachträglich behaupteter früherer Empfang der historischen Eingaben.
- Preisfreie, geschlossene Feldprojektion vorhandener Eingaben. Fehlende
  native Metadaten oder ein unbekanntes Rezept dürfen eine sonst berechenbare
  Originalprognose nicht sperren.
- Die owning `ConservativeMarketCalibration` darf exakt die alte UEFA-Closure
  ersetzen. Ihre Rechnung bleibt unverändert
  `min([float(probability)] + [float(curve(probability)) for curve in source_curves])`.
  Reihenfolge, Konvertierungen, Exceptions und Anzahl tatsächlicher
  Kurvenaufrufe dürfen sich nicht ändern.
- Bestehende beliebige Callables bleiben im alten Modell zulässig. Bei
  unbekannter oder nicht darstellbarer owning Form bleibt nur das
  Aufnahmerezept ausdrücklich `unsupported-callable`; das ist kein Modellgate.
- Keine Änderung der 15K-Mathematik, IDs, Quoten, Rangfolge, Modelle, Cricket
  oder bestehenden historischen Snapshot-/Ticketdaten.

## Tatsächliche Aufrufkette

Zeilennummern beziehen sich auf diesen Paketstand; das Parent-AST wird in
den Tests unabhängig aus dem ursprünglichen Git-Blob geladen.

| Zuständige Stelle | Tatsächliche Rolle / Änderung |
| --- | --- |
| `challenge_engine._fixture_model`, Zeile 1014 | Unveränderte Original-Tormodellmathematik; bestehendes optionales `include_provenance=True` nur beim neuen Callback genutzt. |
| `football_base_history_record`, Zeile 1137 | Bestehende preisfreie Referenzfelder. Lokale Berechnungs-IDs sind keine native Alias-Freigabe. Nicht geändert. |
| `_football_reference_provenance`, Zeile 1287 | Bereits vorhandene Auswahl-/Gewichtsprovenienz ohne neuen Fit. Nicht geändert. |
| `fixture_market_probabilities`, Zeile 1642 | League-/Team-Iterator einmal materialisieren; eine Originalrechnung; aktive/Saison-/Form-Matrizen und ursprüngliche Zählmodelle; vorhandene Markt-Kurven anwenden; danach optional genau ein Callback. |
| `build_fixture_candidates`, Zeile 2307 | Callback nur optional weiterreichen. Bestehendes `round(probability, 6)` und Ratenrundung auf drei Stellen, Kandidatenidentität und alle übrigen Berechnungen unverändert. |
| `challenge_15k._conservative_calibration_map`, Zeile 499 | Ausschließlich lokale Closure durch die owning Klasse mit exakt derselben Minimum-Rechnung ersetzt. |
| `_run_challenge_scan_worker`, Zeile 1818; `scan_daily_challenge`, Zeile 2187 | Tatsächlicher gemeinsamer automatischer/manueller Scanner. Nicht verdrahtet oder geändert. |
| Scanneraufrufe Zeilen 2377, 2421 und 2442 | UEFA-Berechenbarkeits-/Transferproben, nicht die endgültige kalibrierte Auswahl. Kein Callback eingeführt. |
| Scanneraufruf Zeile 2551 | Tatsächliche endgültige `build_fixture_candidates`-Rechnung mit Liga- oder konservativer Heimatligakalibrierung; zuständiger späterer Anschluss, in diesem Paket unverändert. |
| `wettfinder_automation._default_football_scan`, Zeile 2105 | Nutzt denselben Scanner im Finderprofil und den bereits vorhandenen Quellen-Capture-Scope. Nicht geändert. |

Die neuen Daten stammen aus der endgültigen Kalibrierung **aller drei**
ursprünglichen Modellvarianten. Auch Ecken-/Kartenraten und deren tatsächlich
berechnete Markttripel werden erhalten. Aus marktweise kalibrierten Marginalen
wird keine neue kohärente gemeinsame Torverteilung behauptet. Der getrennte
D1-Raw-Poisson-Replay bleibt unverändert und wird nicht als kalibriertes
Legacy-Original etikettiert.

## Schnittstelle und Aufnahmevertrag

`FootballOriginal` ist eine frozen Dataclass mit immutable JSON-Bytes und
`to_dict()` als jeweils neu abgelöster Projektion. Sie ist ein interner
Beobachtungswert, kein von außen akzeptierter B1-/A1-/Approvalvertrag.

Der Payload trägt:

- `schema=1`, `kind=football-original-market-calculation-v1`, unveränderte
  `prediction_version` und `model_contract_signature`.
- `captured_at`: genau ein tatsächlicher UTC-Clock-Aufruf nach der Rechnung;
  `logical_history_cutoff`: der tatsächlich vom Altmodell verwendete
  Kickoff-Stichtag. Ein nachträglicher Lauf wird nicht zurückdatiert.
- `source_evidence=unresolved-receipts-not-in-this-capture`: insbesondere
  keine aus dem Logikstichtag abgeleitete vorentscheidliche Quellenbehauptung.
- Vor Rechnung abgelöste `fixture`, `league_history` und optionale, separat
  geordnete `team_history`. Die Allowlist umfasst nur Fixture-ID/-Termin/
  Timestamp/Referee/Status, Liga-ID/Saison, tatsächliche Team-IDs, Tore,
  benötigte xG-/Ecken-/Gelbkartenwerte und den bestehenden Quellmarker.
  Namen, Quoten, Buchmacher, Secrets und freie Kontext-/verified-Felder
  werden nicht als alternative Transportfelder übernommen.
- `goal_model` mit tatsächlichen aktiven/Saison-/Formraten, Samples,
  Freshness und xG-Abdeckung; `count_models` mit tatsächlichen Raten,
  Dispersion, Samples und Schiedsrichteraggregaten. Keine Matrix wird neu
  aufgebaut, keine Rate aus einer fertigen Karte invertiert.
- `raw_probabilities` und endgültige `probabilities` als ungerundete
  Markttripel, die tatsächlichen `market_specs` und `calibration_recipes`.
- `goal_provenance` mit der bereits berechneten Auswahl-/Gewichtsreferenz
  sowie expliziten `limitations`.

Die Aufnahmerezept-Abfrage benutzt **denselben** vorhandenen
`calibration.get(market_key)`-Wert wie die Rechnung und konsumiert keine
zusätzliche Mapping-Abfrage oder Kurve. Die Eingabeprojektion erfolgt
vor der Rechnung, damit ein späterer benutzerdefinierter Kalibrator
die protokollierten bereits konsumierten Eingaben nicht umschreibt.

Nur exakte owning `MarketCalibration`-Instanzen mit bekannten numerischen
Punkten sowie exakte `ConservativeMarketCalibration`-Instanzen mit
Tuple-Quellkurven erhalten ein beschreibbares Rezept. Nichtstandardisierte
Iteratoren werden durch die Beschreibung nicht konsumiert. Unbekannte
Callables werden nicht inspiziert, aufgerufen oder zertifiziert.

Unverändert akzeptierte Legacy-Werte werden nicht heimlich repariert:
Bool-Ausgaben bleiben Bool; nichtfinite oder nichtnumerische Ergebnisse
erhalten in der Aufnahme einen typisierten unavailable-Marker, während die
Originalrückgabe unverändert bleibt. Nicht unterstützte Typen, ungültiges
UTF-8 oder für die Finite-Prüfung nicht darstellbare sehr große Integer
werden ausdrücklich markiert, nicht in erfundene Zahlen umgewandelt.
Ein malformed owning Rezept darf keinen freien Text transportieren.
Ein Fehler des ausdrücklich bestellten Callbacks propagiert sichtbar;
er wird nicht als fehlendes Modell verschluckt.

## Reale Parent-Parität

Der Vergleich verwendet keine nachgeschriebene erwartete Altmathematik:

- Parent `bb297bbd34ca80eb83129e87cf1559cc44ae20df`.
- Originaler Git-Blob `challenge_engine.py`:
  `00a4b32eec249c4664b013c1c02ca78233114f45`.
- Originaler Git-Blob `challenge_15k.py`:
  `7d2ed4eeae0de7c949877111c90a9d3fe8b2928b`.
- Beide Originaltexte werden in `test_football_original_parity.py` mit
  `git show` aus genau diesem Commit gelesen. Das echte Engine-Modul wird
  ausgeführt; die ursprüngliche konservative Factory wird als unveränderter
  AST aus dem realen Blob kompiliert.
- Whole-module-AST: Engine exakt gleich nach Entfernung ausschließlich
  der expliziten Callback-Zweige und neuen Klasse; Challenge-Modul exakt
  gleich nach ausschließlich der genehmigten Closureersetzung.
- Zwölf vollständige Kandidatenvergleiche: zwei Profile, drei
  Liga-/Transfer-Scopes, Callback aus/an. Einschließlich aller serialisierten
  IDs, Gründe, Freigabe-/Preisfelder und Reihenfolge. Alle Floatwerte werden
  zusätzlich als `float.hex()` verglichen, nicht mit einer Toleranz.
- Acht konservative Eingaben einschließlich Null/Eins, Bruchzahl, Bool,
  NaN und beider Unendlichkeiten; Zustand und Reihenfolge der tatsächlichen
  Callables identisch. Zwei Ausnahme-/Kurzschlusspositionen separat geprüft.
- UEFA-Endtripel gegen den echten Parent, mit beiden vollständigen
  owning Kurvenrezepten, ihren Samples und unveränderter Quellreihenfolge.

Die neuen Assertions ergänzen alte Tests; keine alte Fixture, kein
eingefrorener Helper und kein Legacy-Modell wurde normalisiert oder verändert.
Git-Blob-Identität und nachstehende tatsächliche Raw-SHA256 sind getrennte
Angaben, keine plattformübergreifende Bytegleichheitsbehauptung.

## TDD und eigene Testbelege

Alle XML liegen unverändert unter `.pytest_tmp/` dieses Worktrees. Die
fehlgeschlagenen Zwischenstände bleiben erhalten; sie werden nicht als
erfolgreiche Tests umetikettiert. Zeiten nach pytest-Konsolenausgabe.

| Lauf | Eigenes Ergebnis | Bedeutung |
| --- | --- | --- |
| `p5a-first-red-01` | 7 rot, 0,40 s | Tatsächlich fehlende Callback-API bzw. neues Aufnahmemodul, vor Implementierung. |
| `p5a-first-green-02` | 6 grün, 1 rot, 0,56 s | Testvergleich konnte das bestehende unendliche Kandidaten-Preisfeld nicht JSON-kodieren; Testhelper auf explizite Floathex-Darstellung korrigiert, keine Modelländerung. Tuple-Matrixschlüssel wurden ebenfalls nur im Vergleichshelper behandelt. |
| `p5a-parity-green-03` | 32 grün, 1 rot, 2,91 s | AST-Testhelper traf fälschlich die alte `team_history`-Bedingung; auf die ausdrücklich neue `original_capture`-Bedingung begrenzt. Kein Source-Finding. |
| `p5a-side-effects-red-04` | 33 grün, 2 rot, 3,07 s | Echte Fehler der ersten Aufnahme: zusätzliches stateful Mapping-get und erst nach Kalibrator-Seiteneffekt kopierte Eingaben. |
| `p5a-side-effects-green-05` | 35 grün, 3,09 s | Dieselben Gegenfälle nach Same-get-/Vorabkopie-Korrektur grün. |
| `p5a-focus-06` | 208 grün, 10,86 s | Neue Iterator-, Metadaten-, Clock-, Bool-/Nonfinite-, Preisunabhängigkeits- und Fehlerkontrollen plus bestehende Football-Fokusmodule. |
| `p5a-unallowlisted-red-07` | 52 grün, 4 rot, 4,25 s | Drei freie nichtnumerische Callable-Payloads wurden zunächst mitkopiert; außerdem konsumierte die Rezeptbeschreibung einen nichtstandardisierten Quelliterator. |
| `p5a-broad-08` | 357 grün, 32 Untertests, 19,99 s | Nach numerischer Ergebnisprojektion und exaktem Tuple-Rezeptvertrag, inklusive bestehender 15K-Suite. |
| `p5a-recipe-red-09` | 1 rot, 30 deselected, 340,05 s | Echte weitere Kante: falsch typisierte owning Kalibrierpunkte transportierten freien Text. Derselbe permanente Fall ist nach expliziter numerischer Punkttypprüfung grün. Dieser Prozess war beim Start des korrigierten Nachlaufs noch offen, beendete sich regulär mit dem erwarteten ursprünglichen Fehler; XML und Ausgabe wurden nicht ersetzt. |
| `p5a-final-focus-10` | **368 grün, 32 Untertests, 63,92 s** | Finaler Source-/Teststand, 57 neue Fälle sowie bestehende Provenienz-, Kalibrier-, xG-, Markteligibilitäts-, Core-, 15K- und D1-Replay-Regressionen. Keine Skips. |

Alle permanenten Negativ-Assertions bleiben bestehen. Es gibt keinen
nachträglich künstlich grünen Originalbeleg. Die langsame neunte Probe
lieferte keine Aussage zu Produktivperformance. Ein versuchter lokaler
Prozessstatus-Lesebefehl war nicht erlaubt; es gab weder Eskalation noch
Abbruch anderer Prozesse. Ein zusätzlicher read-only Hashbefehl enthielt
einen nicht vorhandenen, fachfremden Legacy-Dateipfad und ein optionales
Auditlesen traf einen im Parent nicht enthaltenen Bericht; beide änderten
keine Datei und wurden nicht als Nachweis verwendet.

Finaler Testbefehl mit der vorhandenen Quality-Umgebung:

```text
python -B -m pytest -q -p no:cacheprovider
  tests/test_football_original_capture.py tests/test_football_original_parity.py
  tests/test_football_base_provenance.py tests/test_calibration.py tests/test_xg_hybrid.py
  tests/test_challenge_market_eligibility.py tests/test_core_audit_regressions.py
  tests/test_challenge_15k.py tests/test_context_replay.py
  --basetemp=.pytest_tmp/p5a-final-focus-10
  --junitxml=.pytest_tmp/p5a-final-focus-10.xml
```

### Unveränderte XML-SHA256

```text
p5a-first-red-01.xml         0db7d64261955d4a3dee69b9d2f0df80e40ba2116bb74a474a222a49b9db2060
p5a-first-green-02.xml       7e71742894bcbc48f2c84d7b4ce799ff8791265999d809a88af069f4c39fed1f
p5a-parity-green-03.xml      d5fc0977056a4fb54ce6a7b781a16c59aa285d97ecf86cf332a02a180bc5da12
p5a-side-effects-red-04.xml  bc833f509193bf9da555f4fb02396c7a5910d5ce0444f0fd200e608a23b3daef
p5a-side-effects-green-05.xml b2c4277735043593dff552c2ffdb91ff3426b13caa59809e78b339bae6e5f02d
p5a-focus-06.xml             2f4e1aafc50e6aaeed6956dc2d70456be6fb380f6a3b88cfb8516dbc4e15407a
p5a-unallowlisted-red-07.xml  13cd817d8845ab8fc09b0788ca8764cfe5ed8631950c36c2247de95ccd19072c
p5a-broad-08.xml             0eeec4f1c45194f5224c2f721e9962941d53294b8f4be7bcdc9cf8f7085a8060
p5a-recipe-red-09.xml        33be352ae95259e7270822a778049b1808669d8f23fd86f23229ce54c4bf8c78
p5a-final-focus-10.xml        8820f3e7654b928a26cc5469371e441abff9ad319423aec9c21b206342000b1e
```

## Raw-SHA256 des eingefrorenen Reviewumfangs

```text
football_original.py e5ccaf7d66a7b6138d602f7539f40f01f77095f73c1531d77d9bc69c04d5f2d9
challenge_engine.py 9e3b35cc9c0aba5f611d334336beaccfd4e885b280d9173dd98dcd7c6740922e
challenge_15k.py 289b3a2a2b4676666cf7c87f95af8c77260d0d4e812735f46854d6b2e5ec3c73
tests/test_football_original_capture.py 6909fe55fcca1888f9b7d5c8c5bc5ed5b1f12bc452b56399bca7d8be805f2546
tests/test_football_original_parity.py 1a91b75dd96527c7e03506b65bd9d3104a462279ad3f45ed56907288f26da962
```

`git diff --check` ist sauber. Diese lokalen Belege sind keine unabhängige
Reviewfreigabe und keine Deployment-/Live-/Quellenfreigabe. Das Paket wird
mit fokussiertem Commit unverändert an den Controller zur unabhängigen
Gegenprüfung übergeben; keine Originalbelege werden dafür überschrieben.
