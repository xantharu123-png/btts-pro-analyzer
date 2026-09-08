"""Normal manual recommendations stay coherent across every display tier."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import alternative_markets_tab_extended as market_tab
import bet_finder_ui
from challenge_engine import market_specs
from league_catalog import ALTERNATIVE_MARKET_LEAGUES


def _row(key, fixture=1, *, complete=False, probability=0.5):
    spec = next(item for item in market_specs() if item.key == key)
    return SimpleNamespace(
        candidate_id=f"{fixture}:{key}",
        fixture_id=fixture,
        kickoff="2030-01-02T15:00:00+00:00",
        market_key=key,
        market=spec.market,
        selection=spec.selection,
        home_team=f"Home {fixture}",
        away_team=f"Away {fixture}",
        context={"release_context_complete": complete},
        probability=probability,
        minimum_odds=2.0,
    )


@pytest.mark.parametrize(
    "primary_key, opposing_key",
    [
        ("RESULT_HOME", "RESULT_AWAY"),
        ("RESULT_HOME", "RESULT_DRAW"),
        ("RESULT_HOME", "DC_X2"),
        ("RESULT_TOTAL_1X_UNDER_3_5", "RESULT_AWAY"),
        ("BTTS_YES", "TOTAL_UNDER_1_5"),
        ("HOME_UNDER_1_5", "HOME_OVER_1_5"),
    ],
)
def test_normal_manual_pool_excludes_opposing_same_game_markets(
    primary_key, opposing_key,
):
    primary = _row(primary_key, complete=True)
    opposing = _row(opposing_key)
    other_game = _row(opposing_key, fixture=2)
    rows = [primary, opposing, other_game]
    before = deepcopy(rows)

    selected = bet_finder_ui.coherent_consumer_forecasts(rows)

    assert selected == [primary, other_game]
    assert rows == before
    assert selected[0] is primary
    assert selected[1] is other_game


def test_manual_context_and_market_utility_anchor_not_highest_probability():
    weaker = _row("RESULT_AWAY", probability=0.95)
    stronger_context = _row("RESULT_HOME", complete=True, probability=0.3)
    broad_safety = _row("DC_X2", complete=True, probability=0.99)

    assert bet_finder_ui.coherent_consumer_forecasts(
        [weaker, broad_safety, stronger_context]
    ) == [stronger_context]


def test_manual_compatible_markets_remain_original_payloads():
    home = _row("RESULT_HOME", complete=True)
    total = _row("TOTAL_OVER_1_5")
    corners = _row("CORNERS_OVER_5_5")
    rows = [home, total, corners]

    result = bet_finder_ui.coherent_consumer_forecasts(iter(rows))

    assert result == rows
    assert all(actual is expected for actual, expected in zip(result, rows))


def test_manual_merge_coherence_is_before_display_limit_and_price_shortlist():
    primary = _row("RESULT_HOME", complete=True)
    opposing = [_row("RESULT_AWAY"), _row("RESULT_DRAW"), _row("DC_X2")]
    next_game = _row("BTTS_YES", fixture=2)
    model = [primary, *opposing, next_game]
    before = deepcopy(model)

    result = market_tab._merge_consumer_market_rows(
        [opposing[0]], model, limit=2, coherent=True,
    )

    assert result == [primary, next_game]
    assert model == before
    assert result[0] is primary


def test_manual_quote_and_probability_changes_do_not_change_coherent_ids():
    rows = [_row("RESULT_HOME", complete=True), _row("RESULT_AWAY")]
    baseline = market_tab._merge_consumer_market_rows([], rows, coherent=True)
    rows[0].minimum_odds = 1.01
    rows[0].probability = 0.02
    rows[1].minimum_odds = 50.0
    rows[1].probability = 0.98
    rows[1].evidence_stage = "RELEASED"

    result = market_tab._merge_consumer_market_rows([rows[1]], rows, coherent=True)

    assert [row.candidate_id for row in result] == [row.candidate_id for row in baseline]
    assert result[0] is rows[0]


def test_shared_legacy_default_keeps_challenge_catalog_unchanged():
    rows = [_row("RESULT_HOME"), _row("RESULT_AWAY")]

    assert market_tab._merge_consumer_market_rows([], rows) == rows
    featured, additional = bet_finder_ui.partition_consumer_featured_forecasts(rows)
    assert featured == rows[:1]
    assert additional == rows[1:]


class _Surface:
    def __init__(self, snapshot):
        self.session_state = {"market_bet_finder_snapshot": snapshot}
        self.messages = []
        self.section = None

    def caption(self, text):
        self.messages.append(text)

    info = caption
    warning = caption
    error = caption
    markdown = caption

    def button(self, *_args, **_kwargs):
        return False

    def divider(self):
        pass

    @contextmanager
    def expander(self, label, **_kwargs):
        previous, self.section = self.section, label
        try:
            yield self
        finally:
            self.section = previous


@pytest.mark.parametrize("short_key", ["RESULT_HOME", "RESULT_AWAY"])
def test_actual_manual_surface_filters_before_every_group_and_counts_survivors(
    monkeypatch, short_key,
):
    now = datetime.now(timezone.utc)
    primary = _row("RESULT_HOME", complete=True)
    opposing = _row("RESULT_AWAY")
    compatible = _row("TOTAL_OVER_1_5")
    second_game = _row("BTTS_YES", fixture=2)
    all_rows = [primary, opposing, compatible, second_game]
    scope = market_tab._market_scope_signature(
        list(ALTERNATIVE_MARKET_LEAGUES), now.date(), now.date(),
    )
    scope.update(
        max_fixtures=market_tab.MAX_SCAN_FIXTURES,
        market_scope="Beste Märkte", market_kinds=None,
    )
    snapshot = {
        "version": market_tab.MARKET_SNAPSHOT_VERSION,
        "scanned_at": now.isoformat(), "scope": scope,
        # Only the contradictory, later model row is price-passing.
        "shortlist": [opposing], "model_shortlist": all_rows,
        "reference_quotes": {}, "context_scope_complete": True,
        "operational_error_count": 0,
    }
    original_snapshot = deepcopy(snapshot)
    surface = _Surface(snapshot)
    rendered, split_input = [], []
    monkeypatch.setattr(market_tab, "st", surface)
    monkeypatch.setattr(market_tab, "load_app_config", lambda _st: SimpleNamespace(
        api_football_key="test", weather_key=None,
    ))
    monkeypatch.setattr(market_tab, "_segmented", lambda _label, options, *_: options[0])
    monkeypatch.setattr(market_tab.scan_jobs, "session_scope", lambda _: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "scoped_key", lambda *_: "test")
    monkeypatch.setattr(market_tab.scan_jobs, "get_job", lambda _: {"state": "idle"})
    monkeypatch.setattr(market_tab, "_strict_market_candidate", lambda row: SimpleNamespace(
        event_key=row.candidate_id,
    ))
    monkeypatch.setattr(market_tab, "candidate_context_summary", lambda _: "Analyse")
    monkeypatch.setattr(market_tab, "render_price_decision", lambda candidate, **kwargs: rendered.append(
        (surface.section, candidate.event_key, kwargs["reference_binding_candidate"])
    ))

    def split(rows, **_kwargs):
        split_input.extend(rows)
        return (
            [row for row in rows if row.market_key != short_key],
            [row for row in rows if row.market_key == short_key],
        )

    monkeypatch.setattr(market_tab, "partition_consumer_forecasts", split)
    market_tab.create_alternative_markets_tab_extended(
        search_date=now.date(), search_end_date=now.date(), embedded=True,
    )

    assert split_input == [primary, compatible, second_game]
    assert {key for _, key, _ in rendered} == {
        primary.candidate_id, compatible.candidate_id, second_game.candidate_id,
    }
    assert all(bound is next(row for row in all_rows if row.candidate_id == key)
               for _, key, bound in rendered)
    assert snapshot == original_snapshot
    public_text = " ".join(surface.messages)
    assert "1 Modell-Auswahl mit passender Vergleichsquote" not in public_text
    assert "Alle weiteren berechneten Märkte" not in public_text
    assert "vollständig sichtbar" not in public_text
