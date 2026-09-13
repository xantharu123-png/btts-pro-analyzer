"""Read one published Wettfinder artifact without imports or product writes."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import time

signal.alarm(20)
path = Path("/opt/betboy/app/runtime_state/wettfinder_latest.json")
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    before = os.fstat(fd)
    assert stat.S_ISREG(before.st_mode) and before.st_size <= 64 * 1024**2
    with os.fdopen(os.dup(fd), "rb") as stream:
        raw = stream.read(64 * 1024**2 + 1)
    after = os.fstat(fd)
    assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    assert len(raw) == before.st_size
finally:
    os.close(fd)
document = json.loads(raw)
assert isinstance(document, dict)

def redact(text):
    if not isinstance(text, str):
        return None
    if re.search(r"(?i)password|secret|token|api.?key|authorization|credential", text):
        return "[credential-like error withheld]"
    text = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://\S+", "[URL withheld]", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email withheld]", text)
    return re.sub(r"[A-Za-z0-9_+/=.-]{40,}", "[long identifier withheld]", text)[:500]

fields = ("status", "run_status", "operational_error_count", "error_count", "candidate_count",
          "model_candidate_count", "due_reason", "context_status", "failure_type", "prediction_status")
def summary(value):
    if not isinstance(value, dict):
        return None
    result = {k: value[k] for k in fields if k in value and isinstance(value[k], (str, int, bool, type(None)))}
    for key in ("error", "reason"):
        if key in value:
            result[key] = redact(value[key])
    for key in ("errors", "issues", "operational_errors"):
        if isinstance(value.get(key), list):
            result[key] = [redact(item) for item in value[key][:10] if isinstance(item, str)]
    if isinstance(value.get("settlement"), dict):
        result["settlement"] = summary(value["settlement"])
    return result

sources = document.get("sources", {})
assert isinstance(sources, dict) and len(sources) <= 20
output = dict(format="betboy-wettfinder-status-readonly-v1",
    observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    file_bytes=len(raw), file_sha256=hashlib.sha256(raw).hexdigest(),
    generated_at=document.get("generated_at"), run=summary(document),
    sources={name: summary(value) for name, value in sources.items()},
    football=summary(document.get("football")), riskobet=summary(document.get("riskobet")),
    forecast_evidence=summary(document.get("forecast_evidence")),
    candidates=len(document.get("candidates", [])), model_candidates=len(document.get("model_candidates", [])),
    predictions_returned=False, product_changed=False)
print(json.dumps(output, sort_keys=True, separators=(",", ":")))
