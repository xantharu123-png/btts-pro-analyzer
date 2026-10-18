"""Real temporary A1/B1/B3/Shadow publication with the named optional reader."""
from datetime import timedelta
import json

import pytest

from context_sources.tennis_capture import capture_tennis_worker
from model_artifacts import canonical_bytes
from scripts import tennis_daily as daily
from tennis import shadow
from tennis.live_context import live_worker
from test_tennis_live_worker import configure, run_batch, context_rows, NOW


def test_optional_live_source_preserves_exact_real_publication(monkeypatch, tmp_path):
    from contextlib import closing
    from context_observations import _connect as source_connection
    from context_tennis_index_build import initialize_index, build_index
    old_root, new_root = tmp_path/'legacy', tmp_path/'indexed'
    old_root.mkdir()
    new_root.mkdir()
    old_db, old_predictions, _, _ = configure(monkeypatch, old_root)
    _, old_rows = run_batch(old_db, old_predictions)
    old_context = json.loads(old_rows[0]['context_json'])['context_model']
    new_db, new_predictions, _, calls = configure(monkeypatch, new_root)
    # Explicit temporary fixture setup, never a production schema upgrade.
    with closing(source_connection(new_db)):
        pass
    initialize_index(new_db)
    assert build_index(new_db).status == 'ready'
    with live_worker(path=new_db, source_transport='tennis-live-indexed-source-v1') as batch:
        with capture_tennis_worker(path=new_db) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn('2026-09-09')
            result = daily.scan_fixtures('2026-09-09', fixtures, decision_at=NOW,
                db_path=new_predictions, surfaces={}, workload_history=(),
                append_observed_at=NOW+timedelta(seconds=2))
        batch.finish()
    new_rows = shadow.latest_predictions(new_predictions, as_of=NOW+timedelta(seconds=3))
    assert result['stored'] == 1 and not result['errors'] and len(new_rows) == 1
    assert canonical_bytes(json.loads(new_rows[0]['context_json'])['context_model']) == canonical_bytes(old_context)
    assert canonical_bytes(context_rows(new_db)) == canonical_bytes(context_rows(old_db))
    assert len(calls) == 2


def test_unready_index_never_publishes_a_successful_prefix(monkeypatch, tmp_path):
    db, predictions, _, _ = configure(monkeypatch, tmp_path)
    with live_worker(path=db, source_transport='tennis-live-indexed-source-v1') as batch:
        with capture_tennis_worker(path=db) as capture:
            batch.attach_capture(capture)
            fixtures = daily.fetch_fixtures_espn('2026-09-09')
            result = daily.scan_fixtures('2026-09-09', fixtures, decision_at=NOW,
                db_path=predictions, surfaces={}, workload_history=())
        before = db.read_bytes()
        with pytest.raises(ValueError, match='tennis player index'):
            batch.finish()
        assert db.read_bytes() == before
    assert result['stored'] == 0 and context_rows(db) == []
    assert shadow.latest_predictions(predictions, as_of=NOW+timedelta(seconds=3)) == []
