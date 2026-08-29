# Wettfinder UX V2 Implementation Plan

> **For Codex:** Required skill: execute this plan with `superpowers:subagent-driven-development`, task-scoped review after every task, then a whole-diff review.

**Goal:** Replace the consumer Wettfinder's nested automated-result hierarchy with the approved flat, immediately readable V2 surface while preserving every model forecast, exact price logic, manual quote checks, saving of playable tips, and every existing sport/search capability.

**Spec:** `docs/ux/wettfinder-v2/WETTFINDER_WIREFRAME_V1.md` and the approved renders in `docs/ux/wettfinder-v2/renders/` are binding. The production surface must match their information architecture and visual hierarchy; the wireframe's synthetic values must never enter production data.

**Architecture:** Add a focused, mostly pure `wettfinder_surface.py` presentation layer. It converts persisted `ModelSignal` rows and exact `MarketConsensus` data into escaped card view models and creates a sport-diverse, price-neutral visible catalog. `app.py` owns Streamlit orchestration, mode/search controls, and responsive layout. `bet_finder_ui.py` keeps the existing price evaluation and persistence behavior but gains a compact presentation path so the V2 cards can display one concise price state and use a popover for the optional manual quote form instead of rendering the legacy card a second time.

**Tech Stack:** Python 3, Streamlit 1.59, pytest, existing BetBoy model/market-consensus modules, in-app browser verification.

## Global Constraints

- The model forecast remains visible regardless of missing, stale, thin, borderline, or too-low odds.
- Odds never change model probability, cautious probability, model order within a sport, or release evidence.
- Do not call an entry a confirmed/playable tip unless the strict row is `RELEASED`, the statistical release is no longer pending, the exact current market price is `PLAYABLE`, and the evaluated decision is `BET`.
- Keep every forecast visible exactly once. Simple markets and very short prices may be visually secondary, but never excluded.
- Top cards are never numbered as ranks. With sport filter `Alle`, create a sport-diverse round-robin from each sport's existing model order; do not calculate a numeric cross-sport ranking.
- Same-fixture secondary markets stay adjacent while retaining their original order.
- The automatic and custom-search journeys are separate top-level modes. Default to `Automatisch`; do not render both long journeys simultaneously.
- No outer automated-check expander, sport expander, fixture expander, or simple-market expander. Only optional per-selection analysis may use an expander. Manual quote entry uses a popover.
- Every top card immediately shows sport/time, event, market, selection, model probability, cautious probability, value threshold, observed price or dash, evidence state, price state, context text, and the two actions from the approved wireframe.
- Additional rows remain flat and immediately visible with the same key values; controls are at least 44 px high.
- Preserve current search coverage for all configured sports, date horizons, football market scopes, and leagues.
- Escape all provider/model text before inserting it into HTML.
- Preserve the four known untracked audit/screenshot files; do not add, edit, delete, stage, or commit them.
- Use real behavioral tests. Do not add source-grep, change-detector, placeholder, or mock-only tests.

## Task 1: Build the price-neutral Wettfinder view model and catalog

**Files:**

- Create: `wettfinder_surface.py`
- Create: `tests/test_wettfinder_surface.py`

### Step 1: Write failing view-model tests

Cover at least:

- `ModelSignal` plus exact consensus data maps to all required visible fields without altering either probability.
- `TOO_LOW`, `BORDERLINE`, `THIN`, `STALE`, `UNAVAILABLE`, and `PLAYABLE` become concise consumer price labels; a non-current price is never presented as current.
- An observed best price remains visible for fresh `TOO_LOW` and `BORDERLINE` states, while missing/stale/unbound data shows a dash.
- Evidence labels distinguish released/confirmed, fully checked, partial, and pending context without inventing facts.
- HTML markup escapes event, market, selection, context, bookmaker, and model detail.
- The card is only `confirmed_tip=True` under the exact four-part release/price contract in Global Constraints.
- Catalog curation uses original per-sport order, round-robin diversity for `Alle`, max three featured rows, no price input for ordering, all remaining forecasts exactly once, and same-fixture adjacency.
- Repeated broad `Team 1 über 0,5` forecasts remain visible but cannot monopolize featured cards while useful diverse markets exist.

Run:

```powershell
pytest -q tests/test_wettfinder_surface.py
```

Expected: FAIL because `wettfinder_surface.py` does not exist.

### Step 2: Implement the smallest pure presentation layer

Implement immutable dataclasses and pure helpers for:

- safe display formatting of scheduled starts, percentages, and decimal odds;
- reference-price classification through the existing `wettfinder_reference_price_status` contract;
- concise evidence and price labels/tones;
- strict confirmed-tip calculation;
- escaped top-card and compact-row markup;
- price-neutral, sport-diverse featured/additional catalog composition using the existing market-utility and fixture-grouping helpers where applicable.

Do not duplicate betting math or quote-validity rules.

### Step 3: Run tests and self-review

Run:

```powershell
pytest -q tests/test_wettfinder_surface.py
```

Expected: PASS. Mutation check: temporarily change the cross-sport round-robin or HTML escaping and confirm the corresponding test fails, then restore the implementation and rerun green.

### Step 4: Commit

```powershell
git add wettfinder_surface.py tests/test_wettfinder_surface.py
git commit -m "feat: add price-neutral Wettfinder view model"
```

## Task 2: Add compact price actions without changing betting decisions

**Files:**

- Modify: `bet_finder_ui.py`
- Modify: `tests/test_bet_finder_ui.py`

### Step 1: Write failing compact-presentation tests

Cover at least:

- The default/full mode retains the existing header, metrics, reference-price explanation, manual expander, and save behavior.
- Compact mode skips duplicate header/metrics/reference alerts but evaluates the same automatic price and returns the same `PriceDecision`.
- Compact manual quote entry is opened through `st.popover("Eigene Quote prüfen")`, not an expander.
- A compact automatic `BET` still offers `Tipp merken` and persists the same concrete provider/bookmaker provenance.
- Manual quote confirmation still saves only an eligible decision and cannot bypass `release_pending`.

Run:

```powershell
pytest -q tests/test_bet_finder_ui.py -k "compact or manual or reference"
```

Expected: FAIL because compact presentation does not exist.

### Step 2: Refactor evaluation from rendering

- Extract one helper that evaluates the existing exact reference quote and returns the same `(decision, status, effective_quote)` data without UI side effects.
- Keep the current verbose renderer as the full-mode default.
- Add an explicit compact presentation option to `render_price_decision`; do not infer compactness from the call site.
- Add an explicit manual surface option whose default remains the legacy expander and whose V2 value is a popover.
- Do not change thresholds, status codes, stake math, persistence, or release gates.

### Step 3: Run focused and regression tests

```powershell
pytest -q tests/test_bet_finder_ui.py -k "compact or manual or reference"
pytest -q tests/test_bet_finder_ui.py tests/test_market_scope.py
```

Expected: PASS.

### Step 4: Commit

```powershell
git add bet_finder_ui.py tests/test_bet_finder_ui.py
git commit -m "refactor: support compact Wettfinder price actions"
```

## Task 3: Integrate the flat automatic surface and separate modes

**Files:**

- Modify: `app.py`
- Modify: `tests/test_workflow_integrity.py`
- Modify: `tests/test_wettfinder_surface.py`

### Step 1: Replace expander-contract tests with failing V2 behavior tests

Extend the Streamlit recording fake with the actual APIs used by the new surface (`container`, `columns`, `segmented_control` or equivalent, `popover`, and HTML markdown flags). Test behavior, not source text:

- `render_wettfinder()` defaults to `Automatisch` and does not render custom-search controls until that mode is chosen.
- `Eigene Suche` still reaches every existing sport/date/football-market renderer.
- The automatic surface renders its status strip, top cards, and additional rows without any enclosing expander.
- The only expanders emitted by the automatic surface are labeled `Analyse anzeigen`; manual quote forms are popovers.
- All forecasts across Football, Tennis, and E-Sport are rendered exactly once in `Alle`, with no numeric rank labels.
- Price status does not reorder cards when the same forecasts receive different quote states.
- Partial-run wording stays short and consumer-facing, and no fixture/model/price diagnostic counts leak into the page.
- Empty state remains concise and does not claim a price failure when no candidate exists.
- A strict released overlay replaces the same forecast row without duplicating it.

Run:

```powershell
pytest -q tests/test_workflow_integrity.py -k "automatic or wettfinder"
```

Expected: FAIL against the legacy nested surface.

### Step 2: Implement the V2 Streamlit orchestration

- Render an `Automatisch` / `Eigene Suche` mode control directly below the page intro.
- Move current custom-search controls into the `Eigene Suche` branch unchanged in capability.
- In automatic mode, render compact timestamps, one short result/coverage strip, sport filter chips, top-card columns, and a flat additional-list section from `wettfinder_surface.py`.
- Call compact `render_price_decision` inside every visible card/row so automatic save/manual quote behavior remains available without duplicate presentation.
- Render `Analyse anzeigen` as the sole expander and include only genuine model/context/evidence data already present on the signal.
- Keep the strict `RELEASED` overlay by key before building the catalog.

