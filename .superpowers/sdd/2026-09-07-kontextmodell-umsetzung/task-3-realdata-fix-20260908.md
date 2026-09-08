# Task 3 / A3 - Real-data Serve-Admission Fix

Stand: 8. September 2026. Ausgangsstand fuer den Fix:
`6031e31a574aecd55f3d1efe7baddada2b6115f8`. Dieser Bericht ergaenzt die
vorherige Ursachenanalyse `task-3-realdata-diagnosis-20260908.md`.

## Ergebnis

Die freigegebene enge Reparaturoption ist umgesetzt. Neue getrennte
Tour-Builds und ihre `calibration_only`-Traversierung verwenden dieselbe
atomare bilaterale Serve-Admission. Eine Zeile wird nur aufgenommen, wenn alle
sechs tatsaechlich benoetigten Game-/Break-Counts echte numerische, endliche,
nichtnegative Werte sind, alle vier Game-Denominatoren positiv sind und die
Breaks weder eigene Return-Games noch gegnerische Service-Games uebersteigen.

Bei einer Verletzung wird die komplette Serve-Zeile vor jeder Spieler- oder
Bucket-Mutation uebersprungen. Das gueltige Elo-Ergebnis bleibt erhalten. Es
gibt kein Clipping, keine Toleranzlockerung, keine erfundenen Denominatoren und
keinen Event-/Marktausschluss. Payload-/Codec-/Manifest-Schema und
`ModelState` sind unveraendert.

Der gewoehnliche Backtest und der explizite Legacy-Combined-Build rufen weiter
den bisherigen `update_from_match_row`-Pfad auf. Nur
`build_tour_state` und `run_backtest(..., calibration_only=True)` aktivieren
die neue Admission. Tests sichern sowohl diese Trennung als auch die
Payload-Identitaet eines gueltigen Updates gegen den alten Pfad.

## Implementierung

- `tennis/serve_model.py`
  - Ein gemeinsamer owning Helper klassifiziert Ablehnungen stabil als
    `missing_count`, `non_numeric_count`, `nonfinite_count`, `negative_count`,
    `fractional_count`, `nonpositive_game_denominator` oder
    `breaks_exceed_games`.
  - `ServeReturnModel.update_from_match_row_if_valid` validiert beide Seiten
    vollstaendig, bevor es den unveraenderten Updatepfad einmal aufruft.
  - `ServeAdmissionDiagnostics` ist ausschliesslich ein fluechtiger
    In-memory-Bericht: Zeilen-, Jahres-, distinct Match- und distinct
    Turnier-Counts, getrennte Unknown-Provenienz sowie exakte bekannte skipped
    Match- und Turnier-IDs. Er wird nicht serialisiert. Match-Identitaet stammt
    aus `row["id"]`, Turnier-Identitaet separat aus `row["tournament_id"]`.
- `tennis/tour_state.py`
  - `build_tour_state(..., diagnostics=None)` besitzt die freigegebene
    optionale caller-owned Berichtnaht.
  - Direkter ATP-Serve-Build und Calibration erhalten getrennte Summarys;
    die Admission gilt auch ohne angeforderten Bericht. Elo und `consumed`
    bleiben von einem Serve-Skip unberuehrt.
- `tennis/backtest.py`
  - `run_backtest(..., diagnostics=None)` nutzt die Admission ausschliesslich
    im bereits existierenden `calibration_only`-Modus, fuer ATP und einen
    gegebenenfalls aktivierten getrennten WTA-Serve-Pfad.
  - Der Defaultzweig ruft byte-/verhaltensseitig weiter den alten Updater.
- `scripts/rebuild_state.py`
  - Der getrennte CLI-Build sammelt pro Tour und getrennt fuer Build/Calibration
    die Diagnostik. Die Ausgabe ist deterministisches kompaktes JSON mit
    admitted/skipped Zeilen, distinct Matches/Turnieren, Jahren,
    Unknown-Counts und Gruenden; die potentiell grosse ID-Liste wird nicht
    gedruckt.
  - Originale Build-Ausnahmen werden nicht ersetzt oder verschluckt. Auch ein
    fehlgeschlagener Tour-Build gibt bis dahin erfasste Diagnostik aus; die
    bestehenden Status-/Exitregeln bleiben unveraendert.

## TDD RED

