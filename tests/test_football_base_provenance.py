"""Synthetic opt-in baseline provenance, not claimed live source coverage."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

import challenge_engine as engine
from context_models.contracts import digest, validate_history_refs, validate_reference_weights
from model_artifacts import canonical_bytes


START = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)


def fixture(number, day, home, away, *, source=None, xg=True, goals=True):
    row = {"fixture": {"id": number, "date": (START + timedelta(days=day)).isoformat()},
           "league": {"id": 39, "season": 2026},
           "teams": {"home": {"id": home, "name": f"Team {home}"}, "away": {"id": away, "name": f"Team {away}"}},
           "goals": {"home": day % 4 if goals else None, "away": day % 3 if goals else None},
           "challenge_stats": {"xg_home": 1 + day % 7 / 10, "xg_away": .7 + day % 5 / 10} if xg else {}}
    if source is not None:
        row["challenge_source"] = source
    return row


def history():
    rows = []
    for day in range(32):
        pairs = [(1, 3), (4, 2), (5, 6), (7, 8)] if day % 2 == 0 else [(3, 1), (2, 4), (6, 5), (8, 7)]
        for home, away in pairs:
            rows.append(fixture(len(rows) + 1, day, home, away, xg=day % 5 != 0))
    return rows


def target():
    return fixture(10001, 36, 1, 2, xg=False, goals=False)


def record_map(rows):
    return {digest(engine.football_base_history_record(row)): engine.football_base_history_record(row) for row in rows}


def reconstructed(model, records, *, home=1, away=2):
    rates = []
    for side in ("home", "away"):
        head = model["reference_weights"]["heads"][side]
        branches = {}
        for name, component in head["components"].items():
            local_team = home if (side == "home") == name.endswith("attack") else away
            values = {}
            for metric in ("goals", "xg"):
                term = component[metric]
                if term is None:
                    continue
                weighted = []
                for sample in term["samples"]:
                    record = records[sample["ref"]]
                    own = record["home_id"] == local_team
                    scorer_is_home = own == name.endswith("attack")
                    value = record[f"{metric}_{'home' if scorer_is_home else 'away'}"]
                    weighted.append(sample["weight"] * value)
                values[metric] = sum(weighted) + term["prior_weight"] * term["prior_value"]
            branches[name] = sum(component["metric_weights"][metric] * value for metric, value in values.items())
        rates.append(sum(head["outer_weights"][period] * sum(
            head["pair_weights"][period][role] * branches[f"{period}_{role}"] for role in ("attack", "defense")
        ) for period in ("venue", "form")))
    return tuple(rates)


def test_opt_in_does_not_change_one_bit_of_the_legacy_model_output():
    raw = history()
    normal = engine._fixture_model(target(), raw)
    # Captured from f876df0 BEFORE the opt-in producer existed.
    assert digest(normal) == "5f711bff5c840febb82fc96eda4f11819e5d210a893e6b4ea373fa147f307d5c"
    opted = engine._fixture_model(target(), raw, include_provenance=True)
    assert {key: value for key, value in opted.items() if key not in {"history_refs", "reference_weights"}} == normal
    assert canonical_bytes({key: opted[key] for key in normal}) == canonical_bytes(normal)
    assert "history_refs" not in normal and "reference_weights" not in normal


def test_exact_venue_form_prior_and_xg_terms_reconstruct_existing_rates():
    raw = history()
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert validate_history_refs(model["history_refs"]) == model["history_refs"]
    assert validate_reference_weights(model["reference_weights"], model["history_refs"], family="football:goals:90min") == model["reference_weights"]
    assert reconstructed(model, record_map(raw)) == pytest.approx(model["active_lambdas"], abs=1e-12)
    for head in model["reference_weights"]["heads"].values():
        assert head["outer_weights"] == {"venue": .75, "form": .25}
        for name, component in head["components"].items():
            count, prior = (12, 4) if name.startswith("venue") else (6, 3)
            assert component["prior_raw_weight"] == prior
            assert len(component["goals"]["samples"]) == count
            assert component["goals"]["prior_weight"] == prior / (count + prior)
            assert all(sample["weight"] == 1 / (count + prior) for sample in component["goals"]["samples"])
            assert len(component["goals"]["prior_refs"]) == len(raw)
            assert all(sample["weight"] == 1 / len(raw) for sample in component["goals"]["prior_refs"])


def test_no_source_binding_does_not_promote_positive_ids_or_team_names():
    model = engine._fixture_model(target(), history(), include_provenance=True)
    assert all(ref["event_join"] == ref["roster_join"] == "unresolved" and ref["native_event_key"] is None for ref in model["history_refs"])
    for head in model["reference_weights"]["heads"].values():
        assert all(component["team_join"] == "unresolved" for component in head["components"].values())


def test_future_fixture_and_unusable_scores_cannot_enter_any_weighted_reference():
    raw = history()
    ordinary = engine._fixture_model(target(), raw, include_provenance=True)
    extra = [fixture(20001, 37, 1, 2), fixture(20002, 36, 1, 2), fixture(20003, 33, 1, 2, goals=False)]
    revised = engine._fixture_model(target(), raw + extra, include_provenance=True)
    assert revised == ordinary


def test_individual_window_xg_subset_uses_its_own_normalizer_not_goal_count():
    raw = history()
    model = engine._fixture_model(target(), raw, include_provenance=True)
    records = record_map(raw)
    for head in model["reference_weights"]["heads"].values():
        for component in head["components"].values():
            if component["xg"] is not None:
                xg = component["xg"]
                actual = [sample["ref"] for sample in component["goals"]["samples"] if records[sample["ref"]]["xg_home"] is not None]
                assert {sample["ref"] for sample in xg["samples"]} == set(actual)
                count = len(actual)
                prior = component["prior_raw_weight"]
                assert all(sample["weight"] == 1 / (count + prior) for sample in xg["samples"])
                assert xg["prior_weight"] == prior / (count + prior)


def test_sparse_xg_is_not_claimed_as_used_and_one_missing_side_invalidates_the_pair():
    raw = history()
    for row in raw:
        row["challenge_stats"] = {"xg_home": 3.0, "xg_away": None}
    model = engine._fixture_model(target(), raw, include_provenance=True)
    for head in model["reference_weights"]["heads"].values():
        for component in head["components"].values():
            assert component["xg"] is None
            assert component["metric_weights"] == {"goals": 1., "xg": 0.}
    assert reconstructed(model, record_map(raw)) == pytest.approx(model["active_lambdas"], abs=1e-12)


def test_csv_rows_keep_their_source_and_negative_identity_even_with_remapped_team_ids():
    raw = history()
    for row in raw:
        row["fixture"]["id"] = -row["fixture"]["id"]
        row["challenge_source"] = "football-data-results-only"
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert all(ref["source"] == "football-data" and int(ref["source_event_id"]) < 0 for ref in model["history_refs"])
    assert all(ref["native_event_key"] is None and ref["roster_join"] == "unresolved" for ref in model["history_refs"])
    assert reconstructed(model, record_map(raw)) == pytest.approx(model["active_lambdas"], abs=1e-12)


def test_price_fields_names_and_extra_provider_metadata_never_enter_record_hash_or_rates():
    raw = history()
    before = deepcopy(raw)
    expected = engine._fixture_model(target(), raw, include_provenance=True)
    records = record_map(raw)
    for row in raw:
        row["odds"] = {"bestPrice": 1.2}
        row["surprise_provider_field"] = "opaque"
        row["teams"]["home"]["name"] = "Changed display name"
        row["challenge_stats"]["bookmaker"] = "not a feature"
    assert engine._fixture_model(target(), raw, include_provenance=True) == expected
    assert record_map(raw) == records
    assert raw != before


def test_generator_histories_and_separate_team_pool_keep_exact_provenance():
    raw = history()
    team_pool = raw + [fixture(50001, 34, 1, 2)]
    result = engine._fixture_model(target(), iter(raw), iter(team_pool), include_provenance=True)
    assert result == engine._fixture_model(target(), raw, team_pool, include_provenance=True)
    assert reconstructed(result, record_map(team_pool)) == pytest.approx(result["active_lambdas"], abs=1e-12)


def test_repeated_identical_rows_aggregate_weights_without_rewriting_base_math():
    raw = history()
    raw.append(deepcopy(raw[-4]))
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert len({ref["ref"] for ref in model["history_refs"]}) == len(model["history_refs"])
    validate_reference_weights(model["reference_weights"], model["history_refs"], family="football:goals:90min")
    assert reconstructed(model, record_map(raw)) == pytest.approx(model["active_lambdas"], abs=1e-12)


def test_record_and_opt_in_model_are_pure_finite_canonical_json():
    raw = history()
    expected = deepcopy(raw)
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert json.loads(canonical_bytes(model))["reference_weights"] == model["reference_weights"]
    assert raw == expected
    assert engine.football_base_history_record(target())["goals_home"] is None


def native_transport(raw, current=None, *, appearances=True):
    """Synthetic internal adapter output; NOT a real API receipt or proof."""
    current = target() if current is None else current
    records = {}
    decision = START + timedelta(days=35)
    for row in [*raw, current]:
        record = engine.football_base_history_record(row)
        record_hash = digest(record)
        future = record["goals_home"] is None
        observed = decision - timedelta(minutes=1) if future else datetime.fromisoformat(record["scheduled_start"]) + timedelta(hours=3)
        payload = {"schema": 1, "source": "api-football", "source_schema": "fixtures-v3",
                   "observed_at": observed.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                   "record_hash": record_hash,
                   **{name: record[name] for name in ("fixture_id", "scheduled_start", "league_id", "season", "home_id", "away_id", "goals_home", "goals_away")},
                   "appearances": []}
        if appearances and not future:
            payload["appearances"] = [{"fixture_id": record["fixture_id"], "team_id": record[side + "_id"],
                "player_id": record[side + "_id"] * 1000 + 1, "minutes": 90., "started": True, "role": "M"} for side in ("home", "away")]
        envelope = {"kind": "football-base-native-evidence-v1", "payload": payload}
        records[record_hash] = {"digest": digest(envelope), **envelope}
    return {"schema": 1, "decision_at": decision.isoformat(timespec="microseconds").replace("+00:00", "Z"), "records": records}


def rehash_envelope(envelope):
    envelope["digest"] = digest({name: envelope[name] for name in ("kind", "payload")})


def test_verified_adapter_transport_binds_event_and_roster_without_changing_rates():
    raw = history()
    transport = native_transport(raw)
    before = deepcopy(transport)
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert result["reference_weights"]["kind"] == "football-goals-v1"
    assert all(row["event_join"] == row["roster_join"] == "verified_native" for row in result["history_refs"])
    assert all(row["source"] == "api-football" and row["native_event_key"] == "api-football:football:" + row["source_event_id"] for row in result["history_refs"])
    for side, head in result["reference_weights"]["heads"].items():
        for name, component in head["components"].items():
            expected_team = 1 if (side == "home") == name.endswith("attack") else 2
            assert component["team_id"] == f"api-football:team:{expected_team}"
            assert component["team_join"] == "verified_native"
    assert transport == before
    assert reconstructed(result, record_map(raw)) == pytest.approx(result["active_lambdas"], abs=1e-12)
    assert canonical_bytes({key: result[key] for key in engine._fixture_model(target(), raw)}) == canonical_bytes(engine._fixture_model(target(), raw))


def test_verified_match_identity_without_player_evidence_does_not_claim_roster_join():
    raw = history()
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=native_transport(raw, appearances=False))
    assert result["history_refs"]
    assert all(row["event_join"] == "verified_native" and row["roster_join"] == "unresolved" for row in result["history_refs"])


@pytest.mark.parametrize("minutes,started,role", [(None, None, None), (120., True, "M")])
def test_native_player_linkage_is_not_a_claim_of_complete_regulation_exposure(minutes, started, role):
    raw = history()
    transport = native_transport(raw)
    for envelope in transport["records"].values():
        for row in envelope["payload"]["appearances"]:
            row.update(minutes=minutes, started=started, role=role)
        rehash_envelope(envelope)
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert result["reference_weights"]["kind"] == "football-goals-v1"
    assert all(row["roster_join"] == "verified_native" for row in result["history_refs"])
    assert "regulation_minutes" not in canonical_bytes(result).decode()


@pytest.mark.parametrize("field,value", [("source", "another-source"), ("source_schema", "unknown-v1"),
    ("fixture_id", 9999), ("home_id", 9999), ("away_id", 9999), ("league_id", 44),
    ("season", 2025), ("goals_home", 99), ("goals_away", 99), ("record_hash", "f" * 64),
    ("scheduled_start", "2026-07-02T13:00:00.000000Z"), ("observed_at", "2026-12-01T12:00:00.000000Z"),
    ("observed_at", "2026-06-01T12:00:00.000000Z"), ("observed_at", "2026-07-01T15:00:00"),
    ("verified", True), ("odds", 1.5), ("fixture_id", True)])
def test_misbound_or_unknown_native_proof_never_hides_basis_or_certifies_sources(field, value):
    raw = history()
    transport = native_transport(raw)
    evidence = next(iter(transport["records"].values()))
    evidence["payload"][field] = value
    rehash_envelope(evidence)
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert result["reference_weights"] == {"schema": 1, "kind": "unavailable", "reason": "football-source-provenance-invalid"}
    assert result["history_refs"] == []
    assert {key: result[key] for key in engine._fixture_model(target(), raw)} == engine._fixture_model(target(), raw)


@pytest.mark.parametrize("field,value", [("fixture_id", 999), ("team_id", 999), ("player_id", 0),
    ("player_id", True), ("minutes", -1), ("minutes", float("nan")), ("minutes", True),
    ("started", 1), ("role", ""), ("odds", 1.1)])
def test_appearance_ids_types_and_scope_must_match_the_bound_fixture(field, value):
    raw = history()
    transport = native_transport(raw)
    evidence = next(iter(transport["records"].values()))
    evidence["payload"]["appearances"][0][field] = value
    if field == "minutes" and value != value:
        # A forged non-finite transport is rejected before canonical hashing.
        pass
    else:
        rehash_envelope(evidence)
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert result["reference_weights"]["kind"] == "unavailable"
    assert result["active_lambdas"] == engine._fixture_model(target(), raw)["active_lambdas"]


def test_duplicate_appearance_rows_do_not_create_verified_identity_coverage():
    raw = history()
    transport = native_transport(raw)
    evidence = next(iter(transport["records"].values()))
    evidence["payload"]["appearances"].append(deepcopy(evidence["payload"]["appearances"][0]))
    rehash_envelope(evidence)
    assert engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)["reference_weights"]["kind"] == "unavailable"


def test_payload_tampering_without_new_digest_never_gets_native_status():
    raw = history()
    transport = native_transport(raw)
    next(iter(transport["records"].values()))["payload"]["appearances"][0]["minutes"] = 80.
    assert engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)["reference_weights"]["kind"] == "unavailable"


@pytest.mark.parametrize("positive", [False, True])
def test_csv_identity_cannot_be_laundered_by_a_native_looking_proof(positive):
    raw = history()
    for row in raw:
        row["challenge_source"] = "football-data-results-only"
        if not positive:
            row["fixture"]["id"] *= -1
    transport = native_transport(raw)
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert result["reference_weights"]["kind"] == "unavailable"
    assert result["active_lambdas"] == engine._fixture_model(target(), raw)["active_lambdas"]


def test_api_tail_marker_alone_does_not_prove_remapped_team_or_player_identity():
    raw = history()
    for row in raw:
        row["challenge_source"] = "api-football-ft-tail"
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert all(row["roster_join"] == "unresolved" for row in model["history_refs"])
    assert all(component["team_join"] == "unresolved" for head in model["reference_weights"]["heads"].values() for component in head["components"].values())


def test_a_missing_target_binding_keeps_all_reference_team_joins_unresolved():
    raw = history()
    transport = native_transport(raw)
    transport["records"].pop(digest(engine.football_base_history_record(target())))
    model = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert model["reference_weights"]["kind"] == "football-goals-v1"
    assert all(component["team_join"] == "unresolved" for head in model["reference_weights"]["heads"].values() for component in head["components"].values())


def test_mixed_native_and_csv_component_is_not_an_implicitly_verified_team_window():
    raw = history()
    transport = native_transport(raw)
    replaced = raw[-4]
    transport["records"].pop(digest(engine.football_base_history_record(replaced)))
    replaced["fixture"]["id"] *= -1
    replaced["challenge_source"] = "football-data-results-only"
    model = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=transport)
    assert model["reference_weights"]["kind"] == "football-goals-v1"
    assert any(row["source"] == "football-data" and row["roster_join"] == "unresolved" for row in model["history_refs"])
    assert model["reference_weights"]["heads"]["home"]["components"]["form_attack"]["team_join"] == "unresolved"


def test_two_conflicting_rows_for_one_native_event_are_not_certified_as_two_events():
    raw = history()
    revised = deepcopy(raw[0])
    revised["goals"]["home"] += 1
    raw.append(revised)
    model = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=native_transport(raw))
    assert model["reference_weights"]["kind"] == "unavailable"
    assert model["active_lambdas"] == engine._fixture_model(target(), raw)["active_lambdas"]


@pytest.mark.parametrize("swap,verified", [(False, False), (True, False), (True, True)])
def test_reference_windows_bind_the_exact_selected_rows_even_when_team_sides_change(swap, verified):
    raw = history()
    current = target()
    if swap:
        current["teams"]["home"], current["teams"]["away"] = current["teams"]["away"], current["teams"]["home"]
    proof = native_transport(raw, current) if verified else None
    model = engine._fixture_model(current, raw, include_provenance=True, native_provenance=proof)
    home, away = current["teams"]["home"]["id"], current["teams"]["away"]["id"]
    assert reconstructed(model, record_map(raw), home=home, away=away) == pytest.approx(model["active_lambdas"], abs=1e-12)
    for side, head in model["reference_weights"]["heads"].items():
        for name, component in head["components"].items():
            team = home if (side == "home") == name.endswith("attack") else away
            eligible = [row for row in raw if team in (row["teams"]["home"]["id"], row["teams"]["away"]["id"])]
            if name.startswith("venue"):
                venue = "home" if team == home else "away"
                eligible = [row for row in eligible if row["teams"][venue]["id"] == team]
            expected = sorted(eligible, key=lambda row: row["fixture"]["date"], reverse=True)[:12 if name.startswith("venue") else 6]
            assert {sample["ref"] for sample in component["goals"]["samples"]} == set(record_map(expected))
            assert component["team_id"] == (f"api-football:team:{team}" if verified else None)
            assert component["team_join"] == ("verified_native" if verified else "unresolved")


def test_league_prior_refs_reconstruct_goal_priors_on_the_correct_side_even_for_xg_terms():
    raw = history()
    team_only = fixture(20001, 34, 1, 2)
    team_only["goals"] = {"home": 7, "away": 6}
    model = engine._fixture_model(target(), raw, raw + [team_only], include_provenance=True)
    records = record_map(raw)
    for side, head in model["reference_weights"]["heads"].items():
        for name, component in head["components"].items():
            for metric in ("goals", "xg"):
                term = component[metric]
                if term is None:
                    continue
                assert {row["ref"] for row in term["prior_refs"]} == set(records)
                value = sum(row["weight"] * (
                    (records[row["ref"]]["goals_home"] + records[row["ref"]]["goals_away"]) / 2
                    if name.startswith("form") else records[row["ref"]][f"goals_{side}"]
                ) for row in term["prior_refs"])
                assert term["prior_value"] == pytest.approx(value, abs=1e-12)
    assert digest(engine.football_base_history_record(team_only)) in {row["ref"] for row in model["history_refs"]}


def test_equal_date_selection_preserves_actual_stable_input_order_at_the_window_boundary():
    raw = history()
    first = fixture(20001, 31, 1, 2)
    second = deepcopy(first)
    second["fixture"]["id"] = 20002
    second["goals"] = {"home": 6, "away": 5}
    # Five newer observations leave exactly one place at the six-row boundary.
    recent = [fixture(21000 + day, day, 1, 2) for day in range(32, 37)]
    current = fixture(30000, 39, 1, 2, xg=False, goals=False)
    for ordered in ([first, second], [second, first]):
        model = engine._fixture_model(current, raw, [*recent, *ordered, *raw], include_provenance=True)
        component = model["reference_weights"]["heads"]["home"]["components"]["form_attack"]
        refs = {row["ref"] for row in component["goals"]["samples"]}
        assert digest(engine.football_base_history_record(ordered[0])) in refs
        assert digest(engine.football_base_history_record(ordered[1])) not in refs


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("schema", 2), ("records", []), ("records", None),
    ("decision_at", "2026-08-06T12:00:00.000000Z"),
    ("decision_at", "2026-08-05T12:00:00+00:00"),
    ("decision_at", "2026-08-05T12:00:00"), ("decision_at", None),
    ("price", 1.1), ("quote", None), ("approval", "claimed"),
])
def test_native_transport_boundary_is_closed_and_does_not_remove_the_base(field, value):
    raw = history()
    proof = native_transport(raw)
    proof[field] = value
    model = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=proof)
    assert model["reference_weights"]["kind"] == "unavailable"
    assert model["active_lambdas"] == engine._fixture_model(target(), raw)["active_lambdas"]


@pytest.mark.parametrize("field,value", [("kind", "arbitrary-kind"), ("digest", "a" * 64),
    ("digest", b"a" * 64), ("payload", []), ("quote", 1.2)])
def test_native_envelope_is_closed_and_requires_an_actual_typed_digest(field, value):
    raw = history()
    proof = native_transport(raw)
    next(iter(proof["records"].values()))[field] = value
    assert engine._fixture_model(target(), raw, include_provenance=True, native_provenance=proof)["reference_weights"]["kind"] == "unavailable"


def test_unused_native_record_cannot_be_claimed_as_an_input_to_this_baseline():
    raw = history()
    proof = native_transport(raw + [fixture(50001, 33, 5, 6)])
    result = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=proof)
    assert result["reference_weights"]["kind"] == "unavailable"


def test_current_target_native_binding_does_not_require_an_unplayed_match_to_have_goals():
    raw = history()
    current = target()
    current["goals"] = {"home": None, "away": None}
    proof = native_transport(raw, current)
    model = engine._fixture_model(current, raw, include_provenance=True, native_provenance=proof)
    assert model["reference_weights"]["kind"] == "football-goals-v1"
    assert digest(engine.football_base_history_record(current)) not in {row["ref"] for row in model["history_refs"]}


def test_unknown_source_ids_leave_historical_record_refs_available_but_never_native():
    raw = history()
    for row in raw:
        row["fixture"].pop("id")
        row.pop("league")
    model = engine._fixture_model(target(), raw, include_provenance=True)
    assert model["reference_weights"]["kind"] == "football-goals-v1"
    assert all(row["source_event_id"] == "record:" + row["ref"] and row["event_join"] == "unresolved" for row in model["history_refs"])
    assert reconstructed(model, record_map(raw)) == pytest.approx(model["active_lambdas"], abs=1e-12)


def test_naive_source_datetime_is_not_upgraded_to_an_actual_timestamp_but_keeps_legacy_basis():
    raw = history()
    raw[0]["fixture"]["date"] = raw[0]["fixture"]["date"].removesuffix("+00:00")
    normal = engine._fixture_model(target(), raw)
    opted = engine._fixture_model(target(), raw, include_provenance=True)
    assert opted["reference_weights"]["kind"] == "unavailable"
    assert canonical_bytes({key: opted[key] for key in normal}) == canonical_bytes(normal)


def test_same_numeric_fixture_id_from_csv_and_native_sources_cannot_collide_in_record_hash():
    raw = history()
    native_row = raw[0]
    csv_row = deepcopy(native_row)
    csv_row["challenge_source"] = "football-data-results-only"
    assert digest(engine.football_base_history_record(csv_row)) != digest(engine.football_base_history_record(native_row))
    proof = native_transport(raw)
    model = engine._fixture_model(target(), raw + [csv_row], include_provenance=True, native_provenance=proof)
    refs = [row for row in model["history_refs"] if row["source_event_id"] == str(native_row["fixture"]["id"])]
    assert len(refs) == 2
    assert {row["source"]: row["event_join"] for row in refs} == {"football-data": "unresolved", "api-football": "verified_native"}


@pytest.mark.parametrize("source", ["another-source", "custom-import-v1", "football-data"])
def test_explicit_foreign_source_marker_cannot_be_promoted_by_a_conflicting_native_claim(source):
    raw = history()
    raw[0]["challenge_source"] = source
    assert engine._fixture_model(target(), raw, include_provenance=True)["reference_weights"]["kind"] == "football-goals-v1"
    model = engine._fixture_model(target(), raw, include_provenance=True, native_provenance=native_transport(raw))
    assert model["reference_weights"]["kind"] == "unavailable"


def test_default_call_does_not_run_provenance_or_import_evidence_work(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("default calculation must not execute opt-in source work")
    monkeypatch.setattr(engine, "_football_reference_provenance", unexpected)
    monkeypatch.setattr(engine, "football_base_history_record", unexpected)
    assert digest(engine._fixture_model(target(), history(), native_provenance={"malformed": True})) == "5f711bff5c840febb82fc96eda4f11819e5d210a893e6b4ea373fa147f307d5c"


def test_unusable_unused_xg_metadata_cannot_discard_a_computable_goal_prior_basis():
    raw = history()
    # This row is a league GOAL prior input, never a team xG observation.
    raw[2]["challenge_stats"] = {"xg_home": 10 ** 1000, "xg_away": 1.0}
    normal = engine._fixture_model(target(), raw)
    assert normal is not None
    opted = engine._fixture_model(target(), raw, include_provenance=True)
    assert canonical_bytes({key: opted[key] for key in normal}) == canonical_bytes(normal)
    assert opted["reference_weights"]["kind"] == "unavailable"
