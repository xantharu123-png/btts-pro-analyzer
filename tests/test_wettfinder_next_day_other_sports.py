"""Heute und morgen, Schritt 3a (owner 10./11.11.2026): ice hockey, basketball and e-sport list tomorrow.

Like football's Folgetag, tomorrow's rows are Wettfinder model selections only. They never become a
public tip, a 15K row, a Doublebet choice, an evidence forecast or an archived publication before their
own match day, and RisikoBet keeps today. A failure there leaves today unchanged; an invalid tomorrow
row is withheld alone instead of erasing today's document.
"""
import json
from datetime import timedelta

import pytest

import wettfinder_automation as automation
from config_loader import AppConfig
from ev_signal_sources import (
    ModelSignal,
    _load_automated_wettfinder_document,
    automated_next_day,
    automated_wettfinder_forecasts,
    automated_wettfinder_signals,
    automated_wettfinder_snapshot,
    listed_next_day_signal,
)
from riskobet_automation import RiskSourceBatch
from riskobet_candidates import adapt_research_matchwinner
from tests.test_wettfinder_next_day import NOW, TODAY, TOMORROW, _next_day_snapshot, _refuse_context, _today_snapshot
from test_sports_prematch import NOW as TEAM_NOW, event, history


def _esport(match_id: int, start) -> ModelSignal:
    from betting_math import BETTING_POLICY_VERSION
    from esports_shadow import ESPORTS_MODEL_VERSION
    team_a, team_b = f"Team A{match_id}", f"Team B{match_id}"
    return ModelSignal(
        key=f"esports-{match_id}", label=f"CS2 · {team_a} vs {team_b} · Sieg {team_a}", probability=0.61,
        probability_haircut=0.1, evidence_stage="SHADOW",
        policy_version=f"{BETTING_POLICY_VERSION}:{ESPORTS_MODEL_VERSION}",
        detail="E-Sport-Pre-Match-Modell · Modell im Test", scheduled_start=start.isoformat(),
        source="esports_shadow", sport="E-Sport", event_label=f"CS2 · {team_a} vs {team_b}",
        market="Match Winner", selection=f"Sieg {team_a}", market_key="H2H", competitor_a=team_a,
        competitor_b=team_b, selected_competitor=team_a, competition="CS2", modeled_at=NOW.isoformat(),
        input_cutoff_at=NOW.isoformat(), model_version=ESPORTS_MODEL_VERSION, fixture_source="pandascore",
        provider_event_id=str(match_id),
    )


ESPORTS = (
    _esport(1, NOW + timedelta(hours=6)),  # today, 17:00 Zurich
    _esport(2, NOW + timedelta(hours=30)),  # tomorrow
    _esport(3, NOW + timedelta(hours=54)),  # the day after tomorrow
)


def _football(day):
    return _next_day_snapshot() if day == TOMORROW else _today_snapshot()


def _run(tmp_path, *, esports=ESPORTS, football_next_day=False, other=True, **kwargs):
    artifact = tmp_path / "wettfinder.json"
    document = automation.run_wettfinder(
        now=NOW, state_path=artifact, config=AppConfig(api_football_key="test"),
        football_scanner=_football, football_context_refresher=_refuse_context,
        football_quote_loader=lambda _rows: ({}, []), tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: list(esports), football_next_day=football_next_day,
        team_esports_next_day=other, **kwargs,
    )
    return artifact, document


def _keys(rows):
    return {row["key"] for row in rows}


def _rewrite(artifact, document, now=NOW):
    artifact.write_text(json.dumps(document), encoding="utf-8")
    return _load_automated_wettfinder_document(artifact, now=now)


def _recorder(monkeypatch):
    import forecast_evidence
    recorded = []

    def record(document, _db_path, *, model_version):
        recorded.extend(document["model_candidates"])
        return {"run_id": "run", "recorded": len(document["model_candidates"]), "rejected": [],
                "quotes_rejected": []}

    monkeypatch.setattr(forecast_evidence, "record_forecast_run", record)
    return recorded


