# Task 4 / A4 - Unabhaengiges Korrektheits- und Vertragsreview

Stand: 8. September 2026. Reviewer: `/root/a4_independent_review`.

## Urteil

**NOT APPROVED: zwei Important-Befunde (R1/P1, R2/P2).** Die Tour-Trennung und die Modellidentitaets-/Cutoff-Seams sind lokal schluessig; die geforderte Absicherung beim Prognose-Append ist noch nicht vollstaendig.

Exakt geprueft:

- BASE `16d9c4e88435017c5841e613b9cd91670313813a`
- HEAD `870224c122beb4763c8eef31268212fe85deb14d`
- Vollstaendige `task-4-brief.md`, `task-4-report.md`, freigegebene Spezifikation `docs/superpowers/specs/2026-09-07-kontextmodell-design.md` und einschlaegige verbindliche Rulings in `progress.md`.
- Software-/Testdiff dieses Bereichs sowie relevante Aufrufer in `wettfinder_automation.py`, `ev_signal_sources.py`, `forecast_evidence.py`, `tennis_tab.py`, `tennis/prediction_revisions.py`, `tennis/workload.py` und die Registry-/Codec-Abhaengigkeiten.

Controller-eigene Aenderungen an Handoff/Audit und das inhaltlich unveraenderte `scripts/stage_runtime_databases.py` sind nicht Teil des Softwareurteils. Keine Produktionsdatei, kein Git-Zustand und kein externes System wurden veraendert. Dieser ignorierte Bericht und isolierte Test-SQLite-Dateien sind die einzigen Review-Artefakte.

## R1 - Important / P1: Reale Append-Zeit fehlt im transaktionalen Startschutz

Anker: `scripts/tennis_daily.py:919-940`, insbesondere `modeled_at=decision_at` in Zeile 938; gemeinsamer Write-Guard `tennis/shadow.py:814-815`.

`main()` erfasst den Entscheidungszeitpunkt vor dem gesamten Scan. `scan_fixtures()` verwendet diesen Zeitpunkt nach beliebig langer Modellberechnung weiterhin fuer jeden Append. Der neue transaktionale Guard vergleicht den Matchbeginn nur mit `modeled_utc`, also mit diesem frueheren fachlichen Cutoff, nicht mit dem realen Zeitpunkt innerhalb der Schreibtransaktion. Ein im Laufe der Berechnung gestartetes Match kann daher als neue Vorstartprognose gespeichert werden. Der Initialscan besitzt nicht einmal den nachgelagerten Zeitcheck des Pending-Pfads. Dessen Check in Zeilen 827-830 ist zudem nur ein Preflight vor einem potentiell wartenden Datenbankzugriff und ersetzt keine Pruefung am Append.

Reproduktion ueber den unveraenderten produktiven Einstieg `daily.main()` mit isolierter Datenbank und kontrollierter Uhr: Entscheidung `2030-01-02T12:00:00Z`, Beginn `12:00:30Z`, die Vorhersage beendet ihre Berechnung um `12:00:31Z`. Beobachtet: Exit 0, **1 Prediction und 1 Revision gespeichert**, obwohl der reale Append nach Beginn liegt. Evidenzdatenbank: `.pytest_tmp/a4-review-clock-ijg828gr/initial.db`.

Erwartung: Kein neuer Append; bisherige Prognosen unveraendert. Die reale, aware Append-/Empfangsuhr muss separat vom fachlichen Modell-Cutoff erhalten bleiben und innerhalb des Schreib-Guards gegen den gueltigen Beginn geprueft werden. Den Modell-Cutoff nicht auf einen kuenftigen Beginn umdatieren. Regression fuer Initialscan und den Pending-Zwischenraum zwischen Preflight und Transaktion erforderlich.

## R2 - Important / P2: Veralteter Pending-Termin dreht einen neueren Reschedule zurueck

