# Task 19 follow-up: reactive manual price decisions

Review the frozen manual-price correction only, base
`f2f7611823c8e0b23b102bafba9e880adab87f9f`, head
`c0a83f191e200b5305acbf06cf23ddfb359a0a91`.

Root reproduced in the actual browser: submit 1.12, then edit to 4.00
and blur; the old below-price decision still looked current because `st.form`
withheld edits. Required: edits to quote, bankroll or exact-selection
confirmation invalidate the previous displayed decision, without computing,
saving, archiving or changing any candidate. Explicit checking remains explicit.
The result must identify the inputs it checked. Changed model snapshots,
legacy cached decisions, edit/revert, two cards, empty/invalid inputs must not
resurrect stale results. Preserve existing manual save/price rules.

Binding plan constraints:
- Keine Quote, Buchmacheridentität, Mindestquote oder Preisfreigabe als Modell- oder Rankingmerkmal.
- Kein pauschales Wettartenverbot. Ein nicht aktivierbarer Kontextteil entfernt keine berechenbare Basisprognose.
- Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben unverändert.
- Keine neue Echtgeldfunktion; 15K-Konto-, Einsatz-, Ticket- und Abrechnungsregeln bleiben unverändert.
- Alte Prognosen, authentisierte Tickets und Abrechnungen werden nicht umgeschrieben.
- Nur der VPS schreibt produktive Daten; lokale Tests/Forschung verwenden isolierte Dateien.

Report: `docs/audits/2026-09-10-manual-price-reactivity.md` in the frozen UI worktree.
No production source edits by reviewer; no browser (Root owns it), provider,
VPS, money, full-suite rerun, Git mutation or subagents. Review the diff once;
inspect unchanged functions only for a named concrete risk. Existing AppTest
evidence is in the report. Any additional test must answer a concrete unresolved
doubt, use isolated files and a new basetemp.

Return both spec-compliance and code-quality verdicts with source lines and
findings. Root separately owns actual browser validation and final integration.
