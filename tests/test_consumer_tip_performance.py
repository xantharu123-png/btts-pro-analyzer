from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3

import pytest

import consumer_tip_history as history
import forecast_evidence as evidence
from consumer_tip_performance import build_consumer_tip_performance_report
from market_consensus import parse_fixture_consensus


NOW = datetime(2030, 1, 1, 10, tzinfo=timezone.utc)
START = NOW+timedelta(hours=4)
AS_OF = NOW+timedelta(days=1)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_now", lambda: NOW)
    monkeypatch.setattr(evidence, "_now", lambda: NOW)
    return tmp_path/"consumer.db", tmp_path/"forecast.db"


def row(fixture=1, **changes):
    return dict(candidate_id=f"{fixture}:BTTS_YES", fixture_id=fixture,
                event_identity=f"football:{fixture}", sport="Fußball",
                source="football_challenge", market_key="BTTS_YES", selection="Ja",
                scheduled_start=START.isoformat(), probability=.6,
                model_version="m1", policy_version="p1",
                modeled_at=(NOW-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(NOW-timedelta(minutes=10)).isoformat(), **changes)


def quote(item, odds=2.0, clock=NOW):
    payload = {"response": [{"fixture": {"id": item["fixture_id"], "date": item["scheduled_start"]},
        "update": clock.isoformat(), "bookmakers": [
            {"id": index, "name": f"Book {index}", "bets": [
                {"name": "Both Teams Score", "values": [{"value": "Yes", "odd": str(odds)}]}]}
            for index in (1, 2, 3)]}]}
    return parse_fixture_consensus(payload, [item], fetched_at=clock)[item["candidate_id"]].to_dict()


def freeze(db, item):
    return evidence.record_forecast_run(dict(generated_at=NOW.isoformat(),
        selection_policy_version="p1", model_candidates=[item]), db, "m1")["forecast_ids"][0]


def publish(db, item, *, surface="wettfinder:top", clock=NOW):
    return history.record_tip_publication(db, surface=surface, rows=[item], as_of=clock)


def settle(db, monkeypatch, fixture=1, outcome="WIN", actual_start=None):
    monkeypatch.setattr(evidence, "_now", lambda: AS_OF)
    proof = dict(provider="api-football", provider_event_id=str(fixture), source_record_id=f"terminal:{fixture}",
                 payload_sha256="a"*64, settlement_rule="football-fulltime-v1")
    if actual_start:
        proof["actual_starts_at"] = actual_start.isoformat()
    return evidence.append_result(f"football:{fixture}", "BTTS_YES", "Ja", outcome,
        observed_at=START+timedelta(hours=2), provenance=proof, db_path=db)


def report(paths, **kwargs):
    return build_consumer_tip_performance_report(*paths, from_day="2030-01-01",
        through_day="2030-01-01", as_of=AS_OF, **kwargs)


def test_no_history_never_falls_back_to_internal_forecast_pool(paths):
    freeze(paths[1], row())
    result = report(paths)
    assert result["cohort"] == "archived_publications" and result["summary"]["selections"] == 0
    assert not paths[0].exists()


def test_empty_publication_is_honest_and_readonly(paths):
    history.record_tip_publication(paths[0], surface="daily3", rows=[], as_of=NOW)
    before = hashlib.sha256(paths[0].read_bytes()).hexdigest()
    result = report(paths)
    assert result["publication_count"] == 1 and result["summary"]["selections"] == 0
    assert hashlib.sha256(paths[0].read_bytes()).hexdigest() == before
    assert not paths[1].exists()


def test_roi_uses_actual_publication_price_not_original_forecast_entry(paths, monkeypatch):
    item = row()
    item["reference_quote"] = quote(item, odds=3)
    forecast_id = freeze(paths[1], item)
    captured = NOW+timedelta(minutes=30)
    monkeypatch.setattr(history, "_now", lambda: captured)
    item["reference_quote"] = quote(item, odds=1.5, clock=captured)
    item["forecast_id"] = forecast_id
    publish(paths[0], item, clock=captured)
    settle(paths[1], monkeypatch)
    result = report(paths, unit_stake=10)
    assert result["summary"]["wins"] == 1
    assert result["summary"]["hypothetical_net_amount"] == 5
    assert result["selections"][0]["entry_odds"] == 1.5
    assert result["publication_quote_source"] == "actual_publication_capture"


def test_first_capture_not_best_later_price_or_probability(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item, odds=1.5)
    publish(paths[0], item)
    later = NOW+timedelta(minutes=20)
    monkeypatch.setattr(history, "_now", lambda: later)
    item["reference_quote"] = quote(item, odds=5, clock=later)
    publish(paths[0], item, clock=later, surface="daily3")
    settle(paths[1], monkeypatch)
    data = report(paths)
    assert data["summary"]["hypothetical_net_units"] == .5
    assert data["archive_revisions_collapsed"] == 1
    only_daily3 = report(paths, surface="daily3")
    assert only_daily3["summary"]["hypothetical_net_units"] == 4


@pytest.mark.parametrize("kind", ["missing", "stale", "below_floor"])
def test_missing_stale_low_price_does_not_invent_profit_or_loss(paths, monkeypatch, kind):
    item = row()
    freeze(paths[1], item)
    if kind != "missing":
        item["reference_quote"] = quote(item, odds=1.1 if kind == "below_floor" else 2,
            clock=NOW-timedelta(hours=2) if kind == "stale" else NOW)
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    result = report(paths)
    assert result["summary"]["wins"] == 1
    assert result["summary"]["hypothetical_resolved_quote_samples"] == 0
    assert result["summary"]["hypothetical_roi"] is None
    assert result["selections"][0]["quote_status"] == kind


def test_forecast_hint_is_rebound_not_trusted_and_mismatch_is_gap(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["forecast_id"] = "b"*64
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    data = report(paths)
    assert data["summary"]["selections"] == 0
    assert data["linkage_gap_reasons"] == {"archived_forecast_binding_mismatch": 1}


def test_unknown_model_clocks_and_frozen_riskobet_snapshot_are_gaps(paths):
    item = row()
    freeze(paths[1], item)
    item["model_version"] = "another-model"
    item["snapshot_id"] = "a"*64
    publish(paths[0], item)
    data = report(paths)
    assert data["linkage_gap_reasons"] == {"unlinked_frozen_snapshot": 1}
    assert data["summary"]["selections"] == 0


@pytest.mark.parametrize("field", ["model_version", "policy_version", "modeled_at", "input_cutoff_at"])
def test_missing_original_model_identity_cannot_be_inferred_from_matching_probability(paths, field):
    item = row()
    freeze(paths[1], item)
    item[field] = None
    publish(paths[0], item)
    result = report(paths)
    assert result["summary"]["selections"] == 0
    assert result["linkage_gap_reasons"] == {"missing_exact_model_identity": 1}


@pytest.mark.parametrize("change", ["wrong_market", "wrong_selection", "wrong_fixture", "after_capture", "after_observation", "stale", "no_bookmaker"])
def test_publication_quote_is_revalidated_independently_of_archive_status(change):
    from consumer_tip_performance import _published_quote
    tip = dict(row(), starts_at=START.isoformat(), sport="football")
    tip["quote"] = dict(status="observed", odds=2.0, bookmaker_id="1",
        observed_at=NOW.isoformat(), fetched_at=NOW.isoformat(), source="API-Football Mehrbuchmacher",
        starts_at=START.isoformat(), market_key="BTTS_YES", bet_name="Both Teams Score", selection="Yes", fixture_id=1)
    field, value = {
        "wrong_market": ("market_key", "TOTAL_OVER_25"),
        "wrong_selection": ("selection", "No"),
        "wrong_fixture": ("fixture_id", 2),
        "after_capture": ("fetched_at", (NOW+timedelta(seconds=1)).isoformat()),
        "after_observation": ("observed_at", (NOW+timedelta(seconds=1)).isoformat()),
        "stale": ("observed_at", (NOW-timedelta(hours=1)).isoformat()),
        "no_bookmaker": ("bookmaker_id", ""),
    }[change]
    tip["quote"][field] = value
    status, odds = _published_quote(tip, NOW, START)
    assert status == ("stale" if change == "stale" else "invalid")
    assert odds is None


def test_actual_kickoff_before_capture_prevents_profit(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item)
    publish(paths[0], item)
    settle(paths[1], monkeypatch, actual_start=NOW-timedelta(minutes=1))
    data = report(paths)
    assert data["summary"]["selections"] == 0
    assert data["linkage_gap_reasons"] == {"publication_after_actual_start": 1}


def test_unresolved_results_and_voids_are_not_losses(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    item["reference_quote"] = quote(item)
    publish(paths[0], item)
    assert report(paths)["summary"]["unresolved"] == 1
    settle(paths[1], monkeypatch, outcome="VOID")
    summary = report(paths)["summary"]
    assert summary["voids"] == 1 and summary["losses"] == 0
    assert summary["hypothetical_resolved_quote_samples"] == 0


def test_complete_report_is_nonmutating_for_both_databases(paths, monkeypatch):
    item = row()
    freeze(paths[1], item)
    publish(paths[0], item)
    settle(paths[1], monkeypatch)
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    monkeypatch.setattr(evidence, "_connect", lambda *_: pytest.fail("writer invoked"))
    report(paths)
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == before


def test_report_metadata_excludes_archives_of_unrelated_event_days(paths, monkeypatch):
    old = NOW-timedelta(days=3)
    monkeypatch.setattr(history, "_now", lambda: old)
    item = row()
    item.update(scheduled_start=(old+timedelta(hours=4)).isoformat(),
                modeled_at=(old-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    publish(paths[0], item, clock=old)
    data = report(paths)
    assert data["publication_count"] == data["unique_archived_selections"] == 0


def test_mixed_inventory_counts_only_target_event_day(paths):
    today, future = row(), row(2)
    future["scheduled_start"] = (START+timedelta(days=2)).isoformat()
    freeze(paths[1], today)
    freeze(paths[1], future)
    history.record_tip_publication(paths[0], surface="wettfinder:top", rows=[today, future], as_of=NOW)
    data = report(paths)
    assert data["unique_archived_selections"] == data["summary"]["selections"] == 1


def test_archived_counter_uses_actual_day_and_preserves_first_capture(paths, monkeypatch):
    old = NOW-timedelta(days=2)
    item = row()
    item.update(scheduled_start=(old+timedelta(hours=4)).isoformat(),
                modeled_at=(old-timedelta(minutes=5)).isoformat(),
                input_cutoff_at=(old-timedelta(minutes=10)).isoformat())
    monkeypatch.setattr(history, "_now", lambda: old)
    monkeypatch.setattr(evidence, "_now", lambda: old)
    evidence.record_forecast_run(dict(generated_at=old.isoformat(),
        selection_policy_version="p1", model_candidates=[item]), paths[1], "m1")
    publish(paths[0], item, clock=old)
    monkeypatch.setattr(history, "_now", lambda: NOW)
    changed = dict(item, scheduled_start=START.isoformat())
    publish(paths[0], changed)
    settle(paths[1], monkeypatch, actual_start=START)
    data = report(paths)
    assert data["unique_archived_selections"] == data["summary"]["selections"] == 1
    assert data["selections"][0]["first_observed_at"] == old.isoformat()


SURFACE = "wettfinder_default_inventory"


def card(fixture=1, market="BTTS_YES", p=.72):
    return dict(row(fixture), candidate_id=f"{fixture}:{market}", market_key=market,
                probability=p, home_team="Home", away_team="Away",
                selection="Ja" if market == "BTTS_YES" else "Over")


def matchday(paths):
    data = report(paths, surface=SURFACE)
    assert "matchday" in data, "named Wettfinder inventory needs a separate first-card cohort"
    return data["matchday"]


def test_market_review_uses_original_leads_and_only_settled_exact_fresh_prices(paths, monkeypatch, capsys):
    import json
    from scripts.selection_performance_report import main

    items = [card(i) for i in range(1, 5)]
    items[0]["reference_quote"] = quote(items[0], odds=1.5)
    items[1]["reference_quote"] = quote(items[1], odds=4.0, clock=NOW-timedelta(hours=2))
    items[2]["reference_quote"] = quote(items[2], odds=2.0)
    for item in items:
        freeze(paths[1], item)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=items, as_of=NOW,
                                   event_lead_candidates=[item["candidate_id"] for item in items[:3]])
    settle(paths[1], monkeypatch, fixture=1, outcome="WIN")
    settle(paths[1], monkeypatch, fixture=2, outcome="LOSS")
    settle(paths[1], monkeypatch, fixture=4, outcome="WIN")
    before = [p.read_bytes() for p in paths]
    assert main(["--db", str(paths[1]), "--history-db", str(paths[0]), "--from-day", "2029-12-31",
                 "--through-day", "2030-01-01", "--as-of", AS_OF.isoformat(), "--market-review"]) == 0
    result = json.loads(capsys.readouterr().out)
    empty, day = result["daily"]
    assert empty["first_main_card"]["summary"]["decided"] == 0
    cohort = day["first_main_card"]["summary"]
    assert (cohort["wins"], cohort["losses"], cohort["open"], cohort["unmatched"]) == (1, 1, 1, 1)
    assert cohort["mean_model_probability"] == pytest.approx(.72)
    assert cohort["priced_decisions"] == 1 and cohort["hypothetical_roi"] == .5
    assert cohort["quote_statuses"] == {"fresh": 2, "stale": 1, "unverified": 1}
    assert cohort["stale_quote_reasons"] == {"both": 1}
    assert day["first_main_card"]["by_sport_and_market"]["football"]["btts"]["wins"] == 1
    assert day["all_distinct_markets"]["summary"]["wins"] == 2
    assert result["overall"]["first_main_card"]["summary"] == cohort
    assert [p.read_bytes() for p in paths] == before
    standard = matchday(paths)["first_main_card"]["rows"][0]
    assert "stale_quote_reason" not in standard and "hypothetical_return_units" not in standard


def test_market_review_rejects_excessive_completed_day_window(paths, capsys):
    from scripts.selection_performance_report import main

    with pytest.raises(SystemExit) as error:
        main(["--db", str(paths[1]), "--history-db", str(paths[0]), "--from-day", "2029-11-01",
              "--through-day", "2030-01-01", "--as-of", AS_OF.isoformat(), "--market-review"])
    assert error.value.code == 2
    assert "31" in capsys.readouterr().err


@pytest.mark.parametrize(("provider_minutes", "fetch_minutes", "expected"), [
    (150, 3, "provider"), (40, 36, "fetch"), (150, 36, "both"), (40, 30, "unknown"),
    (None, 3, "unknown"), (150, None, "unknown"), (30, 35, "unknown"), (0, -1, "unknown"),
])
def test_stale_quote_diagnostics_keep_both_clocks_and_do_not_invent_a_reason(provider_minutes, fetch_minutes, expected):
    from consumer_tip_performance import _stale_quote_reason

    clocks = {key: (NOW-timedelta(minutes=age)).isoformat()
              for key, age in [("observed_at", provider_minutes), ("fetched_at", fetch_minutes)] if age is not None}
    assert _stale_quote_reason(clocks, NOW) == expected


def test_matchday_keeps_first_card_despite_later_better_market(paths, monkeypatch):
    first, side, late = card(), card(market="TOTAL_OVER_25", p=.64), card(market="TOTAL_OVER_15", p=.88)
    other = dict(card(2), featured_role="primary")
    first["featured_role"] = "primary"
    for item in (first, side, late, other):
        freeze(paths[1], item)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[side, first, other], as_of=NOW)
    later = NOW+timedelta(minutes=15)
    monkeypatch.setattr(history, "_now", lambda: later)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[
        dict(late, featured_role="primary"), dict(first, featured_role="catalogue"), side], as_of=later)
    settle(paths[1], monkeypatch, outcome="LOSS")
    data = matchday(paths)
    main = data["first_main_card"]
    assert [(r["event_key"], r["market_key"]) for r in main["rows"]] == [
        ("football:1", "BTTS_YES"), ("football:2", "BTTS_YES")]
    assert [r["market_key"] for r in data["retrospective_catalogue_max"]["rows"]] == ["TOTAL_OVER_15", "BTTS_YES"]
    change, = data["first_vs_retrospective_differences"]
    assert (change["event_key"], change["reason"], change["first_market"], change["retrospective_market"]) == (
        "football:1", "different_market_in_later_inventory", "BTTS_YES", "TOTAL_OVER_15")
    assert data["all_distinct_markets"]["summary"]["selections"] == 4
    sport = main["by_sport"]["football"]
    assert (sport["games"], sport["selections"], sport["losses"], sport["open"], sport["decided"]) == (2, 2, 1, 1, 1)
    assert (sport["mean_announced_probability"], sport["hit_rate"], sport["announced_minus_actual_pp"]) == (.72, 0, 72)
    assert sport["fresh_quotes"] == 0 and sport["wins"] == sport["voids"] == sport["unmatched"] == 0
    assert all(v["ticket_count"] is None for v in data["tickets"].values())


def test_unlinked_first_winner_not_replaced_by_lower_or_later_linked_market(paths, monkeypatch):
    missing, lower, late = card(p=.83), card(market="TOTAL_OVER_25", p=.65), card(market="TOTAL_OVER_15", p=.91)
    missing["featured_role"] = "primary"
    for item in (lower, late):
        freeze(paths[1], item)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[missing, lower], as_of=NOW)
    later = NOW+timedelta(minutes=15)
    monkeypatch.setattr(history, "_now", lambda: later)
    publish(paths[0], late, surface=SURFACE, clock=later)
    summary = matchday(paths)["first_main_card"]
    assert summary["summary"]["unmatched"] == 1 and summary["summary"]["decided"] == 0
    assert summary["rows"][0]["market_key"] == "BTTS_YES"
    assert summary["rows"][0]["reason"] == "missing_exact_forecast_binding"


def test_incomplete_first_publication_is_gap_even_after_complete_republication(paths, monkeypatch):
    item = card()
    freeze(paths[1], item)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[item, {}], as_of=NOW)
    later = NOW+timedelta(minutes=20)
    monkeypatch.setattr(history, "_now", lambda: later)
    publish(paths[0], item, surface=SURFACE, clock=later)
    main = matchday(paths)["first_main_card"]
    assert main["summary"]["unmatched"] == 1
    assert main["rows"][0]["reason"] == "incomplete_first_publication"


