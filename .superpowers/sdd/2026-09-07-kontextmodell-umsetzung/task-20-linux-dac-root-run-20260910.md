# Actual Linux root / betboy DAC — Root execution

2026-09-10 CEST / 2026-09-09 UTC. **Passed**, narrowly scoped synthetic fixture.
This closes the real Linux principal/file-access test, not the installed
trusted updater A-to-B transition and not a production context deployment.

## Reviewed execution and preserved evidence

Root read the complete fixed design and script before execution. The original
design remains an explicitly historical NOT RUN artifact, not silently edited
into a successful result. Independent local design check: 24 passed, zero
skips, 0.66 seconds, XML
`kontext-updater-hook-20260909/.pytest_tmp/hook-linux-dac-root-design-04.xml`,
SHA256 `762275f4eddc59b93361a1e566150cbada673c4d3bf7bf0a0bac8cd3b74c2c37`.
These local checks alone were not DAC evidence.

The exact reviewed script was transferred into the already known private QA
directory, verified as uid/gid 1000:1000, mode 0600, one link and 23799 bytes.
A fixed stdin bootstrap verified no-follow path/descriptor identities and
the complete hash, then executed those same in-memory bytes. No arbitrary
argument, source path, key path, installer or privileged app import exists.
Root execution imports only stdlib; app/model code runs as the actual betboy
account using the existing interpreter. No dependency was installed.

Actual command completed exit 0. New fixture:
`/tmp/betboy-context-dac-5zxtb2ij`. Full bounded result:
`/tmp/betboy-context-dac-5zxtb2ij/private/RESULT.json`, SHA256
`015e0300db0a7139e206e0ac8161dc2646d005272b0652527b1f166d99cf06c0`.
Root read the complete synthetic report. The archived local wrapper keeps
its exact bytes as a JSON string, not parsed/reserialized JavaScript numbers;
large inode/time identities therefore are not rounded through IEEE doubles.

## Actual results

- betboy uid 997, gid 987, sole group 987; successful read of sealed input
  and create/read/chmod/unlink in its own new scratch are positive controls.
- Twelve actual denied operations: write, chmod, unlink, replace, hardlink;
  WAL/SHM/journal creation; reads of four root-private archive/key/ZIP/receipt
  paths. The key is deliberately public synthetic material, not a production
  secret or a claim about financial-chain validation.
- Unchanged hook extracted and sealed a genuine SQLite online-backup WAL
  image via SQLite to DELETE mode, root:betboy 0440, one link. No manual
  header mutation and no overwrite of the original evidence image.
- Real CLI structural case returned 0: two tour artifacts, one observation,
  one manifest, no snapshots, no limitations; empirical flag false.
- Real transport-only case returned 2: three artifacts, two observations,
  one manifest and one B3 snapshot. The sole actual limitation was
  `d3-snapshot-input-binding-unavailable`; the unchanged closed report
  validator accepted it, with empirical flag false.
- Real broken-reference CLI returned 1/ArtifactIntegrityError. The unchanged
  validator rejected it. No forged success report or widened whitelist.
- Genuine inner one-second GNU timeout terminated a 30-second app sleeper
  with 124; that status was rejected. The original outer 600/610-second
  bounds were unchanged, but this was not a 600-second expiration test.
- A genuine 8 MiB child output was bounded by the unchanged head at exactly
  1048577 bytes. The unchanged 1 MiB reader limit rejected the oversized
  report. No unbounded child capture was substituted.
- Whole staged-source manifest and file identities, source archive/image,
  private ZIPs and sealed inputs were verified pre/post. No children from
  the fixture's own process sessions remained.

The new fixture is root:betboy 0710; private files root:root 0600 under 0700;
source tree root:betboy 0750/0640; sealed directories 0750 and databases 0440;
app scratch betboy:betboy 0700. The exact real hook's runuser/env-i/timeout/
head chain was used. No production job was stopped, old QA tree deleted,
real database/key read, group/unit/pin changed or root updater installed.

## Pins

```text
design DRAFT.md 551f43ddcc5ca95c730a2a7062dc35fd2a4b39c59129c8b8fc00dc3f00479088
root_dac_smoke.py 958836d1a74376cf76f35d44b526cfd4b7438deadc61f539a7d86b6e8b0ad756
test_smoke_design.py dea1f93cf0fe119b888d28451c72315ac608ebd0c5f53dddb8798563b7806aaf
Root bootstrap 2d20097d9bc05c54d61edce5d4a7c551b5d7a13b0cfbbc3b128f7d27eee9a939
trusted hook 74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f
a224d13 archive e76488f9a34ca8544667411151bac6e69ab275ccad4d6079c47a2051cf83492f
original WAL backup image 66ee78e58b4b70fb33b0f70f8b7995ac220025ef2c5bc8f34c273dfa5cfe6c09
actual sealed DELETE image 2662cf5ac908e0c688796faf6584e6b6f1bf0a226af660a3bbf59971ac8ab20b
test source helper 71dc37951bed4e6fc576e842829f7b0af08b692243bd6c353423237c9cddef62
app-only scratch builder 71a9615d1ef908746c21535a89164471e2f4beb480e8fe5c668498715d223cbc
source manifest ac70daac9c3d8483b4c3d1b2c85e67cc3be2c094d65c88a075aa16378300570e
```

The installed production updater still needs its reviewed Bridge A followed
by context target B through the trusted updater itself, complete backups and
revision/service/health verification. No empirical source/fit capability is
created by this successful infrastructure test.
