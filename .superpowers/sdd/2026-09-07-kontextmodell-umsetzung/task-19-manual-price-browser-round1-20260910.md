# Root actual browser acceptance — manual price round 1

10 September 2026, approximately 11:13–11:26 CEST. Source frozen at
`acf6b8ed443a0d938171319ac29ffa29b3e80bbf`; separate LF worktree
`kontext-manual-price-round1-20260910`. Root later merged those exact source
bytes as `74d714a712ba3abc207ff0c717e7f27927624ba5`. This report is local
functional/visual QA, not production or sports-effect evidence.

## Isolation

Own Streamlit process on127.0.0.1:8508, existing quality Python/Streamlit1.59.2,
no watcher/telemetry, explicit empty secrets and removed provider credentials.
The prior synthetic seed and empty-secrets file were copied byte-identically
to this worktree's new `output/playwright/context-round1-20260910` directory.
New fixture time11:13 CEST; own normal payload SHA256
`c3deca8b1f2e3db4ff62398aee46e639b957e575aa440d55811ac875a390e69a`.
No production scan, bet, money transfer or historical prediction change. The
unchanged manual helper may archive NO_BET/SHADOW in this worktree's synthetic
tip store; this is not falsely described as no database operation.

Source `bet_finder_ui.py` SHA2569447488dd3874946e46087ad33fed8525372226099386644a5e8d85650c2a88b.
Runtime source has actual LF SHA710b8f8b1bfacf35397aad47d8df2fc9c28f6af60a4888540acfac4030331a8c.
Protected stage helper1441158 is unchanged. Root's inherited CRLF-only runtime
and phantom stage status are not normalized by this browser work.

## Actual checks

- PASS fresh card A and card B: visible bankroll text100.00. Submitting1.12 on
  A without touching the bankroll evaluates the actual visible100.00 and names
  quote, bankroll and confirmation in the result. No hidden default is inferred.
- PASS two simultaneous cached manual decisions: A1.12/100.00 and B1.20/100.00,
  both confirmed, show their own below-price result. Reopening A after B returns
  its exact earlier dialog text. Editing A to4.00 and blurring clears A's old
  result. Reopening B retains its exact prior dialog text. No Python session-
  state mutation was used to establish this browser invariant.
- PASS explicit A4.00 yields pending-evidence/no-stake. Five normal article
  texts and order remain exactly equal to the original rendered texts.
- PASS actual keyboard Select-all/Backspace produces a visibly empty balance;
  after blur and completed rerun it remains empty and invalidates the check.
  Explicit4.00/empty names `Wettguthaben ""` and rejects it without a stake.
  Refilling100.00 does not resurrect the old result.
- PASS unchecking selection then explicitly checking names confirmation`nein`
  and requests confirmation, without an old result or stake. Malformed
  `bad-price`/`bad-balance` names both exact raw values and rejects them.
- PASS reopening B after A's clear, refill and malformed explicit submission
  still returns B's exact prior dialog text. All five model articles unchanged.
- PASS320px screenshot: open malformed-result popover, text fields, checkbox,
  explicit button and feedback readable. Dialog width288, left24; client/scroll
  width286; document width/scrollWidth320. No horizontal clipping.
- PASS normal Tennis empty-filter state has no Top heading; All restores the
  exact five articles. Mobile Finder→Risk→Finder navigation works.
- PASS all six existing Risk sport filters show exactly one matching synthetic
  event; All restores all six. Cricket code is unchanged, not newly integrated.
- PASS separate existing Risk price control:1.12 shows implied89.3% versus
  model41%;4.00 shows25% versus41%. Model sections/order exact. Only the first
  price section changes from unavailable to the entered4.00, as intended.
- PASS both views at1440/1024/761/760/390/320: document scrollWidth equals
  viewport, five normal/six Risk cards retained. Temporary viewport reset.
- Final captured browser error/warning list empty. One engine, no real-device
  claim. Screenshot bytes displayed inline through CUA, no invented PNG path.

## Qualified attempts and evidence boundaries

The first `.fill('')` plus immediate Tab/wait did not establish a durable clear:
the queried message was absent and a subsequent DOM showed100.00. No source
failure or successful clear is inferred from that attempt. The actual keyboard
clear was then observed empty before blur and after the completed rerun. The
first immediate post-blur read still showed the prior explicitly identified
result; the subsequent state showed invalidation. Do not conflate a client/
rerender transient with a completed stale-result check.

A whole-article equality assertion after changing Risk's own quote was false.
The exact diff contains only its intended price section (Quote fehlt→Quote
beobachtet4.00/Eigene Buchmacherquote). All pre-price model sections and order
are exact, and the other five full articles are exact. This is a qualified
overbroad assertion, not a ranking/probability regression.

The Risk fixture deliberately contains legacy technical Pro/Contra strings to
test sanitization. It cannot prove that today's source emits those strings or
that a checked neutral factor is a real advantage. No effect validation claim.

Independent round1 review addressed both source findings and raised only an
audit-attribution error. Root corrected the historical C0 statement to distinguish
AppTest from CUA. This new F1 report supplies the later actual two-card proof.
No extra source change or repeated focus suite is indicated by that correction.
The final integrated full suite and actual trusted A→B deployment remain separate.