Anker: `tennis/shadow.py:940-945` (insbesondere Zeile 944), anschliessend Zeilen 953-965; Aufrufer `scripts/tennis_daily.py:831-836`.

Der Pending-Worker liest Fixture-Metadaten vor der Berechnung. Aktualisiert ein paralleler nativer Scan danach den Termin, liest der neue Write-Guard zwar den nun aktuellen `stored[5]`, bevorzugt aber mit `scheduled_start_utc or stored[5]` immer den alten, vom Worker mitgebrachten Wert. Anschliessend schreibt der vorhandene UPDATE-Block `match_date` und `scheduled_start_utc` mit diesen veralteten Werten zurueck. Es gibt weder einen Vergleich mit dem fuer die Berechnung gelesenen Metadatenstand noch eine zeitliche/versionsgebundene Schreibbedingung.

Reproduktion mit dem normalen Pending-Default `as_of=None`: urspruenglicher Beginn `2030-01-02T18:00:00Z`; der laufende Pending-Worker beginnt um `12:00:00Z`; waehrend `predict_match` schreibt ein anderer Scan um `12:00:01Z` eine native Revision fuer den neuen Beginn `2030-01-03T18:00:00Z`; der alte Pending-Worker beendet um `12:00:02Z`. Beobachtet: `status=complete`, `refreshed=1`; Parent wieder **2030-01-02 / 18:00Z**, neueste immutable Revision dagegen korrekt **2030-01-03 / 18:00Z**. Damit sind aktuelle Fixture-Metadaten und Modellrevision inkonsistent. Parent-Leser wie `pending_predictions()`/`auto_settle_completed()` und `_prediction_price_context()` verwenden weiterhin den Parent-Termin. Evidenz: `.pytest_tmp/a4-review-live-reschedule-u7w8mr01/refresh.db`.

Erwartung: Der veraltete Worker darf den neueren Termin nicht zuruecksetzen und keine auf ueberholten Fixture-Eingaben beruhende Revision als erfolgreichen aktuellen Refresh melden. Im selben Schreibvorgang einen erwarteten Metadaten-/Revisionsstand pruefen und bei zwischenzeitlicher Aenderung konservativ ablehnen beziehungsweise mit belegtem neuen Stand neu berechnen. Keine neue Fetch-Schleife und keine Aenderung von Preis-/Settlement-Regeln erforderlich.

Abgrenzung: Der UPDATE-Block existierte bereits vor A4. Dies ist ein weiterhin offener A4-Reschedule-/Racevertrag; die neue transaktionale Schutznaht liest den aktuellen Termin, prueft ihn aber nicht wirksam. Es wird nicht behauptet, A4 habe den gesamten vorhandenen UPDATE-Block neu eingefuehrt.

## Unabhaengig bestaetigte Teile

- Initial- und Pending-Reader waehlen einmal pro angeforderter Tour; normale Aufrufer bleiben `allow_legacy_model=False`. Fehlende Touren bleiben auch fuer den unveraenderten Wettfinder-Fehlerverbraucher sichtbar, die gesunde Tour laeuft weiter.
- Manifest-Hashpruefung liegt vor dessen Publication-Cutoff-Entscheidung in derselben Lesetransaktion. Wrapper und State pruefen Training, Build und Entscheidung. Der aeussere Artefakthash bleibt erhalten.
- Legacy-Hash stammt aus genau den einmal ueber den Trusted-Handle gelesenen Pickle-Bytes; keine Umkodierung oder Tour-Slot-Erzeugung.
- Modellhash/Build/Tour/Coverage/Training-Cutoff werden in der Context-Evidenz gespeichert. Der bestehende Signal-/Wettfinder-/Forecast-Evidence-Pfad transportiert diese Evidenz; keine neue Quote als Modelleingabe.
- Aenderungen des Artefakts machen auch juengere Pending-Prognosen faellig. Alte Modell- und Preiszeilen werden nicht als aktualisierte Preisbelege ausgegeben.
- Bereits gespeicherte native `started`- und `cancelled`-Beobachtungen sowie Settlement waehrend der Berechnung blockieren den Append innerhalb der Transaktion. Andere Provider mit gleicher Event-ID blockieren nicht falsch. Ein eigener vierteiliger Interleaving-Check bestaetigte: started/cancelled/settled jeweils 0 neue Revisionen; anderer Provider 1 neue Revision. Testartefakte: `.pytest_tmp/a4-review-status-ne1l9bhg/`.
- Statusbeobachtungen bleiben ohne belegten Eintrag unbekannt; aeltere Beobachtungen verdrängen die neueste nicht. Die vorhandenen Fixture-Fetcher geben reale aware Empfangszeiten weiter, keine kuenftigen Kickoffs. Kein zusaetzlicher Providerabruf im Pending-Worker.
- Schema-/Legacy-Revisionsregressionen und Pipeline-Fortsetzung mit Fehler-Exit sind im unabhaengigen Fokuslauf gruen.