def test_esport_tomorrow_rows_are_model_selections_only(tmp_path, monkeypatch):
    from daily3_selection import daily3_choices

    recorded = _recorder(monkeypatch)
    _reference_artifact, reference = _run(tmp_path / "a", other=False)
    artifact, document = _run(tmp_path / "b", evidence_db_path=tmp_path / "evidence.db")

    assert {"esports-1", "esports-2"} <= _keys(document["model_candidates"])
    assert "esports-3" not in _keys(document["model_candidates"])
    # Today's rows, tips and 15K list are exactly those of a run without tomorrow.
    assert [row for row in document["model_candidates"] if row["key"] != "esports-2"] == reference["model_candidates"]
    assert document["candidates"] == reference["candidates"]
    assert document["challenge_release_candidates"] == reference["challenge_release_candidates"]
    assert document["run_status"] == reference["run_status"] == "completed"
    assert document["next_day_search_date"] == "2030-01-02"
    assert document["sources"]["esports"]["next_day"] == {
        "search_date": "2030-01-02", "status": "listed", "candidate_count": 1, "games": 1}
    # The evidence ledger receives only today's rows.
    assert "esports-1" in _keys(recorded) and "esports-2" not in _keys(recorded)

    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    assert {signal.key for signal in forecasts if listed_next_day_signal(signal, now=NOW)} == {"esports-2"}
    assert "esports-1" in {signal.key for signal in forecasts}
    assert "esports-2" not in {signal.key for signal in automated_wettfinder_signals(artifact, now=NOW)}
    assert "esports-2" not in {choice.signal.key for choice in daily3_choices(forecasts, now=NOW)}


def test_isolated_runs_keep_esports_on_the_match_day_unless_asked(tmp_path):
    _artifact, document = _run(tmp_path, other=None)
    assert "esports-2" not in _keys(document["model_candidates"])
    assert "next_day_search_date" not in document and "next_day" not in document["sources"]["esports"]


def test_football_is_no_longer_the_only_next_day_gate(tmp_path):
    from ev_signal_sources import automated_next_day_sports

    artifact, document = _run(tmp_path)
    assert "football_next_day" not in document and automated_next_day(document, TODAY) is None
    assert automated_next_day_sports(document, TODAY) == {"e-sport"}
    assert _rewrite(artifact, document) is not None

    artifact, both = _run(tmp_path / "both", football_next_day=True)
    assert automated_next_day(both, TODAY) == TOMORROW
    assert automated_next_day_sports(both, TODAY) == {"fussball", "e-sport"}
    forecasts = automated_wettfinder_forecasts(artifact, now=NOW)
    listed = {signal.key for signal in forecasts if listed_next_day_signal(signal, now=NOW)}
    football_next = {row["key"] for row in both["model_candidates"] if row.get("fixture_id") == 2}
    assert football_next and listed == football_next | {"esports-2"}


@pytest.fixture
def esports_listed(tmp_path):
    artifact, _document = _run(tmp_path)
    return artifact, json.loads(artifact.read_text(encoding="utf-8"))


@pytest.mark.parametrize("change", [
    {"probability_haircut": 0.9}, {"minimum_odds": 9.0}, {"status": "RECOMMENDED"},
    {"bookmaker_odds": 2.0}, {"reference_price_status": "PLAYABLE"},
])
def test_invalid_tomorrow_row_is_withheld_alone(esports_listed, change):
    artifact, document = esports_listed
    rows = [dict(row, **change) if row["key"] == "esports-2" else row for row in document["model_candidates"]]
    loaded = _rewrite(artifact, {**document, "model_candidates": rows})

    assert loaded is not None
    assert _keys(loaded[0]["model_candidates"]) == _keys(document["model_candidates"]) - {"esports-2"}


