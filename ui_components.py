"""Shared UI building blocks: empty states, edge badges, milestone bar."""

from __future__ import annotations

import html
import math
import sqlite3
from pathlib import Path
from typing import Any, Optional

import streamlit as st

import scan_jobs

SHADOW_DB_PATH = Path(__file__).resolve().parent / "shadow_clv.db"

_JARGON_REPLACEMENTS = (
    ("das Walk-forward-Gate", "die Walk-forward-Prüfung"),
    ("das Walk-Forward-Gate", "die Walk-forward-Prüfung"),
    ("chronologisch validierte", "validierte"),
    ("chronologisch validiert", "validiert"),
    ("Modellgates", "Prüfkriterien"),
    ("Modellgate", "Prüfkriterium"),
    ("Walk-forward-Gate", "Walk-forward-Prüfung"),
    ("Walk-Forward-Gate", "Walk-forward-Prüfung"),
)


def plain_german(text: str) -> str:
    """Translate internal model jargon into words a bettor understands."""
    result = str(text)
    for old, new in _JARGON_REPLACEMENTS:
        result = result.replace(old, new)
    return result


def edge_class(edge_pp: Optional[float]) -> str:
    """Edge is diagnostic; only a negative break-even gap is colored red."""
    if edge_pp is None:
        return "bb-edge-none"
    return "bb-edge-none" if edge_pp >= 0.0 else "bb-edge-weak"


def edge_badge_html(edge_pp: Optional[float], *, label: str = "Edge") -> str:
    """Render the probability gap without presenting it as the wager gate."""
    css_class = edge_class(edge_pp)
    value = "k. A." if edge_pp is None else f"{edge_pp:.1f} pp"
    return (
        f'<span class="bb-edge-badge {css_class}">'
        f'<span class="bb-edge-label">{label}</span> {value}</span>'
    )


def ev_class(ev_percent: Optional[float]) -> str:
    if ev_percent is None:
        return "bb-edge-none"
    if ev_percent >= 5.0:
        return "bb-edge-strong"
    if ev_percent >= 3.0:
        return "bb-edge-ok"
    return "bb-edge-weak"


def ev_badge_html(ev_percent: Optional[float], *, label: str = "EV") -> str:
    css_class = ev_class(ev_percent)
    value = "k. A." if ev_percent is None else f"{ev_percent:.1f} %"
    return (
        f'<span class="bb-edge-badge {css_class}">'
        f'<span class="bb-edge-label">{label}</span> {value}</span>'
    )


