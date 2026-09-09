# Independent D3 pure-transport review — 9 September 2026

## Verdict

**Changes required: one P2 exact-binding finding, six reproducible RED cases.**
The controller has independently read and confirmed all six probes. A narrow
fix is to be prepared separately, not in the frozen target during this review.
No numerical probability change, source qualification, empirical bypass or
live consumer deployment has been demonstrated by this finding.

Target worktree:
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`.
Starting HEAD: `4d332249594107572877f7833e058bd07afdf60e`.
All four target source/test/audit/ruling hashes were checked at entry and again
after the independent tests and are unchanged. The surrounding Root worktree
contains unrelated active WIP; it is **not represented as Git-clean**. That WIP,
including football capture, workers and privileged staging, was neither reviewed
nor modified here. Only this ignored `.pytest_tmp` directory was written.

## Finding D3-R1 — mathematical equality is weaker than the promised exact copy binding

Priority P2. Owning location: `context_transport.py:216-226` in `_validate_payload`.

The validator compares stored copies of original input fields using Python
`!=`, delegates the role's used/base-or-comparison equality to the generic B3
result validator, and also checks each recomputed delta using numeric equality.
Those comparisons conflate integers and floats, and positive/negative zero.
This means the explicit full original payload can retain `2.0`, while its
supposedly exact `base_params` or `used_params` copy contains integer `2`.
Similarly, a genuinely calculated delta `0.0` may be replaced by `0` or `-0.0`.

Actual frozen-code reproductions:

- A valid B5 football payload has original `home_lambda: 2.0`. Changing only
  `result.base_params`, only `result.used_params`, or both to integer `2`
  remains accepted by `validate_context_payload` against the unchanged original
  Base and the same input key. These are three independent RED cases.
- A valid no-effect B7 winner payload produces canonical delta bytes `0.0`.
  Changing them to integer `0` or float `-0.0` remains accepted. Two RED cases.
- With a newly calculated key-bound payload reference, the lightweight reader
  returns `{"away_lambda":1.0,"home_lambda":2}` although the bound original
  remains `{"away_lambda":1.0,"home_lambda":2.0}`. One RED case. The new
  reference is expressly public transport identity, not A1/D2 proof.

These are six manifestations of one exact-copy boundary issue, **not six
separate findings**. The original probability is unchanged. The original
unchanged consumer payload digest rejects a changed payload, and the full
owning `replay_context_payload` also rejects these scalar substitutions; both
are independently green controls. The issue is confined to advertised exact
input/used/delta copy validation, including its light read branch.

Recommended narrow fix, as confirmed by the controller: compare each copied
expected input, the role-selected used parameters/markets, and the complete
recomputed delta mapping by `canonical_bytes`. Do not normalize/rewrite the
original values, widen numeric tolerances, or introduce a fit on the light read
path. Genuine original endpoints and even an original signed zero must retain
their own original bytes; changing only a copied field is different.

Frozen repro locations:

- `test_independent_transport.py:35`: original/used JSON numeric type (3 cases).
- `test_independent_transport.py:51`: computed zero delta representations (2).
- `test_independent_transport.py:61`: light projection (1).

## Independent runs

Python:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
All invocations used `-B -m pytest -q -p no:cacheprovider` and distinct temporary
database directories. Both new probe files remain unchanged after their first
completed execution; no failing assertion or source was relaxed.

| Run | Actual result | Time | Artifact |
| --- | --- | --- | --- |
| Original independent probes | **6 failed, 35 passed** | 2.24 s | `run-01.xml` |
| Additional bounded controls | **18 passed** | 1.23 s | `controls-01.xml` |
| Combined frozen packet | **6 failed, 53 passed** | 2.66 s | `combined-01.xml` |
| Existing affected regression | **836 passed** | 30.25 s | `focus-01.xml` |

The existing affected run explicitly covered:
`test_context_transport.py`, `test_context_copy.py`, `test_context_snapshots.py`,
`test_context_contracts.py`, `test_tennis_context_model.py`,
`test_football_context_model.py`, and `test_basketball_context.py`.
There were no skips in this focused run. The controller's historical full
4351/18/97 run is **not relabelled independent reviewer evidence**. A new full
run of unrelated changing Root WIP was deliberately not attempted.

Reproduce from the target worktree with a fresh basetemp:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider .pytest_tmp/d3-transport-independent-20260909/test_independent_transport.py .pytest_tmp/d3-transport-independent-20260909/test_transport_controls.py --basetemp=.pytest_tmp/d3-transport-independent-20260909/rereview-new
```

## Green controls and scope separation

