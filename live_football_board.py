"""Scoreboard projection and presentation. No provider access, timers or ledgers here."""
from datetime import datetime
from dataclasses import dataclass
from html import escape
from math import isfinite

from football_recommendations import LIVE_MAX_AGE_SECONDS
from live_football_feed import LiveRefreshIssue
from live_football_source import _valid_child, confirmed_live_dismissals
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
    dismissals: tuple[tuple[str, int, int, bool], ...] = ()
    stats_at: datetime | None = None


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
        cards = confirmed_live_dismissals(fixture)
        matchup = " – ".join(name + "".join(f" 🟥 {when}" for when in _card_times(cards, side))
                             for side, name in (("home", home), ("away", away)))
        games.append(Game(game_id, matchup, clock, score, source.get("date"),
                          fixture, row["observed_at"], row["detailed_at"], cards, row.get("stats_at")))
    return ordered_event_rows(games, event_key=lambda g: g.id, starts_at=lambda g: g.start,
                              probability=lambda _: None)


def fresh_age(stamp, now):
    if not isinstance(stamp, datetime) or stamp.utcoffset() is None:
        return None
    seconds = (now - stamp).total_seconds()
    return seconds if 0 <= seconds <= LIVE_MAX_AGE_SECONDS else None


def _card_times(cards, side):
    return [f"{minute}{f'+{extra}' if extra else ''}′" + (" (Bank)" if off_field else "")
            for team, minute, extra, off_field in cards if team == side]


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
    if (candidate.market == "Nächstes Tor" and candidate.selection != "Kein weiteres Tor"
            and not candidate.selection.startswith("Nächstes Tor: ")):
        return f"Nächstes Tor: {candidate.selection}"
    return candidate.selection


def live_percent(percent):
    display = f"{percent:.1f}"
    if display == "100.0" and percent < 100:
        return ">99,9 %"
    if display == "0.0" and percent > 0:
        return "<0,1 %"
    return display.removesuffix(".0").replace(".", ",") + " %"


def _percent(candidate):
    return live_percent(candidate.model_probability)


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
    def team_cell(side, name):
        cards = ''.join(f'<small class="lv-card-fact">Rot {when}</small>' for when in _card_times(game.dismissals, side))
        return f'<span>{escape(name)}{cards}</span>'

    ui.markdown(f'<div class="lv-inspector-kicker"><span>{escape(" · ".join(filter(None, (league, country))))}</span>'
                f'<b>{badge}</b></div><div class="lv-scoreline">{team_cell("home", home)}'
                f'<b>{escape(game.score)}</b>{team_cell("away", away)}</div>', unsafe_allow_html=True)
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


def _inspector_tip(ui, candidate, reason=None):
    ui.markdown('<div class="lv-pick"><div><small>Automatischer Live-Tipp</small>'
                f'<strong>{escape(_pick_label(candidate))}</strong></div>'
                f'<div class="lv-percent"><small>Modell</small><b>{escape(_percent(candidate))}</b></div></div>',
                unsafe_allow_html=True)
    if reason:
        ui.markdown(f'<p class="lv-pick-reason">{escape(reason)}</p>', unsafe_allow_html=True)
    notice = "Modellschätzung ohne Preisprüfung."
    if candidate.blockers:
        notice += " Daten- oder Modellprüfung noch offen."
    ui.caption(notice)


# The display does not require a model-ready pair of xG or a complete event history.
# Only named native fields count: no inferred attacks, complementary possession or null -> zero.
_STAT_FIELDS = (
    ("attacks", "Angriffe", "total attacks"), ("dangerous_attacks", "Gefährliche Angriffe", "dangerous attacks"),
    ("corners", "Eckbälle", "corner kicks"), ("shots", "Schüsse", "total shots"),
    ("on_target", "Schüsse aufs Tor", "shots on goal"), ("xg", "Erwartete Tore (xG)", "expected_goals"),
    ("possession", "Ballbesitz", "ball possession"),
)
_STAT_KEYS = {native: key for key, _, native in _STAT_FIELDS}
_STAT_KEYS["attacks"] = "attacks"


def _stat_number(key, raw):
    if key not in ("xg", "possession"):
        return raw if type(raw) is int and 0 <= raw <= 5000 else None
    if type(raw) not in (int, float, str):
        return None
    if isinstance(raw, str) and key == "possession":
        raw = raw.strip().removesuffix("%")
    try:
        value = float(raw)
    except (ValueError, OverflowError):
        return None
    return value if isfinite(value) and 0 <= value <= (100 if key == "possession" else 20) else None


