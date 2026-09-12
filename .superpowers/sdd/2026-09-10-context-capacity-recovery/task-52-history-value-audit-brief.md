# Task 52 — narrow existing-history admission audit, read-only product work

Named risk discovered while checking the actual Corpus->History interface:
`context_storage_v2/history.py` rejects an otherwise selected canonical row when
its length exceeds `limits.block_bytes`. The approved C specification preserves
all formerly accepted values; a processing block is not itself a statement
about old payload sizes, and large structures need their old reader or an
equivalent adapter. Determine whether the current real source owner makes the
branch unreachable for valid legacy inputs, or whether this is a real gap.

Read the C4/C6 requirements in
`docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md`; the old
unapproved heading is superseded by the current ledger/user approval. Do not
change the spec or rule the gap away merely because an old test asserts a cap.

Inspect only the named history/source/contract paths necessary for this risk.
Use an actual old normalizer, physical receipt storage/validation, old selection
and new build_history on the same small sealed test data. Native status names
are stable-code strings with no obvious size cap, but this is a hypothesis,
not a required fixture or predetermined finding. An actually invalid source
record is not a counterexample. Prefer a single bounded reproducer if needed,
not another broad suite or multiple heavy repetitions.

Product files, all existing tests/specs, Git and server remain read-only.
You may create only an ignored local probe under .pytest_tmp/task52-* and the
report `task-52-history-value-audit.md` in this directory, using apply_patch.
Use the working qa-python312-c-01 runtime and new retained output paths.
Do not dispatch subagents or mutate sources outside the newly created fixture.

Report exact accepted/rejected owner boundaries, source sizes, canonical sizes,
commands/output, named code lines, and either a concrete semantic discrepancy
or evidence that the same existing contract rejects it first. No native RSS,
overall C/B, model quality or deployment claim. Do not implement a fix yet.