def test_moved_event_unlinked_gap_belongs_to_actual_day(paths, monkeypatch):
    old = NOW-timedelta(days=2)
    item = dict(card(), scheduled_start=(old+timedelta(hours=2)).isoformat(),
                modeled_at=old.isoformat(), input_cutoff_at=old.isoformat())
    monkeypatch.setattr(history, "_now", lambda: old)
    publish(paths[0], item, surface=SURFACE, clock=old)
    freeze(paths[1], card())
    settle(paths[1], monkeypatch, actual_start=START)
    data = report(paths, surface=SURFACE)
    assert data["linkage_gap_reasons"] == {"missing_exact_forecast_binding": 1}
    assert data["matchday"]["first_main_card"]["summary"]["unmatched"] == 1


def test_matchday_cli_requires_original_history_and_never_mixes_surfaces(paths, capsys):
    import json
    from scripts.selection_performance_report import main
    publish(paths[0], card(), surface="daily3_default_plan")
    options = ["--db", str(paths[1]), "--matchday", "2030-01-01", "--as-of", AS_OF.isoformat()]
    with pytest.raises(SystemExit):
        main(options)
    assert main([*options, "--history-db", str(paths[0])]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "hypothetical_net_units" not in json.dumps(data)
    assert data["surface_filter"] == SURFACE
    assert data["matchday"]["first_main_card"]["summary"]["games"] == 0
    assert data["matchday"]["tickets"]["doublebet"]["ticket_count"] is None


def test_actual_start_from_another_market_prevents_post_start_scoring(paths, monkeypatch):
    lead, side = card(p=.75), card(market="TOTAL_OVER_25", p=.80)
    side["featured_role"] = "primary"
    for item in (lead, side):
        freeze(paths[1], item)
    later = NOW+timedelta(hours=2)
    monkeypatch.setattr(history, "_now", lambda: later)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[lead, side], as_of=later)
    settle(paths[1], monkeypatch, actual_start=NOW+timedelta(hours=1))
    proof = dict(provider="api-football", provider_event_id="1", source_record_id="terminal:side",
                 payload_sha256="b"*64, settlement_rule="football-fulltime-v1")
    evidence.append_result("football:1", "TOTAL_OVER_25", "Over", "WIN",
                           observed_at=START+timedelta(hours=2), provenance=proof, db_path=paths[1])
    views = matchday(paths)
    assert views["first_main_card"]["summary"]["wins"] == 0
    assert views["first_main_card"]["rows"][0]["reason"] == "publication_after_actual_start"


