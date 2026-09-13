# Task 59 report: deterministic bounded seven-day QA profile inputs

## Declared data shapes (before implementation)

The module will expose frozen scalar/byte-backed values only:

- `TourSeed(tour, tournament_id, grouping_slug, surface, best_of, indoor,
  _fixture_bytes)`. `native_fixture` is a property returning a new decoded copy;
  mutable caller input is never retained as authority.
- `GrowthScheduleEntry(ordinal, day_index, day_ordinal, tour, native_id,
  observed_at, receive_bucket, consumer_index, key_index)`. Every field is an
  immutable scalar or `datetime`.
- `GrowthConsumerDescriptor(ordinal, day_index, consumer_index, key_index,
  tour, tournament_id, grouping_slug, observed_at, cutoff, created_at,
  surface, best_of, indoor, _fixture_bytes)`. `native_fixture` returns a fresh
  decoded copy.
- `GrowthTargets(final_receipts_target, final_originals_target,
  final_snapshots_target, final_tour_cutoff_keys_target)`. These are planning
  targets, never observations.
- `GrowthProfile(kind, baseline_sha256, start_at, first_native_id, seeds,
  _consumers, targets, days, additions_per_day, total_additions)`. It stores at
  most two seeds and 168 descriptors. Schedule and receipt streams are derived;
  no 490,000-row/ID history is retained.

Implementation and evidence will be recorded below after the required RED.

## Implemented contract and exact schedule

`build_growth_profile(kind, *, baseline_sha256, start_at, first_native_id,
atp_fixture, wta_fixture)` accepts only `atp-heavy`, `mixed`, and `burst`.
It requires a lowercase SHA-256 label, an aware zero-offset UTC `datetime`, and
a positive exact `int` whose inclusive 490,000-ID range fits signed 64-bit.
The ATP seed is mandatory for all profiles and the WTA seed for `mixed`; WTA
may be omitted for the other two. Known clock overflow is rejected while
building the profile. Real `normalize_tennis_status` validates detached seed
bytes before any iterator can escape. It must produce exactly one intact
scheduled status, and the real consumer-required player display names and
surface must also be present.

The fixed schedule is:

- Seven days, exactly 70,000 rows per day and 490,000 total. Native event IDs
  are `first_native_id + ordinal`, for ordinal 0 through 489,999 inclusive.
- Consumer rows are exactly daily positions 69,976 through 69,999, inside the
  70,000. `atp-heavy` and `burst` are entirely ATP: consumer indices 0-19 form
  ten two-consumer keys and 20-23 form four single-consumer keys.
- `mixed` positions 0-34,987 plus consumer indices 0-11 are ATP; positions
  34,988-69,975 plus consumer indices 12-23 are WTA. Per tour, indices 0-9
  form five pairs and 10-11 form two singles. This gives exactly 35,000 rows,
  12 consumers and seven keys per tour/day.
- Non-burst receive clocks are `start_at + day + day_ordinal microseconds`, so
  insertion is strictly chronological and mixed clocks are globally distinct.
- Burst has ten 7,000-row receive buckets/day. Insertion uses bucket clock
  order `(0,2,1,4,3,6,5,8,7,9)` seconds from the day anchor. Thus each clock
  has 7,000 ties and real backward transitions after daily positions 13,999,
  27,999, 41,999 and 55,999. All 24 consumers occupy the final bucket.
- Consumer key clocks use a global daily key index 0-13. Non-burst cutoff is
  day anchor + one hour + key-index seconds; burst cutoff is day anchor +
  10 + key-index seconds. Scheduled start is cutoff + one hour and creation is
  cutoff + one microsecond. Therefore receive <= cutoff < scheduled start and
  creation >= cutoff. Tournament is `189-2026`; grouping is `mens-singles` or
  `womens-singles`; `surface` preserves the seed; `best_of=3`, `indoor=None`.
- Every ordinary row is a real normalizable scheduled fixture at day anchor +
  18 hours. Its two synthetic player IDs stay in the bounded range
  1,000,000,001-1,002,000,000 and its names have fixed bounded length.
  Consumer fixtures preserve supplied player IDs and display names.

`iter_schedule()` derives cheap immutable metadata for all additions.
`iter_receipts(start=0, stop=None)` validates the requested half-open range
before returning an iterator and invokes unchanged `normalize_tennis_status`
for every emitted row. A diagnostic slice is only a slice. `consumers()`
returns exactly 168 frozen descriptors. Caller mutation of the original seed,
a returned fixture copy, or an emitted normalized record cannot affect future
emissions.

