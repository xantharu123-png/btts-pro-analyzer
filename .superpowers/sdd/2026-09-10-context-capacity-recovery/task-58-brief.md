## Task 58: Complete the actual dual-reader timezone binding prerequisite

**Ruling and scope:** Task57's fifth scoped fix is independently approved but
its fourth actual native attempt still stops before Task54. The two canonical
timezone originals and readonly copies are independently verified. A bounded
ordinary-user actual import diagnostic proves a distinct reader:
`pandas/_libs/tslibs/timezones.pyx:43 -> dateutil/tz/tz.py:1557,1640,464 -> open
/usr/share/zoneinfo/UTC`. Stdlib ZoneInfo binding cannot configure dateutil.
This is a load-bearing execution-contract omission, not grounds for another
Task57 blind allowlist/fix round or for accepting its native result. Complete
this smallest dependency-binding prerequisite, then rerun the unchanged real
Task54 acceptance via Root. No new system-file permission, dependency install,
arbitrary importer/reader shim, altered clock/prediction or resource relaxation.

**Read first:** original task-57-brief.md and the FIX5 finding/ruling sections
of task-57-fix5-brief.md in the current plan's SDD directory. Read final FIX5
report appendix, not earlier fix iterations. Exact actual diagnostic script and
result are `evidence/task57-timezone-route-diagnostic.py` (SHA
50bfe280658c57c95e3528909c917cfb8b8da0ec1f0bca9f7846eeaa75c1c216) and
`evidence/task57-timezone-route-diagnostic-01.json` (SHA
bf49a28b4b6eda232da27fc0bc7b4e6d9968235bf87b8166f07be6f408b067a7).
It imported only Pandas with the real sealed worker audit/binding, ordinary
UID1000/CPU15/AS2GiB/wall25; it is not guarded native acceptance. Root inspected
the local dateutil/tz/tz.py bytes; SHA
1149c474c7de4e15e263a978b21f7205a6d9eb7fcf3b3cb4d734ac87db619f5a exactly
matches the actual native catalogue and sealed file. Lines1460-67 configure
TZPATHS/TZFILES; gettz has cache_clear; missing-key fallback loads the bundled
dateutil.zoneinfo archive. That archive is already catalogued as a dependency,
so generic dependency admission alone does NOT prevent alternative timezone
data use. Inspect the actual relevant reader implementation before editing.

**Owned files:** only `tests/native_context_chain_worker.py`,
`tests/test_native_context_chain.py`, new focused
`tests/test_native_context_timezones.py` if necessary, and append/write
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-58-report.md`.
Declare exact edits first. Parent/catalogue/helpers/Task54/product/spec bytes
stay unchanged. No Git/index/commit/push/server/network/install/delete or
subagents by the writer. Root owns all those operations and native diagnosis.

**Binding implementation contract:**

1. Keep guard/kernel verification and the existing exact file audit installed
   before any third-party or product imports. Configure both real readers
   before Pandas/product import: stdlib ZoneInfo retains its current exact
   TZPATH/cache binding; the already admitted dateutil reader must use only
   that same sealed two-key directory, no local/system TZFILES, and clear its
   actual cache. Setting its existing path configuration is permitted;
   replacing gettz/nocache/tzfile, monkeypatching Pandas UTC, seeding fabricated
   timezone objects, custom import machinery or suppressing errors is not.
   Reject preloaded reader/fallback state rather than claiming it was rebased.
   Make dependency-path availability/order explicit and closed. No dateutil
   import in the clean privileged parent or before the worker guard/audit.
2. Preserve the exact two records and source/copy size/hash/custody/accounting
   contract: Europe/Zurich1909bytes and UTC114bytes, all native original/copy
   hashes/owners/permissions remain those of FIX5. No new record/package/key.
   Deny dateutil's bundled-zone fallback file/module use even though its bytes
   occur inside the existing dependency catalogue; exact-file denials must
   cover the real resource-loader route rather than rely solely on import
   audit events. No fallback-cache read or silent alternative source. Preserve
   normal numeric timezone/UTC/DST arithmetic; do not introduce product limits
   on the set of user-selectable dates or sports.
3. Keep actual Task54 invocation, Source/D2/History/features/consumer/rollback,
   kernel guard/readback, exact-copy/source rechecks and every existing fixed
   bound unchanged: parent90CPU, ATP/WTA90CPU each, retained300CPU, total600wall,
   AS2GiB/RSS<1GiB/output1MiB,4GiB active/8GiB new work/4GiB actual free reserve.
   This diagnostic is still not protected whole-C/B accounting or transitive
   runtime closure. No full-growth/empirical/release claim.

**TDD and evidence:** Reproduce real dateutil gettz UTC trying the original
system path after only ZoneInfo binding, then prove both real readers read
the same sealed files and agree for UTC/Zurich winter/summer/fold. Test actual
missing-key/bundled-resource fallback with bytes present and otherwise admitted,
unknown/system/alias/write denials, preloaded/cached reader rejection, actual
guard -> audit -> dependency configuration -> product ordering. No fabricated
reader or success validator; real subprocesses with timeouts and retained fresh
artifacts. Reuse legitimate existing TZif fixture bytes. Local PyArrow remains
a known unrelated import difference: do not install/admit it or report a
partial local Pandas import as native/full Task54 success. If a Linux-specific
reader route cannot be demonstrated portably, state exactly what the existing
actual diagnostic proves and leave full native execution to Root.

Run focused tests while changing, then the amended harness/timezone modules
once final with the existing QA Python, plugin autoload/bytecode/cache disabled,
fresh retained basetemp/XML and a real subprocess timeout. No unchanged full
product/guard suite or whole repository run. Report exact RED/GREEN commands,
results, byte hashes, known limitations and explicit sole-writer return. Root
will commit, obtain a new task-scoped independent spec/quality review, archive
the exact diff, push the repair branch, and run the unchanged isolated native
chain with a fresh immutable archive/catalogue/stdin and complete readback.
