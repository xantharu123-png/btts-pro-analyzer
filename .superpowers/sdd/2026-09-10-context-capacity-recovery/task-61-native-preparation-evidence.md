# Task61 native input preparation: upload passed, catalogue STOP

Observed on 13 September 2026. This records one actual fixed upload and one
actual fixed catalogue-preparation attempt. Neither invoked diagnostic main,
Task60 admission, a receipt worker, or an application update. The completed
Task58 and Task61 child-prefix protocols were not repeated.

## Reviewed identities

- Root controller HEAD at execution: `33b758cfb371b1f923f47c98c25e44c802465e26`.
- Exact code archive commit: `1632072216b33d85b0343c1f389f762356b62d0a`.
- Archive: `task61-1632072-01.tar`, 449 tracked nonhidden Python members,
  9533440 bytes, SHA256
  `daf6ac61183bb3a42f8401f7568b2020a0f4bdef07d07a72d295e61363bc4d4c`.
- Upload entry SHA256
  `c118672160b6fdcd5f4699e0fd63c6b89d3affeafd28ecaaf62656dc807580f0`.
- Catalogue entry SHA256
  `97b605c2b29bcce2d9b401847cc5ea4fb942f591453122e59accddbabcc895e6`.
- Runner SHA256
  `55152459a26fe5cc94cdd80fcb6ff38cd2c7f4d1b78cb4d5e62779ff58778c7b`.
- Independent bounded transport review: spec compliant / quality approved,
  SHA256 `37875733ef4a9c17e85b48305bd65e144c350fd645458dcaaae15156e062d00d`.
  T2 generic unbounded SSH logging remains a deferred Minor, not silently closed.
- Root reread the entire review/runner and freshly matched all four hashes in
  actual tool chunk `0507a6`, exit0, before either execution.

## Upload: actual success and separate readback

Actual invocation of the fixed runner with `-Mode upload`: chunk `bf10ce`,
SSH0 and outer tool0. Observed remote completion `2026-09-13T12:38:47Z`.
Held stdin9533440 bytes and SHA matched the exact archive above.

GNU time: `exit=0 wall=4.46 user=0.12 sys=0.09 rss_kib=16000`.
Reported process CPU208754551ns; archive allocated9535488 bytes.
No archive extraction or import occurred. Only these previously absent roots
were created:

- `/var/lib/betboy-receipt-input-task61-01`, root:root0755, inode2177134.
- `/var/lib/betboy-receipt-registry-task61-01`, root:root0700, inode2177135.
- `/var/lib/betboy-receipt-task61-01`, root:root0755, inode2177136.

Separate read-only SSH readback `6cf9f4`, exit0, at12:39:06UTC confirmed each
directory is4096 logical/4096 allocated bytes. Only the input root contains a
file: exact archive root:root0444, inode2177137,9533440 bytes/18624 blocks of
512 bytes, full SHA equal. Registry/job remained empty.

Retained local logs under `.pytest_tmp/`:

- `task61-native-prepare-upload-01.stdout.log`,471 bytes,
  `efcd9851f9dc490169bc51c5403257c81389effed966bbfcc1a102f540aaaab0`.
- `task61-native-prepare-upload-01.stderr.log`,62 bytes,
  `bad6c00482435d90940d4b1ddf236847ea1db686a1d4529923983700afa5abc4`.

## Catalogue: actual signal termination, no completed first inventory

One invocation with `-Mode catalogue`: initial chunk `074be5`, session24529;
terminal chunk `5c540b`. Held stdin474157 bytes / SHA256
`88368cf0e0733fd54a94d7bddbe07ce2c30e08c3385da654f7de67845be2e76d`.
The runner printed waiting status at30 and60 seconds; no retry was issued.

**Actual SSH exit137; PowerShell/outer tool exit1; signal9.** GNU time printed:

```text
Command terminated by signal 9
TASK61_PREP exit=0 wall=74.12 user=46.68 sys=13.18 rss_kib=32176
```

The printed `%x=0` is not a successful child exit: GNU time explicitly observed
signal9 and SSH returned137. The approximately59.86 reported CPU seconds are
consistent with this instrument's hardCPU60 boundary. Do not represent that
inference as a separately observed kernel kill-reason field.

There was no stdout and no retained.json/catalogue.json. Thus the initial full
retained-root scan did not reach its completed control write. No exact last
root/file is known: this fixed preparation instrument has no durable phase
prefix. This is not a measured receipt append/copy failure, a failed Task61
worker, an admitted300CPU job, or a completed native diagnostic.

Retained local logs:

- `task61-native-prepare-catalogue-01.stdout.log`,0 bytes,
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- `task61-native-prepare-catalogue-01.stderr.log`,96 bytes,
  `63693953ed82be7b9e96f05ea1d67eb449eedaa65f06a446089a70cbfb67aa19`.

## Post-stop readback and accounting

Independent read-only chunk `07a5ee`, exit0, observed12:41:22UTC:

- All three exact roots and archive retain the upload identities/modes/sizes.
- Input membership is still only the unchanged archive; registry and job are
  still empty. No admission journal, copied baseline, code/dependency tree,
  progress record, worker result or generated receipt exists there.
- No UID65534 process was listed. This preparation entry creates no child.
- Filesystem available12494200832 bytes, observed then, not a future guarantee.
- No deletion, overwrite, recovery, resealing of old files or alternate name.

Preparation CPU/wall remains actual engineering cost with no durable full-C
budget journal; do not invent a settled1800CPU lifecycle or credit/refund.
The separate diagnostic300CPU admission is still unconsumed. Upload allocated
9535488 plus three4096-byte directories; no additional catalogue file was left.

## Next bounded repair

Preserve this STOP and all earlier roots. Read the exact retained-root path for
avoidable repeated work without skipping bytes, membership, identity, journal
replay or physical allocation. The same author is assigned read-only diagnosis;
no new implementation or native attempt was authorized by this evidence file.
Any changed implementation needs a scoped brief/tests/review before a new
explicitly identified measurement. Existing60/240/300,1800/3600 and space
contracts remain unchanged. Full C, B, restore, final QA, main and VPS rollout
are still open. Production remains separately observed, not changed by this run.