- Actual owning B5/B7/C2 laws execute in the affected regression. New independent
  B7 numerical overflow/saturation controls fall back to unchanged Base with
  a typed limitation; changing the effect body without its original hash is
  corruption and does not masquerade as missing context.
- A valid but only inspected foreign-family effect retains its identity and
  produces no comparison or approval. Future training, missing input states,
  different coverage and different format do not inherit an application.
- Actual changed/nonfinite/boolean/null used probabilities and malformed inner
  Base/Event/Feature/Result objects are rejected with the contract error type.
  Reference ordering, membership, bad digest types and closed price fields
  are tested. Original 0/0.0/-0.0/1/1.0 winner bases retain exact original bytes
  without inventing an effect.
- The complete externally supplied effect and approval envelopes must match
  the embedded identities. Synthetic hand-built approvals are used **only** to
  test this CPU transport's scope and role; they are not actual D2 approvals.
- Real local B3 SQLite roundtrips cover absent, experimental and synthetically
  applied roles. Two consumers share the same immutable reference and exact
  underlying distribution, their returned dictionaries are detached, and
  price variables remain outside the API. Repeated reads create one row.
- The key can be built from the complete input descriptor **before** running
  an owning comparison. Four concurrent threads/eight actual SQLite requests
  invoke the owning comparison exactly once, and subsequent card projections
  invoke none. This demonstrates B3 CPU once-only, **not** provider/base/feature/
  empirical-resolution once-only work; fixture construction occurs upstream.
- A real SQLite changed-key, TEXT-instead-of-BLOB or incorrect digest fails
  without recalculation. A modified comparison with a recomputed SQL payload
  digest fails the old consumer reference and fails owning numerical replay.
- A rehashed, structurally coherent but numerically fabricated comparison can
  pass the intentionally weaker structural reader when also given an untrusted
  new reference. That is **not an additional finding**: the contract expressly
  leaves actual law replay/publication and source/approval resolution elsewhere.
  It still cannot change an unapproved comparison into the used distribution;
  independent full-law replay rejects it.
- Actual C2 recipe, context effect, B2 fitter and B1 lookup spies all remain
  uncalled during `project_context_market`. Full preparation/reference building
  and audit may validate the owning Base recipe; the light projection does not.

## Unfinished boundaries — not claimed by this review

Read completely: `context_transport.py`, its permanent test file, the full D3
audit, Task18 controller rulings and Task18 brief. Reviewed the relevant actual
B3 key/persistence/selection, shared parameter/result contracts and owning
football/tennis/basketball helpers. No currently changing football capture
source, UI, worker, price, money, privileged stage or provider integration was
reviewed or changed.

New genuine provider/source captures: **0**. New API/VPS/SSH/deployment/push
actions: **0**. These tests use synthetic frozen sport inputs and actual local
SQLite transport. Actual A1/B1 receipt resolution, source reconstruction,
native causal eligibility, real D2 reports/approval, and D4 source/feature replay
remain caller-owned and unfinished by this packet. This pure transport is not
complete D3, a forecast-quality claim, empirical acceptance or production
activation. The unsupported C1/C3/C4 adapters, native Tennis state resolver,
both-tab worker/consumer integration and rendered UI proof remain separate.

## Frozen target SHA256 inventory

| Target | SHA256 |
| --- | --- |
| context_transport.py | 2fa1c380e30eece0ff8da6db2ec28b0743a717ef217b23f2a3d6a5236662f205 |
| tests/test_context_transport.py | 805fb2b31004dc5bdf671e77a80efc6b893039027d8071f4586ee7cb5db79e88 |
| docs/audits/2026-09-09-d3-context-transport.md | 8cb2060a97edc9c7ed9e31927d15a63d843453d99846733a2b5fe74178563ff6 |
| task-18-controller-rulings-20260909.md | ecb4d94d48c4b6d31e24604bec204ef7bd880098decd334bdbc880bd01802020 |

| Independent artifact | SHA256 |
| --- | --- |
| test_independent_transport.py | 7720e8fc0206d0288451bafe3790d78e2be7a101ba3a2b592745e6f76f36700c |
| test_transport_controls.py | cd794a7b6ff2b8fd05890a2041bdd2678a2b08cac4549db334820e3679120530 |
| run-01.xml | a9c385d6e75278658d899e9d4fb3452671a8d9912b0857f9fef93eab7697ffb2 |
| controls-01.xml | 28a3c1a7b8c442a80fe24edb022a84788c14d04c37430f09209bfd7482cf1d7e |
| combined-01.xml | c4b093f6d771472b91b99e342ab3c7ca197add78e51666433dc01a62df17fdaf |
| focus-01.xml | 4270a651faec59149f3780c27f1a454f6713d16bafb113725075bf8f0349c440 |
