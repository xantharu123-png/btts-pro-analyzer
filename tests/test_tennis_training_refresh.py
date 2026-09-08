from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from io import BytesIO
from types import SimpleNamespace
import sys

import pandas as pd
import pytest
import requests

from scripts import rebuild_state
from tennis import data_loader, model_state
from tennis.elo import SurfaceElo
from tennis.serve_model import ServeReturnModel


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc).timestamp()
TOURNAMENTS = (
    b"id,name,year,indoor_outdoor,surface,series_category_id,start_dtm\n"
    b"1,Test Open,2026,Outdoor,Hard,atp_250,20260901\n"
    b"101,Old Open,2025,Outdoor,Hard,atp_250,20250901\n"
)
OLD_MATCHES = b"id,tournament_id,winner_name,loser_name\n1,1,Old Player,Other Player\n"
HISTORICAL_MATCHES = (
    b"id,tournament_id,winner_name,loser_name\n"
    b"101,101,Old Player,Other Player\n"
)
NEW_MATCHES = b"id,tournament_id,winner_name,loser_name\n2,1,New Player,Other Player\n"


def xlsx(winner="New Woman", day="2026-09-01"):
    output = BytesIO()
    pd.DataFrame([{"Date": day, "Winner": winner, "Loser": "Other Woman", "Surface": "Hard"}]).to_excel(output, index=False)
    return output.getvalue()


def response(payload):
    return SimpleNamespace(content=payload, raise_for_status=lambda: None)


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: pytest.fail("unexpected external request"))


def cached_sources(tmp_path):
    (tmp_path / "atp_tournaments.csv").write_bytes(TOURNAMENTS)
    (tmp_path / "atp_matches_2025.csv").write_bytes(HISTORICAL_MATCHES)
    (tmp_path / "atp_matches_2026.csv").write_bytes(OLD_MATCHES)
    (tmp_path / "wta_odds_2025.xlsx").write_bytes(
        xlsx("Old Woman", "2025-09-01")
    )
    (tmp_path / "wta_odds_2026.xlsx").write_bytes(xlsx("Old Woman"))


def test_explicit_refresh_revalidates_current_atp_and_tournaments_not_history(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        return response(TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES)
    monkeypatch.setattr(data_loader.requests, "get", get)
    rows = data_loader.load_atp_stats((2025, 2026), tmp_path, refresh_current=True, current_year=2026)
    assert rows["winner_name"].tolist() == ["Old Player", "New Player"]
    assert urls == [f"{data_loader.MAN_TENNIS_BASE}/atp/tournaments.csv", f"{data_loader.MAN_TENNIS_BASE}/atp/matches_2026.csv"]
    assert (tmp_path / "atp_matches_2025.csv").read_bytes() == HISTORICAL_MATCHES
    assert (tmp_path / "atp_matches_2026.csv").read_bytes() == NEW_MATCHES


def test_existing_loader_defaults_remain_cache_only(tmp_path):
    cached_sources(tmp_path)
    assert data_loader.load_atp_stats((2026,), tmp_path)["winner_name"].tolist() == ["Old Player"]
    assert data_loader.load_market_odds((2026,), "wta", tmp_path)["Winner"].tolist() == ["Old Woman"]


@pytest.mark.parametrize("refresh", [False, True])
def test_real_atp_compound_tournament_ids_are_opaque_not_numbers(tmp_path, monkeypatch, refresh):
    tournaments = TOURNAMENTS.replace(b"1,Test Open", b"2026-2801,Test Open")
    matches = OLD_MATCHES.replace(b"1,1,Old Player", b"1,2026-2801,Old Player")
    (tmp_path / "atp_tournaments.csv").write_bytes(tournaments)
    (tmp_path / "atp_matches_2026.csv").write_bytes(matches)
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        tournaments if url.endswith("tournaments.csv") else matches))
    rows = data_loader.load_atp_stats((2026,), tmp_path, refresh_current=refresh, current_year=2026)
    assert rows["winner_name"].tolist() == ["Old Player"]
    assert rows["tournament_id"].tolist() == ["2026-2801"]


