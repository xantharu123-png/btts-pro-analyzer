"""Keep optional publication receipts out of real local runtime state."""
import os

import pytest
from hashlib import sha256

PRICE_POLICIES = ("gate", "floor")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "price_policy(name): pin BETBOY_PRICE_POLICY for a test that documents one contract only",
    )


@pytest.fixture(autouse=True)
def legacy_price_gate_policy(monkeypatch, request):
    """Existing suites document the execution contract that was the default until
    23.10.2026; tests of the 1.20 floor policy set BETBOY_PRICE_POLICY=floor
    themselves (tests/test_price_floor_policy.py).

    BETBOY_TEST_PRICE_POLICY=floor runs the other suites under the production
    default as well (CI job ``floor``, Audit 25.10.2026 D5); a test whose
    assertions only hold under one contract carries ``@pytest.mark.price_policy``."""
    if "price_floor" in request.node.nodeid:
        return
    marker = request.node.get_closest_marker("price_policy")
    policy = marker.args[0] if marker else os.environ.get("BETBOY_TEST_PRICE_POLICY", "gate")
    if policy not in PRICE_POLICIES:
        raise pytest.UsageError(f"unknown price policy {policy!r}")
    monkeypatch.setenv("BETBOY_PRICE_POLICY", policy)


@pytest.fixture(autouse=True)
def isolate_consumer_tip_receipts(monkeypatch, request, tmp_path_factory):
    import tip_publication
    # Derive a private per-test path lazily: most numerical tests never write
    # a receipt and should not create thousands of unnecessary directories.
    receipt_dir = tmp_path_factory.getbasetemp() / 'consumer-receipts' / sha256(request.node.nodeid.encode()).hexdigest()
    monkeypatch.setattr(tip_publication, 'DEFAULT_HISTORY_DB', receipt_dir / 'consumer_tips.db')
    monkeypatch.setattr(tip_publication, 'DEFAULT_FORECAST_DB', receipt_dir / 'forecast_evidence.db')