@pytest.mark.price_policy("gate")  # under the floor a price inconsistency withholds only its row
def test_invalid_match_day_row_still_rejects_the_document(esports_listed):
    artifact, document = esports_listed
    for change in ({"probability_haircut": 0.9}, {"status": "RECOMMENDED"}, {"reference_price_status": "PLAYABLE"}):
        rows = [dict(row, **change) if row["key"] == "esports-1" else row for row in document["model_candidates"]]
        assert _rewrite(artifact, {**document, "model_candidates": rows}) is None


def test_undeclared_tomorrow_rows_still_reject_the_document(esports_listed):
    artifact, document = esports_listed
    assert _rewrite(artifact, document) is not None

    unmarked = dict(document)
    unmarked.pop("next_day_search_date")
    assert _rewrite(artifact, unmarked) is None
    assert _rewrite(artifact, {**document, "next_day_search_date": "2030-01-03"}) is None
    for summary in ({"search_date": "2030-01-02", "status": "failed"}, {"search_date": "2030-01-03", "status": "listed"},
                    None):
        sources = json.loads(json.dumps(document["sources"]))
        sources["esports"].pop("next_day")
        if summary is not None:
            sources["esports"]["next_day"] = summary
        assert _rewrite(artifact, {**document, "sources": sources}) is None
    # Tennis keeps the match day (its next day is a separate step).
    tomorrow = next(row for row in document["model_candidates"] if row["key"] == "esports-2")
    tennis = dict(tomorrow, key="tennis-9", candidate_id="tennis-9", sport="Tennis", source="tennis_shadow")
    assert _rewrite(artifact, {**document, "model_candidates": [*document["model_candidates"], tennis]}) is None
    # Tomorrow never becomes a tip or a 15K row.
    tip = dict(tomorrow, status="RECOMMENDED")
    assert _rewrite(artifact, {**document, "candidates": [*document["candidates"], tip]}) is None


@pytest.mark.price_policy("floor")  # unpriced rows below 65 % stay in the default inventory
def test_tip_archive_skips_tomorrow_esports(esports_listed, monkeypatch):
    import tip_publication

    artifact, _document = esports_listed
    archived = {}

    def record(surface, signals, **_kwargs):
        archived[surface] = [signal.key for signal in signals]
        return {"status": "recorded"}

    monkeypatch.setattr(tip_publication, "record_signal_catalog", record)
    assert tip_publication.record_automatic_publication(artifact, as_of=NOW)["status"] == "completed"
    assert "esports-1" in archived["wettfinder_default_inventory"]
    assert "esports-2" not in archived["wettfinder_default_inventory"]
    assert "esports-2" not in archived["daily3_default_plan"]


def test_tomorrow_respects_the_per_sport_reader_cap(tmp_path, monkeypatch):
    # The reader rejects a document with more rows per sport than its cap; tomorrow only uses what today leaves.
    monkeypatch.setattr(automation, "MAX_AUTOMATIC_OTHER_CANDIDATES_PER_SPORT", 1)
    artifact, document = _run(tmp_path)
    assert "esports-1" in _keys(document["model_candidates"]) and "esports-2" not in _keys(document["model_candidates"])
    assert document["sources"]["esports"]["next_day"]["status"] == "empty"
    assert "next_day_search_date" not in document and _rewrite(artifact, document) is not None


# --- Basketball and ice hockey ------------------------------------------------------------------

def _team_snapshot(sport, event_id, hours):
    target = event(sport, provider_event_id=event_id, starts_at=(TEAM_NOW + timedelta(hours=hours)).isoformat(),
                   source_observed_at=TEAM_NOW.isoformat())
    return adapt_research_matchwinner(sport, target, history(sport), modeled_at=TEAM_NOW).snapshot


TODAY_GAME = _team_snapshot("basketball", "bb-today", 6)  # 20:00 Zurich
NHL_OVERNIGHT = _team_snapshot("ice_hockey", "nhl-overnight", 12)  # 02:00 Zurich tomorrow, within 24 h: today
BB_TOMORROW = _team_snapshot("basketball", "bb-tomorrow", 26)
NHL_TOMORROW = _team_snapshot("ice_hockey", "nhl-tomorrow", 30)
BB_LATER = _team_snapshot("basketball", "bb-later", 50)