def test_atp_season_metadata_cannot_date_current_results_into_previous_year(tmp_path, monkeypatch):
    tournaments = TOURNAMENTS.replace(b"20260901", b"20250901")
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        tournaments if url.endswith("tournaments.csv") else NEW_MATCHES))
    with pytest.raises(ValueError, match="2026"):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert not (tmp_path / "atp_tournaments.csv").exists()


def test_incomplete_atp_source_rows_do_not_block_or_inflate_completed_coverage(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    partial = NEW_MATCHES + b"3,1,Pending Player,\n"
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        TOURNAMENTS if url.endswith("tournaments.csv") else partial))
    rows = data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert rows["winner_name"].tolist() == ["New Player"]
    dates = data_loader._tournament_dates_for_year(data_loader._validate_tournaments(TOURNAMENTS), 2026)
    count, _ = data_loader._atp_match_coverage(partial, tournament_dates=dates, year=2026,
                                             as_of=pd.Timestamp("2026-09-07", tz="UTC"))
    assert count == 1


def test_removal_of_empty_tournament_does_not_block_real_result_refresh(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    prior = TOURNAMENTS + b"2,Empty Open,2026,Outdoor,Hard,atp_250,20260801\n"
    (tmp_path / "atp_tournaments.csv").write_bytes(prior)
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES))
    rows = data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert rows["winner_name"].tolist() == ["New Player"]


def test_removed_tournament_with_completed_results_keeps_old_metadata(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    removed = TOURNAMENTS.replace(b"1,Test Open", b"2,Replacement Open")
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        removed if url.endswith("tournaments.csv") else NEW_MATCHES.replace(b"2,1,", b"2,2,")))
    with pytest.raises(ValueError):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_tournaments.csv").read_bytes() == TOURNAMENTS


def test_newly_mapped_results_cannot_offset_loss_of_previously_consumed_results(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    matches = OLD_MATCHES + b"2,2,Previously Unmapped,Other Player\n"
    (tmp_path / "atp_matches_2026.csv").write_bytes(matches)
    replacement = TOURNAMENTS.replace(b"1,Test Open", b"2,New Open").replace(b"20260901", b"20260902")
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(
        replacement if url.endswith("tournaments.csv") else matches))
    with pytest.raises(ValueError, match="history"):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_tournaments.csv").read_bytes() == TOURNAMENTS


@pytest.mark.parametrize("bad", [b"", b"<html>error</html>", b"id,tournament_id,winner_name,loser_name\n", b"id,tournament_id,winner_name,loser_name\n2,1,,Other\n"])
def test_invalid_current_atp_response_never_replaces_good_cache(tmp_path, monkeypatch, bad):
    cached_sources(tmp_path)
    monkeypatch.setattr(data_loader.requests, "get", lambda url, **_: response(TOURNAMENTS if url.endswith("tournaments.csv") else bad))
    with pytest.raises(ValueError):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


