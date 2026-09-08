# A3 Real-data Admission: unabhaengiges Review

Stand: 2026-09-08. Ergebnis: **keine verbleibenden Findings; Softwarefreigabe fuer exakt `2436dd411987ba0b543fd73212da6cbb72d65e99`** innerhalb des engen A3-Reparaturvertrags. Kein Produktions-, Empirie- oder D4-Abschluss.

## Eingefrorener Bereich

- Basis: `6031e31a574aecd55f3d1efe7baddada2b6115f8`.
- Erster Fix: `fa98a3e4d107a44746391349b20225263b15e49c`.
- Abschliessender Folgecommit: `2436dd411987ba0b543fd73212da6cbb72d65e99`.
- Beide vollstaendigen Commit-Diffs gelesen, nicht wechselnde Worktree-Diffs als Ersatz. Gesamtscope: `tennis/serve_model.py`, `tennis/tour_state.py`, `tennis/backtest.py`, `scripts/rebuild_state.py` und die drei Tests `test_serve_admission.py`, `test_tennis_tour_state.py`, `test_tennis_training_refresh.py`.
- Diagnosebericht, abschliessender Fixbericht und oberster Progress-Ruling vollstaendig im verlangten Umfang gelesen. Der anfangs falsche volle fa98-Hash im Fixbericht wurde vor Abschluss auf den tatsaechlichen Hash korrigiert; beide finalen Commit-Identitaeten stimmen.
- Vor und nach den Tests stimmten getrackte Source-/Testdateien mit dem finalen Commit ueberein. Nur controller-eigene `progress.md` und `context-contract-decisions.md` differierten. `git diff --check BASE HEAD` war sauber. Der gepinnte Staginghelper wurde nicht veraendert.

## Vertrag und konkrete Codeanker

1. **Bilaterale Admission vor Snapshots/Mutation:** `tennis/serve_model.py:364-380` ruft zuerst genau einen owning Validator auf; bei Ablehnung wird der alte Updater nicht betreten. Damit liegen auch dessen beide vorherigen Gegner-Snapshots hinter der Admission. `:616-650` prueft alle sechs benoetigten Counts: echte numerische Werte, keine Booleans/Strings, endlich, nichtnegativ, ganzzahlig, vier positive Game-Denominatoren sowie beide eigenen Return-/gegnerischen Service-Grenzen fuer Breaks. Keine Rundung, kein Clipping und keine neue reziproke Game-Gleichheitsregel.

2. **Gleiche Berechnung fuer gueltige Beobachtungen:** Der bestehende `update_from_match_row` samt Opponent-Snapshots, `_add_player`, Decay, Priors und Payload-Validator blieb unveraendert. Der neue Pfad delegiert einmal mit demselben `match_date`. Der Fix schwaecht weder Codec noch Endinvarianten ab.

3. **Eng begrenzte Aktivierung und Elo-Erhalt:** `tennis/tour_state.py:96-111` aktualisiert Elo unabhaengig vom Serve-Ergebnis, laesst die Ergebniszeile in `consumed` und uebergibt denselben Admissionvertrag an die Kalibration. `tennis/backtest.py:531-533`, `:611-619`, `:630-638` aktivieren ihn ausschliesslich bei `calibration_only=True`; beide Defaultzweige behalten ihren alten Updater. Kalibrationsjahre, kausale Pointer/Datumsgrenzen, Preis-Allowlist, Loss-/Rundungsregeln und Legacy-Combined-Aufruf wurden durch diese beiden Commits nicht geaendert.

4. **Eindeutige, nicht persistierte Diagnostik:** `tennis/serve_model.py:106-188` trennt Zeilen, distinct native `id`-Matches und distinct `tournament_id`-Turniere; beide Unknown-Zaehler und die Jahresprovenienz bleiben getrennt. Wiederholte Zeilen bleiben Zeilen, nicht neue Identitaeten. Der Follow-up weist Bruchzahlen mit `fractional_count` aus. Die Diagnostik wird in caller-owned Dictionaries gespiegelt und gelangt nicht in Modell-/Manifest-/Codec-Schemata.

5. **CLI und Ausnahmen:** `scripts/rebuild_state.py:26-37`, `:52-78` druckt getrennte kompakte Build-/Calibration-Diagnostik und behaelt Refreshstatus/Exitregeln. Originale Build-/Updater-Ausnahmen werden nicht durch eine pauschale Admission-Ausnahme ersetzt. Bestehende Partial-/Failed-Tourregeln bleiben bestehen.

## Eigene Ausfuehrungsnachweise