## Ausgefuehrte Tests

Arbeitsverzeichnis: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a4-review-focused-20260908' tests/test_model_artifacts.py tests/test_tennis_state_codec.py tests/test_tennis_tour_state.py tests/test_tennis_tour_readers.py tests/test_tennis_predict.py tests/test_tennis_pending_refresh.py tests/test_tennis_pipeline.py tests/test_tennis_prediction_revisions.py tests/test_tennis_fixture_metadata.py tests/test_quality_worker_integration.py
```

Ergebnis: **267 passed, 4 skipped in 9.00s**, Exit 0. Kein unabhaengiger Vollsuite-Claim: `1878 passed, 15 skipped` stammt aus dem Implementierungsbericht. Die zwei oben beschriebenen zusaetzlichen deterministischen Reproduktionen zeigen dennoch die Vertragsverletzungen.

## Reproduktionsskript fuer R1 und R2

Mit demselben Interpreter aus dem Arbeitsverzeichnis ausfuehren, beispielsweise als PowerShell `-c`-Here-String. Alle Datenbanken entstehen in einem neuen Kindverzeichnis unter `.pytest_tmp`. Es gibt keinerlei Netzwerk-, Modellbuild- oder Produktivzugriff; Quellen/Modellberechnung werden fuer das Interleaving ersetzt. Die oeffentlichen Scan-/Store-Pfade bleiben echt.

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sqlite3, tempfile
from scripts import tennis_daily as daily
from tennis import shadow

now = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
root = Path(tempfile.mkdtemp(prefix='a4-review-reproduce-', dir='.pytest_tmp'))
clock = [now.timestamp()]
state = SimpleNamespace(
    tour_scope='ATP', artifact_hash='new', stats_through='2030-01-01',
    stats_through_kind='tournament_start_proxy',
    built_at=(now-timedelta(days=1)).timestamp(),
    training_cutoff=(now-timedelta(days=2)).isoformat(),
)

def prediction(p=.62, digest='old'):
    return SimpleNamespace(
        player_a='Alpha', player_b='Beta', surface='Hard', best_of=3,
        p_a_raw=p, p_a_cal=p, gates=[], verdict='KEINE WETTE',
        recommended_side=None, recommended_edge=0.,
        market_summary=lambda: {'p_a_cal':p, 'p_b_cal':1-p},
        context_evidence={'model_inputs':{'model_artifact_hash':digest}},
    )

# R1: real main(), computation crosses kickoff.
db = root/'initial.db'
start = now+timedelta(seconds=30)
fixture = dict(
    tour='ATP', tournament='Open', player_a='Alpha', player_b='Beta',
    match_date='2030-01-02', fixture_source='ESPN', provider_event_id='123',
    scheduled_start_utc=start.isoformat(), surface='Hard', indoor=False,
)

def slow_prediction(*args, **kwargs):
    clock[0] = (start+timedelta(seconds=1)).timestamp()
    return prediction(.62, 'new')

with patch.object(shadow, 'DB_PATH', db), \
     patch.object(daily, 'auto_settle_completed', return_value=0), \
     patch.object(daily, 'tournament_surface_map', return_value={}), \
     patch.object(daily, 'fetch_fixtures', return_value=[fixture]), \
     patch.object(daily, 'load_tour_state', return_value=state), \
     patch.object(daily, 'predict_match', side_effect=slow_prediction), \
     patch.object(daily.time, 'time', side_effect=lambda: clock[0]), \
     patch('sys.argv', ['tennis_daily.py', '2030-01-02']):
    code = daily.main()
with sqlite3.connect(db) as conn:
    print('R1', code, conn.execute('SELECT COUNT(*) FROM predictions').fetchone())
# Current output: R1 0 (1,); expected no prediction after actual start.

# R2: normal as_of=None worker overlaps a newer native reschedule.
db = root/'reschedule.db'
clock[0] = now.timestamp()
old_start = now+timedelta(hours=6)
new_start = old_start+timedelta(days=1)

def store(pred, when, start):
    return shadow.store_prediction(
        start.date().isoformat(), 'ATP', 'Open', pred,
        fixture_source='ESPN', provider_event_id='123',
        scheduled_start_utc=start.isoformat(), modeled_at=when, db_path=db,
    )

store(prediction(), now-timedelta(hours=3), old_start)

def concurrent_reschedule(*args, **kwargs):
    clock[0] = (now+timedelta(seconds=1)).timestamp()
    store(prediction(.66, 'new'), datetime.fromtimestamp(clock[0], timezone.utc), new_start)
    clock[0] = (now+timedelta(seconds=2)).timestamp()
    return prediction(.57, 'new')

with patch.object(daily.time, 'time', side_effect=lambda: clock[0]), \
     patch.object(daily, 'load_tour_state', return_value=state), \
     patch.object(daily, 'predict_match', side_effect=concurrent_reschedule):
    result = daily.refresh_pending_predictions(db_path=db)
with sqlite3.connect(db) as conn:
    parent = conn.execute('SELECT match_date,scheduled_start_utc FROM predictions').fetchone()
latest = shadow.latest_predictions(db, as_of=now+timedelta(seconds=2))[0]
print('R2', result['status'], result['refreshed'], parent, latest['scheduled_start_utc'])
# Current: complete 1 ('2030-01-02', '2030-01-02T18:00:00+00:00')
#          2030-01-03T18:00:00+00:00
# Expected: stale refresh rejected; parent retains the Jan 3 reschedule.
print(root.resolve())
```

