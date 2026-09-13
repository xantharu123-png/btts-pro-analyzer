"""Read-only replay of explicitly selected historical QA journals, not reuse."""
import base64
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time
import types

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
signal.alarm(20)
assert os.geteuid() == 0 and sys.flags.isolated and sys.flags.no_site
raw_source = base64.b64decode("BUDGET_BASE64", validate=True)
assert hashlib.sha256(raw_source).hexdigest() == "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478"
budget = types.ModuleType("context_preparation_budget")
assert budget.__name__ not in sys.modules
sys.modules[budget.__name__] = budget
exec(compile(raw_source, "<held-reviewed-budget>", "exec"), budget.__dict__)

# The dictionary derives only from the explicit known native execution roots.
# Embedded roundtrip/recovery fixtures are preserved but not actual cost claims.
selected = {
    "betboy-native-probe-wu61odle": [
        ("output/journal-diagnostic/dc07569778e932ed3f40f580d0499a40a35f128f533f36dd30bf24df3c77752f.jsonl", "historical-measurement"),
        ("output/journal-roundtrip/77210ca0cad5508cb9f020b896f68292101a97c5220dc3a530e31a85f19e4674.jsonl", "synthetic-protocol"),
        ("output/journal-recovery/ff9660da6ed77bc7cbf2ca31e4e82cad3c80d9855cb1eeb2df95162ab62f4cc6.jsonl", "synthetic-protocol")],
    "betboy-native-probe-ncx37y3f": [
        ("output/journal-diagnostic/5d962c723ee0b9926f0daebd68b83424d871d456c51e24a8209fadd53f87294c.jsonl", "historical-measurement"),
        ("output/journal-roundtrip/6361b5d086c44baa1b4eb0c655e0ed9c9812cca7ccfe03963dfe3b5faa278b36.jsonl", "synthetic-protocol"),
        ("output/journal-recovery/0a9ef4c2135ac71d4ca892cec1c9777084a190874a8be6b02e60cb7c8dd358a5.jsonl", "synthetic-protocol")],
    "betboy-native-probe-2gcraxxf": [
        ("output/journal-diagnostic/86e6c30e6d4ef5d893b8e551fbcb2e6185f16abe5d5de374b6d592d703cdca0f.jsonl", "historical-measurement"),
        ("output/journal-roundtrip/9e787f8f05596eabcfbf8a4875ccd8d4dd290c0cf1e0d5e1d723d460a7eaf6c4.jsonl", "synthetic-protocol"),
        ("output/journal-recovery/262d6d3eb3c2b146e28102cb1cc51a118b8035d3bb47e14b30df5aa50eb982d1.jsonl", "synthetic-protocol")],
    "betboy-context-chain-task57-ba9c88f-02": [("a8061f178ea8b126f39a93aaaa9621b24e630faeb7ce8548ebe068fb70ee8249.jsonl", "historical-measurement")],
    "betboy-context-chain-task57-97e3bb6-03": [("be5cd6877f5a3fe5dbb4ee00049eea963c8cf0b5c4782aecc10b58ac1f67a238.jsonl", "historical-measurement")],
    "betboy-context-chain-task57-df874ba-04": [("99f8aff214f96ac6debc056a865d7b447c5caade5310feb6e90676575cfb4c97.jsonl", "historical-measurement")],
    "betboy-context-chain-task57-bc6305c-05": [("b764d67226dfba5ab97281d19a7ef903b542f810e4b212591d772c3f63ad488f.jsonl", "historical-measurement")],
    "betboy-context-chain-task58-588843d-01": [("8cf04c77ca7a47063617cb1489471160c8329ce1420298b112e04c547c2a720f.jsonl", "historical-measurement")],
    "betboy-admission-task60-protocol-8574747-01": [
        ("registry/e66e8a4f9b6958c5c30126ce5761e31a41d89a995fb01212811ac5e334a5f627.jsonl", "synthetic-protocol"),
        ("loss-registry/e66e8a4f9b6958c5c30126ce5761e31a41d89a995fb01212811ac5e334a5f627.jsonl", "synthetic-protocol")],
}


def stamp(value):
    return [value.st_dev, value.st_ino, value.st_mode, value.st_uid,
            value.st_gid, value.st_nlink, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_blocks]


rows = []
for root_name, entries in sorted(selected.items()):
    root = Path("/var/lib") / root_name
    for relative, category in sorted(entries):
        path = root / relative
        ancestors = [(parent, stamp(parent.lstat())) for parent in reversed(path.parents)]
        for parent, identity in ancestors:
            assert stat.S_ISDIR(identity[2]) and identity[3] == 0 and not identity[2] & 0o022
        before = path.lstat()
        assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 1048576
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            held = os.fstat(stream.fileno())
            assert stamp(held) == stamp(before)
            raw = stream.read(1048577)
            assert len(raw) == held.st_size <= 1048576
            assert stamp(os.fstat(stream.fileno())) == stamp(held) == stamp(path.lstat())
        assert all(stamp(parent.lstat()) == identity for parent, identity in ancestors)
        first = json.loads(raw.splitlines()[0])
        identity = budget.BudgetIdentity(**first["record"]["body"]["identity"])
        value = budget._replay(raw, identity).snapshot()
        rows.append({"root": str(root), "path": relative, "category": category,
                     "identity": dataclasses.asdict(identity), "journal_head": value.journal_digest,
                     "ticket": None if value.pending is None else dataclasses.asdict(value.pending),
                     "state": value.status, "charged_cpu_ns": value.charged_cpu_ns,
                     "settled_cpu_ns": value.settled_cpu_ns, "bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest(), "file_identity": stamp(held)})
output = {"format": "betboy-known-qa-journals-readback-v1", "journals": rows,
          "observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "cpu_seconds": time.process_time(), "durable_ticket_for_this_read": None,
          "reopened_or_resumed": False, "full_cost_authority": False}
encoded = json.dumps(output, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
assert len(encoded) <= 65536
view = memoryview(encoded)
while view:
    written = os.write(1, view)
    assert written > 0
    view = view[written:]
