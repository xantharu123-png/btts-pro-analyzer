"""Trusted-updater context hook: isolated data and real Bash, never a VPS."""
from copy import deepcopy
from contextlib import closing
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "deploy/update_server.sh"
LIMITS = {
    "d2-final-source-replay-not-opened", "d1-participation-training-receipts-unresolved",
    "d1-final-source-replay-unavailable", "d1-fit-owning-replay-unavailable",
    "d2-dataset-owning-experiment-unavailable", "d1-case-owning-replay-unavailable",
    "d1-original-replay-context-unavailable", "d2-evaluation-opening-unavailable",
    "d2-approval-evidence-resolution-unavailable", "d3-owning-family-replay-unavailable",
    "d3-owning-source-feature-replay-unavailable", "d3-snapshot-input-binding-unavailable",
}


def shell_function(name, *, optional=False):
    text = UPDATER.read_text(encoding="utf-8")
    start = text.find(name + "() {")
    if optional and start < 0:
        return ""
    assert start >= 0, f"missing actual updater function {name}"
    lines, delimiter = [], None
    for line in text[start:].splitlines(keepends=True):
        lines.append(line)
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        found = re.search(r"<<'([^']+)'", line)
        if found:
            delimiter = found[1]
        elif line == "}\n":
            return "".join(lines)
    raise AssertionError("unterminated actual shell function")


@pytest.fixture
def data():
    source = shell_function("context_hook_data")
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    code = source[start:source.index("\nPY", start)]
    namespace = {"__name__": "isolated_hook_functions"}
    exec(compile(code, str(UPDATER) + "::context_hook_data", "exec"), namespace)
    return namespace


def report(*, incomplete=False):
    return {"status": "incomplete" if incomplete else "verified", "schema": 1,
        "verification_level": "transport_only" if incomplete else "structural",
        "empirical_approval_verified": False,
        "limitations": ["d3-owning-source-feature-replay-unavailable"] if incomplete else [],
        "d2_verified": {name: [] for name in ("experiments", "datasets", "fits", "cases", "evaluations", "approvals")},
        "counts": {name: 0 for name in ("artifacts", "manifests", "contents", "observations", "snapshots", "rollbacks")},
        "active_manifest": None, "active_slots_hash": hashlib.sha256(b"{}").hexdigest(),
        "active_slot_count": 0, "tour_states": {}}


@pytest.mark.parametrize("incomplete", [False, True])
def test_closed_continuity_result(data, incomplete):
    value = report(incomplete=incomplete)
    assert data["validate_report"](value, 2 if incomplete else 0) == value
    assert data["ALLOWED_LIMITS"] == LIMITS


@pytest.mark.parametrize("defect", ["schema-bool", "count-bool", "empty-limits", "duplicate-limits",
    "unknown-limit", "status", "empirical", "extra", "missing", "unsorted", "exit", "nan"])
def test_continuity_result_never_trusts_flags_or_unknown_capabilities(data, defect):
    value, code = report(incomplete=True), 2
    if defect == "schema-bool": value["schema"] = True
    elif defect == "count-bool": value["counts"]["artifacts"] = True
    elif defect == "empty-limits": value["limitations"] = []
    elif defect == "duplicate-limits": value["limitations"] *= 2
    elif defect == "unknown-limit": value["limitations"] = ["d2-unrecognized-artifact-schema"]
    elif defect == "status": value["status"] = "verified"
    elif defect == "empirical": value["empirical_approval_verified"] = 0
    elif defect == "extra": value["trusted"] = True
    elif defect == "missing": value.pop("active_manifest")
    elif defect == "unsorted": value["limitations"] = sorted(LIMITS, reverse=True)
    elif defect == "exit": code = 124
    else: value["active_slot_count"] = float("nan")
    with pytest.raises(ValueError):
        data["validate_report"](value, code)


@pytest.mark.parametrize("text,expected", [(b"API_KEY=opaque\n", None),
    (b"# comment\nBETBOY_RUNTIME_STATE_DIR=/opt/betboy/app/state\n", "/opt/betboy/app/state"),
    (b'BETBOY_RUNTIME_STATE_DIR="/opt/betboy/app/state space"\n', "/opt/betboy/app/state space"),
    (b"BETBOY_RUNTIME_STATE_DIR=\n", None)])
def test_closed_environment_records(data, text, expected):
    assert data["runtime_override"](text) == expected


@pytest.mark.parametrize("text", [b"BETBOY_RUNTIME_STATE_DIR=/a\nBETBOY_RUNTIME_STATE_DIR=/b\n",
    b"OTHER='multiline\nBETBOY_RUNTIME_STATE_DIR=/hidden\n'\n", b"export BETBOY_RUNTIME_STATE_DIR=/a\n",
    b"BETBOY_RUNTIME_STATE_DIR=/a\\\n/b\n", b"BETBOY_RUNTIME_STATE_DIR=/a\x00\n"])
def test_ambiguous_environment_never_becomes_a_guessed_path(data, text):
    with pytest.raises(ValueError):
        data["runtime_override"](text)


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
@pytest.mark.parametrize("position", ["value", "quoted", "comment"])
def test_environment_unicode_record_separators_never_invent_assignments(data, separator, position):
    suffix = separator + "BETBOY_RUNTIME_STATE_DIR=/opt/betboy/app/custom"
    record = {"value": "OTHER=opaque" + suffix,
              "quoted": 'OTHER="opaque' + suffix + '"',
              "comment": "# opaque" + suffix}[position]
    with pytest.raises(ValueError):
        data["runtime_override"]((record + "\n").encode())


@pytest.mark.parametrize("space", ["\u00a0", "\u2003", "\u202f"])
def test_unicode_whitespace_is_not_environment_name_syntax(data, space):
    with pytest.raises(ValueError):
        data["runtime_override"]((space + "BETBOY_RUNTIME_STATE_DIR=/opt/betboy/app/custom\n").encode())


@pytest.mark.parametrize("space", ["\u00a0", "\u2003", "\u202f"])
@pytest.mark.parametrize("quote", ["", "'", '"'])
@pytest.mark.parametrize("side", ["before", "after"])
def test_selected_runtime_value_never_normalizes_unicode_path_edges(data, space, quote, side):
    path = "/opt/betboy/app/custom"
    value = space + path if side == "before" else path + space
    with pytest.raises(ValueError):
        data["runtime_override"](("BETBOY_RUNTIME_STATE_DIR=" + quote + value + quote + "\n").encode())


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("quote", ["", "'", '"'])
def test_real_ascii_boundaries_and_ordinary_unicode_values_remain_exact(data, ending, quote):
    # OTHER remains opaque, including inner/edge Unicode spaces. Only the
    # selected path is inspected; letters and interior spaces are not rewritten.
    records = ["\t# comment", "OTHER=\u00a0Zürich\u2003value\u202f", "\tBETBOY_RUNTIME_STATE_DIR="
               + quote + "/opt/betboy/app/Zürich\u00a0state" + quote + " \t"]
    assert data["runtime_override"]((ending.join(records) + ending).encode()) == "/opt/betboy/app/Zürich\u00a0state"


def bash():
    result = shutil.which("bash")
    if not result:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        result = str(candidate) if candidate.is_file() else None
    assert result, "A real Bash is required; do not turn the orchestration proof into a skip"
    return result


def test_real_shell_executes_hook_between_verified_backup_and_apply():
    # Run the actual main fragment with only external seams replaced by logs.
    source = UPDATER.read_text(encoding="utf-8")
    start = source.index("\ncreate_fresh_backup\n")
    end = source.index("\ngit_betboy update-ref", start)
    fragment = source[start:end]
    harness = """set -euo pipefail
TARGET_MANIFEST=manifest
TARGET_PAYLOAD=payload
create_fresh_backup() { printf 'backup\n'; }
verify_context_runtime_before_update() { printf 'context\n'; }
apply_trusted_payload() { printf 'apply\n'; }
""" + fragment
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["backup", "context", "apply"]


def test_real_shell_context_failure_prevents_apply():
    source = UPDATER.read_text(encoding="utf-8")
    start = source.index("\ncreate_fresh_backup\n")
    end = source.index("\ngit_betboy update-ref", start)
    harness = """set -euo pipefail
TARGET_MANIFEST=manifest
TARGET_PAYLOAD=payload
create_fresh_backup() { printf 'backup\n'; }
verify_context_runtime_before_update() { printf 'context-failed\n'; return 1; }
apply_trusted_payload() { printf 'apply\n'; }
""" + source[start:end]
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode != 0
    assert result.stdout.splitlines() == ["backup", "context-failed"]


@pytest.fixture
def content_data(data, tmp_path):
    """Real bytes/SQLite, with fixture-only ownership emulation (NOT Linux DAC QA).

    No production guard changes on Windows. Root runs the actual Unix owner,
    group, permission and user-switch boundary separately on Linux.
    """
    def fixture_info(path, **_):
        path = Path(path)
        path.absolute().relative_to(tmp_path.absolute())
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        assert not path.is_symlink()
        return info

    def fixture_directory(path, **_):
        path = Path(path)
        path.absolute().relative_to(tmp_path.absolute())
        assert path.is_dir() and not path.is_symlink()
        return path.stat()

    def fixture_write(path, raw, *, mode=0o600, **_):
        fixture_directory(Path(path).parent)
        with Path(path).open("xb") as handle:
            handle.write(raw)
        Path(path).chmod(mode)

    data["file_info"] = fixture_info
    data["directory"] = fixture_directory
    data["sealed_directory"] = fixture_directory
    data["write_new"] = fixture_write
    # Windows fd ctime and named ctime differ; neither proves Unix DAC here.
    if os.name == "nt":
        original = data["signature"]
        data["signature"] = lambda info: original(info)[:-1]
    data["os"] = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    data["os"].chown = lambda *_: None
    data["os"].chmod = lambda path, mode: Path(path).chmod(mode)
    data["os"].fchown = lambda *_: None
    data["os"].fchmod = lambda *_: None
    data["os"].O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
    data["os"].O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
    return data


def backup_fixture(tmp_path, raw=None, *, relative="runtime_state/context_models.db", mutation=None):
    source = tmp_path / "original.db"
    if raw is None:
        connection = sqlite3.connect(source)
        try:
            connection.execute("CREATE TABLE transport(value TEXT)")
            connection.execute("INSERT INTO transport VALUES('real sqlite bytes')")
            connection.commit()
        finally:
            connection.close()
        raw = source.read_bytes()
    entry = {"path": relative, "source_size": len(raw), "backup_size": len(raw),
             "sha256": hashlib.sha256(raw).hexdigest()}
    manifest = {"created_at": "2026-09-09T12:00:00+00:00", "source_head": "a" * 40,
        "database_count": 1, "databases": [entry],
        "integrity_key": {"path": "integrity/challenge-ledger-hmac.key", "sha256": hashlib.sha256(b"test-only").hexdigest()}}
    if mutation:
        mutation(manifest)
    archive = tmp_path / "backup.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("MANIFEST.json", json.dumps(manifest))
        handle.writestr(relative, raw)
        handle.writestr("integrity/challenge-ledger-hmac.key", b"test-only")
    return archive, raw


def test_actual_four_field_backup_inventory_and_single_sqlite_seal(content_data, tmp_path):
    archive, original = backup_fixture(tmp_path)
    copy = tmp_path / "sealed.db"
    result = content_data["extract_and_seal"](archive, "runtime_state/context_models.db", copy,
        source_head="a" * 40, app_gid=1000)
    assert result["member_hash"] == hashlib.sha256(original).hexdigest()
    assert copy.read_bytes()[18:20] == b"\x01\x01"
    with sqlite3.connect(copy) as connection:
        assert connection.execute("SELECT value FROM transport").fetchall() == [("real sqlite bytes",)]


