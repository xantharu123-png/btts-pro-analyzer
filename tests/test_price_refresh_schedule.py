"""Scheduled observations never regenerate or reorder sporting forecasts."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from config_loader import AppConfig
import wettfinder_automation as automation
from test_shared_quote_observations import _tennis_price_fixture
from test_wettfinder_surface import NOW, _signal, _quote
from wettfinder_surface import wettfinder_quote_binding_candidate


def _state(tmp_path, rows):
    path = tmp_path / "wettfinder.json"
    document = dict(generated_at=(NOW-timedelta(hours=1)).isoformat(),
                    model_candidates=rows, candidates=deepcopy(rows),
                    challenge_release_candidates=deepcopy(rows),
                    football={"last_discovery_at": "unchanged"}, sources={})
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, deepcopy(document)


def _football():
    signal = _signal()
    row = {**automation._signal_record(signal), **wettfinder_quote_binding_candidate(signal),
           "status": "MODEL_SELECTION"}
    return row, _quote(signal)


@pytest.mark.parametrize('failed', [False, True])
def test_price_refresh_hands_received_quotes_to_evidence_without_model_run(tmp_path, monkeypatch, failed):
    row, quote = _football()
    path, original = _state(tmp_path, [row])
    seen = []
    def capture(document, *, db_path, model_version):
        seen.append((document['generated_at'], document['model_candidates'][0]['reference_quote'], db_path))
        if failed:
            raise ValueError('not-for-publication')
        return {'status': 'completed', 'recorded': 3, 'rejected': 0}
    monkeypatch.setattr('forecast_evidence.record_current_closing_quotes', capture)
    monkeypatch.setattr(automation, 'run_wettfinder', lambda **kw: pytest.fail('model run'))
    evidence_path = tmp_path/'evidence.db'
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        quote_loader=lambda *args, **kw: ({quote.candidate_id: quote}, []), evidence_db_path=evidence_path)
    assert len(seen) == 1
    assert seen[0][0] == original['generated_at']
    assert seen[0][1] is not None
    assert seen[0][2] == evidence_path
    assert result['closing_evidence']['status'] == ('failed' if failed else 'completed')
    assert int(result.get('operational_errors', 0)) == int(failed)
    assert json.loads(path.read_text())['generated_at'] == original['generated_at']
    assert 'not-for-publication' not in path.read_text()


def _native_loaders(monkeypatch, football, tennis, *, outcome="quotes"):
    calls = []
    def receive(sport, quote, rows, kwargs):
        calls.append((sport, deepcopy(rows)))
        if outcome == "failure":
            raise RuntimeError("credential-not-for-publication")
        if outcome == "empty":
            return {}, []
        for row in rows:
            kwargs["diagnostics"][row["candidate_id"]] = {
                "reason_code": "OBSERVED", "fetched_at": NOW.isoformat()}
        return {quote.candidate_id: quote} if quote else {}, []
    monkeypatch.setattr(automation, "fetch_football_consensus",
        lambda key, rows, **kwargs: receive("football", football, rows, kwargs))
    monkeypatch.setattr(automation, "fetch_tennis_h2h_consensus",
        lambda key, rows, **kwargs: receive("tennis", tennis, rows, kwargs))
    return calls


@pytest.mark.parametrize("outcome", ["quotes", "empty", "failure"])
def test_scheduled_all_refresh_throttles_every_attempt_without_model_changes(tmp_path, monkeypatch, outcome):
    football, fq = _football()
    _, tennis, tq = _tennis_price_fixture()
    start = (NOW+timedelta(hours=8)).isoformat()
    football['scheduled_start'] = tennis['scheduled_start'] = start
    fq, tq = replace(fq, scheduled_start=start), replace(tq, scheduled_start=start)
    path, original = _state(tmp_path, [football, tennis])
    calls = _native_loaders(monkeypatch, fq, tq, outcome=outcome)
    monkeypatch.setattr(automation, "run_wettfinder", lambda **kw: pytest.fail("model run"))
    config = AppConfig(api_football_key="fixture", odds_api_key="fixture")
    first = automation.refresh_prices_only(state_path=path, now=NOW, config=config, quote_sport="all")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert [sport for sport, rows in calls] == ["football", "tennis"]
    assert first["checked"] == 2
    assert first["operational_errors"] == (2 if outcome == "failure" else 0)
    assert after["generated_at"] == original["generated_at"]
    assert after["football"] == original["football"]
    assert [r["key"] for r in after["model_candidates"]] == [football["key"], tennis["key"]]
    for before, row in zip(original["model_candidates"], after["model_candidates"]):
        for field, value in before.items():
            if not field.startswith(("reference_", "quote_")):
                assert row[field] == value
    assert after["candidates"] == after["challenge_release_candidates"] == []
    assert "credential-not-for-publication" not in path.read_text(encoding="utf-8")
    automation.refresh_prices_only(state_path=path, now=NOW+timedelta(minutes=179),
                                   config=config, quote_sport="all")
    assert len(calls) == 2  # Empty/failure is a real attempt too.
    automation.refresh_prices_only(state_path=path, now=NOW+timedelta(hours=3),
                                   config=config, quote_sport="all")
    assert len(calls) == 4


def test_scheduled_empty_catalog_never_calls_any_provider(tmp_path, monkeypatch):
    path, original = _state(tmp_path, [])
    def forbidden(*args, **kwargs):
        pytest.fail("empty catalog must not request provider")
    monkeypatch.setattr(automation, "fetch_football_consensus", forbidden)
    monkeypatch.setattr(automation, "fetch_tennis_h2h_consensus", forbidden)
    monkeypatch.setattr("team_sport_prices.refresh_team_sport_prices", forbidden)
    monkeypatch.setattr("esports_prices.refresh_esports_prices", forbidden)
    result = automation.refresh_prices_only(state_path=path, now=NOW, config=AppConfig(), quote_sport="all")
    assert result["checked"] == result["errors"] == 0


def test_scheduled_refresh_does_not_overwrite_concurrent_snapshot(tmp_path, monkeypatch):
    row, quote = _football()
    path, _ = _state(tmp_path, [row])
    def changed(*args, **kwargs):
        path.write_text('{"newer":true}', encoding="utf-8")
        return {}, []
    monkeypatch.setattr(automation, "fetch_football_consensus", changed)
    with pytest.raises(RuntimeError, match="snapshot changed"):
        automation.refresh_prices_only(state_path=path, now=NOW,
            config=AppConfig(api_football_key="fixture"), quote_sport="all")
    assert json.loads(path.read_text()) == {"newer": True}


@pytest.mark.parametrize("busy_check", [1, 2])
def test_scheduled_canonical_refresh_checks_daily_worker_before_fetch_and_publish(tmp_path, monkeypatch, busy_check):
    import subprocess
    row, quote = _football()
    path, _ = _state(tmp_path, [row])
    original = path.read_bytes()
    monkeypatch.setattr(automation, "STATE_PATH", path)
    checks, calls = [], []
    def state(*args, **kwargs):
        checks.append(True)
        return SimpleNamespace(stdout="active" if len(checks) == busy_check else "inactive")
    monkeypatch.setattr(subprocess, "run", state)
    monkeypatch.setattr(automation, "fetch_football_consensus", lambda *a, **k: calls.append(True) or ({}, []))
    with pytest.raises(RuntimeError, match="must be idle"):
        automation.refresh_prices_only(state_path=path, now=NOW,
            config=AppConfig(api_football_key="fixture"), quote_sport="all")
    assert path.read_bytes() == original
    assert len(calls) == busy_check-1


def test_scheduled_lock_rejects_competing_publication_before_provider(tmp_path, monkeypatch):
    row, _ = _football()
    path, _ = _state(tmp_path, [row])
    original = path.read_bytes()
    with automation._quote_publication_lock(path):
        with pytest.raises(RuntimeError, match="publication.*locked"):
            automation.refresh_prices_only(state_path=path, now=NOW, quote_sport="all")
    assert path.read_bytes() == original


def test_cli_all_refresh_never_dispatches_models(monkeypatch, capsys):
    monkeypatch.setattr(automation, "run_wettfinder", lambda **kw: pytest.fail("model scan"))
    calls = []
    monkeypatch.setattr(automation, "refresh_prices_only", lambda **kw:
        calls.append(kw) or dict(errors=0, operational_errors=0))
    assert automation.main(["--quotes-only", "--quote-sport", "all", "--state-path", "fixture.json"]) == 0
    assert calls == [{"state_path": "fixture.json", "quote_sport": "all"}]


def test_scheduled_uses_stored_riskobet_football_market_without_changing_immutable_run(tmp_path, monkeypatch):
    from riskobet_domain import FactorEvidence, RiskRunSnapshot, RunStatus, stable_event_key
    from test_riskobet_ui import _bundle
    row, quote = _football()
    snapshot, candidate = _bundle("stored")
    start = __import__("datetime").datetime.fromisoformat(row["scheduled_start"])
    snapshot = replace(snapshot, event_key=stable_event_key("football", "api-football", str(row["fixture_id"])),
        event_label=f"{row['home_team']} vs {row['away_team']}", starts_at=start,
        modeled_at=NOW-timedelta(hours=1), input_cutoff_at=NOW-timedelta(hours=2),
        factors=(FactorEvidence(f"football_fixture_id:{row['fixture_id']}", "Native identity", "api-football",
            NOW-timedelta(hours=2), NOW-timedelta(hours=1), start),))
    candidate = replace(candidate, snapshot_id=snapshot.snapshot_id, event_key=snapshot.event_key,
        event_label=snapshot.event_label, starts_at=start, market_key="double_chance_90_minutes",
        selection_key="home_or_draw", selection_label=row["home_team"],
        settlement_contract="riskobet-settlement-v1:football:double_chance_90_minutes:home_or_draw")
    run = RiskRunSnapshot(NOW-timedelta(hours=1), NOW-timedelta(minutes=50), RunStatus.COMPLETE,
        (snapshot,), (candidate,))
    risk_path = tmp_path / "riskobet_latest.json"
    risk_path.write_text(json.dumps(run.to_dict()), encoding="utf-8")
    risk_original = risk_path.read_bytes()
    path, _ = _state(tmp_path, [])
    def provider(key, rows, **kwargs):
        assert len(rows) == 1 and rows[0]["fixture_id"] == row["fixture_id"]
        assert rows[0]["market_key"] == "DC_1X"
        return {rows[0]["candidate_id"]: replace(quote, candidate_id=rows[0]["candidate_id"])}, []
    monkeypatch.setattr(automation, "fetch_football_consensus", provider)
    summary = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key="fixture"), quote_sport="all")
    after = json.loads(path.read_text())
    assert summary["checked"] == summary["quotes"] == 1
    assert after["model_candidates"] == []
    assert after["riskobet_price_observations"][0]["reference_quote"]["best_odds"] == quote.best_odds
    assert risk_path.read_bytes() == risk_original


def test_native_manual_refresh_replaces_diagnostic_but_injected_loader_stays_one_argument(tmp_path, monkeypatch):
    row, quote = _football()
    row['reference_price_diagnostic'] = {'reason_code': 'REQUEST_FAILED'}
    path, _ = _state(tmp_path, [row])
    def native(key, rows, **kwargs):
        kwargs['diagnostics'][row['candidate_id']] = dict(reason_code='MARKET_ABSENT',
            fetched_at=NOW.isoformat(), untrusted_body={'private': True})
        return {}, []
    monkeypatch.setattr(automation, 'fetch_football_consensus', native)
    automation.refresh_prices_only(state_path=path, now=NOW, config=AppConfig(api_football_key='fixture'))
    after = json.loads(path.read_text())
    assert after['model_candidates'][0]['reference_price_diagnostic'] == {
        'reason_code': 'MARKET_ABSENT', 'fetched_at': NOW.isoformat()}
    def injected(rows):
        return {quote.candidate_id: quote}, []
    result = automation.refresh_prices_only(state_path=path, now=NOW, quote_loader=injected)
    assert result['quotes'] == 1


def test_missing_tennis_credential_is_not_misreported_as_received_empty_market(tmp_path):
    _, row, _ = _tennis_price_fixture()
    path, _ = _state(tmp_path, [row])
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(), quote_sport='tennis')
    diagnostic = json.loads(path.read_text())['model_candidates'][0]['reference_price_diagnostic']
    assert diagnostic == dict(reason_code='REQUEST_FAILED', error_type='MISSING_CREDENTIAL',
                             checked_at=NOW.isoformat())
    assert result['operational_errors'] == 1


def test_daily_native_price_wrapper_persists_diagnostics_without_refetching_models(tmp_path, monkeypatch):
    """The shared attachment boundary is also the daily-worker integration."""
    row, _ = _football()
    checked = dict(row)
    diagnostics = {row['candidate_id']: dict(reason_code='REQUEST_FAILED',
        checked_at=NOW.isoformat(), error_type='Timeout', http_status=503,
        url='private-request-url')}
    automation._persist_quote_diagnostics([row], [checked], diagnostics, now=NOW, errors=['safe error'])
    assert row['reference_price_diagnostic'] == dict(reason_code='REQUEST_FAILED',
        checked_at=NOW.isoformat(), error_type='Timeout', http_status=503)
    assert checked['reference_price_diagnostic'] == row['reference_price_diagnostic']


def test_pagination_failure_receipt_survives_storage_without_provider_payload():
    row, _ = _football()
    checked = dict(row)
    expected = dict(reason_code='REQUEST_FAILED', error_type='INCOMPLETE_PAGINATION',
        checked_at=NOW.isoformat(), pagination_complete=False,
        pagination_pages_received=1, pagination_total_pages=2,
        pagination_failure='REQUEST_FAILED')
    diagnostics = {row['candidate_id']: {**expected,
        'raw_response': {'credential': 'never-store'}, 'url': 'private-request-url'}}
    automation._persist_quote_diagnostics([row], [checked], diagnostics, now=NOW)
    assert row['reference_price_diagnostic'] == expected
    assert checked['reference_price_diagnostic'] == expected
    assert 'never-store' not in str(row['reference_price_diagnostic'])


def test_team_and_esports_schedule_reuse_existing_caches_and_do_not_claim_execution(tmp_path, monkeypatch):
    from test_team_sport_prices import row as team_row
    from test_esports_prices import row as esports_row
    start = (NOW+timedelta(hours=6)).isoformat()
    team = team_row(source='team_sport_research', scheduled_start=start)
    esports = esports_row(scheduled_start=start)
    path, original = _state(tmp_path, [team, esports])
    calls = []
    def teams(rows, **kwargs):
        calls.append(('team', rows, kwargs))
        return {'status': 'cached', 'checked': 0, 'quotes': 0}
    def esports_refresh(**kwargs):
        calls.append(('esports', [], kwargs))
        return {'status': 'cached', 'events': 2}
    monkeypatch.setattr('team_sport_prices.refresh_team_sport_prices', teams)
    monkeypatch.setattr('esports_prices.refresh_esports_prices', esports_refresh)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture', oddspapi_key='fixture'), quote_sport='all')
    assert [c[0] for c in calls] == ['team', 'esports']
    assert calls[0][2]['now'] == calls[1][2]['now'] == NOW
    after = json.loads(path.read_text())
    assert after['generated_at'] == original['generated_at']
    assert all(r['reference_price_status'] == 'UNAVAILABLE' for r in after['model_candidates'])
    assert all('reference_quote_executable_odds' not in r for r in after['model_candidates'])
    assert all('reference_price_evaluated_at' not in r for r in after['model_candidates'])
    automation.refresh_prices_only(state_path=path, now=NOW+timedelta(hours=1),
        config=AppConfig(api_football_key='fixture', oddspapi_key='fixture'), quote_sport='all')
    assert len(calls) == 2


def test_scheduled_full_football_pool_does_not_reintroduce_ten_fixture_eight_market_cutoff(tmp_path, monkeypatch):
    base, quote = _football()
    rows = []
    for fixture in range(1, 17):
        for market in range(10):
            rows.append(dict(base, fixture_id=fixture, key=f'{fixture}-{market}',
                candidate_id=f'{fixture}-{market}', event_identity=f'event-{fixture}'))
    path, _ = _state(tmp_path, rows)
    received = []
    def native(key, selected, **kwargs):
        received.extend(selected)
        return {}, []
    monkeypatch.setattr(automation, 'fetch_football_consensus', native)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture'), quote_sport='all')
    assert len(received) == result['checked'] == 160
    assert len({r['fixture_id'] for r in received}) == 16


def test_received_foreign_kickoff_is_diagnosed_as_identity_mismatch(tmp_path, monkeypatch):
    row, quote = _football()
    path, _ = _state(tmp_path, [row])
    quote = replace(quote, scheduled_start=(NOW+timedelta(hours=20)).isoformat())
    def received(key, selected, **kwargs):
        kwargs['diagnostics'][row['candidate_id']] = dict(reason_code='OBSERVED',
            fetched_at=NOW.isoformat(), provider_updated_at=NOW.isoformat(), bookmaker_count=3)
        return {row['candidate_id']: quote}, []
    monkeypatch.setattr(automation, 'fetch_football_consensus', received)
    automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture'))
    saved = json.loads(path.read_text())['model_candidates'][0]
    assert saved.get('reference_quote') is None
    assert saved['reference_price_diagnostic'] == dict(reason_code='IDENTITY_MISMATCH',
        fetched_at=NOW.isoformat(), provider_updated_at=NOW.isoformat(), bookmaker_count=3)


def test_deadline_deferred_rows_have_no_attempt_stamp_and_remain_due(tmp_path, monkeypatch):
    first, _ = _football()
    second = dict(first, key='later', candidate_id='later', fixture_id=2, event_identity='later')
    path, _ = _state(tmp_path, [first, second])
    def native(key, rows, **kwargs):
        assert kwargs['deadline'] > 0
        kwargs['diagnostics'][first['candidate_id']] = dict(reason_code='MARKET_ABSENT', fetched_at=NOW.isoformat())
        kwargs['diagnostics'][second['candidate_id']] = dict(reason_code='DEFERRED')
        return {}, []
    monkeypatch.setattr(automation, 'fetch_football_consensus', native)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture'), quote_sport='all')
    after = json.loads(path.read_text())
    assert after['price_check_attempts'] == {first['key']: NOW.isoformat()}
    assert result['checked'] == 1
    assert after['model_candidates'][1]['reference_price_diagnostic'] == {'reason_code': 'DEFERRED'}


@pytest.mark.parametrize('sport', ['team_sports', 'esports'])
def test_partial_cached_provider_errors_are_operational_and_old_execution_fields_are_cleared(tmp_path, monkeypatch, sport):
    from test_team_sport_prices import row as team_row
    from test_esports_prices import row as esports_row
    row = team_row(source='team_sport_research') if sport == 'team_sports' else esports_row()
    row['scheduled_start'] = (NOW+timedelta(hours=6)).isoformat()
    row['reference_quote_executable_odds'] = 2.5
    row['reference_quote_bookmaker_id'] = 'old-proof'
    path, _ = _state(tmp_path, [row])
    def partial(*args, **kwargs):
        return {'status': 'partial', 'errors': ['Timeout']}
    monkeypatch.setattr('team_sport_prices.refresh_team_sport_prices', partial)
    monkeypatch.setattr('esports_prices.refresh_esports_prices', partial)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture', oddspapi_key='fixture'), quote_sport='all')
    assert result['operational_errors'] == 1
    after = json.loads(path.read_text())
    assert all(not k.startswith('reference_quote_') for k in after['model_candidates'][0])


def test_scheduled_daily_attempt_age_prevents_an_immediate_second_paid_query(tmp_path, monkeypatch):
    row, quote = _football()
    path, _ = _state(tmp_path, [row])
    document = json.loads(path.read_text())
    document['price_check_attempts'] = {row['key']: (NOW-timedelta(hours=1)).isoformat()}
    path.write_text(json.dumps(document))
    def forbidden(*args, **kwargs):
        pytest.fail('daily worker already checked this event within3h')
    monkeypatch.setattr(automation, 'fetch_football_consensus', forbidden)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(api_football_key='fixture'), quote_sport='all')
    assert result['checked'] == 0


def test_started_esports_model_does_not_trigger_global_price_catalog_call(tmp_path, monkeypatch):
    from test_esports_prices import row as esports_row
    path, _ = _state(tmp_path, [esports_row(scheduled_start=NOW.isoformat())])
    def forbidden(*args, **kwargs):
        pytest.fail('started model must not trigger global esports price request')
    monkeypatch.setattr('esports_prices.refresh_esports_prices', forbidden)
    automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(oddspapi_key='fixture'), quote_sport='all')


@pytest.mark.parametrize('foreign', [False, True])
def test_stored_riskobet_tennis_uses_only_exact_readonly_prediction_identity(tmp_path, monkeypatch, foreign):
    import sqlite3
    from datetime import datetime
    from riskobet_domain import FactorEvidence, RiskRunSnapshot, RunStatus, stable_event_key
    from test_riskobet_ui import _bundle
    _, row, quote = _tennis_price_fixture()
    snapshot, candidate = _bundle('stored-tennis', sport='tennis')
    start = datetime.fromisoformat(row['scheduled_start'])
    event_key = stable_event_key('tennis', 'ESPN', 'native-tennis')
    snapshot = replace(snapshot, event_key=event_key, event_label='A vs B', starts_at=start,
        modeled_at=NOW-timedelta(hours=1), input_cutoff_at=NOW-timedelta(hours=2),
        factors=(FactorEvidence('tennis_prediction_id:7', 'Native prediction identity', 'tennis_shadow.predictions',
            NOW-timedelta(hours=2), NOW-timedelta(hours=1), start),))
    candidate = replace(candidate, snapshot_id=snapshot.snapshot_id, event_key=event_key,
        event_label='A vs B', starts_at=start, market_key='match_winner', selection_key='home',
        selection_label='A', settlement_contract='riskobet-settlement-v1:tennis:match_winner:home')
    run = RiskRunSnapshot(NOW-timedelta(hours=1), NOW-timedelta(minutes=50), RunStatus.COMPLETE,
        (snapshot,), (candidate,))
    risk_path = tmp_path/'riskobet_latest.json'
    risk_path.write_text(json.dumps(run.to_dict()))
    db_path = tmp_path/'tennis.sqlite'
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE predictions (id INTEGER PRIMARY KEY, fixture_source TEXT, '
            'provider_event_id TEXT, player_a TEXT, player_b TEXT, scheduled_start_utc TEXT)')
        connection.execute('INSERT INTO predictions VALUES (7, ?, ?, ?, ?, ?)',
            ('Other' if foreign else 'ESPN', 'native-tennis', 'A', 'B', row['scheduled_start']))
    monkeypatch.setattr(automation, 'TENNIS_DB', db_path)
    original = db_path.read_bytes()
    path, _ = _state(tmp_path, [])
    calls = []
    def native(key, rows, **kwargs):
        calls.extend(rows)
        return {r['candidate_id']: replace(quote, candidate_id=r['candidate_id'], origin_provider='ESPN',
            origin_event_id='native-tennis') for r in rows}, []
    monkeypatch.setattr(automation, 'fetch_tennis_h2h_consensus', native)
    result = automation.refresh_prices_only(state_path=path, now=NOW,
        config=AppConfig(odds_api_key='fixture'), quote_sport='all')
    assert len(calls) == (0 if foreign else 1)
    assert result['checked'] == (0 if foreign else 1)
    assert db_path.read_bytes() == original
