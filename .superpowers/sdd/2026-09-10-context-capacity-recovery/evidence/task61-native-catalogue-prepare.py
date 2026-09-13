"""Fixed read/hash control preparation, not admission, copying or a worker run."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time

signal.alarm(300)  # This interpreter never creates a child/custodian.
assert os.getresuid() == os.getresgid() == (0,) * 3
assert (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode, sys.flags.optimize) == (1, 1, 1, 0)
assert dict(os.environ) == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
bundle = json.loads(base64.b64decode("BUNDLE_BASE64", validate=True))
pins = {
    "tests/native_context_receipt_diagnostic.py": "22faafb79d08f956b11693106cf933f4e6c9869f755c6f3e23628b5f5cca17c1",
    "tests/native_context_receipt_diagnostic_catalogue.py": "8ebd29f82bd8c92a8601adf8a339f9eb27ddbdf7dcb02bcc0f61d56ea03012e8",
    "tests/native_context_chain_catalogue.py": "48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935",
    "tests/native_context_diagnostic_admission.py": "f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad",
    "context_preparation_process_guard.py": "62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4",
    "context_preparation_budget.py": "fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478",
    "context_preparation_supervisor.py": "c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8",
}
assert type(bundle) is dict and set(bundle) == set(pins)
sources = {name: base64.b64decode(value, validate=True) for name, value in bundle.items()}
assert all(0 < len(raw) <= 1024**2 and hashlib.sha256(raw).hexdigest() == pins[name] for name, raw in sources.items())
parent = dict(__name__="_task61_fixed_preparation", __file__="<held-reviewed-task61-parent>")
exec(compile(sources["tests/native_context_receipt_diagnostic.py"], parent["__file__"], "exec"), parent)
c = parent["load_catalogue"](sources)
helpers = parent["load_helpers"](c, sources)
assert not any(name.startswith(("pytest", "numpy", "scipy", "pandas", "context_storage_v2")) for name in sys.modules)

journal_raw = base64.b64decode("JOURNALS_BASE64", validate=True)
assert len(journal_raw) <= 262144 and hashlib.sha256(journal_raw).hexdigest() == "4b88319870c1cc504a52e1842f29d40337cf1c355f5e098c5ae242a8ad5536cd"
known = json.loads(journal_raw)["journals"]
assert len(known) == 16
prior_raw = base64.b64decode("PREVIOUS_ROOTS_BASE64", validate=True)
assert len(prior_raw) <= 262144 and hashlib.sha256(prior_raw).hexdigest() == "2e1699479e0bae473ac9f8bfd7038dbac4ec7bf9f2060081cfc6652ec4be1171"
prior = {record["path"] for record in json.loads(prior_raw)["roots"]}
assert len(prior) == 85
root = Path("/var/lib/betboy-receipt-input-task61-01")
registry = Path("/var/lib/betboy-receipt-registry-task61-01")
job = Path("/var/lib/betboy-receipt-task61-01")
archive = root / "task61-1632072-01.tar"
retained_path, manifest_path = root / "retained.json", root / "catalogue.json"
new = {str(root), str(registry), str(job)}
for path in (root, registry, job):
    c["protected"](path, directory=True)
assert sorted(p.name for p in root.iterdir()) == [archive.name]
assert not list(registry.iterdir()) and not list(job.iterdir())
assert c["old"]()["file_record"](archive, maximum=64 * 1024**2) == dict(size=9533440, sha256="daf6ac61183bb3a42f8401f7568b2020a0f4bdef07d07a72d295e61363bc4d4c")

selectors = (("/var/lib", "betboy-", ("betboy-backup",)),
             ("/var/tmp", "betboy-update.", ()),
             ("/tmp", "betboy-context-", ()), ("/tmp", "betboy-tour-", ()),
             ("/var/backups", "betboy", ("betboy-ssh",)))
def selected():
    result = set()
    for directory, prefix, omitted in selectors:
        count = 0
        with os.scandir(directory) as items:
            for item in items:
                count += 1
                assert count <= 50000
                if item.name.startswith(prefix) and item.name not in omitted and item.path not in new:
                    result.add(item.path)
    assert 0 < len(result) <= 256 and prior <= result
    assert "/var/lib/betboy-admission-task60-protocol-8574747-01" in result
    assert "/var/lib/betboy-receipt-prefix-task61-01" in result
    return sorted(result)

paths = selected()
assert all(record["root"] in paths for record in known)
records = []
for path in paths:
    record = c["retained_root"](path)
    record.update(category="backup" if path.startswith("/var/backups/") or path.startswith("/var/lib/betboy-live-backup-") else "historical-qa",
                  charged_cpu_ns=None,
                  journals=sorted(({key: value for key, value in item.items() if key in (
                      "path", "identity", "journal_head", "ticket", "state", "charged_cpu_ns", "settled_cpu_ns", "category")}
                      for item in known if item["root"] == path), key=lambda item: item["path"]))
    c["validate_journals"](Path(path), record["journals"], observe=True)
    records.append(record)
assert paths == selected()
retained = c["canonical"](dict(format="betboy-receipt-diagnostic-retained-v1", roots=records,
                              backup_rollback_reserve=4 * 1024**3))
c["validate_retained"](retained)  # Exact shape; actual hashes were measured above.
parent["write_new"](c, retained_path, retained, 8 * 1024**2)
manifest = c["inventory"](str(archive), "1632072216b33d85b0343c1f389f762356b62d0a",
    manifest_path=str(manifest_path), retained_path=str(retained_path),
    retained_sha256=c["digest"](retained), registry_directory=str(registry), job_directory=str(job))
assert paths == selected()
parent["write_new"](c, manifest_path, manifest, 8 * 1024**2)
value = c["decode"](manifest)
launch = c["launcher"](str(archive), value["archive"]["sha256"], str(manifest_path), c["digest"](manifest))
output = dict(format="betboy-task61-catalogue-prepared-v1", roots=len(records),
    retained_bytes=len(retained), retained_sha256=c["digest"](retained),
    manifest_bytes=len(manifest), manifest_sha256=c["digest"](manifest),
    launcher_bytes=len(launch), launcher_sha256=c["digest"](launch),
    occupied_allocated_upper_bound=sum(x["allocated"] for x in records),
    new_job_reservation=value["allocation"]["total"], active_input_cap=value["allocation"]["active_input_cap"],
    backup_rollback_reserve=value["allocation"]["backup_rollback_reserve"],
    cpu_ns=time.process_time_ns(), observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    admitted=False, worker_launched=False, application_changed=False)
print(c["canonical"](output).decode("ascii"), flush=True)
