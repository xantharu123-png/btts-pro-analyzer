"""CLI wrapper: run the calibration watchdog and print JSON on the last line."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tennis.calibration_watch import run_watch

if __name__ == "__main__":
    result = run_watch()
    print("CALIBRATION_WATCH_JSON=" + json.dumps(result))
    for market, info in result["markets"].items():
        flag = "DRIFT" if info["drift"] else "ok"
        print(f"  {market:16s} n={info['n']:5d} rms={info['rms']:.4f} "
              f"max_mid_bias={info['max_mid_bias']:.4f} [{flag}]")
    print(f"STATUS: {result['status']} (n={result['n_scored']})")
