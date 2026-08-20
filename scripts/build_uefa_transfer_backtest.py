"""Build a hash-bound UEFA transfer *shadow* artifact from local JSON.

The command performs no network or provider access.  Its input must already
contain completed, result-only replay fixtures in schema version 1.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Sequence


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from uefa_transfer_backtest import (  # noqa: E402
    TRANSFER_DATASET_SCHEMA_VERSION,
    TransferBacktestError,
    TransferReplayFixture,
    build_transfer_artifact,
    verify_transfer_artifact,
)


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("datetime must include a timezone")
    return parsed


def _load_replays(path: Path) -> list[TransferReplayFixture]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransferBacktestError(f"cannot read replay dataset: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "replays",
    }:
        raise TransferBacktestError("dataset fields do not match schema version 1")
    if document.get("schema_version") != TRANSFER_DATASET_SCHEMA_VERSION:
        raise TransferBacktestError("dataset schema version is unsupported")
    raw_replays = document.get("replays")
    if not isinstance(raw_replays, list) or not raw_replays:
        raise TransferBacktestError("dataset must contain at least one replay")
    return [TransferReplayFixture.from_dict(raw) for raw in raw_replays]


def _replay_kickoff(replay: TransferReplayFixture) -> datetime:
    try:
        value = replay.fixture["fixture"]["date"]
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise TransferBacktestError("replay fixture date is invalid") from exc
    if parsed.tzinfo is None:
        raise TransferBacktestError("replay fixture date must include a timezone")
    return parsed


def _verification_replay(
    replays: Sequence[TransferReplayFixture],
    *,
    competition_id: int,
    cohort: str,
    cutoff: datetime,
) -> TransferReplayFixture:
    candidates = [
        replay
        for replay in replays
        if replay.competition_id == competition_id
        and str(replay.cohort or "").strip().casefold() == cohort
        and _replay_kickoff(replay) <= cutoff
    ]
    if not candidates:
        raise TransferBacktestError(
            "cannot select an in-scope replay for artifact verification"
        )
    return min(
        candidates,
        key=lambda replay: (
            _replay_kickoff(replay),
            replay.fixture["fixture"]["id"],
        ),
    )


def _atomic_write_json(path: Path, document: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an offline UEFA cross-competition shadow backtest artifact. "
            "No provider or network calls are made."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-signature", required=True)
    parser.add_argument(
        "--competition-id",
        required=True,
        action="append",
        type=int,
        dest="competition_ids",
    )
    parser.add_argument(
        "--cohort",
        required=True,
        choices=("qualification", "main"),
    )
    parser.add_argument(
        "--training-cutoff",
        required=True,
        type=_parse_datetime,
    )
    parser.add_argument(
        "--market-key",
        action="append",
        dest="market_keys",
        help="Repeat to restrict the artifact; the default evaluates all model markets.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        replays = _load_replays(args.input)
        artifact = build_transfer_artifact(
            replays,
            model_signature=args.model_signature,
            competition_ids=args.competition_ids,
            cohort=args.cohort,
            training_cutoff=args.training_cutoff,
            market_keys=args.market_keys,
        )
        # Exercise the same strict parser used by later offline audit tooling,
        # including one real round/source-domain sample per competition.
        parsed = None
        for competition_id in sorted(set(args.competition_ids)):
            representative = _verification_replay(
                replays,
                competition_id=competition_id,
                cohort=args.cohort,
                cutoff=args.training_cutoff,
            )
            parsed = verify_transfer_artifact(
                artifact,
                expected_model_signature=args.model_signature,
                expected_competition_id=competition_id,
                expected_cohort=args.cohort,
                fixture_round=representative.fixture["league"]["round"],
                expected_source_league_ids=representative.source_league_ids,
                fixture_kickoff=args.training_cutoff + timedelta(days=1),
                expected_dataset_hash=artifact["provenance"]["dataset_hash"],
                expected_artifact_id=artifact["artifact_id"],
            )
        if parsed is None:
            raise TransferBacktestError("artifact has no competition scope")
        _atomic_write_json(args.output, artifact)
    except (TransferBacktestError, OSError, ValueError) as exc:
        print(f"UEFA transfer artifact not written: {exc}", file=sys.stderr)
        return 2

    print(
        "shadow artifact written: "
        f"{args.output.resolve()} | replays={parsed.provenance.replay_count} | "
        f"modeled={parsed.provenance.modeled_replay_count} | "
        f"validated_markets={len(parsed.validated_market_keys)} | "
        "release_authorized=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