The four `GrowthTargets` values are explicitly planning targets from the
approved brief: 590,553 final receipts, 199 final Originals, 199 final
snapshots and 114 final tour/cutoff keys. They are not observed counts.

The representative test uses the freshly proposed large namespace beginning
at `8000000000000000000` and UTC start `2026-09-12T00:00:00+00:00`. This only
proves that the generator and actual normalizer/physical decoder handle that
valid range; the separate baseline metadata observation and later owner retain
all collision/baseline authority.

## TDD and focused verification evidence

The applicable `test-driven-development/SKILL.md` and its complete
`writing-good-tests.md` reference were read before coding. Tests were written
first. An initial attempt with the copied `.codex_test_venv` exited 1 before
pytest collection because that environment exposes only a namespace named
`pytest` (`No module named pytest.__main__`). It is environment discovery, not
RED evidence. The existing task-local QA Python was then identified as
`.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, Python 3.12 with pytest
9.1.1.

Valid RED command (PowerShell environment assignments shown verbatim):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_growth_profile.py --basetemp '.pytest_tmp/task59-red-bt-8f20c2' --junitxml '.pytest_tmp/task59-red-8f20c2.xml'
```

Actual RED: outer/pytest exit 2; collection failed only because
`context_growth_profile` did not exist (`ModuleNotFoundError`), with one
collection error in 0.50s. This was the expected missing-feature failure.

The first implementation check used the same disabled plugin/bytecode/cache
settings and a 120-second `subprocess.Popen(...).communicate(timeout=120)`
wrapper with fresh `task59-final-bt-1d947c` / `task59-final-1d947c.xml` paths.
Actual child/outer exit 1: 26 passed and three failed in 9.83s. The failures
identified two test-harness mistakes, not a changed contract: the asserted
burst transition offsets did not match the declared fixed bucket order, and
the invalid-first-ID assertion omitted the deliberately raised `TypeError`.
Only those expectations were corrected before the passing run; the suite was
therefore not rerun unchanged.

Final focused command executed by the bounded wrapper:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -c '<subprocess wrapper below>'

# Child command constructed by that wrapper:
.pytest_tmp/qa-python312-c-01/Scripts/python.exe -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_growth_profile.py --basetemp=.pytest_tmp/task59-final-bt-44d5bb --junitxml=.pytest_tmp/task59-final-44d5bb.xml

# Wrapper behavior:
subprocess.Popen(child_command, stdout=PIPE, stderr=PIPE, text=True,
                 env=os.environ.copy()).communicate(timeout=120)
```

Authoritative exact executed wrapper command (this supplies the complete value
summarized by the placeholder above):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; & '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -c 'import datetime,json,os,subprocess,sys,time; cmd=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider","-o","junit_family=xunit1","tests/test_context_growth_profile.py","--basetemp=.pytest_tmp/task59-final-bt-44d5bb","--junitxml=.pytest_tmp/task59-final-44d5bb.xml"]; started=datetime.datetime.now(datetime.timezone.utc); begin=time.monotonic(); p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy()); print("TASK59_SESSION_START="+json.dumps({"wrapper_pid":os.getpid(),"child_pid":p.pid,"started_at":started.isoformat(),"timeout_seconds":120,"command":cmd},separators=(",",":"))); timed_out=False
try: out,err=p.communicate(timeout=120)
except subprocess.TimeoutExpired: timed_out=True; p.kill(); out,err=p.communicate()
ended=datetime.datetime.now(datetime.timezone.utc); print("TASK59_STDOUT_BEGIN"); print(out,end=""); print("TASK59_STDOUT_END"); print("TASK59_STDERR_BEGIN"); print(err,end=""); print("TASK59_STDERR_END"); print("TASK59_SESSION_END="+json.dumps({"child_exit":p.returncode,"timed_out":timed_out,"ended_at":ended.isoformat(),"wall_seconds":round(time.monotonic()-begin,6)},separators=(",",":"))); sys.exit(124 if timed_out else p.returncode)' ; $code=$LASTEXITCODE; Write-Output "TASK59_OUTER_EXIT=$code"; exit $code
```

Exact captured terminal text from that execution:

```text
TASK59_SESSION_START={"wrapper_pid":128092,"child_pid":128172,"started_at":"2026-09-13T08:09:43.369268+00:00","timeout_seconds":120,"command":["C:\\Projekt\\BetBoy\\betboy-app\\.worktrees\\context-capacity-recovery-20260910\\.pytest_tmp\\qa-python312-c-01\\Scripts\\python.exe","-B","-m","pytest","-q","-p","no:cacheprovider","-o","junit_family=xunit1","tests/test_context_growth_profile.py","--basetemp=.pytest_tmp/task59-final-bt-44d5bb","--junitxml=.pytest_tmp/task59-final-44d5bb.xml"]}
TASK59_STDOUT_BEGIN
.............................                                            [100%]
29 passed in 9.86s
TASK59_STDOUT_END
TASK59_STDERR_BEGIN
TASK59_STDERR_END
TASK59_SESSION_END={"child_exit":0,"timed_out":false,"ended_at":"2026-09-13T08:09:53.567959+00:00","wall_seconds":10.203}
TASK59_OUTER_EXIT=0
```

The retained execution-tool completion envelope was: chunk
`475741`, tool exit `0`, tool wall `10.4403858` seconds, and reported original
output token count `205`. The wrapper did not capture child CPU time, peak RSS,
peak address space, or separate stdout/stderr byte counts; those fields are
unavailable and are not inferred.

Captured session metadata:

| Field | Actual value |
| --- | --- |
| Wrapper PID / child PID | `128092` / `128172` |
| Start UTC | `2026-09-13T08:09:43.369268+00:00` |
| End UTC | `2026-09-13T08:09:53.567959+00:00` |
| Wrapper-observed wall | `10.203` seconds |
| Hard subprocess timeout | `120` seconds |
| Timed out | `false` |
| Child exit / outer exit | `0` / `0` |
| stdout | `29 passed in 9.86s` (29 dots, `[100%]`) |
| stderr | empty |

The final tests independently enumerate all three complete cheap schedules
with bounded counters; verify daily/tour/consumer/key multiplicities,
sequential ordinal/large native-ID mapping, burst ties/transitions, cutoff
grouping, repeatability, mutation isolation, slices, invalid inputs and clock
overflow; and pass representative boundaries plus every one of the 168
consumer statuses in each profile through actual `normalize_tennis_status`,
canonical persisted bytes, physical `context_observations._decode_receipt`,
and `validate_tennis_status_record`. They deliberately do not normalize all
1.47 million planned rows.

## Tested byte hashes

| File | Bytes | SHA-256 of final tested bytes |
| --- | ---: | --- |
| `tests/context_growth_profile.py` | 14,269 | `dd48769d00d8080c6fc542be88a3e5f28d0a54986af1c9ab2ac2984b643fad42` |
| `tests/test_context_growth_profile.py` | 13,555 | `08232b3998a227f1b5eee16551cc593dc9611229105f5d7e0e74cd0150e8bebb` |
| `.pytest_tmp/task59-red-8f20c2.xml` | 1,083 | `dadb4808365e4ffd900c30f3a6e9705d24561f945640138efc8e79676592f376` |
| `.pytest_tmp/task59-final-1d947c.xml` | 13,068 | `1a762c420dc1484646cc35e52c174bfecab65be914fd618522be55e1648e5971` |
| `.pytest_tmp/task59-final-44d5bb.xml` | 6,175 | `d5c32e12efa541650a4e911fa5e8a267327e455743175777d133e87ed35eeb71` |

The report SHA is returned externally after this final append because a file
cannot embed its own stable hash.

## Limits, exclusions and writer return

This unit result is not the future 590,553-receipt stored/native profile pass.
It does not establish baseline sealing, old/new collision freedom, complete
corpus or preservation, Source/D2 authority, model-state/native-state binding,
199 created Originals, 199 snapshots, 114 stored keys, filesystem ownership,
CPU/RSS/AS/output/global-C limits, B, restore, empirical approval, deployment
or release. No provider, random source, current-clock read, filesystem owner,
Git/index, network, install, server, product source, existing test, frozen spec,
guard, catalogue, limit or unrelated report was changed. Inherited untracked
QA directories were preserved. No unchanged whole suite was run.

Task 59's sole-writer authority is explicitly returned to Root. Root alone now
owns independent review, Git/index/commit and the subsequent full-growth native
integration.

## Fix round 1/5 — explicit closed tour-seed prediction inputs

