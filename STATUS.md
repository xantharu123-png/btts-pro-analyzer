# STATUS

Knappe, fortlaufende Statusseite. Bei jeder Übergabe oder jedem Release den Abschnitt
„Stand“ ersetzen, nicht anhängen; Historie steht in `TODO_AKTUELL.md` und
`PC_WECHSEL_UEBERGABE.md`. Regeln und Einstieg: `AGENTS.md`.

## Stand: 22.10.2026

| Bereich | Status |
|---|---|
| Produktion (VPS) | unverändert auf dem Stand vom 17.10.2026; `main` ist noch nicht deployt (Env-Prüfung vorher, `deploy/README.md`) |
| `origin/main` | `9b0382f` = Merge von PR #4 (Status) am 22.10.2026; enthält PR #1 (`62e6e73`), PR #2 (`24837c3`) und PR #3 (`08b7473`); Quick-CI grün |
| Folge-Branch 3 | `claude/hybrid-shadow-20261022` (PR #5): Pins je Basis, ORIGINAL für den Hybrid, Shadow mit beiden Basen (`BETBOY_SHADOW_HYBRID_BASIS`, Default an) |
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
- Kohärenter Hybrid `dixon_coles_hl365_hybrid` (eine Matrix: DC-Struktur, Legacy-Torsumme) ist das beste Modell: 148 Zellen signifikant besser als Legacy, 111 schlechter; im Release-Gate 262 statt 224 glaubwürdige Zellen, kein Markt verliert. Venue-spezifisches DC (H4) widerlegt; kein Modell schlägt den Markt.
- Marktwahrscheinlichkeit (No-Vig, Shin/Power) liegt jetzt aus den gespeicherten Buchmacher-Partitionen vor; die Edge-Kappung (Default aus) nutzt sie.
- Hybrid-Aktivierung vorbereitet: eigene Prediction-Version und Vertragssignatur, ORIGINAL-Erfassung und Replay für die Hybrid-Basis, Shadow-Kohorte neben Legacy (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`). Produktionsbasis bleibt Legacy.

## Offen

| Wer | Was |
|---|---|
| Owner | Env auf dem VPS prüfen, bevor die neue App startet (`deploy/README.md`, Portal-Token) |
| Owner | Impressum/Datenschutz/AGB ausfüllen, prüfen lassen, URLs setzen |
| Owner | VPS-Release über den geprüften No-Backup-Weg |
| Codex | Branch integrieren, Konflikte lösen, Prüfbefehle, Release vorbereiten (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Codex | Linux-Vollnachweis über die VPS-QA-Launcher (Gruppen A/B); der 7-GB-GitHub-Runner trägt die Suite auch halbiert nicht (Exit 137), zusätzlich 21 runner-spezifische Fehlschläge in `test_native_context_*` |
| Owner | Nach dem Deploy: Shadow-Artefakt `hybrid_cohort` beobachten; Aktivierung erst nach dem Prüfplan (300 Paare, positive untere CLV-Differenz) |
| Codex/Claude | Edge-Cap prospektiv prüfen (`docs/superpowers/plans/2026-10-21-edge-cap.md`); Shadow-Pfad soll beide Kohorten protokollieren |

## Wo nachlesen

`AUDIT_BERICHT_2026-10-16_CLAUDE.md` (Befund), `docs/audits/2026-10-19-audit-reparaturen.md`
(Protokoll mit Zahlen), `docs/handoffs/2026-10-20-claude-uebergabe.md` (Code-Übergabe),
`docs/audits/2026-10-17-claude-gegenpruefung.md` (Nutzerentscheidungen 17.10.).
