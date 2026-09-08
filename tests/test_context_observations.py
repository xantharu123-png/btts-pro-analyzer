from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

import context_observations as observations
from context_observations import append_observation, observations_as_of, factor_state, freshness_policy
from context_models.contracts import ContextContractError, ContextIntegrityError, digest


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def normalized_record(**changes):
    """Explicit normalized source fixture; no raw provider blob or real coverage."""
    return {
        "event_key": "api-football:football:1", "sport": "football",
        "competition": "39", "format": "90min", "subject_id": "player:7",
        "kind": "availability", "source": "api-football", "source_schema": "injuries-v3",
        "source_revision": "r1", "schedule_revision": "s1", "published_at": None,
        "publication_proof": None, "valid_from": NOW.isoformat(), "valid_until": None,
        "complete": False, "payload": {"status": "out"}, **changes,
    }


def selected(path, *, cutoff=NOW, schedule="s1", mode="prospective", proof_resolver=None):
    return observations_as_of(path, "api-football:football:1", cutoff=cutoff,
                              schedule_revision=schedule, mode=mode, proof_resolver=proof_resolver)


def state(rows, *, cutoff=NOW, start=NOW + timedelta(hours=10), kind="availability", complete=False, **kwargs):
    policy = freshness_policy(kind, schedule_revision="s1", requires_complete=complete, **kwargs)
    return factor_state(rows, cutoff=cutoff, scheduled_start=start, policy=policy)


def test_late_injury_correction_is_not_backdated(tmp_path):
    path = tmp_path / "models.db"
    cutoff = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    row = dict(
        event_key="api-football:football:1", sport="football",
        competition="39", format="90min", subject_id="player:7",
        kind="availability", source="api-football", source_schema="injuries-v3",
        source_revision="r1", schedule_revision="s1", published_at=None,
        publication_proof=None, valid_from=cutoff.isoformat(), valid_until=None,
        complete=False, payload={"status": "out"},
    )
    first = append_observation(path, row, observed_at=cutoff)
    append_observation(
        path, {**row, "source_revision": "r2", "payload": {"status": "available"}},
        observed_at=cutoff + timedelta(hours=1),
    )
    rows = observations_as_of(path, row["event_key"], cutoff=cutoff,
                              schedule_revision="s1")
    assert [r["digest"] for r in rows] == [first]
    assert rows[0]["payload"]["status"] == "out"


def test_unchanged_recheck_has_new_receipt_not_rewritten_first_observation(tmp_path):
    path = tmp_path / "models.db"
    record = normalized_record()
    first = append_observation(path, record, observed_at=NOW)
    assert append_observation(path, record, observed_at=NOW) == first
    later = append_observation(path, record, observed_at=NOW + timedelta(hours=7))
    old, new = selected(path)[0], selected(path, cutoff=NOW + timedelta(hours=7))[0]
    assert old["digest"] == first != later == new["digest"]
    assert old["content_digest"] == new["content_digest"]
    assert old["observed_at"] == "2026-09-07T12:00:00.000000Z"
    assert state((old,), cutoff=NOW + timedelta(hours=7))["state"] == "stale"
    assert state((new,), cutoff=NOW + timedelta(hours=7))["state"] == "available"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone() == (2,)


def test_timezone_equivalent_content_and_receipts_share_canonical_identity(tmp_path):
    path = tmp_path / "models.db"
    local = datetime(2026, 9, 7, 14, tzinfo=timezone(timedelta(hours=2)))
    a = append_observation(path, normalized_record(), observed_at=NOW)
    b = append_observation(path, normalized_record(valid_from=local.isoformat()), observed_at=local)
    assert a == b
    assert selected(path, cutoff=local)[0]["valid_from"] == "2026-09-07T12:00:00.000000Z"


