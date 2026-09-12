# Task56 — limited read-only VPS package/space observation

Root, 2026-09-12T16:16:47Z. SSH alias `betboy-vps`, ordinary read-only shell
metadata; no sudo, package import/install, copy, file modification, application
operation, database access or health/release claim. The query exits0.

Filesystem `/tmp`: total40483942400, used26341908480, available14125256704 bytes.
These are current free-space observations, not admission of the later full
workspace or a quota/peak/CPU/resource certificate. Recheck before any writer.

Package root: `/tmp/betboy-context-qa.9xr68INa/venv/lib/python3.12/site-packages`.
The following values are `du -sb` apparent sizes, including directory contents,
not authenticated file inventories, actual native imports or allocated peaks.

| Candidate root | Observed bytes / availability |
| --- | ---: |
| pandas | 68241073 |
| requests | 460390 |
| _pytest | 2971725 |
| pytest | 10779 |
| pluggy | 129799 |
| packaging | 977034 |
| iniconfig | 32265 |
| dateutil | 728905 |
| six.py | 34703 |
| pytz | absent |
| tzdata | absent |
| urllib3 | 882221 |
| idna | 495459 |
| charset_normalizer | 852192 |
| certifi | 249114 |

Absence of the two listed optional candidates is not adjudicated here as an
import failure or permission to install packages. Actual platform dependency
metadata, system timezone/runtime data and the final native import route still
need binding; a source-level list is not a complete Python/ELF catalogue.

The first attempt at16:16:01Z printed date/df (available14125268992) then failed
before its package loop: `/bin/sh: 12: Syntax error: end of file unexpected
(expecting "done")`. No package result or mutation came from that attempt.
Root replaced the PowerShell-to-shell stdin transport with one literal SSH
command string for the same read-only loop; no safety setting was relaxed.
No native probe rerun and no reset/refund of a preparation budget is claimed.
