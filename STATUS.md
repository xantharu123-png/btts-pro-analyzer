# STATUS

Knappe, fortlaufende Statusseite. Bei jeder Übergabe oder jedem Release den Abschnitt
„Stand“ ersetzen, nicht anhängen; Historie steht in `TODO_AKTUELL.md` und
`PC_WECHSEL_UEBERGABE.md`. Regeln und Einstieg: `AGENTS.md`.

## Stand: 21.10.2026

| Bereich | Status |
|---|---|
| Produktion (VPS) | unverändert auf dem Stand vom 17.10.2026; nichts aus dem Audit-Branch deployt |
| `origin/main` | `be5e441` (18.10.2026) |
| Audit-Branch | `claude/audit-repairs-20261019`, 18 Commits vor `main`, PR #1 offen und mergefähig, CI-Schnelljob grün |
| Codex-Worktree | `.worktrees/audit-repairs-20261013`, 7 unveröffentlichte Commits, 18 ungesicherte Änderungen; Auftrag in `docs/handoffs/2026-10-21-codex-auftrag.md` |
| Hauptcheckout `betboy-app` | veraltet (60 Commits hinter `main`), fremdes WIP; nicht benutzen |

## Erledigt auf dem Audit-Branch

- Daily3: Mindestquote je Auswahl, Vormerkung nur ab Mindestquote (aktiv; `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab).
- Karte: Mindestquote und Preisstatus auf erster Ebene.
- Rechtsfooter mit 18+ und Spielsucht-Hilfe; Rechtslinks aus Env, sonst Platzhalter.
- Kundenzugang fail-closed, sobald `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- Marktbenchmark, Mischungsgewicht, optionales Markt-Gate (aus), Dixon-Coles mit Varianten (Opt-in), FDR über Ligen (an), Tennis-Populationsfit (Option), CI, Lockfiles.

## Kernbefunde

- 0 von 112 Liga×Markt-Zellen schlagen den No-Vig-Closing-Markt; Preispolicy-Replay ROI −5,5 %.
- Mischungsgewicht Modell/Markt out-of-sample 0,00.
- Hybrid Dixon-Coles (Ergebnis) + Legacy (Tore) ist das beste Modell (56 Zellen signifikant besser, 32 schlechter); kein Modell schlägt den Markt.

## Offen

| Wer | Was |
|---|---|
| Owner | Merge-Entscheidung PR #1 (jetzt oder nach Codex) |
| Owner | Env auf dem VPS prüfen, bevor die neue App startet (`deploy/README.md`, Portal-Token) |
| Owner | Impressum/Datenschutz/AGB ausfüllen, prüfen lassen, URLs setzen |
| Owner | VPS-Release über den geprüften No-Backup-Weg |
| Codex | Branch integrieren, Konflikte lösen, Prüfbefehle, Release vorbereiten (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Codex/Claude | Linux-Vollnachweis (GitHub-Job `full` scheitert am Speicherlimit; Suite halbieren) |
| Codex/Claude | Hypothese H4 (venue-spezifische DC-Parameter), kohärenter Hybrid, Quotenabruf aller Seiten, Edge-Cap als Produktregel |

## Wo nachlesen

`AUDIT_BERICHT_2026-10-16_CLAUDE.md` (Befund), `docs/audits/2026-10-19-audit-reparaturen.md`
(Protokoll mit Zahlen), `docs/handoffs/2026-10-20-claude-uebergabe.md` (Code-Übergabe),
`docs/audits/2026-10-17-claude-gegenpruefung.md` (Nutzerentscheidungen 17.10.).
