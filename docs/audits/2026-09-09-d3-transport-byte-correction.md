# D3 exact transport copies — 9 September 2026

Owning narrow correction to independent D3 P2 review of `4d33224`. Worktree:
`kontext-d3-bytefix-20260909`; original Root capture/evaluator full-run bytes
remain unchanged while this independent patch is prepared. The earlier review
and its six RED probe assertions are retained unchanged.

## Confirmed failure and correction

Python numeric equality accepted `2` as a copy of `2.0`, and `0`/`-0.0` as the
actual computed `0.0` delta. Probabilities were mathematically unchanged, and
the old immutable consumer reference and full numerical replay already rejected
rewrites. Nonetheless a newly hashed reference could pass the advertised exact
copy boundary. This is a transport integrity defect, not empirical activation.

`context_transport._validate_payload` now compares canonical JSON bytes of:

- each original input copied into ContextResult;
- used parameters AND used markets against the actual role-selected base or
  comparison copies;
- the complete actual `100 * (used - original)` delta map.

The numerical models, generic B3 contracts/tolerances, effect fitting, source
resolvers and light-read/no-fit boundary are unchanged. Rehashed arbitrary
comparison laws still require the separate full owning numerical replay;
this patch does not turn structural validation into source/fit authority.

## Actual tests and frozen identities

Twenty new permanent cases: **17 true RED / 3 positive controls**, before the
source change. They cover all three roles, original and used parameters,
applied comparison copying, exact endpoint market zeros, delta types/sign,
unchanged zero-effect bytes and detached consumer reads. After correction,
**296 passed in 5.54s** across these 20, original 61 transport, 33 copy and
182 B3 tests (`d3-bytes-own-green-20260909-02`).

The first combined green attempt had 255 passes and 41 setup errors because
this new worktree lacked the `.pytest_tmp` parent. Creating only that directory
fixed the harness; no source/assertion change was made to resolve those errors.

- Source: `feff952c7f8a7d769d7a20e25b9d164f9dd0d9470446b9d647e9aebb52e187ce`.
- New tests: `1481cb2b7f190bfe9ffa2501363029c7e973ed49bb70ebd9034aa0a1a668e00c`.
- Original tests unchanged: `805fb2b31004dc5bdf671e77a80efc6b893039027d8071f4586ee7cb5db79e88`.

Independent unchanged-probe re-review and parent integration remain required.
No provider call, actual database publication, new effect approval, money,
Cricket, main push or VPS deployment has occurred in this packet.