This addendum supersedes only the earlier report statements that described a
bare native fixture, fixed tournament `189-2026`, or invented consumer
`best_of=3` / `indoor=None`. Finding I1 was accepted verbatim:

> the seed contract omits caller-supplied best_of and indoor, then silently
> invents 3 and None. Consequently the generator cannot represent or preserve
> an indoor fixture or best-of-five prediction input, despite the brief
> requiring explicit prediction inputs. Tests cement the substitution by
> supplying no such inputs at tests/test_context_growth_profile.py:34-50 and
> asserting the constants at:150-152. Define a precise tour-seed input shape
> carrying the native competition plus surface,best_of,indoor; validate/freeze
> it and copy those values unchanged into every descriptor, with tests for
> non-default ATP and WTA values.

The binding seed input is now a closed mapping with exactly these five required
keys and no others:

```python
{
    "competition": dict,       # actual scheduled native singles competition
    "tournament_id": str,     # validated by real status normalization
    "surface": "Hard" | "Clay" | "Grass" | "Carpet" | None,
    "best_of": 3 | 5,         # exact int; bool is rejected
    "indoor": bool | None,    # explicit key; None is a supplied value
}
```

Grouping remains derived solely from tour (`mens-singles` / `womens-singles`).
The full mapping is detached through canonical bytes before inspection; only
the native competition is retained as immutable bytes, while tournament,
surface, best-of and indoor are validated immutable scalars in `TourSeed`.
`native_fixture` still yields a fresh competition copy. Every one of the 168
descriptors copies the four supplied tournament/prediction values unchanged.
No compatibility path for the unreleased bare fixture exists.

The tests now use ATP `tournament_id=901-2026`, `surface=Clay`, `best_of=5`,
`indoor=True`, and mixed-profile WTA `tournament_id=902-2026`, `surface=Grass`,
`best_of=3`, `indoor=False`. These non-default values flow through all normal
consumer and physical decoder/source-validator checks. A separate ATP case
proves explicit `surface=None` and `indoor=None`. Caller mutation covers the
nested competition plus all four scalar inputs. Parameterized boundaries reject
every omitted key, an unknown key, invalid surface values, bool/4 best-of,
non-bool indoor and an invalid tournament before an iterator is returned.
All original counts, clocks, event IDs, player IDs/names and isolation behavior
remain unchanged.

### Fix-round TDD evidence

Focused RED exact command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; & '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -c 'import datetime,json,os,subprocess,sys,time; cmd=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider","-o","junit_family=xunit1","tests/test_context_growth_profile.py","-k","explicit_none_prediction_inputs_are_preserved_without_defaults","--basetemp=.pytest_tmp/task59-fix1-red-bt-a73d2e","--junitxml=.pytest_tmp/task59-fix1-red-a73d2e.xml"]; started=datetime.datetime.now(datetime.timezone.utc); begin=time.monotonic(); p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy()); print("TASK59_FIX1_RED_SESSION_START="+json.dumps({"wrapper_pid":os.getpid(),"child_pid":p.pid,"started_at":started.isoformat(),"timeout_seconds":60,"command":cmd},separators=(",",":"))); timed_out=False
try: out,err=p.communicate(timeout=60)
except subprocess.TimeoutExpired: timed_out=True; p.kill(); out,err=p.communicate()
ended=datetime.datetime.now(datetime.timezone.utc); print("TASK59_FIX1_RED_STDOUT_BEGIN"); print(out,end=""); print("TASK59_FIX1_RED_STDOUT_END"); print("TASK59_FIX1_RED_STDERR_BEGIN"); print(err,end=""); print("TASK59_FIX1_RED_STDERR_END"); print("TASK59_FIX1_RED_SESSION_END="+json.dumps({"child_exit":p.returncode,"timed_out":timed_out,"ended_at":ended.isoformat(),"wall_seconds":round(time.monotonic()-begin,6)},separators=(",",":"))); sys.exit(124 if timed_out else p.returncode)' ; $code=$LASTEXITCODE; Write-Output "TASK59_FIX1_RED_OUTER_EXIT=$code"; exit $code
```

Captured RED terminal summary: wrapper PID `142936`, child PID `141980`, start
`2026-09-13T08:26:43.976879+00:00`, end
`2026-09-13T08:26:44.624783+00:00`, wrapper wall `0.64` seconds, timeout 60,
`timed_out=false`, child/outer exit `1/1`, stderr empty. Stdout reported
`1 failed, 41 deselected in 0.28s`; the expected failure was the old `_seed`
passing the new closed mapping directly to `normalize_tennis_status`, whose real
native `_id` rejected missing competition ID `None`. Execution-tool envelope:
chunk `31ba2d`, wall `0.8919907` seconds, exit 1, original token count 698.

Corrected full-module GREEN exact command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; & '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -c 'import datetime,json,os,subprocess,sys,time; cmd=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider","-o","junit_family=xunit1","tests/test_context_growth_profile.py","--basetemp=.pytest_tmp/task59-fix1-final-bt-ec721f","--junitxml=.pytest_tmp/task59-fix1-final-ec721f.xml"]; started=datetime.datetime.now(datetime.timezone.utc); begin=time.monotonic(); p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy()); print("TASK59_FIX1_SESSION_START="+json.dumps({"wrapper_pid":os.getpid(),"child_pid":p.pid,"started_at":started.isoformat(),"timeout_seconds":120,"command":cmd},separators=(",",":"))); timed_out=False
try: out,err=p.communicate(timeout=120)
except subprocess.TimeoutExpired: timed_out=True; p.kill(); out,err=p.communicate()
ended=datetime.datetime.now(datetime.timezone.utc); print("TASK59_FIX1_STDOUT_BEGIN"); print(out,end=""); print("TASK59_FIX1_STDOUT_END"); print("TASK59_FIX1_STDERR_BEGIN"); print(err,end=""); print("TASK59_FIX1_STDERR_END"); print("TASK59_FIX1_SESSION_END="+json.dumps({"child_exit":p.returncode,"timed_out":timed_out,"ended_at":ended.isoformat(),"wall_seconds":round(time.monotonic()-begin,6)},separators=(",",":"))); sys.exit(124 if timed_out else p.returncode)' ; $code=$LASTEXITCODE; Write-Output "TASK59_FIX1_OUTER_EXIT=$code"; exit $code
```