## Daten- und Releasegrenzen

Dieses Review macht keinerlei aktuelle Aussage ueber ATP-/WTA-Quellenverfuegbarkeit und hat keine Provider-, Netzwerk-, VPS-, Push- oder Deploy-Operation ausgefuehrt. Die im Implementierungsbericht datierten Quellbefunde wurden nicht live erneut verifiziert. Reale getrennte Builds, Publication, echter Scan/Pending-Lauf, Runtime-Root, D4-Backup/Restore, D5-Release/Hash/Timer, empirische Abnahme und Aktivierung bleiben gesonderte offene Gates. Grüne synthetische Tests ersetzen keinen dieser Nachweise.

Nach R1/R2-Fix sind gezielte RED/GREEN-Nachweise, unabhaengiges Re-Review und eine frische Regression fuer den dann exakten Commit erforderlich.

## Re-Review der Korrektur 156ba46 - 8. September 2026

**Aktuelles Urteil: NOT APPROVED. R1 und R2 sind ADDRESSED; ein neuer Important-Befund R3/P2 verbleibt in der ergaenzten Receipt-Idempotenzpruefung.**

Exakter Re-Review-Bereich: `870224c122beb4763c8eef31268212fe85deb14d` bis `156ba46a610f690ff792b1bee752ba3692d11dff`. HEAD wurde vor dem Review auf den zweiten SHA aufgeloest. Vollstaendig gelesen: neue Korrektursektion in `task-4-report.md`, bisheriger eigener Bericht, kompletter Fixdiff aller sechs Dateien. Kein produktiver Source-Edit, Git-Eingriff, Netzwerk-, Provider- oder VPS-Zugriff; keine Unteragenten.

