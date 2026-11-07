"""Read-only measurement of one goal basis against another on new games.

Default: the form strength (production since 07.11.2026) against the previous legacy basis
(docs/audits/2026-11-06-formstaerke-test.md). ``--baseline legacy_form_strength_v1 --candidate
dixon_coles_hl365_hybrid`` measures the hybrid against the production basis (owner decision 07.11.2026:
this replaces the 300/1000-pair shadow plan of the hybrid).

For every league history the app stores in ``.shadow_cache`` (current and previous season), the unchanged
validation path ``challenge_engine._walk_forward_market_records`` runs once per basis. Only calibrated
goal-market forecasts of games kicked off on or after ``--since`` are scored, against the four
pre-registered conditions (candidate minus baseline).

No network, no provider call, no write. Run on the server, for example:
    nice -n 19 /opt/betboy/venv/bin/python -I scripts/form_strength_measurement.py --since 2026-11-06
"""
from __future__ import annotations

import argparse
import math
import re
import socket
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULT_KEYS = ("RESULT_HOME", "RESULT_DRAW", "RESULT_AWAY")
_EPS = 1e-12


def scored_records(fixtures, goal_model, since):
    """Goal-market (probability, outcome) pairs of games on/after ``since``, keyed by market."""
    import challenge_engine as engine
    order = []
    original = engine.fixture_market_probabilities

    def tracking(fixture, *args, **kwargs):
        result = original(fixture, *args, **kwargs)
        if result is not None:
            order.append((str((fixture.get("fixture") or {}).get("id")), engine._fixture_datetime(fixture)))
        return result

    engine.fixture_market_probabilities = tracking
    try:
        records = engine._walk_forward_market_records(fixtures, goal_model=goal_model)
    finally:
        engine.fixture_market_probabilities = original
    out = {}
    for spec in engine.GOAL_MARKET_SPECS:
        record = records[spec.key]
        if len(record["probabilities"]) != len(order):
            raise ValueError("record order does not match the evaluated fixtures: " + spec.key)
        out[spec.key] = {fixture_id: (p, int(y)) for p, y, (fixture_id, kickoff)
                         in zip(record["probabilities"], record["outcomes"], order) if kickoff >= since}
    return out


def league_losses(live, form):
    """Summed Brier/log-loss differences (form minus live) and the 1X2 log loss of both arms."""
    totals = {"n": 0, "db": 0.0, "dl": 0.0, "b0": 0.0, "l0": 0.0, "x12": [0.0, 0.0, 0]}
    bands = {"live": defaultdict(lambda: [0, 0.0, 0]), "form": defaultdict(lambda: [0, 0.0, 0])}
    for key, live_pairs in live.items():
        form_pairs = form[key]
        # Only games both arms forecast are compared (an arm may fail closed on a game).
        for fixture_id in sorted(set(live_pairs) & set(form_pairs)):
            (p0, y), (p1, y1) = live_pairs[fixture_id], form_pairs[fixture_id]
            if y != y1:
                raise ValueError("both arms must see the same outcome: " + key)
            q0, q1 = min(max(p0, _EPS), 1 - _EPS), min(max(p1, _EPS), 1 - _EPS)
            b0, b1 = (q0 - y) ** 2, (q1 - y) ** 2
            l0 = -math.log(q0 if y else 1 - q0)
            l1 = -math.log(q1 if y else 1 - q1)
            totals["n"] += 1
            totals["db"] += b1 - b0
            totals["dl"] += l1 - l0
            totals["b0"] += b0
            totals["l0"] += l0
            for arm, p in (("live", p0), ("form", p1)):
                cell = bands[arm][min(int(p * 10), 9)]
                cell[0] += 1
                cell[1] += p
                cell[2] += y
            if key in RESULT_KEYS and y:
                totals["x12"][0] += -math.log(q0)
                totals["x12"][1] += -math.log(q1)
                totals["x12"][2] += 1
    return totals, bands


