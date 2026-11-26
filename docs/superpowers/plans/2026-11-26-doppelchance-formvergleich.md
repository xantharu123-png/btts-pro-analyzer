# Doppelchance-Formvergleich Implementation Plan

> **For agentic workers:** Use test-driven-development. Keep the study out of serving and API routing.

**Goal:** Compare the 75/25 form blend against the venue-only variant on the same prospective matches and report the paired scores by league.

**Architecture:** Opt in from the normal current-day football discovery. Capture the existing calibrated active and season 1X2 vectors (same input and existing calibration; the separate form-strength multiplier is unchanged). Put only identity, clocks, version, scope, and six probabilities in a bounded SQLite sidecar. Reuse native 90-minute final details from existing settlement and write an internal league report.

**Tech Stack:** Python, SQLite, pytest, existing worker and deployment path.

**Spec:** Owner approved in chat, 26.11.2026. Only remove the 25% all-venue blend in the comparison arm. Do not change the model shown, rankings, price policy, publication, backup policy, timer, or number of API requests. Domestic and cross-competition paths remain separately identified; national-team calculations are different and excluded.

## Review Focus

- Same fixture, team roles and kickoff; no joining a moved or reversed fixture to an old forecast.
- Take only a successfully calibrated pair, bind it before kickoff, and freeze the first per fixture/version/scope/start.
- Keep the regular job and the product available even if the diagnostic storage fails.
- Compare exactly the same games for both arms; leave missing terminal scores open and never request them solely for this comparison.
- Count Home/Draw/Away and 1X/X2/12 separately; do not infer causality from small samples or change production weights.

## Test and implementation

- [x] Model and scan: test same frozen 1X2 vectors versus the model's existing active/season estimates, no change to public candidates, and reject wrong scope/projection failure. Implement optional `form_comparison_capture` through `build_fixture_candidates` and `scan_daily_challenge`.
- [x] Storage/report: test real SQLite duplicate, timing and native-identity constraints, full-time vs incomplete results, paired Brier and individual outcome counts by league/scope/version. Implement the bounded comparison sidecar and offline report.
- [x] Integration: exercise worker opt-in and existing settlement with stubbed provider, assert identical fixture queries, no new model for quote refresh and diagnostic isolation. Run relevant regression tests and independent review.
- [ ] Commit, push, CI and deploy with the established no-backup procedure; verify the running revision and health without starting a job. The next scheduled discovery/settlement is the production data proof.

Local check: 331 selected tests passed under `gate`. In a wider-than-CI
`floor` run 329 passed; two existing gate-eligibility tests in
`test_football_joint_calibration.py` failed identically when re-run against
unmodified `origin/main` under `floor`. No test fixture or gate changed.
