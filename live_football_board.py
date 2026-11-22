"""Scoreboard projection and presentation. No provider access, timers or ledgers here."""
from datetime import datetime
from dataclasses import dataclass
from html import escape

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


def _team_names(fixture):
    teams = fixture.get("teams")
    def name(side, fallback):
        team = teams.get(side) if isinstance(teams, dict) else None
        value = team.get("name") if isinstance(team, dict) else None
        return value.strip() if isinstance(value, str) and value.strip() else fallback
    return name("home", "Heimteam"), name("away", "Gastteam")


def games_in_start_order(rows):
    games = []
    for game_id, row in rows.items():
        fixture = row["fixture"]
        source = fixture["fixture"]
        if source.get("id") != game_id:
            continue
        home, away = _team_names(fixture)
        status = source.get("status") or {}
        minute, extra = status.get("elapsed"), status.get("extra")
        clock = "Minute offen"
        if type(minute) is int and minute >= 0 and (extra is None or type(extra) is int and extra >= 0):
            clock = f"{minute}{f'+{extra}' if extra else ''}′"
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


_COUNTRY_DE = {
    "Argentina": "Argentinien", "Austria": "Österreich", "Belgium": "Belgien",
    "Brazil": "Brasilien", "Bulgaria": "Bulgarien", "Croatia": "Kroatien",
    "Cyprus": "Zypern", "Czech-Republic": "Tschechien", "Denmark": "Dänemark",
    "Finland": "Finnland", "France": "Frankreich", "Germany": "Deutschland",
    "Greece": "Griechenland", "Hungary": "Ungarn", "Ireland": "Irland",
    "Italy": "Italien", "Mexico": "Mexiko", "Netherlands": "Niederlande",
    "Norway": "Norwegen", "Poland": "Polen", "Romania": "Rumänien",
    "Saudi Arabia": "Saudi-Arabien", "Scotland": "Schottland", "Serbia": "Serbien",
    "South Africa": "Südafrika", "Spain": "Spanien", "Sweden": "Schweden",
    "Switzerland": "Schweiz", "Turkey": "Türkei", "World": "International",
}


def _competition(game):
    raw = game.fixture.get("league")
    league = raw if isinstance(raw, dict) else {}
    name = league.get("name")
    country = league.get("country")
    name = name.strip() if isinstance(name, str) and name.strip() else "Liga offen"
    country = country.strip() if isinstance(country, str) else ""
    number = league.get("id")
    return (number if type(number) is int else None, name, _COUNTRY_DE.get(country, country))


def _pick_label(candidate):
    if candidate.market == "Noch ein Tor":
        return "Noch ein Tor"
    if candidate.market == "Nächstes Tor" and candidate.selection != "Kein weiteres Tor":
        return f"Nächstes Tor: {candidate.selection}"
    return candidate.selection


def _percent(candidate):
    return f"{candidate.model_probability:.1f}".removesuffix(".0").replace(".", ",") + " %"


def _show_fixture(ui, game, selected, status, now, format_time, *, pick=False):
    clock = game.clock
    if fresh_age(game.observed_at, now) is None:
        stamp = game.observed_at
        clock += f" · Letzter Stand: {format_time(stamp.isoformat()) if stamp else 'offen'}"
    signal = plain_markdown(status) + (" · Ausgewählt" if selected == game.id else "")
    signal = f":green[**{signal}**]" if pick else f":gray[{signal}]"
    label = f"**{plain_markdown(game.title)}** *{plain_markdown(game.score)}* `{clock}` {signal}"
    return ui.button(label, key=f"live_fixture_{game.id}", width="stretch",
                     type="primary" if selected == game.id else "secondary",
                     on_click=_select_game, args=(ui.session_state, game.id))


