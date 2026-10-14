# Task21: eliminate transient path interning in the actual footprint owner

Approved repair scope remains the existing reader's unmodified512KiB gross
allocation gate. This is not a new C source policy, resource increase, cached
proof, admission bypass, native model effect, test warmup or new data scan.

## Real RED / cause

QA03 complete13980PASS/1FAIL/97identical skips/147PASSsubtests, exact14078IDs.
Original unchanged memory node peak7720876. Combined diagnostic collects all
6837 A nodes, retains their live roots, executes only the exact1544-item prefix
via the real partition entry; peak7720933, original threshold524288FAIL.
The saved original measurement precedes diagnostic work. Snapshot has a single
7689584-byte allocation attributed to stdlib pathlib.py404, sys.intern; exact
CPython Unicode dict table size for2^19 slots. This proves intern-dict table
allocation/rebuild, not unbounded output buffering or necessarily doubling.
Separate collection-only and prefix-only controls do not reproduce it.

## Narrow implementation and unchanged safety contract

Keep `_require_connection`'s current Path-valued return contract for its cold
callers (snapshot_source, tennis_consumer and admissions). Extract the exact
existing connection/type/transaction/text/row/attached/TEMP checks into a
private raw-file-path-string helper; do not skip any check. The old wrapper
calls that helper then Path exactly as before. Only `_check_footprint` uses
the validated raw string for native os.stat and os.path.dirname/free-space
calls, avoiding repeated main/companion Path parsing in the hot boundary.

All page/physical/journal/free/max_page/cache/mmap calculations and calls stay
in order. Companion existence retains Path.exists' exact current error policy:
ignore only ENOENT/ENOTDIR/EBADF/ELOOP, WinError21/123/1921 or ValueError; all
other errors propagate to the owning StorageIntegrityError. Do NOT use broad
os.path.exists (would mask PermissionError). Preserve exists followed by a
second stat and its race/error behavior, no cached metadata or one-stat grant.
No other footprint owner, schema, descriptor, generation, guard, iteration,
TracedConnection lifecycle, output bytes, persisted format or budget changes.

## TDD, acceptance, ownership

Implementer owns only refs.py, a new focused native-footprint regression file
and its report. Write genuine focused RED first; full-prefix original RED is
already retained separately. Cover unchanged cold Path return, exact-type
admission, all companion suffix bytes, ignored and nonignored errors, permission
denial, disappearance after positive existence, live free-space/physical changes,
and no Path parser calls in the hot footprint with real tracked SQLite.
Original memory test stays byte-identical with12000refs/4096block/1024chunks.
Run it cold, full chunks and owning neighbors in fresh offline processes.
Controller owns final identical combined-prefix memory comparison, independent
review, exact full-QA disposition, scoped Git checkpoint/release and VPS work.
No production/API/backup/cleanup or fullsuite rerun by implementer.
