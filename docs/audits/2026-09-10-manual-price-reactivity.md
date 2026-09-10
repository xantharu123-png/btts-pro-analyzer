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

## Round 1: independent findings and the actual widget protocol

The historical claims above that the initial bankroll remained visibly 100 and
that every explicit result identified its checked inputs were too broad. They
are superseded by this correction, not erased. Root's actual fresh-browser
check on `c0a83f191e200b5305acbf06cf23ddfb359a0a91` found blank first and second
bankroll fields, even after waiting, and an untouched submission correctly
rejected that blank input. Its independent report also found that invalid
outcomes lacked the checked-input identity. Root's C0 browser run confirmed the
primary 1.12 -> 4.00 reactive invalidation and single-card pending/no-stake
behavior. At that point, two simultaneously cached manual decisions and their
isolation were proven by AppTest, not by Root's C0 browser run. This round does
not change those rules. Root's later F1 browser report records its own separate
two-card check; it does not retroactively upgrade the earlier evidence.

This round is isolated in `kontext-manual-price-round1-20260910`, branched with
`git -c core.autocrlf=false` from that exact C0 commit. The original worktree,
Root's browser fixture, original review and all earlier evidence stay intact.

### Cause and the narrowly approved control change

Actual first-render `NewElement` data under installed Streamlit 1.59.2 showed
`number_input.value=100`, `set_value=true`, and
`new_element.has_one_shot_effect=true`, but **no `default` field**. The next
ordinary rerun omitted `default`, `value` and `set_value` while AppTest still
reported the Python session value 100. AppTest's `NumberInput.value` reads that
server state and its next generated widget-state message supplies 100 itself;
it did not establish a visible browser default.

The owning local NumberInput frontend initializes through the widget manager
or `proto.default`, and its commit handler substitutes `proto.default` for a
blank value. The shared widget-state hook can apply a transient `setValue`,
but that is not a durable default for later rendering/remounting. Thus neither
the old Python-value assertion nor its one-shot seed proved the required
initial display. No claim is made here to have independently traced Root's
exact React scheduling/interleaving in a second browser.

NumberInput's optional default also controls its clear affordance: an actual
default of 100 restores blank edits to 100, while `default=None` permits a
genuine clear. There is no independent public initial-value/clearable switch.
Root therefore explicitly approved replacing **only this bankroll control**
with a normal `st.text_input`, same label/layout/key/callback and visible
`value="100.00"`. The numerical stepper is intentionally removed. No new
library, dedicated delete button, source query or alternative UI path is added.

- Its real fresh and subsequent protos contain `default="100.00"`, without a
  `set_value` or `has_one_shot_effect` dependency, on both cards/surfaces.
- A user clear is an actual **present `string_value=""`**, not an absent numeric
  field. The owning frontend commits that string; actual `TextInputSerde`
  preserves it instead of falling back to the default. It is passed to the
  unchanged evaluator as `bankroll=None` only on explicit submit.
- Parsing accepts signed decimal/comma/dot/exponent spelling, but only finite
  values at least 1, preserving the old widget's min-1 boundary. Blank,
  malformed, sub-minimum, nonfinite and overflowing inputs are not clamped,
  guessed or silently replaced by 100. Raw spelling remains stored separately.
- Existing numeric session values are represented by their actual string value;
  an existing None is not reseeded. Such a legacy value has no invented
  historical raw spelling. No persisted model, ticket or database is migrated.
- `_ManualPriceInputs` now binds raw bankroll spelling as well as its parsed
  value. An edit/revert or same-numeric-value spelling change cannot resurrect
  a previous check, including replacement without an input callback.
- Every explicit outcome, including invalid, missing and unconfirmed inputs,
  renders **the stored snapshot** through `st.text`: exact raw quote, exact raw
  bankroll and confirmation. Empty strings and None are distinguished;
  JSON string escaping makes whitespace/control characters unambiguous, and
  plain Text protobuf output does not interpret Markdown/HTML/links.

### Regressions, qualifications and unchanged scope

Before this source change the inherited five-file baseline was
**159 passed, 0 skipped, 10.01 seconds, exit 0**. The new initial protocol and
input-identity/control tests were then executed against frozen C0:
**28 failed, 30 deselected, 5.90 seconds, exit 1**. This includes two actual
missing-default failures, missing explicit-result identities, and the newly
approved text/empty-string contract that the previous number control lacked.
The entire original red test file and XML remain byte-identical under
`.pytest_tmp/`.

First post-fix run: **56 passed, 2 failed, 11.66 seconds**. Those two failures
were test-harness errors: trying to manufacture None by delivering an absent
widget value *after* registration used the preceding serde default. A real
text-field clear is `""`, not that absent value. The qualified None controls now
begin with a genuinely existing nullable session state before registration;
the actual clear controls independently assert the present empty wire string.
The first post-fix test source/XML remain separately retained; their expected
values were not silently relabeled as a successful unchanged run.

