"""Read-only system journal triage: return exception types/frames, no payloads."""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
import json
import re
import signal
import subprocess
import time

signal.alarm(20)
result = subprocess.run([
    "/usr/bin/journalctl", "--unit=betboy-wettfinder.service", "--since=2026-09-13 10:07:00 UTC",
    "--until=2026-09-13 10:15:00 UTC", "--no-pager", "--output=json", "-n", "120",
], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
assert len(result.stdout) <= 2 * 1024**2 and len(result.stderr) <= 4096
frames, exceptions, timestamps, summaries = [], [], [], []
messages = 0
for line in result.stdout.splitlines():
    entry = json.loads(line)
    message = entry.get("MESSAGE", "")
    if not isinstance(message, str):
        continue
    messages += 1
    timestamps.append(entry["__REALTIME_TIMESTAMP"])
    for filename, number, function in re.findall(r'File "([^"\r\n]{1,500})", line ([0-9]{1,8}), in ([A-Za-z0-9_<>.]{1,200})', message):
        frames.append(dict(file=filename, line=int(number), function=function))
    exceptions.extend(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):", message))
    if re.search(r"(?i)password|secret|token|api.?key|authorization|credential", message):
        summaries.append("[credential-like log message withheld]")
    else:
        summary = re.sub(r"[A-Za-z][A-Za-z0-9+.-]*://\S+", "[URL withheld]", message)
        summary = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email withheld]", summary)
        summary = re.sub(r"[A-Za-z0-9_+/=.-]{40,}", "[long identifier withheld]", summary)
        summaries.append(summary[:600])
print(json.dumps(dict(format="betboy-wettfinder-error-frames-readonly-v1",
    observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    journal_exit=result.returncode, messages=messages,
    first_timestamp=timestamps[0] if timestamps else None,
    last_timestamp=timestamps[-1] if timestamps else None,
    frames=frames[-40:], exception_types=exceptions[-20:], redacted_summaries=summaries[-20:],
    raw_messages_returned=False, service_changed=False), sort_keys=True, separators=(",", ":")))
