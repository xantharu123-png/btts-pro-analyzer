"""Bounded Linux QA against an explicit isolated database, no provider calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import sys
from time import monotonic, process_time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--tour", choices=("ATP", "WTA"), required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (1400*1024**2, 1400*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    from context_sources.tennis_status import tennis_observations_as_of
    started, cpu = monotonic(), process_time()
    owner = tennis_observations_as_of(args.database, cutoff=datetime.now(timezone.utc), tour=args.tour, prepared=True)
    refs = owner.observation_refs
    evidence = hashlib.sha256()
    for ref in refs:
        evidence.update(bytes.fromhex(ref))
    print(json.dumps({"tour": args.tour, "reference_count": len(refs),
        "reference_set_digest": evidence.hexdigest(), "wall_seconds": monotonic()-started,
        "cpu_seconds": process_time()-cpu, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
