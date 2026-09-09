"""Persisted D3 consumer boundary, not source/empirical model acceptance."""
from copy import deepcopy
import sqlite3

import pytest

from context_models.contracts import ContextContractError, ContextIntegrityError
from context_snapshots import compute_once
from context_transport import calculate_context_payload, context_consumer_reference, context_payload_key
from model_artifacts import canonical_bytes
from test_context_transport import inputs, synthetic_approval
from test_esports_context import case


def saved(tmp_path, *, approved=False):
    args = inputs(with_effect=True)
    if approved:
        args["approval"] = synthetic_approval(args)
    payload = calculate_context_payload(**args)
    key = context_payload_key(payload)
    path = tmp_path / "models.db"
    compute_once(path, key, lambda: payload)
    reference = context_consumer_reference(key, payload)
    return path, reference, payload


def read(path, ref, payload, **kwargs):
    from context_consumers import load_context_market
    return load_context_market(path, ref, "winner_a", expected_event=payload["event"],
                               expected_cutoff=payload["base"]["cutoff"], **kwargs)


@pytest.mark.parametrize("approved", [False, True])
def test_shared_read_retains_exact_stored_probability_and_public_copy(tmp_path, approved):
    from context_consumers import load_context_market
    path, ref, payload = saved(tmp_path, approved=approved)
    before = path.read_bytes()
    one = read(path, ref, payload)
    two = load_context_market(path, ref, "winner_b", expected_event=payload["event"],
                              expected_cutoff=payload["base"]["cutoff"])
    assert one["projection"]["context_ref"] == two["projection"]["context_ref"] == ref
    assert one["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_a"]
    assert two["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_b"]
    assert one["public_summary"]["used_probability"] == one["projection"]["used_probability"]
    assert one["public_summary"]["delta_pp"] == payload["result"]["delta_pp"]["winner_a"]
    one["projection"]["used_params"].clear()
    one["public_summary"]["admin_details"]["factor_states"].clear()
    assert read(path, ref, payload) != one
    assert canonical_bytes(payload["result"]["used_params"]) == canonical_bytes(two["projection"]["used_params"])
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-journal").exists()


@pytest.mark.parametrize("field", ["home_id", "away_id", "schedule_revision", "scheduled_start", "status", "tour"])
def test_reader_rejects_ref_from_another_consumer_event_revision(tmp_path, field):
    path, ref, payload = saved(tmp_path)
    expected = deepcopy(payload)
    if field == "scheduled_start":
        expected["event"][field] = "2026-09-09T19:00:00.000000Z"
    elif field == "status":
        expected["event"][field] = "cancelled"
    elif field == "tour":
        expected["event"][field] = "WTA"
    else:
        expected["event"][field] += "-different"
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        read(path, ref, expected)


def test_reader_requires_exact_persisted_decision_not_current_time(tmp_path):
    path, ref, payload = saved(tmp_path)
    payload["base"]["cutoff"] = "2026-09-09T12:00:00.000001Z"
    with pytest.raises(ContextIntegrityError):
        read(path, ref, payload)


@pytest.mark.parametrize("field,value", [("schema", True), ("kind", "future"), ("key", "e"*64),
    ("payload_digest", "e"*64), ("extra", "odds")])
def test_reader_rejects_missing_changed_or_open_reference(tmp_path, field, value):
    path, ref, payload = saved(tmp_path)
    ref[field] = value
    with pytest.raises((ContextContractError, ContextIntegrityError)):
        read(path, ref, payload)


@pytest.mark.parametrize("corruption", ["payload-text", "digest", "missing", "view"])
def test_corruption_is_not_a_request_to_regenerate_or_show_legacy(tmp_path, corruption):
    path, ref, payload = saved(tmp_path)
    with sqlite3.connect(path) as connection:
        if corruption == "payload-text":
            connection.execute("UPDATE context_snapshots SET payload=CAST(payload AS TEXT)")
        elif corruption == "digest":
            connection.execute("UPDATE context_snapshots SET payload_digest=?", ("b"*64,))
        elif corruption == "missing":
            connection.execute("DELETE FROM context_snapshots")
        else:
            connection.execute("ALTER TABLE context_snapshots RENAME TO hidden_snapshots")
            connection.execute("CREATE VIEW context_snapshots AS SELECT * FROM hidden_snapshots")
    before = path.read_bytes()
    with pytest.raises(ContextIntegrityError):
        read(path, ref, payload)
    assert path.read_bytes() == before


