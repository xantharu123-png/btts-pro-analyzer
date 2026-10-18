"""Optional named live API; canonical callers retain legacy until acceptance."""
from datetime import timedelta

import pytest

from context_models.contracts import ContextContractError


def test_live_owner_default_and_v3_remain_legacy(tmp_path):
    from tennis.live_context import LiveWorker, live_worker
    assert LiveWorker(tmp_path/'missing').source_transport == 'legacy'
    assert LiveWorker(tmp_path/'missing', feature_version='tennis-performed-load-v3').source_transport == 'legacy'
    with live_worker(path=tmp_path/'missing') as batch:
        assert batch.source_transport == 'legacy'
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('transport', [None, '', 'indexed', True, 'tennis-source-stream-v1'])
def test_api_rejects_unknown_or_offline_transport_before_io(tmp_path, transport):
    from tennis.live_context import LiveWorker
    with pytest.raises(ContextContractError, match='source transport'):
        LiveWorker(tmp_path/'missing', source_transport=transport)
    assert not (tmp_path/'missing').exists()


def test_live_v3_cannot_silently_use_event_scoped_refs(tmp_path):
    from tennis.live_context import LiveWorker
    with pytest.raises(ContextContractError, match='requires v4'):
        LiveWorker(tmp_path/'missing', feature_version='tennis-performed-load-v3',
                   source_transport='tennis-live-indexed-source-v1')