def native_stat_pairs(fixture, fixture_id):
    """Home/away observations; None means no identified group, not two missing xG."""
    if not isinstance(fixture, dict) or type(fixture_id) is not int or fixture_id <= 0:
        return None
    native, teams, groups = (fixture.get(k) for k in ("fixture", "teams", "statistics"))
    if (not isinstance(native, dict) or type(native.get("id")) is not int or native["id"] != fixture_id
            or not isinstance(teams, dict) or not isinstance(groups, list) or not 1 <= len(groups) <= 2):
        return None
    names = {}
    for side in ("home", "away"):
        team = teams.get(side)
        if not isinstance(team, dict):
            return None
        team_id, name = team.get("id"), team.get("name")
        if type(team_id) is not int or team_id <= 0 or team_id in names or not isinstance(name, str) or not name.strip():
            return None
        names[team_id] = name
    by_team = {}
    for group in groups:
        if not _valid_child(group, fixture_id, names) or not isinstance(group.get("statistics"), list):
            return None
        team_id = group["team"]["id"]
        if team_id in by_team:
            return None
        observed = by_team[team_id] = {}
        for stat in group["statistics"]:
            label = stat.get("type") if isinstance(stat, dict) else None
            key = _STAT_KEYS.get(label.strip().casefold()) if isinstance(label, str) else None
            if key is not None:
                observed[key] = _stat_number(key, stat.get("value")) if key not in observed else None
    return {key: tuple(by_team.get(team, {}).get(key) for team in names) for key, _, _ in _STAT_FIELDS}


def _stat_cell(key, value, total):
    if value is None:
        return '<td aria-label="Nicht gemeldet">–</td>'
    if key == "xg":
        label = f"{value:.2f}".replace(".", ",")
    elif key == "possession":
        label = f"{value:g}".replace(".", ",") + " %"
    else:
        label = str(value)
    share = f' style="--lv-share:{100 * value / total:.2f}%"' if total else ""
    return f'<td{share}>{label}</td>'


def _stat_table(game, now, *, revision_current):
    pairs = (native_stat_pairs(game.fixture, game.id)
             if revision_current and fresh_age(game.stats_at or game.detailed_at, now) is not None else None)
    rows = []
    for key, label, _ in _STAT_FIELDS:
        home, away = pairs[key] if pairs else (None, None)
        if home is None and away is None:
            continue
        total = home + away if home is not None and away is not None else None
        rows.append(f'<tr>{_stat_cell(key, home, total)}<th scope="row">{label}</th>{_stat_cell(key, away, total)}</tr>')
    if not rows:
        return '<div class="lv-stats-empty">Keine aktuellen Statistikdaten.</div>'
    home, away = _team_names(game.fixture)
    return ('<table class="lv-stats"><caption>Spielstatistik</caption><thead><tr>'
            f'<th scope="col">{escape(home)}</th><th scope="col">Kennzahl</th><th scope="col">{escape(away)}</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')


def _inspector_footer(ui, game, now, format_time, *, revision_current):
    _, league, _ = _competition(game)
    ui.markdown(f'<div class="lv-pitch" aria-hidden="true"><span class="lv-pitch-minute">{escape(game.clock)}</span></div>'
                + _stat_table(game, now, revision_current=revision_current) +
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

    def no_pick_reason(game_id):
        return "Live-Stand wird aktualisiert" if game_id in candidates else reasons.get(game_id, "Kein aktueller Live-Tipp")

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
                        show(no_pick_reason(game.id))
        with ui.container(key="live_detail"):
            game = by_id[selected]
            _inspector_header(ui, game, now)
            has_candidate = selected in candidates
            revision_current = not has_candidate or publish_pick(
                game, candidates[selected], lambda c: _inspector_tip(
                    ui, c, (candidates[selected][1].get("live_comparison") or {}).get("reason")))
            if not has_candidate or not revision_current:
                reason = no_pick_reason(selected)
                ui.markdown(f'<div class="lv-no-pick"><small>Live-Tipp</small><strong>{escape(reason)}</strong></div>',
                            unsafe_allow_html=True)
            _inspector_footer(ui, game, now, format_time, revision_current=revision_current)


def _select_game(state, game_id):
    state["live_selected_fixture_id"] = game_id


def _resume_automatic(state):
    state.pop("live_selected_fixture_id", None)
