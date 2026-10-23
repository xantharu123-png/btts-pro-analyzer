# AGENTS.md – Arbeitsregeln und aktueller Stand für Codex und Claude

Stand: 21.10.2026. Dieser Einstieg ergänzt `STATUS.md` (aktueller Stand auf einer Seite),
`ARCHITECTURE.md` (Datenfluss, Persistenz, Betrieb) und `PROJEKTBIBEL.md` (Produktgesetze). Bei Widersprüchen gilt zuerst der
Code, dann `PROJECT_HANDBUCH.md`, dann die Bibel. Historische Logs: `TODO_AKTUELL.md`,
`PC_WECHSEL_UEBERGABE.md` (append-only, oberster Block ist der aktuelle).

## Nicht verhandelbar

- **Modell vor Preis.** Keine Quote fließt in eine Modellschätzung. Quoten dürfen
  Benchmark, Validierung, Mindestquote, EV und Einsatz bestimmen, nie Modell-p oder
  Reihenfolge. Validierung gegen den Markt ist ausdrücklich erlaubt (Bibel §3.1).
- **Fail-closed.** Fehlende Pflichtdaten sperren den Kandidaten; nichts wird geschätzt
  oder still ersetzt. Ein neuer Modellpfad fällt nie auf den alten zurück.
- **Kein Schwellen-Tuning auf das gewünschte Ergebnis** (Bibel §3.5). Gates nur mit
  vorab definierter Hypothese und zeitlich getrennter Prüfung ändern.
- **Keine Garantieversprechen** in UI-Texten, keine erfundenen Bilanzen.
- **Secrets nur per Umgebung** (`config_loader.py`); nie Schlüsselwerte in Chat,
  Doku, Tests oder Git. Die im Januar 2026 committeten Schlüssel wurden am
  17.10.2026 ersetzt (`docs/audits/2026-10-17-claude-gegenpruefung.md`); der
  Widerruf der alten Werte beim Anbieter ist nicht bewiesen. Der veraltete
  Hauptcheckout trägt noch die alten Werte in `config.ini`.
- **Nutzerentscheidungen vom 17.10.2026 gelten** (Gegenabgleich, Abschnitt
  „Abgleich Audit 16.10.2026“): keine neuen Backups, obere Hauptnavigation,
  Einstellungen nicht in der Kundennavigation, keine Badge-Wand auf der Karte.
  Die Regel „Daily3 ohne Echtgeld-Preisfreigabe“ hat der Owner am 20.10.2026
  aufgehoben: das Vormerk-Gate ist aktiv. Mindestquote und Preisstatus auf der
  Karte sind am 20.10.2026 ausdrücklich bestätigt. Audit-Empfehlungen, die einer
  Nutzerentscheidung widersprechen, werden als abschaltbare Option umgesetzt
  und dem Owner vorgelegt. Am 23.10.2026 hat der Owner die Frischeregel der
  Öffnungsquote im CLV-Ledger von zehn Minuten auf drei Stunden Provider-Alter
  gelockert (Alter je Tipp gespeichert, Policy `shadow-model-first-v6`;
  `docs/audits/2026-10-23-oeffnungsquote-frischeregel.md`). Ebenfalls am
  23.10.2026: Buchmacherquoten sind kein Freigabegate mehr und werden in der
  App nicht gezeigt; die einzige Preisregel ist die 1,20-Grenze im Hintergrund
  (`BETBOY_PRICE_POLICY`, Default `floor`, `gate` = alter Vertrag;
  `docs/audits/2026-10-23-preisregel-1-20.md`). Diese Regel gilt für
  Wettfinder, Daily3 und RisikoBet; sie darf nicht eigenmächtig zurückgedreht
  werden. Am Abend des 23.10.2026 dazu: Die Hauptauswahl je Spiel ist die
  Auswahl mit der höchsten Modellwahrscheinlichkeit (gleiche Revision), und die
  Karte nennt keine Mindestquote (`docs/audits/2026-10-23-hauptauswahl-wahrscheinlichkeit.md`).
- **Keine Backups, Produktions-DB-Kopien oder API-Scans** ohne ausdrücklichen Auftrag.
- **Checkout-Disziplin.** Hauptcheckout `betboy-app` trägt fremdes WIP und liegt hinter
  `origin/main`; eigene Arbeit in einem eigenen Worktree unter `.worktrees/` auf einem
  eigenen Branch. Nie `git stash` ohne Tag, nie fremde Worktrees anfassen.

## Lokal arbeiten

```powershell
# aus dem jeweiligen Checkout (Worktree oder Hauptcheckout)
..\..\.venv\Scripts\python.exe -m pytest tests -q          # Vollsuite ≈ 1,5 h auf Windows
..\..\.venv\Scripts\python.exe -m pytest tests/test_daily3_ui.py -q   # gezielt
```

