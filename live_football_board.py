"""Scoreboard projection and presentation. No provider access, timers or ledgers here."""
from datetime import datetime
from dataclasses import dataclass

from football_recommendations import LIVE_MAX_AGE_SECONDS
from live_football_feed import LiveRefreshIssue
from tip_display_order import ordered_event_rows
from wettfinder_surface import plain_markdown


_REFRESH_MESSAGES = {
    LiveRefreshIssue.TICKER_LIMIT: "Tageslimit des Live-Tickers erreicht.",
    LiveRefreshIssue.PROTECTED_RESERVE: "Das verbleibende Abrufkontingent ist für die Tagesläufe reserviert.",
    LiveRefreshIssue.BUDGET_BLOCKED: "Ein Abruflimit verhindert die Live-Aktualisierung.",
    LiveRefreshIssue.BUDGET_UNAVAILABLE: "Das Abrufkontingent konnte nicht geprüft werden.",
    LiveRefreshIssue.JOBS_DEFERRED: "Live-Aktualisierung pausiert: Hintergrundläufe haben Vorrang.",
    LiveRefreshIssue.PROVIDER_ERROR: "Live-Daten des Anbieters sind derzeit nicht verfügbar.",
    LiveRefreshIssue.TEMPORARY_ERROR: "Live-Aktualisierung ist vorübergehend gestört; neue Spielstände sind nicht verfügbar.",
    LiveRefreshIssue.PARTIAL_DATA: "Die Live-Daten sind unvollständig.",
}


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


def render_board(ui, games, candidates, *, preferred_id, format_time, render_tip, reasons, now,
                 refresh_issue=None):
    """Render one tip/detail pane and a keyboard-accessible list of live scores."""
    if refresh_issue is not None:
        message = _REFRESH_MESSAGES.get(refresh_issue, _REFRESH_MESSAGES[LiveRefreshIssue.TEMPORARY_ERROR])
        ui.info(message + (" Die zuletzt bekannten Spielstände bleiben sichtbar." if games else ""))
        if not games:
            return
    if not games:
        ui.info("Kein Live-Spiel in den unterstützten Ligen verfügbar.")
        return
    by_id = {game.id: game for game in games}
    key = "live_selected_fixture_id"
    selected = ui.session_state.get(key)
    if selected not in by_id:
        # The upstream model ranks tips; kickoff order applies only to the scoreboard.
        selected = preferred_id if preferred_id in by_id and preferred_id in candidates else games[0].id
        ui.session_state.pop(key, None)
    with ui.container(key="live_board"):
        # Reserve the pane before the scoreboard so phone reading order matches the layout.
        detail = ui.container(key="live_detail")
        with ui.container(key="live_scoreboard"):
            ui.markdown("## Spielstände")
            count = f"{len(games)} laufende Spiele" if len(games) != 1 else "1 laufendes Spiel"
            ui.caption(f"{count} · Wähle ein Spiel für die Details.")
            if key in ui.session_state and len(by_id) > 1:
                ui.button("Zur automatischen Auswahl", key="live_resume_automatic",
                          on_click=_resume_automatic, args=(ui.session_state,))
            with ui.container(key="live_scoreboard_matches"):
                for game in games:
                    label = f"**{plain_markdown(game.score)}** · {plain_markdown(game.clock)} · {plain_markdown(game.title)}"
                    league = game.fixture.get("league")
                    league_name = league.get("name") if isinstance(league, dict) else None
                    if isinstance(league_name, str) and league_name.strip():
                        label += f" · {plain_markdown(league_name)}"
                    if fresh_age(game.observed_at, now) is None:
                        stamp = game.observed_at
                        label += f" · Letzter Stand: {format_time(stamp.isoformat() if stamp else None)}"
                    if selected == game.id:
                        label += " · Ausgewählt"
                    if ui.button(label,
                                 key=f"live_fixture_{game.id}", width="stretch",
                                 type="primary" if selected == game.id else "secondary",
                                 on_click=_select_game, args=(ui.session_state, game.id)):
                        selected = game.id
                        _select_game(ui.session_state, selected)
    with detail:
        game = by_id[selected]
        heading = ui.empty()
        stamp = game.observed_at
        ui.markdown(f"**{plain_markdown(game.score)}** · {plain_markdown(game.clock)}")
        ui.caption(f"Datenstand: {format_time(stamp.isoformat() if stamp else None)}")
        if selected in candidates and render_tip(game, candidates[selected]):
            title = "Bester Live-Tipp" if selected == preferred_id else "Live-Tipp zum Spiel"
        else:
            title = "Spieldetails"
            ui.write(plain_markdown(game.title))
            ui.info("Kein aktueller Modellvorschlag für dieses Spiel.")
            if reason := reasons.get(selected):
                ui.caption(plain_markdown(reason))
        heading.markdown(f"## {title}")


def _select_game(state, game_id):
    state["live_selected_fixture_id"] = game_id


def _resume_automatic(state):
    state.pop("live_selected_fixture_id", None)
