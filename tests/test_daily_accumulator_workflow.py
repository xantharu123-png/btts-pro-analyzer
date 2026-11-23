from datetime import datetime, timezone
from types import SimpleNamespace

from daily_accumulator_publication import linked_legs, record_worker_combos


def test_only_exact_existing_forecasts_can_enter_pool():
    signals = [SimpleNamespace(key=k) for k in ('a','b','c','c')]
    clock = datetime.now(timezone.utc)
    def bind(rows, *, as_of, db_path):
        assert as_of == clock and db_path == 'existing.db'
        assert {r['key'] for r in rows} == {'a','b'}
        return [{'key':'a','forecast_id':'a'*64}, {'key':'b'}]
    legs = [{'signal_key': k, 'event_key': k, 'forecast_id': 'bogus'} for k in 'abcd']
    result = linked_legs(legs, signals, as_of=clock, evidence_path='existing.db',
                         compact=lambda s: {'key':s.key}, bind=bind)
    assert result == [{'signal_key':'a','event_key':'a','forecast_id':'a'*64}]


def test_worker_does_not_invent_forecasts_or_create_empty_db(tmp_path):
    assert record_worker_combos([], as_of=datetime.now(timezone.utc), directory=tmp_path)['status'] == 'empty'
    assert list(tmp_path.iterdir()) == []


def test_candidate_freezes_the_original_hit_probability_and_fit(monkeypatch, tmp_path):
    from daily_accumulator_receipts import capture_day
    from daily_accumulator_publication import candidate_selector
    from test_daily_accumulators import NOW, model, pool
    import daily_accumulator_receipts as receipts
    import daily_accumulator_quality as quality
    monkeypatch.setattr(receipts, "_now", lambda: NOW)
    monkeypatch.setattr(quality, "candidate_scorer", lambda model, **kw: lambda slip: .31)
    model_info = {"kind": "fit", "digest": "a"*64, "groups": {"synthetic": {}}}
    db = tmp_path / "proof.db"
    legs = [dict(leg, forecast_id=f'{i:064x}') for i, leg in enumerate(pool(*(model(i) for i in range(1, 4))), 1)]
    select = candidate_selector(NOW, model_info, None)
    slip, = capture_day(db, day=NOW.date(), as_of=NOW, pool=legs, select=select, arm="candidate")
    assert slip["fit_digest"] == model_info["digest"] and slip["candidate_probability"] == .31
    assert slip["candidate_probability"] != slip["reference_probability"]


def test_worker_publishes_playing_day_picks_without_a_common_book_or_fit(tmp_path, monkeypatch):
    import daily_accumulator_receipts as receipts
    import forecast_evidence as evidence
    from dataclasses import replace
    from test_daily_accumulators import NOW, model
    from tip_publication import compact_signal_row
    monkeypatch.setenv("BETBOY_PRICE_POLICY", "floor")
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    monkeypatch.setattr(receipts, "_now", lambda: NOW)
    signals = [model(i, odds=1.4) for i in (1, 2, 7, 8)]
    signals.extend(model(i, odds=1.4, key="TOTAL_UNDER_2_5") for i in (3, 4))
    # Both unpriced but only the first passes the existing public model guard.
    signals.extend(replace(model(i, p=p, key="TOTAL_UNDER_2_5"), reference_quote=None)
                   for i,p in [(6,.62), (9,.81)])
    # No shared book even for the three highest-ranked tips. Odds identify real
    # bookmaker offers, not a fictitious common booking venue.
    from copy import deepcopy
    for index, s in enumerate(signals[:6]):
        quote = deepcopy(s.reference_quote)
        for point in quote["points"]:
            point["bookmaker_id"] += f"-{index}"
        quote.pop("executable_quote", None)
        signals[index] = replace(s, reference_quote=quote)
    rows = [dict(compact_signal_row(s), event_identity=f"football:{s.fixture_id}",
                 home_id=s.home_team_id, away_id=s.away_team_id, source="football_challenge") for s in signals]
    db = tmp_path / "forecast_evidence.db"
    stored = evidence.record_forecast_run(dict(generated_at=NOW.isoformat(), selection_policy_version="test-v1",
                                               model_candidates=rows), db, "test-model-v1")
    assert stored["recorded"] == len(signals)
    first = record_worker_combos([s for s in signals if s.fixture_id in (1, 2, 3)],
                                as_of=NOW, directory=tmp_path)
    assert first["sizes"] == {"daily-picks": [3]}
    slips_path = tmp_path / "daily_accumulators.db"
    original, = receipts.load_daily_picks(slips_path, day=NOW.date())
    report = record_worker_combos(signals, as_of=NOW, directory=tmp_path)
    assert report["linked_legs"] == 7
    assert report["sizes"] == {"daily-picks": [3,4]}
    saved = receipts.load_daily_picks(slips_path, day=NOW.date())
    assert [s["size"] for s in saved] == [3, 4]
    assert all(s["price_status"] == "unconfirmed" and s["bookmaker_id"] is None for s in saved)
    assert not receipts.load_day(slips_path, day=NOW.date(), arm="model-observation")
    assert not receipts.load_day(slips_path, day=NOW.date(), arm="reference")
    assert [sorted(leg["fixture_id"] for leg in s["legs"]) for s in saved] == [[1, 2, 3], [4, 6, 7, 8]]
    assert saved[0] == original
    assert {leg["forecast_id"] for s in saved for leg in s["legs"]} <= set(stored["forecast_ids"])
