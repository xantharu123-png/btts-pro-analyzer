# Historical scalar-law evidence

These files are copied verbatim, not modified model implementations. They keep
the existing scalar-law golden hashes and old capture-seam AST assertions
executable without Git history or network access. Current joint-law behavior is
tested separately in `tests/test_football_joint_calibration.py`.

| Fixture | Source revision:path | Git blob |
| --- | --- | --- |
| challenge_engine.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229:challenge_engine.py | 2ec5d40e1429470477db7330832d1cb205fdc11e |
| football_original.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229:football_original.py | f4f20e2de10c423f44a0468937c9e548af629e8f |
| challenge_15k.py.txt | 94671485b9659aa3f047491cb7c34f4ddfb03229:challenge_15k.py | 5c48f4c3f58c58124339beaa42031fc5ab2fe4b5 |
| parent_engine.py.txt | bb297bbd34ca80eb83129e87cf1559cc44ae20df:challenge_engine.py | 00a4b32eec249c4664b013c1c02ca78233114f45 |
| parent_challenge.py.txt | bb297bbd34ca80eb83129e87cf1559cc44ae20df:challenge_15k.py | 7d2ed4eeae0de7c949877111c90a9d3fe8b2928b |

`challenge_15k.py.txt` is also byte-identical to the existing approved daily
refresh reference `a1d15b6972f01ba617a62381bacf7bf08a168b1f:challenge_15k.py`.
The loader checks SHA-256 for every used source. `.gitattributes` disables
checkout line-ending conversion for these byte-verified fixtures.

Historical invalid scalar results and independent marginal-halving assertions
remain here as historical evidence only; they are not valid v13 predictions.
V13 explicitly rejects nonfinite, boolean and out-of-range target values.
