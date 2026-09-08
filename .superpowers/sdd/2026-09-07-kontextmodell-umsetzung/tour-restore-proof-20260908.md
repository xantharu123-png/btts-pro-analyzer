# Real cached ATP/WTA build and isolated Linux restore — 2026-09-08

## Scope and result

**PASS for this bounded proof:** both separated tour models were built on the
VPS from its existing versioned training seeds, then staged, archived,
verified and restored with identical registry contents and complete forecast
outputs. No production model was activated. This is not current-source
freshness, empirical improvement, a live tour database under concurrent WAL
writes, or the complete B3/D4 observation/snapshot/rollback proof.

Exact reviewed source: `2436dd411987ba0b543fd73212da6cbb72d65e99`.
Private, betboy-owned QA root: `/tmp/betboy-tour-restore-qa.jkLTynWQ`.
Actual unprivileged identity: UID 997 / GID 987. Root mode 0700.
Production Python: `/opt/betboy/venv/bin/python`, invoked with `-I -B`;
no package installation or production environment file was used.

An attempted local model-DB upload was denied by the execution reviewer and
did not run. It was not retried or disguised. The replacement transferred
only reviewed Python code and built the test DB **on the VPS**, reading only
the already-present versioned `/opt/betboy/app/tennis/data` seeds. Mutable
training/model/report paths were bound to the private QA root before imports.
All requests were forbidden. No production DB, ledger, key, mutable training
cache or legacy pickle was opened, copied or modified by these harnesses.

## Exact code identity

- LF source archive SHA-256:
  `eead4b10f0699d64444217bf7688fb95ae4c98b14a86635317b7abd9d85dff67`.
- All 19 archived source files were compared byte-for-byte with the actual
  Git blobs at the reviewed commit before upload.
- Pinned staging helper SHA-256 on the VPS:
  `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
- Build harness `output/context-evaluation/tour_build_on_vps_probe.py`:
  `03bf1b159c37526e5edbd06e6b8c833e3771ddb1a28e7c9d784186dd7d1230ae`.
- Restore harness `output/context-evaluation/tour_restore_probe.py`:
  `8aaefbd8e9d4e59a143ad8ade196068f02933d352a315e6e89997b94247e7ebc`.

Both harnesses were independently inspected before execution. The source
archive was generated with command-local `-c core.autocrlf=false`: the first
Windows archive had converted LF to CRLF and was preserved but not executed.
No repository setting or helper pin was weakened. QA files remain available;
no cleanup or broad deletion was performed.

## Actual offline build

Command, executed once on the fresh QA tree, exit 0:

```sh
sudo -n -u betboy /opt/betboy/venv/bin/python -I -B /tmp/betboy-tour-restore-qa.jkLTynWQ/tour_build_on_vps_probe.py /tmp/betboy-tour-restore-qa.jkLTynWQ
```

Logical training cutoff: `2026-09-08T17:43:41.763537+00:00`.
All 40 versioned seed hashes were identical before and after the build;
inventory SHA-256 `336bea697a3d1ff03c120f13b75d37f78a6ad6351f3a9a0862da0ea62bde44ee`.
Both outcomes were `published`, aggregate status `complete`:

| Tour | Artifact hash | Actual data coverage |
| --- | --- | --- |
| ATP | `f23da2f665d5add7b95afcf43b5761d74d27e08f8e33f213bb01f426486d1dcd` | 2026-07-27, tournament-start proxy |
| WTA | `8177117edec99878a60708319f5a819bf39e485c5e2bde87cc9d5d64a3f05d61` | 2026-07-26, result date |

ATP serve training admitted 63,477 matches and skipped 1,133 invalid serve
contributions (884 nonpositive denominators, 249 nonfinite counts).
Calibration admitted 57,195 and skipped 1,014 (884/130 respectively).
Native match/tournament/year diagnostic identities were present throughout.
Valid Elo results were retained; WTA remained its declared Elo-only model.
Four known openpyxl extension-reading warnings occurred. Successful rebuilding
does not relabel these July seeds as fresh September data.

## Actual restore

Command, exit 0:

```sh
sudo -n -u betboy /opt/betboy/venv/bin/python -I -B /tmp/betboy-tour-restore-qa.jkLTynWQ/tour_restore_probe.py /tmp/betboy-tour-restore-qa.jkLTynWQ
```

Fixed comparison decision: `2026-09-08T17:47:18.558052+00:00`.
Results: discovered 1 / staged 1 / archived 1 / verified 1; SQLite and
foreign-key checks `ok`. Registry rows were exactly equal before/after:
2 artifacts, 2 manifests, 1 active-manifest row, including original timestamps.
Active model manifest:
`e3049dc0e8a813588afc0afa95f9868aa234abd99c223058768152c1ca805043`.

The harness asserted private ownership, sealed stage directories 0550,
database mode 0440, no WAL/SHM/journal in the sealed stage, DELETE journal mode,
exact one-member ZIP inventory, and byte-identical extracted member. It used
the unchanged unprivileged staging/backup APIs, not the privileged production
service. The tour-only registry legitimately has no 15K HMAC/key tables.

- Archive: `/tmp/betboy-tour-restore-qa.jkLTynWQ/archives/betboy-sqlite-20260908T174720Z.zip`
- Archive SHA-256: `7d233c1420cba89a8725ebf6bb510a6c97801d940343d618af3068036481722e`
- Sole member: `runtime_state/context_models.db`
- Member SHA-256: `7493ab7887a2da9f05d4af4bdec9a38d533470ad162e71e04d2003d4ea93d80c`
- Separate staging-manifest SHA-256: `de35ec76b61b5073ff3a74c306802f37123507510c931ffff598bbba450d418f`

Hash-checked manifests, both strict decoded tour states, every ordered registry
row and the full `asdict` prediction output were identical. Comparison used
fixed hypothetical pairings of players actually present in each model, Hard,
best-of-three and the same decision instant; these were restore probes, not
real scheduled fixtures or betting recommendations. Original input registry
rows remained unchanged.

## Remaining release boundaries

Current provider refresh/coverage, real prospective contextual data, learned
injury/fatigue effects, D1/D2 empirical validation, full linked B3/D4 restore
and rollback, and final production activation are still separate required
work. This proof closes the actual cached-tour build/static Linux restore
gap only. Main/live remain the separately reviewed card-analysis release.