Exact captured GREEN terminal text:

```text
TASK59_FIX1_SESSION_START={"wrapper_pid":140220,"child_pid":139120,"started_at":"2026-09-13T08:27:41.165033+00:00","timeout_seconds":120,"command":["C:\\Projekt\\BetBoy\\betboy-app\\.worktrees\\context-capacity-recovery-20260910\\.pytest_tmp\\qa-python312-c-01\\Scripts\\python.exe","-B","-m","pytest","-q","-p","no:cacheprovider","-o","junit_family=xunit1","tests/test_context_growth_profile.py","--basetemp=.pytest_tmp/task59-fix1-final-bt-ec721f","--junitxml=.pytest_tmp/task59-fix1-final-ec721f.xml"]}
TASK59_FIX1_STDOUT_BEGIN
..........................................                               [100%]
42 passed in 9.78s
TASK59_FIX1_STDOUT_END
TASK59_FIX1_STDERR_BEGIN
TASK59_FIX1_STDERR_END
TASK59_FIX1_SESSION_END={"child_exit":0,"timed_out":false,"ended_at":"2026-09-13T08:27:51.315305+00:00","wall_seconds":10.156}
TASK59_FIX1_OUTER_EXIT=0
```

Execution-tool envelope: chunk `535166`, wall `10.3895225` seconds, exit 0,
original token count 216. No CPU, RSS or AS measurements were captured by this
unit-test wrapper; none are inferred.

| Fix-round file | Bytes | SHA-256 of corrected tested bytes |
| --- | ---: | --- |
| `tests/context_growth_profile.py` | 15,382 | `584bd2c9c14aee3abe5b5dc2f537ebc25914cd7d63b7dabf6d0abb306798e2c9` |
| `tests/test_context_growth_profile.py` | 16,481 | `bf917cebeb86939d351e979ea5d4f23213566adafba9050c41a2974932d69829` |
| `.pytest_tmp/task59-fix1-red-a73d2e.xml` | 2,039 | `29f082a24f67ab576f6399e41703097ff0c9f3d34dd4689d5244dfb2e9bdee52` |
| `.pytest_tmp/task59-fix1-final-ec721f.xml` | 9,028 | `de7d64682098d5cb739b5e74473eef7a3babb4f41985ae2bc65e7559acc69ee6` |

No product/existing-test/other-report, Git/index, server, network or package was
touched, and no unchanged suite was rerun. Task 59 fix-round 1/5 sole-writer
authority is explicitly returned to Root for commit and scoped re-review.
