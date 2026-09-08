# Task 4 / A4 – Tour-spezifische Leser und Prognose-Refresh

Stand: 8. September 2026
Status: Software und lokale Tests abgeschlossen; Produktionsaktivierung und empirische Abnahme offen.

## Ergebnis

Commit `870224c` (`fix: consume tour-specific model identities in tennis scans`) stellt Initialscan und netzwerkfreien Pending-Refresh auf unabhängig publizierte ATP-/WTA-Artefakte um.

- Beide Leser laden jede angeforderte Tour höchstens einmal pro Lauf, wählen ausschließlich anhand des Fixture-Felds `tour` und bauen niemals implizit ein Modell.
- Der normale Pfad hat `allow_legacy_model=False`. Nur der ausdrückliche Migrationspfad (Keyword beziehungsweise CLI `--allow-legacy-model`) darf das kombinierte Legacy-Pickle lesen. Dessen exakte, einmal über den bestehenden Trusted-Handle gelesene Bytes liefern den SHA-256; Scope und alte Abdeckung bleiben `legacy-combined`. Es werden keine Tour-Slots erzeugt.
- Fehlende/ungültige Tour-Artefakte erscheinen pro Tour unter `models` und zusätzlich in der bestehenden Top-Level-Liste `errors`. Eine gesunde Tour läuft weiter. Damit bleibt der unveränderte Consumer in `wettfinder_automation.py` kompatibel, der Teilfehler nur über `errors` beziehungsweise `failed`/`unavailable` erkennt.
- `load_manifest` und `load_tour_state` akzeptieren einen optionalen, aware Entscheidungs-Cutoff. Die aktive Manifestzeile wird in derselben Lesetransaktion vollständig hashgeprüft, bevor `published_at <= decision_cutoff` bewertet wird; Wrapper-Cutoff, Buildzeit und Entscheidungszeit bleiben kausal geordnet. Der äußere Artefakt-Digest bleibt die Modellidentität.
- `predict_match` weist Cross-Tour-Zustände zurück, validiert auch direkt übergebene Zustände an `training_cutoff <= built_at <= as_of` und speichert Hash, Buildzeit, Tour-Scope, benannte Abdeckungsart und Training-Cutoff in `context_evidence`. Preise/Quoten sind kein Teil dieser Identität.
- Ein geänderter Tour-Artefakthash erzeugt für ein noch offenes Event eine neue Modellrevision. Alte Prognosen und ursprüngliche Preiszeilen bleiben unverändert; Preisänderungen verändern die Modellidentität nicht.
- Bereits vom vorhandenen SofaScore-/ESPN-Abruf empfangene native Zustände werden mit Provider-/Event-ID und tatsächlicher aware Empfangszeit append-only gespeichert. Neuere Beobachtungen werden nicht durch ältere zurückgedreht; unbekannt bleibt unbekannt. Der Prediction-Append prüft Settlement, Beginn und die jüngste tatsächlich gespeicherte `started`-/`cancelled`-Beobachtung gemeinsam in seiner `BEGIN IMMEDIATE`-Schreibtransaktion. Es gibt keine zusätzliche Abrufschleife und der Pending-Pfad behauptet weiterhin `provider_checked=False`.
- Die Tagespipeline führt den Scan auch nach teilweisem/fehlgeschlagenem Rebuild aus, behält aber einen Fehler-Exit.

## TDD-Nachweis

Alle Befehle verwendeten `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`, `-p no:cacheprovider` und einen jeweils neuen Kindpfad unter `.pytest_tmp`.

### Verhaltens-REDs und jeweilige GREENs

