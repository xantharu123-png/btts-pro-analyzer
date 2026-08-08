"""Tennis tab: daily model tips, optional price check, settlement.

UX discipline (same as football): one clear verdict per match —
"WETTE" or "KEINE WETTE" — with the exact blocking reasons in plain
German inside an expander.  No jargon, no duplicated verdicts.

Data flow:
- predictions arrive via scripts/tennis_daily.py (scheduled every
  morning) and live in tennis/data/tennis_shadow.db
- the calibrated winner model produces a concrete selection and minimum price
- an optional bookmaker price check evaluates the risk-adjusted EV from the
  stored probability (no model reload needed)
- settlement is manual (winner + optional retirement note) until the
  weekly stats refresh can confirm results automatically

Nothing here recommends real money: this is the shadow phase.  The
verdict tells you what the model WOULD bet; the CLV protocol decides
later whether it was right.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

import scan_jobs
from betting_math import (
    MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
    BettingMathError,
    evaluate_market_price,
    minimum_acceptable_odds,
)
from ui_components import scan_progress_fragment
from tennis import shadow
from tennis.predict import (
    MIN_EXPECTED_ROI,
    SIDE_MARKET_PROBABILITY_HAIRCUT,
    WINNER_PROBABILITY_HAIRCUT,
)
from tennis.shadow import SIDE_MARKETS

DB_PATH = shadow.DB_PATH
DAILY_SCRIPT = Path(__file__).resolve().parent / "scripts" / "tennis_daily.py"
ZURICH_TZ = ZoneInfo("Europe/Zurich")


# --------------------------------------------------------------------- helpers


def _load_predictions(
    date_from: str | None = None,
    *,
    date_to: str | None = None,
    unsettled_only: bool = False,
    current_only: bool = True,
) -> list[dict]:
    if not DB_PATH.exists():
        return []
    shadow.ensure_schema()
    query = "SELECT * FROM predictions"
    clauses = []
    params: list[str] = []
    if current_only:
        clauses.extend(("model_version=?", "policy_version=?"))
        params.extend(
            (shadow.TENNIS_MODEL_VERSION, shadow.TENNIS_POLICY_VERSION)
        )
    if date_from:
        clauses.append("match_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("match_date <= ?")
        params.append(date_to)
    if unsettled_only:
        clauses.append("settled=0")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY match_date, tour, tournament, id"
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(query, tuple(params)).fetchall()]


def _parse_start_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _zurich_today(now_utc: datetime | None = None) -> str:
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ZURICH_TZ).date().isoformat()


def _next_tennis_scan_date(
    now_utc: datetime | None = None,
    *,
    today_value: str | None = None,
) -> date:
    local_today = today_value or _zurich_today(now_utc)
    return date.fromisoformat(local_today) + timedelta(days=1)


def _prematch_visibility(
    row: dict,
    now_utc: datetime | None = None,
) -> tuple[bool, str | None]:
    """Only a verified fixture whose scheduled start is ahead is actionable."""
    if int(row.get("settled") or 0):
        return False, "bereits abgerechnet"
    start = _parse_start_utc(row.get("scheduled_start_utc"))
    if start is None:
        return False, "Startzeit nicht verifiziert"
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if start <= current.astimezone(timezone.utc):
        return False, "angesetzte Startzeit erreicht"
    return True, None


def _split_prematch_rows(
    rows: list[dict],
    now_utc: datetime | None = None,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    visible = []
    hidden = []
    for row in rows:
        allowed, reason = _prematch_visibility(row, now_utc)
        if allowed:
            visible.append(row)
        else:
            hidden.append((row, reason or "nicht mehr startbar"))
    return visible, hidden


def _format_start_local(value: str | None) -> str:
    start = _parse_start_utc(value)
    if start is None:
        return "Startzeit nicht verifiziert"
    return start.astimezone(ZURICH_TZ).strftime("%d.%m.%Y, %H:%M Uhr")


def _closing_window_state(
    row: dict,
    now_utc: datetime | None = None,
) -> tuple[str, float | None]:
    start = _parse_start_utc(row.get("scheduled_start_utc"))
    if start is None:
        return "unverified", None
    current = now_utc or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    lead = (start - current.astimezone(timezone.utc)).total_seconds()
    if lead < 0:
        return "closed", lead
    if lead > shadow.CLOSING_WINDOW_SECONDS:
        return "early", lead
    return "open", lead


def _update_price_check(
    row_id: int,
    odds_a: float,
    odds_b: float,
    p_cal: float,
    model_gates_ok: bool,
) -> dict:
    """Evaluate the shared risk-adjusted EV gate and persist the Shadow pick."""
    shadow.ensure_schema()
    prices_ok = odds_a > 1.0 and odds_b > 1.0
    metrics_a = metrics_b = None
    if prices_ok:
        try:
            metrics_a = evaluate_market_price(
                p_cal * 100.0,
                odds_a,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            )
            metrics_b = evaluate_market_price(
                (1.0 - p_cal) * 100.0,
                odds_b,
                probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            )
        except BettingMathError:
            prices_ok = False
            metrics_a = metrics_b = None
    edge_a = (
        metrics_a.risk_adjusted_edge / 100.0 if metrics_a is not None else 0.0
    )
    edge_b = (
        metrics_b.risk_adjusted_edge / 100.0 if metrics_b is not None else 0.0
    )
    risk_ev_a = (
        metrics_a.risk_adjusted_expected_roi / 100.0
        if metrics_a is not None
        else float("-inf")
    )
    risk_ev_b = (
        metrics_b.risk_adjusted_expected_roi / 100.0
        if metrics_b is not None
        else float("-inf")
    )
    side = edge = 0.0
    verdict = "KEINE WETTE"
    if prices_ok and model_gates_ok:
        if risk_ev_a >= risk_ev_b and risk_ev_a >= MIN_EXPECTED_ROI:
            side, edge = "A", edge_a
        elif risk_ev_b > risk_ev_a and risk_ev_b >= MIN_EXPECTED_ROI:
            side, edge = "B", edge_b
        if side:
            verdict = "WETTE"
    if prices_ok:
        shadow.record_entry_prices(
            row_id,
            odds_a,
            odds_b,
        )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE predictions SET recommended_side=?, "
            "recommended_edge=?, verdict=?, policy_version=? "
            "WHERE id=?",
            (
                side or None,
                edge or None,
                verdict,
                shadow.TENNIS_POLICY_VERSION,
                row_id,
            ),
        )
    return {
        "prices_ok": prices_ok,
        "edge_a": edge_a,
        "edge_b": edge_b,
        "risk_ev_a": risk_ev_a,
        "risk_ev_b": risk_ev_b,
        "side": side,
        "verdict": verdict,
    }


def _run_daily_scan(search_date: str | None = None) -> str:
    command = [sys.executable, str(DAILY_SCRIPT)]
    if search_date:
        command.append(str(search_date))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(DAILY_SCRIPT.parent.parent),
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    output = output.strip()
    if result.returncode != 0:
        detail = output[-1200:] if output else "Kein Prozess-Output"
        raise RuntimeError(
            f"Tennis-Tageslauf endete mit Code {result.returncode}: {detail}"
        )
    return output


def _run_tennis_scan_worker(
    search_date: str | None = None,
    search_end_date: str | None = None,
    progress_cb=None,
) -> str:
    """Run the tennis model once for every day in a bounded search window."""
    if search_date is None:
        if search_end_date is not None:
            raise ValueError("search_end_date benötigt search_date")
        if progress_cb:
            progress_cb(0.1, "Tennis-Modell wird aktualisiert …")
        output = _run_daily_scan()
        if progress_cb:
            progress_cb(1.0, "Fertig")
        return output

    try:
        start_date = date.fromisoformat(str(search_date))
        end_date = date.fromisoformat(str(search_end_date or search_date))
    except ValueError as exc:
        raise ValueError("Ungültiger Tennis-Suchzeitraum") from exc
    horizon = (end_date - start_date).days
    if not 0 <= horizon <= 14:
        raise ValueError("Tennis-Suchzeitraum darf höchstens 14 Tage umfassen")

    outputs = []
    total_days = horizon + 1
    for index in range(total_days):
        target_date = start_date + timedelta(days=index)
        if progress_cb:
            progress_cb(
                0.05 + 0.90 * index / total_days,
                f"Tennis {index + 1}/{total_days}: {target_date:%d.%m.%Y}",
            )
        outputs.append(_run_daily_scan(target_date.isoformat()))
    if progress_cb:
        progress_cb(1.0, "Fertig")
    return "\n\n".join(outputs)


# ------------------------------------------------------------------- rendering


def _render_shadow_summary() -> None:
    summary = shadow.summary()
    cols = st.columns(5)
    cols[0].metric("Vorhersagen gesamt", summary["predictions"])
    cols[1].metric("Offen", summary["open"])
    cols[2].metric("Abgerechnet", summary["settled"])
    cols[3].metric("Empfohlene Wetten", summary["recommended_bets"])
    roi = summary["roi"]
    cols[4].metric(
        "Shadow-Bilanz (Units)",
        summary["units"],
        delta=f"{roi:+.1%} ROI" if roi is not None else None,
    )
    st.caption(
        "Shadow bedeutet: Entscheidung und Quote werden vor dem Start eingefroren, "
        "danach werden Ergebnis, Kalibrierung und eine startzeitnahe "
        "Startzeitnahe Referenzquote verglichen. "
        "Das prüft das Modell, garantiert aber keinen Gewinn."
    )
    st.caption(
        f"Aktuelle Auswahl-Policy: {summary.get('policy_version', 'unbekannt')}. "
        "Empfehlungs-ROI und CLV werden nicht mit älteren Policies vermischt."
    )
    evidence_cols = st.columns(2)
    clv = summary.get("clv")
    evidence_cols[0].metric(
        f"Sieger-CLV (n={summary.get('clv_samples', 0)})",
        f"{clv:+.1%}" if clv is not None else "Noch offen",
    )
    brier = summary.get("brier")
    evidence_cols[1].metric(
        f"Brier Score (n={summary.get('brier_samples', 0)})",
        f"{brier:.3f}" if brier is not None else "Noch offen",
    )
    if summary.get("benchmark_samples"):
        st.caption(
            "Brier auf identischer CLV-Stichprobe, kleiner ist besser: "
            f"Modell {summary['benchmark_model_brier']:.3f} · "
            f"Referenzmarkt {summary['benchmark_market_brier']:.3f} · "
            f"n={summary['benchmark_samples']}."
        )
    side = shadow.side_bet_summary()
    if side["side_bets"]:
        cols = st.columns(4)
        cols[0].metric("Satz-Markt Wetten", side["side_bets"])
        cols[1].metric("Offen", side["open"])
        cols[2].metric("Abgerechnet", side["settled"])
        roi = side["roi"]
        cols[3].metric(
            "Satz-Markt Bilanz (Units)",
            side["units"],
            delta=f"{roi:+.1%} ROI" if roi is not None else None,
        )
        side_clv = side.get("clv")
        st.caption(
            f"Satz-Markt CLV: {side_clv:+.1%} "
            f"(n={side.get('clv_samples', 0)})"
            if side_clv is not None
            else "Satz-Markt CLV: noch keine startzeitnahe Referenzquote."
        )


def _render_gate_badges(gates: dict) -> None:
    for name, info in gates.items():
        icon = "✅" if info.get("passed") else "⛔"
        st.markdown(f"{icon} **{name}** — {info.get('detail', '')}")


def _render_market_sheet(markets: dict, best_of: int) -> None:
    if markets.get("expected_games") is None:
        st.caption(
            "Keine Satz- oder Tiebreak-Modellierung: Mindestens einem Spieler "
            "fehlen ausreichend zugeordnete Aufschlagdaten."
        )
        return
    cols = st.columns(4)
    cols[0].metric("Erwartete Games", markets.get("expected_games", "n/a"))
    cols[1].metric("Tiebreak im Match", f"{markets.get('p_tiebreak', 0):.0%}")
    if best_of == 5:
        cols[2].metric("Über 3,5 Sätze", f"{markets.get('over_3_5_sets', 0):.0%}")
        cols[3].metric("Über 4,5 Sätze", f"{markets.get('over_4_5_sets', 0):.0%}")
    else:
        cols[2].metric("Über 2,5 Sätze", f"{markets.get('over_2_5_sets', 0):.0%}")
    st.caption(
        "Games-Märkte (Über 21,5 & Co.) zeigt die App bewusst nicht: Im Kalibrierungs-"
        "Backtest (9.647 ATP-Matches) liegt der Simulator dort 5–7 Prozentpunkte "
        "daneben — genau in die Richtung, in die Buchmacher ihre Linien setzen. "
        "Satz-Märkte sind dagegen kalibriert und werden mit fairen Preisen angeboten."
    )


_SIDE_MARKET_KEYS = {
    "over_2_5_sets": "over_2_5_sets",
    "under_2_5_sets": "under_2_5_sets",
    "set_a_2_0": "set_handicap_a_minus_1_5",
    "set_b_2_0": "set_handicap_b_minus_1_5",
}


def _render_side_markets(row: dict, markets: dict, model_gates_ok: bool) -> None:
    """Render calibrated set markets with an optional price check."""
    if not model_gates_ok or int(row.get("best_of") or 3) != 3:
        return  # calibration was measured on Bo3; Bo5 stays out for now
    available = {
        code: markets[key]
        for code, key in _SIDE_MARKET_KEYS.items()
        if markets.get(key) is not None
    }
    if not available:
        return

    st.markdown(
        "**Satz-Märkte** (Shadow-only; expliziter "
        f"{SIDE_MARKET_PROBABILITY_HAIRCUT:+.0%} Modellabschlag und mindestens "
        f"{MIN_EXPECTED_ROI:+.0%} Risiko-EV)"
    )
    tracked = {
        b["market"]: b
        for b in shadow.side_bets_for([row["id"]])
        if not b["settled"]
    }
    for code, p in available.items():
        label = SIDE_MARKETS[code]["label"].replace("A ", f"{row['player_a']} ").replace("B ", f"{row['player_b']} ")
        cols = st.columns([3, 1, 1, 1])
        fair = 1.0 / p if p > 0 else float("inf")
        cols[0].markdown(f"{label}  \n{p:.0%} · fair {fair:.2f}")
        if code in tracked:
            b = tracked[code]
            cols[1].markdown(f"**{b['odds']:.2f}**")
            tracked_metrics = evaluate_market_price(
                b["model_p"] * 100.0,
                b["odds"],
                probability_haircut=SIDE_MARKET_PROBABILITY_HAIRCUT * 100.0,
            )
            cols[2].markdown(
                f"EV {tracked_metrics.risk_adjusted_expected_roi / 100.0:+.1%}"
            )
            cols[3].caption("getrackt ✓")
            window, _ = _closing_window_state(row)
            if b.get("closing_checked_utc"):
                st.caption(
                    f"Startzeitnahe Referenzquote gespeichert: "
                    f"{b['closing_odds']:.2f}"
                )
            elif window == "open":
                closing_cols = st.columns([3, 1])
                closing_odds = closing_cols[0].number_input(
                    f"Startquote {label}",
                    min_value=1.01,
                    max_value=50.0,
                    value=float(b["odds"]),
                    step=0.01,
                    format="%.2f",
                    key=f"side_closing_capture_{b['id']}",
                )
                if closing_cols[1].button(
                    "Referenz speichern",
                    key=f"side_closing_btn_{b['id']}",
                    use_container_width=True,
                ):
                    try:
                        shadow.record_side_closing_price(b["id"], closing_odds)
                    except (KeyError, ValueError) as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            continue
        odds = cols[1].number_input(
            "Buchmacherquote", min_value=1.01, max_value=50.0, value=None,
            step=0.01, format="%.2f", key=f"side_odds_{code}_{row['id']}",
            placeholder="Quote",
            label_visibility="collapsed",
        )
        if odds is None:
            risk_ev = float("-inf")
            adjusted_edge = 0.0
            ok = False
            cols[2].caption("Quote fehlt")
        else:
            price_metrics = evaluate_market_price(
                p * 100.0,
                odds,
                probability_haircut=SIDE_MARKET_PROBABILITY_HAIRCUT * 100.0,
            )
            risk_ev = price_metrics.risk_adjusted_expected_roi / 100.0
            adjusted_edge = price_metrics.risk_adjusted_edge / 100.0
            ok = risk_ev >= MIN_EXPECTED_ROI
            cols[2].markdown(f"**{risk_ev:+.1%}**" if ok else f"{risk_ev:+.1%}")
        if cols[3].button("Track", key=f"side_track_{code}_{row['id']}",
                          disabled=not ok, use_container_width=True):
            shadow.store_side_bet(row["id"], code, p, odds, adjusted_edge)
            st.rerun()


def _render_winner_closing_capture(row: dict) -> None:
    if row.get("recommended_side") not in ("A", "B"):
        return
    if row.get("closing_checked_utc"):
        st.caption(
            "Startzeitnahe Referenzquoten gespeichert: "
            f"{row['closing_odds_a']:.2f} / {row['closing_odds_b']:.2f}."
        )
        return

    window, lead = _closing_window_state(row)
    if window == "early":
        minutes = max(int((lead or 0) // 60), 0)
        st.caption(
            f"CLV-Referenz wird in den letzten 60 Minuten vor dem angesetzten "
            f"Start erfasst (noch ca. {minutes} Min.)."
        )
        return
    if window != "open":
        return

    with st.expander("Startzeitnahe Referenzquote erfassen"):
        st.caption(
            "Nur jetzt vor dem angesetzten Start speichern. Diese Preise werden "
            "später nicht rückwirkend ergänzt."
        )
        cols = st.columns([1, 1, 1])
        closing_a = cols[0].number_input(
            f"Referenz {row['player_a']}",
            min_value=1.01,
            max_value=50.0,
            value=float(row.get("odds_a") or 1.50),
            step=0.01,
            format="%.2f",
            key=f"closing_capture_a_{row['id']}",
        )
        closing_b = cols[1].number_input(
            f"Referenz {row['player_b']}",
            min_value=1.01,
            max_value=50.0,
            value=float(row.get("odds_b") or 2.60),
            step=0.01,
            format="%.2f",
            key=f"closing_capture_b_{row['id']}",
        )
        if cols[2].button(
            "Referenz speichern",
            key=f"closing_capture_btn_{row['id']}",
            use_container_width=True,
        ):
            try:
                shadow.record_closing_prices(row["id"], closing_a, closing_b)
            except (KeyError, ValueError) as exc:
                st.error(str(exc))
            else:
                st.rerun()


def _render_match_card(row: dict) -> None:
    gates = json.loads(row["gates_json"] or "{}")
    markets = json.loads(row["markets_json"] or "{}")
    model_gates = {
        name: info for name, info in gates.items() if name != "Quote/Risiko-EV"
    }
    model_gates_ok = (
        all(g.get("passed") for g in model_gates.values())
        if model_gates
        else False
    )
    failed_gates = [
        name for name, info in model_gates.items() if not info.get("passed")
    ]

    header = f"{row['player_a']} vs {row['player_b']}"
    with st.container(border=True):
        st.markdown(f"**{header}**")
        likely_player = (
            row["player_a"] if row["p_cal"] >= 0.5 else row["player_b"]
        )
        likely_probability = max(row["p_cal"], 1.0 - row["p_cal"])
        st.caption(
            f"{row['tour']} · {row.get('tournament') or 'Turnier?'} · "
            f"{row.get('surface') or 'Belag?'} · Best of {row.get('best_of') or 3} · "
            f"{_format_start_local(row.get('scheduled_start_utc'))} · "
            f"{row.get('fixture_source') or 'Quelle unbekannt'}"
        )

        if not model_gates_ok:
            blockers = ", ".join(failed_gates) if failed_gates else "fehlende Prüfdaten"
            st.error(f"KEINE EMPFEHLUNG — blockiert durch: {blockers}.")
            st.caption(
                "Die Modellrechnung ist unvollständig. Deshalb werden weder ein "
                "Sieger-Prozentwert noch Mindestquoten oder eine Preisprüfung angezeigt."
            )
            with st.expander("Prüfdetails"):
                _render_gate_badges(gates)
                st.divider()
                _render_market_sheet(markets, int(row.get("best_of") or 3))
            return

        min_a = minimum_acceptable_odds(
            row["p_cal"] * 100.0,
            probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            minimum_expected_roi_percent=MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
        )
        p_b = 1.0 - row["p_cal"]
        min_b = minimum_acceptable_odds(
            p_b * 100.0,
            probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            minimum_expected_roi_percent=MINIMUM_RISK_ADJUSTED_ROI_PERCENT,
        )
        likely_minimum = min_a if row["p_cal"] >= 0.5 else min_b
        conservative_probability = max(
            0.0,
            likely_probability - WINNER_PROBABILITY_HAIRCUT,
        )
        minimum_text = (
            f"{likely_minimum:.2f}"
            if likely_minimum is not None
            else "nicht belastbar"
        )
        st.info(
            f"MODELLANALYSE: {likely_player} ist wahrscheinlicher. "
            "Noch keine Wettfreigabe ohne bestätigten Marktpreis."
        )
        metrics = st.columns(3)
        metrics[0].metric("Modell", f"{likely_probability:.1%}")
        metrics[1].metric("Konservativ", f"{conservative_probability:.1%}")
        metrics[2].metric("Mindestquote", minimum_text)
        st.caption(
            "Der Tennis-Datenfeed liefert derzeit keine belastbare automatische "
            "Mehrbuchmacherquote. Die Mindestquote ist deshalb nur die Schwelle "
            "für eine spätere Preisprüfung und ausdrücklich noch kein Tipp."
        )

        odds_a_key = f"odds_a_{row['id']}"
        odds_b_key = f"odds_b_{row['id']}"
        with st.expander("Eigene Buchmacherquote prüfen", expanded=False):
            price_cols = st.columns([1, 1, 1])
            odds_a_kwargs = {}
            if odds_a_key not in st.session_state:
                odds_a_kwargs["value"] = (
                    float(row["odds_a"]) if row.get("odds_a") else None
                )
            odds_a = price_cols[0].number_input(
                f"Quote {row['player_a']}",
                min_value=1.01,
                max_value=50.0,
                step=0.01,
                format="%.2f",
                placeholder="Quote",
                key=odds_a_key,
                **odds_a_kwargs,
            )
            odds_b_kwargs = {}
            if odds_b_key not in st.session_state:
                odds_b_kwargs["value"] = (
                    float(row["odds_b"]) if row.get("odds_b") else None
                )
            odds_b = price_cols[1].number_input(
                f"Quote {row['player_b']}",
                min_value=1.01,
                max_value=50.0,
                step=0.01,
                format="%.2f",
                placeholder="Quote",
                key=odds_b_key,
                **odds_b_kwargs,
            )
            prices_entered = odds_a is not None and odds_b is not None
            if price_cols[2].button(
                "Preis prüfen",
                key=f"check_{row['id']}",
                disabled=not prices_entered,
                use_container_width=True,
            ):
                result = _update_price_check(
                    row["id"],
                    odds_a,
                    odds_b,
                    row["p_cal"],
                    model_gates_ok,
                )
                st.session_state[f"price_result_{row['id']}"] = result

        result = st.session_state.get(f"price_result_{row['id']}")
        if row.get("verdict") and row.get("odds_a") and result is None:
            result = {
                "prices_ok": True,
                "side": row.get("recommended_side"),
                "verdict": row["verdict"],
            }
            restored_a = evaluate_market_price(
                row["p_cal"] * 100.0,
                row["odds_a"],
                probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            )
            restored_b = evaluate_market_price(
                (1.0 - row["p_cal"]) * 100.0,
                row["odds_b"],
                probability_haircut=WINNER_PROBABILITY_HAIRCUT * 100.0,
            )
            result.update(
                {
                    "edge_a": restored_a.risk_adjusted_edge / 100.0,
                    "edge_b": restored_b.risk_adjusted_edge / 100.0,
                    "risk_ev_a": restored_a.risk_adjusted_expected_roi / 100.0,
                    "risk_ev_b": restored_b.risk_adjusted_expected_roi / 100.0,
                }
            )
        if result:
            if result["verdict"] == "WETTE" and model_gates_ok:
                name = row["player_a"] if result["side"] == "A" else row["player_b"]
                selected_odds = odds_a if result["side"] == "A" else odds_b
                risk_ev = (
                    result["risk_ev_a"]
                    if result["side"] == "A"
                    else result["risk_ev_b"]
                )
                st.success(
                    f"PREIS BESTANDEN: Sieg {name} @ {selected_odds:.2f} | "
                    f"Risiko-EV {risk_ev:+.1%} nach "
                    f"{WINNER_PROBABILITY_HAIRCUT:+.0%} Modellabschlag."
                )
            else:
                reasons = []
                if not model_gates_ok:
                    reasons.append("Modell-Prüfung nicht bestanden (Details unten)")
                if not result.get("prices_ok"):
                    reasons.append("Quote unplausibel")
                elif max(
                    result.get("risk_ev_a", float("-inf")),
                    result.get("risk_ev_b", float("-inf")),
                ) < MIN_EXPECTED_ROI:
                    reasons.append(
                        "Preis zu niedrig: maximaler Risiko-EV "
                        f"{max(result.get('risk_ev_a', float('-inf')), result.get('risk_ev_b', float('-inf'))):+.1%} "
                        f"(erforderlich {MIN_EXPECTED_ROI:+.1%})"
                    )
                st.error(
                    "KEINE WETTE ZU DIESER QUOTE — die quotenfreie Prognose "
                    f"bleibt {likely_player} ({likely_probability:.1%}). "
                    + "; ".join(reasons)
                )

        _render_winner_closing_capture(row)

        with st.expander("Weitere Märkte und Prüfdetails"):
            _render_side_markets(row, markets, model_gates_ok)
            st.divider()
            _render_gate_badges(gates)
            st.divider()
            _render_market_sheet(markets, int(row.get("best_of") or 3))


def _render_settlement(open_rows: list[dict]) -> None:
    today = _zurich_today()
    due = [r for r in open_rows if r["match_date"] < today]
    if due:
        st.subheader(
            f"Shadow-Abrechnung ({len(due)}) – keine Wettvorschläge"
        )
        st.caption(
            "Diese Spiele sind beendet oder älter und erscheinen nur, damit das "
            "vorab gespeicherte Modell ehrlich abgerechnet wird. Hier nichts mehr wetten."
        )
        settlement_dates = sorted(
            {row["match_date"] for row in due},
            reverse=True,
        )
        selected_date = st.selectbox(
            "Abrechnungstag",
            settlement_dates,
            key="tennis_settlement_date",
        )
        visible_due = [
            row for row in due if row["match_date"] == selected_date
        ]
    else:
        selected_date = None
        visible_due = []
    for row in visible_due:
        label = (
            f"{row['player_a']} vs {row['player_b']} · "
            f"{row['match_date']}"
        )
        with st.expander(label):
            st.caption(row.get("tournament") or "Turnier unbekannt")
            cols = st.columns([2, 2, 1])
            winner_choice = cols[0].radio(
                "Wer hat gewonnen?",
                (row["player_a"], row["player_b"]),
                key=f"settle_winner_{row['id']}",
            )
            mode = cols[1].radio(
                "Wie endete das Match?",
                (
                    "Normal beendet",
                    "Aufgabe nach Satz 1 (Wette steht)",
                    "Aufgabe in Satz 1 (Wette void)",
                ),
                key=f"settle_mode_{row['id']}",
            )
            if row.get("recommended_side"):
                if row.get("closing_checked_utc"):
                    st.caption(
                        "Pre-Match-Referenz dokumentiert: "
                        f"{row['closing_odds_a']:.2f} / {row['closing_odds_b']:.2f}"
                    )
                else:
                    st.caption(
                        "Keine zeitgestempelte Pre-Match-Referenzquote vorhanden; "
                        "dieses Match zählt nicht zur CLV-Stichprobe."
                    )
            if cols[2].button("Abrechnen", key=f"settle_btn_{row['id']}"):
                if mode == "Normal beendet":
                    shadow.settle(
                        row["id"],
                        winner_choice,
                    )
                elif mode.startswith("Aufgabe nach"):
                    shadow.settle(
                        row["id"],
                        winner_choice,
                        ret=True,
                        ret_set=2,
                    )
                else:
                    shadow.settle(
                        row["id"],
                        winner_choice,
                        ret=True,
                        ret_set=0,
                    )
                st.rerun()

    # ---- side bets: settled from the SET SCORE (any retirement = void) ----
    open_sides = [
        b for b in shadow.open_side_bets()
        if b["match_date"] < today
        and (selected_date is None or b["match_date"] == selected_date)
    ]
    if open_sides:
        st.subheader("Shadow-Abrechnung Satz-Märkte")
        by_match: dict[int, list[dict]] = {}
        for b in open_sides:
            by_match.setdefault(b["prediction_id"], []).append(b)
        for pred_id, bets in by_match.items():
            first = bets[0]
            label = (
                f"{first['player_a']} vs {first['player_b']} · "
                f"{first['match_date']}"
            )
            with st.expander(label):
                st.caption(
                    "Offen: " + ", ".join(
                        f"{SIDE_MARKETS[b['market']]['label']} @ {b['odds']:.2f}" for b in bets
                    )
                )
                missing_clv = sum(
                    1 for bet in bets if not bet.get("closing_checked_utc")
                )
                if missing_clv:
                    st.caption(
                        f"{missing_clv} Satzmarkt-Tipp(s) ohne zeitgestempelte "
                        "Pre-Match-Referenz; nicht Teil der CLV-Stichprobe."
                    )
                cols = st.columns([3, 1])
                result = cols[0].radio(
                    f"Satzergebnis aus Sicht {first['player_a']}?",
                    ("2:0", "2:1", "1:2", "0:2", "Aufgabe (alle Satz-Märkte void)"),
                    key=f"side_result_{pred_id}",
                )
                if cols[1].button("Abrechnen", key=f"side_settle_btn_{pred_id}"):
                    code = "ret" if result.startswith("Aufgabe") else result
                    for bet in bets:
                        shadow.settle_side_bet(
                            bet["id"],
                            code,
                        )
                    st.rerun()


def render_tennis_finder(
    search_date: date | str | None = None,
    search_end_date: date | str | None = None,
) -> None:
    """Render actionable pre-match tennis picks for a bounded date window."""
    session_scope = scan_jobs.session_scope(st.session_state)
    job_key = scan_jobs.scoped_key("tennis", session_scope)
    selected_date = (
        search_date.isoformat() if isinstance(search_date, date) else search_date
    )
    if selected_date is not None:
        selected_date = str(selected_date)
    selected_end_date = (
        search_end_date.isoformat()
        if isinstance(search_end_date, date)
        else search_end_date
    )
    if selected_end_date is not None:
        selected_end_date = str(selected_end_date)
    elif selected_date is not None:
        selected_end_date = selected_date

    if selected_date is not None:
        try:
            start_value = date.fromisoformat(selected_date)
            end_value = date.fromisoformat(selected_end_date or selected_date)
        except ValueError as exc:
            raise ValueError("Ungültiger Tennis-Suchzeitraum") from exc
        if not 0 <= (end_value - start_value).days <= 14:
            raise ValueError("Tennis-Suchzeitraum darf höchstens 14 Tage umfassen")

    st.subheader("Tennis-Vorhersagen")
    if st.button(
        "Tennis-Vorhersagen aktualisieren",
        type="primary",
        use_container_width=True,
        key="run_tennis_scan",
    ):
        if scan_jobs.get_job(job_key)["state"] == "running":
            st.info("Der Tennis-Scan läuft bereits im Hintergrund.")
        else:
            scan_jobs.start_job(
                job_key,
                _run_tennis_scan_worker,
                args=(selected_date, selected_end_date),
            )

    job = scan_jobs.get_job(job_key)
    if job["state"] == "running":
        scan_progress_fragment(job_key, "Tennis-Scan")
    elif job["state"] == "done":
        st.session_state["tennis_scan_output"] = job.get("result") or ""
        scan_jobs.clear_job(job_key)
        st.rerun()
    elif job["state"] == "error":
        st.error(f"Tennis-Scan fehlgeschlagen: {job.get('error')}")
        scan_jobs.clear_job(job_key)
    if st.session_state.get("tennis_scan_output"):
        with st.expander("Letzter Scan-Verlauf"):
            st.text(st.session_state["tennis_scan_output"])

    today = _zurich_today()
    raw_rows = _load_predictions(
        date_from=selected_date or today,
        date_to=selected_end_date,
        unsettled_only=True,
    )
    rows, hidden_rows = _split_prematch_rows(raw_rows)
    if hidden_rows:
        st.warning(
            f"{len(hidden_rows)} Einträge ausgeblendet: angesetzte Startzeit "
            "erreicht oder Startzeit nicht verifiziert. Keine Pre-Match-Wette mehr."
        )
    if not rows:
        if raw_rows:
            st.info(
                "Aktuell gibt es keine verifizierte, noch nicht gestartete "
                "Tennis-Auswahl."
            )
        else:
            if selected_date is not None:
                target_date = date.fromisoformat(selected_date)
                target_end = date.fromisoformat(selected_end_date or selected_date)
                target_label = (
                    target_date.strftime("%d.%m.%Y")
                    if target_date == target_end
                    else (
                        f"{target_date:%d.%m.%Y} bis "
                        f"{target_end:%d.%m.%Y}"
                    )
                )
            else:
                target_label = _next_tennis_scan_date(
                    today_value=today
                ).strftime("%d.%m.%Y")
            st.info(f"Noch keine Tennis-Vorhersagen für {target_label}.")
    else:
        current_date = None
        for row in rows:
            if row["match_date"] != current_date:
                current_date = row["match_date"]
                st.markdown(f"**{current_date}**")
            _render_match_card(row)


def render_tennis_history() -> None:
    """Render tennis decisions and settlement away from the finder surface."""
    _render_shadow_summary()
    settled_rows = [
        row for row in _load_predictions() if int(row.get("settled") or 0)
    ]
    st.subheader("Verlauf")
    if settled_rows:
        history = []
        for row in reversed(settled_rows[-100:]):
            side = row.get("recommended_side")
            selection = (
                row.get("player_a")
                if side == "A"
                else row.get("player_b")
                if side == "B"
                else "Keine Wette"
            )
            odds = (
                row.get("odds_a")
                if side == "A"
                else row.get("odds_b")
                if side == "B"
                else None
            )
            history.append(
                {
                    "Datum": row.get("match_date"),
                    "Match": f"{row.get('player_a')} vs {row.get('player_b')}",
                    "Tipp": selection,
                    "Quote": odds,
                    "Sieger": row.get("actual_winner"),
                    "Bilanz": row.get("pnl"),
                }
            )
        st.dataframe(history, use_container_width=True, hide_index=True)
    else:
        st.caption("Noch keine abgerechneten Tennis-Tipps.")
    _render_settlement(_load_predictions(unsettled_only=True))


def render_tennis_page() -> None:
    """Backward-compatible complete tennis workspace."""
    _render_shadow_summary()
    render_tennis_finder()
    _render_settlement(_load_predictions(unsettled_only=True))


__all__ = [
    "render_tennis_finder",
    "render_tennis_history",
    "render_tennis_page",
]
