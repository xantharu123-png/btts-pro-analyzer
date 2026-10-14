# Task 21: reduce real repeated guard allocation, unchanged admission

Base74f8e0d6d5c520b577596bdf0bc3f71cb531ab07; canonical existing isolated worktree.
User explicitly resumed all remaining repairs. Existing Cold test is RED;
do not repeat discarded warmup/GC/cursor-close/threshold experiments.

Verified causal evidence: output/context-completion-20261014/memory-causal-v2/
REPORT.md. CPython3.12 cold trace shows 2000 cached tuples EACH of sizes5/6/7;
collected cycles are pytest nodes, not reader/cursor cycles. Unknown-length
tuple(generator) creates hint10 then resizes, accumulating destination caches.

Own ONLY context_storage_v2/refs.py last member of _generation, new focused
tests/test_context_storage_generation_values.py, and this task's report.
No production contracts/ref_chunks/helper/schema/resource/clock changes.
Controller owns index, Git, full regression, final publication and main/VPS.

Replace generated name/value pairs and fields(StorageLimits) on this hot
boundary with exact literal six-value snapshot in their current declared
order: input_bytes,tour_history_bytes,block_bytes,workspace_bytes,min_free_bytes,
blocks_per_set. Keep outer generation layout/index10 limits and index11 value
snapshot, exact StorageLimits type, its post_init, all SQL pragma/generation/
schema/resource/pre/post/terminal checks. No boundary skipped or cached answer.
This is an internal representation optimization, not a new persistent format.

TDD requirement: first add literal generation-value test (new shape fails
before implementation) AND six independently parameterized legitimate
mid-stream limit changes, each kept valid/tightened but must reject before
the next value. Expected values literal/currentdefaults, not computed via
productionhelper. Add future layout-completeness check in test tied to exact
six declarations; production missing fields must not silently gain acceptance.
Existing resource/lifetime tests must continue. No mock-memory getters.

First run RED. Then the minimal last-element source change. Verify unchanged
isolated cold512KiB owning test AND complete unchanged test_ref_chunks module
in separate fresh processes, output exact results; no warmup/GC/reset/filters/
thresholdraise or baseline test edits. If complete module is RED, freeze
report and return NEEDS_CONTEXT, do not iterate speculative extra owners.
Then smallest owning generation/resource neighbor modules; no fullsuite.
Use existing offline launcher and .codex_test_venv Python-B, qa_settings/PYTHONPATH
portal, new private TMP/TEMP/basetemps under output/context-completion-20261014/
allocation-owner. Windows scoped escalation permissible for existingfilelimits.
No API/VPS/backup/newagents, no commit. Read TDD+writing-good-tests and full
owning code before acting. Full source freeze and independent review follow.