### R1: ADDRESSED

`tennis/shadow.py:951-952` erwirbt zuerst `BEGIN IMMEDIATE`; `1010-1021` beziehungsweise `1050-1059` lesen danach die separate aware Append-Uhr und pruefen sie im Write-Guard. `modeled_at` bleibt der fachliche Cutoff. `main()` und der normale Wettfinder-Aufruf setzen den expliziten Offline-Receipt nicht.

Das oben gespeicherte originale Reproduktionsskript wurde unveraendert erneut ausgefuehrt. Ergebnis R1 jetzt: `R1 0 (0,)`, also keine verspätete Prediction. Zusaetzlich wurde ueber den oeffentlichen `shadow.store_prediction`-Pfad ein echter SQLite-Schreiblock in einer zweiten Verbindung gehalten. Der Worker erreichte nachweislich sein blockiertes `BEGIN IMMEDIATE`; erst dann wurde die kontrollierte Uhr von vor Beginn auf Beginn+1s gesetzt und die Sperre freigegeben. Ergebnis: `FixtureNotRefreshable: tennis prediction append must precede match start`, weiter genau eine urspruengliche Revision. Evidenz: `.pytest_tmp/a4-rereview-real-lock-tal15sps/locked.db`.

### R2: ADDRESSED

`scripts/tennis_daily.py:838-840` uebergibt die gelesene Modellrevision sowie Matchdatum und Start als erwarteten Snapshot. `tennis/shadow.py:841-877` vergleicht diese Werte nach der Schreibsperre; der Aufruf erfolgt vor Parent-Update und Append in `1001-1009`.

Das originale R2-Skript liefert jetzt `R2 complete 0 ('2030-01-03', '2030-01-03T18:00:00+00:00') 2030-01-03T18:00:00+00:00`: stale Refresh uebersprungen, neuer Parent-Termin und neueste Revision konsistent. Original-Reproduktionsartefakte dieses Re-Runs: `.pytest_tmp/a4-review-reproduce-m80g2_x0/`.

Weitere eigene Interleaving-Pruefungen ueber den oeffentlichen Pending-/Store-Pfad:

- Neue Modellrevision bei unveraendertem Start: alter Pending-Worker wird uebersprungen; genau zwei vorhandene Revisionen bleiben.
- Nur Preise zwischenzeitlich geaendert: Pending-Append bleibt erlaubt, neue Preise bleiben erhalten; Preise sind nicht Teil des Snapshot-CAS.
- Gueltige Legacy-Zeile ohne Revisionstabelle: erwartete Revision `None` migriert weiterhin erfolgreich mit eingefrorener Baseline und neuer Revision.

Alle drei Faelle bestanden. Evidenz: `.pytest_tmp/a4-rereview-cas-sx_8ndza/`.

### R3 - Important / P2: Idempotenter Retry akzeptiert einen fuer den Leser ungueltigen gespeicherten Payload

Anker: `tennis/prediction_revisions.py:91-102`, insbesondere Zeilen 92 und 95; `_modeled_identity` in Zeilen 55-58. Zugehoeriger Leser: `read_latest_predictions`, Zeilen 198-201.

Der neue Retry-Branch prueft den Digest ueber den **rohen gespeicherten JSON-String**, waehrend der Leser den Digest ueber `_canonical(json.loads(payload_json))` prueft. Danach normalisiert `_modeled_identity` den gespeicherten Inhalt unbesehen mit `dict(payload)`. Dadurch akzeptiert der Retry sowohl ein nichtkanonisch serialisiertes Objekt mit dazu passend berechnetem Raw-Hash als auch ein JSON-Array aus Schluessel/Wert-Paaren. Im zweiten Fall wird das Array still in ein Modellobjekt umgewandelt. Der oeffentliche Store meldet in beiden Faellen erfolgreichen idempotenten Abschluss (`-1`), obwohl `latest_predictions` dieselbe eine gespeicherte Zeile anschliessend nicht lesen kann.

