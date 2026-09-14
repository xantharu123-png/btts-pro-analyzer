"""Explicit offline physical compaction; stop writers and verify a backup first."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_snapshot_storage import compact_snapshots


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--vacuum", action="store_true", help="reclaim unused pages after lossless conversion")
    args = parser.parse_args(argv)
    print(json.dumps(compact_snapshots(args.database, vacuum=args.vacuum), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