def _tomorrow_sources():
    return {
        "basketball": lambda: RiskSourceBatch(sport="basketball", snapshots=(BB_TOMORROW, BB_LATER)),
        "ice_hockey": RiskSourceBatch(sport="ice_hockey", snapshots=(NHL_OVERNIGHT, NHL_TOMORROW)),
    }


def _run_team(tmp_path, *, sources=None, other=True, now=TEAM_NOW):
    path = tmp_path / "wettfinder.json"
    document = automation.run_wettfinder(
        now=now, state_path=path, config=AppConfig(), football_scanner=lambda _day: {"candidates": []},
        tennis_loader=lambda **_kwargs: [], esports_loader=lambda **_kwargs: [],
        riskobet_sources={
            "basketball": RiskSourceBatch(sport="basketball", snapshots=(TODAY_GAME,)),
            "ice_hockey": RiskSourceBatch(sport="ice_hockey", snapshots=(NHL_OVERNIGHT,)),
        },
        riskobet_db_path=tmp_path / "risk.db", riskobet_latest_path=tmp_path / "risk.json",
        team_esports_next_day=other, next_day_team_sources=sources,
    )
    return path, document


def _events(rows):
    return {row["provider_event_id"] for row in rows}


def test_team_tomorrow_rows_are_model_selections_only(tmp_path, monkeypatch):
    recorded = _recorder(monkeypatch)
    _reference_path, reference = _run_team(tmp_path / "a", other=False)
    path, document = _run_team(tmp_path / "b", sources=_tomorrow_sources())

    assert _events(reference["model_candidates"]) == {"bb-today", "nhl-overnight"}
    assert _events(document["model_candidates"]) == {"bb-today", "nhl-overnight", "bb-tomorrow", "nhl-tomorrow"}
    assert len(document["model_candidates"]) == 8
    tomorrow = {"bb-tomorrow", "nhl-tomorrow"}
    assert [row for row in document["model_candidates"]
            if row["provider_event_id"] not in tomorrow] == reference["model_candidates"]
    assert document["candidates"] == document["challenge_release_candidates"] == []
    assert document["run_status"] == reference["run_status"]
    assert document["next_day_search_date"] == "2026-09-06"
    for sport, games in (("basketball", 1), ("ice_hockey", 1)):
        summary = document["sources"][sport]["next_day"]
        assert summary == {"search_date": "2026-09-06", "status": "listed", "source": "scanned",
                           "candidate_count": 2 * games, "games": games}
    # RisikoBet keeps today: tomorrow's snapshots never enter its run or catalog.
    latest = json.loads((tmp_path / "b" / "risk.json").read_text(encoding="utf-8"))
    assert {row["event_key"] for row in latest["snapshots"]} == {TODAY_GAME.event_key, NHL_OVERNIGHT.event_key}
    assert not tomorrow & _events(recorded)

    snapshot = automated_wettfinder_snapshot(path, now=TEAM_NOW)
    decided = snapshot.status.generated_at
    listed = {signal.provider_event_id for signal in snapshot.forecasts
              if listed_next_day_signal(signal, now=TEAM_NOW, decided_at=decided)}
    # Native NHL within 24 hours stays on the match day although its Zurich date is tomorrow.
    assert listed == tomorrow
    assert {signal.provider_event_id for signal in snapshot.forecasts} == _events(document["model_candidates"])
    assert snapshot.signals == ()