def _latest_shadow_example() -> Optional[dict[str, Any]]:
    """Most recent logged shadow prediction, used as a real example ticket."""
    if not SHADOW_DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(SHADOW_DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT home_team, away_team, market_type, prediction, odds "
            "FROM predictions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    return dict(row) if row else None


def _example_ticket_html(
    illustrative_example: Optional[tuple[str, str]] = None,
) -> str:
    if illustrative_example is not None:
        line, pick = illustrative_example
        return (
            '<div class="bb-empty-example">'
            '<span class="bb-empty-example-tag">Beispiel (illustrativ)</span>'
            f'<div class="bb-empty-example-line">{html.escape(line)}</div>'
            f'<div class="bb-empty-example-pick">{html.escape(pick)}</div>'
            "</div>"
        )

    example = _latest_shadow_example()
    if example:
        odds = example.get("odds")
        odds_text = f" @ {odds:.2f}" if isinstance(odds, (int, float)) else ""
        home_team = html.escape(str(example["home_team"]))
        away_team = html.escape(str(example["away_team"]))
        prediction = html.escape(str(example["prediction"]))
        market_type = html.escape(str(example["market_type"]))
        return (
            '<div class="bb-empty-example">'
            '<span class="bb-empty-example-tag">Echtes Shadow-Beispiel</span>'
            f'<div class="bb-empty-example-line">{home_team} vs '
            f'{away_team}</div>'
            f'<div class="bb-empty-example-pick">{prediction} '
            f'({market_type}){odds_text}</div>'
            "</div>"
        )
    return (
        '<div class="bb-empty-example">'
        '<span class="bb-empty-example-tag">Beispiel (illustrativ)</span>'
        '<div class="bb-empty-example-line">Team A vs Team B</div>'
        '<div class="bb-empty-example-pick">Beide treffen: Ja @ 1,95 — '
        "Modell 62 %, konservativ 52 %, Mindestquote 1,99</div>"
        "</div>"
    )


def render_empty_state(
    title: str,
    steps: list[str],
    *,
    duration_hint: str,
    illustrative_example: Optional[tuple[str, str]] = None,
) -> None:
    """Informative empty state: what happens on click, how long it takes,
    and one example ticket (real shadow data when available)."""
    steps_html = "".join(
        f'<li><span class="bb-empty-step-num">{index}</span> {step}</li>'
        for index, step in enumerate(steps, start=1)
    )
    st.markdown(
        '<div class="bb-empty">'
        f'<div class="bb-empty-title">{title}</div>'
        f'<ol class="bb-empty-steps">{steps_html}</ol>'
        f'<div class="bb-empty-duration">{duration_hint}</div>'
        f"{_example_ticket_html(illustrative_example)}"
        "</div>",
        unsafe_allow_html=True,
    )


def milestone_bar_html(
    current: float,
    target: float,
    start: float,
    milestones: tuple[float, ...] = (250.0, 500.0, 1000.0, 2500.0, 5000.0, 15000.0),
) -> str:
    """Log-scaled milestone progress bar from start to target balance.

    Log scale because the challenge grows multiplicatively (roll-over);
    a linear bar would park 1.000 € at 6 % width and look broken.
    """
    start = max(start, 1.0)
    target = max(target, start + 1.0)
    current = max(0.0, current)

    def pos(value: float) -> float:
        value = min(max(value, start), target)
        low = math.log(start)
        high = math.log(target)
        if high <= low:
            return 100.0
        return (math.log(value) - low) / (high - low) * 100.0

    fill = pos(max(current, start)) if current > 0 else 0.0
    align = "left" if fill < 8 else ("right" if fill > 92 else "center")
    markers = []
    for mark in milestones:
        if not start < mark <= target:
            continue
        mark_pos = pos(mark)
        mark_align = "right" if mark_pos > 92 else "center"
        passed = current >= mark
        cls = "passed" if passed else "open"
        label = f"{mark:,.0f}".replace(",", ".") + " €"
        markers.append(
            f'<div class="bb-mile-marker {cls} bb-align-{mark_align}" '
            f'style="left:{mark_pos:.2f}%">'
            f'<div class="bb-mile-tick"></div>'
            f'<div class="bb-mile-label">{label}</div>'
            "</div>"
        )
    current_label = f"{current:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    target_label = f"{target:,.0f}".replace(",", ".")
    return (
        '<div class="bb-mile-wrap" role="img" '
        f'aria-label="Fortschritt {current_label} Euro von {target_label} Euro Ziel">'
        + '<div class="bb-mile-track">'
        + f'<div class="bb-mile-fill" style="width:{fill:.2f}%"></div>'
        + "".join(markers)
        + f'<div class="bb-mile-current bb-align-{align}" style="left:{fill:.2f}%">'
        + f'<div class="bb-mile-dot"></div>'
        + f'<div class="bb-mile-current-label">{current_label} €</div>'
        + "</div></div></div>"
    )


@st.fragment(run_every=2)
def scan_progress_fragment(job_key: str, label: str) -> None:
    """Pollt einen Hintergrund-Scan und zeigt Fortschritt, bis er fertig ist.

    Läuft als eigenes Fragment alle 2 s: Der Seitenwechsel des Nutzers bricht
    den Job nicht ab (er lebt in scan_jobs), und bei Abschluss wird genau ein
    voller Rerun ausgelöst, damit die Seite das Ergebnis einsammelt.
    """
    job = scan_jobs.get_job(job_key)
    state = job.get("state")
    if state == "running":
        progress = float(job.get("progress") or 0.0)
        st.progress(min(max(progress, 0.0), 1.0))
        detail = job.get("progress_text") or "Scan läuft …"
        st.caption(
            f"🔍 {label}: {detail} — läuft im Hintergrund, "
            "Seitenwechsel unterbricht den Scan nicht."
        )
        return
    if state in ("done", "error"):
        # Ergebnis liegt bereit → Haupt-Render einsammeln lassen.
        st.rerun()
