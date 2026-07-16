"""Responsive alternative-market workflow for one selected fixture at a time."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from alternative_markets import MatchResultPredictor, PreMatchAlternativeAnalyzer
from config_loader import load_app_config
from league_catalog import ALTERNATIVE_MARKET_LEAGUES
from season_utils import current_season_start_year_for_id

try:
    from smart_bet_finder import SmartBetFinder, display_smart_bet

    SMART_BET_AVAILABLE = True
except ImportError:
    SMART_BET_AVAILABLE = False


DEFAULT_LEAGUES = [78, 39, 140]
MARKET_SNAPSHOT_VERSION = 2


def _segmented(label: str, options: list[str], key: str, default: str) -> str:
    if hasattr(st, "segmented_control"):
        value = st.segmented_control(
            label,
            options,
            default=default,
            key=key,
            selection_mode="single",
        )
        return value or default
    return st.radio(label, options, index=options.index(default), horizontal=True, key=key)


def _model_price(probability: Optional[float]) -> Optional[float]:
    if probability is None or probability <= 0:
        return None
    return 1.0 / probability


def _rounded_model_price(probability: Optional[float]) -> Optional[float]:
    price = _model_price(probability)
    return round(price, 2) if price is not None else None


def _signal_label(probability: float) -> str:
    if probability >= 0.80:
        return "Sehr stark"
    if probability >= 0.70:
        return "Stark"
    if probability >= 0.60:
        return "Moderat"
    if probability >= 0.50:
        return "Schwach"
    return "Kein Signal"


def _market_scope_signature(leagues: list[int], search_date) -> dict:
    return {
        "league_ids": sorted(int(league_id) for league_id in leagues),
        "date": search_date.isoformat(),
    }


def _format_snapshot_time(value: Optional[str]) -> str:
    if not value:
        return "n/a"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def _fixture_model_input(match: dict) -> dict:
    return {
        "home_team_id": match["teams"]["home"]["id"],
        "away_team_id": match["teams"]["away"]["id"],
        "league_id": match["league"]["id"],
        "season": match.get("league", {}).get("season"),
        "home_team": match["teams"]["home"]["name"],
        "away_team": match["teams"]["away"]["name"],
    }


def _collect_match_analysis(match: dict, api_key: str) -> dict:
    """Collect API-backed market probabilities without mixing in bookmaker prices."""
    fixture = _fixture_model_input(match)
    analysis = {
        "fixture_id": match.get("fixture", {}).get("id"),
        "fixture_date": match.get("fixture", {}).get("date"),
        "league_id": match.get("league", {}).get("id"),
        "data_sources": {},
    }
    analyzer = PreMatchAlternativeAnalyzer(api_key=api_key)

    try:
        corners = analyzer.analyze_prematch_corners(fixture)
        if corners and corners.get("thresholds"):
            analysis["corners"] = {
                key: {
                    "probability": value.get("probability", 0),
                    "threshold": value.get("threshold", 0),
                }
                for key, value in corners["thresholds"].items()
            }
            analysis["corners"]["expected_total"] = corners.get("expected_total")
            analysis["corners"]["confidence"] = corners.get("confidence", "MEDIUM")
            analysis["data_sources"]["corners"] = "API_FIXTURE_HISTORY"
    except Exception as exc:
        analysis.setdefault("errors", {})["corners"] = str(exc)

    try:
        cards = analyzer.analyze_prematch_cards(fixture)
        if cards and cards.get("thresholds"):
            analysis["cards"] = {
                key: {
                    "probability": value.get("probability", 0),
                    "threshold": value.get("threshold", 0),
                }
                for key, value in cards["thresholds"].items()
            }
            analysis["cards"]["expected_total"] = cards.get("expected_total")
            analysis["cards"]["confidence"] = cards.get("confidence", "MEDIUM")
            analysis["data_sources"]["cards"] = "API_TEAM_HISTORY"
    except Exception as exc:
        analysis.setdefault("errors", {})["cards"] = str(exc)
    return analysis


def _market_rows(market: str, result: dict) -> list[dict]:
    rows = []
    for data in result.get("thresholds", {}).values():
        probability = data.get("probability")
        threshold = data.get("threshold")
        if probability is None or threshold is None:
            continue
        over = float(probability) / 100.0
        under = 1.0 - over
        rows.extend(
            [
                {
                    "Markt": market,
                    "Auswahl": f"Over {threshold}",
                    "Modell %": round(over * 100, 1),
                    "Modellpreis": _rounded_model_price(over),
                    "Signal": _signal_label(over),
                },
                {
                    "Markt": market,
                    "Auswahl": f"Under {threshold}",
                    "Modell %": round(under * 100, 1),
                    "Modellpreis": _rounded_model_price(under),
                    "Signal": _signal_label(under),
                },
            ]
        )
    return rows


def _render_corners_cards_analysis(match: dict, api_key: str) -> None:
    fixture = _fixture_model_input(match)
    analyzer = PreMatchAlternativeAnalyzer(api_key=api_key)
    with st.spinner("Liga- und venue-spezifische Stichproben werden geladen..."):
        corners = analyzer.analyze_prematch_corners(fixture)
        cards = analyzer.analyze_prematch_cards(fixture)

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    st.subheader(f"{home} vs {away}")
    st.caption(match["league"]["name"])

    metrics = st.columns(4)
    metrics[0].metric(
        "Erwartete Corners",
        f"{corners['expected_total']:.1f}" if corners.get("expected_total") is not None else "n/a",
    )
    metrics[1].metric("Corner-Qualität", corners.get("confidence", "n/a"))
    metrics[2].metric(
        "Erwartete Karten",
        f"{cards['expected_total']:.1f}" if cards.get("expected_total") is not None else "n/a",
    )
    metrics[3].metric("Karten-Qualität", cards.get("confidence", "n/a"))

    corner_quality = corners.get("data_quality", {})
    card_quality = cards.get("data_quality", {})
    st.caption(
        "Stichproben Heim/Auswärts: "
        f"Corners {corner_quality.get('home_matches', 0)}/{corner_quality.get('away_matches', 0)}, "
        f"Karten {card_quality.get('home_matches', 0)}/{card_quality.get('away_matches', 0)}"
    )

    rows = _market_rows("Corners", corners) + _market_rows("Karten", cards)
    if not rows:
        st.warning("Die Mindeststichprobe für Corners oder Karten ist nicht erreicht.")
        return
    frame = pd.DataFrame(rows).sort_values(
        ["Markt", "Modell %"], ascending=[True, False]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.caption(
        "Unkalibrierte Modellwahrscheinlichkeiten. Der Modellpreis ist 1/p und keine Buchmacherquote."
    )


def _request_team_fixtures(
    api_key: str,
    team_id: int,
    league_id: int,
    season: int,
) -> list[dict]:
    response = requests.get(
        "https://v3.football.api-sports.io/fixtures",
        headers={"x-apisports-key": api_key},
        params={
            "team": team_id,
            "league": league_id,
            "season": season,
            "last": 20,
            "status": "FT",
        },
        timeout=15,
    )
    response.raise_for_status()
    fixtures = response.json().get("response", [])
    return sorted(
        fixtures,
        key=lambda fixture: fixture.get("fixture", {}).get("date", ""),
        reverse=True,
    )


def _venue_history(fixtures: list[dict], team_id: int, venue: str) -> dict:
    history = {"goals_scored": [], "goals_conceded": []}
    for fixture in fixtures:
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})
        if teams.get(venue, {}).get("id") != team_id:
            continue
        home_goals = goals.get("home")
        away_goals = goals.get("away")
        if not isinstance(home_goals, int) or not isinstance(away_goals, int):
            continue
        if home_goals < 0 or away_goals < 0:
            continue
        if venue == "home":
            history["goals_scored"].append(home_goals)
            history["goals_conceded"].append(away_goals)
        else:
            history["goals_scored"].append(away_goals)
            history["goals_conceded"].append(home_goals)
        if len(history["goals_scored"]) == 10:
            break
    return history


def _probability_row(market: str, selection: str, probability: float) -> dict:
    return {
        "Markt": market,
        "Auswahl": selection,
        "Modell %": round(probability * 100, 1),
        "Modellpreis": _rounded_model_price(probability),
        "Signal": _signal_label(probability),
    }


def _prediction_rows(prediction) -> list[dict]:
    rows = [
        _probability_row("1X2", "Heim", prediction.home_win_prob),
        _probability_row("1X2", "Remis", prediction.draw_prob),
        _probability_row("1X2", "Auswärts", prediction.away_win_prob),
        _probability_row("Doppelte Chance", "1X", prediction.home_or_draw),
        _probability_row("Doppelte Chance", "X2", prediction.draw_or_away),
        _probability_row("Doppelte Chance", "12", prediction.home_or_away),
        _probability_row("BTTS", "Ja", prediction.btts_yes),
        _probability_row("BTTS", "Nein", prediction.btts_no),
    ]
    for threshold in (1.5, 2.5, 3.5):
        over, under = prediction.over_under[threshold]
        rows.append(_probability_row("Tore", f"Over {threshold}", over))
        rows.append(_probability_row("Tore", f"Under {threshold}", under))
    return rows


def _render_match_result_analysis(match: dict, api_key: str) -> None:
    home = match["teams"]["home"]
    away = match["teams"]["away"]
    league = match["league"]
    with st.spinner("Venue-spezifische Teamhistorien werden geladen..."):
        home_fixtures = _request_team_fixtures(
            api_key, home["id"], league["id"], league["season"]
        )
        away_fixtures = _request_team_fixtures(
            api_key, away["id"], league["id"], league["season"]
        )
        home_history = _venue_history(home_fixtures, home["id"], "home")
        away_history = _venue_history(away_fixtures, away["id"], "away")

    home_sample = len(home_history["goals_scored"])
    away_sample = len(away_history["goals_scored"])
    if min(home_sample, away_sample) < MatchResultPredictor.MIN_SAMPLE:
        st.warning("Mindestens fünf Liga- und venue-spezifische Spiele pro Team sind nötig.")
        return

    predictor = MatchResultPredictor(league_id=league["id"])
    prediction = predictor.predict_match(home_history, away_history)
    st.subheader(f"{home['name']} vs {away['name']}")
    st.caption(
        f"{league['name']} | Stichproben Heim/Auswärts: {home_sample}/{away_sample}"
    )

    metrics = st.columns(3)
    metrics[0].metric(f"xG {home['name']}", f"{prediction.home_xg:.2f}")
    metrics[1].metric("xG gesamt", f"{prediction.total_xg:.2f}")
    metrics[2].metric(f"xG {away['name']}", f"{prediction.away_xg:.2f}")

    frame = pd.DataFrame(_prediction_rows(prediction))
    st.dataframe(frame, use_container_width=True, hide_index=True)
    strongest = frame.sort_values("Modell %", ascending=False).iloc[0]
    st.info(
        f"Stärkstes Modellsignal: {strongest['Auswahl']} ({strongest['Modell %']:.1f}%). "
        "Ohne verifizierte Quote keine Edge-, EV- oder Einsatz-Aussage."
    )
    st.caption(
        "Unkalibrierte unabhängige Poisson-Basis; kein fixer Heim-, H2H-, Wetter- oder Quotenfaktor."
    )


def _render_value_analysis(match: dict, api_key: str) -> None:
    if not SMART_BET_AVAILABLE:
        st.error("Smart Bet Finder ist nicht verfügbar.")
        return
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    with st.spinner("Modell und exakte Marktquote werden geprüft..."):
        match_analysis = _collect_match_analysis(match, api_key)
        config = load_app_config(st)
        finder = SmartBetFinder(
            odds_api_key=config.odds_api_key,
            api_football_key=api_key,
        )
        bets = finder.find_value_bets(match_analysis, home, away)

    st.subheader(f"{home} vs {away}")
    if not bets:
        st.warning(
            "Kein zulässiger Value-Kandidat: Kalibrierung, exaktes Fixture, frische vollständige "
            "Same-Book-Quote und Overround müssen gemeinsam bestehen."
        )
        return
    for rank, bet in enumerate(bets, start=1):
        display_smart_bet(bet, rank)


def _fixture_label(match: dict) -> str:
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    league = match["league"]["name"]
    raw_date = match.get("fixture", {}).get("date", "")
    try:
        local_time = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone()
        time_text = local_time.strftime("%H:%M")
    except (AttributeError, TypeError, ValueError):
        time_text = "n/a"
    return f"{time_text} | {home} vs {away} | {league}"


def _load_fixtures(api_key: str, leagues: list[int], search_date) -> tuple[list[dict], list[str]]:
    fixtures = []
    errors = []
    progress = st.progress(0)
    status = st.empty()
    total = max(len(leagues), 1)
    try:
        for index, league_id in enumerate(leagues):
            status.caption(
                f"Lade {ALTERNATIVE_MARKET_LEAGUES.get(league_id, league_id)} "
                f"({index + 1}/{len(leagues)})"
            )
            try:
                season = current_season_start_year_for_id(league_id, search_date)
                response = requests.get(
                    "https://v3.football.api-sports.io/fixtures",
                    headers={"x-apisports-key": api_key},
                    params={
                        "league": league_id,
                        "season": season,
                        "date": search_date.strftime("%Y-%m-%d"),
                    },
                    timeout=15,
                )
                response.raise_for_status()
                fixtures.extend(response.json().get("response", []))
            except (requests.RequestException, ValueError, TypeError) as exc:
                league_name = ALTERNATIVE_MARKET_LEAGUES.get(league_id, str(league_id))
                errors.append(f"{league_name}: {exc}")
            progress.progress((index + 1) / total)
    finally:
        status.empty()
        progress.empty()
    return fixtures, errors


def create_alternative_markets_tab_extended() -> None:
    """Render a linear search, select, analyze workflow."""
    api_key = load_app_config(st).api_football_key
    if not api_key:
        st.error("API-Football-Key fehlt.")
        return

    st.subheader("Matchauswahl")
    league_scope = _segmented(
        "Ligen",
        ["Favoriten", "Auswahl", "Alle"],
        "market_league_scope",
        "Favoriten",
    )
    available_ids = list(ALTERNATIVE_MARKET_LEAGUES)
    favorites = [league_id for league_id in DEFAULT_LEAGUES if league_id in available_ids]
    if league_scope == "Favoriten":
        selected_leagues = favorites
        st.caption(
            ", ".join(ALTERNATIVE_MARKET_LEAGUES[league_id] for league_id in selected_leagues)
        )
    elif league_scope == "Alle":
        selected_leagues = available_ids
        st.caption(f"{len(selected_leagues)} Ligen")
    else:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            available_ids,
            default=favorites,
            format_func=lambda league_id: ALTERNATIVE_MARKET_LEAGUES.get(
                league_id, f"Liga {league_id}"
            ),
            key="market_selected_leagues",
        )

    date_mode = _segmented(
        "Datum",
        ["Heute", "Morgen", "Auswahl"],
        "market_date_mode",
        "Heute",
    )
    if date_mode == "Heute":
        search_date = datetime.now().date()
    elif date_mode == "Morgen":
        search_date = (datetime.now() + timedelta(days=1)).date()
    else:
        search_date = st.date_input(
            "Spieldatum", datetime.now().date(), key="market_custom_date"
        )

    action_columns = st.columns([1, 2])
    load_matches = action_columns[0].button(
        "Matches laden",
        type="primary",
        use_container_width=True,
        key="load_market_matches",
    )
    if load_matches and not selected_leagues:
        st.warning("Mindestens eine Liga auswählen.")
    elif load_matches:
        try:
            fixtures, errors = _load_fixtures(api_key, selected_leagues, search_date)
            st.session_state["market_fixtures"] = fixtures
            st.session_state["tab7_fixtures"] = fixtures
            st.session_state["market_snapshot_meta"] = {
                "version": MARKET_SNAPSHOT_VERSION,
                "scanned_at": datetime.now().astimezone().isoformat(),
                "scope": _market_scope_signature(selected_leagues, search_date),
            }
            if fixtures:
                st.success(f"{len(fixtures)} Matches gefunden.")
            else:
                st.warning("Für Datum und Ligen wurden keine Matches gefunden.")
            if errors:
                st.info(f"{len(errors)} Liga-Abfragen waren nicht verfügbar; übrige Ergebnisse bleiben sichtbar.")
        except Exception as exc:
            st.error(f"Matchsuche fehlgeschlagen: {exc}")

    fixtures = st.session_state.get("market_fixtures", [])
    snapshot_meta = st.session_state.get("market_snapshot_meta")
    if not isinstance(snapshot_meta, dict):
        if fixtures:
            st.warning("Dieser Markt-Snapshot besitzt keinen gültigen Scope. Matches neu laden.")
        else:
            st.info("Noch kein Markt-Snapshot in dieser Sitzung.")
        return
    if snapshot_meta.get("version") != MARKET_SNAPSHOT_VERSION:
        st.warning("Dieser Markt-Snapshot stammt aus einer älteren App-Version. Matches neu laden.")
        return
    current_scope = _market_scope_signature(selected_leagues, search_date)
    if snapshot_meta.get("scope") != current_scope:
        st.warning("Ligaauswahl oder Datum wurden seit dem Snapshot geändert. Matches neu laden.")
        return
    st.caption(f"Snapshot: {_format_snapshot_time(snapshot_meta.get('scanned_at'))}")
    if not fixtures:
        st.info("Dieser Snapshot enthält keine Matches für Datum und Ligaauswahl.")
        return
    fixture_rows = [
        {
            "Zeit / Match / Liga": _fixture_label(match),
            "Fixture-ID": match.get("fixture", {}).get("id"),
        }
        for match in fixtures
    ]
    st.dataframe(pd.DataFrame(fixture_rows), use_container_width=True, hide_index=True)

    fixture_ids = [match["fixture"]["id"] for match in fixtures]
    by_id = {match["fixture"]["id"]: match for match in fixtures}
    fixture_key = "market_fixture_id"
    if st.session_state.get(fixture_key) not in fixture_ids:
        st.session_state[fixture_key] = fixture_ids[0]
    selected_id = st.selectbox(
        "Match",
        fixture_ids,
        format_func=lambda fixture_id: _fixture_label(by_id[fixture_id]),
        key=fixture_key,
    )
    mode = _segmented(
        "Analyse",
        ["Resultat", "Corners & Karten", "Value"],
        "market_analysis_mode",
        "Resultat",
    )
    labels = {
        "Resultat": "Resultat analysieren",
        "Corners & Karten": "Corners und Karten analysieren",
        "Value": "Verifizierten Preis prüfen",
    }
    if not st.button(
        labels[mode],
        type="primary",
        use_container_width=True,
        key="run_market_analysis",
    ):
        return

    selected_match = by_id[selected_id]
    try:
        if mode == "Resultat":
            _render_match_result_analysis(selected_match, api_key)
        elif mode == "Corners & Karten":
            _render_corners_cards_analysis(selected_match, api_key)
        else:
            _render_value_analysis(selected_match, api_key)
    except Exception as exc:
        st.error(f"Marktanalyse fehlgeschlagen: {exc}")