def test_mutating_selected_content_to_noncanonical_equivalent_time_cannot_change_comparison_semantics(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    rows = selected(path)
    rows[0]["valid_from"] = "2026-09-07T14:00:00+02:00"
    with pytest.raises(ContextIntegrityError):
        state(rows)


@pytest.mark.parametrize("field", ["observed_at", "published_at", "valid_from", "valid_until", "cutoff"])
def test_naive_clocks_rejected_without_fabricated_timezone(tmp_path, field):
    path = tmp_path / "models.db"
    record = normalized_record()
    if field == "cutoff":
        append_observation(path, record, observed_at=NOW)
        with pytest.raises(ContextContractError):
            selected(path, cutoff=NOW.replace(tzinfo=None))
    else:
        if field != "observed_at":
            record[field] = "2026-09-07T12:00:00"
        with pytest.raises(ContextContractError):
            append_observation(path, record, observed_at=NOW.replace(tzinfo=None) if field == "observed_at" else NOW)
        assert not path.exists()


def test_publication_after_receipt_is_invalid_but_future_forecast_validity_is_legal(tmp_path):
    path = tmp_path / "models.db"
    with pytest.raises(ContextContractError, match="publication"):
        append_observation(path, normalized_record(published_at=(NOW + timedelta(microseconds=1)).isoformat()), observed_at=NOW)
    assert not path.exists()
    record = normalized_record(kind="weather", source_schema="weather-forecast-v1", complete=True,
                               valid_from=(NOW + timedelta(hours=1)).isoformat(),
                               valid_until=(NOW + timedelta(hours=4)).isoformat(), payload={"temperature_c": 22})
    append_observation(path, record, observed_at=NOW)
    rows = selected(path)
    assert state(rows, start=NOW + timedelta(hours=2), kind="weather", complete=True)["state"] == "available"
    assert state(rows, start=NOW + timedelta(hours=5), kind="weather", complete=True)["state"] == "stale"


def test_empty_incomplete_collection_is_missing_but_explicit_complete_empty_is_available(tmp_path):
    path = tmp_path / "models.db"
    record = normalized_record(subject_id="team:1", payload={"players": []})
    append_observation(path, record, observed_at=NOW)
    assert state(selected(path), complete=True)["state"] == "missing"
    assert state((), complete=True)["state"] == "missing"
    append_observation(path, {**record, "source_revision": "r2", "complete": True}, observed_at=NOW + timedelta(minutes=1))
    result = state(selected(path, cutoff=NOW + timedelta(minutes=1)), cutoff=NOW + timedelta(minutes=1), complete=True)
    assert result["state"] == "available"
    assert result["coverage"] == "complete"


def test_partial_player_fact_never_becomes_complete_team_coverage(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    rows = selected(path)
    assert state(rows, complete=False)["state"] == "available"
    assert state(rows, complete=False)["coverage"] == "incomplete"
    assert state(rows, complete=True)["state"] == "missing"


@pytest.mark.parametrize("payload", [{}, {"players": []}, {"status": None}])
def test_no_reported_player_fact_cannot_become_available_by_disabling_collection_requirement(tmp_path, payload):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(payload=payload), observed_at=NOW)
    assert state(selected(path), complete=False)["state"] == "missing"


@pytest.mark.parametrize("kind", ["availability", "expected_lineup", "workload_coverage"])
def test_operational_expiry_tightens_before_kickoff_and_preserves_stricter_source_limits(tmp_path, kind):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(kind=kind), observed_at=NOW)
    rows = selected(path)
    assert state(rows, cutoff=NOW + timedelta(hours=5), start=NOW + timedelta(hours=10), kind=kind)["state"] == "available"
    assert state(rows, cutoff=NOW + timedelta(hours=6), start=NOW + timedelta(hours=10), kind=kind)["state"] == "stale"
    assert state(rows, cutoff=NOW + timedelta(minutes=29), start=NOW + timedelta(hours=1), kind=kind)["state"] == "available"
    assert state(rows, cutoff=NOW + timedelta(minutes=30), start=NOW + timedelta(hours=1), kind=kind)["state"] == "stale"
    assert state(rows, cutoff=NOW + timedelta(minutes=5), kind=kind, source_max_age_seconds={"api-football": 300})["state"] == "stale"


