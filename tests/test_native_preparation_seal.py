"""Portable parser/identity tests, never a root seal or native execution."""
import hashlib
import io
import tarfile

import pytest

import native_preparation_seal as seal


def archive_of(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, body, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(body)
            if kind == tarfile.SYMTYPE:
                info.linkname = "/outside"
            archive.addfile(info, io.BytesIO(body))
    return output.getvalue()


@pytest.fixture
def source_set(monkeypatch):
    helpers = {name: (name + " fixture").encode("ascii") for name in seal.HELPERS}
    monkeypatch.setattr(seal, "HELPERS", {name: hashlib.sha256(body).hexdigest()
                                         for name, body in helpers.items()})
    entries = [(name + ".py", body, tarfile.REGTYPE) for name, body in helpers.items()]
    entries.extend([("tests/native_preparation_probe.py", b"probe", tarfile.REGTYPE),
                    ("tests/native_preparation_worker.py", b"worker", tarfile.REGTYPE)])
    return entries


def decode(raw, **changes):
    kwargs = dict(archive_sha=hashlib.sha256(raw).hexdigest(),
                  probe_sha=hashlib.sha256(b"probe").hexdigest(),
                  worker_sha=hashlib.sha256(b"worker").hexdigest())
    kwargs.update(changes)
    return seal.decode_archive(raw, **kwargs)


def test_complete_pinned_five_source_archive(source_set):
    raw = archive_of([("tests", b"", tarfile.DIRTYPE), *source_set])
    assert decode(raw) == {name: body for name, body, _ in source_set}


@pytest.mark.parametrize("change", ["missing", "unknown", "duplicate", "traversal", "symlink", "oversized", "changed"])
def test_nonclosed_or_changed_archive_is_not_extracted(source_set, change):
    values = list(source_set)
    if change == "missing":
        values.pop()
    elif change == "unknown":
        values.append(("extra.py", b"extra", tarfile.REGTYPE))
    elif change == "duplicate":
        values.append(values[0])
    elif change == "traversal":
        name, body, kind = values[0]
        values[0] = ("../" + name, body, kind)
    elif change == "symlink":
        values[0] = (values[0][0], b"", tarfile.SYMTYPE)
    elif change == "oversized":
        values[0] = (values[0][0], b"x" * (128 * 1024 + 1), tarfile.REGTYPE)
    else:
        values[0] = (values[0][0], b"changed", tarfile.REGTYPE)
    with pytest.raises(RuntimeError):
        decode(archive_of(values))


@pytest.mark.parametrize("value", ["", "A" * 64, "0" * 63, "g" * 64, None, 42])
def test_hashes_not_coerced(value):
    with pytest.raises(RuntimeError):
        seal.digest_text(value)


def test_wrong_archive_or_source_hash_never_accepted(source_set):
    raw = archive_of(source_set)
    for key in ("archive_sha", "probe_sha", "worker_sha"):
        with pytest.raises(RuntimeError):
            decode(raw, **{key: "0" * 64})


def test_unknown_directory_member_rejected(source_set):
    with pytest.raises(RuntimeError):
        decode(archive_of([("elsewhere", b"", tarfile.DIRTYPE), *source_set]))


def test_sealer_no_execution_or_deletion_on_import():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(seal.__file__).read_text(encoding="utf-8"))
    names = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)}
    assert not names & {"execve", "system", "Popen", "unlink", "rmtree", "remove", "extractall"}
    assert seal.DEPENDENCY_SOURCE.parents[3].as_posix() == "/tmp/betboy-context-qa.9xr68INa"
