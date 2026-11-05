"""Offline fit and walk-forward test of the UEFA league strength (plan 2026-11-05, step 1).

Usage: python scripts/uefa_league_strength_fit.py DATA_DIR [--burn 200]

DATA_DIR holds ``uefa.json.gz`` (stored UEFA 90-minute results, exported read-only from
context_models.db) and ``domestic_<league>_<season>.json.gz`` (owner-approved one-off
API-Football fetch of 05.11.2026, 88 calls). Nothing here calls an API or writes a database.

1. For every UEFA game, rebuild the live cross-competition goal rates with the unchanged
   ``challenge_engine._fixture_model``: UEFA competition (season and previous season) for the
   league means, both teams' domestic-league results for team strength.
2. Offset Poisson regression with a ridge prior (tau) and a time half-life:
   log lam_home' = log lam_home + c_home + s[home league] - s[away league]
   log lam_away' = log lam_away + c_away + s[away league] - s[home league]
3. Walk-forward: before each matchday fit only on earlier games, predict that matchday.
4. Print the final table (fit on all games) for ``football_league_strength.py``.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import challenge_engine as ce  # noqa: E402

TAU = 0.3
HALF_LIFE_DAYS = 365.0
BINARY = ("o15", "o25", "o35", "btts", "h05", "a05", "h15", "a15")


def _when(row):
    return datetime.fromisoformat(row["date"].replace("Z", "+00:00"))


def _api_shape(row):
    return {"fixture": {"id": row["id"], "date": row["date"], "status": {"short": row["status"]}},
            "league": {"id": row["league"], "season": row["season"]},
            "teams": {"home": {"id": row["home"]}, "away": {"id": row["away"]}},
            "goals": {"home": row["hg"], "away": row["ag"]}}


def build_dataset(data_dir):
    team_rows, names = defaultdict(list), {}
    for path in glob.glob(os.path.join(data_dir, "domestic_*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for row in json.load(handle):
                if row["status"] == "FT" and isinstance(row["hg"], int) and isinstance(row["ag"], int):
                    row["when"] = _when(row)
                    team_rows[row["home"]].append(row)
                    team_rows[row["away"]].append(row)
                    names[row["league"]] = "%s / %s" % (row["country"], row["league_name"])
    with gzip.open(os.path.join(data_dir, "uefa.json.gz"), "rt", encoding="utf-8") as handle:
        uefa = sorted(json.load(handle), key=_when)
    for row in uefa:
        row["when"] = _when(row)

    def domestic_league(team, kickoff):
        recent = [r for r in team_rows.get(team, ()) if kickoff - timedelta(days=400) <= r["when"] < kickoff]
        return Counter(r["league"] for r in recent).most_common(1)[0][0] if recent else None

    rows, skipped = [], Counter()
    for game in uefa:
        kickoff = game["when"]
        leagues = [domestic_league(game["home"], kickoff), domestic_league(game["away"], kickoff)]
        if None in leagues:
            skipped["team outside fetched leagues"] += 1
            continue
        history = [_api_shape(r) for r in uefa if r["league"] == game["league"]
                   and r["season"] in (game["season"], game["season"] - 1) and r["when"] < kickoff]
        team_history = []
        for team, league in zip((game["home"], game["away"]), leagues):
            own = sorted((r for r in team_rows[team] if r["league"] == league and r["when"] < kickoff),
                         key=lambda r: r["when"])[-60:]
            team_history.extend(_api_shape(r) for r in own)
        model = ce._fixture_model(_api_shape(game), history, team_history=team_history)
        if model is None:
            skipped["model not computable"] += 1
            continue
        lh, la = model["active_lambdas"]
        rows.append({"date": game["date"], "comp": game["league"], "season": game["season"],
                     "home_league": leagues[0], "away_league": leagues[1], "lh": lh, "la": la,
                     "hg": game["hg"], "ag": game["ag"]})
    return rows, names, len(uefa), skipped


def fit(rows, leagues, ref_date, tau=TAU, half_life=HALF_LIFE_DAYS):
    index = {league: i for i, league in enumerate(leagues)}
    count = len(leagues)
    hi = np.array([index[r["home_league"]] for r in rows])
    ai = np.array([index[r["away_league"]] for r in rows])
    off_h, off_a = np.log([r["lh"] for r in rows]), np.log([r["la"] for r in rows])
    yh, ya = np.array([r["hg"] for r in rows], float), np.array([r["ag"] for r in rows], float)
    age = np.array([(ref_date - _when(r)).days for r in rows])
    weight = 0.5 ** (age / half_life)

    def objective(theta):
        s = theta[2:]
        eta_h = off_h + theta[0] + s[hi] - s[ai]
        eta_a = off_a + theta[1] + s[ai] - s[hi]
        mh, ma = np.exp(eta_h), np.exp(eta_a)
        rh, ra = weight * (mh - yh), weight * (ma - ya)
        value = np.sum(weight * (mh - yh * eta_h)) + np.sum(weight * (ma - ya * eta_a))
        value += 0.5 * np.sum(s ** 2) / tau ** 2
        grad = np.empty_like(theta)
        grad[0], grad[1] = rh.sum(), ra.sum()
        grad[2:] = (np.bincount(hi, rh, count) - np.bincount(ai, rh, count)
                    + np.bincount(ai, ra, count) - np.bincount(hi, ra, count) + s / tau ** 2)
        return value, grad

    theta = minimize(objective, np.zeros(2 + count), jac=True, method="L-BFGS-B").x
    return float(theta[0]), float(theta[1]), {league: float(theta[2 + i]) for i, league in enumerate(leagues)}


def adjusted(row, params):
    c_home, c_away, strength = params
    gap = strength[row["home_league"]] - strength[row["away_league"]]
    return row["lh"] * math.exp(c_home + gap), row["la"] * math.exp(c_away - gap)


def losses(row, lam_home, lam_away):
    ph, pa = poisson.pmf(np.arange(16), lam_home), poisson.pmf(np.arange(16), lam_away)
    matrix = np.outer(ph, pa)
    matrix /= matrix.sum()
    goals = np.add.outer(np.arange(16), np.arange(16))
    hg, ag = row["hg"], row["ag"]
    p = {"o15": matrix[goals >= 2].sum(), "o25": matrix[goals >= 3].sum(), "o35": matrix[goals >= 4].sum(),
         "btts": matrix[1:, 1:].sum(), "h05": matrix[1:, :].sum(), "a05": matrix[:, 1:].sum(),
         "h15": matrix[2:, :].sum(), "a15": matrix[:, 2:].sum()}
    hit = {"o15": hg + ag >= 2, "o25": hg + ag >= 3, "o35": hg + ag >= 4, "btts": hg > 0 and ag > 0,
           "h05": hg >= 1, "a05": ag >= 1, "h15": hg >= 2, "a15": ag >= 2}
    three_way = (np.tril(matrix, -1).sum(), np.trace(matrix), np.triu(matrix, 1).sum())
    outcome = 0 if hg > ag else 1 if hg == ag else 2
    result = {"goal": -(poisson.logpmf(hg, lam_home) + poisson.logpmf(ag, lam_away)),
              "1x2": -math.log(max(1e-9, three_way[outcome]))}
    for key in BINARY:
        q = min(1 - 1e-9, max(1e-9, p[key]))
        result[key] = -math.log(q if hit[key] else 1 - q)
    bands = [(p[key], hit[key]) for key in BINARY] + [(1 - p[key], not hit[key]) for key in BINARY]
    return result, bands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir")
    parser.add_argument("--burn", type=int, default=200)
    args = parser.parse_args()
    rows, names, total, skipped = build_dataset(args.data_dir)
    rows.sort(key=lambda r: r["date"])
    leagues = sorted({r["home_league"] for r in rows} | {r["away_league"] for r in rows})
    print("UEFA games %d, computable %d, skipped %s" % (total, len(rows), dict(skipped)))

    per_day = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(lambda: [0.0, 0.0])
    band_live, band_new = defaultdict(lambda: [0, 0.0, 0]), defaultdict(lambda: [0, 0.0, 0])
    tested = 0
    for day in sorted({r["date"][:10] for r in rows}):
        train = [r for r in rows if r["date"][:10] < day]
        if len(train) < args.burn:
            continue
        params = fit(train, leagues, datetime.fromisoformat(day + "T00:00:00+00:00"))
        for row in (r for r in rows if r["date"][:10] == day):
            tested += 1
            live, live_bands = losses(row, row["lh"], row["la"])
            new, new_bands = losses(row, *adjusted(row, params))
            for key in live:
                per_day[key][day] += new[key] - live[key]
                totals[key][0] += live[key]
                totals[key][1] += new[key]
            for store, bands in ((band_live, live_bands), (band_new, new_bands)):
                for q, hit in bands:
                    cell = store[min(9, int(q * 10))]
                    cell[0] += 1
                    cell[1] += q
                    cell[2] += hit
    print("walk-forward: %d games after burn-in %d" % (tested, args.burn))
    for key in ("goal", "1x2") + BINARY:
        diffs = np.array(list(per_day[key].values()))
        se = diffs.std(ddof=1) * math.sqrt(len(diffs)) / tested
        print("  %-5s live %.4f  new %.4f  diff %+.4f  (SE %.4f)" % (
            key, totals[key][0] / tested, totals[key][1] / tested, diffs.sum() / tested, se))
    for label, store in (("live", band_live), ("new ", band_new)):
        print("  bands %s: %s" % (label, "  ".join("%d0%% n%d %.1f->%.1f" % (
            b, v[0], 100 * v[1] / v[0], 100 * v[2] / v[0]) for b, v in sorted(store.items()) if b >= 3)))

    last = _when(rows[-1])
    c_home, c_away, strength = fit(rows, leagues, last)
    games = Counter()
    for row in rows:
        games[row["home_league"]] += 1
        games[row["away_league"]] += 1
    print("final fit through %s: HOME_OFFSET = %.3f, AWAY_OFFSET = %.3f" % (last.date(), c_home, c_away))
    print("STRENGTHS = {")
    for league in sorted(leagues, key=lambda x: -strength[x]):
        print("    %d: %.3f,  # %s, %d team games" % (league, strength[league], names[league], games[league]))
    print("}")


if __name__ == "__main__":
    main()
