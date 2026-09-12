# Task57 FIX5 scoped re-review

## Finding verdicts

### F1 — exact two-file timezone catalogue, custody, copy, and accounting: ADDRESSED

**SPEC: compliant. QUALITY: approved.**

The FIX5 delta declares exactly the ordered `Europe/Zurich` and `UTC` keys and binds them to the two Root-observed canonical regular source paths, sizes, and SHA-256 values (`tests/native_context_chain_catalogue.py:18-35,129-138`). Manifest validation rejects any other list or source alias and incorporates only those two destinations into the closed namespace (`tests/native_context_chain_catalogue.py:579-609`). Inventory observes the same fixed records through held, no-follow inputs (`tests/native_context_chain_catalogue.py:613-644`). The explanatory `/usr/share/zoneinfo/UTC` symlink is neither catalogued nor copied.

The plan adds the 2,023 logical source/copy bytes, both 4,096-byte original allocation slots, and the original containing-directory metadata without changing the separate 128 MiB new-work and original-metadata reserves or the fixed 4 GiB active/8 GiB new-work ceilings (`tests/native_context_chain_catalogue.py:191-222,517-576`). The parent installs exact copy slots before reservation use, holds both source FDs, binds their initial identities into the original observation, rejects the active-input overrun before copying, and rechecks source and complete sealed-copy identities at every existing boundary (`tests/native_context_chain.py:315-376,390-423`). The reserved copy entrypoint checks the durable ticket before its first directory creation, opens each fixed regular source via the existing no-follow copier, and seals the distinct same-parent data subtree read-only (`tests/native_context_chain.py:145-161`).

The catalogue's source checks retain full Linux FD/path identity and hashes, require native root:root regular0644 single-link inputs, and keep only the already-established portable FD-ctime exception while preserving full pathname equality (`tests/native_context_chain_catalogue.py:370-400`). Complete-copy validation rejects extra, missing, linked, writable, hash-changed, replaced, or identity-changed files/directories (`tests/native_context_chain_catalogue.py:403-428`). The focused tests cover closed-list aliases, pre-admission accounting, no-reservation/no-directory creation, held-source and sealed-copy mutation, native/portable identity fields, and actual launcher reconstruction (`tests/test_native_context_chain.py:80-239,960-1012`).

### F2 — real guarded stdlib ZoneInfo binding with no original or undeclared fallback read: ADDRESSED

**SPEC: compliant. QUALITY: approved.**

The worker adds only the two copied file paths to exact file admission. It rejects writes to them, lexical aliases/traversal into the sealed or system timezone trees, direct reads of either original system path, and narrow `tzdata` import fallback; all rejections use the existing bounded file context when an actual file open is attempted (`tests/native_context_chain_worker.py:112-194`). After `require_guard`, catalogue/control loading, and audit installation, `bind_timezone_data` rejects preloaded fallback modules, validates the complete read-only two-file tree, invokes the real stdlib `zoneinfo.reset_tzpath` with exactly the sealed root, clears the real cache, and verifies the resulting search tuple before product/dependency imports (`tests/native_context_chain_worker.py:198-228`). No timezone reader, calculation, clock, product route, Task54 callable, helper, supervisor, or limit is replaced or changed.

The tests use legitimate deterministic TZif2 bytes with the actual stdlib reader for UTC, Zurich winter/summer, and both 2026 autumn folds. They deny original system paths, sealed unlisted members, relative traversal aliases, and writes. Crucially, the missing-key regression creates a real unadmitted `tzdata` package/data tree and calls actual `ZoneInfo("Europe/Missing")`; it asserts rejection from the resulting fallback file-open context rather than from a mocked reader or manual source audit (`tests/test_native_context_chain.py:242-323`). Separate real-binding cases validate tree completeness/read-only state, preloaded fallback rejection, and guard/data/product ordering (`tests/test_native_context_chain.py:326-423`).

## New breakage in the FIX5 diff

- **Critical:** none found.
- **Important:** none found.
- **Minor:** none found.

The parent catalogue pin, manifest format, launcher reconstruction, resource-plan equality, and focused tests move together. I found no new executable change outside the four authorized harness files in the immutable FIX5 package.

## Out-of-scope observations and evidence limits

- Actual guarded native FIX5 execution has not run and is not implied by this local re-review. The prior FIX4 native stop at `/usr/share/zoneinfo/UTC` remains historical failure evidence, not a FIX5 pass.
- Root reports that the external readback was extended to the new original/copied timezone inputs and that the refreshed archive/runtime preparation is complete. Those preparation observations are outside the immutable implementation diff and do not substitute for the pending guarded native run.
- The deterministic local TZif fixtures prove the mechanism and UTC/Zurich semantics, not byte-equivalence to the two native system files. The native source hashes, modes, ownership, allocation, and copied-tree custody still require the planned external/native evidence chain.
- Task54-M1, the deferred platform fixture minor, actual native/global C/B/terminal/restore/full-suite/main/VPS gates, and the full published profiles remain open and are not findings in this FIX5 loop.

## Evidence reviewed

- Immutable package read once completely through EOF: `task-57-fix5-review-df874ba-complete.diff`, 133,843 bytes / 2,130 lines, SHA-256 `ee00c748b353e6695595b8c9cadf8316fc074155aa1c32697a2f52bff368d69a`.
- Binding FIX5 brief: 7,138 bytes / 118 lines, SHA-256 `52eb8bfdb06e737e6a5ae6c7516e06279c0366ca57e2c53f535a13cd11d38959`.
- Full author report through EOF: 88,594 bytes / 1,430 lines, SHA-256 `18dedb6a9f33f55152ab98a35932ff9f5ccc092cc184016496d2ae30c0c71bae`.
- Current source hashes match the reviewed report: parent `73befce90e1087c27350258387c1454527838b7242b767227bafd69cb4f3fff7`; catalogue `48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935`; worker `afaa8e2cfa01bb6f3d99db2b51f975569ddf84a911d0d3f3f67b840a2fa1d711`; tests `8d78df5ada52785f17be17d29b97b75f616b95d1b341b0fdaf1f941301c45bd0`.
- Recorded final XML was parsed read-only, not rerun: `task57-fix5-final-32.xml`, 60 tests / 0 failures / 0 errors / 0 skipped in 13.916 s, SHA-256 `103fab346b690eadaa131e62d2aa7e6e1547af956efac2297178bf09bd32d0b2`.
- Retained RED26/28/29/30 and GREEN31 claims were checked against the patch/report. Run28's transient cause remains explicitly unproven; the deterministic RED29 plus field-by-field regressions justify only the narrow pre-existing portable FD-ctime alignment. No suite or subprocess was rerun for this review.

## Final round verdict

**FIX5 scoped finding: ADDRESSED. SPEC: COMPLIANT. QUALITY: APPROVED.** The implementation is ready for Root's separately controlled guarded native execution. This verdict does not certify native acceptance or any later global gate.