1. Cross-Tour-Schutz: gezielter Selector `tests/test_tennis_tour_readers.py::test_prediction_rejects_cross_tour_state` war vor dem Guard rot (`1 failed`, keine `ValueError`) und danach grün (`1 passed`).
2. Cutoff/Identität/Evidenz: die neuen Reader-/Codec-Selektoren waren vor Implementierung rot (`5 failed, 1 passed`: unbekanntes `decision_cutoff`, fehlender Legacy-Hash und fehlende Evidenzfelder); nach Implementierung war der damalige Fokuslauf grün (`80 passed, 4 skipped`).
3. Status-/Cancel-Rennen: `test_observed_cancellation_during_model_computation_prevents_append` und `test_fixture_status_is_monotonic_and_unknown_is_not_invented` waren zunächst rot (`2 failed`: API/Guard fehlten) und danach grün (`2 passed`).
4. Normales Legacy-Verhalten: die Default-Assertions in `test_initial_scan_selects_independent_tour_states_with_same_player_names` und `test_missing_wta_state_keeps_atp_refresh_and_per_tour_diagnostics` waren vor der Opt-in-Abgrenzung rot (`2 failed`, `allow_legacy=True`). Nach `allow_legacy_model=False` als Default und ausdrücklichem positiven `test_explicit_legacy_fallback_remains_labelled` war der zugehörige Fokus grün (`7 passed`). Der finale Fokuslauf unten enthält alle drei Fälle erneut.
5. Selbstreview-RED (exakt):

   ```text
   & 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-self-review-red' tests/test_model_artifacts.py::test_manifest_hash_is_verified_before_publication_cutoff tests/test_tennis_tour_readers.py::test_prediction_rejects_explicit_state_with_training_after_build tests/test_tennis_pending_refresh.py::test_fixture_status_rows_are_append_only
   ```

   Beobachtung: `3 failed in 0.92s` – Cutoff wurde vor Manifesthash geprüft, ein direkt übergebener State erlaubte Training nach Build, Statuszeilen waren per direktem SQL änder-/löschbar.

6. Selbstreview-GREEN (exakt):

   ```text
   & 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-self-review-green' tests/test_model_artifacts.py::test_manifest_hash_is_verified_before_publication_cutoff tests/test_tennis_tour_readers.py::test_prediction_rejects_explicit_state_with_training_after_build tests/test_tennis_pending_refresh.py::test_fixture_status_rows_are_append_only tests/test_tennis_tour_readers.py::test_tour_reader_rejects_manifest_published_after_decision tests/test_tennis_pending_refresh.py::test_observed_cancellation_during_model_computation_prevents_append tests/test_tennis_pending_refresh.py::test_fixture_status_is_monotonic_and_unknown_is_not_invented
   ```

   Beobachtung: `6 passed in 1.39s`.

Ein zwischenzeitlicher A1–A4-/Tennis-Lauf vor der Selbstreview-Korrektur ergab `382 passed, 7 skipped`; zwei alte Assertions erwarteten zunächst die ersetzte Sammelfehlermeldung und wurden auf die weiterhin kompatiblen, präzisen Settlement-/Starttexte korrigiert. Ein nach der Konto-Unterbrechung ausgeführter Migrations-/Pipeline-Fokus ergab `7 passed`. Zwei falsch benannte historische Selektorversuche sammelten wegen nicht existierender Dateien null Tests; sie wurden als Befehlsfehler verworfen und nicht als Produktnachweis verwendet.

## Abschließende lokale Verifikation

Finaler A1–A4-/Tennis-Fokus:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-green-final-focus' tests/test_model_artifacts.py tests/test_tennis_state_codec.py tests/test_tennis_tour_state.py tests/test_tennis_tour_readers.py tests/test_tennis_predict.py tests/test_tennis_pending_refresh.py tests/test_tennis_pipeline.py tests/test_tennis_prediction_revisions.py tests/test_tennis_fixture_metadata.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_tab.py tests/test_tennis_side_bets.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py tests/test_quality_worker_integration.py
```

Ergebnis: `385 passed, 7 skipped in 15.84s`, Exit 0.

Einmaliger vollständiger Lauf unmittelbar vor dem Implementierungscommit:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-full-final'
```

Ergebnis: `1878 passed, 15 skipped in 66.08s`, Exit 0. `git diff --check` hatte Exit 0; die ausgegebenen LF/CRLF-Hinweise waren keine Whitespace-Fehler.

## Geänderte Dateien und Commit

Implementierungscommit: `870224c` (`fix: consume tour-specific model identities in tennis scans`).

- `model_artifacts.py`
- `scripts/run_daily_pipeline.py`
- `scripts/tennis_daily.py`
- `tennis/model_state.py`
- `tennis/predict.py`
- `tennis/shadow.py`
- `tennis/tour_state.py`
- `tests/test_model_artifacts.py`
- `tests/test_tennis_fixture_metadata.py`
- `tests/test_tennis_pending_refresh.py`
- `tests/test_tennis_pipeline.py`
- `tests/test_tennis_state_codec.py`
- `tests/test_tennis_tour_readers.py`