Fokussierter Lauf erst nach dem finalen Folgehash, mit eigenem frischem Basetemp:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a3-realdata-independent-final-20260908-01' tests/test_serve_admission.py tests/test_serve_decay.py tests/test_serve_indoor.py tests/test_tennis_model.py tests/test_tennis_backtest_policy.py tests/test_tennis_tour_state.py tests/test_tennis_training_refresh.py tests/test_tennis_training_cache.py tests/test_tennis_state_codec.py tests/test_tennis_pipeline.py
```

**239 passed, 3 skipped in 6.71s; Exit 0.** Die Vollsuite mit 1904 passed / 15 skipped / 97 subtests ist separat im Implementerbericht dokumentiert und wurde in diesem engen Review nicht erneut ausgefuehrt.

Zusaetzliche eigene In-memory-Reproduktionen ohne Source-/Fixturedatei-Aenderungen:

- **62 Ablehnungsfaelle** auf bereits befuelltem Modell. Alle sechs Counts jeweils mit None, String, Python-/NumPy-Boolean, NaN, Infinity, negativem Wert, `Fraction(1, 3)` und `math.nextafter(1.0, 2.0)`; dazu Null-Denominatoren und vier gezielte Break-/Game-Grenzen. `hold_and_break` war fuer jeden Fall auf eine sofortige Assertion gepatcht: keine Gegner-Snapshots, keine halbe Mutation, keine Aenderung bestehender Akkumulatorwerte oder `last_date`; der gesamte vorherige Payload blieb exakt gleich. Stabile Ablehnungsgruende bestaetigt.
- **Vier gueltige Folgeupdates** mit zeitlichem Abstand/Decay, Hard-Outdoor, Hard-Indoor und Clay: nach jedem Update exakte Payloadgleichheit zum alten Pfad. Die letzte Zeile hatte positive, nicht reziprok gleiche Game-Denominatoren, aber gueltige Break-Grenzen: keine unfreigegebene zusaetzliche Symmetrieregel.
- **Native Identitaeten:** fuenf angenommene Zeilen mit Duplikat, zwei weiteren nativen Match-IDs und jeweils unabhaengig fehlender Match-/Turnieridentitaet ergaben 5 Zeilen / 3 bekannte Matches / 1 bekanntes Turnier. Zwei Ablehnungen derselben nativen Match-ID ergaben 2 Zeilen / 1 Match / 1 Turnier; alle Unknown-/Skipmaps stimmten.
- **Originalexception:** ein gepatchter gueltiger Updater warf ein konkretes `RuntimeError`-Objekt; exakt dasselbe Objekt erreichte den Aufrufer.
- **Echter Builder mit isolierten In-memory-Loaderseams:** zwei gueltige Ergebniszeilen versus identische Ergebnisse mit einer fehlerhaften Serve-Zeile ergaben exakt gleiche vollstaendige Elo-Payloads und je zwei Matches, gleiche Ergebnis-Coverage `2026-03-09`, aber nur den gueltigen Serve-Beitrag und Diagnostik 1 admitted / 1 skipped. Die Eingabe verwendete die wirkliche `series_category_id`-Naht.

Kompakte Ausgabe des erfolgreichen Grenzlaufs:

```text
invalid_cases_no_snapshots_no_mutation=62
valid_sequence_exact_legacy_parity=4
native_identity_counts=ok
original_exception_identity=ok
valid_elo_and_coverage_retained=ok
```

Zwei anfaengliche eigene Probeannahmen wurden ausschliesslich im Speicher korrigiert: ein falsch benannter synthetischer Kategorien-Key und die Annahme, der Registryhash sei der nackte gespeicherte BLOB-Hash. Das waren keine Produktbefunde. Fuer den anschliessenden Registrycheck wurden die bestehenden owning Hashpruefer auf einer bereits `mode=ro`/`query_only` geoeffneten Verbindung benutzt; kein schemaerzeugender oeffentlicher Reader auf der Original-DB.

## Echter Build: belegte Daten und Grenzen

Den aktualisierten Bericht ueber den frischen Offline-Build unter `.pytest_tmp/tour-offline-realdata-fix-20260908-02` gelesen. Seine Admissionpopulation ist klar offengelegt:

- ATP Build: 63,477 admitted / 1,133 skipped Matches; 1,045 / 38 Turniere; 884 Null-/unbrauchbare Game-Denominatoren und 249 nonfinite Counts.
- ATP Calibration: 57,195 / 1,014 Matches; 942 / 28 Turniere; 884 Denominator- und 130 nonfinite Faelle.
- WTA bleibt Elo-only, beide Serve-Diagnostiken 0/0. Unknown-Provenienz im dokumentierten realen Lauf 0. Kein behaupteter Empiriegewinn; Abdeckung und Turnierstart-Proxy werden ausdruecklich genannt.

Diese Admissiongesamtzahlen stammen aus dem Implementer-/Controller-Buildbericht, nicht aus einem von mir wiederholten Vollbuild. Zusaetzlich habe ich die tatsaechliche neue isolierte SQLite-DB read-only in einer Lesetransaktion geprueft: `quick_check=ok`, keine Foreign-Key-Verletzung, aktiver Manifesthash und beide Artifacthashes durch die bestehenden owning Pruefer gueltig. Die gespeicherten Werte stimmen mit dem Bericht:

- Manifest: `5b9cda7ea2ecd127b38ace93b0c315306dec4a9d7c84442791bc1f688e36aaeb`.
- ATP: `ad3e452ac0c77b752336a38cacecfaac935cce084a9db109d52c33b679435b0f`; Coverage `2026-07-27` / `tournament_start_proxy`; 8,127 Serve-Zeilen und 7,770 Calibration-Samples.
- WTA: `d43315e055a0824c277d90596c4b19049ea071157b371f332a85f1940c8b6a4f`; Coverage `2026-07-26` / `result_date`; 0 Serve-Zeilen und 7,025 WTA-Calibration-Samples.

Die Source-/Build-/Publikationsuhren wurden nicht umgeschrieben. Keine Netzwerk-/Provider-/VPS-/Git-Mutations-/Deployment-Aktion, kein Sourcefix und kein Unteragent in diesem Review. Nur dieser Bericht wurde als beauftragtes Ergebnis geschrieben; Tests nutzten ihren eigenen temporaeren QA-Baum.

**Verbleibende Gates:** spaetere empirische Akzeptanz der veraenderten ATP-Serve-Trainingspopulation, echte aktuelle Providerfrische, separat ausgefuehrtes Linux-Tour-Backup/Restore, releasegenaue Produktionsverifikation und spaeter vollstaendiges D4 bleiben unabhaengig offen. Diese Softwarefreigabe erlaubt keine Ausweitung darauf.
