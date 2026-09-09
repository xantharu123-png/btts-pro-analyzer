# Domain reference type: independent Root rereview, 9 September 2026

**Accepted for narrow integration**: `53c9a886b8a3ef667d45b302fa45b11a7e31f015`
on exact original parent `9de9b52ab096c8c08852460dfe8226854014e789`.
The original independent report remains REQUEST CHANGES against that parent.

Root fully read the original report, complete correction audit, thirteen-line
runtime diff, all fifty new permanent cases, and both qualified original probe
files. No test/source edit was needed for this rereview. The existing
whole-document identity policy is preserved; this is not a price gate or a
partial-document redesign.

Independent rerun against the exact fix worktree: **88 passed**, no skips or
deselections, 1.62 seconds, exit zero. This includes all fifty new permanent
cases, fourteen optional-domain cases, sixteen qualified original overlay/race
controls and eight original direct bool/float-schema failures. All eleven genuine
original failures are now green. Source and fixture modules were explicitly
imported from the fix checkout before the unchanged external probes loaded,
and the runtime source path was asserted. Pytest emitted one already-imported
`anyio` assertion-rewrite warning; this did not omit a test.

Command: quality Python `-B -c`, cwd `kontext-domain-fix-20260909`, bootstrap
cwd and cwd/tests on `sys.path`; preimport `ev_signal_sources`,
`test_ev_signal_sources`, `test_riskobet_store`; `pytest.main` with `-q -p
no:cacheprovider`, the two new/owning domain files, and the unchanged
`test_domain_overlay_qualified.py` and `test_domain_reference_type_witness.py`
under the original review's `.pytest_tmp/domain-independent-20260909`.
Basetemp/JUnit: `.pytest_tmp/domain-root-rereview-20260909-01[.xml]`.

JUnit SHA256: `9750edabee4bf00e38760a10da436574656baa0e625cf0673aa51d1152bfce62`.
Runtime source SHA256:
`090b11fadbaf32246aff9ebd8afb396c6e2754dfda92d2c386d042f7377c763f`.
New permanent test SHA256:
`9befc9feee8bd69336833b63f4e648a5ebcb8a712ccfe07c9ee5dcc576ef170d`.

Healthy legacy and linked rows retain the same probability/reference when
quotes are absent, below the price threshold, playable or expired. Malformed
context provenance is rejected before Python equality can equate true/1.0/1.
No source/price request, IDs, store schema, reader code, Cricket, ticket money,
production data or VPS changed. Source truth and live worker wiring are outside
this structural acceptance; final integrated regression and release remain open.
