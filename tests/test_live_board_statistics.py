"""The inspector compares native observations, never model estimates or discovery data."""
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import pytest

from live_football_board import games_in_start_order, render_board
from test_live_tip_surface import Screen


NOW = datetime(2026, 11, 22, 15, tzinfo=timezone.utc)


def match_rows():
    home, away = {"id": 8, "name": "Heim & Co"}, {"id": 9, "name": "Gast <Ost>"}
    def group(team, fields):
        return {"fixture_id": 77, "team": team.copy(),
                "statistics": [{"type": name, "value": value} for name, value in fields]}
    fixture = {
        "fixture": {"id": 77, "status": {"short": "2H", "elapsed": 90, "extra": 4}},
        "teams": {"home": home, "away": away}, "goals": {"home": 1, "away": 0}, "events": [],
        "statistics": [
            group(away, [("Total attacks", 19), ("Dangerous attacks", 3), ("Total Shots", 12),
                         ("Shots on Goal", 4), ("Corner Kicks", 2), ("expected_goals", "0.94"),
                         ("Ball Possession", "39%")]),
            group(home, [("Total attacks", 30), ("Dangerous attacks", 9), ("Total Shots", 7),
                         ("Shots on Goal", 1), ("Corner Kicks", 0), ("expected_goals", "1.20"),
                         ("Ball Possession", "61%")]),
        ]}
    return {77: {"fixture": fixture, "observed_at": NOW, "detailed_at": NOW}}


def inspect(rows, *, candidates=None, reasons=None):
    ui = Screen()
    render_board(ui, games_in_start_order(rows), candidates or {}, preferred_id=77, format_time=lambda x: x,
                 publish_pick=lambda *_: False,
                 reasons=reasons if reasons is not None else {77: "Keine neuen Tipps ab Minute 90"}, now=NOW)
    return ui, ET.fromstring("<main>" + "".join(text for kind, text in ui.messages if kind == "markdown") + "</main>")


def values(dom):
    table = dom.find(".//table[caption='Spielstatistik']")
    assert table is not None, "no comparison for the selected fixture"
    return {row.findtext("th[@scope='row']"): tuple("".join(cell.itertext()) for cell in row.findall("td"))
            for row in table.findall("./tbody/tr")}


def test_inspector_compares_all_native_stats_directly_under_pitch_even_after_market_closed():
    ui, dom = inspect(match_rows())
    assert values(dom) == {
        "Angriffe": ("30", "19"), "Gefährliche Angriffe": ("9", "3"),
        "Eckbälle": ("0", "2"), "Schüsse": ("7", "12"), "Schüsse aufs Tor": ("1", "4"),
        "Erwartete Tore (xG)": ("1,20", "0,94"), "Ballbesitz": ("61 %", "39 %"),
    }
    table = dom.find(".//table")
    assert [th.text for th in table.findall(".//thead/tr/th[@scope='col']")][::2] == ["Heim & Co", "Gast <Ost>"]
    following = list(dom)[list(dom).index(dom.find("./div[@class='lv-pitch']")) + 1]
    assert following is table or following.find(".//table") is table
    assert "Keine neuen Tipps ab Minute 90" in str(ui.messages)


def test_missing_is_not_zero_one_sided_stats_are_never_drawn_as_a_lead():
    rows = match_rows()
    away, home = rows[77]["fixture"]["statistics"]
    away["statistics"] = [{"type": "Corner Kicks", "value": None}, {"type": "expected_goals", "value": None}]
    home["statistics"] = [{"type": "Corner Kicks", "value": 0}, {"type": "Total Shots", "value": 7}]
    _, dom = inspect(rows)
    assert values(dom) == {"Eckbälle": ("0", "–"), "Schüsse": ("7", "–")}
    assert not dom.findall(".//tbody/tr/td[@style]"), "shares are unknown without the other side"


def test_single_bound_team_group_does_not_turn_into_two_teams_data():
    rows = match_rows()
    rows[77]["fixture"]["statistics"].pop()
    _, dom = inspect(rows)
    assert values(dom)["Angriffe"] == ("–", "19")


