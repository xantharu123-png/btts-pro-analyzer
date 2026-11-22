"""Scoreboard projection and presentation. No provider access, timers or ledgers here."""
from datetime import datetime
from dataclasses import dataclass

from football_recommendations import LIVE_MAX_AGE_SECONDS
from tip_display_order import ordered_event_rows
from wettfinder_surface import plain_markdown


@dataclass(frozen=True)
class Game:
    id: int
    title: str
    clock: str
    score: str
    start: str | None
    fixture: dict
    observed_at: datetime | None
    detailed_at: datetime | None


def games_in_start_order(rows):
    games = []
    for game_id, row in rows.items():
        fixture = row["fixture"]
        source = fixture["fixture"]
        if source.get("id") != game_id:
            continue
        home = (fixture.get("teams", {}).get("home") or {}).get("name") or "Heimteam"
        away = (fixture.get("teams", {}).get("away") or {}).get("name") or "Auswärtsteam"
        status = source.get("status") or {}
        minute, extra = status.get("elapsed"), status.get("extra")
        clock = f"{minute}{f'+{extra}' if extra else ''}′" if minute is not None else "Minute offen"
        if status.get("short") == "HT":
            clock = "Pause"
        goals = fixture.get("goals") or {}
        score = (f"{goals['home']}:{goals['away']}" if all(goals.get(s) is not None for s in ("home", "away"))
                 else "Stand offen")
        games.append(Game(game_id, f"{home} – {away}", clock, score, source.get("date"),
                          fixture, row["observed_at"], row["detailed_at"]))
    return ordered_event_rows(games, event_key=lambda g: g.id, starts_at=lambda g: g.start,
                              probability=lambda _: None)


def fresh_age(stamp, now):
    if not isinstance(stamp, datetime) or stamp.utcoffset() is None:
        return None
    seconds = (now - stamp).total_seconds()
    return seconds if 0 <= seconds <= LIVE_MAX_AGE_SECONDS else None


def render_board(ui, games, candidates, *, market_label, format_time, render_tip, reasons, now):
    """Stable fixture buttons. A missing candidate never selects a different match's tip."""
    if not games:
        ui.info("Kein Live-Spiel in den unterstützten Ligen verfügbar.")
        return
    by_id = {game.id: game for game in games}
    key = "live_selected_fixture_id"
    selected = ui.session_state.get(key)
    if selected not in by_id:
        # Selection policy is upstream; start time only orders the admitted top three.
        selected = next((g.id for g in games if g.id in candidates), games[0].id)
        ui.session_state.pop(key, None)
    left, right = ui.columns([1, 1])
    with left:
        ui.markdown("### Spielstände")
        with ui.container(height=300 if len(games) > 4 else "content"):
            for game in games:
                label = f"{game.clock} · {game.score} · {plain_markdown(game.title)}"
                if fresh_age(game.observed_at, now) is None:
                    stamp = game.observed_at
                    label += f" · Letzter Stand: {format_time(stamp.isoformat() if stamp else None)}"
                if ui.button(label,
                             key=f"live_fixture_{game.id}", use_container_width=True,
                             type="primary" if selected == game.id else "secondary",
                             on_click=_select_game, args=(ui.session_state, game.id)):
                    selected = game.id
                    _select_game(ui.session_state, selected)
    with right:
        game = by_id[selected]
        ui.markdown(f"### {market_label}")
        stamp = game.observed_at
        ui.caption(f"{game.clock} · {game.score} · Datenstand: {format_time(stamp.isoformat() if stamp else None)}")
        if selected not in candidates or not render_tip(game, candidates[selected]):
            ui.write(plain_markdown(game.title))
            ui.info("Kein aktueller Modellvorschlag für dieses Spiel und diesen Markt.")
            if reason := reasons.get(selected):
                ui.caption(reason)


def _select_game(state, game_id):
    state["live_selected_fixture_id"] = game_id
