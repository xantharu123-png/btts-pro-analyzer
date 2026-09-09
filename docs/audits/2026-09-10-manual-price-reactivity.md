# Manual quote edits invalidate the previous explicit check

Date: 2026-09-10. Scoped implementation in the LF worktree
`kontext-manual-price-ui-20260910`, parent
`f2f7611823c8e0b23b102bafba9e880adab87f9f` (frozen release B).

## Finding and scope

Root's actual browser witness submitted quote 1.12 and then edited it to 4.00.
Even after blur, the previous below-value message remained visible. The manual
check used `st.form`, which defers input delivery until submission. Its cached
`PriceDecision` was bound only to the candidate, not to the current raw quote,
bankroll or confirmation. The message also did not identify the checked price.

This packet changes only `bet_finder_ui.py`'s manual input/display handling,
three existing widget mocks, and new actual Streamlit tests. No formula,
candidate ranking, quote gate, TipStore policy, 15K rule, automatic offer path,
Riskobet Pro/Contra copy, source capture or privileged deployment file changes.

## Implemented behavior

- The existing expander/popover and `bet_price_<key>` CSS scope stay in place.
  A keyed `st.container` replaces the form; normal text/number/checkbox widgets
  deliver their edits on the normal reactive event, with a separately keyed
  explicit check button. Their actual Streamlit widget protos have no form ID.
- A per-card immutable `_ManualPriceInputs` snapshot binds the complete
  candidate, raw quote spelling, bankroll and confirmation to the explicitly
  requested decision. The existing `bet_decision_<key>` key is retained.
- Input callbacks only discard cached display state and mark it changed.
  They never calculate, save, archive or call `_save_tip`. The ordinary render
  path independently rejects changed inputs/candidates and missing old input
  bindings, including state changes without a widget callback.
- An edit shows **“Eingabe geändert – neu prüfen.”** Old success, below-price and
  stake messages disappear. Reverting an edit does not resurrect the old check.
  The other card's stored and returned decisions remain independently unchanged.
- Initial manual bankroll remains 100. A one-time state seed and nullable
  number-input default preserve an explicit clear as `None`; it is no longer
  silently replaced by 100. The unchanged evaluator rejects that value on a
  later explicit check. No price computation is performed merely on clearing.
- Every available result names its last checked quote and bankroll. This also
  distinguishes the previous submitted result while newly typed text is still
  client-local before blur. Invalid inputs whose decision has no quoted odds
  are explained as invalid input, not falsely as a below-value quote.
- The explicit calculation and save guard remain exactly the old rule:
  `_save_tip` is considered only after submission, with `save_source`, confirmed
  selection, and a status other than `PRICE_REQUIRED`. Its own BET/NO_BET/
  SHADOW handling is untouched. Tests intercept the helper; no real ticket or
  money movement was created by this packet.

## Actual evidence

Installed Streamlit is 1.59.2. The local owning `NumberInputSerde` was inspected:
with a default of 100 it deserializes an empty UI value to that default, so the
initial reactive patch still needed the narrow nullable-widget correction.
No library installation or new dependency was required.

Before source edits, 25 real AppTest cases failed in 6.04 seconds, exit 1.
They cover form delivery, 1.12 -> 4.00, bankroll and checkbox edits, immutable
candidate revision, two cards, invalid/empty/nonfinite quote strings, no effects
on edit, explicit rechecking and legacy cached decisions. The original test
source and XML are retained under `.pytest_tmp/`.

The first corrected run had 32 passed/5 failed. One was the real empty-bankroll
default described above. Four newly reached follow-on assertions incorrectly
assumed the cached pending decision equals the renderer return: the pre-existing
`_enforce_pending_release` appends a second reason to the return. That helper is
unchanged. Each card's cached and returned object is now compared exactly to its
own pre-edit object, without dropping or normalizing any field. The original
frozen probe rerun confirms 21 passed/4 such follow-on assertion failures;
those four are explicitly not claimed as green unchanged probes.

The permanent qualified file has 30 real AppTest cases, including five further
edit/revert, cleared-bankroll and non-widget state controls. Final bounded run:

**159 passed, 0 skipped, 8.86 seconds, exit 0**, with:

- `tests/test_manual_price_reactivity.py`
- `tests/test_bet_finder_ui.py`
- `tests/test_workflow_integrity.py`
- `tests/test_manual_selection_coherence.py`
- `tests/test_challenge_15k_ui_audit.py`

The original candidate-stale assertions remain. The only changes to their
existing test file are six widget-mock substitutions: `form` -> `container`
and `form_submit_button` -> `button` in three tests. No assertion is weakened.

An additional read-only Git/AST scope check confirms all 25 other original
named UI definitions have exactly their parent source text/AST, including
`_save_tip`, price parser, automatic reference path, pending wrapper and ranking.
It also checks the explicit save guard and exact untouched bytes for the
math/model, TipStore, 15K, coherence, app and updater/helper modules. Its first
local attempt selected the containing `if submitted` instead of the nested save
guard; that test-helper selection was corrected without touching source.
Final scope check exits 0. Both helper versions are retained.

## Frozen file and evidence hashes

| File | SHA256 |
| --- | --- |
| `bet_finder_ui.py` | `16fa6c4ee5d667379db8b39f759f249fb2c0fd89e5b0cb2e048fc48db9142f4f` |
| `tests/test_bet_finder_ui.py` | `45c169c5c2f7e6ef4e26aae08517c844ed309981d5d15e6b83c34f178273f9a1` |
| `tests/test_manual_price_reactivity.py` | `d8a6f4e7f5fb3dd7d371ffc345f2beca862885acee3a3a60e31916c0aec0d1e7` |
| `.pytest_tmp/manual-price-red01.xml` | `f93ef8a99b78a8a7fe44794f8b526902d59e4b4c29f29363cb9af34fc4543706` |
| `.pytest_tmp/test_manual_price_reactivity-original-red.py` | `ce4f135fbefc644aee6a7268a4257574b4e7ea2ae6c268db8886e647e987a10d` |
| `.pytest_tmp/manual-price-green02.xml` | `ee2e87499a78cc0e5a0ef9dd71cbfce51940c442b02fdbbe48c671bd16408072` |
| `.pytest_tmp/manual-price-focus04.xml` | `af0d7b9698da0f27830819a6531cbfcf35d4bd040e44847b21059b36964903cd` |
| `.pytest_tmp/manual-price-original05.xml` | `05a58895cc2e72c97dc498cc6a37fd2e1d10f3bde90ff2392d394a69b7c9e51d` |
| `.pytest_tmp/verify_manual_price_scope.py` | `6f4a12fb51756d5e322e2ebc03562a2b180cf873361c9ff8563f080268764050` |

## Handoff boundary

No full suite or parallel browser run was started; Root requested both be kept
separate. Actual blur/Tab/popover rendering and responsive layout still require
Root's browser rereview on the frozen fix, followed by its release-target QA.
Neither frozen B nor Root was modified. No push, merge, provider query or VPS
deployment was performed. The overall release hold is not lifted by these
AppTests alone.
