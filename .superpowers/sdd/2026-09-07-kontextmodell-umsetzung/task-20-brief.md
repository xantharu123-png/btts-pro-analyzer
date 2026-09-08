## Task 20: D5 — Volle Regression, empirische Entscheidung und belegtes VPS-Release

**Files:** Update `docs/audits/2026-09-07-kontext-abnahme.md`, `docs/audits/2026-09-07-kontext-daten.md`, `PC_WECHSEL_UEBERGABE.md` and plan checkboxes with verified results only. No blanket staging of screenshots, caches or unrelated reports.

**Interfaces:** Existing trusted updater `/usr/local/sbin/betboy-update <40-character-main-commit>`, SSH alias `betboy-vps`, app `/opt/betboy/app`, venv `/opt/betboy/venv`, services from `deploy/systemd/`.

- [ ] **Verify exactly the release candidate.** Read Git status, diff/check and upstream; prove changed paths match completed A/B/C/D tasks. Request code review using the applicable review skill before claiming completion. Do not dispatch agents unless execution mode/skill/user allows them. All P1/P2 correctness findings affecting this release require fix plus new targeted regression; unchanged empirical failure must not be “fixed” by weakening policy.
- [ ] **Run full local regression.**

```powershell
& .\.codex_test_venv\quality\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/context-release-final
if ($LASTEXITCODE -ne 0) { throw 'Context release tests failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff check failed' }
```

Use a new suffix if that basetemp already exists. Report actual pass/skip/subtest counts, never the historical 1,724 figure as a current run. Compare Cricket fixtures exactly. Existing account/ticket/HMAC tests and ordinary quote-independent visibility must pass. Validate all Python imports and configured worker commands using current local dependencies.
- [ ] **Evaluate the real frozen experiment before effect activation.** Attach D1/D2 artifact hashes, real events, blocks, coverage, paired statistics, calibration and each family outcome. Technical deployment can include unactivated experimental software and independent tour refresh; document precisely which effects remain unvalidated/unavailable. Do not use fabricated data or a successful source call to satisfy empirical criteria.
- [ ] **Commit/push exact reviewed files.**

```powershell
git diff --cached --name-only
git remote get-url origin
git branch --show-current
```

Verify trusted remote and `main`, stage only the explicit files of completed tasks, inspect staged diff, commit. `git push origin main`; then `git ls-remote origin refs/heads/main` must match local full HEAD. Use managed approval for Git/network operations when required; no force-push and no secret in command output. A documentation-only commit is not described as a functional deployment.
- [ ] **Deploy through the existing trusted updater with an exact hash.**

```powershell
$contextReleaseHead = (git rev-parse HEAD).Trim()
if ($contextReleaseHead -notmatch '^[0-9a-f]{40}$') { throw 'Invalid release revision' }
ssh betboy-vps "sudo /usr/local/sbin/betboy-update $contextReleaseHead"
if ($LASTEXITCODE -ne 0) { throw 'VPS deployment failed' }
```

Immediately before calling, verify upstream equality, clean relevant worktree, available backup and expected previous server revision. Do not bypass updater migration/backup checks or manually reset server files. No application data collection/settlement on the local PC.
- [ ] **Verify production identity and health separately.**

```powershell
ssh betboy-vps 'sudo -u betboy git -C /opt/betboy/app rev-parse HEAD'
ssh betboy-vps 'sudo systemctl is-active betboy-app caddy'
ssh betboy-vps 'sudo systemctl list-timers --all "betboy-*" --no-pager'
ssh betboy-vps 'sudo systemctl --failed --no-pager'
```

Read exact service/timer state, not merely process existence. Check local and public health endpoints used by the current deployment. Verify the backup archive includes and restores the context DB; seven timers are still enabled/scheduled and **do not pull/deploy code**.
- [ ] **Observe one real relevant worker cycle.** Use the existing `betboy-tennis.service`/`betboy-wettfinder.service` and scheduler; if a manual execution is necessary, first check it is not already running and use systemd's single service rather than a duplicate Python process. Record start/end, exit status, actual tour artifact identities/coverage, event/context snapshot counts and data gaps. Timer ACTIVE alone is not evidence of a completed calculation. Respect API budget limits; no forced all-source rescan on repeated UI reloads.
- [ ] **Reload the production UI in a real browser.** Verify used probabilities/roles match persisted snapshot and both tabs show the same event revision; missing and low quotes only affect price copy. Inspect desktop/mobile rendering and console/page/request errors. Check source/schema text and training diagnostics are not leaked into normal cards. Read-only observation only; place no bets.
- [ ] **Finish the handoff with evidence, not a blanket claim.** Record local/GitHub/VPS exact hashes, tests, backup/restore, actual worker result, independently refreshed tours and per-family data/software/empirical/activation status. Include unresolved external data dependencies and the next actionable packet. “Alles erledigt” requires all five sports and the agreed empirical acceptance, not just deployed code. Commit/push the compact final report separately if it was generated after the code commit; identify that documentation-only difference honestly.