@pytest.mark.price_policy("floor")
def test_tip_archive_skips_tomorrow_team_games(tmp_path, monkeypatch):
    import tip_publication

    path, document = _run_team(tmp_path, sources=_tomorrow_sources())
    archived = {}

    def record(surface, signals, **_kwargs):
        archived[surface] = {signal.provider_event_id for signal in signals}
        return {"status": "recorded"}

    monkeypatch.setattr(tip_publication, "record_signal_catalog", record)
    assert tip_publication.record_automatic_publication(path, as_of=TEAM_NOW)["status"] == "completed"
    assert not {"bb-tomorrow", "nhl-tomorrow"} & archived["wettfinder_default_inventory"]


def test_failed_tomorrow_team_source_leaves_today_unchanged(tmp_path):
    _reference_path, reference = _run_team(tmp_path / "a", other=False)

    def broken():
        raise RuntimeError("provider down for key=secret")

    sources = {"basketball": broken, "ice_hockey": lambda: RiskSourceBatch(sport="basketball")}
    _path, document = _run_team(tmp_path / "b", sources=sources)

    assert document["model_candidates"] == reference["model_candidates"]
    assert document["run_status"] == reference["run_status"]
    assert "next_day_search_date" not in document
    assert document["sources"]["basketball"]["next_day"] == {
        "search_date": "2026-09-06", "status": "failed", "source": "scanned", "failure_type": "RuntimeError",
        "candidate_count": 0, "games": 0}
    assert document["sources"]["ice_hockey"]["next_day"]["status"] == "failed"
    assert "secret" not in json.dumps(document)


def test_invalid_tomorrow_team_row_is_withheld_alone(tmp_path):
    path, document = _run_team(tmp_path, sources=_tomorrow_sources())

    def tampered(event_id):
        index = next(i for i, row in enumerate(document["model_candidates"]) if row["provider_event_id"] == event_id)
        rows = [dict(row) for row in document["model_candidates"]]
        rows[index]["probability"] = 0.99
        return {**document, "model_candidates": rows}, rows[index]["key"]

    changed, key = tampered("bb-tomorrow")
    loaded = _rewrite(path, changed, now=TEAM_NOW)
    assert loaded is not None
    assert _keys(loaded[0]["model_candidates"]) == _keys(document["model_candidates"]) - {key}
    changed, _key = tampered("bb-today")
    assert _rewrite(path, changed, now=TEAM_NOW) is None


def test_tomorrow_rows_survive_a_scan_that_advances_the_runtime_clock(tmp_path):
    # Production reads hockey with the runtime clock: the snapshot is modeled after the run started.
    clock = [TEAM_NOW]

    def hockey():
        clock[0] = TEAM_NOW + timedelta(minutes=2)
        target = event("ice_hockey", provider_event_id="nhl-tomorrow",
                       starts_at=(TEAM_NOW + timedelta(hours=30)).isoformat(), source_observed_at=clock[0].isoformat())
        snapshot = adapt_research_matchwinner("ice_hockey", target, history("ice_hockey"), modeled_at=clock[0]).snapshot
        return RiskSourceBatch(sport="ice_hockey", snapshots=(snapshot,))

    path = tmp_path / "wettfinder.json"
    document = automation.run_wettfinder(
        state_path=path, clock=lambda: clock[0], config=AppConfig(),
        football_scanner=lambda _day: {"candidates": []}, tennis_loader=lambda **_kwargs: [],
        esports_loader=lambda **_kwargs: [],
        riskobet_sources={"basketball": RiskSourceBatch(sport="basketball", snapshots=(TODAY_GAME,))},
        riskobet_db_path=tmp_path / "risk.db", riskobet_latest_path=tmp_path / "risk.json",
        team_esports_next_day=True, next_day_team_sources={"ice_hockey": hockey},
    )

    assert document["sources"]["ice_hockey"]["next_day"]["status"] == "listed"
    assert "nhl-tomorrow" in _events(document["model_candidates"])
    forecasts = automated_wettfinder_forecasts(path, now=clock[0])
    assert {"bb-today", "nhl-tomorrow"} <= {signal.provider_event_id for signal in forecasts}


