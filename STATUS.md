# STATUS

Knappe, fortlaufende Statusseite. Bei jeder Übergabe oder jedem Release den Abschnitt
„Stand“ ersetzen, nicht anhängen; Historie steht in `TODO_AKTUELL.md` und
`PC_WECHSEL_UEBERGABE.md`. Regeln und Einstieg: `AGENTS.md`.

## Stand: 25.10.2026

| Bereich | Status |
|---|---|
| Produktion (VPS) | `ff5f5a0` live seit 25.10.2026 16:28 CET (No-Backup-Fast-forward von `5f467d3`, Beleg `output/release-20261025-5/deploy-01.log` ausserhalb Git); Shadow mit Trefferquote nach Tracker-Code, Hybrid-Warm-up vor der Bewertung, Protokoll der veröffentlichten Tipps und HAC-Intervallen; App-Lader hält Preisabweichungen je Zeile zurück, 15K-Snapshot mit Zeilen-Uhr, Preisregel 1,20 nur im Hintergrund, öffentliche Tipps rücken nach jedem Quotenlauf nach, unbepreiste Tipps bleiben öffentlich, Hauptauswahl je Spiel nach Modellwahrscheinlichkeit, Freigabe ohne Aufstellungspflicht, Pro-Tarif, Shadow-Kohorten mit Policy v6 |
| `origin/main` | Stand nach Merge von PR #34 (dreistufige Preisprüfung) am 25.10.2026, **noch nicht ausgerollt** (Übergabe in `TODO_AKTUELL.md`, Helfer `output/release-20261025-6/deploy.sh`); enthält PR #33 (Protokoll), #32 (Massnahme 2), PR #31 (Protokoll), #30 (Massnahme 1), PR #29 (Gesamtaudit), #28 (Protokoll), #27 (Lader-Preis-Uhr), PR #26 (Protokoll), #25 (Nachrücken), PR #24 (Protokoll), #23 (E-Sport-Preisstatus), PR #22 (Protokoll), #21 (keine 1,20-Hinweise), PR #20 (Protokoll), #19 (Hauptauswahl, Karte), #18 (Protokoll), #17 (App-Lader), PR #12 (Zähler-Fix), #14 (Preisregel 1,20), #15 (Freigabekontext), #16 (Protokoll), PR #10 (Frischeregel 3 h, Policy v6), PR #7 (`fd45176`, live), #8/#9 (Doku), enthält PR #1 (`62e6e73`), #2 (`24837c3`), #3 (`08b7473`), #4 (`9b0382f`), #5 (`be6258c`, Hybrid-Aktivierung vorbereitet), #6 (`a6661a6`, Edge-Cap-Protokoll); Quick-CI grün |
| Offene Claude-Branches | keine |
| Codex-Worktree | `.worktrees/audit-repairs-20261013`, 7 unveröffentlichte Commits, 18 ungesicherte Änderungen; muss `main` einmergen (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Hauptcheckout `betboy-app` | veraltet, fremdes WIP; nicht benutzen |

## Erledigt auf dem Audit-Branch

- Daily3: Mindestquote je Auswahl, Vormerkung nur ab Mindestquote (aktiv; `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab).
- Karte: Mindestquote und Preisstatus auf erster Ebene.
- Rechtsfooter mit 18+ und Spielsucht-Hilfe; Rechtslinks aus Env, sonst Platzhalter.
- Kundenzugang fail-closed, sobald `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- Marktbenchmark, Mischungsgewicht, optionales Markt-Gate (aus), Dixon-Coles mit Varianten (Opt-in), FDR über Ligen (an), Tennis-Populationsfit (Option), CI, Lockfiles.
- Shadow-Pfad: zweite Kohorte mit dem Hybrid (`BETBOY_SHADOW_HYBRID_BASIS`, an) und Edge-Cap-Protokoll je Tipp (`shadow_edge_cap`, 8 pp, nie angewendet); seit 25.10. Trefferquoten nach Tracker-Code, HAC-Intervalle und Protokoll der veröffentlichten Tipps (`shadow_published`).

## Kernbefunde

- 0 von 112 Liga×Markt-Zellen schlagen den No-Vig-Closing-Markt; Preispolicy-Replay ROI −5,5 %.
- Mischungsgewicht Modell/Markt out-of-sample 0,00.
- Kohärenter Hybrid `dixon_coles_hl365_hybrid` (eine Matrix: DC-Struktur, Legacy-Torsumme) ist das beste Modell: 148 Zellen signifikant besser als Legacy, 111 schlechter; im Release-Gate 262 statt 224 glaubwürdige Zellen, kein Markt verliert. Venue-spezifisches DC (H4) widerlegt; kein Modell schlägt den Markt.
- Marktwahrscheinlichkeit (No-Vig, Shin/Power) liegt jetzt aus den gespeicherten Buchmacher-Partitionen vor; die Edge-Kappung (Default aus) nutzt sie.
- **Preisregel seit 23.10.2026 (Owner):** Tipps erscheinen nach Modell- und Kontextgates; Buchmacherquoten sind kein Gate mehr und werden nicht gezeigt, nur die 1,20-Grenze sperrt im Hintergrund (`BETBOY_PRICE_POLICY`, Default `floor`; `docs/audits/2026-10-23-preisregel-1-20.md`). Grund: seit 10.10. null öffentliche Tipps, weil die 45-Minuten-Frische nie erreichbar war. Dazu zwei weitere Sperren behoben: Freigabekontext braucht keine bestätigten Aufstellungen mehr (Scan läuft Stunden vor Anpfiff), und die Hypothesenfamilie darf ein Vielfaches von 96 sein (FDR über Ligen; die starre 96 hatte seit 20.10. jede Freigabe blockiert). Der App-Lader akzeptiert seit PR #17 unbepreiste öffentliche Tipps; vorher verwarf er das ganze Dokument und die Website blieb leer.
- **Hauptauswahl seit 23.10.2026 abends (Owner):** je Spiel führt die Auswahl mit der höchsten Modellwahrscheinlichkeit (gleiche Teilnehmer und Modellrevision), nicht mehr der statistische Lead des Produzenten; weder Karte noch Eingabemasken (Daily3-Vormerkung, Manuelle Suche, Tennis, Meine Tipps) nennen eine Mindestquote, Tennis-Tab und Multi-Sport-Suche zeigen keine Buchmacherquote mehr; die 1,20-Grenze wirkt nur im Hintergrund und begründet nur Ablehnungen (`docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md`).
- **E-Sport-Preisstatus (25.10.2026):** Die E-Sport-Quotenanbindung speicherte den alten Code `OBSERVED`, der App-Lader verwarf deshalb am 25.10. ab 06:15 das ganze Tagesdokument (Website leer). Seit PR #23 folgt der gespeicherte Status der aktiven Preisregel (mit Ausführungsfeldern bei `PLAYABLE`), und der Lader akzeptiert Altzeilen mit `OBSERVED` ohne Ausführungsfelder (`docs/audits/2026-10-23-preisregel-1-20.md`, Nachtrag).
- **Nachrücken seit 25.10.2026 (Owner):** Jeder Quotenlauf besetzt die bis zu drei öffentlichen Tipps und die 15K-Liste nach der Auswahlregel des Nachtscans neu (`wettfinder_automation._republish_floor_candidates`); vorher leerte er beide Listen bis zum nächsten Scan. Unbepreiste veröffentlichte Zeilen werden zu öffentlichen Tipps, die Tipps leben so lange wie das Modelldokument (statt 150 Minuten), und die Karte blendet nur noch Prognosen mit Marktquote unter 1,20 aus statt jede ohne Quote (`docs/audits/2026-10-25-tipp-nachruecken.md`).
- **Massnahme 1 des Gesamtaudits (25.10.2026):** Der App-Lader hält Preis- oder Statusabweichungen je Zeile zurück (Zähler `price_inconsistent_rows`) statt das ganze Dokument zu verwerfen; Struktur- und Identitätsfehler bleiben fail-closed. Behaltene Quoten im Quotenlauf werden unter `floor` klassifiziert, der 15K-Snapshot bewertet jede Zeile mit ihrer Preis-Uhr und dem Floor-Status (vorher strukturell leer), das Nachrücken prüft denselben Fehlerzähler wie der Lader, Budgetmeldungen sind keine Betriebsfehler (`docs/audits/2026-10-25-lader-je-zeile.md`). Übrige Audit-Massnahmen: `AUDIT_BERICHT_2026-10-25_CLAUDE.md` §5.
- **Massnahme 2 des Gesamtaudits (25.10.2026):** Der Shadow misst wieder: Trefferquoten vergleichen den Tracker-Code `Won` (vorher `WIN`, immer 0), das Hybrid-Warm-up läuft vor der Bewertung (früheste Anpfiffe zuerst) und fehlende Artefakte lassen ein Spiel bis zum letzten Versuch offen statt es abzuhaken (seit 22.10. `artifacts_warmed: 0`); fehlgeschlagene Bauten sind je Tag markiert. Neue Tabelle `shadow_published` protokolliert je Lauf exakt die veröffentlichten Tipps und die 15K-Liste (Preisstatus, Öffnungsquote bei `PLAYABLE`) und rechnet Tormärkte aus dem Endstand ab; Edge-Cap-Gruppen und die paarweise Hybrid-Differenz tragen HAC-Intervalle (`docs/audits/2026-10-25-shadow-massnahme-2.md`). Offen aus S5: No-Vig-CLV.
- **Dreistufige Preisprüfung seit 25.10.2026 abends (Owner):** Die 1,20-Grenze prüft den mittleren statt den besten Buchmacherpreis; Tor-Bereiche ohne direkte Quote werden über die Über/Unter-Linien desselben Spiels bewertet (`reference_price_bound`, Marge 6 %); ohne jeden Preisbeleg wird eine Auswahl ab 65 % Modellwahrscheinlichkeit zurückgehalten. Anlass: Hauptauswahlen wie „Hammarby 1–4 Tore“ (Buchmacher 1,15) und „Ajax über 2,5 Ecken“ ohne geprüfte Quote; am 25.10. waren 16 von 46 Hauptauswahlen ungeprüft (`docs/audits/2026-10-25-preispruefung-dreistufig.md`).
- Hybrid-Aktivierung vorbereitet: eigene Prediction-Version und Vertragssignatur, ORIGINAL-Erfassung und Replay für die Hybrid-Basis, Shadow-Kohorte neben Legacy (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`). Produktionsbasis bleibt Legacy.
- **Shadow sammelt keine Evidenz** (`docs/audits/2026-10-22-shadow-befund.md`): API-Football-Limit seit 19.10. bei 100 Aufrufen je Tag (vorher 7 500), dadurch keine Spielpläne ab 21.10.; die Zehn-Minuten-Frischeregel der Öffnungsquote hatte seit Anfang Oktober jede Protokollierung blockiert (2 Tipps seit 1.9.). Owner-Entscheidung 23.10.: Öffnungsquote bis drei Stunden Provider-Alter, Alter je Tipp im Ledger, Policy `shadow-model-first-v6` (`docs/audits/2026-10-23-oeffnungsquote-frischeregel.md`). Das API-Kontingent ist seit 23.10. wieder Pro (7 500/Tag); der lokale Zähler übernimmt ein höheres Providerlimit seit demselben Tag sofort (`api_budget`, `scripts/api_budget_resync.py`).

## Offen

| Wer | Was |
|---|---|
| Nächste Session | PR #34 (dreistufige Preisprüfung) mit Owner-Freigabe ausrollen: Helfer `output/release-20261025-6/deploy.sh` (ausserhalb Git, `ff5f5a0` → `a2864ac`), danach Website und nächsten Quotenlauf prüfen (Schritte in `TODO_AKTUELL.md`, 25.10. abends) |
| Owner | Wirkung der dreistufigen Preisprüfung beobachten (Hauptauswahlen ohne Quote, Anteil zurückgehaltener Bereiche); offen bleibt, dass die 1,20-Grenze Auswahlen knapp darüber zulässt (25.10.: 14 von 46 Hauptauswahlen mit 80 % oder mehr) |
| Owner | Impressum/Datenschutz/AGB ausfüllen, prüfen lassen, URLs setzen |
| Codex | Branch integrieren, Konflikte lösen, Prüfbefehle, Release vorbereiten (`docs/handoffs/2026-10-21-codex-auftrag.md`) |
| Codex | Linux-Vollnachweis über die VPS-QA-Launcher (Gruppen A/B); der 7-GB-GitHub-Runner trägt die Suite auch halbiert nicht (Exit 137), zusätzlich 21 runner-spezifische Fehlschläge in `test_native_context_*` |
| Owner | Shadow-Artefakt `hybrid_cohort` beobachten (`paired.difference.lower_bound`, `artifacts_warmed`, `leagues_pending`); Aktivierung erst nach dem Prüfplan (300 Paare, untere HAC-Grenze der CLV-Differenz über 0) |
| Owner | Edge-Cap: Shadow protokolliert seit 22.10. je Tipp bestanden/nicht bestanden (`edge_cap` im Run-Artefakt, seit 25.10. mit `passed_clv`/`failed_clv`); Entscheidung nach 300 abgerechneten Tipps je Gruppe (`docs/superpowers/plans/2026-10-21-edge-cap.md`) |
| Owner | `published_tips` im Shadow-Artefakt beobachten (veröffentlichte Tipps und 15K-Liste, Anteil mit Quote, Trefferquote der Tormärkte); Tabelle `shadow_published` füllt sich ab dem ersten Lauf nach Release von Massnahme 2 |

## Wo nachlesen

`AUDIT_BERICHT_2026-10-25_CLAUDE.md` (Gesamtaudit 25.10.: Logik, Mathematik, Statistik, Betrieb, UX; Massnahmenplan),
`AUDIT_BERICHT_2026-10-16_CLAUDE.md` (Befund 16.10.), `docs/audits/2026-10-19-audit-reparaturen.md`
(Protokoll mit Zahlen), `docs/handoffs/2026-10-20-claude-uebergabe.md` (Code-Übergabe),
`docs/audits/2026-10-17-claude-gegenpruefung.md` (Nutzerentscheidungen 17.10.).
