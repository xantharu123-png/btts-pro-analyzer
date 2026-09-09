# Football capture: controller independent correction review

2026-09-09. Owner of the correction: worker_failures_20260909; reviewer: Root.
Disposition: PASS for the exact discovery-scope correction, not full D3 or
live/empirical acceptance. Root did not author or change this correction.

Read the complete original independent report, correction audit, production
module and all 16 appended permanent cases. Compared the actual diff: one
native status equality and three comments, inside discovery only. The
general normalizer, explicit ID capture, clocks, report schema, old provider
return/error behavior and budgets remain unchanged.

Independently reran all 90 unchanged original reviewer cases, all 44 permanent
capture cases and both transport test modules against current Root after
the independently accepted transport merge: **215 passed in 10.17 s**, no
skips, `.pytest_tmp/root-capture-transport-integration-20260909-01.xml`.
The original three RED cases pass; native NS/TBD/PST direct-ID positive
controls and wrong-scope whole-response rejection also pass. This count is
not a new whole-project run. The earlier Root full result was 4449 passed,
18 platform skips and 97 subtests before both correction integrations.

Exact reviewed bytes:

```text
ae8e0dd25a4003519d35c86d904d807c94b16137765ded0f021b4beb97f91b52  context_sources/football_capture.py
6a3b10167cdec99de2b62863f66bda559e61a918bc05ab2eb250a01b1834a67b  tests/test_context_football_capture.py
4420382a18108daf25cc895fdd164c9bebbc0cc61f9112361eecbb5c9323f177  docs/audits/2026-09-09-d3-football-capture-ns-korrektur.md
914b96cdd593c83c34065956f3c38467f292040a4156a843be2cbed6b8a15e87  original independent review
```

The original independent probes/report remain unchanged and preserved.
No actual provider/VPS run, empirical improvement or new UI is implied.