### Step 3: Run focused tests and mutation checks

```powershell
pytest -q tests/test_workflow_integrity.py -k "automatic or wettfinder"
pytest -q tests/test_wettfinder_surface.py tests/test_bet_finder_ui.py tests/test_market_scope.py tests/test_workflow_integrity.py
```

Expected: PASS. Mutation check: force the automatic branch to render one fixture expander or to select the custom-search branch by default, confirm the covering test fails, restore, and rerun green.

### Step 4: Commit

```powershell
git add app.py tests/test_workflow_integrity.py tests/test_wettfinder_surface.py
git commit -m "feat: ship flat Wettfinder automatic surface"
```

## Task 4: Match the approved responsive visual hierarchy

**Files:**

- Modify: `app.py`
- Create: `design-qa.md`
- Add only new screenshots under: `output/playwright/wettfinder-ux-v2/`

### Step 1: Add focused V2 CSS

Use the existing BetBoy tokens and production Material icons. Add narrowly scoped styles for:

- mode control, status strip, sport chips;
- three equal desktop cards, two-column intermediate state, one-column mobile state;
- top-card badges, typographic hierarchy, probability band, four-metric grid, price notice, context line, actions;
- compact additional rows and same-fixture adjacency;
- 44 px minimum interactive targets, safe wrapping, no horizontal overflow;
- mobile bottom-navigation clearance.

Do not globally restyle unrelated pages.

### Step 2: Run CSS-adjacent regressions

```powershell
pytest -q tests/test_workflow_integrity.py tests/test_wettfinder_surface.py
```

Expected: PASS.

### Step 3: Browser behavior and visual QA

- Start/reuse the real local Streamlit app with the project environment.
- Use the Codex in-app browser only.
- Test the production page at desktop `1600x1600` and mobile `390x844`, plus overflow checks at `320`, `360`, `390`, and `430` px widths.
- Exercise automatic/custom mode switching, sport filter, `Analyse anzeigen`, manual quote popover/form, and the mobile bottom navigation.
- Capture production screenshots and combine each with the approved same-viewport reference in the design QA comparison.
- Load and follow `product-design:design-qa` and its rubric. Fix every P0/P1/P2 difference or functional defect and repeat the comparison.
- Write `design-qa.md` at repository root with tested states, viewport evidence, remaining P3 differences if any, and a final line exactly `final result: passed`.
- Verify no console, page, or failed-request errors and no horizontal overflow.

### Step 4: Run the full local suite

```powershell
pytest -q
```

Expected: the complete suite passes with only documented expected skips.

### Step 5: Commit visual completion

```powershell
git add app.py design-qa.md output/playwright/wettfinder-ux-v2
git commit -m "style: complete responsive Wettfinder V2"
```

## Task 5: Independent release review, push, and VPS deployment

**Files:** no product code unless review finds a defect.

### Step 1: Whole-diff reviews

- Generate a review package from the starting commit through `HEAD`.
- Run independent spec/quality review and a separate regression review focused on price independence, release gating, data preservation, Streamlit state, and responsive UX.
- Fix every Critical/Important/P0/P1/P2 finding in one bounded fix wave, rerun affected tests, and obtain a scoped re-review.

### Step 2: Reconcile repository state

```powershell
git status --short
git log --oneline --decorate -8
git diff --check <starting-commit>..HEAD
```

Expected: only the four pre-existing untracked files remain outside the implementation commits; no whitespace errors.

### Step 3: Push

```powershell
git push origin main
git ls-remote origin refs/heads/main
```

Expected: remote `main` equals local `HEAD`.

### Step 4: Deploy the exact commit to BetBoy VPS

Use the repository's existing, verified deployment procedure. Pull/fast-forward the VPS checkout to the exact pushed `main` commit, install only manifest-required changes if any, restart the app only when required, and do not alter production secrets or databases.

### Step 5: Verify production

- VPS `HEAD` equals local and remote `HEAD`.
- App and reverse proxy are active; no failed systemd units.
- All seven known BetBoy timers remain enabled/active with valid next-run times.
- Local and public health checks return `ok`.
- Open the public Wettfinder in the in-app browser and repeat the critical desktop/mobile interaction checks with no console/page/request errors.
- Confirm the automatic scheduler still writes forecasts and the surface reads the latest artifact without manual user action.

### Step 6: Final report

Report the exact commit, test counts/skips, reference-vs-production QA result, browser states tested, remote/VPS hash equality, health/timer status, and any explicit P3-only visual differences. Do not call the UX complete without the production browser evidence.
