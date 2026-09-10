### Finding Verdicts

- **Fresh manual cards render blank instead of the required initial EUR 100, while an explicit clear must remain empty** — ADDRESSED in the fix diff and protocol evidence. `bet_finder_ui.py:666-675` parses only finite values of at least 1, while `bet_finder_ui.py:726-744` converts inherited numeric widget state without reseeding an inherited `None` and gives the new text widget a real `default="100.00"`. `tests/test_manual_price_reactivity.py:337-359` checks that both cards and both surfaces emit that durable default on the first and subsequent protobufs without a one-shot effect; `tests/test_manual_price_reactivity.py:391-421,488-498,515-526` separately covers a present empty string, untouched default submission, and legacy numeric/None state. Replacing only the bankroll stepper with this text control is covered by Root's recorded ruling. Actual visible-browser acceptance on F1 remains Root-owned.

- **Invalid explicit results fail to identify the raw quote and bankroll they checked** — ADDRESSED. `_ManualPriceInputs` now includes `raw_bankroll` (`bet_finder_ui.py:658-664`), the exact raw snapshot is stored at submission (`bet_finder_ui.py:758-774`), and every retained explicit decision renders quote, bankroll, and confirmation from that immutable snapshot using plain `st.text` (`bet_finder_ui.py:803-813`), independent of `decision.quoted_odds`. `tests/test_manual_price_reactivity.py:362-386,432-451,467-485` covers invalid/missing/unconfirmed values, strict raw-bankroll boundaries, escaping, and plain-Text rather than Markdown output.

### New Breakage in the Fix Diff

- **Important — browser and AppTest evidence are conflated:** `docs/audits/2026-09-10-manual-price-reactivity.md:127-129` says the primary invalidation, two-card isolation, and pending/no-stake behavior were all confirmed separately by Root. Root's C0 CUA did not create two simultaneously cached manual-price decisions and edit one; that exact invariant is supported by AppTest (`tests/test_manual_price_reactivity.py:186-210,391-414`), while Root's current browser evidence covered the five model-card text/order and filter roundtrip plus the separately reported single-card manual flows. Rewrite the sentence so each claim names its actual evidence source. This is release-significant audit provenance, not a code failure.

- No new Critical or Important source-code breakage found in the scoped fix. The parser preserves the approved min-1/finite boundary, raw spelling participates in snapshot equality, edit/revert remains invalidating, and calculation/save gates stay outside callbacks.

### Out-of-Scope Observations

- F1 actual browser acceptance is still pending from Root for visible first-render `100.00`, literal clear/reopen persistence, exact invalid-result identity, and the final two-simultaneously-cached-decision scenario. The protocol/AppTest evidence is strong but is not visual/browser acceptance.
- Evidence-only check, no suite rerun: `.pytest_tmp/manual-round1-focus.xml` reports 195 tests, 0 failures/errors/skips in 15.357 seconds; `.pytest_tmp/manual-round1-original-controls.xml` reports 18 tests, 0 failures/errors/skips in 4.727 seconds. The baseline/red/intermediate XML summaries also match the owning audit's 159/0, 28/28, 58/2, and 65/0 counts.

### Verdict

**Fix round:** Findings remain open — both original implementation findings are addressed, but the new Important audit-provenance misstatement at `docs/audits/2026-09-10-manual-price-reactivity.md:127-129` must be corrected. No additional implementation or test-suite run is indicated by this review.

### Closure Addendum — integrated `74d714a`

- **Audit-provenance misstatement** — ADDRESSED. `docs/audits/2026-09-10-manual-price-reactivity.md:127-132` now attributes the original reactive and single-card pending checks to C0 CUA, the contemporaneous simultaneous-decision isolation to AppTest, and the later two-card browser proof only to the separate F1 report. It explicitly rejects retroactive evidence upgrading.
- `task-19-manual-price-browser-round1-20260910.md` independently records the later F1 browser results: visible `100.00` defaults, simultaneous A 1.12/B 1.20 cached decisions, A-only 4.00/clear/invalid changes with B unchanged, exact checked-input identity, 320 px popover usability, and unchanged model-card text/order. These results close the browser acceptance items for this scoped fix but do not replace older evidence, a real-device run, the integrated full suite, production, or deployment QA.
- **Final scoped verdict:** All original findings and the sole Round-1 provenance finding are addressed; no new Critical or Important breakage remains. This addendum confirms documentation and existing Root evidence only—no code, test, or browser run was performed.
