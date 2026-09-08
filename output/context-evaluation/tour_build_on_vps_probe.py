"""Build QA models in place from already-present VPS training seeds.

No local model/database is uploaded. No production DB, key, environment file
or mutable training cache is opened. The only production-tree inputs are the
versioned tennis/data training seeds, read without alteration or network.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


parser = argparse.ArgumentParser()
parser.add_argument("qa_root", type=Path)
args = parser.parse_args()
root = args.qa_root
assert os.name == "posix" and os.geteuid() != 0
assert root.is_absolute() and root.resolve(strict=True) == root
assert root.parent == Path("/tmp") and root.name.startswith("betboy-tour-restore-qa.")
assert root.stat().st_uid == os.geteuid() and stat.S_IMODE(root.stat().st_mode) == 0o700
os.umask(0o077)
source = root / "source"
assert source.is_dir() and not source.is_symlink()
destination = root / "input"
destination.mkdir(mode=0o700)  # A fresh test, never overwrite an existing DB.
os.environ["BETBOY_RUNTIME_STATE_DIR"] = str(destination)
os.environ["BETBOY_REPORT_DIR"] = str(root / "reports")
sys.path.insert(0, str(source))
import requests


def forbidden_network(*args, **kwargs):
    raise AssertionError("Offline VPS QA must not call a provider")


requests.sessions.Session.request = forbidden_network
import runtime_paths

# Explicit process-local read-only test input. All mutable paths still point
# into this new private QA tree; no production setting/file is changed.
seeds = Path("/opt/betboy/app/tennis/data")
assert seeds.is_dir() and seeds.resolve(strict=True) == seeds
runtime_paths.PACKAGED_TENNIS_TRAINING_DATA_DIR = seeds
from tennis.tour_state import build_tour_state, refresh_tours

cutoff = datetime.now(timezone.utc)
names = {"atp_tournaments.csv"}
for year in range(2010, cutoff.year + 1):
    names.update((f"atp_matches_{year}.csv", f"atp_odds_{year}.xlsx", f"wta_odds_{year}.xlsx"))
# Some unused historical ATP price years are not packaged. Missing required
# files still fail the real loader under the network guard; never fabricate.
def seed_inventory():
    result = {}
    for name in sorted(names):
        path = seeds / name
        assert not path.is_symlink()
        if path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


before = seed_inventory()
diagnostics = {}


def build(tour):
    diagnostics[tour] = {}
    return build_tour_state(tour, as_of=cutoff, refresh_training_data=False,
                            diagnostics=diagnostics[tour])


outcome = refresh_tours(path=destination / "context_models.db", as_of=cutoff, builder=build)
assert seed_inventory() == before, "Versioned VPS training seeds changed during isolated QA"
compact = {
    tour: {phase: {key: value for key, value in summary.items()
                   if key not in {"skipped_matches", "skipped_tournaments"}}
           for phase, summary in phases.items()}
    for tour, phases in diagnostics.items()
}
print(json.dumps({"qa_root": str(root), "cutoff": cutoff.isoformat(),
                  "seed_root": str(seeds), "seed_files": len(before),
                  "seed_inventory_sha256": hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                  "versioned_seeds_unchanged": True, "local_database_uploaded": False,
                  "outcome": outcome, "serve_diagnostics": compact}, indent=2))
assert outcome["status"] == "complete", "Both real offline tour builds must succeed before restore QA"
