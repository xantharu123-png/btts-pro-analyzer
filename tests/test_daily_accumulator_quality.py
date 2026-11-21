from datetime import date, datetime, time, timedelta, timezone
import json
import sqlite3

import pytest


UTC = timezone.utc
BEGIN = date(2030, 1, 1)


def at(day, hour=8):
    return datetime.combine(day, time(hour), UTC)


def slip(day, size=3):
    point = dict(odds=1.25, observed_at=at(day).isoformat(), fetched_at=at(day).isoformat())
    return dict(day=str(day), size=size, policy="daily-accumulators-v1", arm="reference", bookmaker_id="api-football:8", price_status="confirmed",
                captured_at=at(day).isoformat(), decision_at=at(day).isoformat(),
                legs=[dict(forecast_id=f"{day.toordinal() * 10 + i:064x}", sport="football", model_version="model1",
                           event_key=f"football:{day.toordinal() * 10 + i}", market_key="DC_1X", selection="1X",
                           starts_at=at(day, 19).isoformat(), offers={"api-football:8": dict(point)}, probability=0.8) for i in range(size)])


def test_result_all_legs_exactly_bound_and_captured_before_actual_start():
    from daily_accumulator_quality import grade
    s = slip(BEGIN)
    results = {leg["forecast_id"]: dict(leg, decision_at=at(BEGIN, 7), recorded_at=at(BEGIN, 7),
                effective_start=at(BEGIN, 19), causal=True, invalid_result_evidence=False, outcome="WIN")
               for leg in s["legs"]}
    assert grade(s, results) == "WIN"
    s["legs"][0].update(selection="Heimsieg oder Remis", evidence_selection="1X")
    assert grade(s, results) == "WIN"
    first, second, third = results.values()
    first["outcome"] = "LOSS"
    assert grade(s, results) == "LOSS"
    second["outcome"] = "VOID"
    assert grade(s, results) == "VOID"
    first["outcome"] = second["outcome"] = "WIN"
    third["outcome"] = "UNRESOLVED"
    assert grade(s, results) == "OPEN"
    third["outcome"] = "WIN"
    third["market_key"] = "DC_X2"
    assert grade(s, results) == "UNMATCHED"
    third["market_key"] = "DC_1X"
    third["recorded_at"] = at(BEGIN, 9)
    assert grade(s, results) == "UNMATCHED"
    third["recorded_at"] = at(BEGIN, 7)
    third["effective_start"] = at(BEGIN, 6)
    assert grade(s, results) == "UNMATCHED"


def cohort(start, days, *, wins=3):
    return [(slip(start + timedelta(days=i)), "WIN" if i % 4 < wins else "LOSS") for i in range(days)]


def test_chronological_frozen_fit_and_scope_specific_chance():
    from daily_accumulator_quality import fit, review, chance_for_slip
    first = BEGIN + timedelta(days=85)
    last = first + timedelta(days=167)
    issued = at(last + timedelta(days=9))
    model = fit(cohort(BEGIN, 80), issued_at=at(first-timedelta(days=1)),
                test_from=first, test_through=last)
    artifact = review(model, cohort(first, 168), issued_at=issued)
    entry, = artifact["groups"].values()
    assert entry["test_days"] == 168 and entry["weeks"] >= 24
    assert entry["wins"] == 126 and entry["brier_difference_ci"][1] < 0
    assert entry["passed"] is True
    future = slip(last + timedelta(days=10))
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) == pytest.approx(.75, abs=.01)
    # Neither historical retroactive release nor stale, wrong scope, price-only or past-start bars.
    assert chance_for_slip(slip(first), artifact, as_of=issued) is None
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 20)) is None
    assert chance_for_slip(slip(last+timedelta(days=200)), artifact, as_of=at(last+timedelta(days=200), 9)) is None
    future["legs"][0]["model_version"] = "new-model"
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) is None
    assert chance_for_slip(future, {}, as_of=issued) is None
    assert chance_for_slip(future, None, as_of=issued) is None
    future["legs"][0]["model_version"] = "model1"
    future["bookmaker_id"] = "odds-api:example"
    for leg in future["legs"]:
        leg["offers"]["odds-api:example"] = leg["offers"].pop("api-football:8")
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) is None
    future["bookmaker_id"] = "api-football:2"  # different bookmaker, same supported source
    for leg in future["legs"]:
        leg["offers"]["api-football:2"] = leg["offers"].pop("odds-api:example")
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) is not None
    future["legs"][0]["offers"]["api-football:2"]["odds"] = 1.19
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) is None
    future["legs"][0]["offers"]["api-football:2"]["odds"] = 1.20
    entry["offset"] = 5  # accidental corruption -> no value
    assert chance_for_slip(future, artifact, as_of=at(last+timedelta(days=10), 9)) is None


