"""Native storage refusals must not impersonate missing historical sources."""
from copy import deepcopy
from datetime import timedelta

import pytest

from challenge_engine import football_base_history_record
from context_models.contracts import digest
from context_models.football_original_publication import FootballOriginalPublication
from context_sources.football_capture import _Capture
from test_context_football_capture import detail
from test_football_context_provider import NOW, payload


@pytest.mark.parametrize('csv_id', [-5001, 1575469])
def test_budget_reason_applies_only_to_attempted_native_records(tmp_path, csv_id):
    native = detail()
    missing = deepcopy(native)
    missing['fixture']['id'] = 1575470
    csv = deepcopy(native)
    csv['fixture']['id'] = csv_id
    csv['challenge_source'] = 'football-data-results-only'
    rows = (native, missing, csv)
    path = tmp_path / 'capture.db'
    capture = _Capture(path, baseline_enabled=True)
    capture.record('fixtures', {'id': 1575469}, payload([native]),
                   observed_at=NOW, status=200)
    session = FootballOriginalPublication(path, capture,
        max_publication_payload_bytes=100_000, max_worker_payload_bytes=100_000,
        max_source_payload_bytes=0)
    session.freeze(rows)
    decisions = session.model_kwargs(decision_at=NOW + timedelta(seconds=1))
    proof = decisions['native_resolver'](rows)
    assert not proof['records']
    # Observe the real owning callback's reasons without constructing an
    # unrelated goal model or altering any stored historical original.
    selected = next(cell.cell_contents for cell in decisions['native_resolver'].__closure__
                    if isinstance(cell.cell_contents, dict) and 'unresolved' in cell.cell_contents)
    reasons = selected['unresolved']
    assert reasons[digest(football_base_history_record(native))] == 'source-retention-budget-exhausted'
    assert reasons[digest(football_base_history_record(missing))] == 'native-receipt-reference-unavailable'
    assert reasons[digest(football_base_history_record(csv))] == 'native-receipt-reference-unavailable'
