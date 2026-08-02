"""Regenerate the red-card pattern report from redcard_history.db.

Reads the harvested dismissal history and produces:
- phase buckets (0-20 / 21-40 / 41+ minutes after the card)
- fatigue-cliff rates per exposure-minute (the honest per-minute view)
- score-state splits (red team leading / level / trailing)
- markdown report + PNG chart in the workspace root

Model horizon: regulation time only (up to 93'). Goals in extra time or
shootouts never count, and dismissals that happened in extra time are
excluded — the impact model ends at 93'.

Safe to run at any history size; every figure carries its sample count.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "redcard_history.db"
REPORT_DIR = Path(os.environ.get("BETBOY_REPORT_DIR", ROOT / "runtime_reports"))
OUT_MD = REPORT_DIR / "rot_karten_musteranalyse.md"
OUT_PNG = REPORT_DIR / "rot_karten_musteranalyse.png"

MATCH_MINUTES = 93
PHASES = ((0, 20, "0-20"), (21, 40, "21-40"), (41, 200, "41+"))
FINE_PHASES = (
    (0, 10, "0-10"),
    (11, 20, "11-20"),
    (21, 30, "21-30"),
    (31, 45, "31-45"),
    (46, 200, "46+"),
)
LATE_SHELL_MINUTE = 75


def _goal_in_model_horizon(abs_minute: int, status) -> bool:
    """True, wenn das Tor im Modell-Horizont (reguläre Spielzeit) fiel.

    Halte diese Regel synchron mit redcard_signal_log.py: 93 deckt
    Nachspielzeit im alten API-Stil ab; 91-93 zählt nur bei Endstatus FT,
    alles darüber ist Verlängerung oder Elfmeterschießen.
    """
    if abs_minute > MATCH_MINUTES:
        return False
    if abs_minute > 90 and status != "FT":
        return False
    return True


def _in_scope(case) -> bool:
    """Nur Fälle im Modell-Horizont: keine komplexen Fälle (2+ Platzverweise),
    keine Platzverweise, die erst in der Verlängerung fielen."""
    return not case["complex"] and case["red_minute"] <= MATCH_MINUTES


def load_cases(conn: sqlite3.Connection):
    rows = conn.execute(
        """SELECT d.match_date, d.league_name, d.home_name, d.away_name,
                  d.final_home, d.final_away, d.red_minute, d.red_side,
                  d.red_team_name, d.score_at_red_home, d.score_at_red_away,
                  d.red_team_goal_diff, d.complex_state, d.goals_after_json,
                  f.status_short
           FROM dismissals d
           LEFT JOIN fixtures f ON f.fixture_id = d.fixture_id"""
    ).fetchall()
    cases = []
    for row in rows:
        status = row[14]
        red_minute = row[6]
        goals_after = []
        for goal in json.loads(row[13]):
            since = goal.get("since_card")
            if not isinstance(since, int):
                continue
            if _goal_in_model_horizon(red_minute + since, status):
                goals_after.append(goal)
        cases.append(
            {
                "date": row[0],
                "league": row[1],
                "match": f"{row[2]} vs {row[3]}",
                "final": f"{row[4]}:{row[5]}",
                "red_minute": red_minute,
                "red_side": row[7],
                "red_team": row[8],
                "score_at_red": f"{row[9]}:{row[10]}",
                "goal_diff": row[11],
                "complex": row[12],
                "goals_after": goals_after,
                "status": status,
            }
        )
    return cases


def _phase_bucket_stats(cases, phases):
    """Goals and exposure minutes per phase bucket (generic over bucket grid)."""
    stats = {
        label: {"goals_11": 0, "goals_10": 0, "exposure": 0.0}
        for _, _, label in phases
    }
    for case in cases:
        if not _in_scope(case):
            continue
        window = max(0, MATCH_MINUTES - case["red_minute"])
        for lo, hi, label in phases:
            stats[label]["exposure"] += max(0, min(hi, window) - lo)
        for goal in case["goals_after"]:
            since = goal["since_card"]
            for lo, hi, label in phases:
                if lo <= since <= hi:
                    key = "goals_11" if goal["by_11_team"] else "goals_10"
                    stats[label][key] += 1
                    break
    return stats


def phase_stats(cases):
    """Goals and exposure minutes per phase.

    Exposure = minutes a match actually spent in that phase at 11-v-10.
    A red at minute 80 contributes 13 minutes to phase 0-20, none to the
    later phases. Per-minute rates are the only honest comparison.
    """
    return _phase_bucket_stats(cases, PHASES)


def fine_phase_stats(cases):
    """Finer fatigue-ramp grid for model calibration."""
    return _phase_bucket_stats(cases, FINE_PHASES)


def exact_score_stats(cases):
    """Rates split by the exact goal difference of the red team at the card."""
    stats = {}
    for case in cases:
        if not _in_scope(case):
            continue
        diff = case["goal_diff"]
        if diff >= 2:
            state = "+2 oder mehr"
        elif diff == 1:
            state = "+1"
        elif diff == 0:
            state = "0"
        elif diff == -1:
            state = "-1"
        else:
            state = "-2 oder mehr"
        entry = stats.setdefault(
            state, {"matches": 0, "goals_11": 0, "goals_10": 0, "exposure": 0.0}
        )
        entry["matches"] += 1
        entry["exposure"] += max(0, MATCH_MINUTES - case["red_minute"])
        for goal in case["goals_after"]:
            key = "goals_11" if goal["by_11_team"] else "goals_10"
            entry[key] += 1
    return stats


def late_shell_stats(cases):
    """Leading red teams: does the 11-man rate drop after minute 75?

    Splits exposure by absolute match minute (<75 vs >=75) for cases where
    the red team led at the card. Absolute minute of a goal =
    red_minute + since_card.
    """
    stats = {
        "bis 75": {"goals_11": 0, "goals_10": 0, "exposure": 0.0},
        "ab 75": {"goals_11": 0, "goals_10": 0, "exposure": 0.0},
    }
    matches = 0
    for case in cases:
        if not _in_scope(case) or case["goal_diff"] <= 0:
            continue
        matches += 1
        red_minute = case["red_minute"]
        early = max(0, min(LATE_SHELL_MINUTE, MATCH_MINUTES) - red_minute)
        late = max(0, MATCH_MINUTES - max(red_minute, LATE_SHELL_MINUTE))
        stats["bis 75"]["exposure"] += early
        stats["ab 75"]["exposure"] += late
        for goal in case["goals_after"]:
            absolute = red_minute + goal["since_card"]
            label = "ab 75" if absolute >= LATE_SHELL_MINUTE else "bis 75"
            key = "goals_11" if goal["by_11_team"] else "goals_10"
            stats[label][key] += 1
    return stats, matches


def score_state_stats(cases):
    stats = {}
    for case in cases:
        if not _in_scope(case):
            continue
        diff = case["goal_diff"]
        state = "fuehrend" if diff > 0 else ("rueckstand" if diff < 0 else "ausgeglichen")
        entry = stats.setdefault(
            state, {"matches": 0, "goals_11": 0, "goals_10": 0, "exposure": 0.0}
        )
        entry["matches"] += 1
        entry["exposure"] += max(0, MATCH_MINUTES - case["red_minute"])
        for goal in case["goals_after"]:
            key = "goals_11" if goal["by_11_team"] else "goals_10"
            entry[key] += 1
    return stats


def per_100(goals: int, exposure: float) -> float:
    return goals / exposure * 100 if exposure > 0 else 0.0


def main():
    if not DB_PATH.exists():
        print("Keine Historie gefunden — Harvester zuerst laufen lassen.")
        return
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cases = load_cases(conn)
    scanned = conn.execute(
        "SELECT COUNT(*) FROM fixtures WHERE events_fetched = 1"
    ).fetchone()[0]
    backlog = conn.execute(
        "SELECT COUNT(*) FROM fixtures WHERE events_fetched = 0"
    ).fetchone()[0]

    clean = [c for c in cases if not c["complex"]]
    phases = phase_stats(cases)
    fine_phases = fine_phase_stats(cases)
    states = score_state_stats(cases)
    exact_states = exact_score_stats(cases)
    shell, shell_matches = late_shell_stats(cases)
    dates = sorted(c["date"] for c in cases)

    lines = [
        "# Rotkarten-Musteranalyse (Historie)",
        "",
        f"**{len(cases)} Platzverweise** aus **{scanned} gescannten Spielen** "
        f"({dates[0] if dates else '?'} bis {dates[-1] if dates else '?'}) | "
        f"Backlog: {backlog} Spiele",
        "",
        "## Phase nach Platzverweis (pro 100 Minuten 11-gegen-10)",
        "",
        "| Phase | Tore 11-Mann | Tore 10-Mann | Exposition (Min) | Rate 11M/100min | Rate 10M/100min |",
        "|---|---|---|---|---|---|",
    ]
    for _, _, label in PHASES:
        s = phases[label]
        lines.append(
            f"| {label} | {s['goals_11']} | {s['goals_10']} | "
            f"{s['exposure']:.0f} | {per_100(s['goals_11'], s['exposure']):.2f} | "
            f"{per_100(s['goals_10'], s['exposure']):.2f} |"
        )
    lines += [
        "",
        "## Spielstand des 10-Mann-Teams bei Rot",
        "",
        "| Stand | Spiele | Tore 11M | Tore 10M | Rate 11M/100min | Rate 10M/100min |",
        "|---|---|---|---|---|---|",
    ]
    for state in ("fuehrend", "ausgeglichen", "rueckstand"):
        s = states.get(state)
        if not s:
            continue
        lines.append(
            f"| {state} | {s['matches']} | {s['goals_11']} | {s['goals_10']} | "
            f"{per_100(s['goals_11'], s['exposure']):.2f} | "
            f"{per_100(s['goals_10'], s['exposure']):.2f} |"
        )
    lines += [
        "",
        "## Feine Phase nach Platzverweis (Rampenform, pro 100 Min 11-gegen-10)",
        "",
        "| Phase | Tore 11M | Tore 10M | Exposition (Min) | Rate 11M/100min | Rate 10M/100min |",
        "|---|---|---|---|---|---|",
    ]
    for _, _, label in FINE_PHASES:
        s = fine_phases[label]
        lines.append(
            f"| {label} | {s['goals_11']} | {s['goals_10']} | "
            f"{s['exposure']:.0f} | {per_100(s['goals_11'], s['exposure']):.2f} | "
            f"{per_100(s['goals_10'], s['exposure']):.2f} |"
        )
    lines += [
        "",
        "## Exakter Spielstand bei Rot (aus Sicht des 10-Mann-Teams)",
        "",
        "| Diff | Spiele | Tore 11M | Tore 10M | Rate 11M/100min | Rate 10M/100min |",
        "|---|---|---|---|---|---|",
    ]
    for state in ("+2 oder mehr", "+1", "0", "-1", "-2 oder mehr"):
        s = exact_states.get(state)
        if not s:
            continue
        lines.append(
            f"| {state} | {s['matches']} | {s['goals_11']} | {s['goals_10']} | "
            f"{per_100(s['goals_11'], s['exposure']):.2f} | "
            f"{per_100(s['goals_10'], s['exposure']):.2f} |"
        )
    lines += [
        "",
        f"## Late-Shell-Test: 10-Mann-Team führt ({shell_matches} Spiele)",
        "",
        "| Absolutminute | Tore 11M | Tore 10M | Exposition (Min) | Rate 11M/100min | Rate 10M/100min |",
        "|---|---|---|---|---|---|",
    ]
    for label in ("bis 75", "ab 75"):
        s = shell[label]
        lines.append(
            f"| {label} | {s['goals_11']} | {s['goals_10']} | "
            f"{s['exposure']:.0f} | {per_100(s['goals_11'], s['exposure']):.2f} | "
            f"{per_100(s['goals_10'], s['exposure']):.2f} |"
        )
    lines += [
        "",
        f"_Komplexe Fälle (2+ Platzverweise) ausgenommen: {len(cases) - len(clean)}_",
        "",
        f"_Modell-Horizont reguläre Spielzeit (bis {MATCH_MINUTES}'): "
        f"Platzverweise in der Verlängerung ausgenommen: "
        f"{sum(1 for c in cases if c['red_minute'] > MATCH_MINUTES)} · "
        "Tore in Verlängerung/Elfmeterschießen zählen nicht "
        "(Regel synchron zur Shadow-Abrechnung in redcard_signal_log.py)._",
        "",
        "_Chart: rot_karten_musteranalyse.png_",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {OUT_MD}")

    # Chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        def draw_panel(ax, labels, r11, r10, title):
            x = np.arange(len(labels))
            ax.bar(x - 0.2, r11, 0.38, color="#1a66cc", label="11-Mann trifft")
            ax.bar(x + 0.2, r10, 0.38, color="#e08a00", label="10-Mann trifft")
            for xi, v in zip(x - 0.2, r11):
                ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=8,
                        fontweight="bold")
            for xi, v in zip(x + 0.2, r10):
                ax.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=8,
                        fontweight="bold")
            ax.set_xticks(x, labels)
            ax.set_ylabel("Tore pro 100 Min. 11v10")
            ax.set_title(title, fontweight="bold")
            ax.legend()
            ax.spines[["top", "right"]].set_visible(False)

        fig, axes = plt.subplots(1, 3, figsize=(19, 5.5))
        fig.subplots_adjust(top=0.80, wspace=0.25)

        fine_labels = [label for _, _, label in FINE_PHASES]
        draw_panel(
            axes[0],
            fine_labels,
            [per_100(fine_phases[l]["goals_11"], fine_phases[l]["exposure"]) for l in fine_labels],
            [per_100(fine_phases[l]["goals_10"], fine_phases[l]["exposure"]) for l in fine_labels],
            "Feine Phase seit Rot (Rampenform)",
        )

        exact_order = [s for s in ("+2 oder mehr", "+1", "0", "-1", "-2 oder mehr") if s in exact_states]
        draw_panel(
            axes[1],
            exact_order,
            [per_100(exact_states[s]["goals_11"], exact_states[s]["exposure"]) for s in exact_order],
            [per_100(exact_states[s]["goals_10"], exact_states[s]["exposure"]) for s in exact_order],
            "Exakter Spielstand bei Rot (10-Mann-Sicht)",
        )

        shell_labels = ["bis 75", "ab 75"]
        draw_panel(
            axes[2],
            shell_labels,
            [per_100(shell[l]["goals_11"], shell[l]["exposure"]) for l in shell_labels],
            [per_100(shell[l]["goals_10"], shell[l]["exposure"]) for l in shell_labels],
            f"Late-Shell: 10-Mann führt ({shell_matches} Spiele)",
        )

        fig.suptitle(
            f"Rotkarten-Historie: {len(cases)} Platzverweise aus {scanned} Spielen "
            f"({dates[0] if dates else '?'} bis {dates[-1] if dates else '?'})",
            fontsize=13, fontweight="bold",
        )
        fig.savefig(OUT_PNG, bbox_inches="tight", dpi=150)
        print(f"Chart: {OUT_PNG}")
    except Exception as exc:
        print(f"Chart fehlgeschlagen (Report liegt trotzdem vor): {exc}")


if __name__ == "__main__":
    main()