Reproduzierte Ausgaben mit jeweils genau einer Equal-Time-Zeile und einem zu ihren Rohbytes passenden Digest:

```text
noncanonical-object: public_retry_result=-1
                     public_reader_result=ValueError: tennis model revision content mismatch
pairs-array:         public_retry_result=-1
                     public_reader_result=TypeError: list indices must be integers or slices, not str
```

Evidenzdatenbanken: `.pytest_tmp/a4-rereview-stored-shape-pc6n_xw3/`. Dies ist eine isolierte Korruptions-/Migrationspruefung, kein behaupteter Produktionsschaden. Der Befund liegt in der neu erweiterten Integritaetsentscheidung: ein bereits ungueltiger gespeicherter Zustand darf nicht durch semantische Normalisierung als gueltiger Retry bestaetigt werden. Der alte direkte Identitaetsvergleich haette einen solchen vom kanonischen Payload abweichenden Digest nicht akzeptiert.

Erwartung: Vor idempotenter Rueckgabe fuer jede Equal-Time-Zeile denselben gespeicherten Objekt-/Kanonisierungs-/Hashvertrag wie beim Leser anwenden. Ein Top-Level-Array bleibt ungueltig; nichtkanonische/mehrdeutige gespeicherte Bytes duerfen nicht still repariert beziehungsweise als lesbare Modellrevision bestaetigt werden. Erst danach darf ausschliesslich `append_observed_at` aus dem Vergleich der Modellidentitaet entfernt werden. Erster Receipt, Legacy-Identitaet, vollstaendige Hashpruefung und Ablehnung mehrerer Receipt-Historien bleiben erhalten.

Minimaler oeffentlicher Reproducer, mit demselben Testinterpreter im Worktree als `-c`-Here-String ausfuehrbar:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sqlite3, tempfile, json, hashlib
from tennis import shadow
from tennis.prediction_revisions import REVISION_SCHEMA

now = datetime(2030, 1, 2, 12, tzinfo=timezone.utc)
start = now + timedelta(hours=6)
root = Path(tempfile.mkdtemp(prefix='a4-rereview-r3-', dir='.pytest_tmp'))

def prediction():
    return SimpleNamespace(
        player_a='Alpha', player_b='Beta', surface='Hard', best_of=3,
        p_a_raw=.62, p_a_cal=.62, gates=[], verdict='KEINE WETTE',
        recommended_side=None, recommended_edge=0.,
        market_summary=lambda: {'p_a_cal':.62, 'p_b_cal':.38},
        context_evidence={'model_inputs':{'model_artifact_hash':'new'}},
    )

for scenario in ('noncanonical-object', 'pairs-array'):
    db = root / (scenario + '.db')

    def store(receipt):
        return shadow.store_prediction(
            '2030-01-02', 'ATP', 'Open', prediction(),
            fixture_source='ESPN', provider_event_id='123',
            scheduled_start_utc=start.isoformat(), modeled_at=now,
            append_observed_at=receipt, db_path=db,
        )

    prediction_id = store(now)
    with sqlite3.connect(db) as conn:
        original = json.loads(conn.execute(
            'SELECT payload_json FROM prediction_revisions'
        ).fetchone()[0])
        serialized = (
            json.dumps(original, indent=2, ensure_ascii=False)
            if scenario == 'noncanonical-object'
            else json.dumps(list(original.items()), ensure_ascii=False,
                            separators=(',', ':'))
        )
        digest = hashlib.sha256(
            f'{prediction_id}\n{serialized}'.encode('utf-8')
        ).hexdigest()
        # Replace only this isolated fixture's revision table with one bad row.
        conn.executescript('DROP TABLE prediction_revisions;' + REVISION_SCHEMA)
        conn.execute('INSERT INTO prediction_revisions VALUES (?,?,?,?)',
                     (digest, prediction_id, now.timestamp(), serialized))
    print(scenario, 'retry=', store(now + timedelta(seconds=1)))
    try:
        shadow.latest_predictions(db, as_of=now + timedelta(seconds=2))
    except Exception as exc:
        print(type(exc).__name__, str(exc))