Dieser Bericht bleibt als Übergabeartefakt außerhalb des verlangten exakten Software-/Testcommits. Controller-eigene Änderungen an `PC_WECHSEL_UEBERGABE.md`, `docs/audits/2026-09-07-kontext-daten.md` und `progress.md` wurden nicht gestaged. `scripts/stage_runtime_databases.py` blieb unstaged und inhaltlich unverändert; sein Rohbyte-SHA-256 ist weiterhin `1441158C542E97A19B193FA0CD091B645EC6442D6D8157F1D4FCEABBBA72B026`.

## Selbstreview

- Anforderungen/Scope: Nur A4-Reader, ihre minimal erlaubten Registry-/Legacy-/Status-Seams und fokussierte Tests wurden geändert; keine B-/C-/D-Kontextmodelle, kein Cricket, keine Preis-, Echtgeld-, Ticket- oder Settlement-Regel.
- Korrektheit: Hashprüfung precediert Zeitentscheidung; Tourwahl ist explizit; Default ist separated-only; Legacy ist ausdrücklicher Bridge-Pfad; Aggregate-/Tourdiagnostik ist wahrheitsgemäß; der Statusguard befindet sich in derselben Schreibtransaktion wie Revision/Settlement-/Startprüfung.
- Erhalt bestehender Daten: Neue Modellstände werden als Revisionen angehängt. Originalprognose, Preisbeobachtungen, Tickets und Abrechnung bleiben unverändert.
- Wartbarkeit: Gemeinsame `_load_models`-/`_reader_status`-Hilfen vermeiden zwei Leserimplementierungen; Statusnormalisierung sitzt an den vorhandenen Provider-Adaptern; der eigentliche Predictor bleibt tourzustandslos.
- Testqualität: Die Tests prüfen nicht nur Aufrufzahlen, sondern gegensätzliche ATP-/WTA-Ausgaben bei identischen Namen, exakte Hash-/Coverage-Evidenz, Top-Level-Teilfehler, unveränderte Altprognose/Preisbasis und das Cancellation-Rennen vor Append. Keine Akzeptanz wurde abgeschwächt.
- Ergebnis: Keine bekannte Softwareblockade innerhalb A4. Die Änderung ist lokal testbar abgeschlossen, aber ausdrücklich nicht produktiv aktiviert.

## Offene Betriebs-, Daten- und Abnahmegrenzen

- Der Controller sah um 17:27Z ATP-Quellenantworten HTTP 200 (229 aktuelle Turnierzeilen, 11.680 Saison-Resultatzeilen; Proxy-Abdeckung 2026-09-07). WTA `2026w/2026.xlsx` antwortete HTTP 503 und wurde nicht geparst oder erneut versucht. Das beweist Quellenverfügbarkeit/-störung, keinen getrennten Tour-Build.
- Ein späterer read-only VPS-Logbefund zeigte den alten kombinierten Rebuild: ATP verarbeitete 197.212 Matches bis Proxy 2026-09-07, danach `REFRESH_FAILED HTTPError`; der bisherige kombinierte Stand mit ATP-Proxy 2026-07-27 blieb erhalten. Auch das ist kein erfolgreicher unabhängiger Publish und kein Live-A4-Nachweis.
- Reale getrennte ATP-/WTA-Builds, Manifestpublication, echter Initial-/Pending-Lauf, Runtime-Root, Backup/Restore (D4), technischer Release/Hash/Timer (D5), Push und VPS-Aktivierung bleiben Controller-Aufgaben. Für diesen Task wurden keine Provider-, Netzwerk-, SSH-, Deployment- oder Push-Operationen ausgeführt.
- Die empirische Aktivierung (mindestens 200 eindeutige Testevents über mindestens drei Zeitblöcke, mindestens 2 % relativer primärer Brier-Gewinn, HAC/BH FDR 5 %, nicht steigender Verteilungs-Logloss und Kalibrierung) ist weiterhin offen und von Software-/Quellstatus getrennt.
- Der aktuelle Live-Tennisbestand hat `match_duration_minutes`, aber 0/1239 Werte; `ended_at`, `player_a_id` und `player_b_id` fehlen. Das begrenzt spätere B6-Erholungs-/Identitätsarbeit und erweitert A4 nicht.

## Korrekturrunde nach unabhängigem Review

Das unabhängige Review auf `870224c` lautete **NOT APPROVED** und reproduzierte zwei Rennen:

1. Ein Initial- oder Pending-Append konnte nach dem angesetzten Beginn erfolgen, weil der transaktionale Guard nur den früheren Modell-Cutoff prüfte und die Pending-Nachprüfung vor einem blockierenden Write lag.
2. Ein Pending-Worker konnte nach paralleler nativer Verschiebung mit seinem veralteten Matchdatum/Start den Parent zurückdrehen und eine überholte Modellrevision anhängen.

Korrekturcommit: `156ba46` (`fix: guard tennis prediction append races`) auf Basis `870224c`.

### Implementierte Korrektur

- `modeled_at` bleibt unverändert der fachliche Prognose-/Modell-Cutoff.
- `store_prediction` liest im normalen Produktionspfad erst **nach** `BEGIN IMMEDIATE` eine separate tatsächliche aware Append-Uhr und prüft sie im selben Write gegen den gültigen Beginn. `append_observed_at` ist nur der explizite aware Offline-Test-/Replay-Zeitpunkt; `main()` und der unveränderte Wettfinder-Consumer lassen ihn weg und nutzen daher den echten Default.
- Der tatsächliche Receipt wird als `append_observed_at` im unveränderlichen Revisionspayload erhalten. Er ersetzt weder `created_utc`/Modell-Cutoff noch wird ein künftiger Kickoff als Uhr verwendet.
- Pending übergibt zusätzlich den tatsächlich gelesenen `model_revision_id`, `match_date` und `scheduled_start_utc` als erwarteten Snapshot. `store_prediction` vergleicht alle drei nach Erwerb derselben Schreibsperre. Eine zwischenzeitliche Revision oder Terminänderung führt zu `FixtureNotRefreshable`; der neue Parent bleibt erhalten, der stale Worker zählt nur `skipped`, und keine weitere Fetch-/Rechenrunde wird erfunden.
- Reine Preisänderungen gehören nicht zum Snapshot-CAS und verändern weiterhin weder Modellidentität noch Prognose.
- `tennis/prediction_revisions.py` behandelt einen Receipt-only-Retry desselben Modellpayloads zur gleichen Modellzeit idempotent: der erste Receipt bleibt erhalten. Vor Wiederverwendung werden **alle** vorhandenen Equal-Time-Zeilen samt vollständigem gespeicherten Hash geprüft. Gemischte, beschädigte oder mehrere Receipt-Historien werden als mehrdeutig abgelehnt; es wird keine Zeile geraten.

Geänderte Korrekturdateien:

- `scripts/tennis_daily.py`
- `tennis/prediction_revisions.py`
- `tennis/shadow.py`
- `tests/test_tennis_pending_refresh.py`
- `tests/test_tennis_prediction_revisions.py`
- `tests/test_tennis_tour_readers.py`

### TDD RED

Der erste Testlauf enthielt bei zwei Pending-Fällen noch einen Test-Signaturfehler für die erst zu implementierende Offline-Uhr und wurde nicht als verhaltensmäßiger RED-Nachweis gewertet. Der korrigierte, ausschließlich öffentliche Pfade verwendende RED war:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r1-r2-behavior-red' tests/test_tennis_tour_readers.py::test_initial_main_rejects_default_append_when_computation_crosses_start tests/test_tennis_pending_refresh.py::test_pending_default_append_rechecks_start_inside_write tests/test_tennis_pending_refresh.py::test_pending_stale_snapshot_cannot_rewind_concurrent_reschedule
```

Beobachtung: `3 failed in 0.97s`:

- `daily.main()` speicherte 1 Prediction nach dem Start.
- Pending meldete nach dem Zwischenraum Preflight→Write fälschlich `refreshed=1`.
- Pending meldete nach parallelem Reschedule fälschlich `refreshed=1` und drehte den Parent zurück.

### GREEN und Korrektur während des Fokuslaufs

Unmittelbarer R1/R2-GREEN mit demselben Selektor und `.pytest_tmp/a4-r1-r2-green`: `3 passed in 0.86s`.

Der erste breitere Fokus auf Reader/Pending/Revisions/Fixture-Metadaten fand anschließend eine reale Verträglichkeitslücke: ein inhaltlich identischer Equal-Time-Retry hatte wegen des neuen Receipt-Felds eine zweite Identität. Ergebnis: `1 failed, 116 passed`. Die Korrektur bewahrt den ersten Receipt, prüft aber alle gespeicherten Zeilen und Hashes. Der wiederholte Viermodul-Fokus war danach `117 passed in 16.10s`.

Zusätzlicher finaler Equal-Time-/Hash-/Aware-Clock-Fokus:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r1-r2-equal-time-final' tests/test_tennis_prediction_revisions.py::test_revision_mutations_are_rejected_and_equal_time_is_unambiguous tests/test_tennis_prediction_revisions.py::test_equal_time_retry_checks_all_rows_and_their_hashes tests/test_tennis_prediction_revisions.py::test_equal_time_retry_rejects_a_stored_hash_mismatch tests/test_tennis_prediction_revisions.py::test_equal_time_retry_does_not_choose_between_receipt_histories tests/test_tennis_prediction_revisions.py::test_explicit_append_clock_must_be_aware
```

