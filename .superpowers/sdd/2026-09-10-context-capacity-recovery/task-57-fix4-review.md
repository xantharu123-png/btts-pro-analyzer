- **The proven optional NumPy `direct_url.json` probe must fall back as not-found without admitting unknown bytes.** — **ADDRESSED (SPEC).** The worker derives only the exact `direct_url.json` sibling of an already admitted `numpy-*.dist-info/METADATA` path and subtracts targets already present in the exact catalogue (`tests/native_context_chain_worker.py:119-136`). A read-only open of an uncatalogued derived target is recorded and rejected as `FileNotFoundError` before the operating-system open; write/create/truncate/append modes remain `ChainError`, while a catalogued target bypasses the exception and follows normal exact-file admission (`tests/native_context_chain_worker.py:141-177`). The actual-subprocess regression covers absent, present-but-unadmitted, and admitted states using `importlib.metadata.PathDistribution.read_text`, verifies catalogued contents, rejects direct uncatalogued reads and every required write mode, rejects sibling/unanchored/other-distribution aliases, and confirms retained bytes are unchanged (`tests/test_native_context_chain.py:217-284`).
- **Remaining rejected file access must report bounded path/event/flags context without additional file I/O.** — **ADDRESSED (SPEC).** The shared rejection path captures the audit event, a 512-character pathname prefix plus truncation bit, a SHA-256 of the full encoded pathname, and bounded signed-64-bit flags (or null), then raises without reopening or inspecting the target (`tests/native_context_chain_worker.py:141-176`). `failure_bytes` emits one ASCII-escaped line capped at 8192 bytes and is used by the worker failure boundary (`tests/native_context_chain_worker.py:20-37`, `tests/native_context_chain_worker.py:232-239`). The focused subprocess test observes the original audit event independently, rejects two real `os.open` calls including a long non-BMP path, matches event/actual flags/prefix/truncation/full-path digest, proves exactly one open event per rejection, and verifies two bounded parseable stderr records (`tests/test_native_context_chain.py:287-331`).

### New Breakage in the Fix Diff

None. No new Critical, Important, or Minor defect was found in the executable FIX4 delta.

### Out-of-Scope Observations

- The earlier guarded native ATP failure remains terminal retained evidence, but its stderr did not record the rejected pathname. The Root-supplied native NumPy source and exact absence observations establish mechanism parity, not direct proof that the prior native pathname was `direct_url.json`.
- No guarded FIX4 native retry has run. The post-fix portable import crossed the NumPy metadata phase and then correctly stopped on a local-only, unadmitted PyArrow cache probe; the sealed native inventory has no PyArrow. This incomplete portable result neither requires PyArrow admission nor proves native ATP/WTA completion.
- The package's `9007150` controller documentation, archived FIX3 review package, retained native evidence, ledger, and handoff changes are non-executable unchanged-area material for this scoped fix review.
- Native ATP-then-WTA execution/custody, terminal and resource evidence, full growth profiles, protected all-cost/global-C/B closure, restore, whole suite, main/VPS rollout, release, Task54-M1, and the prior platform-fixture MinorM1 remain open and are not certified here.

### Checks and Evidence Limits

- Read `task-57-brief.md`, `task-57-fix4-brief.md`, and the FIX4 report appendix through EOF.
- Read the complete immutable 308795-byte/4870-line package through EOF in consecutive bounded chunks and independently confirmed SHA-256 `2c14485fb54d31a756c3a6443416116e9672f653ddc7764a1a30fb6283c41722`.
- Independently hashchecked the final files: unchanged parent `1325881bed452574159568d6fba93dae6c091d7baf0ee2388adb86108e3038e8`, unchanged catalogue `93d38e46c17b9796088cfad66ea1667413b702b93f8310ac43b6e6ee7ac648f9`, worker `b05e45ab5ac2d2a76fedc88245ad76dd28c85f4eee7006d45c096a693ab989cd`, and test `b2ffb4539d081df0e7cbdd4204eb5b4948853ae02575003311ffcd538004ccb4`.
- Independently parsed retained `.pytest_tmp/task57-fix4-final-25.xml` as 36 tests, 0 failures, 0 errors, 0 skips, 9.433 seconds, and hashchecked it as `a0a3337736df5abc812fa308a8c020da862da72f5467f17d0ac2bb99e994dfe0`. The report also contains the exact focused RED/GREEN commands and intermediate 4-test outcomes. No test suite, native process, Git, server, network, or dependency command was run during this re-review.
- The native source/absence parity and original guarded-run counters are Root-supplied evidence. This review validates their stated boundary against the fix; it does not independently recreate server evidence or promote it into a native success claim.

### Spec and Quality Verdicts

**Spec compliance:** COMPLIANT for the scoped FIX4 requirements. The exception is exact, catalogue-anchored, non-admitting, and read-only; catalogued targets remain normally readable, writes and unrelated files remain fail-closed, and the diagnostic is bounded and performs no additional target I/O. Parent, catalogue, helpers, resource/accounting limits, child order, and product code are unchanged.

**Task quality:** APPROVED for this fix round. The implementation is localized and auditable, and the tests exercise actual stdlib metadata behavior plus the diagnostic's non-I/O and output-bound properties.

### Verdict

**Fix round:** All scoped findings addressed, no new Critical/Important breakage.