@pytest.mark.parametrize("error", [requests.HTTPError("503"), requests.Timeout("timeout")])
def test_current_atp_http_failure_cannot_fall_back_to_old_season(tmp_path, monkeypatch, error):
    cached_sources(tmp_path)
    def get(url, **kwargs):
        if url.endswith("tournaments.csv"):
            return response(TOURNAMENTS)
        raise error
    monkeypatch.setattr(data_loader.requests, "get", get)
    with pytest.raises(type(error)):
        data_loader.load_atp_stats((2025, 2026), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_matches_2026.csv").read_bytes() == OLD_MATCHES


def test_wrong_year_current_atp_payload_cannot_replace_good_cache(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    old = (tmp_path / "atp_matches_2026.csv").read_bytes()
    wrong_year = (
        b"id,tournament_id,winner_name,loser_name\n"
        b"2,101,Wrong Year,Other Player\n"
    )
    monkeypatch.setattr(
        data_loader.requests,
        "get",
        lambda url, **_: response(
            TOURNAMENTS if url.endswith("tournaments.csv") else wrong_year
        ),
    )

    with pytest.raises(ValueError, match="2026"):
        data_loader.load_atp_stats(
            (2026,), tmp_path, refresh_current=True, current_year=2026,
        )

    assert (tmp_path / "atp_matches_2026.csv").read_bytes() == old


def test_regressed_current_atp_payload_cannot_replace_good_cache(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    old = (
        b"id,tournament_id,winner_name,loser_name\n"
        b"1,1,Old Player,Other Player\n"
        b"2,1,Second Player,Other Player\n"
    )
    (tmp_path / "atp_matches_2026.csv").write_bytes(old)
    monkeypatch.setattr(
        data_loader.requests,
        "get",
        lambda url, **_: response(
            TOURNAMENTS if url.endswith("tournaments.csv") else OLD_MATCHES
        ),
    )

    with pytest.raises(ValueError, match="regressed"):
        data_loader.load_atp_stats(
            (2026,), tmp_path, refresh_current=True, current_year=2026,
        )

    assert (tmp_path / "atp_matches_2026.csv").read_bytes() == old


def test_invalid_tournament_response_keeps_previous_metadata(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: response(TOURNAMENTS.replace(b"20260901", b"not-a-date")))
    with pytest.raises(ValueError):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_tournaments.csv").read_bytes() == TOURNAMENTS


def test_wta_refresh_uses_real_result_columns_and_reuses_historical_years(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    urls = []
    def get(url, **kwargs):
        urls.append(url)
        return response(xlsx())
    monkeypatch.setattr(data_loader.requests, "get", get)
    rows = data_loader.load_market_odds((2025, 2026), "wta", tmp_path, refresh_current=True, current_year=2026)
    assert rows["Winner"].tolist() == ["Old Woman", "New Woman"]
    assert urls == [f"{data_loader.TENNIS_DATA_BASE}/2026w/2026.xlsx"]


def test_wrong_year_current_wta_payload_cannot_replace_good_cache(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    target = tmp_path / "wta_odds_2026.xlsx"
    old = target.read_bytes()
    output = BytesIO()
    pd.DataFrame([{
        "Date": "2025-09-01", "Winner": "Wrong Year",
        "Loser": "Other Woman", "Surface": "Hard",
    }]).to_excel(output, index=False)
    monkeypatch.setattr(
        data_loader.requests,
        "get",
        lambda *a, **k: response(output.getvalue()),
    )

    with pytest.raises(ValueError, match="2026"):
        data_loader.load_market_odds(
            (2026,), "wta", tmp_path,
            refresh_current=True, current_year=2026,
        )

    assert target.read_bytes() == old


def test_future_wrong_year_wta_typo_does_not_satisfy_current_coverage(
    tmp_path, monkeypatch,
):
    cached_sources(tmp_path)
    target = tmp_path / "wta_odds_2026.xlsx"
    old = target.read_bytes()
    output = BytesIO()
    pd.DataFrame([{
        "Date": "2029-09-01", "Winner": "Future Typo",
        "Loser": "Other Woman", "Surface": "Hard",
    }]).to_excel(output, index=False)
    monkeypatch.setattr(
        data_loader.requests,
        "get",
        lambda *a, **k: response(output.getvalue()),
    )

    with pytest.raises(ValueError, match="2026"):
        data_loader.load_market_odds(
            (2026,), "wta", tmp_path,
            refresh_current=True, current_year=2026,
        )

    assert target.read_bytes() == old


def test_current_wta_payload_may_include_known_future_date_typo(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    output = BytesIO()
    pd.DataFrame([
        {
            "Date": "2026-09-01", "Winner": "Current Woman",
            "Loser": "Other Woman", "Surface": "Hard",
        },
        {
            "Date": "2029-09-01", "Winner": "Future Typo",
            "Loser": "Other Woman", "Surface": "Hard",
        },
    ]).to_excel(output, index=False)
    payload = output.getvalue()
    monkeypatch.setattr(
        data_loader.requests, "get", lambda *a, **k: response(payload),
    )

    rows = data_loader.load_market_odds(
        (2026,), "wta", tmp_path,
        refresh_current=True, current_year=2026,
    )

    assert rows["Winner"].tolist() == ["Current Woman"]
    assert (tmp_path / "wta_odds_2026.xlsx").read_bytes() == payload


def test_regressed_current_wta_payload_cannot_replace_good_cache(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    target = tmp_path / "wta_odds_2026.xlsx"
    output = BytesIO()
    pd.DataFrame([
        {
            "Date": "2026-09-01", "Winner": "First Woman",
            "Loser": "Other Woman", "Surface": "Hard",
        },
        {
            "Date": "2026-09-05", "Winner": "Second Woman",
            "Loser": "Other Woman", "Surface": "Hard",
        },
    ]).to_excel(output, index=False)
    old = output.getvalue()
    target.write_bytes(old)
    monkeypatch.setattr(
        data_loader.requests,
        "get",
        lambda *a, **k: response(xlsx("First Woman")),
    )

    with pytest.raises(ValueError, match="regressed"):
        data_loader.load_market_odds(
            (2026,), "wta", tmp_path,
            refresh_current=True, current_year=2026,
        )

    assert target.read_bytes() == old


@pytest.mark.parametrize("bad", [b"", b"<html>error</html>", b"not-an-xlsx"])
def test_invalid_wta_response_never_replaces_good_results(tmp_path, monkeypatch, bad):
    cached_sources(tmp_path)
    old = (tmp_path / "wta_odds_2026.xlsx").read_bytes()
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: response(bad))
    with pytest.raises(ValueError):
        data_loader.load_market_odds((2026,), "wta", tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "wta_odds_2026.xlsx").read_bytes() == old


@pytest.mark.parametrize("kind", ["empty", "missing_results", "invalid_date"])
def test_parseable_but_invalid_wta_workbook_is_not_published(tmp_path, monkeypatch, kind):
    cached_sources(tmp_path)
    old = (tmp_path / "wta_odds_2026.xlsx").read_bytes()
    output = BytesIO()
    frame = pd.DataFrame([{"Date": "not-a-date", "Winner": "Alpha", "Loser": "Beta", "Surface": "Hard"}])
    if kind == "empty":
        frame = frame.iloc[:0]
    elif kind == "missing_results":
        frame = pd.DataFrame([{"Price": 2.0}])
    frame.to_excel(output, index=False)
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: response(output.getvalue()))
    with pytest.raises(ValueError):
        data_loader.load_market_odds((2026,), "wta", tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "wta_odds_2026.xlsx").read_bytes() == old


def test_atomic_cache_replace_failure_retains_original_bytes(tmp_path, monkeypatch):
    import runtime_paths
    cached_sources(tmp_path)
    monkeypatch.setattr(data_loader.requests, "get", lambda *a, **k: response(TOURNAMENTS))
    def interrupted(*args):
        raise OSError("simulated atomic replacement failure")
    monkeypatch.setattr(runtime_paths.os, "replace", interrupted)
    with pytest.raises(OSError, match="atomic replacement"):
        data_loader.load_atp_stats((2026,), tmp_path, refresh_current=True, current_year=2026)
    assert (tmp_path / "atp_tournaments.csv").read_bytes() == TOURNAMENTS
    assert not list(tmp_path.glob("*.tmp"))


def old_state():
    return model_state.ModelState(
        elo=SurfaceElo(), serve=ServeReturnModel(), cal_a=1., cal_b=0., cal_samples=0,
        built_at=NOW-60, stats_through="2026-07-27", serve_weight=.3,
    )


def isolated_build(tmp_path, monkeypatch):
    cached_sources(tmp_path)
    monkeypatch.setattr(model_state, "load_atp_stats", partial(data_loader.load_atp_stats, cache_dir=tmp_path, current_year=2026))
    monkeypatch.setattr(model_state, "load_market_odds", partial(data_loader.load_market_odds, cache_dir=tmp_path, current_year=2026))
    monkeypatch.setattr(model_state, "run_backtest", lambda **_: SimpleNamespace(rows=[]))
    monkeypatch.setattr(model_state, "DEFAULT_STATE_PATH", tmp_path / "model_state.pkl")
    model_state.save_state(old_state())


def test_model_build_refreshes_both_planes_without_changing_rating_contract(tmp_path, monkeypatch):
    isolated_build(tmp_path, monkeypatch)
    def get(url, **kwargs):
        return response(xlsx() if url.endswith(".xlsx") else TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES)
    monkeypatch.setattr(data_loader.requests, "get", get)
    state = model_state.build_state(stats_years=(2026,), refresh_training_data=True, verbose=False)
    assert state.stats_through == "2026-09-01"
    assert state.elo.known_players() == {"player n", "player o", "woman n", "woman o"}
    assert state.elo.win_probability("player n", "player o") > .5
    assert state.elo.win_probability("woman n", "woman o") > .5


@pytest.mark.parametrize("later_date,retirement", [("20261001", ""), ("20260906", "(RET)")])
def test_training_coverage_excludes_future_or_unconsumed_atp_rows(tmp_path, monkeypatch, later_date, retirement):
    isolated_build(tmp_path, monkeypatch)
    monkeypatch.setattr(model_state.time, "time", lambda: NOW)
    tournaments = TOURNAMENTS + f"2,Other Open,2026,Outdoor,Hard,atp_250,{later_date}\n".encode()
    matches = b"id,tournament_id,winner_name,loser_name,match_ret\n2,1,New Player,Other Player,\n" + f"3,2,Excluded Player,Other Player,{retirement}\n".encode()
    def get(url, **kwargs):
        return response(xlsx() if url.endswith(".xlsx") else tournaments if url.endswith("tournaments.csv") else matches)
    monkeypatch.setattr(data_loader.requests, "get", get)
    state = model_state.build_state(stats_years=(2026,), refresh_training_data=True, verbose=False)
    assert state.stats_through == "2026-09-01"
    assert "player e" not in state.elo.known_players()


def test_future_wta_results_do_not_enter_refreshed_ratings(tmp_path, monkeypatch):
    isolated_build(tmp_path, monkeypatch)
    monkeypatch.setattr(model_state.time, "time", lambda: NOW)
    output = BytesIO()
    pd.DataFrame([
        {"Date": "2026-09-01", "Winner": "New Woman", "Loser": "Other Woman", "Surface": "Hard"},
        {"Date": "2026-09-08", "Winner": "Future Woman", "Loser": "Other Woman", "Surface": "Hard"},
    ]).to_excel(output, index=False)
    def get(url, **kwargs):
        return response(output.getvalue() if url.endswith(".xlsx") else TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES)
    monkeypatch.setattr(data_loader.requests, "get", get)
    state = model_state.build_state(stats_years=(2026,), refresh_training_data=True, verbose=False)
    assert "woman f" not in state.elo.known_players()
    assert "woman n" in state.elo.known_players()


def test_wta_refresh_failure_cannot_replace_combined_state_with_atp_only(tmp_path, monkeypatch, capsys):
    isolated_build(tmp_path, monkeypatch)
    before = model_state.DEFAULT_STATE_PATH.read_bytes()
    def get(url, **kwargs):
        if url.endswith(".xlsx"):
            raise requests.HTTPError("WTA refresh unavailable")
        return response(TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES)
    monkeypatch.setattr(data_loader.requests, "get", get)
    monkeypatch.setattr(rebuild_state, "build_state", partial(model_state.build_state, stats_years=(2026,)))
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--force", "--refresh-data"])
    assert rebuild_state.main() == 1
    assert model_state.DEFAULT_STATE_PATH.read_bytes() == before
    assert "REFRESH_FAILED" in capsys.readouterr().out


def test_recent_pickle_does_not_hide_old_tournament_start_coverage(tmp_path, monkeypatch, capsys):
    isolated_build(tmp_path, monkeypatch)
    before = model_state.DEFAULT_STATE_PATH.read_bytes()
    monkeypatch.setattr(rebuild_state.time, "time", lambda: NOW)
    monkeypatch.setattr(rebuild_state, "build_state", partial(model_state.build_state, stats_years=(2026,)))
    def unavailable(*args, **kwargs):
        raise requests.Timeout("refresh unavailable")
    monkeypatch.setattr(data_loader.requests, "get", unavailable)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--if-stale-days", "7"])
    assert rebuild_state.main() == 1
    output = capsys.readouterr().out
    assert "REFRESH_FAILED" in output
    assert "ATP-Turnierstart" in output
    assert model_state.DEFAULT_STATE_PATH.read_bytes() == before


def test_recent_pickle_and_current_coverage_skip_rebuild(tmp_path, monkeypatch):
    isolated_build(tmp_path, monkeypatch)
    state = old_state()
    state.stats_through = "2026-09-06"
    model_state.save_state(state)
    monkeypatch.setattr(rebuild_state.time, "time", lambda: NOW)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--if-stale-days", "7"])
    assert rebuild_state.main() == 0


def test_cli_publishes_refreshed_combined_state_only_after_valid_sources(tmp_path, monkeypatch, capsys):
    isolated_build(tmp_path, monkeypatch)
    monkeypatch.setattr(rebuild_state, "build_state", partial(model_state.build_state, stats_years=(2026,)))
    def get(url, **kwargs):
        return response(xlsx() if url.endswith(".xlsx") else TOURNAMENTS if url.endswith("tournaments.csv") else NEW_MATCHES)
    monkeypatch.setattr(data_loader.requests, "get", get)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--force", "--refresh-data"])
    assert rebuild_state.main() == 0
    published = model_state.load_state()
    assert published.stats_through == "2026-09-01"
    assert published.elo.known_players() == {"player n", "player o", "woman n", "woman o"}
    assert "aktive Quellen revalidiert=True" in capsys.readouterr().out


def test_explicit_cached_rebuild_does_not_claim_a_source_refresh(tmp_path, monkeypatch, capsys):
    isolated_build(tmp_path, monkeypatch)
    monkeypatch.setattr(rebuild_state, "build_state", partial(model_state.build_state, stats_years=(2026,)))
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--force", "--no-refresh-data"])
    assert rebuild_state.main() == 0
    assert "aktive Quellen revalidiert=False" in capsys.readouterr().out
    assert model_state.load_state().elo.known_players() == {"player o", "woman o"}


def test_failed_atomic_model_publish_retains_last_good_state(tmp_path, monkeypatch):
    import runtime_paths
    isolated_build(tmp_path, monkeypatch)
    before = model_state.DEFAULT_STATE_PATH.read_bytes()
    monkeypatch.setattr(rebuild_state, "build_state", partial(model_state.build_state, stats_years=(2026,)))
    def interrupted(*args):
        raise OSError("simulated model publication failure")
    monkeypatch.setattr(runtime_paths.os, "replace", interrupted)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--legacy-combined", "--force", "--no-refresh-data"])
    assert rebuild_state.main() == 1
    assert model_state.DEFAULT_STATE_PATH.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("broken,expected", [(None, 0), ("WTA", 1), ("ATP", 1), ("both", 1)])
def test_cli_default_publishes_tours_independently_without_touching_legacy(tmp_path, monkeypatch, capsys, broken, expected):
    from tennis import tour_state
    isolated_build(tmp_path, monkeypatch)
    legacy = model_state.DEFAULT_STATE_PATH.read_bytes()
    path = tmp_path / "models.db"
    monkeypatch.setattr(rebuild_state, "CONTEXT_MODEL_DB_PATH", path, raising=False)
    monkeypatch.setattr(rebuild_state.time, "time", lambda: NOW)
    calls = []
    def build(tour, *, as_of, refresh_training_data, diagnostics):
        calls.append((tour, as_of.year, refresh_training_data))
        diagnostics.update({
            "serve_build": {
                "admitted": 10 if tour == "ATP" else 0, "skipped": 1 if tour == "ATP" else 0,
                "admitted_match_count": 10 if tour == "ATP" else 0,
                "skipped_match_count": 1 if tour == "ATP" else 0,
                "admitted_tournament_count": 2 if tour == "ATP" else 0,
                "skipped_tournament_count": 1 if tour == "ATP" else 0,
                "unknown_match_identity": {"admitted_rows": 0, "skipped_rows": 0},
                "unknown_tournament_identity": {"admitted_rows": 0, "skipped_rows": 0},
                "unknown_year": {"admitted_rows": 0, "skipped_rows": 0},
                "reasons": {"nonpositive_game_denominator": 1} if tour == "ATP" else {},
                "admitted_years": {"2026": 10} if tour == "ATP" else {},
                "skipped_years": {"2018": 1} if tour == "ATP" else {},
                "skipped_matches": {"2018-560-v717-f974-Q1": 1} if tour == "ATP" else {},
                "skipped_tournaments": {"2018-560": 1} if tour == "ATP" else {},
            },
            "serve_calibration": {
                "admitted": 8 if tour == "ATP" else 0, "skipped": 0,
                "admitted_match_count": 8 if tour == "ATP" else 0,
                "skipped_match_count": 0,
                "admitted_tournament_count": 2 if tour == "ATP" else 0,
                "skipped_tournament_count": 0,
                "unknown_match_identity": {"admitted_rows": 0, "skipped_rows": 0},
                "unknown_tournament_identity": {"admitted_rows": 0, "skipped_rows": 0},
                "unknown_year": {"admitted_rows": 0, "skipped_rows": 0},
                "reasons": {}, "admitted_years": {"2024": 8} if tour == "ATP" else {},
                "skipped_years": {}, "skipped_matches": {}, "skipped_tournaments": {},
            },
        })
        if broken in (tour, "both"):
            raise OSError("secret-provider-detail")
        result = old_state()
        result.built_at = NOW
        result.tour_scope = tour
        result.stats_through_kind = "result_date" if tour == "WTA" else "tournament_start_proxy"
        result.serve_weight = 0. if tour == "WTA" else .3
        return result
    monkeypatch.setattr(rebuild_state, "build_tour_state", build, raising=False)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--force"])
    assert rebuild_state.main() == expected
    assert calls == [("ATP", 2026, True), ("WTA", 2026, True)]
    assert model_state.DEFAULT_STATE_PATH.read_bytes() == legacy
    output = capsys.readouterr().out
    assert "secret-provider-detail" not in output
    if broken in ("ATP", "both"):
        assert "ATP: failed;" in output and "error_type=OSError" in output
    if broken in ("WTA", "both"):
        assert "WTA: failed;" in output and "error_type=OSError" in output
    assert 'ATP serve_admission={"serve_build":{"admitted":10' in output
    assert '"skipped_match_count":1' in output
    assert '"skipped_tournament_count":1' in output
    assert '"reasons":{"nonpositive_game_denominator":1}' in output
    assert '"skipped_years":{"2018":1}' in output
    assert 'WTA serve_admission={"serve_build":{"admitted":0' in output
    for tour in ("ATP", "WTA"):
        if broken not in (tour, "both"):
            assert tour_state.load_tour_state(tour, path=path).tour_scope == tour


def test_cli_retains_only_fresh_tour_and_force_overrides_skip(tmp_path, monkeypatch, capsys):
    from tennis import tour_state
    from model_artifacts import load_manifest
    path = tmp_path / "models.db"
    clock = datetime.fromtimestamp(NOW, timezone.utc)
    def initial(tour):
        result = old_state()
        result.built_at = NOW
        result.stats_through = "2026-09-06" if tour == "ATP" else "2026-07-27"
        result.tour_scope = tour
        result.stats_through_kind = "result_date" if tour == "WTA" else "tournament_start_proxy"
        result.serve_weight = 0. if tour == "WTA" else .3
        return result
    assert tour_state.refresh_tours(path=path, as_of=clock, builder=initial,
        publication_clock=lambda: clock)["status"] == "complete"
    before = load_manifest(path)
    calls = []
    def unavailable(tour, **kwargs):
        calls.append((tour, kwargs["refresh_training_data"]))
        raise OSError("unavailable")
    monkeypatch.setattr(rebuild_state, "CONTEXT_MODEL_DB_PATH", path, raising=False)
    monkeypatch.setattr(rebuild_state, "build_tour_state", unavailable, raising=False)
    monkeypatch.setattr(rebuild_state.time, "time", lambda: NOW)
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--if-stale-days", "7"])
    assert rebuild_state.main() == 1
    assert calls == [("WTA", True)]
    assert "retained_fresh" in capsys.readouterr().out
    assert load_manifest(path) == before
    calls.clear()
    monkeypatch.setattr(sys, "argv", ["rebuild_state", "--force", "--if-stale-days", "7", "--no-refresh-data"])
    assert rebuild_state.main() == 1
    assert calls == [("ATP", False), ("WTA", False)]
    assert load_manifest(path) == before


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
@pytest.mark.parametrize("available", [False, True])
def test_new_season_uses_coherent_real_source_clock_without_fake_coverage(tmp_path, monkeypatch, tour, available):
    from tennis import tour_state
    moment = datetime(2027, 1, 2, tzinfo=timezone.utc)
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz else moment.replace(tzinfo=None)
    monkeypatch.setattr(data_loader, "datetime", FrozenDatetime)
    monkeypatch.setattr(tour_state.time, "time", lambda: moment.timestamp())
    cached_sources(tmp_path)
    tournaments = TOURNAMENTS + b"2,New Season,2027,Outdoor,Hard,atp_250,20270101\n"
    requested = []
    def get(url, **kwargs):
        requested.append(url)
        if url.endswith("tournaments.csv"):
            return response(tournaments)
        if available and url.endswith("matches_2027.csv"):
            return response(NEW_MATCHES.replace(b"2,1,", b"2,2,"))
        if available and url.endswith("2027w/2027.xlsx"):
            return response(xlsx(day="2027-01-01"))
        raise requests.HTTPError("season not published")
    monkeypatch.setattr(data_loader.requests, "get", get)
    monkeypatch.setattr(tour_state, "load_atp_stats", partial(data_loader.load_atp_stats, cache_dir=tmp_path))
    monkeypatch.setattr(tour_state, "load_market_odds", partial(data_loader.load_market_odds, cache_dir=tmp_path))
    monkeypatch.setattr(tour_state, "run_backtest", lambda **k: SimpleNamespace(rows=[]))
    if available:
        built = tour_state.build_tour_state(tour, as_of=moment)
        assert built.stats_through == "2027-01-01"
        assert built.built_at == moment.timestamp()
    else:
        with pytest.raises(requests.HTTPError):
            tour_state.build_tour_state(tour, as_of=moment)
    suffix = "matches_2027.csv" if tour == "ATP" else "2027w/2027.xlsx"
    assert any(url.endswith(suffix) for url in requested)