def test_no_release_on_incomplete_holdout_or_nonimprovement_or_duplicate_days():
    from daily_accumulator_quality import fit, review
    first, last = BEGIN+timedelta(days=81), BEGIN+timedelta(days=248)
    model = fit(cohort(BEGIN, 80), issued_at=at(first-timedelta(days=1)), test_from=first, test_through=last)
    with pytest.raises(ValueError):
        review(model, [], issued_at=at(first))
    with pytest.raises(ValueError):
        fit(cohort(BEGIN, 82), issued_at=at(first), test_from=first, test_through=last)
    cutoff = at(last+timedelta(days=9))
    def row(rows):
        artifact = review(model, rows, issued_at=cutoff)
        return next(iter(artifact["groups"].values()))
    assert not row(cohort(first, 90))["passed"]
    assert not row(cohort(first, 168, wins=2))["passed"]
    held = cohort(first,168)
    with pytest.raises(ValueError):
        row(held+held)
    held[-1] = held[-1][0], "UNMATCHED"
    assert not row(held)["passed"]


def test_outcomes_from_real_forecast_evidence_and_missing_database(tmp_path, monkeypatch):
    import forecast_evidence as ev
    from daily_accumulator_quality import settled_receipts
    s = slip(BEGIN)
    path = tmp_path / "forecasts.db"
    assert list(settled_receipts([s], path, known_at=at(BEGIN+timedelta(days=1)))) == [(s, "UNMATCHED")]
    assert not path.exists()
    monkeypatch.setattr(ev, "_now", lambda: at(BEGIN, 7))
    candidates = []
    for i, leg in enumerate(s["legs"]):
        ident = 4000 + i
        leg["event_key"] = f"football:{ident}"
        candidates.append(dict(candidate_id=f"{ident}:DC_1X", fixture_id=ident, source="football_challenge",
            event_identity=leg["event_key"], sport="Fußball", market_key="DC_1X", selection="1X",
            scheduled_start=leg["starts_at"], probability=.8, minimum_odds=2., policy_version="p1",
            modeled_at=at(BEGIN, 6).isoformat(), input_cutoff_at=at(BEGIN, 5).isoformat()))
    ev.record_forecast_run(dict(generated_at=at(BEGIN, 7).isoformat(), selection_policy_version="p1",
                           model_candidates=candidates), path, "model1")
    with sqlite3.connect(path) as conn:
        ids = dict(conn.execute("select event_key,forecast_id from forecast_rows"))
    for leg in s["legs"]:
        leg["forecast_id"] = ids[leg["event_key"]]
    monkeypatch.setattr(ev, "_now", lambda: at(BEGIN+timedelta(days=1)))
    for leg in s["legs"]:
        ev.append_result(leg["event_key"], "DC_1X", "1X", "WIN", observed_at=at(BEGIN,22),
                         provenance=dict(provider="api-football",provider_event_id=leg["event_key"].split(":")[1],
                            source_record_id="fulltime-v1",payload_sha256="a"*64,settlement_rule="native-fulltime-v1"),db_path=path)
    assert list(settled_receipts([s],path,known_at=at(BEGIN+timedelta(days=1)))) == [(s,"WIN")]
    s["legs"][1]["probability"] = .9
    assert list(settled_receipts([s],path,known_at=at(BEGIN+timedelta(days=1)))) == [(s,"UNMATCHED")]


def test_cli_refuses_missing_archives_and_leaves_old_artifact_intact(tmp_path):
    from scripts.daily_accumulator_review import main
    output = tmp_path/"old.json"
    output.write_text(json.dumps({"original": 1}), encoding="utf-8")
    receipts, evidence = tmp_path/"absent.db", tmp_path/"evidence.db"
    tomorrow = datetime.now(UTC).date()+timedelta(days=2)
    assert main(["fit", "--receipts", str(receipts), "--evidence", str(evidence),
                 "--training-from", str(tomorrow-timedelta(days=10)), "--test-from", str(tomorrow),
                 "--test-through", str(tomorrow+timedelta(days=167)), "--output", str(output)]) != 0
    assert json.loads(output.read_text()) == {"original": 1}
    assert not receipts.exists() and not evidence.exists()