Ergebnis: `5 passed in 0.93s`.

Finaler A1–A4-/Tennis-Fokus nach allen Korrekturen:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r1-r2-final-focus-2' tests/test_model_artifacts.py tests/test_tennis_state_codec.py tests/test_tennis_tour_state.py tests/test_tennis_tour_readers.py tests/test_tennis_predict.py tests/test_tennis_pending_refresh.py tests/test_tennis_pipeline.py tests/test_tennis_prediction_revisions.py tests/test_tennis_fixture_metadata.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_tab.py tests/test_tennis_side_bets.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py tests/test_quality_worker_integration.py
```

Ergebnis: `392 passed, 7 skipped in 16.11s`, Exit 0.

Einmaliger vollständiger Lauf für die exakten Fixbytes:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r1-r2-full-final'
```

Ergebnis: `1885 passed, 15 skipped in 66.80s`, Exit 0. `git diff --check` war vor dem Korrekturcommit Exit 0.

### Selbstreview der Korrektur

- R1: Default-Uhr wird innerhalb des unmittelbaren Writes und nicht aus `as_of`, `modeled_at` oder Kickoff abgeleitet. Initial- und Pending-Pfade besitzen öffentliche Reproduktionen; beide lassen Altprognosen unverändert.
- R2: Der erwartete Snapshot bindet nur Modellrevision und Fixture-Termin, nicht Preise. Die Prüfung und der nachfolgende Parent-/Revisionsappend liegen in derselben `BEGIN IMMEDIATE`-Transaktion.
- Retry/Integrität: Receipt-only-Retry erzeugt keine neue Revision und überschreibt nicht den ersten Receipt. Alle Equal-Time-Zeilen werden hashgeprüft; mehrere, gemischte oder beschädigte Kandidaten scheitern geschlossen.
- Scope: Keine Providerabrufe, Retryschleifen, Settlement-/Preis-/Ticketregeln, Tourmodelle oder B/C/D-Arbeit wurden geändert. Die kleine Ergänzung in `tennis/prediction_revisions.py` ist die notwendige Idempotenz-/Integritätsfolge des getrennt gespeicherten Append-Receipts.
- Arbeitsbaum: Controller-eigene PC-/Auditdateien, der ignorierte Ledger/Review und `scripts/stage_runtime_databases.py` blieben außerhalb des Fixcommits. Der gepinnte Helperhash blieb unverändert.
- Verbleibend: Ein unabhängiges Re-Review des Fixcommits ist noch ausstehend. Sämtliche bereits oben genannten realen Build-/Restore-/Release-/Empirie-Gates bleiben offen; lokale GREENs sind keine Aktivierung.

## Zweite Korrekturrunde: R3 Canonical-JSON-Vertrag

Das unabhängige Re-Review bestätigte R1 und R2 einschließlich eines echten blockierenden `BEGIN IMMEDIATE`-Interleavings. Es meldete jedoch R3/P2 auf `156ba46`: Ein raw-hash-konsistentes, aber nichtkanonisches JSON-Objekt oder ein Top-Level-Array aus Schlüssel/Wert-Paaren konnte beim Equal-Time-Retry durch `dict(payload)` als passend normalisiert werden. Der öffentliche Store gab `-1` zurück, obwohl der öffentliche Reader dieselbe einzige Zeile anschließend nicht lesen konnte.

Korrekturcommit: `c8935c2` (`fix: enforce canonical tennis revision retries`) auf Basis `156ba46`.

Geänderte Dateien:

- `tennis/prediction_revisions.py`
- `tests/test_tennis_prediction_revisions.py`

Implementierung:

- `_modeled_identity` akzeptiert nur ein echtes Top-Level-`dict` und kopiert dieses; es konvertiert keine Arrays oder fremden Mapping-Formen.
- Ein gemeinsamer strikter Decoder wird von Equal-Time-Retry und `read_latest_predictions` verwendet. Er verlangt ein JSON-Objekt ohne doppelte Schlüssel oder nicht-finite Konstanten und exakte kanonische UTF-8-Textform.
- Für jede gespeicherte Equal-Time-Zeile werden vor einer Idempotenzrückgabe der Digest über den exakten gespeicherten kanonischen Text, der Objektvertrag und `payload.created_utc == row.modeled_utc` geprüft.
- Erst nach diesen Prüfungen wird ausschließlich `append_observed_at` aus dem fachlichen Modellidentitätsvergleich entfernt. Der erste Receipt bleibt erhalten; alle bestehenden Hash-/Mehrdeutigkeitsablehnungen bleiben aktiv.
- Die Änderung repariert oder überschreibt keine fremden gespeicherten Bytes. Ungültige Zeilen scheitern im Store und Reader einheitlich mit `ValueError: tennis model revision content mismatch`.

### R3 RED

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r3-behavior-red' tests/test_tennis_prediction_revisions.py::test_retry_and_reader_reject_noncanonical_stored_revision
```

Ergebnis: `2 failed in 0.86s`. Sowohl `noncanonical-object` als auch `pairs-array` erhielten beim öffentlichen Receipt-only-Retry keinen Fehler; der öffentliche Reader wurde in beiden Parametrisierungen ebenfalls ausgeführt und scheiterte erst danach.

### R3 GREEN und Regression

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r3-green' tests/test_tennis_prediction_revisions.py::test_retry_and_reader_reject_noncanonical_stored_revision tests/test_tennis_prediction_revisions.py::test_revision_mutations_are_rejected_and_equal_time_is_unambiguous tests/test_tennis_prediction_revisions.py::test_equal_time_retry_checks_all_rows_and_their_hashes tests/test_tennis_prediction_revisions.py::test_equal_time_retry_rejects_a_stored_hash_mismatch tests/test_tennis_prediction_revisions.py::test_equal_time_retry_does_not_choose_between_receipt_histories
```

Ergebnis: `6 passed in 0.87s`.

Finaler A1–A4-/Tennis-Fokus:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r3-final-focus' tests/test_model_artifacts.py tests/test_tennis_state_codec.py tests/test_tennis_tour_state.py tests/test_tennis_tour_readers.py tests/test_tennis_predict.py tests/test_tennis_pending_refresh.py tests/test_tennis_pipeline.py tests/test_tennis_prediction_revisions.py tests/test_tennis_fixture_metadata.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_tab.py tests/test_tennis_side_bets.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py tests/test_quality_worker_integration.py
```

Ergebnis: `394 passed, 7 skipped in 14.14s`, Exit 0.

Einmaliger frischer Gesamtlauf für die exakten R3-Fixbytes:

```text
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -p no:cacheprovider --basetemp '.pytest_tmp/a4-r3-full-final'
```

Ergebnis: `1887 passed, 15 skipped in 64.69s`, Exit 0. `git diff --check` war vor dem Commit Exit 0.

Selbstreview:

- Retry und Reader haben nun denselben gespeicherten Objekt-/Kanon-/Hash-/Modellzeitvertrag; beide Review-Reproduktionen verwenden echte öffentliche Store-/Retry-/Read-Pfade.
- Alle Equal-Time-Zeilen werden vor der ersten möglichen Idempotenzrückgabe geprüft. Normale Receipt-only-Parität bewahrt weiterhin exakt den ersten Receipt.
- Keine Datenmigration, kein stilles Reparieren und kein Guessing zwischen Historien. Keine Provider-, Preis-, Settlement-, Tourmodell- oder andere Taskänderung.
- Controller-eigene PC-/Auditdateien, Review/Ledger und der inhaltlich unveränderte gepinnte Helper blieben außerhalb des engen Fixcommits.
- Ein erneutes unabhängiges Review von `c8935c2` bleibt offen. Reale Build-/Restore-/Release-/Empirie-Gates bleiben unverändert separat offen.