def test_conflicting_result_is_not_counted_as_an_open_game(paths, monkeypatch):
    item = dict(card(), featured_role="primary")
    freeze(paths[1], item)
    publish(paths[0], item, surface=SURFACE)
    settle(paths[1], monkeypatch, actual_start=START)
    settle(paths[1], monkeypatch, actual_start=START+timedelta(minutes=20))
    data = matchday(paths)["first_main_card"]
    assert data["summary"]["open"] == 0 and data["summary"]["unmatched"] == 1


def test_mixed_revision_and_tied_capture_do_not_manufacture_a_card(paths):
    initial = card()
    revised = dict(card(market="TOTAL_OVER_25", p=.80), model_version="another-revision")
    second = card(2)
    competing = card(2, market="TOTAL_OVER_25", p=.90)
    for item in (initial, second, competing):
        freeze(paths[1], item)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[initial, revised, second], as_of=NOW)
    publish(paths[0], competing, surface=SURFACE)
    first = matchday(paths)["first_inventory_reconstruction"]
    assert first["summary"]["unmatched"] == 2
    assert [r["reason"] for r in first["rows"]] == [
        "no_comparable_first_card_revision", "ambiguous_first_publication_clock"]
    assert all(r["market_key"] is None for r in first["rows"])


def test_legacy_inventory_without_pre_floor_anchor_is_not_evidence_of_displayed_lead(paths, monkeypatch):
    # The same post-floor receipt can be produced whether or not a stronger
    # lead from another revision was removed before serialization.
    visible = dict(card(), featured_role="featured")
    freeze(paths[1], visible)
    publish(paths[0], visible, surface=SURFACE)
    later = NOW + timedelta(minutes=20)
    monkeypatch.setattr(history, "_now", lambda: later)
    publish(paths[0], dict(visible, featured_role="primary"), surface=SURFACE, clock=later)
    settle(paths[1], monkeypatch)
    day = matchday(paths)
    strict = day["first_main_card"]
    assert strict["summary"]["wins"] == 0 and strict["summary"]["unmatched"] == 1
    assert strict["rows"][0]["reason"] == "no_archived_event_lead_role"
    assert strict["rows"][0]["tip_id"] is None
    assert strict["rows"][0]["first_observed_at"] == NOW.isoformat()
    assert day["first_card_evidence"] == dict(identified=0, missing=1,
                                               missing_reasons={"no_archived_event_lead_role": 1})
    assert day["first_inventory_reconstruction"]["summary"]["wins"] == 1


