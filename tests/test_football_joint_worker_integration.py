"""Post-capture wiring only; no provider, fitting or production data used."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import wettfinder_automation as automation
from config_loader import AppConfig

NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
ORIGINAL = dict(schema=1, scope='football-final-same-call-originals',
    published_count=0, inserted_payload_bytes=0, source_inserted_payload_bytes=0, events=[])
JOINT = dict(schema=1, scope='football-post-capture-internal-joint-comparison',
    events=[], unprocessed_events=0, reserved_payload_bytes=0)


@pytest.mark.parametrize('entry', ['scan', 'model-refresh', 'context-only'])
@pytest.mark.parametrize('enabled', [False, True])
def test_comparison_runs_only_after_committed_opt_in_original(entry, enabled, tmp_path, monkeypatch):
    state = dict(open=False, closed=False)
    calls = []
    capture = SimpleNamespace(path=tmp_path/'never-created.db',
        report=lambda: dict(schema=1, scope='existing-football-context-requests',
            status='no_receipts', receipt_refs=[], issues=[]))
    publication = SimpleNamespace(report=lambda: deepcopy(ORIGINAL))
    @contextmanager
    def capturing(_provider, **_kwargs):
        state['open'] = True
        try:
            yield capture
        finally:
            state.update(open=False, closed=True)
    def compare(path, report, *, decision_at):
        assert state['closed'] and not state['open']
        assert path == capture.path and report == ORIGINAL
        assert decision_at == NOW + timedelta(minutes=3)
        calls.append(decision_at)
        return deepcopy(JOINT)
    def work(_provider, *_args, **kwargs):
        assert state['open']
        if kwargs.get('original_publication') is not None:
            assert kwargs['original_publication'] is publication
            return dict(football_original_capture=deepcopy(ORIGINAL), marker='baseline-unchanged')
        return dict(marker='baseline-unchanged')
    class ActualClock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            return NOW + timedelta(minutes=3)
    monkeypatch.setattr(automation, 'datetime', ActualClock)
    monkeypatch.setattr(automation, 'ChallengeDataProvider', lambda *_args: object())
    monkeypatch.setattr('context_sources.football_capture.capture_football_worker', capturing)
    monkeypatch.setattr('context_models.football_original_publication.publication_for_worker',
        lambda *_args, **_kwargs: publication)
    monkeypatch.setattr('football_joint_worker.publish_joint_capture_report', compare)
    monkeypatch.setattr(automation, 'scan_daily_challenge', work)
    monkeypatch.setattr(automation, 'refresh_fixture_models', work)
    monkeypatch.setattr(automation, 'refresh_discovered_candidates', work)
    cfg = AppConfig(api_football_key='offline-not-a-key')
    limits = {} if enabled else None
    if entry == 'scan':
        result = automation._default_football_scan(NOW.date(), cfg, original_capture_limits=limits)
    else:
        result = automation._default_football_context_refresh([], NOW.date(), NOW, cfg,
            recompute_models=entry == 'model-refresh', original_capture_limits=limits)
    expected = enabled and entry != 'context-only'
    assert bool(calls) is expected
    assert ('football_joint_comparison' in result) is expected
    assert result['marker'] == 'baseline-unchanged'
    assert not capture.path.exists()


def test_internal_report_survives_state_and_context_merge_without_public_selection_changes():
    source = dict(football_original_capture=deepcopy(ORIGINAL), football_joint_comparison=deepcopy(JOINT))
    state = automation._football_state_from_snapshot(source, attempted_at=NOW, search_date=NOW.date())
    assert state['football_joint_comparison'] == JOINT
    before = deepcopy(state['candidates'])
    merged = automation._merge_context_refresh(state, source, fixture_ids=[], checked_at=NOW)
    assert merged['football_joint_comparison'] == JOINT
    assert merged['candidates'] == before