def _inspector_header(ui, game, now):
    _, league, country = _competition(game)
    home, away = _team_names(game.fixture)
    status = (game.fixture.get("fixture") or {}).get("status") or {}
    phase, elapsed = status.get("short"), status.get("elapsed")
    badge = "Letzter Stand" if fresh_age(game.observed_at, now) is None else "Live"
    ui.markdown(f'<div class="lv-inspector-kicker"><span>{escape(" · ".join(filter(None, (league, country))))}</span>'
                f'<b>{badge}</b></div><div class="lv-scoreline"><span>{escape(home)}</span>'
                f'<b>{escape(game.score)}</b><span>{escape(away)}</span></div>', unsafe_allow_html=True)
    if type(elapsed) is int and elapsed >= 0 and phase in {"1H", "2H", "HT", "ET", "BT"}:
        limit = 120 if phase in {"ET", "BT"} else 90
        value = 45 if phase == "HT" else min(elapsed, limit)
        middle = "HZ" if limit == 90 else "60′"
        ui.markdown(f'<div class="lv-clock" style="--lv-progress:{100 * value / limit:.2f}%">'
                    '<div class="lv-clock-labels"><span>0′</span>'
                    f'<span>{middle}</span><span>{limit}′</span></div><progress value="{value}" max="{limit}" '
                    f'aria-label="Spielzeit" aria-valuetext="{escape(game.clock)}"></progress>'
                    '<span class="lv-clock-now">'
                    f'{escape(game.clock)}</span></div>', unsafe_allow_html=True)


def _inspector_tip(ui, candidate):
    ui.markdown('<div class="lv-pick"><div><small>Automatischer Live-Tipp</small>'
                f'<strong>{escape(_pick_label(candidate))}</strong></div>'
                f'<div class="lv-percent"><small>Modell</small><b>{_percent(candidate)}</b></div></div>',
                unsafe_allow_html=True)
    notice = "Modellschätzung ohne Preisprüfung."
    if candidate.blockers:
        notice += " Daten- oder Modellprüfung noch offen."
    ui.caption(notice)


def _inspector_footer(ui, game, format_time):
    _, league, _ = _competition(game)
    ui.markdown(f'<div class="lv-pitch" aria-hidden="true"><span class="lv-pitch-minute">{escape(game.clock)}</span></div>'
                '<div class="lv-meta">' + ''.join(f'<div><small>{key}</small><b>{escape(val)}</b></div>'
                for key, val in (("Stand", game.score), ("Zeit", game.clock), ("Liga", league))) + '</div>',
                unsafe_allow_html=True)
    if game.observed_at is not None:
        ui.caption(f"Datenstand: {format_time(game.observed_at.isoformat())}")


def render_board(ui, games, candidates, *, preferred_id, format_time, publish_pick, reasons, now,
                 refresh_issue=None):
    """Show the actual live pick on its fixture row, with a single selectable inspector."""
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
        with ui.container(key="live_scoreboard"):
            count = f"{len(games)} laufende Spiele" if len(games) != 1 else "1 laufendes Spiel"
            ui.markdown(f'<div class="lv-list-title"><h2>Live-Spiele</h2><span>{count} · Automatische Live-Tipps</span></div>',
                        unsafe_allow_html=True)
            if key in ui.session_state and len(by_id) > 1:
                ui.button("Zur automatischen Auswahl", key="live_resume_automatic",
                          on_click=_resume_automatic, args=(ui.session_state,))
            with ui.container(key="live_scoreboard_matches"):
                ui.markdown('<div class="lv-head"><span>Spiel</span><span>Stand</span>'
                            '<span>Zeit</span><span>Live-Tipp</span></div>', unsafe_allow_html=True)
                groups = {}
                for game in games:
                    groups.setdefault(_competition(game), []).append(game)
                for (_, league, country), group in groups.items():
                    context = " · ".join(filter(None, (country, league)))
                    ui.markdown(f'<div class="lv-league">{escape(context)} <small>({len(group)})</small></div>',
                                unsafe_allow_html=True)
                    for game in group:
                        def show(status, *, pick=False):
                            nonlocal selected
                            if _show_fixture(ui, game, selected, status, now, format_time, pick=pick):
                                selected = game.id
                                _select_game(ui.session_state, selected)

                        if game.id in candidates and publish_pick(
                            game, candidates[game.id],
                            lambda c: show(f"{_pick_label(c)} · Modell {_percent(c)}", pick=True),
                        ):
                            continue
                        show(reasons.get(game.id, "Spieldaten fehlen"))
        with ui.container(key="live_detail"):
            game = by_id[selected]
            _inspector_header(ui, game, now)
            if selected not in candidates or not publish_pick(game, candidates[selected], lambda c: _inspector_tip(ui, c)):
                reason = reasons.get(selected, "Spieldaten fehlen")
                ui.markdown(f'<div class="lv-no-pick"><small>Live-Tipp</small><strong>{escape(reason)}</strong></div>',
                            unsafe_allow_html=True)
            _inspector_footer(ui, game, format_time)


def _select_game(state, game_id):
    state["live_selected_fixture_id"] = game_id


def _resume_automatic(state):
    state.pop("live_selected_fixture_id", None)