def test_sibling_actual_start_moves_exact_lead_into_new_zurich_day(paths, monkeypatch):
    old = NOW - timedelta(days=1)
    monkeypatch.setattr(history, "_now", lambda: old)
    monkeypatch.setattr(evidence, "_now", lambda: old)
    lead = dict(card(market="TOTAL_OVER_25"), featured_role="primary")
    sibling = card()
    for item in (lead, sibling):
        item.update(scheduled_start=(old+timedelta(hours=4)).isoformat(),
                    modeled_at=(old-timedelta(minutes=2)).isoformat(), input_cutoff_at=(old-timedelta(minutes=5)).isoformat())
    evidence.record_forecast_run(dict(generated_at=old.isoformat(), selection_policy_version="p1",
                                      model_candidates=[sibling, lead]), paths[1], "m1")
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[sibling, lead], as_of=old)
    settle(paths[1], monkeypatch, actual_start=START)
    proof = dict(provider="api-football", provider_event_id="1", source_record_id="terminal:side",
                 payload_sha256="b"*64, settlement_rule="football-fulltime-v1")
    evidence.append_result("football:1", "TOTAL_OVER_25", "Over", "LOSS",
                           observed_at=START+timedelta(hours=2), provenance=proof, db_path=paths[1])
    data = matchday(paths)["first_main_card"]
    assert data["summary"]["losses"] == 1 and data["summary"]["unmatched"] == 0
    assert data["rows"][0]["market_key"] == "TOTAL_OVER_25"


