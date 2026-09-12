- **P1: Keep input lifetime validation inside the rollback scope after the actual final footprint I/O.** — **ADDRESSED.** The consumer now passes the actual bound live check as `final_validate=prepared.assert_intact` at `context_storage_v2/tennis_consumer.py:587`. The shared owner performs its existing post-yield `_check_footprint` at `context_storage_v2/refs.py:170`, calls the validator at `context_storage_v2/refs.py:171-174`, and only then releases the savepoint at `context_storage_v2/refs.py:187-188`. Validator exceptions remain inside the existing `try` and therefore run the existing rollback and SQLite error-conversion path at `context_storage_v2/refs.py:175-186`. The private keyword-only default remains `None` at `context_storage_v2/refs.py:163`, so unchanged callers retain the prior path. The fix adds no second transaction/footprint pass and no detached proof, schema, limit, source, model, odds, or publication-format authority.

### New Breakage in the Fix Diff

- None. The authorized product change is limited to the optional private-owner seam and its bound consumer use. The default and validator paths are covered at `tests/test_context_storage_refs.py:518-591`; the real late-`disk_usage` feature-lifetime rollback is covered at `tests/test_context_storage_tennis_consumer.py:547`.

### Checks and Retained Evidence

- RED 12 is the unchanged product failure: `.pytest_tmp/task51-fix1-consumer-red-12.xml:1` records 1 test / 1 failure, `DID NOT RAISE StorageIntegrityError`, SHA256 `83be17c2afc36a51d3941566d0816d7bf37b85b8e7cb05147d4af8f2661598aa`.
- RED 13 separately establishes the missing private seam: `.pytest_tmp/task51-fix1-seam-red-13.xml:1` records 7 tests / 6 failures / 1 default-path pass, with all six failures reporting the absent `final_validate` keyword, SHA256 `734d78aa4663be7526d88c5c39dfde91ff5c105483ef1aafb1c9c7fd06c638b6`.
- Focused GREEN 14 records 9 passes, including the unchanged final-code-read regression, the real final-footprint regression, default/validator success, exactly-once/order, rollback/error conversion, and earlier-failure suppression: `.pytest_tmp/task51-fix1-focused-green-14.xml:1`, SHA256 `5de4d8e1340c9c7e72d657704a129684a530937c568e9b96f59ac0b021977c43`.
- Final scoped XML records 411 passes in 84.937 seconds with zero failures/errors/skips: consumer 55, refs 106, snapshots 96, ref chunks 71, snapshot source 83. `.pytest_tmp/task51-fix1-final-scope-15.xml:1` matches SHA256 `64cd5582a4c4a734c9a3c8cefec66cfce968f810d054dc029f0dd0a573a184fb`; its system-out/system-err elements are empty. Product/test hashes match the fix report. No author suite or broad regression was rerun for this review.
- The complete supplied fix package matches BASE `f777e9ea2b6313e187d911877f5669a832ee5786`, HEAD `4d538203d2b50c61b6dfba9e7681b7e0061e9f56`, diff SHA256 `c599431481709a7590b01817cdaea585aa9c2442d8e395f9de7b50251a29bc26`, and full report SHA256 `b334b9084d681f82a30b853aac480f3e6076fab557b3ff0b403316bee040ef6a`.

### Out-of-Scope Observations

- None within the fix diff. Native/global capacity and custody, fresh Corpus-D2 integration, B verification, restore, empirical acceptance, deployment, and release readiness remain separate unverified gates and are not implied by this scoped result.

### Verdict

- **Fix round: All findings addressed, no new Critical/Important breakage.** Task 51 FIX ROUND 1 is clean within its stated scope.