print(root.resolve())
```

### Frischer Testnachweis fuer 156ba46

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a4-rereview-156ba46-focus-01' tests/test_tennis_tour_readers.py tests/test_tennis_pending_refresh.py tests/test_tennis_prediction_revisions.py tests/test_tennis_fixture_metadata.py tests/test_quality_worker_integration.py tests/test_model_artifacts.py tests/test_tennis_state_codec.py tests/test_tennis_tour_state.py tests/test_tennis_predict.py tests/test_tennis_pipeline.py
```

Ergebnis: **274 passed, 4 skipped in 9.19s**, Exit 0. Die vorhandenen Equal-Time-/Hash-/Receipt-Tests sind darin enthalten. R3 stammt aus der zusaetzlichen unabhaengigen Reproduktion und wird durch diesen gruenen Fokus nicht widerlegt. Der volle Lauf `1885 passed, 15 skipped` bleibt ein Nachweis des Implementers, nicht dieses Re-Reviews.

Fazit: R1/R2-Korrektur technisch bestaetigt. Vor Softwarefreigabe ist R3 zu korrigieren und erneut unabhaengig zu pruefen. Alle zuvor genannten realen Daten-, Empirie-, Backup-/Restore- und Release-Gates bleiben unveraendert separat offen.

## Enges R3-Abschlussreview c8935c2 - 8. September 2026

**Aktuelles Softwareurteil: APPROVED. R1, R2 und R3 sind ADDRESSED; keine verbleibenden Findings im geprueften A4-Softwarestand.** Dieses Urteil ersetzt die obigen historischen NOT-APPROVED-Zwischenstaende, nicht die weiterhin offenen Daten-/Release-Gates.

Exakt gepruefter Fixbereich: `156ba46a610f690ff792b1bee752ba3692d11dff` bis **`c8935c22af0d4a5e5e03a575be8eb1b5d3f1dc40`**. Der Bereich enthaelt ausschliesslich `tennis/prediction_revisions.py` und `tests/test_tennis_prediction_revisions.py`. Vollstaendig gelesen wurden die neue R3-Sektion im Implementierungsbericht, der gesamte enge Fixdiff und das resultierende Revisionsmodul. HEAD blieb beim abschliessenden Check exakt der genannte SHA.

### R3: ADDRESSED

- `_modeled_identity` akzeptiert ausschliesslich ein echtes Objekt und kopiert es; keine Array-/Mapping-Normalisierung mittels `dict(payload)` mehr.
- Retry und Reader verwenden denselben `_decode_stored_revision`-Pfad. Dieser verlangt JSON-Objektform, verwirft doppelte Schluessel auch in verschachtelten Objekten sowie nicht-finite Zahlen und verlangt exakte kanonische Textform. Erst deren exakte UTF-8-Bytes bilden den gespeicherten Digestvertrag.
- Im Retry werden saemtliche Equal-Time-Zeilen vor einer moeglichen idempotenten Rueckgabe auf gespeicherten Hash, Objekt-/Kanonvertrag und `payload.created_utc == stored modeled_utc` geprueft. Der Reader verwendet denselben Text-/Hash-/Modellzeitvertrag.
- Ausschliesslich `append_observed_at` wird aus dem fachlichen Modellvergleich genommen. Gueltige Receipt-only-Retries behalten die erste Revision samt Original-Receipt. Ein gueltiger Legacy-Payload ohne dieses Feld bleibt bytegleich ohne erfundenen nachtraeglichen Receipt.

