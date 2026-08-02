"""Tennis tab: daily model predictions, manual N1Bet price check, settlement.

UX discipline (same as football): one clear verdict per match —
"WETTE" or "KEINE WETTE" — with the exact blocking reasons in plain
German inside an expander.  No jargon, no duplicated verdicts.

Data flow:
- predictions arrive via scripts/tennis_daily.py (scheduled every
  morning) and live in tennis/data/tennis_shadow.db
- the user types the two N1Bet prices; the edge gate is evaluated
  from the STORED calibrated probability (no model reload needed)
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
from datetime import date, datetime
from pathlib import Path

import streamlit as st

import scan_jobs
from ui_components import scan_progress_fragment
from tennis import shadow
from tennis.predict import MIN_EDGE, SIDE_MARKET_MIN_EDGE
from tennis.shadow import SIDE_MARKETS

DB_PATH = shadow.DB_PATH
DAILY_SCRIPT = Path(__file__).resolve().parent / "scripts" / "tennis_daily.py"


# --------------------------------------------------------------------- helpers


def _load_predictions(date_from: str | None = None) -> list[dict]:
    if not DB_PATH.exists():
        return []
    query = "SELECT * FROM predictions"
    params: tuple = ()
    if date_from:
        query += " WHERE match_date >= ?"
        params = (date_from,)
    query += " ORDER BY match_date, tour, tournament, id"
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def _update_price_check(row_id: int, odds_a: float, odds_b: float, p_cal: float) -> dict:
    """Evaluate the edge gate from the stored probability and persist it."""
    prices_ok = odds_a > 1.0 and odds_b > 1.0
    edge_a = p_cal - 1.0 / odds_a if prices_ok else 0.0
    edge_b = (1.0 - p_cal) - 1.0 / odds_b if prices_ok else 0.0
    side = edge = 0.0
    verdict = "KEINE WETTE"
    if prices_ok:
        if edge_a >= edge_b and edge_a >= MIN_EDGE:
            side, edge = "A", edge_a
        elif edge_b > edge_a and edge_b >= MIN_EDGE:
            side, edge = "B", edge_b
        if side:
            verdict = "WETTE"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE predictions SET odds_a=?, odds_b=?, recommended_side=?, "
            "recommended_edge=?, verdict=? WHERE id=?",
            (odds_a, odds_b, side or None, edge or None, verdict, row_id),
        )
    return {
        "prices_ok": prices_ok,
        "edge_a": edge_a,
        "edge_b": edge_b,
        "side": side,
        "verdict": verdict,
    }


def _run_daily_scan() -> str:
    result = subprocess.run(
        [sys.executable, str(DAILY_SCRIPT)],
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


def _run_tennis_scan_worker(progress_cb=None) -> str:
    """Hintergrund-Worker für den Tennis-Tages-Scan (kein st.* im Thread)."""
    if progress_cb:
        progress_cb(0.1, "Tennis-Modell wird aktualisiert …")
    output = _run_daily_scan()
    if progress_cb:
        progress_cb(1.0, "Fertig")
    return output


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
        "Shadow-Phase: Das Modell zeigt, was es spielen würde. Erst wenn die "
        "Bilanz über Wochen gegen die N1Bet-Schlussquoten stimmt (CLV), wird "
        "über Echtgeld gesprochen."
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


def _render_gate_badges(gates: dict) -> None:
    for name, info in gates.items():
        icon = "✅" if info.get("passed") else "⛔"
        st.markdown(f"{icon} **{name}** — {info.get('detail', '')}")


def _render_market_sheet(markets: dict, best_of: int) -> None:
    if not markets:
        st.caption("Keine Markt-Daten (Aufschlag-Daten fehlen).")
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
    """Set markets with fair prices + manual N1Bet check + shadow tracking."""
    if int(row.get("best_of") or 3) != 3:
        return  # calibration was measured on Bo3; Bo5 stays out for now
    available = {
        code: markets[key]
        for code, key in _SIDE_MARKET_KEYS.items()
        if markets.get(key) is not None
    }
    if not available:
        return

    st.markdown("**Satz-Märkte** (kalibriert, Schwelle "
                f"{SIDE_MARKET_MIN_EDGE:+.0%} Edge — härter als Sieger-Markt)")
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
            cols[2].markdown(f"Edge {b['edge']:+.1%}")
            cols[3].caption("getrackt ✓")
            continue
        odds = cols[1].number_input(
            "N1Bet", min_value=1.01, max_value=50.0, value=round(fair, 2),
            step=0.01, format="%.2f", key=f"side_odds_{code}_{row['id']}",
            label_visibility="collapsed",
        )
        edge = p - 1.0 / odds
        ok = edge >= SIDE_MARKET_MIN_EDGE and model_gates_ok
        cols[2].markdown(f"**{edge:+.1%}**" if ok else f"{edge:+.1%}")
        if cols[3].button("Track", key=f"side_track_{code}_{row['id']}",
                          disabled=not ok, use_container_width=True):
            shadow.store_side_bet(row["id"], code, p, odds, edge)
            st.rerun()


def _render_match_card(row: dict) -> None:
    gates = json.loads(row["gates_json"] or "{}")
    markets = json.loads(row["markets_json"] or "{}")
    model_gates_ok = all(g.get("passed") for g in gates.values()) if gates else False

    header = (
        f"{row['player_a']} vs {row['player_b']} — "
        f"{row['p_cal']:.0%} / {1 - row['p_cal']:.0%}"
    )
    with st.container(border=True):
        st.markdown(f"**{header}**")
        st.caption(
            f"{row['tour']} · {row.get('tournament') or 'Turnier?'} · "
            f"{row.get('surface') or 'Belag?'} · Best of {row.get('best_of') or 3} · "
            f"{row['match_date']}"
        )

        price_cols = st.columns([1, 1, 1])
        odds_a = price_cols[0].number_input(
            f"N1Bet {row['player_a']}",
            min_value=1.01,
            max_value=50.0,
            value=float(row["odds_a"]) if row.get("odds_a") else 1.50,
            step=0.01,
            format="%.2f",
            key=f"odds_a_{row['id']}",
        )
        odds_b = price_cols[1].number_input(
            f"N1Bet {row['player_b']}",
            min_value=1.01,
            max_value=50.0,
            value=float(row["odds_b"]) if row.get("odds_b") else 2.60,
            step=0.01,
            format="%.2f",
            key=f"odds_b_{row['id']}",
        )
        if price_cols[2].button("Preis prüfen", key=f"check_{row['id']}", use_container_width=True):
            result = _update_price_check(row["id"], odds_a, odds_b, row["p_cal"])
            st.session_state[f"price_result_{row['id']}"] = result

        result = st.session_state.get(f"price_result_{row['id']}")
        if row.get("verdict") and row.get("odds_a") and result is None:
            result = {
                "prices_ok": True,
                "edge_a": row["p_cal"] - 1.0 / row["odds_a"],
                "edge_b": (1 - row["p_cal"]) - 1.0 / row["odds_b"],
                "side": row.get("recommended_side"),
                "verdict": row["verdict"],
            }
        if result:
            if result["verdict"] == "WETTE" and model_gates_ok:
                name = row["player_a"] if result["side"] == "A" else row["player_b"]
                st.success(
                    f"WETTE: {name} — Edge {max(result['edge_a'], result['edge_b']):+.1%} "
                    f"(Schwelle {MIN_EDGE:+.0%}). Shadow-Protokoll, noch kein Echtgeld."
                )
            else:
                reasons = []
                if not model_gates_ok:
                    reasons.append("Modell-Prüfung nicht bestanden (Details unten)")
                if not result.get("prices_ok"):
                    reasons.append("Quote unplausibel")
                elif result.get("verdict") != "WETTE":
                    reasons.append(
                        f"Edge zu klein: {max(result['edge_a'], result['edge_b']):+.1%} "
                        f"(Schwelle {MIN_EDGE:+.0%})"
                    )
                st.error("KEINE WETTE — " + "; ".join(reasons))

        _render_side_markets(row, markets, model_gates_ok)

        with st.expander("Prüfungen & alle Märkte"):
            _render_gate_badges(gates)
            st.divider()
            _render_market_sheet(markets, int(row.get("best_of") or 3))


def _render_settlement(open_rows: list[dict]) -> None:
    today = date.today().isoformat()
    due = [r for r in open_rows if r["match_date"] < today]
    if due:
        st.subheader("Abrechnung Sieger-Markt (gestern und älter)")
    for row in due:
        with st.container(border=True):
            st.markdown(
                f"**{row['player_a']} vs {row['player_b']}** · {row['match_date']} · "
                f"{row.get('tournament') or ''}"
            )
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
            if cols[2].button("Abrechnen", key=f"settle_btn_{row['id']}"):
                if mode == "Normal beendet":
                    shadow.settle(row["id"], winner_choice)
                elif mode.startswith("Aufgabe nach"):
                    shadow.settle(row["id"], winner_choice, ret=True, ret_set=2)
                else:
                    shadow.settle(row["id"], winner_choice, ret=True, ret_set=0)
                st.rerun()

    # ---- side bets: settled from the SET SCORE (any retirement = void) ----
    open_sides = [b for b in shadow.open_side_bets() if b["match_date"] < today]
    if open_sides:
        st.subheader("Abrechnung Satz-Märkte (gestern und älter)")
        by_match: dict[int, list[dict]] = {}
        for b in open_sides:
            by_match.setdefault(b["prediction_id"], []).append(b)
        for pred_id, bets in by_match.items():
            first = bets[0]
            with st.container(border=True):
                st.markdown(
                    f"**{first['player_a']} vs {first['player_b']}** · {first['match_date']}"
                )
                st.caption(
                    "Offen: " + ", ".join(
                        f"{SIDE_MARKETS[b['market']]['label']} @ {b['odds']:.2f}" for b in bets
                    )
                )
                cols = st.columns([3, 1])
                result = cols[0].radio(
                    f"Satzergebnis aus Sicht {first['player_a']}?",
                    ("2:0", "2:1", "1:2", "0:2", "Aufgabe (alle Satz-Märkte void)"),
                    key=f"side_result_{pred_id}",
                )
                if cols[1].button("Abrechnen", key=f"side_settle_btn_{pred_id}"):
                    code = "ret" if result.startswith("Aufgabe") else result
                    for b in bets:
                        shadow.settle_side_bet(b["id"], code)
                    st.rerun()


def render_tennis_page() -> None:
    session_scope = scan_jobs.session_scope(st.session_state)
    job_key = scan_jobs.scoped_key("tennis", session_scope)
    _render_shadow_summary()

    st.subheader("Tägliche Vorhersagen")
    if st.button(
        "Tennis-Vorhersagen aktualisieren",
        type="primary",
        use_container_width=True,
        key="run_tennis_scan",
    ):
        if scan_jobs.get_job(job_key)["state"] == "running":
            st.info("Der Tennis-Scan läuft bereits im Hintergrund.")
        else:
            scan_jobs.start_job(job_key, _run_tennis_scan_worker)

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

    rows = _load_predictions(date_from=date.today().isoformat())
    if not rows:
        st.info(
            "Noch keine Tennis-Vorhersagen gespeichert. Ein Klick auf "
            "»Tennis-Vorhersagen aktualisieren« holt die Spiele von morgen "
            "ins Shadow-Protokoll."
        )
    else:
        current_date = None
        for row in rows:
            if row["match_date"] != current_date:
                current_date = row["match_date"]
                st.markdown(f"**{current_date}**")
            _render_match_card(row)

    _render_settlement(_load_predictions())
