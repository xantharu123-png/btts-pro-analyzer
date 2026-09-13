# Task60 — native operator protocol checks

Actual native execution completed on13September2026 at09:35:47UTC.
This is the isolated Linux counterpart of two previously skipped native tests,
not a pytest rerun, real-baseline admission, Task61 receipt run, C/B or release.

## Reviewed program and transport

- `evidence/task60-native-admission-protocol.py` template SHA
  b73951134de6d0ffd06d2a9e3ebd0a8501864eb52953d9be857d98e7930132b1.
- Independent instrument review: APPROVED, no findings, report SHA
  871ce3645ad7e228f5913d64084e8aa8c673191b50f3aebf46babfad75321516.
- Root transport `evidence/task60-native-admission-run.ps1` SHA
  7fb4823f638f795cffba1553d60f303970cf9823e48fab7d8c1648d393cec275.
- Only the quoted bundle placeholder was substituted with exact held reviewed
  budget/admission bytes. Prepared stdin107692bytes, SHA
  627d8ef424b98052fb5197ae19ab2a38bd7fcf4291fbd631535faa6b662af526.
- Actual invoked remote command:

```text
sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK60_NATIVE exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/python3 -I -S -B -
```

Code pins were recomputed before compilation, then actual public native API
executed with real kernel process/boot clocks, not portable adapters. Parent
CPU15/AS512MiB/FSIZE1MiB/CORE0/alarm30; no product, venv, database or secret import.
Root source/action was confined to the exact new private test root:
`/var/lib/betboy-admission-task60-protocol-8574747-01`.

## Actual result

Tool chunkf13842, actual tool/SSH exits0/0,1.699859s tool wait.
GNU time: `exit=0 wall=0.22 user=0.13 sys=0.02 rss_kib=20736`.
Reported whole Python process CPU0.15121269s before final output. Stdout1579bytes,
SHA9b513f9e4045e0e9cddb049f3e5b16ff3874d0dd4b829521d3e66f3a5fc254ae;
stderr64bytes, containing only the GNU-time line, SHA
8bf3a415548b41abd7fd0def085602736febe1b7eb5e4e49878a7289870492ff.
Exact outputs retained at `.pytest_tmp/task60-native-protocol-8574747-01.*`.

Eight actual assertions/groups completed:

1. Root-owned private native namespace admits the actual owner.
2. Real competing flock acquisition is rejected without mutation.
3. Actual close retains stopped history/full charge; no refund.
4. Same consumed family is rejected without changing the closed files.
5. Symlink registry is rejected without following it into admission.
6. Group/world-writable ancestor is rejected before a journal is created.
7. Deliberately losing the actual held flock poisons live assertion and close.
8. Different-family retry in that poisoned registry is rejected without mutation.

The intentionally writable fixture is beneath a root-private0700 test root;
no existing directory permission changed. All files/links/failure journals are
preserved. These are metadata/custody admission tests, not proof of an attempted
unprivileged write denial, receipt resource enforcement or whole source identity.

## Independent post-exit readback

Separate SSH readback chunk ee3ba5, actual final exit0,0.812159s tool wait.
All four complete SHA256 values matched the terminal observation exactly:

| Registry | File | Bytes | SHA256 |
| --- | --- | ---: | --- |
| registry | diagnostic-admissions.jsonl | 2841 | 020d98c7ce8a8652ff2e20059115f08f862af0142dbc741f2ebd75608bc09766 |
| registry | e66e8a4f9b6958c5c30126ce5761e31a41d89a995fb01212811ac5e334a5f627.jsonl | 1751 | 324214aaf820be7c2995e1d67a6908b7ccdb36ac5760ec3cebc05085ead0da19 |
| loss-registry | diagnostic-admissions.jsonl | 2426 | fe54a2d9f81d1d28180d82e57f777eba220fa0543df881278a259859a291b070 |
| loss-registry | e66e8a4f9b6958c5c30126ce5761e31a41d89a995fb01212811ac5e334a5f627.jsonl | 1469 | 1c4053cf6bae8accccd5007d174c9967d40d3b5f2a3239030e5fed5e291feceb |

All four regular files root:root0600; full new root49152allocated bytes,
seven directories, one symlink, four regular files. No artifact deleted.
The deliberately broken second registry remains nonterminal/poisoned evidence,
not repaired into a success record. The program starts no descendant worker;
actual external Python/time/SSH terminal states were observed.

Two deliberately synthetic test admissions reserve300CPU each:600CPU remains
charged permanently, not the measured0.151s and not a real-baseline family.
The previously stated1770CPU engineering allowance comprises1680CPU in the
eight primary old diagnostic journals plus90CPU of separately retained sealer
allowances. Thus the ten primary diagnostic/admission journals now hold2280CPU;
including those external sealer allowances gives2370CPU conservatively, not
2370CPU in durable tickets. Six additional old roundtrip/recovery fixture
journals retain synthetic values and are not actual execution-cost claims.
The distinction was freshly checked by read-only replay at09:48:35UTC (see
task-61-known-journals-20260913.md). None of these totals is a settlement or a
claim that a full-C1800CPU preparation lifecycle has run/passed. Metadata
preflights without a durable ticket stay separately labeled.

## Remaining gates / production

Task60's two native categories now have the above concrete Linux observations.
Actual Task61 parent60/child240 prefix, full retained/source/resource checks,
the1024 receipt call, full490000growth C, B, restore and release remain open.
No original Task60/Task58 product/helper bytes changed or old suite repeated.
Fresh unrelated production read-only observation09:32:10UTC/chunka48e01:
HEAD2dd1116b68f3d94e9c24338c6c9dff9b01799221, app/Caddy active, internal/public
health both `ok`; separately known betboy-tennis.service remains failed.
No main push, VPS pull/deploy, timer/service/key or live-data change occurred.