@pytest.mark.parametrize("mutation", ["team", "fixture", "name", "duplicate-side", "bad-fixture-type"])
def test_foreign_or_ambiguous_groups_are_not_an_attributed_comparison(mutation):
    rows = match_rows()
    groups = rows[77]["fixture"]["statistics"]
    if mutation == "team":
        groups[0]["team"]["id"] = 84
    elif mutation == "fixture":
        groups[0]["fixture"] = {"id": 78}
    elif mutation == "name":
        groups[0]["team"]["name"] = "Heim & Co"
    elif mutation == "duplicate-side":
        groups[0]["team"] = groups[1]["team"].copy()
    else:
        groups[0]["fixture_id"] = 77.0
    _, dom = inspect(rows)
    assert dom.find(".//table") is None
    assert "Keine aktuellen Statistikdaten" in "".join(dom.itertext())


@pytest.mark.parametrize("stamp", [None, NOW - timedelta(seconds=121), NOW + timedelta(seconds=1)])
def test_fresh_score_never_relabels_expired_invalidated_or_future_stats(stamp):
    rows = match_rows()
    rows[77]["detailed_at"] = stamp
    _, dom = inspect(rows)
    assert dom.find(".//table") is None
    assert "Keine aktuellen Statistikdaten" in "".join(dom.itertext())


def test_invalid_or_contradictory_numbers_leave_only_independently_valid_fields():
    rows = match_rows()
    away, home = rows[77]["fixture"]["statistics"]
    away["statistics"] = [{"type": "expected_goals", "value": "2%"}, {"type": "Ball Possession", "value": "999%"},
                         {"type": "Total Shots", "value": True}, {"type": "Corner Kicks", "value": -1}]
    home["statistics"] = [{"type": "expected_goals", "value": "nan"}, {"type": "Total attacks", "value": 3},
                         {"type": "Total attacks", "value": 4}, {"type": "Shots on Goal", "value": 1}]
    _, dom = inspect(rows)
    assert values(dom) == {"Schüsse aufs Tor": ("1", "–")}


def test_both_rejected_publications_point_to_a_revised_stand_not_a_missing_model_input():
    ui, dom = inspect(match_rows(), candidates={77: object()}, reasons={})
    assert "Live-Stand wird aktualisiert" in "".join(dom.itertext())
    assert any(kind == "button" and "Live-Stand wird aktualisiert" in message[0] for kind, message in ui.messages)
    assert dom.find(".//table") is None, "known-revised statistics cannot be presented as current"


def test_attack_alias_is_read_as_native_count_but_a_quoted_integer_is_not():
    rows = match_rows()
    away, home = rows[77]["fixture"]["statistics"]
    away["statistics"] = [{"type": "Attacks", "value": 15}]
    home["statistics"] = [{"type": "Total attacks", "value": "22"}]
    _, dom = inspect(rows)
    assert values(dom) == {"Angriffe": ("–", "15")}


def test_fresh_statistics_survive_missing_events_but_not_a_failed_detail_refresh():
    from live_football_feed import LiveFootballFeed
    from types import SimpleNamespace
    fixture = match_rows()[77]["fixture"]
    fixture.pop("events")
    source = SimpleNamespace(discover=lambda: [fixture], details=lambda ids: [fixture])
    feed = LiveFootballFeed(monotonic=lambda: 0)
    first = feed.tick(source, now=NOW)
    assert first[77]["detailed_at"] is None, "no event stream: not a model-ready detail"
    assert values(inspect(first)[1])["Eckbälle"] == ("0", "2")
    source.details = lambda ids: []
    after = feed.tick(source, now=NOW + timedelta(seconds=61))
    assert inspect(after)[1].find(".//table") is None


def test_missing_internal_display_reason_does_not_claim_the_visible_stats_are_absent():
    _, dom = inspect(match_rows(), reasons={})
    assert values(dom)["Eckbälle"] == ("0", "2")
    assert dom.findtext(".//div[@class='lv-no-pick']/strong") == "Kein aktueller Live-Tipp"