### Binding inherited context (verbatim)

- Keine Quote, Buchmacheridentität, Mindestquote oder Preisfreigabe als Modell- oder Rankingmerkmal.
- Kein pauschales Wettartenverbot. Ein nicht aktivierbarer Kontextteil entfernt keine berechenbare Basisprognose.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Keine neue Echtgeldfunktion; 15K-Konto-, Einsatz-, Ticket- und Abrechnungsregeln bleiben unverändert.
- Alte Prognosen, authentisierte Tickets und Abrechnungen werden nicht umgeschrieben.
- Keine kostenpflichtige Quelle, neuer Vertrag oder Tarifwechsel ohne gesonderte Zustimmung.
- Nur der VPS schreibt produktive Daten; lokale Tests/Forschung verwenden isolierte Dateien.
- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende Zeitblöcke.
- Mindestens 2 % relative Verbesserung des innerhalb eines Events gemittelten primären Brier-Verlusts; Newey-West/HAC und Benjamini-Hochberg, FDR 5 %, über alle untersuchten Familien.
- Mittlerer Verteilungs-Logloss darf nicht steigen; bestehende marktspezifische Kalibrierungsprüfungen bleiben erforderlich.
- Frische Daten, funktionierende Software, empirische Freigabe, Push und VPS-Aktivierung sind unterschiedliche Nachweise.

#### Kontext-Abnahme, gemeinsame Oberfläche und Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede aktivierte Kontextwirkung durch unverfälschten Modellvergleich belegen und dieselbe verständliche Prognose in beiden Tabs sicher betreiben.

**Architecture:** Ein eingefrorener Versuchsplan bindet Daten, Splits, Modelle und Zielmärkte. Gepaarte Eventverluste und Mehrfachtestkorrektur erzeugen hashgebundene Abnahmeentscheidungen. Worker veröffentlichen gemeinsame Snapshots, während Preise und Geldhistorien getrennt bleiben.

**Tech Stack:** Python, NumPy/SciPy, SQLite, pytest, bestehendes Streamlit-UI, systemd und revisionsgebundener VPS-Updater.

**Spec:** [Freigegebene Spezifikation](../specs/2026-09-07-kontextmodell-design.md), insbesondere Abschnitte 9–12.

## Global Constraints

- Alle [Global Constraints des Gesamtplans](2026-09-07-kontextmodell-umsetzung.md#global-constraints) gelten unverändert.
- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende Zeitblöcke.
- Mindestens 2 % relative Verbesserung des pro Event gemittelten primären Brier-Verlusts; Newey-West/HAC und Benjamini-Hochberg, FDR 5 %, über alle untersuchten Familien.
- Mittlerer Verteilungs-Logloss darf nicht steigen; bestehende marktspezifische Kalibrierungsprüfungen bleiben erforderlich.
- Finale Testfenster bleiben unangetastet durch Tuning; keine Freigabeübertragung auf ungetestete Populationen/Abdeckung.
- Basisprognosen bleiben sichtbar, wenn ein neues Kontextmodell nicht freigegeben ist.
- Alte Prognosen/Tickets/Abrechnungen bleiben unverändert; keine Quote als Trainings- oder Rankingmerkmal.
- Commit/Push, VPS-Code, Modellaktivierung, realer Worker-Lauf und empirische Qualität werden separat nachgewiesen.

## Dateigrenzen

Neu: `context_models/replay.py`, `context_models/training.py`, `context_models/validation.py`, `context_models/activation.py`, `model_loss_statistics.py`, `context_copy.py`, `scripts/train_context_models.py`, `scripts/evaluate_context_models.py`, `scripts/verify_context_runtime.py`. Bestehende Sportmodelle erhalten nur die in B/C beschriebenen reinen Modell-/Provenanzschnittstellen. UI-Änderungen betreffen Karten-/Signaladapter, keinen erneuten UX-Neubau.

Ausführliche Rohberichte liegen unter `runtime_paths.RUNTIME_REPORT_DIR`, konfiguriert durch `BETBOY_REPORT_DIR`; keinen zweiten Reports-Root erfinden. Die kompakten, überprüften Ergebnisse kommen nach `docs/audits/2026-09-07-kontext-abnahme.md`. Dieser Plan verwendet für lokale CLI-Ausgaben den ausdrücklich angegebenen Ordner `output/context-evaluation/`, nicht Produktionsdaten.

### Execution context

Read the full approved specification at C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907/docs/superpowers/specs/2026-09-07-kontextmodell-design.md. Original task source: docs/superpowers/plans/2026-09-07-kontext-d-validierung-release.md. This mechanical view changes only heading identifiers and repeats inherited constraints. Use the absolute test interpreter C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe from this worktree. Ensure .pytest_tmp exists; every basetemp child must be new.
