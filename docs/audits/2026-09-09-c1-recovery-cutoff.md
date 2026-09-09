# C1 recovery at the exact cutoff — controller evidence

9 September 2026. Narrow correction against original Git source `30e7c84`.
The independent review is preserved byte-identically in SDD as
`task-12-cutoff-independent-review-20260909.md`, SHA256
`bdbbb832fea96548bca7e2f9e3f3440f8e35f6b4af482e8041d46684de6c25b7`.
It accepts these source/test mechanics only, not a feed or a learned effect.

## Defect and minimal correction

A completed game with actual end and actual receipt exactly at the decision
cutoff was dropped from the entire football schedule pool. An older game then
falsely supplied 34 hours of exact recovery instead of the actually observed
4 hours in the permanent synthetic reproduction, on both native sides.

Keep such a completed game in the observed rest timeline. Existing 1/3/7-day
performed-load windows and historical total-count convention stay strictly
before cutoff. Unknown duration/end remains unknown; source completeness is
not inferred. Tennis source and its existing numerical rules are unchanged.

## Controller RED/GREEN sequence

All commands use quality Python, `-B -m pytest -q -p no:cacheprovider`, new
isolated `.pytest_tmp` basetemps and no network or production database.

- Initial new 12-case run had 4 failures / 8 passed. Two failures were invalid
  new Tennis test setup: subtracting 1 microsecond from end without moving its
  start made the declared duration longer than the actual interval. The fixture
  was corrected before product code, retaining the same endpoint expectation.
- `context-rest-cutoff-red-20260909-02`: **2 failed / 10 passed**, 0.66 s:
  genuine football endpoint failures; all unchanged Tennis controls pass.
- First green attempt was **1 failed / 254 passed** because the old historical
  total-count assertion was correctly stricter than the rest timeline. The
  existing assertion was NOT changed. The product now keeps separate count
  and rest pools, preserving old counts.
- `context-rest-cutoff-green-20260909-02`: **255 passed**, 8.52 s: permanent
  12 cross-sport endpoint cases plus existing football/weather and Tennis features.

Independent reviewer reran those 255 tests, added 28 new probes and finished
**283 passed**, 9.65 s in one combined run. It loaded the actual original Git
source rather than a reimplementation and verified old/new byte parity away
from the endpoint, lower-bound microseconds, distinct receipt clocks, unknown
duration/end and exact original Tennis source bytes. No findings remain for
this narrow correction. Broader context integration is tracked separately.

No old forecast, ticket, ledger, price, Cricket, generic B1, provider or VPS
change. Test success supplies neither missing end times nor an empirical
fatigue coefficient. Complete D3 source/worker and D2 empirical proof remain.

```text
761b000057c41f2cb692304b7dfa839fcf067126e22a94d687c037027bbe4f1b context_models/football_load.py
17eefff17758cb4677548dd80bd5f20ab20f7519d7175eb88fba1cf49e21ca4e tests/test_context_recovery_cutoff.py
8ed2194852f01cd1ac548de4b2ef82e2b2f652561229fd251ec2bb649e885a3b .pytest_tmp/c1-cutoff-independent-20260909/test_c1_cutoff_independent.py
```
