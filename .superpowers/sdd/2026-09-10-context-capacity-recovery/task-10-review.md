# Task10 independent immutable delta review

Date: 2026-09-11. Verdict: **Findings — one P2; not approved yet.**

## Reviewed scope and identity

This is a bounded review of Task10 only, not a second whole-branch review.
Base `40d40147c9468bbe874f3b1cc90873c20911f7c6` -> candidate
`4a27fb98f2379866a90abf3031082ab9a0fd4bf4`.
The saved `.pytest_tmp/review-40d4014..4a27fb9.diff` hashes to
`256aa8178e4926238bb61394de4bf96f50c2abca62cfe0e5a68b453337ddaecd`.
The four changed paths are exactly the two checking modules, new dispatch test
module and implementation report. Candidate-to-working diff for the three
product/test paths is empty; immutable `git diff --check` passes.

Read the complete Task10 brief/report, the production delta and current
checking modules, new tests, original transaction implementation and relevant
canonical-encoding/cold-Tennis/witness owners and tests. Manual immutable
brief/review workflow used; no claim that disappeared skill tools ran.

Verified current SHA256 values:

```text
context_runtime_history_cache.py b1bdc92fcdf6683a7b2b27793515743f137caa59a73e812a540c8a96235c1552
context_runtime_inventory.py 55d54c7db12e7ceae92d8833857584ee63f4a0aa9abec0b7db68a3c681d8d785
tests/test_context_runtime_check_dispatch.py bc0b8c2bcd3db78b88859f3be7a7b4e45a210ff734ee5cace33940af86773929
context_runtime_transaction.py ecec258d9b67964da29b9da91859c5d80ed24100765b04e14db5269b8d4e8e5b
```

## Finding

### P2 — Recheck connection type before reusing the cursor after a callback

Locations: `context_runtime_inventory.py:91-95` and the equivalent
`context_runtime_history_cache.py:129-133`.

The outer fast-path guard verifies `type(connection) is TrackedConnection`,
but the guard after the first schema read does not. A supported SQLite trace
callback can change the connection's `__class__` to a layout-compatible
`TrackedConnection` subclass while the actual main PRAGMA executes. Python
permits this reassignment on this real SQLite connection. Class-level original
method identities, the instance dictionary and `row_factory` can all remain
unchanged. The candidate therefore reuses the first cursor for temp instead
of invoking the new subclass's `execute` override. The base executes that
override. An override raising `sqlite3.OperationalError` is silently bypassed
by the candidate, which returns a successful schema tuple instead.

This is a narrow adverse reentrancy case, not a claim that the ordinary native
input exercises class reassignment. It nevertheless violates the explicitly
required original connection-dispatch compatibility and the stated purpose
of the after-first-cookie guard. No product monkeypatch or fabricated schema
result is needed to reproduce it: both actual SQLite PRAGMAs execute on the
candidate. An existing callback changes the actual connection type.

Required repair: revalidate the exact connection type at both second-cookie
guards and take original `connection.execute` dispatch when it changed. Add
RED-first cases for both boundaries using the real trace callback, with a
delegating subclass override and an exception-producing override; retain
cleanup and one-cursor allocation for the ordinary exact route. Do not weaken
existing override/failure tests or change the protected transaction owner.

The new reentrancy matrix covers class-method replacement, instance-method
replacement, factories and recursive boundaries, but not dynamic connection
subclassing; its initial subclass matrix changes the type only before entry.
Thus the existing passing tests do not cover this transition.

## Independent execution

Working directory for every command:
`C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.

Fresh focused regression, exact candidate product/test bytes:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:VECLIB_MAXIMUM_THREADS='1'
$env:BLIS_NUM_THREADS='1'
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_context_runtime_check_dispatch.py tests/test_context_runtime_receipt_witness.py --basetemp=.pytest_tmp/task10-review-dispatch-witness-1
```

Result: **235 passed in 28.50s**, exit 0. Process completed and was reaped.
This includes all 117 new dispatch tests and the existing receipt-witness
module, with actual cold-validation, alias/canonical matching, before/after/
final/empty proof, source-failure, lifecycle, replacement and full-snapshot
regressions. No tests were edited or relaxed.