def test_configuration_receipt_passes_its_actual_environment_argument(data, tmp_path):
    value = {"app": "app", "env": "private-env", "target": "target", "previous": "old",
        "app_uid": 1, "app_gid": 2, "target_manifest": "new-manifest", "previous_manifest": "old-manifest",
        "previous_head": "a" * 40, "target_head": "b" * 40, "backup_head": "a" * 40,
        "env_hash": None, "relative": "runtime_state/context_models.db", "legacy": True, "present": False}
    called = []
    def configured(*, env_path, **kwargs):
        called.append((env_path, kwargs))
        return value
    data["read_file"] = lambda *_, **__: json.dumps(value).encode()
    data["configuration"] = configured
    assert data["load_config"](tmp_path) == value
    assert called[0][0] == "private-env"


@pytest.mark.parametrize("resuming", [False, True])
def test_actual_preflight_keeps_manifest_ancestor_separate_from_backup_head(tmp_path, resuming):
    # Existing resume means current Git HEAD is already TARGET, but the saved
    # previous payload remains marker.previous. Neither identity may be guessed.
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
STAGE_DIR=stage; APP_DIR=app; TARGET_PAYLOAD=target; PREVIOUS_PAYLOAD=previous
TARGET_MANIFEST=target-manifest; PREVIOUS_MANIFEST=previous-manifest
PREVIOUS_HEAD=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
TARGET_HEAD=cccccccccccccccccccccccccccccccccccccccc
MIGRATION_MARKER_PREVIOUS_HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
VENV_DIR=venv
target_payload_file() { printf 'entry\n'; }
id() { printf '1000\n'; }
context_hook_data() { printf '%s\n' "$*"; }
context_hook_command() { cat >/dev/null; CONTEXT_COMMAND_STATUS=0; }
""" + f"MIGRATION_RESUME_TARGET={int(resuming)}\n" + shell_function("configure_context_phase") + "\nconfigure_context_phase private/online\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    args = result.stdout.splitlines()[0].split()
    expected_code = ("a" if resuming else "b") * 40
    assert args[7:10] == [expected_code, "c" * 40, "b" * 40]


@pytest.mark.parametrize("limitation", sorted(LIMITS))
def test_each_explicit_reviewed_limitation_is_continuity_only(data, limitation):
    value = report(incomplete=True)
    value["limitations"] = [limitation]
    assert data["validate_report"](value, 2)["empirical_approval_verified"] is False


@pytest.mark.parametrize("limitation", ["unrecognized-artifact-schema", "d2-unrecognized-schema",
    "schema-unavailable", "opening-semantics-unavailable", "d3-owning-source-feature-replay-unavailable ",
    "d2-final-source-replay-not-opened\n", "", "trusted", None, True, {}])
def test_unknown_lookalike_or_malformed_limitation_is_not_allowed(data, limitation):
    value = report(incomplete=True)
    value["limitations"] = [limitation]
    with pytest.raises(ValueError):
        data["validate_report"](value, 2)


@pytest.mark.parametrize("body", [b'{"schema":1,"schema":1}', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":-Infinity}', b'{"x":0} trailing', b'{"x":"\xff"}'])
def test_json_reader_rejects_duplicate_keys_and_extra_nonfinite_data(data, body):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        data["decode"](body)


@pytest.mark.parametrize("relative", ["/absolute/context_models.db", "../context_models.db",
    "state/../context_models.db", "state//context_models.db", "state/./context_models.db",
    "state\\context_models.db", "C:/context_models.db", ".git/context_models.db",
    "runtime_state/.venv/context_models.db", "state/x\x00.db", ""])
def test_backup_member_paths_never_escape_existing_scope(data, relative):
    with pytest.raises(ValueError):
        data["relative_name"](relative)


@pytest.mark.parametrize("defect", ["source-head", "source-size-bool", "backup-size-bool", "backup-size",
    "missing-size", "extra-entry", "hash", "count-bool", "count", "duplicate-entry", "key-path"])
def test_genuine_archive_rejects_inconsistent_inventory_before_new_copy(content_data, tmp_path, defect):
    def mutation(value):
        entry = value["databases"][0]
        if defect == "source-head": value["source_head"] = "b" * 40
        elif defect == "source-size-bool": entry["source_size"] = True
        elif defect == "backup-size-bool": entry["backup_size"] = False
        elif defect == "backup-size": entry["backup_size"] += 1
        elif defect == "missing-size": entry.pop("source_size")
        elif defect == "extra-entry": entry["trusted"] = True
        elif defect == "hash": entry["sha256"] = "f" * 64
        elif defect == "count-bool": value["database_count"] = True
        elif defect == "count": value["database_count"] = 2
        elif defect == "duplicate-entry": value["databases"] *= 2; value["database_count"] = 2
        else: value["integrity_key"]["path"] = "integrity/other-key"
    archive, _ = backup_fixture(tmp_path, mutation=mutation)
    target = tmp_path / "copy.db"
    with pytest.raises(ValueError):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", target,
            source_head="a" * 40, app_gid=1000)
    if defect == "hash":
        # Streaming cannot know the digest before writing its private 0600
        # candidate. It must fail before sealing/reporting that candidate.
        assert target.exists()
    else:
        assert not target.exists()


@pytest.mark.parametrize("defect", ["duplicate-member", "traversal", "symlink", "unmanifested"])
def test_archive_member_identity_is_checked_before_database_read(content_data, tmp_path, defect):
    archive, _ = backup_fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as handle:
        if defect == "duplicate-member":
            with pytest.warns(UserWarning, match="Duplicate"):
                handle.writestr("MANIFEST.json", b"{}")
        elif defect == "traversal": handle.writestr("../outside.db", b"x")
        elif defect == "unmanifested": handle.writestr("other.db", b"x")
        else:
            entry = zipfile.ZipInfo("alias.db")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            handle.writestr(entry, b"runtime_state/context_models.db")
    with pytest.raises(ValueError):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "copy.db",
            source_head="a" * 40, app_gid=1000)
    assert not (tmp_path / "copy.db").exists()


def test_single_member_read_never_opens_key_or_other_databases(content_data, tmp_path, monkeypatch):
    archive, _ = backup_fixture(tmp_path)
    opened = []
    original = zipfile.ZipFile.open
    def checked(handle, name, *args, **kwargs):
        member = name.filename if isinstance(name, zipfile.ZipInfo) else name
        opened.append(member)
        assert member in {"MANIFEST.json", "runtime_state/context_models.db"}
        return original(handle, name, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, "open", checked)
    content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "copy.db",
        source_head="a" * 40, app_gid=1000)
    assert opened == ["MANIFEST.json", "runtime_state/context_models.db"]


def test_absence_does_not_create_sqlite_and_is_not_itself_legacy_authority(content_data, tmp_path):
    archive, _ = backup_fixture(tmp_path, relative="other.db")
    target = tmp_path / "copy.db"
    content_data["sqlite3"] = SimpleNamespace(connect=lambda *_a, **_k: pytest.fail("SQLite opened for absence"))
    result = content_data["extract_and_seal"](archive, "runtime_state/context_models.db", target,
        source_head="a" * 40, app_gid=1000)
    assert result["member_hash"] is None and not target.exists()
    assert "legacy" not in result


@pytest.mark.parametrize("failure", ["seal", "quick-check"])
def test_failed_snapshot_seal_always_closes_only_its_own_connection(content_data, tmp_path, failure):
    archive, _ = backup_fixture(tmp_path)
    closed, sql = [], []
    class FailedConnection:
        def execute(self, command):
            sql.append(command)
            if (failure == "seal" and "journal_mode" in command) or (failure == "quick-check" and "quick_check" in command):
                raise sqlite3.DatabaseError("fixture error")
            return SimpleNamespace(fetchone=lambda: ("delete",))
        def close(self): closed.append(True)
    opened = []
    def connect(path, **kwargs):
        opened.append((path, kwargs))
        return FailedConnection()
    content_data["sqlite3"] = SimpleNamespace(connect=connect)
    target = tmp_path / "copy.db"
    with pytest.raises(sqlite3.DatabaseError):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", target,
            source_head="a" * 40, app_gid=1000)
    assert closed == [True]
    assert opened == [(target.as_uri() + "?mode=rw", {"uri": True, "timeout": 30})]


def test_wal_online_backup_then_real_delete_seal_and_actual_cli_preserves_tours(content_data, tmp_path):
    from tests.test_context_runtime_backup import seeded, add_receipt, stored_rows
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    source = root / "live.db"
    first, atp, wta = seeded(source)
    reader = sqlite3.connect(source)
    keeper = sqlite3.connect(source)
    image = root / "image.db"
    try:
        assert keeper.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint=0")
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM artifacts").fetchone()
        receipt = add_receipt(source, revision="new-receipt-in-real-wal")
        with closing(sqlite3.connect(image)) as copy:
            keeper.backup(copy)
        raw = image.read_bytes()
        assert raw[18:20] == b"\x02\x02"
        before = {suffix: Path(str(source) + suffix).read_bytes() for suffix in ("", "-wal", "-shm")}
        archive, _ = backup_fixture(root, raw)
        archive_before = archive.read_bytes()
        target = root / "sealed.db"
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", target,
            source_head="a" * 40, app_gid=1000)
        assert {suffix: Path(str(source) + suffix).read_bytes() for suffix in before} == before
        assert archive.read_bytes() == archive_before
        assert target.read_bytes()[18:20] == b"\x01\x01"
        assert not any(Path(str(target) + suffix).exists() for suffix in ("-wal", "-shm", "-journal"))
        tables = ("artifacts", "manifests", "context_contents", "context_observations")
        for table in tables:
            assert stored_rows(target, table) == stored_rows(source, table)
        assert receipt in {row[0] for row in stored_rows(target, "context_observations")}
        # Actual CLI subprocess, no fixture replacement of the D4 verifier.
        target.chmod(0o600)
        target_before = target.read_bytes()
        result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/verify_context_runtime.py"),
            "--database", str(target)], capture_output=True, text=True, cwd=ROOT, timeout=90)
        value = content_data["validate_report"](json.loads(result.stdout), result.returncode)
        assert value["active_manifest"] == first
        assert value["tour_states"] == {"ATP": atp, "WTA": wta}
        assert value["counts"]["observations"] == 1
        assert target.read_bytes() == target_before
    finally:
        reader.close()
        keeper.close()


@pytest.mark.parametrize("exit_code", [0, 1, 2, 124, 137])
def test_real_shell_capture_preserves_child_exit_and_privilege_arguments(tmp_path, exit_code):
    output = tmp_path / "captured.txt"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c",
        f"import sys; print('fixture-only'); sys.exit({exit_code})"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf '%s\n' "$*" >&2; exit 1; }
# Intercept only Unix account/timeout transport on this Windows-capable host.
# Execute the actual child and actual pipeline; Unix DAC is separate Linux QA.
as_betboy() { printf '%s|' "$@" >&3; shift 13; "$@"; }
exec 3>&2
""" + shell_function("context_hook_command") + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\nprintf '%s\\n' \"$CONTEXT_COMMAND_STATUS\"\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    if exit_code in {124, 137}:
        assert result.returncode != 0 and "VerificationResourceError" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(exit_code)
    assert output.read_bytes() == b"fixture-only\r\n" if os.name == "nt" else output.read_bytes() == b"fixture-only\n"
    assert result.stderr.startswith("/usr/bin/env|-i|PATH=/usr/bin:/bin|LANG=C.UTF-8|OMP_NUM_THREADS=1|OPENBLAS_NUM_THREADS=1|MKL_NUM_THREADS=1|NUMEXPR_NUM_THREADS=1|VECLIB_MAXIMUM_THREADS=1|/usr/bin/timeout|--signal=TERM|--kill-after=10s|600s|")
    assert "|-I|-B|-c|" in result.stderr