def test_reader_never_creates_missing_database_or_schema(tmp_path):
    from context_consumers import load_context_market
    path, ref, payload = saved(tmp_path)
    missing = tmp_path / "not-created" / "unknown.db"
    with pytest.raises(ContextIntegrityError):
        load_context_market(missing, ref, "winner_a", expected_event=payload["event"],
                            expected_cutoff=payload["base"]["cutoff"])
    assert not missing.parent.exists()
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    before = empty.read_bytes()
    with pytest.raises(ContextIntegrityError):
        read(empty, ref, payload)
    assert empty.read_bytes() == before


def test_reader_cannot_fit_refresh_publish_or_contact_provider(tmp_path, monkeypatch):
    import context_models.dataset
    import context_transport
    path, ref, payload = saved(tmp_path)
    from context_consumers import load_context_market
    def forbidden(*args, **kwargs):
        pytest.fail("stored consumer lookup must not run a model, source or writer")
    monkeypatch.setattr("context_models.tennis_effect.apply_tennis_effect", forbidden)
    monkeypatch.setattr("context_snapshots.compute_once", forbidden)
    monkeypatch.setattr("model_artifacts._connect", forbidden)
    monkeypatch.setattr(context_transport, "calculate_context_payload", forbidden)
    monkeypatch.setattr(context_transport, "context_payload_key", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    original_connect = context_models.dataset.sqlite3.connect
    modes = []
    def only_readonly(database, *args, **kwargs):
        assert str(database).endswith("?mode=ro") and kwargs.get("uri") is True
        connection = original_connect(database, *args, **kwargs)
        def authorize(action, *_):
            if action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                          sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE}:
                pytest.fail("reader attempted a data/schema write")
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorize)
        modes.append(connection)
        return connection
    monkeypatch.setattr(context_models.dataset.sqlite3, "connect", only_readonly)
    for _ in range(2):
        result = load_context_market(path, ref, "winner_a", expected_event=payload["event"],
                                    expected_cutoff=payload["base"]["cutoff"])
        assert result["projection"]["used_probability"] == payload["result"]["used_markets"]["winner_a"]
    assert len(modes) == 2


def test_reader_uses_explicit_factor_groups_not_substring_guess(tmp_path):
    path, ref, payload = saved(tmp_path)
    member = next(iter(payload["result"]["factor_roles"]))
    result = read(path, ref, payload, factor_groups={"workload": [member]})
    assert result["public_summary"]["admin_details"]["factor_groups"] == {"workload": [member]}
    with pytest.raises(ContextContractError):
        read(path, ref, payload, factor_groups={"injuries<script>": [member]})


@pytest.mark.parametrize("sport", ["football", "tennis", "basketball", "hockey", "esports"])
def test_all_five_existing_owning_families_read_from_one_persisted_law(tmp_path, case, sport, monkeypatch):
    from context_consumers import load_context_market
    if sport == "tennis":
        args = inputs()
    elif sport == "football":
        from test_football_context_model import inputs as football_inputs, event
        original, features, _ = football_inputs()
        args = dict(event=event(), base=original, features=features,
            observation_refs=sorted({ref for refs in features["refs"].values() for ref in refs}),
            preprocessing_refs=[], effect_artifact=None, effect_hash=None, approval=None)
    else:
        from test_context_original_event_binding import arguments
        args = arguments(sport, case)
    payload = calculate_context_payload(**args)
    key = context_payload_key(payload)
    ref = context_consumer_reference(key, payload)
    path = tmp_path / "worker.db"
    calls = []
    compute_once(path, key, lambda: (calls.append("original"), payload)[1])
    def forbidden(*args, **kwargs):
        pytest.fail("consumer must not reproduce the owning law or source")
    monkeypatch.setattr("context_models.team_sports._recipe_arrays", forbidden)
    monkeypatch.setattr("context_models.ice_hockey._original_parts", forbidden)
    monkeypatch.setattr("context_models.esports._replay", forbidden)
    monkeypatch.setattr("context_transport.validate_base_distribution", forbidden)
    monkeypatch.setattr("context_transport.calculate_context_payload", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    before = path.read_bytes()
    for market, probability in args["base"]["markets"].items():
        result = load_context_market(path, ref, market, expected_event=payload["event"],
                                    expected_cutoff=payload["base"]["cutoff"])
        assert result["projection"]["used_probability"] == probability
        assert result["projection"]["context_ref"] == ref
    assert calls == ["original"]
    assert path.read_bytes() == before
