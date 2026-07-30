"""Regenerate the red-card pattern report from redcard_history.db.

Reads the harvested dismissal history and produces:
- phase buckets (0-20 / 21-40 / 41+ minutes after the card)
- fatigue-cliff rates per exposure-minute (the honest per-minute view)
- score-state splits (red team leading / level / trailing)
- markdown report + PNG chart in the workspace root

Safe to run at any history size; every figure carries its sample count.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DB_PATH = Path(__file__).parent / "redcard_history.db"
OUT_MD = Path(r"C:\Users\miros\Desktop\BetBoy\rot_karten_musteranalyse.md")
OUT_PNG = Path(r"C:\Users\miros\Desktop\BetBoy\rot_karten_musteranalyse.png")

MATCH_MINUTES = 93
PHASES = ((0, 20, "0-20"), (21, 40, "21-40"), (41, 200, "41+"))


def load_cases(conn: sqlite3.Connection):
    rows = conn.execute(
        """SELECT match_date, league_name, home_name, away_name,
                  final_home, final_away, red_minute, red_side, red_team_name,
                  score_at_red_home, score_at_red_away, red_team_goal_diff,
                  complex_state, goals_after_json
           FROM dismissals"""
    ).fetchall()
    cases = []
    for row in rows:
        cases.append(
            {
                "date": row[0],
                "league": row[1],
                "match": f"{row[2]} vs {row[3]}",
                "final": f"{row[4]}:{row[5]}",
                "red_minute": row[6],
                "red_side": row[7],
                "red_team": row[8],
                "score_at_red": f"{row[9]}:{row[10]}",
                "goal_diff": row[11],
                "complex": row[12],
                "goals_after": json.loads(row[13]),
            }
        )
    return cases


def phase_stats(cases):
    """Goals and exposure minutes per phase.

    Exposure = minutes a match actually spent in that phase at 11-v-10.
    A red at minute 80 contributes 13 minutes to phase 0-20, none to the
    later phases. Per-minute rates are the only honest comparison.
    """
    stats = {
        label: {"goals_11": 0, "goals_10": 0, "exposure": 0.0}
        for _, _, label in PHASES
    }
    for case in cases:
        if case["complex"]:
            continue
        window = max(0, MATCH_MINUTES - case["red_minute"])
        for lo, hi, label in PHASES:
            overlap = max(0, min(hi, window) - lo)
            if lo == 0:
                overlap = max(0, min(hi, window) - lo)
            stats[label]["exposure"] += overlap
        for goal in case["goals_after"]:
            since = goal["since_card"]
            for lo, hi, label in PHASES:
                if lo <= since <= hi:
                    key = "goals_11" if goal["by_11_team"] else "goals_10"
                    stats[label][key] += 1
                    break
    return stats


def score_state_stats(cases):
    stats = {}
    for case in cases:
        if case["complex"]:
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
    states = score_state_stats(cases)
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
        f"_Komplexe Fälle (2+ Platzverweise) ausgenommen: {len(cases) - len(clean)}_",
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

        fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
        fig.subplots_adjust(top=0.80, wspace=0.28)

        labels = [label for _, _, label in PHASES]
        rates_11 = [per_100(phases[l]["goals_11"], phases[l]["exposure"]) for l in labels]
        rates_10 = [per_100(phases[l]["goals_10"], phases[l]["exposure"]) for l in labels]
        x = np.arange(len(labels))
        axes[0].bar(x - 0.2, rates_11, 0.38, color="#1a66cc", label="11-Mann trifft")
        axes[0].bar(x + 0.2, rates_10, 0.38, color="#e08a00", label="10-Mann trifft")
        for xi, v in zip(x - 0.2, rates_11):
            axes[0].text(xi, v + 0.02, f"{v:.2f}", ha="center", fontweight="bold")
        for xi, v in zip(x + 0.2, rates_10):
            axes[0].text(xi, v + 0.02, f"{v:.2f}", ha="center", fontweight="bold")
        axes[0].set_xticks(x, labels)
        axes[0].set_ylabel("Tore pro 100 Min. 11v10")
        axes[0].set_title("Tore-Rate nach Phase seit Rot", fontweight="bold")
        axes[0].legend()
        axes[0].spines[["top", "right"]].set_visible(False)

        state_labels = {"fuehrend": "führend", "ausgeglichen": "ausgeglichen",
                        "rueckstand": "im Rückstand"}
        order = [s for s in ("fuehrend", "ausgeglichen", "rueckstand") if s in states]
        r11 = [per_100(states[s]["goals_11"], states[s]["exposure"]) for s in order]
        r10 = [per_100(states[s]["goals_10"], states[s]["exposure"]) for s in order]
        x2 = np.arange(len(order))
        axes[1].bar(x2 - 0.2, r11, 0.38, color="#1a66cc", label="11-Mann trifft")
        axes[1].bar(x2 + 0.2, r10, 0.38, color="#e08a00", label="10-Mann trifft")
        for xi, v in zip(x2 - 0.2, r11):
            axes[1].text(xi, v + 0.02, f"{v:.2f}", ha="center", fontweight="bold")
        for xi, v in zip(x2 + 0.2, r10):
            axes[1].text(xi, v + 0.02, f"{v:.2f}", ha="center", fontweight="bold")
        axes[1].set_xticks(x2, [state_labels[s] for s in order])
        axes[1].set_ylabel("Tore pro 100 Min. 11v10")
        axes[1].set_title("Rate nach Spielstand des 10-Mann-Teams", fontweight="bold")
        axes[1].legend()
        axes[1].spines[["top", "right"]].set_visible(False)

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
