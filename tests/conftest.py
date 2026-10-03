"""Keep optional publication receipts out of real local runtime state."""
import pytest
from hashlib import sha256


@pytest.fixture(autouse=True)
def isolate_consumer_tip_receipts(monkeypatch, request, tmp_path_factory):
    import tip_publication
    # Derive a private per-test path lazily: most numerical tests never write
    # a receipt and should not create thousands of unnecessary directories.
    receipt_dir = tmp_path_factory.getbasetemp() / 'consumer-receipts' / sha256(request.node.nodeid.encode()).hexdigest()
    monkeypatch.setattr(tip_publication, 'DEFAULT_HISTORY_DB', receipt_dir / 'consumer_tips.db')
    monkeypatch.setattr(tip_publication, 'DEFAULT_FORECAST_DB', receipt_dir / 'forecast_evidence.db')