Die venv liegt im Hauptcheckout (`betboy-app/.venv`, Python 3.12). 97/98 Tests sind
Linux-only-Skips (`fcntl`); Produktions-QA läuft auf dem VPS. `tests/conftest.py`
importiert Root-Module, deshalb immer `python -m pytest` aus dem Checkout-Root.

## Audit 16.10.2026 und Reparaturen 19.10.2026

Vollständiger Befund: `AUDIT_BERICHT_2026-10-16_CLAUDE.md`. Reparaturprotokoll:
`docs/audits/2026-10-19-audit-reparaturen.md`. Code-Übergabe (Commits, Dateien, Schalter,
Befehle, Risiken): `docs/handoffs/2026-10-20-claude-uebergabe.md`. Branch
`claude/audit-repairs-20261019`, Worktree `.worktrees/claude-audit-repairs-20261019`,
Basis `origin/main` @ `be5e441`, PR #1.

Umgesetzt auf diesem Branch (Default-Verhalten der Produktion unverändert):

| Thema | Dateien | Vertrag |
|---|---|---|
| Daily3: rechnerische Mindestquote (max(1,20; Risiko-Minimum)) und beobachtetes Angebot je Auswahl sichtbar; Echtgeld-Vormerkung nur ab dieser Mindestquote, **standardmässig aktiv** (Owner-Entscheidung 20.10.2026, ersetzt die Regel vom 17.10.); `BETBOY_DAILY3_RESERVATION_MINIMUM=0` schaltet ab | `daily3_selection.py` (`Daily3Choice.minimum_odds/offer_odds/price_blocked`, `reservation_minimum_enforced`), `daily3_ui.py` (`_require_reservation_price`) | Auswahl bleibt preisblind (Tests sichern das); Gate greift nur beim Geld |
| Karte zeigt Mindestquote und Preisstatus auf erster Ebene (Wettfinder, Daily3, 15K) | `wettfinder_surface.render_editorial_card_html`, `editorial_theme.py` | `.se-number-threshold`, `.se-price-status` |
| Shin- und Power-De-Vig neben proportional | `betting_math.no_vig_market(odds, method)` | nur Benchmark, nie Modellinput |
| Marktbenchmark Modell vs. No-Vig-Closing (Pinnacle, Shin/Power), HAC, BH über Ligen×Märkte, Replay der Preisgate-Policy mit Bootstrap-ROI/CLV | `market_benchmark.py`, `market_benchmark_history.py`, `scripts/download_market_benchmark_data.py`, `scripts/market_benchmark_report.py` | Preise getrennt nach Fixture-ID gejoint; Modell-Loader bleibt quotenblind |
| Dixon-Coles-MLE (Angriff/Abwehr multiplikativ, Heimvorteil, ρ, Zeitdecay) als Opt-in, Varianten `GOAL_MODEL_OPTIONS` (Halbwertszeit 120/240/365 Tage, Niveau-Prior = ungewichtetes Fenstermittel; Plan 2026-10-20 H1/H2), Hybrid H3 nur im Vergleichsskript | `football_dixon_coles.py`; `challenge_engine.score_matrix(rho=)`, `goal_model=` in `_fixture_model`, `fixture_market_probabilities`, `_walk_forward_market_records`; `scripts/compare_goal_models.py --variant` | Default `GOAL_MODEL_LEGACY` byteidentisch (Golden-Tests grün); DC fällt nie zurück, kein ORIGINAL-Capture; ρ wird je Spiel in den gültigen Bereich projiziert |
| Markt-Freigabebedingung (Audit K2): Kandidat erhält Sperrgrund, wenn seine Liga×Markt-Zelle den No-Vig-Closing-Markt nicht geschlagen hat; **Default aus** (`BETBOY_RELEASE_MARKET_BENCHMARK=1`), Verdikte aus `scripts/market_benchmark_report.py --gate-json` | `market_release_gate.py`; Einbau in `challenge_engine.build_fixture_candidates` | fail-closed bei fehlendem/veraltetem Verdikt (120 Tage); Stand 19.10.: 0/112 Zellen bestanden, Aktivieren leert jeden Echtgeldpfad |
| Entscheidungs-p als Log-Odds-Mischung Modell/Markt, Gewicht out-of-sample, Edge-Cap-Replay (Audit K3) | `betting_math.blended_decision_probability`, `market_blend.py`, `scripts/estimate_market_blend.py` | Analyse; gespeicherte Modell-p unverändert; Produktion bräuchte den vollständigen No-Vig-Markt aller Seiten |