def test_root_inline_program_imports_only_stdlib_and_never_backup_helpers(data):
    source = shell_function("context_hook_data")
    begin = source.index("<<'PY'\n") + len("<<'PY'\n")
    tree = ast.parse(source[begin:source.index("\nPY", begin)])
    imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"hashlib", "json", "os", "pathlib", "re", "sqlite3", "stat", "sys", "zipfile", "shutil", "tempfile", "resource", "time"}
    assert "extractall" not in source and "importlib" not in source and "pickle" not in source
    assert "betboy-backup" not in shell_function("context_hook_command")
    for file, expected in {
        "scripts/stage_runtime_databases.py": "1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026",
        "deploy/systemd/betboy-backup.service": "922352a5d3c883cc671da419c5d3fa589cbe9cd025f32d4c4d9f7b6a9648edb8",
    }.items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == expected


def test_actual_a1_slot_aliases_are_not_misclassified_as_report_corruption(data, tmp_path):
    from model_artifacts import publish_slots
    from tests.test_context_runtime_backup import put_tour, NOW
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    database = root / "context_models.db"
    ref = put_tour(database, "ATP")
    publish_slots(database, {"tennis:ATP": ref, "retained-atp-alias": ref}, expected_manifest=None, published_at=NOW)
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/verify_context_runtime.py"),
        "--database", str(database)], capture_output=True, text=True, cwd=ROOT, timeout=90)
    assert result.returncode == 0, result.stdout
    value = json.loads(result.stdout)
    assert value["active_slot_count"] == 2 and value["counts"]["artifacts"] == 1
    assert data["validate_report"](value, 0) == value


@pytest.mark.parametrize("override,expected", [(None, "runtime_state/context_models.db"),
    ("/opt/betboy/app", "context_models.db"), ("/opt/betboy/app/custom state", "custom state/context_models.db")])
def test_closed_runtime_path_matches_actual_known_resolver(data, override, expected):
    assert data["runtime_relative"]("/opt/betboy/app", override) == expected
    normalized = (ROOT / "runtime_paths.py").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == data["PATH_CONTRACT"]


@pytest.mark.parametrize("override", ["relative", "~/state", "/var/lib/betboy/state",
    "/opt/betboy/application", "/opt/betboy/app/../state", "/opt/betboy/app//state",
    "/opt/betboy/app/state/", "/opt/betboy/app/.git", "/opt/betboy/app/backups_runtime",
    "//opt/betboy/app/state", "/opt/betboy/app/state\x00", "/opt/betboy/app/a\\b"])
def test_runtime_override_outside_backup_or_ambiguous_is_not_silently_relocated(data, override):
    with pytest.raises(ValueError):
        data["runtime_relative"]("/opt/betboy/app", override)


