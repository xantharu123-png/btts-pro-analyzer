# Independent Task7 spec and code review

Reviewer `/root/tennis_check_task7_review`, independent read-only review of
65cd304930a422d0bd43dd0549ca0131a28b24f7..17cfbbc3a2786190482b001f40361bf8e7667152.
Package `review-65cd304..17cfbbc.diff`, one commit,51112bytes.

## Spec Compliance

PASS for the bounded Task7 implementation. Native/release acceptance remains open.

- Actual selected-content normalization and full canonical equality remain
  mandatory before SHA256 reuse; native payload/reception validation and
  expected-envelope byte comparison still run. Standalone validation retains
  normalized `_record` construction (tennis_status.py:102-117,171-237,248-283).
- Expected-envelope reuse is equivalent for accepted inputs: the unchanged
  normalizer rejects non-JSON/exact-type violations and copies values without
  coercion. Checked identifiers, canonical clocks, literal metadata and
  digests make the reconstructed envelope normalization-stable
  (contracts.py:123-179; tennis_status.py:102-117,171-228,273-279).
- Completed-proof fusion obtains a fresh authoritative inventory check,
  compares exact mapping and original proof/cache stamps, rechecks live
  writes and transaction lifetime. Missing proof retains full fallback;
  failures clear entries, seals and retained/pending bytes
  (history_cache.py:116-144; inventory.py:67-87).
- Witness matching, independent `_store` owner validation, lifetime boundary
  placement, inventory/transaction implementation, math/predictor and caps
  are not altered by the diff.

## Strengths

Narrow factoring, no caller trust flags/cross-call normalized retention or
digest-only authority. Real delegated validators and schema-query counts
exercise one derivation and standalone normalization (equivalence tests:177-219).
Mutation tests use genuine sealed byte-equal hits at both row boundaries,
both schemas, writes, DDL, restart and closure; late writes/transaction
changes and permanent owner revocation are covered (witness tests:431-495).
Report separates focused results/platform skips from native release evidence.

## Findings and assessment

No Critical or Important findings; no Minor requiring changes. Quality Approved.

The documented sequential final-schema-read limitation is real but existed
before this patch. A main-schema mutation after its last relevant read can
escape that individual check in both implementations; a subsequent boundary
detects persistent mutation. This must not be described as atomic protection
against arbitrary asynchronous DDL (report:147-187; inventory.py:72-87).

Reviewer checked normalization idempotence and inventory/transaction stamp
ordering outside the diff for those named risks, did not rerun suites or
mutate files/index/Git. Historical RED/GREEN counts remain implementer
execution evidence, not independent execution by this reviewer. Actual
current capacity is FAILED at899;17cfbbc native measurement remains root-owned
and outstanding at review time. Smaller G3/local passes do not clear that gate.