The next owning run was **65 passed, 0 skipped, 11.39 seconds**. One additional
literal malformed-bankroll/plain-Text control and exact raw-bankroll caption
assertions were then added. Final bounded five-file run on the final source:

**195 passed, 0 skipped, 15.36 seconds, exit 0**, using exactly the five files
listed in the original audit. The manual reactivity file now contains 66 cases
(30 inherited behavior cases, 36 new protocol/identity/boundary controls).

An additional rerun selected 18 original, byte-unmodified red tests (the two
protocol cases and 16 raw-bankroll contract cases): **18 passed, 40 deselected,
4.73 seconds, exit 0**. The remaining old frozen cases still use the former
number-input helper or the explicitly qualified None simulation; they are not
claimed as an unchanged all-green suite.

The existing tests were adapted only where the actual widget/API changed:
keyed text edits replace numeric assignments, a literal clear is `""`, and
checked identity is now plain Text rather than Caption. The candidate-stale,
pending, no-extra-calculation/save, exact decision/stake and other-card
assertions remain. `tests/test_bet_finder_ui.py` has only the three authorized
widget-mock adaptations; no assertions were weakened.

A fresh read-only AST/source check confirms all 26 other named definitions
are exact C0 source, including `_invalidate_manual_check`, `_decimal_input`,
`_save_tip`, the pending wrapper, all automatic pricing and all catalog/ranking
functions. Both explicit save guards are exact. Whole-file parent bytes also
match for `multi_sport_recommendations.py`, `betting_math.py`,
`selection_coherence.py`, `tip_store.py`, `challenge_15k.py`, `app.py`, the
updater and protected stage helper. The latter remains raw SHA256
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
No runtime file was normalized or modified outside the scoped UI change.

### Round-1 frozen source and evidence SHA256

| File | SHA256 |
| --- | --- |
| `bet_finder_ui.py` | `9447488dd3874946e46087ad33fed8525372226099386644a5e8d85650c2a88b` |
| `tests/test_bet_finder_ui.py` | `673e87146fd3223d3bd7d59360174a1a99be8f7a6502e156957412effb93dfe0` |
| `tests/test_manual_price_reactivity.py` | `51a9ccb6d588483fff045ee571df5264dffda08976b1b8f93f817b9d7f5948db` |
| `.pytest_tmp/manual-round1-baseline.xml` | `23f771d902ba00ebf62584eb14c796c4ff7cd07c18b3c7c38ad229a43e27fdc2` |
| `.pytest_tmp/test_manual_price_round1_original_red.py` | `71c1b631a0412f15819e67221ea9424ad7fb314433813c491f65d50106ef06ca` |
| `.pytest_tmp/manual-round1-red.xml` | `233044b83ee43c4eaf5325a2c950db023622b674aa49d488777b95ae5871833d` |
| `.pytest_tmp/test_manual_price_round1_green_attempt.py` | `8a967bd1446fff692624c6196b9da26df11539bd078f43a1f99a58212cd6d67f` |
| `.pytest_tmp/manual-round1-green.xml` | `40fbbdb2e4b5e1cba2e670ea40c9260f5372578f44fca1d87b62b46d95d0cddf` |
| `.pytest_tmp/manual-round1-green02.xml` | `7307ded06d465ff7db90c6ac1c2372a892a502afd21f8deebfcfc57ce01c6312` |
| `.pytest_tmp/manual-round1-focus.xml` | `56a3afb00bc2111fb753fdb1c5656168e7ca14418008949f91d8c0a99d88e965` |
| `.pytest_tmp/manual-round1-original-controls.xml` | `20cbdbaa109e2729e84bbd94d8790693acbb3fd9ca4e96a7ac6d205518ed23b2` |

Local dependency evidence, unchanged installed Streamlit 1.59.2:

| Source | SHA256 |
| --- | --- |
| `elements/widgets/number_input.py` | `b31a5784be12bd96bf375bae1b9b90ddce8b2fcd7dbae8c63b79f426daaafa20` |
| `static/static/js/NumberInput.DueFDrbi.js` | `c58b900ee5007aae156981c4460ac5b88f35d96e91b91b8a72d5d82f039e54d1` |
| `static/static/js/useBasicWidgetState.D6ltrbB8.js` | `4d28d427e995d628b990ec4a9a64bc1b1438c8d846ff5cfd4f20f35a546efbef` |
| `elements/widgets/text_widgets.py` | `cd9de8b00ed0349a58aeb0ebc0c8703390bfa6ffbf824d7213acd86bcee75463` |
| `static/static/js/TextInput.C78pm77f.js` | `333fe285bad4c57e3f1d8d45e76bae3a57ad55fa0c3e9d5b0ea49c31d7e4bb11` |

No agent browser run, full suite, provider call, additional agent, push, merge
or VPS action was performed. This packet is frozen for Root's independent
review and actual browser test on a separate fixture/port; protocol/AppTest
evidence is not a substitute for that visual/browser acceptance or release QA.
