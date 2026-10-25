# STATUS

Knappe, fortlaufende Statusseite. Bei jeder Übergabe oder jedem Release den Abschnitt
„Stand“ ersetzen, nicht anhängen; Historie steht in `TODO_AKTUELL.md` und
`PC_WECHSEL_UEBERGABE.md`. Regeln und Einstieg: `AGENTS.md`.

## Stand: 23.10.2026

| Bereich | Status |
|---|---|
| Produktion (VPS) | `87d334a` live seit 23.10.2026 21:27 CEST (No-Backup-Fast-forward von `6946e3b`, Beleg `output/release-20261023-7/deploy-01.log` ausserhalb Git); Preisregel 1,20 nur im Hintergrund (keine Mindestquoten-Hinweise, keine Buchmacherquoten), Hauptauswahl je Spiel nach Modellwahrscheinlichkeit, Freigabe ohne Aufstellungspflicht, Pro-Tarif, Shadow-Kohorten mit Policy v6; Website zeigt seit 23.10. abends wieder öffentliche Fussball-Tipps |
| `origin/main` | Stand nach Merge von PR #21 (keine 1,20-Hinweise) am 23.10.2026; enthält PR #20 (Protokoll), #19 (Hauptauswahl, Karte), #18 (Protokoll), #17 (App-Lader), PR #12 (Zähler-Fix), #14 (Preisregel 1,20), #15 (Freigabekontext), #16 (Protokoll), PR #10 (Frischeregel 3 h, Policy v6), PR #7 (`fd45176`, live), #8/#9 (Doku), enthält PR #1 (`62e6e73`), #2 (`24837c3`), #3 (`08b7473`), #4 (`9b0382f`), #5 (`be6258c`, Hybrid-Aktivierung vorbereitet), #6 (`a6661a6`, Edge-Cap-Protokoll); Quick-CI grün |
| Offene Claude-Branches | keine |
| Codex-Worktree | `.worktrees/audit-repairs-20261013`, 7 unveröffentlichte Commits, 18 ungesicherte Änderungen; muss `main` einmergen (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Hauptcheckout `betboy-app` | veraltet, fremdes WIP; nicht benutzen |

## Erledigt auf dem Audit-Branch

- Daily3: Mindestquote je Auswahl, Vormerkung nur ab Mindestquote (aktiv; `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab).
- Karte: Mindestquote und Preisstatus auf erster Ebene.
- Rechtsfooter mit 18+ und Spielsucht-Hilfe; Rechtslinks aus Env, sonst Platzhalter.
- Kundenzugang fail-closed, sobald `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- Marktbenchmark, Mischungsgewicht, optionales Markt-Gate (aus), Dixon-Coles mit Varianten (Opt-in), FDR über Ligen (an), Tennis-Populationsfit (Option), CI, Lockfiles.
- Shadow-Pfad: zweite Kohorte mit dem Hybrid (`BETBOY_SHADOW_HYBRID_BASIS`, an) und Edge-Cap-Protokoll je Tipp (`shadow_edge_cap`, 8 pp, nie angewendet).

## Kernbefunde

- 0 von 112 Liga×Markt-Zellen schlagen den No-Vig-Closing-Markt; Preispolicy-Replay ROI −5,5 %.
- Mischungsgewicht Modell/Markt out-of-sample 0,00.
- Kohärenter Hybrid `dixon_coles_hl365_hybrid` (eine Matrix: DC-Struktur, Legacy-Torsumme) ist das beste Modell: 148 Zellen signifikant besser als Legacy, 111 schlechter; im Release-Gate 262 statt 224 glaubwürdige Zellen, kein Markt verliert. Venue-spezifisches DC (H4) widerlegt; kein Modell schlägt den Markt.
- Marktwahrscheinlichkeit (No-Vig, Shin/Power) liegt jetzt aus den gespeicherten Buchmacher-Partitionen vor; die Edge-Kappung (Default aus) nutzt sie.
- **Preisregel seit 23.10.2026 (Owner):** Tipps erscheinen nach Modell- und Kontextgates; Buchmacherquoten sind kein Gate mehr und werden nicht gezeigt, nur die 1,20-Grenze sperrt im Hintergrund (`BETBOY_PRICE_POLICY`, Default `floor`; `docs/audits/2026-10-23-preisregel-1-20.md`). Grund: seit 10.10. null öffentliche Tipps, weil die 45-Minuten-Frische nie erreichbar war. Dazu zwei weitere Sperren behoben: Freigabekontext braucht keine bestätigten Aufstellungen mehr (Scan läuft Stunden vor Anpfiff), und die Hypothesenfamilie darf ein Vielfaches von 96 sein (FDR über Ligen; die starre 96 hatte seit 20.10. jede Freigabe blockiert). Der App-Lader akzeptiert seit PR #17 unbepreiste öffentliche Tipps; vorher verwarf er das ganze Dokument und die Website blieb leer.
- **Hauptauswahl seit 23.10.2026 abends (Owner):** je Spiel führt die Auswahl mit der höchsten Modellwahrscheinlichkeit (gleiche Teilnehmer und Modellrevision), nicht mehr der statistische Lead des Produzenten; weder Karte noch Eingabemasken (Daily3-Vormerkung, Manuelle Suche, Tennis, Meine Tipps) nennen eine Mindestquote, Tennis-Tab und Multi-Sport-Suche zeigen keine Buchmacherquote mehr; die 1,20-Grenze wirkt nur im Hintergrund und begründet nur Ablehnungen (`docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md`).
- **E-Sport-Preisstatus (25.10.2026):** Die E-Sport-Quotenanbindung speicherte den alten Code `OBSERVED`, der App-Lader verwarf deshalb am 25.10. ab 06:15 das ganze Tagesdokument (Website leer). Seit PR #23 folgt der gespeicherte Status der aktiven Preisregel (mit Ausführungsfeldern bei `PLAYABLE`), und der Lader akzeptiert Altzeilen mit `OBSERVED` ohne Ausführungsfelder (`docs/audits/2026-10-23-preisregel-1-20.md`, Nachtrag).
- Hybrid-Aktivierung vorbereitet: eigene Prediction-Version und Vertragssignatur, ORIGINAL-Erfassung und Replay für die Hybrid-Basis, Shadow-Kohorte neben Legacy (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`). Produktionsbasis bleibt Legacy.
- **Shadow sammelt keine Evidenz** (`docs/audits/2026-10-22-shadow-befund.md`): API-Football-Limit seit 19.10. bei 100 Aufrufen je Tag (vorher 7 500), dadurch keine Spielpläne ab 21.10.; die Zehn-Minuten-Frischeregel der Öffnungsquote hatte seit Anfang Oktober jede Protokollierung blockiert (2 Tipps seit 1.9.). Owner-Entscheidung 23.10.: Öffnungsquote bis drei Stunden Provider-Alter, Alter je Tipp im Ledger, Policy `shadow-model-first-v6` (`docs/audits/2026-10-23-oeffnungsquote-frischeregel.md`). Das API-Kontingent ist seit 23.10. wieder Pro (7 500/Tag); der lokale Zähler übernimmt ein höheres Providerlimit seit demselben Tag sofort (`api_budget`, `scripts/api_budget_resync.py`).

## Offen

| Wer | Was |
|---|---|
| Owner | Impressum/Datenschutz/AGB ausfüllen, prüfen lassen, URLs setzen |
| Codex | Branch integrieren, Konflikte lösen, Prüfbefehle, Release vorbereiten (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Codex | Linux-Vollnachweis über die VPS-QA-Launcher (Gruppen A/B); der 7-GB-GitHub-Runner trägt die Suite auch halbiert nicht (Exit 137), zusätzlich 21 runner-spezifische Fehlschläge in `test_native_context_*` |
| Owner | Shadow-Artefakt `hybrid_cohort` beobachten; Aktivierung erst nach dem Prüfplan (300 Paare, positive untere CLV-Differenz) |
| Owner | Edge-Cap: Shadow protokolliert seit 22.10. je Tipp bestanden/nicht bestanden (`edge_cap` im Run-Artefakt); Entscheidung nach 300 abgerechneten Tipps je Gruppe (`docs/superpowers/plans/2026-10-21-edge-cap.md`) |

## Wo nachlesen

`AUDIT_BERICHT_2026-10-16_CLAUDE.md` (Befund), `docs/audits/2026-10-19-audit-reparaturen.md`
(Protokoll mit Zahlen), `docs/handoffs/2026-10-20-claude-uebergabe.md` (Code-Übergabe),
`docs/audits/2026-10-17-claude-gegenpruefung.md` (Nutzerentscheidungen 17.10.).
