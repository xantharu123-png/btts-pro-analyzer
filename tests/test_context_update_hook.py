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
    data["write_new"] = fixture_write
    # Windows fd ctime and named ctime differ; neither proves Unix DAC here.
    if os.name == "nt":
        original = data["signature"]
        data["signature"] = lambda info: original(info)[:-1]
    data["os"] = SimpleNamespace(**{name: getattr(os, name) for name in dir(os)})
    data["os"].chown = lambda *_: None
    data["os"].chmod = lambda path, mode: Path(path).chmod(mode)
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
""" + f"MIGRATION_RESUME_TARGET={int(resuming)}\n" + shell_function("preflight_context_runtime") + "\npreflight_context_runtime\n"
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
as_betboy() { printf '%s|' "$@" >&3; shift 8; "$@"; }
exec 3>&2
""" + shell_function("context_hook_command") + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\nprintf '%s\\n' \"$CONTEXT_COMMAND_STATUS\"\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(exit_code)
    assert output.read_bytes() == b"fixture-only\r\n" if os.name == "nt" else output.read_bytes() == b"fixture-only\n"
    assert result.stderr.startswith("/usr/bin/env|-i|PATH=/usr/bin:/bin|LANG=C.UTF-8|/usr/bin/timeout|--signal=TERM|--kill-after=10s|600s|")
    assert "|-I|-B|-c|" in result.stderr


def test_root_inline_program_imports_only_stdlib_and_never_backup_helpers(data):
    source = shell_function("context_hook_data")
    begin = source.index("<<'PY'\n") + len("<<'PY'\n")
    tree = ast.parse(source[begin:source.index("\nPY", begin)])
    imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"hashlib", "json", "os", "pathlib", "re", "sqlite3", "stat", "sys", "zipfile"}
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
    for directory in (app, target, old): directory.mkdir()
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
STAGE_DIR=stage; FRESH_BACKUP=private-archive; VENV_DIR=venv
die() { printf 'rejected\n'; exit 1; }
verify_no_betboy_processes() { printf 'process-check\n'; }
target_payload_file() { printf 'root-staged-cli\n'; }
context_hook_command() { printf 'app-user-command:%s\n' "$*"; CONTEXT_COMMAND_STATUS=2; }
"""
    stage = "return 1" if presence == "failed-stage" else "printf '%s\\n' " + shlex.quote(presence)
    harness += "context_hook_data() { if [[ $1 == stage ]]; then " + stage + "; else printf 'finish:%s\\n' \"$*\"; fi; }\n"
    harness += shell_function("verify_context_runtime_before_update") + "\nverify_context_runtime_before_update\nprintf 'after-hook\\n'\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    lines = result.stdout.splitlines()
    assert lines[0] == "process-check"
    if presence in {"unknown", "failed-stage"}:
        assert result.returncode != 0 and "after-hook" not in lines
        assert not any(line.startswith(("finish:", "app-user-command:")) for line in lines)
    elif presence == "present":
        assert result.returncode == 0, result.stderr
        assert lines[1] == "app-user-command:stage/context-hook/report.json venv/bin/python -I -B root-staged-cli --database stage/context-hook/context_models.db"
        assert lines[2:] == ["process-check", "finish:finish stage/context-hook 2", "after-hook"]
    else:
        assert result.returncode == 0, result.stderr
        assert lines == ["process-check", "process-check", "finish:finish stage/context-hook 0", "after-hook"]


def test_real_shell_output_is_bounded_and_already_existing_output_is_never_replaced(tmp_path):
    output = tmp_path / "capture.json"
    command = " ".join(shlex.quote(x) for x in [sys.executable, "-I", "-B", "-c",
        "import sys; sys.stdout.write('x' * (1024 * 1024 * 3))"])
    prefix = """set -euo pipefail
PATH=/usr/bin:/bin
die() { exit 1; }
as_betboy() { shift 8; "$@"; }
""" + shell_function("context_hook_command")
    call = f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\n"
    first = subprocess.run([bash()], input=prefix + call, text=True, capture_output=True, timeout=20)
    assert first.returncode == 0, first.stderr
    assert output.stat().st_size == 1024 * 1024 + 1
    before = output.read_bytes()
    second = subprocess.run([bash()], input=prefix + call, text=True, capture_output=True, timeout=20)
    assert second.returncode != 0
    assert output.read_bytes() == before


def test_actual_dependency_python_uses_target_graph_and_deserialize_before_downtime(data, tmp_path):
    source = shell_function("preflight_context_runtime")
    begin = source.index("<<'PY'\n") + len("<<'PY'\n")
    code = source[begin:source.index("\nPY", begin)]
    result = subprocess.run([sys.executable, "-I", "-B", "-", str(ROOT)], input=code,
        text=True, capture_output=True, cwd=tmp_path, timeout=90)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "context-dependencies-v1:ok\n"
    assert "importlib.import_module(name)" in code
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


def test_64_mib_cap_applies_before_sealing_or_sqlite_parse(content_data, tmp_path):
    assert content_data["MAX_IMAGE"] == 64 * 1024 * 1024
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
as_betboy() { shift 8; "$@"; }
/usr/bin/timeout() { printf 'collector:%s\n' "$*" >&3; command /usr/bin/timeout "$@"; }
exec 3>&2
""" + shell_function("context_hook_command") + f"\ncontext_hook_command {shlex.quote(output.as_posix())} {command}\n"
    result = subprocess.run([bash()], input=harness, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stderr == "collector:--signal=TERM --kill-after=10s 610s /usr/bin/head -c 1048577\n"