def configuration_fixture(data, tmp_path, *, legacy=True, present=False, extra_previous=None, env=None):
    """Actual staged bytes, known code pin, exact manifests; Unix DAC emulated."""
    app, target, old = (tmp_path / name for name in ("app", "target", "previous"))
    for directory in (app, target, old): directory.mkdir(mode=0o700)
    units = {p.relative_to(ROOT).as_posix(): p.read_bytes()
             for p in (ROOT / "deploy/systemd").glob("betboy-*.service") if p.name != "betboy-backup.service"}
    new_files = {**units, "runtime_paths.py": (ROOT / "runtime_paths.py").read_bytes(),
                 "scripts/verify_context_runtime.py": (ROOT / "scripts/verify_context_runtime.py").read_bytes()}
    previous_files = {**units, "runtime_paths.py": b"# proved fixture predecessor without a context contract\n"}
    if not legacy:
        previous_files.update({"runtime_paths.py": new_files["runtime_paths.py"], "model_artifacts.py": b"# fixture known context persistence\n"})
    if extra_previous: previous_files.update(extra_previous)
    manifests = []
    for tree, files, revision in ((target, new_files, "b" * 40), (old, previous_files, "a" * 40)):
        for name, raw in files.items():
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        manifest = tmp_path / (tree.name + ".json")
        manifest.write_text(json.dumps({"revision": revision, "must_be_absent": [],
            "files": {name: {"mode": "100644", "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in files.items()}}))
        manifests.append(manifest)
    env_path = tmp_path / "env"
    if env is not None: env_path.write_bytes(env)
    original_route = data["runtime_relative"]
    def virtual_fixture_route(root, override):
        assert root == app.as_posix()
        return original_route("/opt/betboy/app", override)
    data["runtime_relative"] = virtual_fixture_route
    if present:
        relative = original_route("/opt/betboy/app", data["runtime_override"](env or b""))
        (app / relative).parent.mkdir(parents=True, exist_ok=True)
        (app / relative).write_bytes(b"present is not yet a SQLite or semantic verification")
    arguments = dict(app=app, env_path=env_path, target=target, previous=old, app_uid=1000, app_gid=1000,
        target_manifest=manifests[0], previous_manifest=manifests[1], previous_head="a" * 40,
        target_head="b" * 40, backup_head="c" * 40)
    return arguments


@pytest.mark.parametrize("legacy,present,valid", [(True, False, True), (True, True, True),
    (False, True, True), (False, False, False)])
def test_first_transition_legacy_is_code_proof_plus_presence_not_missing_module_guess(content_data, tmp_path, legacy, present, valid):
    args = configuration_fixture(content_data, tmp_path, legacy=legacy, present=present)
    if valid:
        value = content_data["configuration"](**args)
        assert value["legacy"] is legacy and value["present"] is present
        assert value["relative"] == "runtime_state/context_models.db"
        assert value["previous_head"] == "a" * 40 and value["backup_head"] == "c" * 40
    else:
        with pytest.raises(ValueError, match="context-capable"):
            content_data["configuration"](**args)


@pytest.mark.parametrize("name", ["model_artifacts.py", "context_observations.py", "context_snapshots.py",
    "context_runtime.py", "context_runtime_semantics.py", "context_models/__init__.py",
    "context_sources/football.py", "context_transport.py", "tennis/tour_state.py", "scripts/verify_context_runtime.py"])
def test_partial_legacy_context_code_is_not_absence_authority(content_data, tmp_path, name):
    args = configuration_fixture(content_data, tmp_path, extra_previous={name: b"# partial code\n"})
    with pytest.raises(ValueError, match="partial legacy"):
        content_data["configuration"](**args)


@pytest.mark.parametrize("mutation", ["missing", "extra", "modified", "revision", "unreviewed-path-code", "extra-env-route"])
def test_target_entire_module_graph_and_known_path_contract_are_rechecked(content_data, tmp_path, mutation):
    args = configuration_fixture(content_data, tmp_path)
    target, manifest = args["target"], args["target_manifest"]
    value = json.loads(manifest.read_text())
    if mutation == "missing": (target / "runtime_paths.py").unlink()
    elif mutation == "extra": (target / "unmanifested_import.py").write_text("# extra")
    elif mutation == "modified": (target / "runtime_paths.py").write_text("# different")
    elif mutation == "revision": value["revision"] = "c" * 40
    else:
        name = "runtime_paths.py" if mutation == "unreviewed-path-code" else "deploy/systemd/betboy-app.service"
        extra = b"\n# changed owning runtime contract\n" if mutation == "unreviewed-path-code" else b"EnvironmentFile=/unreviewed/env\n"
        raw = (target / name).read_bytes() + extra
        (target / name).write_bytes(raw)
        value["files"][name]["sha256"] = hashlib.sha256(raw).hexdigest()
    manifest.write_text(json.dumps(value))
    with pytest.raises((ValueError, FileNotFoundError)):
        content_data["configuration"](**args)


def test_real_configuration_receipt_rereads_env_and_cannot_backfill_presence(content_data, tmp_path):
    args = configuration_fixture(content_data, tmp_path, env=b"API_KEY=opaque\n")
    value = content_data["configuration"](**args)
    hook = tmp_path / "hook"
    hook.mkdir()
    (hook / "config.json").write_text(json.dumps(value))
    assert content_data["load_config"](hook) == value
    args["env_path"].write_bytes(b"API_KEY=different-opaque\n")
    with pytest.raises(ValueError, match="changed across downtime"):
        content_data["load_config"](hook)


def test_newly_missing_database_does_not_reuse_earlier_present_receipt(content_data, tmp_path):
    args = configuration_fixture(content_data, tmp_path, present=True)
    value = content_data["configuration"](**args)
    hook = tmp_path / "hook"
    hook.mkdir()
    (hook / "config.json").write_text(json.dumps(value))
    (args["app"] / value["relative"]).unlink()
    with pytest.raises(ValueError, match="changed across downtime"):
        content_data["load_config"](hook)


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_orphaned_runtime_companion_never_becomes_legacy_absence(content_data, tmp_path, suffix):
    args = configuration_fixture(content_data, tmp_path)
    (args["app"] / "runtime_state").mkdir()
    (args["app"] / ("runtime_state/context_models.db" + suffix)).write_bytes(b"")
    with pytest.raises(ValueError, match="sidecars without"):
        content_data["configuration"](**args)


@pytest.mark.parametrize("line", [b"  Environment = BETBOY_RUNTIME_STATE_DIR=/outside\n",
    b"\tEnvironmentFile=/different.env\n", b"PassEnvironment = BETBOY_RUNTIME_STATE_DIR\n",
    b"UnsetEnvironment = BETBOY_RUNTIME_STATE_DIR\n", b"Environment=OTHER=x\\\nBETBOY_RUNTIME_STATE_DIR=/outside\n"])
def test_unit_environment_ambiguity_is_not_ignored_despite_valid_source_hash(content_data, tmp_path, line):
    args = configuration_fixture(content_data, tmp_path)
    name = "deploy/systemd/betboy-app.service"
    target = args["target"] / name
    original = target.read_bytes()
    assert b"[Service]\n" in original
    target.write_bytes(original.replace(b"[Service]\n", b"[Service]\n" + line, 1))
    manifest = json.loads(args["target_manifest"].read_text())
    manifest["files"][name]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    args["target_manifest"].write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        content_data["configuration"](**args)


@pytest.mark.parametrize("replacement", [
    space + "EnvironmentFile=-/etc/betboy/betboy.env" for space in ("\u00a0", "\u2003", "\u202f")
] + [
    "EnvironmentFile=" + space + "-/etc/betboy/betboy.env" for space in ("\u00a0", "\u2003", "\u202f")
] + [
    "# ignored" + separator + "EnvironmentFile=-/etc/betboy/betboy.env" for separator in ("\x85", "\u2028", "\u2029")
])
def test_unit_record_syntax_does_not_normalize_unicode(content_data, tmp_path, replacement):
    args = configuration_fixture(content_data, tmp_path)
    name = "deploy/systemd/betboy-app.service"
    target = args["target"] / name
    old = b"EnvironmentFile=-/etc/betboy/betboy.env"
    assert old in target.read_bytes()
    target.write_bytes(target.read_bytes().replace(old, replacement.encode(), 1))
    manifest = json.loads(args["target_manifest"].read_text())
    manifest["files"][name]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    args["target_manifest"].write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        content_data["configuration"](**args)


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r"])
def test_unit_record_ascii_boundaries_keep_the_exact_environment_route(content_data, tmp_path, ending):
    args = configuration_fixture(content_data, tmp_path)
    name = "deploy/systemd/betboy-app.service"
    target = args["target"] / name
    raw = target.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", ending)
    target.write_bytes(raw)
    manifest = json.loads(args["target_manifest"].read_text())
    manifest["files"][name]["sha256"] = hashlib.sha256(raw).hexdigest()
    args["target_manifest"].write_text(json.dumps(manifest))
    assert content_data["configuration"](**args)["relative"] == "runtime_state/context_models.db"


def verified_context_fixture_archive(tmp_path, image, monkeypatch):
    """Real whole-archive decisions; Windows close seam is not a DAC proof."""
    key = b"a1" * 32 + b"\n"  # Syntactically valid synthetic key; no real secret.
    member = "runtime_state/context_models.db"
    manifest = {"created_at": "2026-09-09T12:00:00+00:00", "source_head": "a" * 40,
        "database_count": 1,
        "databases": [{"path": member, "source_size": len(image), "backup_size": len(image),
                       "sha256": hashlib.sha256(image).hexdigest()}],
        "integrity_key": {"path": "integrity/challenge-ledger-hmac.key", "sha256": hashlib.sha256(key).hexdigest()}}
    archive = tmp_path / "fully-verified.zip"
    with zipfile.ZipFile(archive, "x") as handle:
        handle.writestr("MANIFEST.json", json.dumps(manifest))
        handle.writestr(member, image)
        handle.writestr("integrity/challenge-ledger-hmac.key", key)
    source = shell_function("verify_backup_archive")
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    program = source[start:source.index("\nPY", start)]
    connect = sqlite3.connect

    class ClosingConnection(sqlite3.Connection):
        def __exit__(self, *args):
            try:
                return super().__exit__(*args)
            finally:
                self.close()

    def close_on_exit(*args, **kwargs):
        kwargs["factory"] = ClosingConnection
        return connect(*args, **kwargs)

    with monkeypatch.context() as scoped:
        # The old verifier's `with Connection` otherwise leaves an open handle
        # at TemporaryDirectory unlink on Windows. All SQL/decisions stay real.
        if os.name == "nt":
            scoped.setattr(sqlite3, "connect", close_on_exit)
            scoped.setitem(sys.modules, "resource", SimpleNamespace(RLIMIT_AS=9, RLIMIT_CPU=0, setrlimit=lambda *_: None))
        scoped.setattr(sys, "argv", ["fixture-full-verify", str(archive)])
        exec(compile(program, str(UPDATER) + "::verify_backup_archive", "exec"), {"__name__": "fixture_full_backup"})
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/backup_runtime_databases.py"),
        "--verify-only", str(archive), "--recovery-mode"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return archive


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
def test_fully_verified_backup_and_failed_d4_cannot_turn_into_legacy_absence(content_data, tmp_path, monkeypatch, capsys, separator):
    from tests.test_context_runtime_backup import seeded
    raw_env = ("OTHER=opaque" + separator + "BETBOY_RUNTIME_STATE_DIR=/opt/betboy/app/custom\n").encode()
    args = configuration_fixture(content_data, tmp_path, env=raw_env)
    args["backup_head"] = "a" * 40
    live = args["app"] / "runtime_state/context_models.db"
    live.parent.mkdir(mode=0o700)
    _, atp, _ = seeded(live)
    with closing(sqlite3.connect(live)) as connection:
        connection.execute("DELETE FROM artifacts WHERE digest=?", (atp,))
        connection.commit()
        connection.execute("PRAGMA journal_mode=DELETE")
    image = live.read_bytes()
    archive = verified_context_fixture_archive(tmp_path, image, monkeypatch)
    child = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/verify_context_runtime.py"),
        "--database", str(live)], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert child.returncode == 1 and json.loads(child.stdout)["status"] == "failed"
    archive_before = archive.read_bytes()
    capsys.readouterr()
    with pytest.raises(ValueError):
        content_data["configuration"](**args)
    assert capsys.readouterr().out == ""
    assert live.read_bytes() == image and archive.read_bytes() == archive_before


def prepared_stage(data, tmp_path, *, absent=False):
    args = configuration_fixture(data, tmp_path, present=not absent)
    # The current preupdate source HEAD is independently bound to the archive.
    args["backup_head"] = "a" * 40
    archive, raw = backup_fixture(tmp_path, relative="other.db" if absent else "runtime_state/context_models.db")
    if not absent:
        (args["app"] / "runtime_state/context_models.db").write_bytes(raw)
    value = data["configuration"](**args)
    hook = tmp_path / "hook"
    hook.mkdir(mode=0o700)
    (hook / "config.json").write_text(json.dumps(value))
    data["os"].geteuid = lambda: 0  # ONLY test principal emulation; no Unix-DAC claim.
    data["main"](["stage", str(hook), str(archive)])
    return hook, args, archive


@pytest.mark.parametrize("incomplete", [False, True])
def test_actual_stage_and_finish_recheck_every_source_then_allow_only_continuity(content_data, tmp_path, capsys, incomplete):
    hook, args, archive = prepared_stage(content_data, tmp_path)
    assert capsys.readouterr().out == "present\n"
    before = {path: path.read_bytes() for path in (archive, hook / "context_models.db", args["app"] / "runtime_state/context_models.db")}
    (hook / "report.json").write_text(json.dumps(report(incomplete=incomplete)))
    content_data["main"](["finish", str(hook), "2" if incomplete else "0"])
    assert capsys.readouterr().out == "Context continuity: " + ("transport_only" if incomplete else "structural") + "; no model/effect certification.\n"
    assert {path: path.read_bytes() for path in before} == before


def test_actual_missing_legacy_stage_and_finish_need_no_cli_or_created_database(content_data, tmp_path, capsys):
    hook, _, _ = prepared_stage(content_data, tmp_path, absent=True)
    assert capsys.readouterr().out == "not_present_legacy\n"
    content_data["main"](["finish", str(hook), "0"])
    assert capsys.readouterr().out == "Context continuity: not_present_legacy; no model/effect certification.\n"
    assert not (hook / "context_models.db").exists()
    assert not (hook / "report.json").exists()


@pytest.mark.parametrize("mutate", ["archive", "source", "copy", "wal", "shm", "journal", "env",
    "target", "presence", "report-duplicate", "report-too-large", "report-empty", "exit-one", "timeout", "claim-absence"])
def test_post_verifier_mutation_or_failure_never_reaches_continuity_log(content_data, tmp_path, capsys, mutate):
    hook, args, archive = prepared_stage(content_data, tmp_path)
    assert capsys.readouterr().out == "present\n"
    output = hook / "report.json"
    output.write_text(json.dumps(report()))
    code = "0"
    if mutate == "archive":
        with archive.open("ab") as handle: handle.write(b"post-read change")
    elif mutate == "source":
        with (args["app"] / "runtime_state/context_models.db").open("ab") as handle: handle.write(b"changed")
    elif mutate == "copy":
        target = hook / "context_models.db"
        target.chmod(0o600)
        with target.open("ab") as handle: handle.write(b"changed")
    elif mutate in {"wal", "shm", "journal"}: (hook / ("context_models.db-" + mutate)).write_bytes(b"")
    elif mutate == "env": args["env_path"].write_bytes(b"API_KEY=changed-but-not-disclosed\n")
    elif mutate == "target": (args["target"] / "runtime_paths.py").write_bytes(b"changed code")
    elif mutate == "presence": (args["app"] / "runtime_state/context_models.db").unlink()
    elif mutate == "report-duplicate": output.write_text('{"status":"verified","status":"verified"}')
    elif mutate == "report-too-large": output.write_bytes(b" " * (1024 * 1024 + 1))
    elif mutate == "report-empty": output.write_bytes(b"")
    elif mutate == "exit-one": code = "1"
    elif mutate == "timeout": code = "124"
    else:
        proof = json.loads((hook / "stage.json").read_text())
        proof["member_hash"] = None
        (hook / "stage.json").write_text(json.dumps(proof))
    with pytest.raises((ValueError, FileNotFoundError)):
        content_data["main"](["finish", str(hook), code])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("live,backup", [(True, False), (False, True)])
def test_actual_stage_cannot_accept_live_archive_presence_disagreement(content_data, tmp_path, live, backup):
    args = configuration_fixture(content_data, tmp_path, present=live)
    args["backup_head"] = "a" * 40
    archive, raw = backup_fixture(tmp_path, relative="runtime_state/context_models.db" if backup else "other.db")
    hook = tmp_path / "hook"
    hook.mkdir()
    (hook / "config.json").write_text(json.dumps(content_data["configuration"](**args)))
    content_data["os"].geteuid = lambda: 0
    with pytest.raises(ValueError, match="presence differs"):
        content_data["main"](["stage", str(hook), str(archive)])
    assert not (hook / "stage.json").exists()


@pytest.mark.parametrize("presence", ["present", "not_present_legacy", "unknown", "failed-stage"])
def test_real_shell_post_backup_route_and_process_checks(tmp_path, presence):
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
STAGE_DIR=stage; CONTEXT_STAGE_DIR=private; FRESH_BACKUP=private-archive; VENV_DIR=venv; TARGET_PAYLOAD=target
die() { printf 'rejected\n'; exit 1; }
verify_no_betboy_processes() { printf 'process-check\n'; }
target_payload_file() { printf 'root-staged-cli\n'; }
context_hook_command() { printf 'app-user-command:%s\n' "$*"; CONTEXT_COMMAND_STATUS=2; }
configure_context_phase() { :; }
verification_launcher_source() { :; }
"""
    stage = "return 1" if presence == "failed-stage" else "printf '%s\\n' " + shlex.quote(presence)
    harness += "context_hook_data() { if [[ $1 == stage ]]; then " + stage + "; else printf 'finish:%s\\n' \"$*\"; fi; }\n"
    harness += shell_function("verify_context_runtime_before_update") + shell_function("verify_context_runtime_from_archive") + "\nverify_context_runtime_before_update\nprintf 'after-hook\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    lines = result.stdout.splitlines()
    assert lines[0] == "process-check"
    if presence in {"unknown", "failed-stage"}:
        assert result.returncode != 0 and "after-hook" not in lines
        assert not any(line.startswith(("finish:", "app-user-command:")) for line in lines)
    elif presence == "present":
        assert result.returncode == 0, result.stderr
        assert lines[1] == "app-user-command:private/quiesced/report.json /usr/bin/python3 -I -B private/launcher.py d4 target private/quiesced/context_models.db"
        assert lines[2:] == ["process-check", "finish:finish private/quiesced 2 quiesced", "after-hook"]
    else:
        assert result.returncode == 0, result.stderr
        assert lines == ["process-check", "process-check", "finish:finish private/quiesced 0 quiesced", "after-hook"]


def test_real_shell_output_is_bounded_and_already_existing_output_is_never_replaced(tmp_path):
    output = tmp_path / "capture.json"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c",
        "import sys; sys.stdout.write('x' * (1024 * 1024 * 3))"])
    prefix = """set -euo pipefail
PATH=/usr/bin:/bin
die() { exit 1; }
as_betboy() { shift 13; "$@"; }
""" + shell_function("context_hook_command")
    call = f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\n"
    first = subprocess.run([bash()], input=prefix + call, text=True, capture_output=True, timeout=20)
    assert first.returncode != 0
    assert output.stat().st_size == 1024 * 1024 + 1
    before = output.read_bytes()
    second = subprocess.run([bash()], input=prefix + call, text=True, capture_output=True, timeout=20)
    assert second.returncode != 0
    assert output.read_bytes() == before


def test_actual_dependency_python_requires_linux_sealed_capability_before_downtime(data, tmp_path, monkeypatch):
    command, environment, limits = launcher_decision(monkeypatch, ["dependencies", str(ROOT)], uid=1000)
    assert command[:4] == ["/opt/betboy/venv/bin/python", "-I", "-B", "-c"]
    assert limits == [(9, (2147483648, 2147483648)), (0, (300, 300))]
    # Real target imports/SQLite run; Windows must fail this Linux-only probe.
    result = subprocess.run([sys.executable, "-I", "-B", "-c", command[4], str(ROOT)],
        text=True, capture_output=True, cwd=tmp_path, timeout=90)
    if sys.platform == "linux":
        assert result.returncode == 0 and result.stdout == "context-dependencies-v2:ok\n", result.stderr
    else:
        assert result.returncode != 0 and "AssertionError" in result.stderr
    main = UPDATER.read_text().split('preflight "$@"\nremember_unit_state', 1)
    assert len(main) == 2
    assert shell_function("preflight").index("prepare_dependencies") < shell_function("preflight").index("preflight_context_runtime")
    assert main[1].index("systemctl stop") < main[1].index("\ncreate_fresh_backup\n") < main[1].index("\nverify_context_runtime_before_update\n")


@pytest.mark.parametrize("defect", ["unknown-capability", "missing-reference"])
def test_actual_cli_unknown_schema_and_broken_references_cannot_become_allowed_continuity(data, tmp_path, defect):
    from model_artifacts import put_artifact
    from tests.test_context_runtime_backup import seeded, NOW
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    database = root / "context_models.db"
    _, atp, _ = seeded(database)
    if defect == "unknown-capability":
        put_artifact(database, kind="unreviewed-synthetic-context-kind", payload={"never-print-sentinel": True}, created_at=NOW)
    else:
        with closing(sqlite3.connect(database)) as con:
            con.execute("DELETE FROM artifacts WHERE digest=?", (atp,))
            con.commit()
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/verify_context_runtime.py"),
        "--database", str(database)], capture_output=True, text=True, cwd=ROOT, timeout=90)
    assert result.returncode == (2 if defect == "unknown-capability" else 1)
    assert "never-print-sentinel" not in result.stdout + result.stderr
    with pytest.raises(ValueError):
        data["validate_report"](json.loads(result.stdout), result.returncode)


@pytest.mark.parametrize("opaque_report", [False, True])
def test_real_legacy_b3_preserved_but_opaque_experiment_report_stops_update(content_data, tmp_path, opaque_report):
    from tests.test_context_runtime_backup import seeded, put_effect_pair, effect_payload, add_context_snapshot, stored_rows, NOW
    from context_snapshots import compute_once
    from model_artifacts import put_artifact
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    original = root / "original.db"
    seeded(original)
    if opaque_report:
        # Keep the real old opaque fixture intact: it must NOT become allowed.
        effect, _, payload, _ = put_effect_pair(original)
    else:
        # Independently valid orphan effect before an experiment/report exists.
        payload = effect_payload()
        effect = put_artifact(original, kind="context-effect-v1", payload=payload, created_at=NOW)
    key, snapshot = add_context_snapshot(original, effect, payload)
    raw = original.read_bytes()
    archive, _ = backup_fixture(root, raw)
    sealed = root / "sealed.db"
    content_data["extract_and_seal"](archive, "runtime_state/context_models.db", sealed,
        source_head="a" * 40, app_gid=1000)
    before = sealed.read_bytes()
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/verify_context_runtime.py"),
        "--database", str(sealed)], capture_output=True, text=True, cwd=ROOT, timeout=90)
    value = json.loads(result.stdout)
    if opaque_report:
        assert "d2-report-experiment-schema-unavailable" in value["limitations"]
        with pytest.raises(ValueError, match="unreviewed context continuity limitation"):
            content_data["validate_report"](value, result.returncode)
    else:
        assert content_data["validate_report"](value, result.returncode) == value
    assert result.returncode == 2 and value["empirical_approval_verified"] is False
    assert "d3-snapshot-input-binding-unavailable" in value["limitations"]
    assert sealed.read_bytes() == before
    assert stored_rows(sealed, "context_snapshots") == stored_rows(original, "context_snapshots")
    # B3 read invocation opens owning mutable connection, so do it on a separate
    # test restore, never the updater's read-only sealed CLI image.
    restored = root / "b3-owning-copy.db"
    restored.write_bytes(before)
    restored.chmod(0o600)
    assert compute_once(restored, key, lambda: pytest.fail("restored snapshot recomputed")) == snapshot


@pytest.mark.parametrize("defect", ["link", "hardlink", "owner", "group", "world-write", "group-write", "wrong-mode", "directory"])
def test_exact_unix_file_guard_decision_table_without_claiming_windows_dac(data, defect):
    info = SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=0, st_gid=1000, st_nlink=1)
    if defect == "link": info.st_mode = stat.S_IFLNK | 0o440
    elif defect == "hardlink": info.st_nlink = 2
    elif defect == "owner": info.st_uid = 1001
    elif defect == "group": info.st_gid = 1001
    elif defect == "world-write": info.st_mode |= 0o002
    elif defect == "group-write": info.st_mode |= 0o020
    elif defect == "wrong-mode": info.st_mode = stat.S_IFREG | 0o400
    else: info.st_mode = stat.S_IFDIR | 0o440
    data["Path"] = lambda _: SimpleNamespace(parent="private", lstat=lambda: info)
    data["directory"] = lambda *_a, **_k: None
    with pytest.raises(ValueError):
        data["file_info"]("sealed.db", owners={0}, mode=0o440, gid=1000)


@pytest.mark.parametrize("output,code", [(b"context-dependencies-v1:ok\n", "1"), (b"", "0"),
    (b"context-dependencies-v1:ok\nwarning\n", "0"), (b"context-dependencies-v1:ok\n", "124")])
def test_failed_or_noisy_dependency_probe_never_advances_to_downtime(data, output, code):
    data["os"] = SimpleNamespace(geteuid=lambda: 0)
    data["read_file"] = lambda *_a, **_k: output
    with pytest.raises(ValueError):
        data["main"](["dependencies", "fixture-output", code])


def test_one_gib_sealed_cap_applies_before_sealing_or_sqlite_parse(content_data, tmp_path):
    assert content_data["MAX_IMAGE"] == 1024 * 1024 * 1024
    archive, _ = backup_fixture(tmp_path)
    content_data["MAX_IMAGE"] = 100  # Exercise the same branch without a 64 MiB fixture.
    content_data["sqlite3"] = SimpleNamespace(connect=lambda *_a, **_k: pytest.fail("oversized input reached SQLite"))
    with pytest.raises(ValueError, match="bounded SQLite size"):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "copy.db",
            source_head="a" * 40, app_gid=1000)
    assert not (tmp_path / "copy.db").exists()


def test_real_shell_output_collector_has_its_own_time_bound(tmp_path):
    output = tmp_path / "capture.txt"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c", "print('finished')"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { exit 1; }
as_betboy() { shift 13; "$@"; }
/usr/bin/timeout() { printf 'collector:%s\n' "$*" >&3; command /usr/bin/timeout "$@"; }
exec 3>&2
""" + shell_function("context_hook_command") + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stderr == "collector:--signal=TERM --kill-after=10s 610s /usr/bin/head -c 1048577\n"


# Capacity-recovery RED slice. These exercise existing production functions;
# ownership emulation in content_data remains explicitly NOT native DAC proof.
def test_capacity_member_reads_are_at_most_one_mib(content_data, tmp_path, monkeypatch):
    """A whole-member allocation must fail even for a small valid database."""
    archive, raw = backup_fixture(tmp_path)
    actual_read = zipfile.ZipExtFile.read
    member_reads = []

    def bounded_read(handle, size=-1):
        if handle.name == "runtime_state/context_models.db":
            member_reads.append(size)
            assert 0 < size <= 1024 * 1024, "context extraction requested a whole-image read"
        return actual_read(handle, size)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", bounded_read)
    destination = tmp_path / "streamed.db"
    proof = content_data["extract_and_seal"](archive, "runtime_state/context_models.db", destination,
        source_head="a" * 40, app_gid=1000)
    assert member_reads
    assert proof["member_hash"] == hashlib.sha256(raw).hexdigest()
    assert destination.read_bytes() == raw


def test_capacity_valid_65_mib_member_reaches_sealed_copy(content_data, tmp_path):
    """The legacy 64-MiB in-memory cap must not reject the new sealed route."""
    source = tmp_path / "large.db"
    with closing(sqlite3.connect(source)) as connection:
        connection.execute("CREATE TABLE transport(payload BLOB)")
        connection.execute("INSERT INTO transport VALUES(zeroblob(?))", (65 * 1024 * 1024,))
        connection.commit()
        assert connection.execute("PRAGMA quick_check").fetchall() == [("ok",)]
    assert 64 * 1024 * 1024 < source.stat().st_size < 67 * 1024 * 1024
    raw = source.read_bytes()
    archive, _ = backup_fixture(tmp_path, raw)
    destination = tmp_path / "large-sealed.db"
    proof = content_data["extract_and_seal"](archive, "runtime_state/context_models.db", destination,
        source_head="a" * 40, app_gid=1000)
    assert proof["member_hash"] == hashlib.sha256(raw).hexdigest()
    assert destination.stat().st_size == source.stat().st_size
    with closing(sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True)) as connection:
        assert connection.execute("SELECT length(payload) FROM transport").fetchone() == (65 * 1024 * 1024,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)


@pytest.mark.parametrize("phase,accept_commit", [("online", True), ("quiesced", False)])
def test_capacity_phase_distinguishes_real_live_sqlite_commit(content_data, tmp_path, capsys, phase, accept_commit):
    """Only online replay may tolerate a normal commit on the same live inode."""
    args = configuration_fixture(content_data, tmp_path, present=True)
    args["backup_head"] = "a" * 40
    archive, raw = backup_fixture(tmp_path)
    live = args["app"] / "runtime_state/context_models.db"
    live.write_bytes(raw)
    hook = tmp_path / phase
    hook.mkdir()
    (hook / "config.json").write_text(json.dumps(content_data["configuration"](**args)))
    content_data["os"].geteuid = lambda: 0
    content_data["main"](["stage", str(hook), str(archive), phase])
    assert capsys.readouterr().out == "present\n"
    before = live.stat()
    with closing(sqlite3.connect(live)) as connection:
        connection.execute("INSERT INTO transport VALUES('a real commit during target replay')")
        connection.commit()
    assert (live.stat().st_dev, live.stat().st_ino) == (before.st_dev, before.st_ino)
    (hook / "report.json").write_text(json.dumps(report()))
    if accept_commit:
        content_data["authentication_state"] = lambda *_: {"key": "fixture-bound-key", "marker": None}
        (hook / "authentication.json").write_text(json.dumps({"key": "fixture-bound-key", "marker": None}))
        content_data["main"](["finish", str(hook), "0", phase])
        assert capsys.readouterr().out == "Context continuity: structural; no model/effect certification.\n"
    else:
        with pytest.raises(ValueError, match="live source changed"):
            content_data["main"](["finish", str(hook), "0", phase])
        assert capsys.readouterr().out == ""


def test_capacity_unknown_phase_cannot_silently_use_quiesced_finish(content_data, tmp_path, capsys):
    hook, _, _ = prepared_stage(content_data, tmp_path)
    capsys.readouterr()
    (hook / "report.json").write_text(json.dumps(report()))
    with pytest.raises(ValueError):
        content_data["main"](["finish", str(hook), "0", "unreviewed-phase"])
    assert capsys.readouterr().out == ""


def capacity_order_harness(*, online_failure):
    """Run the real hook orchestration/main sequence; fake only host mutations.

    ZIP creation and D4 execution have their own real-byte tests. Here their
    process boundary is recorded so no test can stop this computer's services.
    """
    source = UPDATER.read_text(encoding="utf-8")
    begin = source.index('preflight "$@"\nremember_unit_state')
    end = source.index('\napply_trusted_payload "${TARGET_MANIFEST}" "${TARGET_PAYLOAD}"', begin)
    end = source.index("\n", end + 1)
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
STAGE_DIR=/var/tmp/betboy-update.fixture
CONTEXT_STAGE_DIR=/var/lib/betboy-context-update.fixture
APP_DIR=/fixture/app; VENV_DIR=/fixture/venv
TARGET_PAYLOAD=target; PREVIOUS_PAYLOAD=previous
TARGET_MANIFEST=target-manifest; PREVIOUS_MANIFEST=previous-manifest
PREVIOUS_HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
TARGET_HEAD=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
MIGRATION_MARKER_PREVIOUS_HEAD=cccccccccccccccccccccccccccccccccccccccc
MIGRATION_RESUME_TARGET=0; UPDATE_STARTED=0; FRESH_BACKUP=; PREFLIGHT_BACKUP=
LEDGER_HMAC_KEY=/etc/betboy/challenge-ledger-hmac.key
LEDGER_MIGRATION_MARKER=/etc/betboy/challenge-ledger-v2-migrated.json
BETBOY_TIMERS=(fixture.timer)
die() { printf 'die:%s\n' "$*"; exit 1; }
log() { :; }
id() { printf '1000\n'; }
target_payload_file() { printf '/fixture/target/%s\n' "$1"; }
context_hook_command() { CONTEXT_COMMAND_STATUS=0; }
context_hook_data() {
    case "$1" in
        create-private) printf '/var/lib/betboy-context-update.fixture\n' ;;
        online-auth) printf 'authenticated\n' ;;
        configure) printf 'configure:%s\n' "$*" >&2 ;;
        stage) printf 'stage:%s\n' "$*" >&2; printf 'present\n' ;;
        finish) printf 'finish:%s\n' "$*" >&2 ;;
        dependencies) : ;;
        *) printf 'unexpected-hook:%s\n' "$*" >&2; return 90 ;;
    esac
}
preflight() { preflight_context_runtime; }
remember_unit_state() { printf 'remember\n'; }
snapshot_root_files() { printf 'root-snapshot\n'; }
ensure_backup_principal() { printf 'backup-principal\n'; }
systemctl() { printf 'service:%s\n' "$*"; }
wait_for_workers() { :; }
verify_no_betboy_processes() { :; }
disable_runtime_autostart() { printf 'autostart-write\n'; }
ensure_ledger_hmac_key() { printf 'key-ensure\n'; }
purge_python_caches() { :; }
verify_untracked_policy() { :; }
verify_resume_app_bytes() { :; }
verify_clean_worktree() { :; }
verify_app_bytes() { :; }
snapshot_backup_source_metadata() { :; }
snapshot_backup_archives() { :; }
prepare_challenge_migration_boundary() { printf 'marker-prepare\n'; }
create_fresh_backup() { FRESH_BACKUP=quiesced-archive; printf 'quiesced-backup\n'; }
apply_trusted_payload() { printf 'payload-write\n'; }
"""
    harness += "create_online_preflight_backup() { printf 'online-backup\\n'; PREFLIGHT_BACKUP=online-archive; "
    harness += "printf 'capacity-resource-failure\\n'; return 1; }\n" if online_failure else "return 0; }\n"
    harness += "verification_launcher_source() { printf 'fixture launcher\\n'; }\n"
    harness += "prepare_verification_launcher() { :; }\n"
    harness += "".join(shell_function(name) for name in ("configure_context_phase", "preflight_context_runtime",
        "verify_context_runtime_before_update", "verify_context_runtime_from_archive"))
    return harness + source[begin:end] + '\nprintf "archives:%s:%s\\n" "$PREFLIGHT_BACKUP" "$FRESH_BACKUP"\n'


def test_capacity_failure_from_fresh_online_backup_precedes_every_stop_and_write():
    result = subprocess.run([bash()], input=capacity_order_harness(online_failure=True),
        text=True, capture_output=True, timeout=20)
    assert "command not found" not in result.stderr, result.stderr
    lines = result.stdout.splitlines()
    assert "online-backup" in lines, "real preflight omitted the required fresh online backup"
    assert "capacity-resource-failure" in lines
    assert result.returncode != 0
    assert not any(line.startswith(("service:", "autostart-write", "key-ensure", "marker-prepare", "payload-write")) for line in lines)


def test_capacity_success_uses_two_distinct_archives_and_private_phase_hooks():
    result = subprocess.run([bash()], input=capacity_order_harness(online_failure=False),
        text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert "online-backup" in lines, "the online snapshot cannot be replaced by the quiesced recovery archive"
    assert lines.index("online-backup") < lines.index("service:stop fixture.timer")
    assert lines.index("marker-prepare") < lines.index("quiesced-backup") < lines.index("payload-write")
    assert lines[-1] == "archives:online-archive:quiesced-archive"
    stages = [line for line in result.stderr.splitlines() if line.startswith("stage:")]
    assert len(stages) == 2
    assert "/var/lib/betboy-context-update.fixture/online" in stages[0] and "online-archive" in stages[0]
    assert "/var/lib/betboy-context-update.fixture/quiesced" in stages[1] and "quiesced-archive" in stages[1]


def test_capacity_full_var_lib_mount_rejects_before_preflight_capture(monkeypatch):
    """A separate full seal mount cannot borrow free space from /var/tmp."""
    with pytest.raises(SystemExit, match="insufficient combined"):
        capacity_disk_decision(monkeypatch, {"/var/tmp": (2, 8 * 1024**3),
            "/var/backups": (2, 8 * 1024**3), "/var/lib": (3, 1024)})


def test_capacity_output_overflow_is_an_immediate_child_failure(tmp_path):
    output = tmp_path / "overflow.txt"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c",
        "import sys; sys.stdout.write('x' * (1024 * 1024 + 1))"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
as_betboy() { shift 13; "$@"; }
""" + shell_function("context_hook_command")
    result = subprocess.run([bash()], input=harness + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\nprintf 'capture-accepted\\n'\n",
        text=True, capture_output=True, timeout=20)
    assert output.stat().st_size <= 1024 * 1024 + 1
    assert result.returncode != 0, "oversized aggregate child output was accepted by the process boundary"
    assert "capture-accepted" not in result.stdout