Erstes enges RED vor der Implementierung:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a3-realdata-red-serve-01' tests/test_serve_admission.py
```

Ergebnis: **11 failed**. Alle Faelle scheiterten erwartungsgemaess daran, dass
`ServeReturnModel.update_from_match_row_if_valid` noch nicht existierte.

Anschliessendes Integrations-RED:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a3-realdata-red-integration-01' tests/test_serve_admission.py tests/test_tennis_tour_state.py::test_separate_atp_build_skips_bad_serve_row_but_retains_elo_and_reports tests/test_tennis_tour_state.py::test_calibration_only_uses_bilateral_admission_and_reports_bad_source tests/test_tennis_tour_state.py::test_default_backtest_does_not_enable_separated_admission tests/test_tennis_training_refresh.py::test_cli_default_publishes_tours_independently_without_touching_legacy
```

Ergebnis: **18 failed**. Die erwarteten fehlenden Methode-/Keyword-/CLI-Nachweise
waren rot. Ein zusaetzlicher Testfixture-Datentypfehler (String-Datum im
Default-Backtest) wurde nur im Test zu `Timestamp` korrigiert; er war kein
Produktionsbefund und aenderte keine Anforderung.

## GREEN und fokussierte Regression

Nach Implementierung bestand der enge GREEN mit **18 passed in 1.06s**
(`.pytest_tmp/a3-realdata-green-02`). Danach wurden Unknown-Provenienz,
distinct Identitaetszaehlung und die unveraenderte Originalexception bei bereits
gesammelter Diagnostik ergaenzt.

Nach dem Controller-Selbstreview wurde die zunaechst mehrdeutige Bezeichnung
`event` korrigiert: `tournament_id` ist kein Match. Der Follow-up-RED in
`.pytest_tmp/a3-realdata-followup-red-01` zeigte **10 failed, 9 passed** fuer
separate Match-/Turnierdiagnostik und fraktionale Counts. Nach der Korrektur
bestand derselbe enge Satz mit **19 passed in 1.34s**
(`.pytest_tmp/a3-realdata-followup-green-01`).

Finaler Fokuslauf:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a3-realdata-followup-focused-01' tests/test_serve_admission.py tests/test_serve_decay.py tests/test_serve_indoor.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py tests/test_tennis_tour_state.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_state_codec.py tests/test_tennis_pipeline.py
```

Ergebnis: **239 passed, 3 skipped in 7.72s**, Exit 0.

Abgedeckt sind insbesondere die echte minimale Fawcett-Zeile, atomare
Ablehnung ohne halbes Winner-/Loser-Update, `None`, String, Boolean, NaN,
Infinity, negative, fraktionale und null Denominatoren, beide
Break/Game-Richtungen,
gueltige Defaultparitaet, Elo-Erhalt, Calibration-Verkabelung, CLI-Ausgabe,
Exception-Erhalt und unbekannte Source-Identitaet ohne erfundene ID.

## Echter isolierter Cached-Publish ohne Netzwerk

Ausgefuehrt wurde der controller-eigene Offline-Harness gegen einen neuen
Runtime-Child. `requests.sessions.Session.request` war auf Assertion gepatcht;
es gab keinen Providerzugriff:

```powershell
$env:BETBOY_RUNTIME_STATE_DIR='C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/.pytest_tmp/tour-offline-realdata-fix-20260908-02'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' output/context-evaluation/tour_offline_probe.py
```

Ergebnis: **OFFLINE_PROBE_EXIT=0**, `REFRESH_COMPLETE`, beide Touren getrennt
publiziert. OpenPyXL meldete vier bekannte `Unknown extension`-Warnungen beim
Lesen der gecachten Excel-Dateien; es gab keinen Test-/Buildfehler.

| Tour / Phase | admitted/skipped Zeilen | admitted/skipped Matches | admitted/skipped Turniere | Gruende |
|---|---:|---:|---:|---|
| ATP Build | 63,477 / 1,133 | 63,477 / 1,133 | 1,045 / 38 | 884 `nonpositive_game_denominator`, 249 `nonfinite_count` |
| ATP Calibration | 57,195 / 1,014 | 57,195 / 1,014 | 942 / 28 | 884 `nonpositive_game_denominator`, 130 `nonfinite_count` |
| WTA Build | 0 / 0 | 0 / 0 | 0 / 0 | Elo-only, keine Serve-Zeile |
| WTA Calibration | 0 / 0 | 0 / 0 | 0 / 0 | Elo-only, keine Serve-Zeile |

Alle Diagnosezeilen hatten bekannte Match- und Turnier-Identitaet sowie ein
bekanntes Jahr; alle drei Unknown-Counts waren 0. Die ATP-Skips betrafen im Build die Jahre 2010-2016,
2018-2019, 2021 und 2024-2026; im Calibration-Lauf endet die kausale
Stats-Traversierung 2024. Die exakten skipped Match- und Turnier-IDs bleiben im
caller-owned Diagnostikdict, nicht im Artefakt oder in der kompakten CLI-Zeile.

Ein zusaetzlicher Read-only-Audit ueber alle 64,610 tour-level-faehigen Zeilen
fand **0 fraktionale Count-Zeilen** und **0 positive bilaterale
Game-Denominator-Abweichungen** (`win_service_games == los_return_games` und
umgekehrt). Deshalb wurde keine weitere Symmetrieregel in die Admission
aufgenommen; ein solcher neuer realer Befund waere erneut berichts- und
entscheidungspflichtig.

Publizierte Identitaeten im isolierten SQLite-Artefaktregister:

- Manifest-Hash
  `5b9cda7ea2ecd127b38ace93b0c315306dec4a9d7c84442791bc1f688e36aaeb`,
  Slots exakt `tennis:ATP` und `tennis:WTA`.
- ATP-Artefakt
  `ad3e452ac0c77b752336a38cacecfaac935cce084a9db109d52c33b679435b0f`,
  Coverage `2026-07-27` als `tournament_start_proxy`, 8,127 serialisierte
  Serve-Zeilen, 7,770 Calibration-Samples.
- WTA-Artefakt
  `d43315e055a0824c277d90596c4b19049ea071157b371f332a85f1940c8b6a4f`,
  Coverage `2026-07-26` als `result_date`, 0 Serve-Zeilen und 7,025
  WTA-Calibration-Samples.

Beide Artefakte wurden anschliessend mit `load_tour_state` strukturell geladen;
Tour-Scope, Hash, Coverage und strikter Serve-Payload-Roundtrip waren gueltig.
Das ist ein realer Build-/Serialisierungs-/Publication-Nachweis fuer die
versionierten Caches, aber weder aktuelle Providerfrische noch Empirie.

## Vollsuite

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a3-realdata-followup-full-01'
```