Benchmark-Daten: `scripts/download_market_benchmark_data.py` legt football-data-CSVs
unter `runtime_state/market_benchmark/` ab (ignoriert). Berichte:
`docs/audits/2026-10-19-marktbenchmark.md`, `docs/audits/2026-10-19-dixon-coles-vergleich.md`.

## Offen (Reihenfolge aus dem Audit)

1. Owner-Entscheidungen vom 20.10.2026 zu diesem Branch: Daily3-Gate aktiv, Karte
   mit Mindestquote und Preisstatus bleibt. Backup-Timer bleibt auf
   Nutzerwunsch deaktiviert; das Wiederherstellungsrisiko ist real. Widerruf der
   alten API-Schlüssel beim Anbieter bestätigen.
2. Impressum, Datenschutz, 18+, Spielsucht-Hinweis in der App; Kundenzugang vor einem
   bezahlten Start auf fail-closed umstellen (mit Migration, sonst sperrt es den Owner aus).
3. Release-Gate: Marktbenchmark als zusätzliche Bedingung in `_credible_validation`
   (HAC-Untergrenze gegen den Markt > 0), erst nach Lektüre des Benchmark-Berichts.
4. Entscheidungs-p als Log-Odds-Mischung mit dem Markt plus Edge-Cap statt festem
   Prozentpunkt-Haircut (Audit K3/H2); Haircut aus Schätzunsicherheit.
5. Dixon-Coles: H1 (Halbwertszeit 240/365 d) bestätigt, H2 (Niveau-Prior) widerlegt,
   H4 (venue-spezifisch) widerlegt. Der **kohärente Hybrid** `dixon_coles_hl365_hybrid`
   (eine Matrix: DC-Struktur je Torsumme, Legacy-Torsummenverteilung; `reweight_totals`,
   `goal_matrix_override`) ist die beste Konfiguration: 148 Zellen signifikant besser als
   Legacy, 111 schlechter (von 560); Berichte `docs/audits/2026-10-2[01]-dixon-coles-*.md`.
   Release-Gate-Validierung (`docs/audits/2026-10-22-hybrid-validierung.md`): 262 statt
   224 glaubwürdige und 257 statt 224 freigegebene Zellen, kein Markt verliert. Seit
   22.10.2026 vorbereitet (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`):
   eigene Pins (`prediction_version_for_goal_model`), ORIGINAL-Erfassung/Replay für die
   Hybrid-Basis, Shadow-Kohorte neben Legacy (`BETBOY_SHADOW_HYBRID_BASIS`, Default an).
   Produktionsbasis bleibt Legacy; Umstellung nur nach dem Prüfplan und als eigener
   Owner-Commit.
   Mischungsgewicht Modell/Markt ist out-of-sample 0,00 (`2026-10-20-marktmischung.md`):
   Entscheidungen sollten dem Markt folgen; der Edge-Cap 8 pp hebt die Policy von −5,5 %
   auf +0,8 % ROI (Intervall enthält 0).
6. Tennis: Kalibrierung auf der gewetteten Population, `market_model_version` v2 als
   Default, Belagsregel durch vorregistrierte Ablation ersetzen.
7. Hauptkarte/UX: Sportarten ohne Evidenzfreigabe aus der Standardansicht, Aussenseiter
   marktdefiniert, ein Token-Set, eine Währung, ein Formatter. Obere Navigation und
   Daily3-Marke sind Nutzerentscheidungen, keine Schuld.
8. Repo: `main` synchronisieren, Worktrees und QA-Artefakte aufräumen, CI mit ruff/pytest
   auf Linux, Lockfile; Domänenpaket ohne Importzyklen.

## Konventionen für Änderungen

- **Jede Session beginnt mit `STATUS.md` und endet mit `STATUS.md`:** zu Beginn lesen, am
  Ende den Abschnitt „Stand“ ersetzen (Datum, Branch/PR, Erledigtes, Offenes nach
  Zuständigkeit); nicht anhängen, Historie gehört in `TODO_AKTUELL.md`.
- Jede Verhaltensänderung zuerst als roter Test, dann grün; Fixtures nicht lockern.
- Keine neuen Felder in persistierten Snapshots ohne Schema-/Validierungsänderung
  (`daily3_store._snapshot`, ORIGINAL-Capture, HMAC-Ledger).
- Neue Module dürfen `challenge_engine` nicht top-level importieren, wenn der Engine sie
  importiert (Zyklen); Funktionsimporte sind der bestehende Ausweg.
- Berichte nach `docs/audits/<datum>-<thema>.md`; Zahlen immer mit n, Intervall und
  Stichprobenherkunft; Softwaretests sind kein Beleg für Wettvorteil.