def test_capacity_child_environment_fixes_all_numerical_threads(tmp_path):
    output = tmp_path / "threads.json"
    names = ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]
    program = "import json, os; print(json.dumps({name: os.environ.get(name) for name in " + repr(names) + "}))"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c", program])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
as_betboy() { "$@"; }
""" + shell_function("context_hook_command")
    result = subprocess.run([bash()], input=harness + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\n",
        text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == {
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}


def inline_program(function):
    source = shell_function(function)
    start = source.index("<<'PY'\n") + len("<<'PY'\n")
    return source[start:source.index("\nPY", start)]


def launcher_decision(monkeypatch, arguments, *, uid):
    """Execute the real stdlib launcher up to execve; never impersonate root."""
    captured, limits = [], []

    class ExecBoundary(Exception):
        pass

    def record_exec(executable, command, environment):
        captured.append((executable, command, environment))
        raise ExecBoundary

    fake_os = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    fake_os.geteuid = lambda: uid
    fake_os.execve = record_exec
    class FixturePath(type(Path())):
        def lstat(self):
            if self.name == "betboy-backup-runtime.py":
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_nlink=1)
            info = super().lstat()
            if self.name == "backup_runtime_databases.py":
                # Only the Unix DAC edge is simulated; real helper bytes and
                # the fixed digest/command selection are still validated.
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_nlink=1)
            return info
        def open(self, *args, **kwargs):
            if self.name == "betboy-backup-runtime.py":
                return (ROOT / "scripts/backup_runtime_databases.py").open(*args, **kwargs)
            return super().open(*args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setitem(sys.modules, "os", fake_os)
        scoped.setitem(sys.modules, "pathlib", SimpleNamespace(Path=FixturePath))
        scoped.setitem(sys.modules, "pwd", SimpleNamespace(getpwnam=lambda name: SimpleNamespace(pw_uid=1001)))
        scoped.setitem(sys.modules, "resource", SimpleNamespace(RLIMIT_AS=9, RLIMIT_CPU=0,
            setrlimit=lambda *args: limits.append(args)))
        scoped.setattr(sys, "argv", ["updater-stdlib-launcher", *arguments])
        with pytest.raises(ExecBoundary):
            exec(compile(inline_program("verification_launcher_source"), "updater-launcher", "exec"), {})
    executable, command, environment = captured[0]
    assert executable == command[0]
    return command, environment, limits


def capacity_disk_decision(monkeypatch, mounts):
    fake_os = SimpleNamespace(
        path=SimpleNamespace(lexists=lambda path: path in mounts),
        stat=lambda path, **_: SimpleNamespace(st_dev=mounts[path][0], st_mode=stat.S_IFDIR | 0o755, st_uid=0),
        statvfs=lambda path: SimpleNamespace(f_bavail=mounts[path][1], f_frsize=1))
    with monkeypatch.context() as scoped:
        scoped.setitem(sys.modules, "os", fake_os)
        scoped.setattr(sys, "argv", ["capacity", "1024", "1024"])
        exec(compile(inline_program("check_capacity_space"), "updater-capacity", "exec"), {})


def test_capacity_same_device_reservations_are_added_not_reused(monkeypatch):
    # Each individual reservation fits 800 MiB; their sum does not.
    with pytest.raises(SystemExit, match="insufficient combined"):
        capacity_disk_decision(monkeypatch, {path: (2, 800 * 1024**2)
            for path in ("/var/tmp", "/var/backups", "/var/lib")})
    capacity_disk_decision(monkeypatch, {path: (index, 800 * 1024**2)
        for index, path in enumerate(("/var/tmp", "/var/backups", "/var/lib"))})


@pytest.mark.parametrize("kind,uid", [("d4", 1000), ("backup", 0)])
def test_capacity_launcher_executes_only_fixed_bounded_target(monkeypatch, kind, uid):
    arguments = [kind, str(ROOT), "/var/lib/betboy-context-update.fixture/online/context_models.db"]
    if kind == "backup":
        arguments = [kind, str(ROOT / "scripts/backup_runtime_databases.py"), "/private/fresh.zip"]
    command, environment, limits = launcher_decision(monkeypatch, arguments, uid=uid)
    assert limits == [(9, (2147483648, 2147483648)), (0, (300, 300))]
    assert environment == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": "/var/tmp",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}
    if kind == "d4":
        assert command == ["/opt/betboy/venv/bin/python", "-I", "-B",
            str(ROOT / "scripts/verify_context_runtime.py"), "--sealed-file", "--database", str(Path(arguments[2]))]
    else:
        assert command == ["/usr/bin/python3", "-I", "-B", arguments[1], "--verify-only", str(Path("/private/fresh.zip")), "--recovery-mode"]


@pytest.mark.parametrize("arguments,uid", [(["d4", "target", "database"], 0),
    (["dependencies", "target"], 0), (["backup", "helper", "archive"], 1000),
    (["shell", "sh", "-c", "untrusted"], 0), (["d4", "target", "database", "--memory"], 1000)])
def test_capacity_launcher_rejects_role_or_free_argument_override(monkeypatch, arguments, uid):
    with pytest.raises(SystemExit, match="invalid verification child selection"):
        launcher_decision(monkeypatch, arguments, uid=uid)


@pytest.mark.parametrize("legacy,present,key,marker,accepted", [
    (True, False, None, None, True), (True, True, None, None, False),
    (False, True, None, None, False), (True, False, None, {"status": "in_progress"}, False),
])
def test_capacity_online_keyless_exception_is_exact_contextless_legacy(content_data, tmp_path, capsys, legacy, present, key, marker, accepted):
    args = configuration_fixture(content_data, tmp_path, legacy=legacy, present=present)
    hook = tmp_path / "online-auth"
    hook.mkdir()
    (hook / "config.json").write_text(json.dumps(content_data["configuration"](**args)))
    content_data["os"].geteuid = lambda: 0
    content_data["authentication_state"] = lambda *_: {"key": key, "marker": marker}
    command = ["online-auth", str(hook), "/etc/betboy/challenge-ledger-hmac.key", "/etc/betboy/challenge-ledger-v2-migrated.json"]
    if accepted:
        content_data["main"](command)
        assert capsys.readouterr().out == "not_present_legacy\n"
    else:
        with pytest.raises(ValueError, match="missing authentication"):
            content_data["main"](command)
    assert not (hook / "authentication.json").exists()


def test_capacity_online_cannot_relabel_quiesced_proof(content_data, tmp_path, capsys):
    hook, _, _ = prepared_stage(content_data, tmp_path)
    capsys.readouterr()
    (hook / "report.json").write_text(json.dumps(report()))
    with pytest.raises(ValueError, match="phase mismatch"):
        content_data["main"](["finish", str(hook), "0", "online"])
    assert capsys.readouterr().out == ""


def test_followup_quiesced_configuration_cannot_rebaseline_changed_online_env(content_data, tmp_path):
    args = configuration_fixture(content_data, tmp_path, present=True, env=b"FIXTURE_MODE=original\n")
    actual_configuration = content_data["configuration"]

    def fixture_environment_route(*values, **named):
        if values:
            values = list(values)
            assert values[1] == "/etc/betboy/betboy.env"
            values[1] = args["env_path"]
        return actual_configuration(*values, **named)

    content_data["configuration"] = fixture_environment_route
    content_data["os"].geteuid = lambda: 0
    common = [str(args[key]) for key in ("app", "target", "previous", "target_manifest", "previous_manifest")]
    def configure(hook):
        content_data["main"](["configure", common[0], "/etc/betboy/betboy.env", *common[1:],
            "a" * 40, "b" * 40, "c" * 40, str(hook), "1000", "1000"])
    configure(tmp_path / "online")
    args["env_path"].write_bytes(b"FIXTURE_MODE=changed-during-quiesce\n")
    with pytest.raises(ValueError, match="configuration|phase"):
        configure(tmp_path / "quiesced")
    assert not (tmp_path / "quiesced/config.json").exists()


def test_followup_extraction_to_seal_replacement_never_rebaselines(content_data, tmp_path):
    archive, raw = backup_fixture(tmp_path)
    replacement = tmp_path / "replacement.db"
    with closing(sqlite3.connect(replacement)) as connection:
        connection.execute("CREATE TABLE substituted(value INTEGER)")
        connection.commit()
    assert replacement.read_bytes() != raw
    destination = tmp_path / "sealed.db"
    real_open = content_data["os"].open
    sqlite_opens = []
    real_connect = sqlite3.connect

    def swap_before_seal(path, flags, *args, **kwargs):
        if Path(path) == destination and not flags & os.O_CREAT and replacement.exists():
            os.replace(replacement, destination)
        return real_open(path, flags, *args, **kwargs)

    def record_sqlite(*args, **kwargs):
        sqlite_opens.append(args[0])
        return real_connect(*args, **kwargs)

    content_data["os"].open = swap_before_seal
    content_data["sqlite3"] = SimpleNamespace(connect=record_sqlite)
    with pytest.raises(ValueError, match="identity|changed|digest"):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", destination,
            source_head="a" * 40, app_gid=1000)
    assert sqlite_opens == []


def test_followup_actual_recovery_mount_not_its_parent_controls_admission(monkeypatch):
    with pytest.raises(SystemExit, match="insufficient combined"):
        capacity_disk_decision(monkeypatch, {"/var/tmp": (1, 8 * 1024**3),
            "/var/backups": (1, 8 * 1024**3), "/var/lib": (1, 8 * 1024**3),
            "/var/backups/betboy-update": (2, 1024 * 1024)})


def completed_archive_fixture(content_data, tmp_path):
    source, target = tmp_path / "produced.zip", tmp_path / "private.zip"
    source.write_bytes(b"completed-capture")
    receipt = tmp_path / "completion.json"
    receipt.write_text(json.dumps({"schema": 1, "path": str(source), "size": source.stat().st_size,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "signature": content_data["signature"](source.stat())}))
    return source, target, receipt


def test_followup_root_transfer_rejects_growth_after_producer_completion(content_data, tmp_path):
    source, target, receipt = completed_archive_fixture(content_data, tmp_path)
    with source.open("ab") as retained:
        retained.write(b"post-capture-growth" * 1024)
        retained.flush()
        with pytest.raises(ValueError, match="changed after producer"):
            content_data["copy_completed_archive"](source, target, receipt, 1024**2, source.stat().st_uid, source.stat().st_gid)
    assert not target.exists()


def test_followup_post_migration_backup_verifier_rejects_output_overflow(tmp_path):
    archive = tmp_path / "scheduled.zip"
    archive.write_bytes(b"fixture-path-exists")
    noisy = " ".join(shlex.quote(value) for value in [sys.executable, "-I", "-B", "-c",
        "import sys; sys.stdout.write('x' * (1024 * 1024 + 1))"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
TRUSTED_BACKUP_HELPER=/usr/local/libexec/betboy-backup-runtime.py
BACKUP_ARCHIVE_INVENTORY=inventory
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
verify_backup_principal() { :; }
verify_backup_home() { :; }
trusted_file() { printf 'trusted-helper\n'; }
systemctl() {
    case "$1" in start) :;; is-active) printf 'inactive\n';;
        show) case "$4" in Result) printf 'success\n';; ExecMainStatus) printf '0\n';; esac;; esac
}
stat() { case "$2" in '%U:%G') printf 'betboy-backup:betboy-backup\n';; '%a') printf '600\n';; '%h') printf '1\n';; *) command stat "$@";; esac; }
"""
    harness += f"STAGE_DIR={shlex.quote(tmp_path.as_posix())}\n/usr/bin/python3() {{ printf '%s\\n' {shlex.quote(archive.as_posix())}; }}\n"
    harness += 'runuser() { if [[ "$*" == *"/usr/bin/test"* ]]; then return 0; fi; ' + noisy + '; }\n'
    harness += shell_function("verification_launcher_source") + shell_function("capture_backup_service_verifier") + shell_function("verify_backup_service_migration")
    harness += "\nverify_backup_service_migration\nprintf 'migration-backup-accepted\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert "command not found" not in result.stderr, result.stderr
    assert result.returncode != 0, "post-migration full verifier accepted unbounded child output"
    assert "migration-backup-accepted" not in result.stdout


