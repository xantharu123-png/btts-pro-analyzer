# STATUS

Knappe, fortlaufende Statusseite. Bei jeder Übergabe oder jedem Release den Abschnitt
„Stand“ ersetzen, nicht anhängen; Historie steht in `TODO_AKTUELL.md` und
`PC_WECHSEL_UEBERGABE.md`. Regeln und Einstieg: `AGENTS.md`.

## Stand: 22.10.2026

| Bereich | Status |
|---|---|
| Produktion (VPS) | unverändert auf dem Stand vom 17.10.2026; `main` ist noch nicht deployt (Env-Prüfung vorher, `deploy/README.md`) |
| `origin/main` | `24837c3` = Merge von PR #2 (Folgearbeiten) am 22.10.2026; enthält PR #1 (`62e6e73`) |
| Folge-Branch 2 | `claude/followups-2-20261022`: No-Vig-Marktwahrscheinlichkeit aus Buchmacher-Partitionen (`market_consensus.no_vig_market_probability`), Edge-Kappung darauf, `goal_model` im Artefakt-Builder, Validierungsvergleich Hybrid vs. Legacy (läuft) |
| Codex-Worktree | `.worktrees/audit-repairs-20261013`, 7 unveröffentlichte Commits, 18 ungesicherte Änderungen; muss `main` einmergen (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Hauptcheckout `betboy-app` | veraltet, fremdes WIP; nicht benutzen |

## Erledigt auf dem Audit-Branch

- Daily3: Mindestquote je Auswahl, Vormerkung nur ab Mindestquote (aktiv; `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab).
- Karte: Mindestquote und Preisstatus auf erster Ebene.
- Rechtsfooter mit 18+ und Spielsucht-Hilfe; Rechtslinks aus Env, sonst Platzhalter.
- Kundenzugang fail-closed, sobald `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- Marktbenchmark, Mischungsgewicht, optionales Markt-Gate (aus), Dixon-Coles mit Varianten (Opt-in), FDR über Ligen (an), Tennis-Populationsfit (Option), CI, Lockfiles.

## Kernbefunde

- 0 von 112 Liga×Markt-Zellen schlagen den No-Vig-Closing-Markt; Preispolicy-Replay ROI −5,5 %.
- Mischungsgewicht Modell/Markt out-of-sample 0,00.
- Kohärenter Hybrid `dixon_coles_hl365_hybrid` (eine Matrix: DC-Struktur, Legacy-Torsumme) ist das beste Modell (148 Zellen signifikant besser als Legacy, 111 schlechter); venue-spezifisches DC (H4) widerlegt; kein Modell schlägt den Markt.

## Offen

| Wer | Was |
|---|---|
| Owner | Merge-Entscheidung PR #1 (jetzt oder nach Codex) |
| Owner | Env auf dem VPS prüfen, bevor die neue App startet (`deploy/README.md`, Portal-Token) |
| Owner | Impressum/Datenschutz/AGB ausfüllen, prüfen lassen, URLs setzen |
| Owner | VPS-Release über den geprüften No-Backup-Weg |
| Codex | Branch integrieren, Konflikte lösen, Prüfbefehle, Release vorbereiten (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Codex | Linux-Vollnachweis über die VPS-QA-Launcher (Gruppen A/B); der 7-GB-GitHub-Runner trägt die Suite auch halbiert nicht (Exit 137), zusätzlich 21 runner-spezifische Fehlschläge in `test_native_context_*` |
| Codex/Claude | Hybrid-Aktivierung vorbereiten (Walk-forward, Kalibrierung, Pins), Quotenabruf aller Seiten, Edge-Cap prospektiv prüfen (`docs/superpowers/plans/2026-10-21-edge-cap.md`) |

## Wo nachlesen

`AUDIT_BERICHT_2026-10-16_CLAUDE.md` (Befund), `docs/audits/2026-10-19-audit-reparaturen.md`
(Protokoll mit Zahlen), `docs/handoffs/2026-10-20-claude-uebergabe.md` (Code-Übergabe),
`docs/audits/2026-10-17-claude-gegenpruefung.md` (Nutzerentscheidungen 17.10.).