Ergebnis: **1904 passed, 15 skipped, 97 subtests passed in 68.05s**, Exit 0.

## Dateien und Commit

Task-Dateien:

- `tennis/serve_model.py`
- `tennis/tour_state.py`
- `tennis/backtest.py`
- `scripts/rebuild_state.py`
- `tests/test_serve_admission.py`
- `tests/test_tennis_tour_state.py`
- `tests/test_tennis_training_refresh.py`

Commits:

- `fa98a3e4d107a44746391349b20225263b15e49c`
  (`Reject invalid serve rows in separated tour builds`)
- `2436dd411987ba0b543fd73212da6cbb72d65e99`
  (`Disambiguate serve diagnostic identities`)

Controller-eigene Aenderungen an `progress.md` und
`context-contract-decisions.md`, das untracked `output/` sowie der gepinnte,
inhaltlich unveraenderte `scripts/stage_runtime_databases.py` sind nicht Teil
des Fixes. Der Helper-Hash blieb exakt
`1441158C542E97A19B193FA0CD091B645EC6442D6D8157F1D4FCEABBBA72B026`.

## Selbstreview und Grenzen

Der vollstaendige Diff wurde gegen den Ruling geprueft:

- Die Admission laeuft vor beiden `_add_player`-Mutationen und nimmt bei Erfolg
  exakt den existierenden Rechenpfad; Decay, Priors und Ratingmath bleiben
  unveraendert. Fraktionale Counts werden mit eigenem stabilen Grund
  abgelehnt, nicht gerundet.
- Breaks werden in beiden fachlichen Beziehungen geprueft: eigener Return-
  Denominator sowie gegnerischer Service-Denominator. Boolean/String werden
  nicht zu Zahlen umgedeutet; NaN/Infinity und negative Counts werden nicht
  aufgenommen.
- Default-/Legacy-Pfade aktivieren den Helper nicht. Weder Preise noch
  Kalibrationsjahre, Cutoffs, Sample-Regeln oder Elo-Updates wurden geaendert.
- Diagnostik ist caller-owned, deterministisch und nicht persistent. Native
  Match- und Turnier-IDs werden getrennt und unveraendert verwendet; fehlende
  IDs/Jahre erhoehen getrennte explizite Unknown-Zaehler.
- `git diff --check` war sauber. Keine Task-fremde Datei wurde editiert,
  geloescht, zurueckgesetzt oder gestaged.

Wesentliche verbleibende Grenze: Die neue Admission veraendert die reale ATP-
Serve-Trainingspopulation um die oben ausgewiesenen Zeilen. Gruene Tests und
der erfolgreiche Offline-Publish belegen technische Korrektheit, **nicht**
bessere Prognosequalitaet. Unabhaengiges Codereview, aktuelle echte
Provider-/Build-Belege, empirische Akzeptanz, Backup/Restore, Push und
Produktionsaktivierung bleiben Controller-Gates. Es wurden keine VPS-,
Provider-, Push- oder Deploy-Operationen ausgefuehrt.