def test_versioned_event_lead_receipt_retains_tip_identity_global_role_and_first_clock(paths, monkeypatch):
    lead = dict(card(), featured_role="catalogue")
    other = dict(card(market="TOTAL_OVER_25", p=.82), featured_role="featured")
    freeze(paths[1], lead)
    legacy = history.record_tip_publication(paths[0], surface="other", rows=[other, lead], as_of=NOW)
    saved = history.record_tip_publication(paths[0], surface=SURFACE, rows=[other, lead], as_of=NOW,
                                          event_lead_candidates=[lead["candidate_id"]])
    later = NOW + timedelta(minutes=5)
    monkeypatch.setattr(history, "_now", lambda: later)
    repeat = history.record_tip_publication(paths[0], surface=SURFACE, rows=[other, lead], as_of=later,
                                           event_lead_candidates=[lead["candidate_id"]])
    assert legacy["status"] == saved["status"] == "recorded" and repeat["status"] == "unchanged"
    archived, = history.read_tip_publications(paths[0], surface=SURFACE)
    old, = history.read_tip_publications(paths[0], surface="other")
    leads, = history.read_tip_publications(paths[0], surface="wettfinder_default_event_leads")
    assert archived["tip_ids"] == old["tip_ids"] and leads["tip_ids"] == [old["tip_ids"][1]]
    assert leads["inventory_id"] == archived["publication_id"]
    assert [t["featured_role"] for t in archived["tips"]] == ["featured", "catalogue"]
    settle(paths[1], monkeypatch)
    scored, = matchday(paths)["first_main_card"]["rows"]
    assert (scored["market_key"], scored["status"], scored["first_observed_at"]) == ("BTTS_YES", "WIN", NOW.isoformat())