def test_followup_archive_copy_is_independent_and_binds_receipt(content_data, tmp_path):
    source, target, receipt = completed_archive_fixture(content_data, tmp_path)
    content_data["copy_completed_archive"](source, target, receipt, 1024**2, source.stat().st_uid, source.stat().st_gid)
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_ino != source.stat().st_ino
    source.write_bytes(b"retained writer changes source")
    assert target.read_bytes() == b"completed-capture"


@pytest.mark.parametrize("mutation", ["truncate", "replace", "digest", "oversize", "deadline"])
def test_followup_archive_copy_rejects_unaccepted_bytes(content_data, tmp_path, mutation):
    source, target, receipt = completed_archive_fixture(content_data, tmp_path)
    maximum = 1024**2
    if mutation == "truncate": source.write_bytes(b"short")
    elif mutation == "replace":
        replacement = tmp_path / "replacement.zip"
        replacement.write_bytes(source.read_bytes())
        os.replace(replacement, source)
    elif mutation == "digest":
        value = json.loads(receipt.read_text())
        value["sha256"] = "0" * 64
        receipt.write_text(json.dumps(value))
    elif mutation == "oversize": maximum = 1
    else:
        ticks = iter([0, 601])
        content_data["time"] = SimpleNamespace(monotonic=lambda: next(ticks))
    with pytest.raises(ValueError):
        content_data["copy_completed_archive"](source, target, receipt, maximum, source.stat().st_uid, source.stat().st_gid)
    if target.exists():
        assert mutation in {"digest", "deadline"}  # private failed candidate, never published