### Eigene oeffentliche Store-/Reader-Pruefungen

Beide urspruenglichen R3-Repros wurden in neuen isolierten Datenbanken erneut ausgefuehrt: nichtkanonisches Objekt und Top-Level-Paararray. Beide werden nun **sowohl vom oeffentlichen Receipt-only-Store als auch von `shadow.latest_predictions` mit `ValueError: tennis model revision content mismatch` abgelehnt**; keine Zeile wird repariert oder ersetzt.

Zusaetzlich bestaetigt wurden sieben weitere Ablehnungsfaelle mit exakt zu den absichtlich eingesetzten Testbytes berechnetem Hash, soweit nicht der Hash selbst Testgegenstand war: doppelter Schluessel, verschachtelter doppelter Schluessel, `NaN`, `Infinity`, Zahlenueberlauf `1e309`, abweichende Payload-Modellzeit und falscher gespeicherter Hash. In allen neun Korruptionsfaellen blieben die gespeicherten Revisionstupel vor/nach Store- und Reader-Aufruf exakt identisch.

Zwei positive Paritaetsfaelle prueften je zwei spaetere Receipt-only-Retries: normale Revision mit Receipt sowie gueltige Legacy-Revision ohne Receipt. Beide lieferten jeweils `-1`, blieben oeffentlich lesbar und behielten exakt ihre urspruenglichen Revisionstupel; der erste Receipt beziehungsweise dessen belegte Abwesenheit blieb unveraendert.

Isolierte Evidenz: `.pytest_tmp/a4-r3-independent-integrity-zmqcvljn/` (neun negative und zwei positive Fall-Datenbanken). Keine produktiven Daten und kein Netzwerk wurden benutzt.

### Frischer fokussierter Regressionsnachweis

```powershell
& 'C:\Projekt\BetBoy\betboy-app\.codex_test_venv\quality\Scripts\python.exe' -m pytest -q -p no:cacheprovider --basetemp '.pytest_tmp/a4-r3-independent-focus-01' tests/test_tennis_prediction_revisions.py tests/test_tennis_pending_refresh.py tests/test_tennis_tour_readers.py tests/test_tennis_fixture_metadata.py tests/test_quality_worker_integration.py
```

Ergebnis: **132 passed in 6.65s**, Exit 0, keine Skips. Enthalten sind normale Receipt-only-Paritaet, alle vorhandenen Equal-Time-Hash-/Konflikt-/Mehrfachreceipt-Pruefungen, die Initial-/Pending-Start-R1-Regressionen, R2-Reschedule-CAS sowie die oeffentlichen Reader-/Worker-Integrationstests. Die zuvor unabhaengig bestaetigte reale SQLite-Lock-Reproduktion bleibt gueltig; die R3-Korrektur aendert diese Schreib-/CAS-Dateien nicht.

Die Implementer-Nachweise `394 passed, 7 skipped` und voller Lauf `1887 passed, 15 skipped` wurden aus der vollstaendig gelesenen R3-Berichtsektion entnommen; sie werden nicht als eigene Vollsuite-Laeufe dieses engen Reviews ausgegeben.

### Abschluss und Grenzen

Keine neuen Critical-/Important-/Minor-Befunde und keine notwendige Scope-Erweiterung festgestellt. Keine Source-, Git-, Provider-, VPS- oder anderen Produktivmutationen; nur dieser ignorierte Bericht und isolierte Testartefakte wurden ergaenzt. Controller-eigene Handoff-/Auditdateien und der gepinnte Staging-Helper blieben unberuehrt.

Die Freigabe gilt fuer die lokale A4-Software auf dem oben vollstaendig angegebenen SHA. Sie ist **kein** Nachweis eines echten getrennten ATP-/WTA-Builds, Live-Publishs/-Scans, Backup-/Restore-Erfolgs, empirischen Wirkungsnachweises, Pushs oder einer VPS-/Produktivaktivierung. Diese Gates bleiben separat durch den Controller zu belegen.