@pytest.mark.parametrize("keys", [["absent"], ["1:BTTS_YES", "1:TOTAL_OVER_25"], ["1:BTTS_YES", "1:BTTS_YES"]])
def test_rejects_invalid_primary_reference_without_touching_history(paths, keys):
    result = history.record_tip_publication(paths[0], surface=SURFACE,
             rows=[card(), card(market="TOTAL_OVER_25")], as_of=NOW, event_lead_candidates=keys)
    assert result["status"] == "rejected" and not paths[0].exists()


def test_later_first_visible_page_binds_its_own_revision_and_clock_not_the_inventory(paths, monkeypatch):
    first, second = card(1), card(2)
    edited = dict(second, probability=.79)
    freeze(paths[1], first)
    freeze(paths[1], second)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[first, second], as_of=NOW,
                                   event_lead_candidates=[first["candidate_id"]])
    later = NOW + timedelta(minutes=10)
    monkeypatch.setattr(history, "_now", lambda: later)
    monkeypatch.setattr(evidence, "_now", lambda: later)
    evidence.record_forecast_run(dict(generated_at=later.isoformat(), selection_policy_version="p1",
                                  model_candidates=[edited]), paths[1], "m1")
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[first, edited], as_of=later,
                                   event_lead_candidates=[edited["candidate_id"]])
    score = matchday(paths)["first_main_card"]["rows"]
    assert [(r["event_key"], r["first_observed_at"], r["probability"]) for r in score] == [
        ("football:1", NOW.isoformat(), .72), ("football:2", later.isoformat(), .79)]
    assert all(r["forecast_id"] and r["status"] == "UNRESOLVED" for r in score)


