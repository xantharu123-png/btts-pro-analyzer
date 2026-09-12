# Task56 — read-only native small-chain import and custody preflight

This is a bounded preparation inside the approved C integration, not a new
design or an implementation task. Task51 is the sole implementation writer;
Task54 is prepared and will run after Task51's independent review.

Read this first: it is the task's requirements. Own only
`task-56-native-chain-report.md` in this SDD directory. No product/test edit,
Git/index operation, dependency installation, server command, data copy,
network access, probe rerun, cleanup or subordinate agent.

## Concrete question

The reviewed native diagnostic exercises guarded NumPy/SciPy plus one tiny
SQLite MEMORY journal. It does not run the actual Corpus/Source/History/Tennis
consumer/parts route. Identify the smallest executable next native test route
using the actual APIs; do not claim that import discovery alone is execution
or B runtime-closure authority.

Read the Task54 integration brief and the current exact consumer imports/API.
Inspect `tests/native_preparation_seal.py`,
`tests/native_preparation_probe.py`, `tests/native_preparation_worker.py` and
only the owner/import couplings needed for this concrete route. Root has
confirmed that `tennis.tour_state`, `tennis.model_state` and `tennis.predict`
also import pandas, backtest and data_loader/requests. The original code paths
remain rooted at `tennis/predict.py` (not predictor.py).

## Required output

- An exact local code/dependency import map for the real small route, naming
  lazy imports and data-file lookups that a top-level-only scan would miss.
  Do not install/import arbitrary packages to make an assumed map work.
- The concrete limitations of the existing five-helper/four-package sealer and
  guarded child entrypoint, with file:line evidence. Identify which interfaces
  can be reused unchanged and which new fixed catalogue/worker is necessary.
- The real output-slot and lifetime sequence (copy writer closes; fresh held
  source/actual raw+D2 admission; old parts writer closes; live History/features;
  separate new-consumer writer). Name a missing seam if one is present rather
  than proposing a fake dataclass/descriptor permission.
- A concise native measurement checklist preserving CPU300/AS2GiB/RSS<1GiB/
  output1MiB, fixed new-work/retries8GiB, active inputs4GiB, history1GiB/tour,
  blocks16MiB and actual free reserve4GiB. Global preparation1800CPU/3600wall
  is not established by the old small probe or a fresh per-run stopwatch.

No complete proof/publisher redesign, no speculative performance optimization,
no Windows-to-Linux extrapolation, no changes to old model/schema/admission,
no A0/P4b3/Cricket/daily-job work. Full three growth profiles, B, restore and
release remain later gates. Bound the report to the executable next native
small-chain step and concrete uncertainties; return status and report path.