def test_later_run_without_research_reuses_tomorrows_team_rows(tmp_path):
    path, first = _run_team(tmp_path, sources=_tomorrow_sources())
    _path, later = _run_team(tmp_path, now=TEAM_NOW + timedelta(hours=1))

    tomorrow = {"bb-tomorrow", "nhl-tomorrow"}
    assert tomorrow <= _events(later["model_candidates"])
    assert {row["key"] for row in later["model_candidates"] if row["provider_event_id"] in tomorrow} == {
        row["key"] for row in first["model_candidates"] if row["provider_event_id"] in tomorrow}
    assert later["sources"]["basketball"]["next_day"]["source"] == "reused"
    assert _rewrite(path, later, now=TEAM_NOW + timedelta(hours=1)) is not None


# --- Default sources: one bounded schedule read per sport, never RisikoBet ----------------------

def test_default_research_sources_offer_tomorrow_only_when_research_is_due(monkeypatch):
    from datetime import date

    target = date(2030, 1, 1)
    sources, due = automation._riskobet_default_sources({}, now=NOW, target_date=target, research_due=True)
    assert set(sources["next_day"]) == {"basketball", "ice_hockey"}
    assert "next_day" not in due
    sources, _due = automation._riskobet_default_sources({}, now=NOW, target_date=target, research_due=False)
    assert "next_day" not in sources


def test_default_hockey_tomorrow_reads_one_schedule_window(monkeypatch):
    from datetime import datetime, timezone

    from test_nhl_overnight_window import NOW as NHL_NOW, OVERNIGHT, TARGET, source_fixture

    late = datetime(2026, 10, 17, 2, 30, tzinfo=timezone.utc)  # 04:30 Zurich tomorrow, after the 24 h horizon
    evening = datetime(2026, 10, 17, 18, tzinfo=timezone.utc)
    later = datetime(2026, 10, 18, 18, tzinfo=timezone.utc)
    _scanner, requests_seen, api_windows = source_fixture(monkeypatch, [OVERNIGHT, late, evening, later])
    sources, _due = automation._riskobet_default_sources({}, now=NHL_NOW, target_date=TARGET, research_due=True,
                                                          clock=lambda: NHL_NOW)
    requests_seen.clear()
    api_windows.clear()
    batch = sources["next_day"]["ice_hockey"]()

    assert {snapshot.starts_at for snapshot in batch.snapshots} == {late, evening}
    assert len(requests_seen) == 1 and api_windows == [(TARGET, TARGET + timedelta(days=1))]


def test_default_basketball_tomorrow_includes_tonights_north_american_games(monkeypatch):
    from datetime import date, datetime, timezone

    import scanners.basketball_scanner as basketball

    now = datetime(2026, 9, 5, 1, 35, tzinfo=timezone.utc)  # 03:35 Zurich
    target = date(2026, 9, 5)
    starts = {
        "today": datetime(2026, 9, 5, 18, tzinfo=timezone.utc),
        "tonight": datetime(2026, 9, 6, 0, 30, tzinfo=timezone.utc),  # 02:30 Zurich tomorrow, US date today
        "tomorrow": datetime(2026, 9, 6, 17, tzinfo=timezone.utc),
        "later": datetime(2026, 9, 7, 17, tzinfo=timezone.utc),
    }
    windows = []

    class Scanner:
        def __init__(self):
            self.errors = {}

        def get_upcoming_games(self, league, start, end):
            windows.append((league, start, end))
            return [event("basketball", provider_event_id=name, starts_at=start_at.isoformat())
                    for name, start_at in starts.items()]

        def get_completed_games(self, league, start, end, *, as_of=None):
            return history("basketball")

    monkeypatch.setattr(basketball, "BasketballScanner", Scanner)
    sources, _due = automation._riskobet_default_sources({}, now=now, target_date=target, research_due=True)
    batch = sources["next_day"]["basketball"]()

    assert windows == [("All", target, target + timedelta(days=1))]
    assert {snapshot.starts_at for snapshot in batch.snapshots} == {starts["tonight"], starts["tomorrow"]}