def test_kickoff_during_capture_keeps_other_inventory_rows_and_marks_receipt_partial(paths, monkeypatch):
    expired = dict(card(), scheduled_start=(NOW+timedelta(seconds=10)).isoformat())
    monkeypatch.setattr(history, "_now", lambda: NOW+timedelta(seconds=11))
    saved = history.record_tip_publication(paths[0], surface=SURFACE, rows=[expired, card(2)], as_of=NOW,
                                           event_lead_candidates=[expired["candidate_id"]])
    assert saved["status"] == "recorded" and saved["skipped_tips"] == 1
    base, = history.read_tip_publications(paths[0], surface=SURFACE)
    assert not base["complete"] and len(base["tips"]) == 1


def test_repeated_pages_and_publication_runs_add_only_never_witnessed_event_leads(paths, monkeypatch):
    games = [card(i) for i in (1, 2, 3)]
    for n, page in enumerate(([0, 1], [1, 2], [0, 1], [])):
        clock = NOW + timedelta(minutes=n)
        monkeypatch.setattr(history, "_now", lambda: clock)
        history.record_tip_publication(paths[0], surface=SURFACE, rows=games, as_of=clock,
            event_lead_candidates=[games[i]["candidate_id"] for i in page], source_run_id=str(n))
    proofs = history.read_tip_publications(paths[0], surface="wettfinder_default_event_leads")
    events = [(t["event_key"], p["first_observed_at"]) for p in proofs for t in p["tips"]]
    assert sorted(events) == [("football:1", NOW.isoformat()), ("football:2", NOW.isoformat()),
                              ("football:3", (NOW+timedelta(minutes=1)).isoformat())]
    assert len(proofs) == 3


