"""Offline dispersion only; intentionally never emits mean loss or tests efficacy.

Run with python -B, preventing bytecode writes in the source worktree.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import groupby
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
import challenge_engine as ce

LEAGUES = {"E0": 39, "D1": 78, "I1": 135, "SP1": 140, "F1": 61}
START = date(2024, 7, 1)  # Monday; 7-day clusters run Mon-Sun across all leagues
END = date(2025, 6, 30)
WARM = date(2023, 7, 1)
FIELDS = ("Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG")


def get_rows(code, data_dir):
    dig = hashlib.sha256()
    rows, keys = [], set()
    for season, lo, hi in (("2324", WARM, START), ("2425", START, date(2025, 7, 1))):
        with (data_dir / f"{season}_{code}.csv").open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
            indexes = [headers.index(field) for field in FIELDS]
            for raw in reader:
                if not raw or not raw[indexes[1]]:
                    continue
                div, ds, home, away, hg, ag = [raw[i].strip() for i in indexes]
                day = datetime.strptime(ds, "%d/%m/%Y").date()
                assert lo <= day < hi and div == code and home and away and home != away
                assert hg.isdecimal() and ag.isdecimal()
                key = (season, home, away)
                assert key not in keys, key
                keys.add(key)
                row = (day, home, away, int(hg), int(ag))
                dig.update(json.dumps([day.isoformat(), *row[1:]], ensure_ascii=True).encode() + b"\n")
                rows.append(row)
    return sorted(rows), dig.hexdigest()


def hda(law, delta):
    assert abs(math.fsum(law.values()) - 1) < 1e-12 and min(law.values()) >= 0
    sums = [0., 0., 0.]
    for (h, a), p in law.items():
        j = 0 if h > a else 1 if h == a else 2
        sums[j] += p * math.exp(delta * (h - a))
    total = sum(sums)
    return tuple(p / total for p in sums)


def replay(code, league, diffs, data_dir):
    rows, digest = get_rows(code, data_dir)
    ids, history = {}, []
    stats = Counter()
    total_h = total_a = 0
    for day, games in groupby(rows, key=lambda row: row[0]):
        completed_today = []
        day_h = day_a = 0
        for _, home, away, hg, ag in games:
            home_id = ids.setdefault(home, len(ids) + 1)
            away_id = ids.setdefault(away, len(ids) + 1)
            fixture = {"fixture": {"date": day.isoformat() + "T00:00:00Z",
                                   "id": f"{day}/{home_id}/{away_id}"},
                       "league": {"id": league},
                       "teams": {"home": {"id": home_id}, "away": {"id": away_id}}}
            if day < START:
                stats["warmup"] += 1
            else:
                stats["development"] += 1
                assert day <= END and len(history) >= 60 and min(total_h, total_a) > 0
                model = ce._fixture_model(fixture, history, goal_model=ce.GOAL_MODEL_FORM_STRENGTH)
                if model is None:
                    stats["missing_raw_model"] += 1
                else:
                    assert model["goal_model"] == ce.PRODUCTION_GOAL_MODEL and model["form_strength"] is not None
                    law = ce.score_matrix(*model["active_lambdas"])
                    delta = 0.125 * math.log(total_h / total_a)
                    p, q = hda(law, 0), hda(law, delta)
                    j = 0 if hg > ag else 1 if hg == ag else 2
                    diff = math.fsum((q[i] - (i == j))**2 - (p[i] - (i == j))**2 for i in range(3))
                    diffs.append(((day - START).days // 7, diff))
                    stats["planning_pairs"] += 1
            # Only after forecast; FT final score as classified by source fields.
            completed_today.append({**fixture, "goals": {"home": hg, "away": ag},
                                    "fixture": {**fixture["fixture"], "status": {"short": "FT"}}})
            day_h += hg
            day_a += ag
        # Games on the same date can never enter one another's history.
        history.extend(completed_today)
        total_h += day_h
        total_a += day_a
    return {**stats, "sport_projection_sha256": digest}


def run(data_dir):
    assert ce.PRODUCTION_GOAL_MODEL == ce.GOAL_MODEL_FORM_STRENGTH
    diffs = []
    leagues = {k: replay(k, v, diffs, data_dir) for k, v in LEAGUES.items()}
    n = len(diffs)
    m = statistics.mean(d for _, d in diffs)
    block = defaultdict(float)
    for k, d in diffs:
        block[k] += d - m
    g = len(block)
    # CR1 variance of a game-weighted intercept, scaled by N; no week gets
    # equal-game weight when its size differs. One block across all five leagues.
    s2 = g / (g - 1) * math.fsum(v*v for v in block.values()) / n
    z = statistics.NormalDist().inv_cdf
    need = math.ceil((z(.975) + z(.8))**2 * s2 / .002**2)
    return {"leagues": leagues, "pilot_pairs": n, "nonempty_weeks": g,
            "cluster_sd_equivalent_per_game": math.sqrt(s2),
            "independent_game_sd_descriptive": statistics.stdev(d for _, d in diffs),
            "normal_approx_target_games": need, "target_weeks_same_throughput": math.ceil(need*g/n),
            "source_sha256": {f: hashlib.sha256((SOURCE/f).read_bytes()).hexdigest()
                for f in ("challenge_engine.py", "football_form_strength.py")},
            "verified_published_law_and_home_venue_pairs_in_these_csvs": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv-dir', required=True, type=Path, help='Directory with the ten 2324/2425 result CSVs')
    print(json.dumps(run(parser.parse_args().csv_dir), indent=2))
