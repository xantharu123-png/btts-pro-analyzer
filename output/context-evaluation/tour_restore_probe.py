"""Isolated Linux tour-only backup/restore proof using real built artifacts.

Run as an unprivileged QA user. This never opens a production DB, never
publishes a new model, and never reads a production integrity key.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import zipfile


def inventory(path):
    assert path.is_file() and not path.is_symlink()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        assert db.execute("PRAGMA quick_check").fetchall() == [("ok",)]
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"artifacts", "manifests", "active_manifest"}, tables
        return {
            "artifacts": db.execute(
                "SELECT digest,kind,payload,created_at FROM artifacts ORDER BY digest"
            ).fetchall(),
            "manifests": db.execute(
                "SELECT digest,predecessor,payload,published_at FROM manifests ORDER BY digest"
            ).fetchall(),
            "active_manifest": db.execute(
                "SELECT id,digest FROM active_manifest ORDER BY id"
            ).fetchall(),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("qa_root", type=Path)
    args = parser.parse_args()
    assert os.name == "posix" and os.geteuid() != 0
    os.umask(0o077)
    root = args.qa_root
    assert root.is_absolute() and root.resolve(strict=True) == root
    assert root.parent == Path("/tmp") and root.name.startswith("betboy-tour-restore-qa.")
    assert root.stat().st_uid == os.geteuid()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    source = root / "source"
    assert source.is_dir() and not source.is_symlink()
    incoming = root / "input" / "context_models.db"
    before_input = inventory(incoming)
    assert len(before_input["artifacts"]) == 2
    assert len(before_input["manifests"]) == 2
    assert len(before_input["active_manifest"]) == 1
    live = root / "live-app"
    live.mkdir(mode=0o700)
    runtime = live / "runtime_state"
    runtime.mkdir(mode=0o700)
    db_path = runtime / "context_models.db"
    # SQLite online backup, not a potentially incomplete raw live DB copy.
    with closing(sqlite3.connect(incoming.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(db_path)) as dest:
            src.backup(dest)
    os.chmod(db_path, 0o600)
    os.environ["BETBOY_RUNTIME_STATE_DIR"] = str(runtime)
    os.environ["BETBOY_REPORT_DIR"] = str(root / "reports")
    sys.path.insert(0, str(source))
    import requests

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Network/source access is forbidden during restore QA")

    requests.sessions.Session.request = forbidden_network
    from model_artifacts import load_artifact, load_manifest
    from scripts import backup_runtime_databases as backup
    from scripts import stage_runtime_databases as stage
    from tennis.predict import predict_match
    from tennis.state_codec import encode_state
    from tennis.tour_state import load_tour_state

    decision = datetime.now(timezone.utc)
    baseline = inventory(db_path)
    assert baseline == before_input
    manifest, slots = load_manifest(db_path, decision_cutoff=decision)
    assert set(slots) == {"tennis:ATP", "tennis:WTA"}
    for digest, kind, *_ in baseline["artifacts"]:
        assert kind == "tennis-tour-state"
        load_artifact(db_path, digest)
    states, predictions, pairs = {}, {}, {}
    for tour in ("ATP", "WTA"):
        state = load_tour_state(tour, path=db_path, allow_legacy=False, decision_cutoff=decision)
        assert state.tour_scope == tour and state.artifact_hash == slots[f"tennis:{tour}"]
        players = sorted(state.elo.known_players(), key=lambda p: (-state.elo.overall.matches(p), p))
        assert len(players) >= 2
        pair = players[:2]
        pairs[tour] = pair
        states[tour] = encode_state(state, tour=tour)
        predictions[tour] = predict_match(
            state, *pair, "Hard", best_of=3, tour=tour, indoor=False, as_of=decision
        )
    assert inventory(db_path) == baseline

    assert stage.discover_databases(live) == [db_path]
    private_stage = root / "private-stage"
    private_stage.mkdir(mode=0o700)
    current = private_stage / "current"
    current.mkdir(mode=0o700)
    identity = current.lstat()
    staged_manifest = stage.stage_databases(
        live, current, expected_stage_identity=(identity.st_dev, identity.st_ino),
        expected_uid=os.geteuid(), expected_gid=os.getegid(),
    )
    assert staged_manifest["database_count"] == 1
    assert [r["path"] for r in staged_manifest["databases"]] == ["runtime_state/context_models.db"]
    staged = current / "runtime_state" / "context_models.db"
    assert stat.S_IMODE(current.stat().st_mode) == 0o550
    assert stat.S_IMODE(staged.stat().st_mode) == 0o440
    assert stat.S_IMODE((current / "manifest.json").stat().st_mode) == 0o440
    assert staged_manifest["databases"][0]["sha256"] == hashlib.sha256(staged.read_bytes()).hexdigest()
    assert all(not Path(str(staged) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
    assert inventory(staged) == baseline
    with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    archive, count = backup.create_archive(
        root / "archives", root=current, logical_root=live,
        stage_manifest_path=current / "manifest.json",
    )
    assert count == backup.verify_archive(archive) == 1

    restored_root = root / "restored-app"
    restored_root.mkdir(mode=0o700)
    restored_runtime = restored_root / "runtime_state"
    restored_runtime.mkdir(mode=0o700)
    restored = restored_runtime / "context_models.db"
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.namelist() == ["runtime_state/context_models.db"]
        member = zipped.read("runtime_state/context_models.db")
        with restored.open("xb") as output:
            output.write(member)
    assert stat.S_IMODE(restored.stat().st_mode) == 0o600
    assert restored.read_bytes() == member
    assert inventory(restored) == baseline
    assert load_manifest(restored, decision_cutoff=decision) == (manifest, slots)
    for digest, *_ in baseline["artifacts"]:
        assert load_artifact(restored, digest) == load_artifact(db_path, digest)
    for tour in ("ATP", "WTA"):
        state = load_tour_state(tour, path=restored, allow_legacy=False, decision_cutoff=decision)
        assert encode_state(state, tour=tour) == states[tour]
        prediction = predict_match(
            state, *pairs[tour], "Hard", best_of=3, tour=tour, indoor=False, as_of=decision
        )
        assert asdict(prediction) == asdict(predictions[tour])
    assert inventory(incoming) == before_input
    assert inventory(db_path) == inventory(restored) == baseline
    print(json.dumps({
        "qa_root": str(root), "decision": decision.isoformat(),
        "uid": os.geteuid(), "gid": os.getegid(),
        "discovered": 1, "staged": 1, "archived": count, "verified": 1,
        "sqlite": "ok", "foreign_keys": "ok", "registry_rows_equal": True,
        "forecast_outputs_equal": True, "row_counts": {k: len(v) for k, v in baseline.items()},
        "model_manifest": manifest, "slots": slots,
        "archive": str(archive), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "member_sha256": hashlib.sha256(member).hexdigest(),
        "stage_manifest_sha256": hashlib.sha256((current / "manifest.json").read_bytes()).hexdigest(),
        "tour_proofs": {tour: {
            "players": pairs[tour], "stats_through": states[tour]["stats_through"],
            "stats_through_kind": states[tour]["stats_through_kind"],
            "built_at": states[tour]["built_at"],
            "market_summary": predictions[tour].market_summary(),
        } for tour in ("ATP", "WTA")},
        "scope": "real cached tour artifacts; static restore, not a live-tour-in-WAL or full D4 proof",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