def test_foreign_capture_clock_cannot_write_child_before_committed_parent(paths, monkeypatch):
    later = NOW+timedelta(minutes=3)
    monkeypatch.setattr(history, "_now", lambda: later)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[card()], as_of=NOW, event_lead_candidates=[])
    monkeypatch.setattr(history, "_now", lambda: NOW)
    saved = history.record_tip_publication(paths[0], surface=SURFACE, rows=[card()], as_of=NOW,
                                           event_lead_candidates=["1:BTTS_YES"])
    assert saved["status"] == "rejected"
    assert history.read_tip_publications(paths[0], surface="wettfinder_default_event_leads") == []


def test_same_market_and_side_at_later_first_visibility_is_not_a_different_pick(paths, monkeypatch):
    item = card()
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[item], as_of=NOW, event_lead_candidates=[])
    later = NOW+timedelta(minutes=5)
    monkeypatch.setattr(history, "_now", lambda: later)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[dict(item, probability=.74)], as_of=later,
                                   event_lead_candidates=[item["candidate_id"]])
    day = matchday(paths)
    assert day["first_main_card"]["rows"][0]["probability"] == .74
    assert day["first_vs_retrospective_differences"] == []


def test_incomplete_new_inventory_does_not_reserve_a_valid_siblings_first_witness(paths, monkeypatch):
    item = card()
    freeze(paths[1], item)
    saved = history.record_tip_publication(paths[0], surface=SURFACE, rows=[item, {}], as_of=NOW,
                                           event_lead_candidates=[item["candidate_id"]])
    assert saved["skipped_tips"] == 1
    later = NOW + timedelta(minutes=2)
    monkeypatch.setattr(history, "_now", lambda: later)
    history.record_tip_publication(paths[0], surface=SURFACE, rows=[item], as_of=later,
                                   event_lead_candidates=[item["candidate_id"]])
    scored, = matchday(paths)["first_main_card"]["rows"]
    assert (scored["first_observed_at"], scored["status"]) == (later.isoformat(), "UNRESOLVED")