The independent base/candidate reproducer below was executed via the same
quality Python `-B -c` prefix. The command only reads base modules through
`git show`, executes them in ephemeral module namespaces, and uses in-memory
SQLite connections. It writes no source or helper file.

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -c 'import sqlite3, subprocess, types; import context_runtime_inventory as inv; import context_runtime_history_cache as hc; from context_runtime_transaction import TrackedConnection
base="40d40147c9468bbe874f3b1cc90873c20911f7c6"
mods={}
for name in ("context_runtime_inventory", "context_runtime_history_cache"):
 m=types.ModuleType("review_base_"+name); exec(compile(subprocess.check_output(["git","show",base+":"+name+".py"]),name,"exec"),m.__dict__); mods[name]=m
for boundary in ("inventory","cache"):
 for version in ("base","candidate"):
  calls=[]
  class ReentrantConnection(TrackedConnection):
   def execute(self,sql,*args,**kwargs):
    calls.append(sql)
    if sql=="PRAGMA temp.schema_version": raise sqlite3.OperationalError("second dispatch veto")
    return super().execute(sql,*args,**kwargs)
  conn=sqlite3.connect(":memory:",factory=TrackedConnection); conn.execute("BEGIN")
  receipts=inv.VerifiedReceiptMapping(conn); cache=hc.EncodedHistoryCache(receipts)
  if boundary=="inventory":
   if version=="base": receipts=mods["context_runtime_inventory"].VerifiedReceiptMapping(conn)
   action=receipts._inventory_stamp
  else:
   action=(mods["context_runtime_history_cache"].EncodedHistoryCache._schema_versions.__get__(cache) if version=="base" else cache._schema_versions)
  def trace(sql):
   if sql=="PRAGMA main.schema_version": conn.__class__=ReentrantConnection
  conn.set_trace_callback(trace)
  try: print(boundary,version,"RETURN",action(),"override_calls",calls)
  except Exception as error: print(boundary,version,type(error).__name__,str(error),"override_calls",calls)
  finally: conn.set_trace_callback(None); conn.close()'
```

Observed output, exit 0:

```text
inventory base OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
inventory candidate RETURN (1, 0, 0, 0) override_calls []
cache base OperationalError second dispatch veto override_calls ['PRAGMA temp.schema_version']
cache candidate RETURN (0, 0) override_calls []
```

## Other review conclusions and boundaries

No additional actionable defect found in this delta. The plain-JSON loop
preserves exact builtin kinds, key-before-value order and first-false behavior;
literal canonical-byte equality remains authoritative. Nonfinite/recursive
comparison errors and aliases still defer to the unchanged actual cold owner.
The single local cursor keeps main-then-temp tracked statements and the
inventory's generation/total-change evaluation order. Ordinary exact-route
success/failure cleanup, double-error chaining and release after unwinding are
covered by the executed tests. The original-dispatch fallback for subclasses
present before entry and covered method/factory changes remains intact; the
finding is specifically the missing dynamic-type recheck.

The immutable delta changes no caps, cold-source validator, feature math,
predictor, helper, protected transaction module or proof-boundary call sites.
No arbitrary-growth/resource improvement is inferred from allocation tests.
No fullsuite, SSH, network, native acceptance, deployment, Git index changes,
product/test/helper edits or subagents were performed by this reviewer. Only
this named report is authored; controller documentation WIP is preserved.

Root still owns a corrected immutable delta/review, exact current-input native
FIRST, meaningful consumer-growth controls, historical/native platform and
DAC/race checks, final fullsuite, fresh backup/actual restore/HMAC and latest
data recheck. Latest supplied actual 30-snapshot acceptance remains failed at
the prior source until superseded by a complete exact-source result. Existing
fullsuite or this 235-test result is not release approval. This review closes
none of the unrelated Cricket/A0/P4b3/five-sport or daily Tennis HTTP failure
work, and authorizes no publication/deployment.