def verdict(per_league, bands, *, min_band=200):
    """The four pre-registered conditions over league clusters."""
    per_league = {league: v for league, v in per_league.items() if v["n"]}
    n = sum(v["n"] for v in per_league.values())
    k = len(per_league)
    if n == 0 or k < 2:
        return {"forecasts": n, "leagues": k, "status": "not_enough_data"}

    def pooled(field):
        mean = sum(v[field] for v in per_league.values()) / n
        var = sum((v[field] - mean * v["n"]) ** 2 for v in per_league.values()) * k / (k - 1) / n ** 2
        return mean, math.sqrt(var)

    brier, brier_se = pooled("db")
    loss, loss_se = pooled("dl")
    better = sum(1 for v in per_league.values() if v["dl"] < 0)
    worst = 0.0
    for band, live_cell in bands["live"].items():
        form_cell = bands["form"].get(band)
        if not form_cell or live_cell[0] < min_band or form_cell[0] < min_band:
            continue
        gap_live = abs(live_cell[1] - live_cell[2]) / live_cell[0]
        gap_form = abs(form_cell[1] - form_cell[2]) / form_cell[0]
        worst = max(worst, 100 * (gap_form - gap_live))
    x_live = sum(v["x12"][0] for v in per_league.values())
    x_form = sum(v["x12"][1] for v in per_league.values())
    conditions = [brier + 1.96 * brier_se < 0 and loss + 1.96 * loss_se < 0, better >= 2 * k / 3,
                  worst <= 2.0, x_form <= x_live]
    return {"forecasts": n, "leagues": k, "brier_diff": brier, "brier_se": brier_se, "logloss_diff": loss,
            "logloss_se": loss_se, "leagues_better": better, "worst_band_pp": worst,
            "x12_live": x_live / max(1, sum(v["x12"][2] for v in per_league.values())),
            "x12_form": x_form / max(1, sum(v["x12"][2] for v in per_league.values())),
            "conditions": conditions, "status": "passed" if all(conditions) else "not_passed"}


def _latest_histories(cache_dir: Path, version_token: str):
    pattern = re.compile(re.escape(version_token) + r"_(\d+)_(\d{4})_(\d{4}-\d{2}-\d{2})\.pkl$")
    latest = {}
    for path in cache_dir.glob("history_*.pkl"):
        match = pattern.search(path.name)
        if match:
            key = (int(match.group(1)), int(match.group(2)))
            if key not in latest or match.group(3) > latest[key][0]:
                latest[key] = (match.group(3), path)
    return latest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", default="2026-11-06", help="first kickoff date that is scored (UTC)")
    parser.add_argument("--cache-dir", default=str(ROOT / ".shadow_cache"))
    parser.add_argument("--baseline", default="legacy", help="goal basis compared against")
    parser.add_argument("--candidate", default="legacy_form_strength_v1", help="goal basis under measurement")
    args = parser.parse_args(argv)
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(OSError("offline measurement"))
    import pickle
    import challenge_engine as engine
    from runtime_paths import open_trusted_pickle
    for basis in (args.baseline, args.candidate):
        if basis not in engine.GOAL_MODELS:
            parser.error(f"unknown goal basis: {basis}")
    print(f"Basis {args.baseline} gegen Kandidat {args.candidate}, Spiele ab {args.since}", flush=True)
    token = engine.CHALLENGE_PREDICTION_VERSION.replace(":", "-")
    per_league, all_bands = {}, {"live": defaultdict(lambda: [0, 0.0, 0]), "form": defaultdict(lambda: [0, 0.0, 0])}
    for (league, season), (_day, path) in sorted(_latest_histories(Path(args.cache_dir), token).items()):
        with open_trusted_pickle(path) as stream:
            fixtures = pickle.load(stream)
        try:
            live = scored_records(fixtures, args.baseline, since)
            form = scored_records(fixtures, args.candidate, since)
        except ValueError as exc:
            print(f"Liga {league} Saison {season}: übersprungen ({exc})", flush=True)
            continue
        totals, bands = league_losses(live, form)
        per_league[league] = totals
        for arm in bands:
            for band, cell in bands[arm].items():
                target = all_bands[arm][band]
                for index in range(3):
                    target[index] += cell[index]
        if totals["n"]:
            print(f"Liga {league} Saison {season}: {totals['n']} Prognosen, "
                  f"Log-Loss-Differenz je Prognose {totals['dl'] / totals['n']:+.5f}", flush=True)
    result = verdict(per_league, all_bands)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
