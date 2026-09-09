"""D3 typed numerical restore checks explicitly do not prove source features."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime
import sqlite3

import pytest

from context_observations import append_observation
from context_snapshots import compute_once, _payload_digest
from context_transport import calculate_context_payload, context_payload_key
from context_runtime import verify_context_database
from model_artifacts import ArtifactIntegrityError, canonical_bytes, put_artifact
from test_context_transport import inputs


def stored_transport(tmp_path, *, with_effect):
    path = tmp_path / "context.db"
    args = inputs(with_effect=with_effect)
    event = args["event"]
    clock = datetime.fromisoformat(args["base"]["cutoff"])
    ref = append_observation(path, {
        **{key: event[key] for key in ("event_key", "sport", "competition", "format", "schedule_revision")},
        "subject_id": event["home_id"], "kind": "workload", "source": "synthetic-d4",
        "source_schema": "unqualified-workload-v1", "source_revision": "one",
        "published_at": None, "publication_proof": None, "valid_from": clock.isoformat(),
        "valid_until": None, "complete": False, "payload": {"observed_sets": 3},
    }, observed_at=clock)
    args["observation_refs"] = [ref]
    for name, refs in args["features"]["refs"].items():
        if refs:
            args["features"]["refs"][name] = [ref]
    if with_effect:
        assert put_artifact(path, **args["effect_artifact"], created_at=clock) == args["effect_hash"]
    payload = calculate_context_payload(**args)
    key = context_payload_key(payload)
    compute_once(path, key, lambda: payload)
    return path, key, payload


@pytest.mark.parametrize("with_effect", [False, True])
def test_real_b3_transport_is_numerically_checked_but_not_source_certified(tmp_path, with_effect):
    path, key, payload = stored_transport(tmp_path, with_effect=with_effect)
    before = path.read_bytes()
    result = verify_context_database(path)
    assert result["verification_level"] == "transport_only"
    assert "d3-owning-source-feature-replay-unavailable" in result["limitations"]
    assert result["empirical_approval_verified"] is False
    assert path.read_bytes() == before
    assert compute_once(path, key, lambda: pytest.fail("restored snapshot recomputed")) == payload


@pytest.mark.parametrize("change", ["comparison", "missing-receipt", "event", "key", "used"])
def test_rehashed_d3_transport_cannot_hide_claimed_math_or_identity_corruption(tmp_path, change):
    path, key, original = stored_transport(tmp_path, with_effect=True)
    payload = deepcopy(original)
    if change == "comparison":
        payload["result"]["comparison_params"]["p_a"] = .51
        payload["result"]["comparison_markets"] = {"winner_a": .51, "winner_b": .49}
    elif change == "missing-receipt":
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DELETE FROM context_observations")
            connection.execute("DELETE FROM context_contents")
            connection.commit()
    elif change == "event":
        payload["event"]["schedule_revision"] = "another-revision"
    elif change == "used":
        payload["result"]["used_markets"]["winner_a"] = .8
    else:
        key = "f" * 64
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM context_snapshots")
        connection.execute("INSERT INTO context_snapshots VALUES(?,?,?)",
            (key, canonical_bytes(payload), _payload_digest(key, payload)))
        connection.commit()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)


@pytest.mark.parametrize("change", ["feature-version", "family", "forged-version-and-result"])
def test_unknown_owning_capability_cannot_claim_numerical_or_source_verification(tmp_path, monkeypatch, change):
    import context_transport
    path, _, payload = stored_transport(tmp_path, with_effect=True)
    if change == "family":
        payload["base"]["family"] = "tennis:future-family"
    else:
        payload["features"]["version"] = "unimplemented-feature-v999"
    if change == "forged-version-and-result":
        payload["result"]["comparison_params"]["p_a"] = .51
        payload["result"]["comparison_markets"] = {"winner_a": .51, "winner_b": .49}
    key = context_transport._input_key(payload, payload["event"], payload["base"], payload["features"])
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM context_snapshots")
        connection.execute("INSERT INTO context_snapshots VALUES(?,?,?)",
            (key, canonical_bytes(payload), _payload_digest(key, payload)))
        connection.commit()
    def not_supported(*args, **kwargs):
        pytest.fail("unknown capability was presented to an incompatible numerical law")
    monkeypatch.setattr(context_transport, "replay_context_payload", not_supported)
    result = verify_context_database(path)
    assert result["verification_level"] == "transport_only"
    assert "d3-owning-family-replay-unavailable" in result["limitations"]
    assert "d3-owning-source-feature-replay-unavailable" not in result["limitations"]
    assert result["empirical_approval_verified"] is False


@pytest.mark.parametrize("change", ["missing-ref", "wrong-key", "mismatched-artifact", "invalid-version-type"])
def test_unknown_capability_does_not_skip_transport_corruption(tmp_path, change):
    import context_transport
    path, _, payload = stored_transport(tmp_path, with_effect=True)
    payload["features"]["version"] = "future-v99"
    key = context_transport._input_key(payload, payload["event"], payload["base"], payload["features"])
    if change == "missing-ref":
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DELETE FROM artifacts")
            connection.commit()
    elif change == "wrong-key":
        key = "e" * 64
    elif change == "invalid-version-type":
        payload["features"]["version"] = 999
    else:
        payload["effect_artifact"]["payload"]["heads"]["winner"]["coef"][0] = 17.
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM context_snapshots")
        connection.execute("INSERT INTO context_snapshots VALUES(?,?,?)",
            (key, canonical_bytes(payload), _payload_digest(key, payload)))
        connection.commit()
    with pytest.raises(ArtifactIntegrityError):
        verify_context_database(path)
