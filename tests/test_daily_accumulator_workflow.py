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


def test_worker_freezes_common_book_and_does_not_author_a_receipt_on_page_view(tmp_path, monkeypatch):
    import daily_accumulator_receipts as receipts
    import forecast_evidence as evidence
    from daily_accumulator_surface import render_daily_accumulators
    from test_daily_accumulators import NOW, model
    from tip_publication import compact_signal_row
    from unittest.mock import MagicMock
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    monkeypatch.setattr(receipts, "_now", lambda: NOW)
    signals = [model(i, odds=1.4) for i in range(1, 7)]
    rows = [dict(compact_signal_row(s), event_identity=f"football:{s.fixture_id}",
                 home_id=s.home_team_id, away_id=s.away_team_id, source="football_challenge") for s in signals]
    db = tmp_path / "forecast_evidence.db"
    stored = evidence.record_forecast_run(dict(generated_at=NOW.isoformat(), selection_policy_version="test-v1",
                                               model_candidates=rows), db, "test-model-v1")
    assert stored["recorded"] == len(signals)
    report = record_worker_combos(signals, as_of=NOW, directory=tmp_path)
    assert report["linked_legs"] == len(signals)
    assert report["sizes"] == {"reference": [3,4], "model-observation": [3,4]}
    slips_path = tmp_path / "daily_accumulators.db"
    saved = receipts.load_day(slips_path, day=NOW.date())
    assert [s["size"] for s in saved] == [3, 4]
    assert all(s["price_status"] == "confirmed" for s in saved)
    assert {leg["forecast_id"] for s in saved for leg in s["legs"]} <= set(stored["forecast_ids"])
    before = slips_path.read_bytes()
    widget = MagicMock()
    render_daily_accumulators(widget, as_of=NOW, directory=tmp_path)
    widget.progress.assert_not_called()
    widget.caption.assert_called_with("Heute noch kein geprüfter Kombischein.")
    assert before == slips_path.read_bytes()