def test_followup_backup_service_launcher_has_exact_principal_and_command(monkeypatch):
    command, _, limits = launcher_decision(monkeypatch, ["backup-service", "/protected/scheduled.zip"], uid=1001)
    assert command == ["/usr/bin/python3", "-I", "-B", str(Path("/usr/local/libexec/betboy-backup-runtime.py")),
        "--verify-only", str(Path("/protected/scheduled.zip"))]
    assert limits == [(9, (2147483648, 2147483648)), (0, (300, 300))]


@pytest.mark.parametrize("uid,args", [(0, []), (1000, []), (1001, ["--recovery-mode"]), (1001, ["helper.py"])])
def test_followup_backup_service_launcher_rejects_role_and_overrides(monkeypatch, uid, args):
    with pytest.raises(SystemExit, match="invalid verification child selection"):
        launcher_decision(monkeypatch, ["backup-service", "/protected/scheduled.zip", *args], uid=uid)


def run_real_producer(monkeypatch, tmp_path, *, mutation=None, maximum=1024**2):
    """Execute complete producer bytes/SQLite/ZIP; simulate only Unix metadata/limits."""
    app = tmp_path / "app"
    app.mkdir()
    live = app / "state.db"
    writer = sqlite3.connect(live)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE sample(value INTEGER)")
    writer.execute("INSERT INTO sample VALUES(1)")
    writer.commit()
    key, marker = tmp_path / "key", tmp_path / "marker"
    key.write_bytes(b"a" * 64 + b"\n")
    marker.write_text(json.dumps({"contract_version": 1, "status": "in_progress"}))
    archive = tmp_path / "capture.zip"
    descriptors, limits = {}, []
    principal_changed = False

    def metadata(info, path):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
        auth = Path(path) in {key, marker}
        values.update(st_uid=0 if auth else (1002 if principal_changed and Path(path) == app else 1000),
            st_gid=1000, st_mode=(stat.S_IFDIR | 0o750) if stat.S_ISDIR(info.st_mode) else
            (stat.S_IFREG | (0o640 if auth else 0o600)))
        # Windows descriptor ctime is not the Unix inode-change timestamp.
        if os.name == "nt": values["st_ctime_ns"] = values["st_mtime_ns"]
        return SimpleNamespace(**values)

    class FixturePath(type(Path())):
        def lstat(self):
            return metadata(super().lstat(), self)

    fake_os = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    def fixture_open(path, flags, *args, **kwargs):
        descriptor = os.open(path, flags | getattr(os, "O_BINARY", 0), *args, **kwargs)
        descriptors[descriptor] = Path(path)
        return descriptor
    fake_os.open = fixture_open
    fake_os.fstat = lambda descriptor: metadata(os.fstat(descriptor), descriptors[descriptor])
    fake_os.getuid = fake_os.getgid = lambda: 1000
    fake_os.umask = lambda _: None
    fake_os.O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

    class ConcurrentSource(sqlite3.Connection):
        def backup(self, target, **kwargs):
            nonlocal principal_changed
            writer.execute("INSERT INTO sample VALUES(2)")
            if mutation == "growth-over-budget":
                writer.execute("INSERT INTO sample VALUES(zeroblob(?))", (maximum * 2,))
            writer.commit()  # actual same-inode WAL commit while capture is active
            super().backup(target, **kwargs)
            if mutation == "add":
                with closing(sqlite3.connect(app / "added.db")) as added:
                    added.execute("CREATE TABLE added(value)")
            elif mutation == "principal": principal_changed = True

    real_connect = sqlite3.connect
    fake_sqlite = SimpleNamespace(**{name: getattr(sqlite3, name) for name in dir(sqlite3)})
    fake_sqlite.connect = lambda *args, **kwargs: real_connect(*args, factory=ConcurrentSource, **kwargs)

    class MutatingArchive(zipfile.ZipFile):
        def close(self):
            was_open = self.fp is not None
            super().close()
            if was_open and mutation == "key-mutate": key.write_bytes(b"b" * 64 + b"\n")
            elif was_open and mutation == "key-replace":
                other = tmp_path / "replacement-key"
                other.write_bytes(key.read_bytes())
                os.replace(other, key)
            elif was_open and mutation == "marker-mutate":
                marker.write_text(json.dumps({"contract_version": 1, "status": "complete"}))
            elif was_open and mutation in {"remove", "replace"}:
                # Perform after source descriptors close: this remains a real
                # filesystem mutation on Windows as well as Unix.
                writer.close()
                if mutation == "remove": live.unlink()
                else:
                    replacement = tmp_path / "replacement.db"
                    with closing(sqlite3.connect(replacement)) as other:
                        other.execute("CREATE TABLE replacement(value)")
                    os.replace(replacement, live)

    fake_zip = SimpleNamespace(**{name: getattr(zipfile, name) for name in dir(zipfile)})
    fake_zip.ZipFile = MutatingArchive
    try:
        with monkeypatch.context() as scoped:
            scoped.setitem(sys.modules, "os", fake_os)
            scoped.setitem(sys.modules, "pathlib", SimpleNamespace(Path=FixturePath))
            scoped.setitem(sys.modules, "sqlite3", fake_sqlite)
            scoped.setitem(sys.modules, "zipfile", fake_zip)
            scoped.setitem(sys.modules, "resource", SimpleNamespace(RLIMIT_FSIZE=1, RLIMIT_AS=9, RLIMIT_CPU=0,
                setrlimit=lambda *args: limits.append(args)))
            scoped.setattr(sys, "argv", ["producer", str(app), str(archive), "c" * 40, str(key), str(marker), str(maximum)])
            exec(compile(inline_program("produce_update_backup"), "actual-update-producer", "exec"), {})
    finally:
        writer.close()
    assert limits == [(9, (2147483648, 2147483648)), (0, (300, 300)), (1, (maximum, maximum))]
    return archive