def test_confirmed_lineup_expires_at_kickoff_or_stricter_source_deadline(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(kind="confirmed_lineup", complete=True, payload={"players": ["player:7"]}), observed_at=NOW)
    rows = selected(path)
    assert state(rows, kind="confirmed_lineup", start=NOW + timedelta(minutes=60))["fresh_until"] == "2026-09-07T13:00:00.000000Z"
    assert state(rows, cutoff=NOW + timedelta(minutes=60), kind="confirmed_lineup", start=NOW + timedelta(minutes=60))["state"] == "not_applicable"
    assert state(rows, cutoff=NOW + timedelta(minutes=5), kind="confirmed_lineup", source_max_age_seconds={"api-football": 300})["state"] == "stale"


def test_schedule_change_and_cancellation_invalidate_event_bound_factors(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    old = selected(path)
    assert selected(path, schedule="s2") == ()
    moved = freshness_policy("availability", schedule_revision="s2", requires_complete=False)
    assert factor_state(old, cutoff=NOW, scheduled_start=NOW + timedelta(hours=12), policy=moved)["state"] == "missing"
    assert state(old, event_status="cancelled")["state"] == "not_applicable"
    append_observation(path, normalized_record(kind="event_status", subject_id="fixture:1", payload={"status": "cancelled"}), observed_at=NOW)
    assert state(selected(path))["state"] == "not_applicable"


def test_immutable_completed_workload_has_no_wall_clock_expiry_but_walkover_is_not_normal_load(tmp_path):
    path = tmp_path / "models.db"
    record = normalized_record(kind="workload", source_schema="completed-workload-v1", complete=True,
                               payload={"status": "completed", "duration_minutes": None, "games": 21})
    append_observation(path, record, observed_at=NOW)
    much_later = NOW + timedelta(days=30)
    result = state(selected(path, cutoff=much_later), cutoff=much_later, start=much_later + timedelta(days=1), kind="workload", complete=True)
    assert result["state"] == "available"
    assert result["fresh_until"] is None
    assert selected(path)[0]["payload"]["duration_minutes"] is None
    append_observation(path, {**record, "source_revision": "r2", "payload": {"status": "walkover", "games": None}}, observed_at=NOW + timedelta(hours=1))
    assert state(selected(path, cutoff=much_later), cutoff=much_later, start=much_later + timedelta(days=1), kind="workload", complete=True)["state"] == "not_applicable"


@pytest.mark.parametrize("status", ["scheduled", "started", None])
def test_uncompleted_workload_cannot_claim_immutable_completed_fact(tmp_path, status):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(kind="workload", complete=True, payload={"status": status, "duration_minutes": 100}), observed_at=NOW)
    assert state(selected(path), kind="workload", complete=True)["state"] == "missing"


@pytest.mark.parametrize("field", ["kind", "event_status"])
def test_policy_rejects_non_scalar_statuses_with_typed_error(field):
    policy = freshness_policy("availability", schedule_revision="s1")
    policy[field] = []
    with pytest.raises(ContextContractError):
        factor_state((), cutoff=NOW, scheduled_start=NOW + timedelta(hours=1), policy=policy)


def test_changed_operational_expiry_must_have_new_policy_version():
    policy = freshness_policy("availability", schedule_revision="s1")
    policy["availability_max_age_seconds"] = 86400
    with pytest.raises(ContextContractError, match="version"):
        factor_state((), cutoff=NOW, scheduled_start=NOW + timedelta(hours=1), policy=policy)
    policy["version"] = "test-new-operational-policy-v2"
    assert factor_state((), cutoff=NOW, scheduled_start=NOW + timedelta(hours=1), policy=policy)["policy_version"] == policy["version"]


