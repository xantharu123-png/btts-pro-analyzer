# Independent P4a review — one confirmed P2, correction required

Reviewed 2026-09-09, read-only source worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-team-sports-live-original-20260909`.
Frozen clean HEAD `f0b020557fc060e500bdb33fb466646ff1c49ce7`, compared with
`1b77286d06f9731c1ffa38ba3d408f20fff1b02e`. All four changed files, the complete
owning audit, unchanged original math/normalization and relevant C2/C3 native
identity/forward helpers were read. The full shared contracts file was read,
not only the 11-line dispatch diff.

**Disposition: do not merge this packet unchanged.** One bounded native-identity
validation-order issue remains. The independent numerical, same-call, pure IO,
price and unresolved-reference controls passed. This review does not require
a new alias resolver, schema, source qualification or empirical gate.

## F1 — P2: an unknown team suppresses a different, already known contradiction

Location: `context_models/team_sports_live.py`, `_native_binding`.
Basketball catches an invalid/unresolvable native team at lines 278–283 and
returns before the known Event/team comparisons at lines 302–305. Hockey has
the same early return at lines 293–301. The actual event ID can already be
known and different, or the other team's valid native ID can already disagree.

The reproduction uses real `sports_prematch.predict_prematch` and its actual
same-call callback; it does not forge coefficients or replace the capture
dataclass. One team's source spelling is consistently changed in target and
history to `legacy-known-nonnative-team`. The inherited model still computes a
valid original probability from its connected history. That team's native
join is genuinely unavailable, so preserving the original without a native
base is the correct positive control.

Then the supplied canonical native Event independently has either:

- a different known event ID (`...:499999999` instead of the actual captured
  target ID); or
- a different known native ID for the *other* team (`...:team:99`).

Expected: reject this explicit known contradiction with a typed contract/
integrity error, while leaving the unchanged original prediction available.
Actual: the builder returns `base=None`, reason
`native-target-team-identity-unavailable`, and stores the supplied contradictory
Event in the captured original. The pure validator repeats the same early
fallback and accepts that contradictory original as merely unresolved.

Eight genuine REDs cover both sports, both unknown-team sides and both kinds of
independent mismatch. Four genuine unresolved-team controls are green. Two
known-ID mismatch controls without the unavailable team are green, proving the
issue is specifically the validation order, not a demand for source truth from
an unknown ID.

**Severity boundary:** this is not a demonstrated B3/model-effect approval
bypass, financial bug or changed baseline probability. The base remains absent
and source resolution remains unresolved. It is nevertheless a known impossible
identity association being accepted, contrary to this packet's explicit audit
contract that known contradictory IDs fail rather than become soft unavailable.

Smallest correction: derive/compare each known native event/participant claim
independently before returning an unavailable result for another claim. Keep
unknown values unknown; do not invent an ID, require a new provider or reject
the legitimate unresolved-only controls. No source/format resolver expansion
is requested by this finding.

## Independent controls and measured scope

- Real callback builders and pure/shared validators add no target `_fit` or
  `_predict`, with cold caches and legitimate historical prequential folds
  preserved.
- Basketball signed influence checked independently using the dual solve
  `X @ solve(G, q)`, then against the actual margin via `weights @ y`.
  Negative weights remain present, and the resulting probability agrees with
  the actual Normal forward law. This is not a second target coefficient fit.
- Hockey's regulation probabilities checked against an independently summed
  Poisson joint distribution. Actual fixed OT rate checked directly against
  contributing observed model rows. All five markets remain coherent and the
  actual original inclusive probability is preserved exactly.
- Coherent rewritten non-target coefficients and rehashed inline model remain
  explicitly unresolved under pure validation. The separately requested fresh
  offline fit rejects them and really performs one fresh fit, not a cached-hit
  substitute. No source proof is inferred from this numerical check.
- Closed receipt links, real raw-history index 85 with an ignored row at index
  7, cancellation at cutoff minus/equal/plus one microsecond, and full original
  history preservation checked. Native receipt verification remains absent by
  design, not asserted by these synthetic links.
- No file, SQLite, provider, target-fit or target-predict access during the pure
  builders/validators, including nonexisting digest links.
- Price-neutral captures, one-ULP rejection, missing season/neutral metadata,
  no-native-Event originals, EuroLeague raw-case and B1-only composite-ID
  non-aliasing controls pass. No new alias/schema/source requirement is invented.
- Actual `sports_prematch.py`, C2 and C3 are byte-unchanged from the parent.
  Small existing legacy/original tests including frozen Cricket/Risk parity
  pass; no default predictions or Cricket source were changed.

## Runs and frozen evidence

1. `p4a-independent-red-01.xml`: initial collection-only failure because an
   existing owning test imports `test_sports_prematch` by its short name.
   Preserved; **not** functional RED evidence. Running the small legacy test
   file alongside the independent probe supplies its existing pytest path.
2. Unchanged first probe plus small legacy tests: **8 failed, 50 passed, 2.86 s**.
3. Closing bounded run: **8 failed, 204 passed, 9.05 s**, exactly the same eight
   F1 cases. Totals: 54 independent cases (46 green/8 RED), 105 owning cases
   green, 53 existing sports/original cases green. Zero skips. No full suite.

Reproduction from the owning worktree:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider tests/test_sports_prematch.py tests/test_sports_prematch_original_capture.py tests/test_team_sports_live_original.py .pytest_tmp/p4a-independent-20260909/test_independent_original.py .pytest_tmp/p4a-independent-20260909/test_independent_boundaries.py --basetemp=.pytest_tmp/p4a-independent-closing-03 --junitxml=.pytest_tmp/p4a-independent-closing-03.xml
```

Use a **new** basetemp/XML name for any rerun; never overwrite the original REDs.
The first probe was not changed after its successful functional reproduction;
closing controls were added in a separate file.

| File | SHA256, verified after review |
| --- | --- |
| context_models/team_sports_live.py | ca6d4f31a113f656f94934c59b03f07fbf5565626aa7eefa38793fb030212308 |
| context_models/contracts.py | 7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8 |
| tests/test_team_sports_live_original.py | 033de00e971455918c9d24e6f5b88a549b5eea5795ab25be290baca7869cbc23 |
| docs/audits/2026-09-09-team-sports-live-original.md | fe9ea9ec43474c5a605659028526965996603429e07eecadb31218206da4bd39 |
| .pytest_tmp/p4a-independent-20260909/test_independent_original.py | 7bb4d33980e8379b010df6b1202ac5b829c22b97793e33b49d09793445a595ec |
| .pytest_tmp/p4a-independent-20260909/test_independent_boundaries.py | 45b0cd408673b2ac1ffcc684f58883102150065466b1136fcec1f3ed71134753 |
| .pytest_tmp/p4a-independent-red-02.xml | 637d23f48957335a3929366b40239ca993e502e90aedd00a411e58c6aab82a84 |
| .pytest_tmp/p4a-independent-closing-03.xml | a046930bad1cc11467c1fbbd8ad7cae260ecc61c3612d917d64d7ba069a9545a |
| sports_prematch.py | 1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d |
| context_models/team_sports.py | 6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 |
| context_models/ice_hockey.py | 5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4 |

No source edits, Git writes, provider calls, full suite, SSH or production action.
Only new ignored review files and unique temporary test outputs were created.
Source hashes and clean HEAD remained unchanged. The separate P4b1 package also
remains frozen and untouched. Final review disposition is correction required,
not empirical/native-feed/runtime approval.