def test_followup_complete_producer_wal_capture_and_resume_head(monkeypatch, tmp_path, capsys):
    archive = run_real_producer(monkeypatch, tmp_path)
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["size"] == archive.stat().st_size
    assert receipt["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as captured:
        manifest = json.loads(captured.read("MANIFEST.json"))
        assert manifest["source_head"] == "c" * 40  # actual source, not marker predecessor
        assert json.loads(captured.read("integrity/challenge-ledger-v2-migrated.json"))["status"] == "in_progress"
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(captured.read("state.db"))
    with closing(sqlite3.connect(snapshot)) as connection:
        assert connection.execute("SELECT value FROM sample ORDER BY value").fetchall() == [(1,), (2,)]


@pytest.mark.parametrize("mutation", ["add", "remove", "replace", "principal", "key-mutate", "key-replace", "marker-mutate"])
def test_followup_complete_producer_rejects_inventory_and_auth_changes(monkeypatch, tmp_path, capsys, mutation):
    with pytest.raises((SystemExit, FileNotFoundError), match="changed|replaced|principal|No such|cannot find"):
        run_real_producer(monkeypatch, tmp_path, mutation=mutation)
    assert capsys.readouterr().out == ""  # no completion receipt for a rejected capture


@pytest.mark.parametrize("function", ["context_hook_command", "capture_root_verifier"])
@pytest.mark.parametrize("failure", ["memory", "cpu", "wall", "file-size"])
def test_followup_resource_failures_are_typed_and_never_continuity(function, failure, tmp_path):
    status = {"memory": 1, "cpu": 152, "wall": 124, "file-size": 153}[failure]
    code = "raise MemoryError" if failure == "memory" else f"raise SystemExit({status})"
    command = " ".join(shlex.quote(value) for value in [sys.executable, "-I", "-B", "-c", code])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
as_betboy() { "$@"; }
""" + shell_function(function)
    harness += f"\n{function} {shlex.quote((tmp_path / 'output').as_posix())} {command}\nprintf 'accepted\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode != 0 and "VerificationResourceError" in result.stderr
    assert "accepted" not in result.stdout


@pytest.mark.parametrize("defect", [None, "sticky", "group-write", "app-owner", "symlink"])
def test_followup_sealed_ancestry_has_no_sticky_exception(data, defect):
    from pathlib import PurePosixPath
    class BoundaryPath(PurePosixPath):
        def lstat(self):
            mode, owner = stat.S_IFDIR | 0o755, 0
            if str(self) == "/var":
                if defect == "sticky": mode = stat.S_IFDIR | stat.S_ISVTX | 0o777
                elif defect == "group-write": mode |= 0o020
                elif defect == "app-owner": owner = 1000
                elif defect == "symlink": mode = stat.S_IFLNK | 0o777
            return SimpleNamespace(st_mode=mode, st_uid=owner)
    data["Path"] = BoundaryPath
    if defect:
        with pytest.raises(ValueError, match="sealed directory"):
            data["sealed_directory"]("/var/lib/private")
    else: data["sealed_directory"]("/var/lib/private")


@pytest.mark.parametrize("replacement", [False, True])
def test_followup_cleanup_identity_ignores_only_directory_link_count(data, replacement):
    removed = []
    root = "/var/lib/betboy-context-update.abcdefgh"
    info = SimpleNamespace(st_dev=1, st_ino=25 if replacement else 24, st_mode=stat.S_IFDIR | 0o750,
        st_uid=0, st_gid=1000, st_nlink=5)
    data["os"] = SimpleNamespace(geteuid=lambda: 0)
    data["sealed_directory"] = lambda _: info
    data["read_file"] = lambda *args, **kwargs: json.dumps([1, 24, stat.S_IFDIR | 0o750, 0, 1000]).encode()
    def remove(path): removed.append(str(path))
    remove.avoids_symlink_attacks = True
    data["shutil"] = SimpleNamespace(rmtree=remove)
    if replacement:
        with pytest.raises(ValueError, match="private stage replaced"):
            data["main"](["remove-private", root])
        assert removed == []
    else:
        data["main"](["remove-private", root])
        assert removed == [str(Path(root))]


@pytest.mark.parametrize("failure", ["backup", "d4"])
def test_followup_second_phase_failure_never_applies_payload(failure):
    harness = capacity_order_harness(online_failure=False)
    if failure == "backup":
        harness = harness.replace("create_fresh_backup() {",
            "create_fresh_backup() { printf 'quiesced-backup\\n'; return 1;")
    else:
        harness = harness.replace("context_hook_command() { CONTEXT_COMMAND_STATUS=0; }",
            'context_hook_command() { [[ "$1" != */quiesced/* ]] || return 1; CONTEXT_COMMAND_STATUS=0; }')
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode != 0 and "quiesced-backup" in result.stdout
    assert "payload-write" not in result.stdout


@pytest.mark.parametrize("durable", [False, True])
def test_followup_recovery_never_uses_online_archive_or_removes_failclosed_evidence(tmp_path, durable):
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
UPDATE_COMPLETE=0; UPDATE_STARTED=1; DATABASE_MIGRATION_STARTED=0; NEW_APP_STARTED=0
FRESH_BACKUP=quiesced-archive; PREFLIGHT_BACKUP=online-archive; STAGE_DIR=preserved-stage
PREVIOUS_HEAD=old; TARGET_HEAD=new; PREVIOUS_MANIFEST=old-manifest; PREVIOUS_PAYLOAD=old-payload
log() { printf '%s\n' "$*"; }
safe_remove_stage() { printf 'cleanup\n'; }
stop_all_runtime_units() { printf 'stopped\n'; }
persist_runtime_autostart_disabled() { printf 'disabled\n'; }
git_betboy() { [[ "$1" != rev-parse ]] || printf 'old\n'; }
apply_trusted_payload() { printf 'restore-old:%s\n' "$*"; }
verify_clean_worktree() { :; }; verify_app_bytes() { :; }
restore_root_files() { :; }; verify_restored_root_files() { :; }
restore_unit_state() { printf 'restore-unit-state\n'; }
"""
    harness += f"ROLLBACK_ROOT={shlex.quote(tmp_path.as_posix())}\n"
    harness += f"durable_migration_requires_fail_closed() {{ return {0 if durable else 1}; }}\n"
    harness += shell_function("recover_update") + "\nrecover_update 1\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 1 and "online-archive" not in result.stdout
    if durable:
        assert "quiesced-archive" in result.stdout and "preserved-stage" in result.stdout
        assert "cleanup" not in result.stdout and "restore-old:" not in result.stdout
    else:
        assert "restore-old:old-manifest old-payload" in result.stdout
        assert "restore-unit-state" in result.stdout and "cleanup" in result.stdout


def test_followup_launcher_generation_failure_cannot_seal_or_execute_partial_source(tmp_path):
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
verification_launcher_source() { printf 'print("partial valid Python")\n'; return 9; }
context_hook_data() { printf 'must-not-seal\n'; }
""" + f"CONTEXT_STAGE_DIR={shlex.quote(tmp_path.as_posix())}\n"
    harness += shell_function("prepare_verification_launcher") + "\nprepare_verification_launcher\nprintf 'accepted\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode != 0 and "could not be written completely" in result.stderr
    assert "must-not-seal" not in result.stdout and "accepted" not in result.stdout


def test_followup_root_collector_failure_preserves_child_failure(tmp_path):
    command = " ".join(shlex.quote(value) for value in [sys.executable, "-I", "-B", "-c", "print('verified')"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
/usr/bin/timeout() { if [[ "$*" == *'610s'* ]]; then return 9; fi; command /usr/bin/timeout "$@"; }
""" + shell_function("capture_root_verifier")
    harness += f"\ncapture_root_verifier {shlex.quote((tmp_path / 'output').as_posix())} {command}\nprintf 'accepted\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode != 0 and "output capture failed" in result.stderr
    assert "accepted" not in result.stdout


@pytest.mark.parametrize("generator_failure", [False, True])
def test_followup_backup_service_requires_complete_launcher_and_bounded_success(tmp_path, generator_failure):
    child = " ".join(shlex.quote(value) for value in [sys.executable, "-I", "-B", "-c",
        "import sys; sys.stdin.read(); print('verified')"])
    harness = """set -euo pipefail
PATH=/usr/bin:/bin
die() { printf 'rejected:%s\n' "$*" >&2; exit 1; }
"""
    harness += f"verification_launcher_source() {{ printf 'fixed launcher\\n'; return {9 if generator_failure else 0}; }}\n"
    harness += "runuser() { " + child + "; }\n" + shell_function("capture_backup_service_verifier")
    harness += f"\ncapture_backup_service_verifier {shlex.quote((tmp_path / 'output').as_posix())} archive\nprintf 'accepted\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert (result.returncode != 0) == generator_failure, result.stderr
    assert ("accepted" in result.stdout) != generator_failure


@pytest.mark.parametrize("damage", ["crc", "truncated"])
def test_followup_real_zip_integrity_damage_never_seals(content_data, tmp_path, damage):
    archive, _ = backup_fixture(tmp_path)
    raw = bytearray(archive.read_bytes())
    if damage == "truncated": raw = raw[:-30]
    else:
        with zipfile.ZipFile(archive) as zipped:
            member = zipped.getinfo("runtime_state/context_models.db")
            offset = member.header_offset
        filename_length = int.from_bytes(raw[offset + 26:offset + 28], "little")
        extra_length = int.from_bytes(raw[offset + 28:offset + 30], "little")
        raw[offset + 30 + filename_length + extra_length + 50] ^= 0xFF
    archive.write_bytes(raw)
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "copy.db",
            source_head="a" * 40, app_gid=1000)


def test_followup_exact_sealed_bound_is_inclusive_and_one_byte_over_rejects(content_data, tmp_path):
    archive, raw = backup_fixture(tmp_path)
    assert content_data["MAX_IMAGE"] == 1024**3
    content_data["MAX_IMAGE"] = len(raw)  # exercise exact inequality with real SQLite bytes, not a 1-GiB unit allocation
    content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "at-limit.db",
        source_head="a" * 40, app_gid=1000)
    content_data["MAX_IMAGE"] = len(raw) - 1
    with pytest.raises(ValueError, match="bounded SQLite size"):
        content_data["extract_and_seal"](archive, "runtime_state/context_models.db", tmp_path / "over-limit.db",
            source_head="a" * 40, app_gid=1000)
    assert not (tmp_path / "over-limit.db").exists()


def test_followup_producer_snapshot_expansion_has_a_total_byte_admission(monkeypatch, tmp_path, capsys):
    with pytest.raises(SystemExit, match="ContextResourceError.*snapshot"):
        run_real_producer(monkeypatch, tmp_path, mutation="growth-over-budget", maximum=65536)
    assert capsys.readouterr().out == ""