def test_native_player_ids_not_names_define_distinct_facts(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(payload={"name": "Same Name", "status": "out"}), observed_at=NOW)
    append_observation(path, normalized_record(subject_id="player:8", payload={"name": "Same Name", "status": "available"}), observed_at=NOW)
    rows = selected(path)
    assert {row["subject_id"] for row in rows} == {"player:7", "player:8"}
    assert state(rows)["state"] == "available"


def test_equal_time_revisions_are_conflicting_not_lexically_selected(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(source_revision="zzz"), observed_at=NOW)
    append_observation(path, normalized_record(source_revision="aaa", payload={"status": "available"}), observed_at=NOW)
    rows = selected(path)
    assert len(rows) == 2
    assert state(rows)["state"] == "conflicting"
    assert state(rows, source_precedence=["api-football"])["state"] == "conflicting"


def test_sources_remain_conflicting_unless_explicit_complete_precedence_policy_resolves(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    append_observation(path, normalized_record(source="official-club", source_schema="confirmed-status-v1", payload={"status": "available"}), observed_at=NOW + timedelta(minutes=1))
    rows = selected(path, cutoff=NOW + timedelta(minutes=1))
    assert state(rows, cutoff=NOW + timedelta(minutes=1))["state"] == "conflicting"
    assert state(rows, cutoff=NOW + timedelta(minutes=1), source_precedence=["official-club", "api-football"])["state"] == "available"
    assert state(rows, cutoff=NOW + timedelta(minutes=1), source_precedence=["official-club"])["state"] == "conflicting"


def test_stale_secondary_source_does_not_report_past_fresh_until_for_available_fact(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    append_observation(path, normalized_record(source="official-club"), observed_at=NOW + timedelta(hours=7))
    result = state(selected(path, cutoff=NOW + timedelta(hours=7)), cutoff=NOW + timedelta(hours=7), start=NOW + timedelta(hours=20))
    assert result["state"] == "available"
    assert result["fresh_until"] == "2026-09-08T01:00:00.000000Z"


def test_historical_retrospective_import_cannot_displace_genuinely_known_revision(tmp_path):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    late = normalized_record(source_revision="r2", published_at=NOW.isoformat(), publication_proof={"verified": True}, payload={"status": "available"})
    append_observation(path, late, observed_at=NOW + timedelta(days=1))
    assert len(selected(path)) == 1
    rows = selected(path, mode="historical")
    assert [(row["evidence_class"], row["payload"]["status"]) for row in rows] == [("prospective", "out"), ("retrospective", "available")]
    assert rows[1]["observed_at"] == "2026-09-08T12:00:00.000000Z"
    assert rows[1]["publication_resolution"] is None
    assert selected(path, mode="historical", proof_resolver="unknown-provider") == rows
    with pytest.raises(ContextContractError, match="callback"):
        selected(path, mode="historical", proof_resolver=lambda row: True)


def test_no_real_archive_source_is_implicitly_certified():
    assert observations._ARCHIVE_RESOLVERS == {}


def register_test_only_archive(monkeypatch, *, change=None):
    """Mechanics-only LOCAL fixture; this certifies no actual archive source."""
    def resolve(row):
        result = {"schema": 1, "resolver_id": "TEST-ONLY", "resolver_version": "fixture-v1",
                  "content_digest": row["content_digest"], "published_at": row["published_at"],
                  "evidence_locator": "secured-local-fixture:1", "evidence_digest": "a" * 64}
        result["resolution_digest"] = digest(result)
        if change:
            result.update(change)
        return result
    monkeypatch.setattr(observations, "_ARCHIVE_RESOLVERS", {"TEST-ONLY": observations._RegisteredArchiveResolver(
        source="api-football", resolver_id="TEST-ONLY", resolver_version="fixture-v1", resolve_local=resolve,
    )})


def test_registered_archive_binds_content_publication_and_resolution_without_rewriting_receipt(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    late = normalized_record(published_at=(NOW - timedelta(hours=1)).isoformat(), publication_proof={"ref": "fixture:1"})
    receipt = append_observation(path, late, observed_at=NOW + timedelta(days=1))
    register_test_only_archive(monkeypatch)
    row = selected(path, mode="historical", proof_resolver="TEST-ONLY")[0]
    assert row["digest"] == receipt
    assert row["evidence_class"] == "archival_verified"
    assert row["observed_at"] == "2026-09-08T12:00:00.000000Z"
    assert row["effective_at"] == "2026-09-07T11:00:00.000000Z"
    assert row["publication_resolution"]["content_digest"] == row["content_digest"]
    # A verified historical publication is not a freshly checked live list.
    assert state((row,))["state"] == "missing"


@pytest.mark.parametrize("change", [
    {"content_digest": "b" * 64}, {"schema": True}, {"resolver_version": "other"},
    {"published_at": "2026-09-07T11:00:00+00:00"}, {"evidence_digest": "not-a-hash"},
    {"resolution_digest": "c" * 64}, {"unknown": "field"},
])
def test_malformed_claimed_recognized_archive_resolution_fails_integrity(tmp_path, monkeypatch, change):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(published_at=(NOW - timedelta(hours=1)).isoformat(), publication_proof={"ref": "fixture:1"}), observed_at=NOW + timedelta(days=1))
    register_test_only_archive(monkeypatch, change=change)
    with pytest.raises(ContextIntegrityError):
        selected(path, mode="historical", proof_resolver="TEST-ONLY")


def test_archival_and_prospective_choose_effective_causal_time_and_retain_equal_time_conflict(tmp_path, monkeypatch):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    append_observation(path, normalized_record(source_revision="r2", published_at=NOW.isoformat(), publication_proof={"ref": "fixture:1"}, payload={"status": "available"}), observed_at=NOW + timedelta(days=1))
    register_test_only_archive(monkeypatch)
    rows = selected(path, mode="historical", proof_resolver="TEST-ONLY")
    assert len(rows) == 2
    assert {row["evidence_class"] for row in rows} == {"prospective", "archival_verified"}
    assert len({row["effective_at"] for row in rows}) == 1


@pytest.mark.parametrize("changes", [
    {"complete": 1}, {"observed_at": NOW.isoformat()}, {"subject_id": "Same Name"},
    {"payload": {"nested": {"bookmaker": "X"}}}, {"payload": {"minimum_odds": 2}},
    {"payload": {"bestOdds": 1.2}}, {"payload": {"nested": {"bookmakerId": 8}}},
    {"payload": {"minimum odds": 1.2}}, {"payload": {"minimumodds": 1.2}},
    {"payload": {"PRICE1": 1.2}},
    {"payload": {"duration_minutes": float("nan")}}, {"payload": {"duration_minutes": float("inf")}},
    {"payload": {"native_id": object()}}, {"payload": {1: "not-a-string"}},
    {"payload": [{"status": "out"}]}, {"payload": {"sets": (1, 2)}},
    {"sport": "tennis"}, {"valid_until": NOW.isoformat()},
])
def test_malformed_or_price_contaminated_observation_is_rejected_before_write(tmp_path, changes):
    path = tmp_path / "models.db"
    with pytest.raises(ContextContractError):
        append_observation(path, normalized_record(**changes), observed_at=NOW)
    assert not path.exists()


@pytest.mark.parametrize("sql,args", [
    ("UPDATE context_contents SET payload=?", (b'{"unexpected":true}',)),
    ("UPDATE context_observations SET observed_at=?", ("2026-09-07T12:00:00+00:00",)),
    ("UPDATE context_observations SET source=?", ("rewritten",)),
    ("UPDATE context_observations SET content_digest=?", ("f" * 64,)),
])
def test_persisted_corruption_is_not_repaired_or_silently_reingested(tmp_path, sql, args):
    path = tmp_path / "models.db"
    record = normalized_record()
    append_observation(path, record, observed_at=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute(sql, args)
    with pytest.raises(ContextIntegrityError):
        selected(path)
    with pytest.raises(ContextIntegrityError):
        append_observation(path, record, observed_at=NOW)


def test_parallel_exact_ingestion_is_atomic_idempotent_and_retains_genuine_rechecks(tmp_path):
    path = tmp_path / "models.db"
    record = normalized_record()
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda index: append_observation(path, record, observed_at=NOW + timedelta(seconds=index // 2)), range(12)))
    assert len(set(receipts)) == 6
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM context_contents").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM context_observations").fetchone() == (6,)


@pytest.mark.parametrize("case", ["future_retrospective", "wrong_revision", "unrelated_wrong_revision", "stale_secondary", "precedence_loser"])
def test_review_r1_audit_and_usable_references_have_distinct_exact_meanings(tmp_path, case):
    path = tmp_path / "models.db"
    current = append_observation(path, normalized_record(), observed_at=NOW)
    options = {}
    if case == "future_retrospective":
        ignored = append_observation(path, normalized_record(source_revision="r2", payload={"status": "available"}), observed_at=NOW + timedelta(days=1))
        rows = selected(path, mode="historical")
    elif case in {"wrong_revision", "unrelated_wrong_revision"}:
        event = "api-football:football:2" if case == "unrelated_wrong_revision" else "api-football:football:1"
        ignored = append_observation(path, normalized_record(event_key=event, schedule_revision="s2"), observed_at=NOW)
        rows = selected(path) + observations_as_of(path, event, cutoff=NOW, schedule_revision="s2")
    elif case == "stale_secondary":
        ignored = append_observation(path, normalized_record(source="old-source", valid_from=(NOW - timedelta(hours=7)).isoformat()), observed_at=NOW - timedelta(hours=7))
        rows = selected(path)
    else:
        ignored = append_observation(path, normalized_record(source="secondary", payload={"status": "available"}), observed_at=NOW)
        rows = selected(path)
        options["source_precedence"] = ["api-football", "secondary"]
    if case == "unrelated_wrong_revision":
        with pytest.raises(ContextContractError, match="scope"):
            state(rows, **options)
    else:
        result = state(rows, **options)
        assert result["state"] == "available"
        assert result["refs"] == sorted([current, ignored])  # audit only
        assert result["usable_refs"] == [current]


@pytest.mark.parametrize("status", ["cancelled", "started", "completed"])
def test_review_r2_foreign_status_rejected_before_any_early_decision(tmp_path, status):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    append_observation(path, normalized_record(event_key="api-football:football:2", kind="event_status", subject_id="fixture:2", payload={"status": status}), observed_at=NOW)
    rows = selected(path) + observations_as_of(path, "api-football:football:2", cutoff=NOW, schedule_revision="s1")
    for policy_status in ("scheduled", "cancelled"):
        with pytest.raises(ContextContractError, match="scope"):
            state(rows, event_status=policy_status)


@pytest.mark.parametrize("validity", ["future", "expired", "future_receipt", "different_schedule", "current"])
def test_review_r2_status_receipt_interval_and_schedule_control_invalidation(tmp_path, validity):
    path = tmp_path / "models.db"
    current = append_observation(path, normalized_record(), observed_at=NOW)
    changes = {}
    observed = NOW
    if validity == "future": changes["valid_from"] = (NOW + timedelta(hours=1)).isoformat()
    if validity == "expired": changes.update(valid_from=(NOW - timedelta(hours=1)).isoformat(), valid_until=NOW.isoformat())
    if validity == "future_receipt": observed += timedelta(hours=1)
    if validity == "different_schedule": changes["schedule_revision"] = "s2"
    status = append_observation(path, normalized_record(kind="event_status", subject_id="fixture:1", payload={"status": "cancelled"}, **changes), observed_at=observed)
    rows = selected(path, mode="historical")
    if validity == "different_schedule": rows += selected(path, schedule="s2")
    result = state(rows)
    assert result["refs"] == sorted([current, status])
    assert result["state"] == ("not_applicable" if validity == "current" else "available")
    assert result["usable_refs"] == ([] if validity == "current" else [current])


def test_review_r3_stale_substantive_fact_cannot_refresh_empty_payload(tmp_path):
    path = tmp_path / "models.db"
    stale = append_observation(path, normalized_record(valid_from=(NOW - timedelta(hours=7)).isoformat()), observed_at=NOW - timedelta(hours=7))
    empty = append_observation(path, normalized_record(source="fresh-empty-source", payload={"status": None}), observed_at=NOW)
    result = state(selected(path))
    assert result["state"] == "missing"
    assert result["refs"] == sorted([stale, empty])
    assert result["usable_refs"] == []
    assert result["fresh_until"] is None


@pytest.mark.parametrize("requires_complete", [True, False])
def test_review_r3_selected_collection_cannot_borrow_loser_completeness_or_deadline(tmp_path, requires_complete):
    path = tmp_path / "models.db"
    loser = append_observation(path, normalized_record(subject_id="team:1", complete=True, payload={"players": []}), observed_at=NOW)
    winner = append_observation(path, normalized_record(source="official", subject_id="team:1", complete=False, payload={"players": ["player:7"]}), observed_at=NOW)
    result = state(selected(path), complete=requires_complete, source_precedence=["official", "api-football"],
                   source_max_age_seconds={"official": 1200, "api-football": 60})
    assert result["state"] == ("missing" if requires_complete else "available")
    assert result["coverage"] == "incomplete"
    assert result["refs"] == sorted([loser, winner])
    assert result["usable_refs"] == ([] if requires_complete else [winner])
    assert result["fresh_until"] == (None if requires_complete else "2026-09-07T12:20:00.000000Z")


@pytest.mark.parametrize("field,value", [("competition", "140"), ("format", "120min"), ("sport", "tennis")])
def test_review_r2_complete_event_scope_is_checked_before_status_decision(tmp_path, field, value):
    path = tmp_path / "models.db"
    append_observation(path, normalized_record(), observed_at=NOW)
    extra = {field: value, "kind": "event_status", "subject_id": "fixture:1", "payload": {"status": "cancelled"}}
    if field == "sport": extra["event_key"] = "api-football:tennis:1"
    append_observation(path, normalized_record(**extra), observed_at=NOW)
    rows = selected(path)
    if field == "sport": rows += observations_as_of(path, extra["event_key"], cutoff=NOW, schedule_revision="s1")
    with pytest.raises(ContextContractError, match="scope"):
        state(rows)


def test_review_controls_missing_and_conflicting_states_have_no_usable_refs(tmp_path):
    assert state(())["usable_refs"] == []
    path = tmp_path / "models.db"
    first = append_observation(path, normalized_record(), observed_at=NOW)
    second = append_observation(path, normalized_record(source_revision="r2", payload={"status": "available"}), observed_at=NOW)
    result = state(selected(path))
    assert result["state"] == "conflicting"
    assert result["usable_refs"] == []
    assert result["refs"] == sorted([first, second])


@pytest.mark.parametrize("preferred_empty", [True, False])
def test_review_control_empty_payload_cannot_borrow_substance_through_source_selection(tmp_path, preferred_empty):
    path = tmp_path / "models.db"
    fact = append_observation(path, normalized_record(), observed_at=NOW)
    empty = append_observation(path, normalized_record(source="official", payload={"status": None}), observed_at=NOW)
    options = {"source_precedence": ["official", "api-football"]} if preferred_empty else {}
    result = state(selected(path), **options)
    assert result["refs"] == sorted([fact, empty])
    assert result["state"] == ("missing" if preferred_empty else "available")
    assert result["usable_refs"] == ([] if preferred_empty else [fact])
    if preferred_empty:
        assert result["fresh_until"] is None
