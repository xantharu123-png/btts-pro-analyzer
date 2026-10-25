# BetBoy – Gesamtaudit 25. Oktober 2026 (Claude Fable 5.1)

Perspektiven: Logik/Korrektheit, Mathematik, Statistik, Engineering/Betrieb, UX.
Geprüft: `origin/main` @ `8e4d06f` (Worktree `.worktrees/claude-audit-repairs-20261019`), Produktion
`https://vps-a30a123f.vps.ovh.net/` (Stand `8e4d06f` seit 12:02 CET) und das Serverjournal des 24./25.10.
Methode: fünf parallele Tiefenprüfungen des Codes mit Offline-Nachrechnungen und gezielten Testläufen
(252 Mathematik-, 93 Statistik-, 72 Betriebs-, 20 Preisregel-Tests grün; `ruff check .` 0 Befunde),
eigene Verifikation jeder kritischen Aussage im Code, Live-Stichprobe aller sieben Seiten, Lesen des
Serverzustands. Das Audit selbst hat nichts geändert; zwei im Verlauf entdeckte Produktionsausfälle
wurden mit Owner-Freigabe sofort behoben (PR #23, PR #27) und sind unten als Befunde aufgeführt.
Zeilenangaben beziehen sich auf `origin/main` @ `8e4d06f`. Vorheriges Audit: `AUDIT_BERICHT_2026-10-16_CLAUDE.md`.

---

## 0. Kurzurteil

**Logik:** Die Veröffentlichungskette Scan → Quotenlauf → Dokument → App-Lader ist seit der
Preisregel vom 23.10. an mehreren Stellen inkonsistent, weil der Lader jede Abweichung einer
einzelnen Zeile mit dem Verwerfen des ganzen Tagesdokuments beantwortet. Am 25.10. war die
Website deshalb zweimal leer (06:15–07:28 und 09:15–12:02 CET); beide Ursachen sind behoben,
zwei weitere Auslöser derselben Art stehen noch im Code (UNAVAILABLE mit behaltener Quote;
Zähler, den der Lader prüft, das Nachrücken aber nicht). Die 15K-Seite kann unter der
Preisregel strukturell nie etwas zeigen, die Daily3-Schiene bleibt faktisch preisgegated.

**Mathematik:** Rechnerisch sauber (Kelly, No-Vig, Dixon-Coles-MLE, Normierungen, Walk-forward
ohne Leckage). Strukturell gilt weiter: additives Legacy-Tormodell in Produktion, Haircut als
gesetzte Zahl statt Intervall. Neu: Unter der Preisregel `floor` ist die gesamte EV-/Kelly-/Edge-
Cap-Mathematik inert; die Joint-Kalibrierung setzt ihre Kurven nur zu 10–70 % um; der Hybrid nutzt
ρ ausserhalb seines Schätzmodells und bekommt wegen Spread 0 strukturell den kleinsten Haircut.

**Statistik:** `RELEASED` beweist weiterhin „besser als die Ligahäufigkeit“, nicht „besser als der
Markt“; seit dem 23.10. erscheinen diese Tipps ohne jede Preisprüfung mit dem Label „Modell
geprüft“. Der Shadow-Pfad, der die Entscheidung über Hybrid und Edge-Cap tragen soll, misst eine
andere Population als veröffentlicht wird, hat eine Trefferquote, die wegen `WIN` ≠ `Won` immer 0
ist, und wärmt den Hybrid aus einem Reihenfolgefehler nie.

**Engineering/Betrieb:** Secrets, Locks, atomare Schreibvorgänge und Ledger-Integrität sind gut.
Kein Backup bei 8 GB Laufzeitdaten (Owner-Entscheid), kein Alarmempfänger, Tagesjobs ohne
Nachholung, Quotendienst mit bedeutungslosem Exit 1, Tennis-Tagesscan seit 22.10. tot, der
Produktionspfad `floor` wird von 20 von 6 629 Tests geprüft.

**UX:** Deutlich besser als am 16.10. (Rechtsfooter mit 18+ und Spielsucht-Hilfe, keine Quoten,
ehrliche Sprache, saubere Formularkontrakte). Offen: Evidenzstufe für den Nutzer unsichtbar,
Manuelle Suche zeigt weiter Quoten, Zeitzonenfehler in der Multi-Sport-Suche, Zahlenformate und
Währung gemischt, erste Karte des Tages wieder E-Sport.

**Gesamtnote:** Integrität überdurchschnittlich, Betrieb fragil, Wettvorteil unbewiesen, Produkt
nahe an „benutzbar“, aber mit drei Seiten (15K, Daily3, Tennis), die heute nichts liefern.

---

## 1. Stand gegenüber dem Audit vom 16.10.2026

| Befund 16.10. | Status 25.10. | Beleg |
|---|---|---|
| K1 Schlüssel in öffentlicher Historie | teilweise: ersetzt 17.10., Widerruf alter Werte unbewiesen | `AGENTS.md` „Nicht verhandelbar“ |
| K2 Release-Gate gegen Basisrate | **unverändert, verschärft** (Tipps ohne Preisprüfung öffentlich) | `challenge_engine.py:2553`, `market_release_gate.py:35` |
| K3 Haircut/Preisgate = Winner's Curse | unverändert; unter `floor` inert (Edge-Cap wird nie erreicht) | `market_consensus.py:668, 930` |
| K4 Daily3 ohne EV-Gate | teilweise: Vormerk-Gate 1,20 aktiv; Pool bleibt SHADOW, EV am Boden −16 % | `daily3_selection.py:35, 58-67, 158-161` |
| K5 15K-Kandidat mit negativem EV | offen; 15K-Snapshot unter `floor` strukturell `None` | `wettfinder_automation.py:2299-2311` |
| K6 Backup inaktiv | unverändert (Owner-Entscheid), Doku widersprüchlich | `deploy/README.md:16, 19-20` |
| H1 Legacy-Tormodell | teilweise: Hybrid als Shadow vorbereitet, Produktion Legacy | `challenge_engine.py:1362`, `shadow_clv_automation.py:103` |
| H2 Haircut kein Intervall | unverändert | `challenge_engine.py:2920-2927` |
| H3/H4 Tennis Kalibrierung, Tiebreak | unverändert (Produktion v2, Code-Default hold-proxy) | `tennis/model_state.py:74`, `tennis/simulator.py:120` |
| H5 CLV misst das Falsche | unverändert, Frischeregel 3 h ergänzt | `clv_tracker.py:731, 755` |
| H6 Keine Rendite-Stichprobe | unverändert: Shadow seit 23.10. 0 Tipps | Serverjournal 25.10. |
| H7 Hauptcheckout veraltet | teilweise: `main` aktuell, Hauptcheckout/Codex-Worktree weiter abweichend | `STATUS.md` |
| H8 Keine CI/Linter/Lockfile | teilweise: ruff + 3 Testdateien in CI, Lockfile ohne Verbraucher | `.github/workflows/tests.yml:40` |
| H9 Importzyklen, God-Functions | unverändert | 44/32/16/14 Funktionsimporte |
| H10 Karte ohne Mindestquote/Preisstatus | durch Owner-Entscheid 23.10. anders gelöst (kein Preis in der App) | `docs/audits/2026-10-23-preisregel-1-20.md` |
| H11 Pflichthinweise | teilweise: 18+/Spielsucht-Footer da, Impressum/Datenschutz Platzhalter | `legal_notice.py:24` |
| H12 Erste Karte E-Sport-Münzwurf | unverändert (25.10. 12:05: Karte 1 „CS2 FUT Esports vs Liquid“) | Live-Stichprobe |
| H13 Währungsmix, Design-Systeme | teilweise: 15K weiter in Euro | `challenge_15k.py:727-729` |
| H14 Kundenzugang opt-in | unverändert (fail-closed nur mit Token, Token nicht gesetzt) | `customer_access.py` |

---

## 2. Produktionsstichprobe 25.10.2026

| Zeit (CET) | Beobachtung | Bewertung |
|---|---|---|
| 03:35–03:59 | Tagesscan `completed`: 107 Spiele, 84 modelliert, 690 zugelassene Kandidaten, 373 Modellzeilen, 3 öffentliche Tipps, 15K-Liste leer | in Ordnung |
| 06:15 | Quotenlauf hängt erstmals E-Sport-Quoten an → Statuscode `OBSERVED` → Lader verwirft das Dokument, **Website leer** bis 07:28 | K (behoben, PR #23) |
| 06:15 | Die 3 Tipps von 03:59 entfernt (unter 1,20), Quotenlauf leert `candidates` ohnehin vollständig | H (behoben, PR #25) |
| 08:05–08:09 | Nachrücken live; Website 60 statt 44 Spiele, weil Prognosen ohne Quote wieder sichtbar | in Ordnung |
| 09:15 | Nachrücken veröffentlicht 3 Tipps + 15 15K-Einträge; Lader bewertet sie mit der Scan-Uhr → **Website leer** bis 12:02 | K (behoben, PR #27) |
| 12:05 | Lader lädt (339 Prognosen, 3 Tipps); Website 52 Spiele | in Ordnung |
| ganztags | 15K-Seite „noch kein verwendbares 15K-Ergebnis“ trotz 15 Einträgen in der Liste | K (offen, Befund L1) |
| ganztags | Daily3 „Heute keine passende Daily3-Auswahl“, Tennis „keine Tennis-Auswahl“ | offen (L7, D3) |
| 00:11 | Tennis-Tagesscan `ValueError('live tennis per-case raw admission exceeded')` (seit 22.10.) | H (offen) |
| alle 3 h | Quotendienst jede zweite Ausführung Exit 1; 03:15/09:15-Muster „checked 0“ dazwischen | H (offen, D2) |
| alle 10 min | Shadow: 0 protokollierte Tipps seit 23.10.; Hybrid `artifacts_warmed: 0` | H (offen, S3/D4) |
| öffentliche Tipps | drei Auswärtssiege mit Modellwahrscheinlichkeit 19 %, 19 %, 50 % (Ledger-Reihenfolge = statistischer Rang) | Owner hat die Regel bestätigt |
| RisikoBet | Chornomorets vs Karpaty als „Premier League“ (ukrainische Liga), „Modell 27.7 %“ mit Punkt, Kurzcheck mit Komma | M (UX) |
| 15K | Guthaben „100,00 €“, Ziel „15.000,00 €“, Rest der App CHF | M (UX) |

---

## 3. Befunde nach Schwere

Kennzeichnung: L Logik, M Mathematik, S Statistik, D Engineering/Betrieb, U UX.

### KRITISCH

**L1 – 15K-Snapshot ist unter der Preisregel strukturell leer**
`wettfinder_automation.py:2299-2311` (`build_scheduled_challenge_snapshot`): jede Zeile der 15K-Liste
braucht `wettfinder_consensus(raw_quote, now=generated_at)` – Quotenpunkte höchstens 45 Minuten vor
der **Scan-Uhr** – sonst `return None` für den ganzen Snapshot. Nach dem Nachrücken (PR #25) sind
alle Quoten jünger als die Scan-Uhr; auch im Tagesscan behält `fetch_football_consensus` Stempel bis
24 h (`market_consensus.py:2743`), `floor_price_status` macht daraus `PLAYABLE`, der 45-Minuten-Konsens
aber `None`. Live-Beleg 25.10.: 15 Einträge in `challenge_release_candidates`, 15K-Seite „Der
Tageslauf hat für heute noch kein verwendbares 15K-Ergebnis erzeugt.“ (`challenge_15k.py:5668-5680`).
Fix: wie PR #27 je Zeile `reference_price_evaluated_at` als Uhr und unter `floor` den Floor-Status statt
der 45-Minuten-Frische prüfen; ungültige Zeile verwerfen, nicht den Snapshot.

**L2 – Zwei weitere Auslöser für ein leeres Tagesdokument stehen im Code**
(a) `wettfinder_automation.py:2628-2650`: eine im Quotenlauf geprüfte Zeile ohne neue passende Quote
behält die alte `reference_quote`, Status `UNAVAILABLE`, ohne `reference_price_evaluated_at`. Der Lader
(`ev_signal_sources.py:1258-1281`) rechnet nach und erhält unter `floor` nur
`PLAYABLE/UNPRICED/BELOW_FLOOR` → Abweichung → Dokument verworfen. Tritt ein, sobald ein Buchmacher
einen zuvor bepreisten Markt zurückzieht (vor Anpfiff üblich). (b) Der Scan zählt Quotenfehler in
`sources.football.operational_error_count` (`:4169`); das Nachrücken prüft nur
`football.operational_error_count` (`:4748-4754`); der Lader verwirft bei `sources[…] != 0`
(`ev_signal_sources.py:979, 992`). Szenario: Scan mit einem Fixture-Timeout → erster Quotenlauf
veröffentlicht 3 Tipps → Website leer bis zum nächsten Scan. Beide offline reproduziert.
Fix: (a) behaltene Quote mit `wettfinder_reference_price_status` und `reference_price_evaluated_at`
bewerten; (b) Nachrücken an `sources[source].operational_error_count == 0` binden. Grundsätzlich
(L8): Preis-/Statusabweichungen je Zeile verwerfen, nicht das Dokument.

**S1 – `RELEASED` ist eine Basisraten-, keine Marktaussage; seit 23.10. ohne Preisprüfung öffentlich**
`challenge_engine.py:2553` (Laplace-Basisrate), `:2451-2501` (Freigabe nur dagegen),
`market_release_gate.py:35` (Marktgate Default aus). Marktbenchmark: 0 von 112 Zellen schlagen den
Closing-Markt, Mischgewicht out-of-sample 0,00, Policy-Replay −5,5 % ROI. Simulation (n = 280,
kalibriertes Modell ohne Marktvorteil): das Gate besteht in 49 % bis 86 % der Läufe. Die
Hybrid-Validierung zeigt zudem, dass genau die 1X2/Doppelte-Chance-Märkte freigegeben werden, in
denen der Rückstand zum Markt am grössten ist. Seit dem 23.10. tragen diese Tipps das Label „Modell
geprüft“ (`wettfinder_surface.py:414-416`) ohne jede Preisprüfung. Empfehlung: Stufe ehrlich
benennen („gegen Basisrate geprüft“) oder Marktgate als Bedingung; Hinweis auf der Karte.

**M1 – Unter `floor` ist die EV-/Kelly-/Edge-Cap-Mathematik inert; Daily3 erlaubt Echtgeld mit EV −16 %**
`market_consensus.py:668` und `:930` springen bei `floor_only_pricing()` zu `floor_price_status`,
bevor `_edge_cap_status` (`:628`) erreicht wird. `daily3_selection.py:58-67` sperrt nur bei Angebot
< 1,20, `reservation_minimum_odds` (`:101-117`) ist konstant 1,20. Nachgerechnet: Daily3-Schwelle
p = 0,70 (`:35`) bei Angebot 1,20 → EV = 0,70 · 1,20 − 1 = −16 %, Kelly 0, Vormerkung erlaubt.
Dazu S4: der Daily3-Pool sind alle Modellzeilen (SHADOW), nicht die freigegebenen
(`ev_signal_sources.py:2041`, `daily3_selection.py:173`), entgegen Bibel §3.4. Empfehlung:
Edge-Cap/Blend vom Preisgate entkoppeln (Hintergrundvergleich Modell vs. No-Vig als Modellhinweis),
Risiko-EV am 1,20-Boden als Hinweis, Daily3-Pool auf freigegebene Zeilen, Schwelle 0,70 durch
EV-am-Boden-Regel ersetzen.

**D1 – Kein Backup bei 8 GB Laufzeitdaten und Geld-Ledgern (Owner-Entscheid, Risiko benannt)**
`context_models.db` 8,0 GB, `forecast_evidence.db` 460 MB, `riskobet.db` 400 MB, dazu 15K-Ledger,
Daily3-Konto und Shadow-DBs auf einer Platte ohne zweite Kopie. `deploy/README.md:16` („backup
timer remains disabled“) widerspricht `:19-20` („backed up transactionally every night“),
`PROJEKTBIBEL.md:574` zählt das Backup zu „exakt sieben Timern“. Eine Reaktivierung würde scheitern:
Stage in `/tmp/betboy-backup-stage` (`scripts/stage_runtime_databases.py:32`, `PrivateTmp`) und
`TimeoutStartSec=30min` sind für 8 GB nicht dimensioniert. Empfehlung: Anbieter-Snapshot (OVH) als
Entscheid dokumentieren; die kleinen Ledger-DBs getrennt sichern; README und Bibel korrigieren.

### HOCH

**S2 – Der Shadow-Pfad misst eine andere Population als veröffentlicht wird**
`shadow_clv_automation.py:1330` nimmt `candidate_is_forecast_credible` (ohne HAC/FDR), beschränkt
auf 18 Märkte (`:133`, keine Teamtore), wählt den höchsten `selection_rank` **mit** Bet365-Quote ≤ 3 h
(`:914-937`); Spiele ohne Quote fallen aus. Veröffentlicht werden freigegebene Zeilen in
Ledger-Reihenfolge, auch unbepreist, mit Lead nach höchster Wahrscheinlichkeit. Die 300-Paare-
Evidenz, falls sie je entsteht, belegt nicht die veröffentlichte Regel (Survivorship-Bias nach
Quotenverfügbarkeit). Empfehlung: zusätzlich exakt die veröffentlichten `candidate_id`s (auch
unbepreist, Opening NULL) protokollieren und die Quote „mit/ohne Preis“ ausweisen.

**S3 – Trefferquoten im Edge-Cap- und Hybrid-Paarprotokoll sind immer 0**
`shadow_clv_automation.py:897`, `:1462-1463` vergleichen `str(result).upper() == "WIN"`; der Tracker
speichert `'Won'/'Lost'/'Push'` (`clv_tracker.py:418, 461, 750`). Die Tests kodieren „WIN“
(`tests/test_shadow_edge_cap.py:139`) und verdecken den Fehler. Das vorregistrierte Kriterium
„Trefferquote gegen implizierte Wahrscheinlichkeit“ ist so nicht messbar. Fix: `== 'Won'`, Tests
korrigieren. Dazu S5: die Pläne verlangen HAC-Intervalle der CLV-Differenz; `_paired_cohort_statistics`
(`:1437-1477`), `_edge_cap_statistics` (`:868-912`) und `get_clv_statistics` (`clv_tracker.py:731, 755`)
liefern nur Mittelwerte, CLV bleibt Opening/Closing − 1 roh und verviggt.

**D4 – Hybrid-Shadow kann strukturell nie wärmen**
`_evaluate_hybrid_cohort` meldet bei fehlenden Artefakten `terminal: True`
(`shadow_clv_automation.py:1206-1215`); `step_evaluate` setzt `evaluated = 1`, sobald Legacy und
Hybrid terminal sind (`:1388-1407`); `step_warm_hybrid` läuft erst danach und nur über
`evaluated = 0`-Zeilen (`:1157-1172`). Jedes Spiel, das erstmals im Fenster vor Anpfiff geprüft wird,
ist für den Hybrid endgültig verloren, bevor seine Liga gebaut wurde; `artifacts_warmed: 0` seit dem
22.10. ist die Folge, nicht ein Budgetproblem. Fix: `hybrid_not_ready` nicht terminal, solange der
Anpfiff weiter als `EVAL_FINAL_RETRY_MINUTES` entfernt ist; Warm-up vor der Bewertung für Ligen mit
fälligen Spielen; `artifacts_cached`/`leagues_pending` ins Artefakt.

**D2 – Quotendienst: Exit 1 jeder zweiten Ausführung ist ein Zähl- und Klassifikationsfehler**
Timer alle 3 h, Sperre `SCHEDULED_PRICE_MIN_GAP = 3 h` (`wettfinder_automation.py:127`), Vergleich
`current - previous_attempt < 3 h` (`:4995`), Versuchsstempel aber erst **nach** dem Abruf
geschrieben (`:5003`). Der Abstand liegt systematisch knapp unter 3 h → jeder zweite Lauf `not_due`
(Journal 25.10.: 03:15 „checked 0“, 06:15 157 Zeilen, 09:15 „checked 0“ …), der fällige Lauf trifft
das OddsPapi-Tagesbudget (10 Aufrufe, Reserve 3, `oddspapi_client.py:27-28, 108-114`) und
Eishockey-Identitätsfehler (`team_sport_prices.py:347-361`) → `operational_errors ≥ 1` → Exit 1,
obwohl Fussballquoten fehlerfrei sind. Dazu L5: der Fussball-Quotenlauf zählt Budgetmeldungen als
Betriebsfehler (`:4928` `len(errors)` statt `_operational_quote_errors`) und schaltet damit das
Nachrücken ab. Fix: Startzeit als Versuchsstempel oder Toleranz; Budget als `budget_deferred`;
Identitätslücken als Datenstatus; Exit 1 nur für den Fussball-/Tennis-Kern.

**D3 – Tennis-Tagesscan seit 22.10. ohne Degradationspfad**
`context_models/tennis_live_source.py:97, 118-129`: ein Fall über 32 768 Rohzeilen, 32 MB oder 2 MB
je Chunk wirft `ValueError`; `scripts/tennis_daily.py:1180, 1221` reiht Prognosen ein und speichert
erst in `batch.finish()` ausserhalb jedes `try` → eine Partie verwirft den ganzen Tag, die Meldung
nennt weder Partie noch Zahlen. Journal: Fehlschläge 22., 24., 25.10., Erfolg nur am 23.10.
Fail-closed ist Vertrag; fehlend sind Ausschluss eines Falls mit Grundcode und Diagnose. Codex-Bereich.

**L3 – `usable_odds` ist unter `floor` der Bestpreis und wandert als ausführbarer Preis weiter**
`market_consensus.py:599-603`: `PLAYABLE` mit `best.odds` aus 24 Stunden. Konsumenten: 15K-Ticket
(`challenge_15k.py:4743`), persistierte `reference_quote_executable_odds`
(`wettfinder_automation.py:2542-2552`), CLV-Evidenz (`forecast_evidence.py:249`). Beispiel
2,00/2,02/2,04/2,06 → 2,06 statt Q25-Ausführungsangebot 2,02 (Bibel §2: Bestpreise nicht zur
Schönrechnung). Zudem `quote_low` (24 h) > `quote_high` (45-min-Teilmenge) → `challenge_engine.py:4525`
`ValueError`, in `challenge_15k.py:4945` nicht gefangen (Seitenfehler). Fix: Floor-Entscheid am
Bestpreis, Ausführungspreis aus `executable_point` der frischen Teilmenge.

**M2 – Joint-Kalibrierung setzt ihre Kurven nur zu 10–70 % um**
`football_joint_calibration.py:30` (Law v1), `:104-105`: Datenterm durch die Marktanzahl (≈ 40)
geteilt, Identitäts-Prior ungeteilt. Nachgerechnet (Poisson 1,5/1,2, Kurve −5 pp auf RESULT_HOME):
Ziel 0,3915, erreicht 0,4362 → 10,5 % der Verschiebung; kohärente 1X2-Verschiebung 33 %;
Über/Unter ±4 pp → 70 %. `_fit_calibration_map` (`challenge_engine.py:2342`) fittet stets auf
Rohwerten, der Rest wird nie nachkorrigiert. Empfehlung: `projection_target_diagnostics` (`:134`)
ausgeben, Residualfehler als Gate, oder Kurven auf den effektiven Werten fitten.

**M3 – Dixon-Coles-Kandidaten bekommen strukturell den kleinsten Haircut und den vollen Einigkeitsscore**
`challenge_engine.py:1421` setzt `active = season = form = dc_rate` → `spread_pp = 0` (`:2910`) →
`structural_haircut = 3 + 0` (`:2926`), `agreement_score` 20/20 (`:2936`), Block „Saison- und
Formmodell widersprechen sich“ (`:2959`) kann nie greifen. Die Hybrid-Validierung (257 statt 224
Zellen, `docs/audits/2026-10-22-hybrid-validierung.md`) ist dadurch teilweise Scoring-Artefakt.
Dazu M4: `reweight_totals` (`football_dixon_coles.py:392-417`) ersetzt die Gesamttorverteilung durch
Poisson, womit nur ≈ 25 % der ρ-Korrektur überleben (P(0:0) Poisson 0,0781, DC 0,0943, Hybrid 0,0781).
Empfehlung: echte DC-Unsicherheit (Hesse/Bootstrap) in Haircut und Score; ρ unter der Hybrid-
Likelihood schätzen oder den Hybrid ohne ρ-Anspruch deklarieren. **Vor der Hybrid-Aktivierung klären.**

**D5 – Produktionspfad `floor` ist schmal getestet; keine Alarmierung; Tagesjobs ohne Nachholung**
`tests/conftest.py:11-12` pinnt `gate` für alle Suiten ausser `price_floor`; 20 von 6 629 Tests prüfen
den Default. Beide Ausfälle vom 25.10. waren Floor-Regressionen. Keine Unit hat `OnFailure=`,
`betboy-wettfinder/tennis/esports/quotes` laufen mit `Persistent=false` (Downtime zur Laufzeit =
kein Lauf). Empfehlung: Fixture per Env parametrisieren und Lader-/Publikations-/Daily3-/15K-Suiten
in CI zusätzlich unter `floor`; `OnFailure=betboy-alert@%n` (Telegram-Token vorgesehen,
`config_loader.py:19-20`); `Persistent=true`.

**U1 – Evidenzstufe für den Nutzer nirgends erkennbar**
`wettfinder_surface.py:501` berechnet `evidence_label` („Modell geprüft“/„Evidenzprüfung“/
„Forschungsmodell“), `render_editorial_card_html` (`:988-1041`) rendert ihn nicht; der Kurzcheck-
Hinweis „Modell noch nicht unabhängig bestätigt“ (`forecast_analysis.py:575-576`) steht in
`_INTERNAL_NOTES` (`forecast_compact.py:45`) und wird herausgefiltert (`:243`). Eine E-Sport-
Forschungsprognose unter „Spiele“ sieht aus wie ein freigegebener Fussballtipp (Bibel §3.4); heute
war Karte 1 eine CS2-Partie. Empfehlung ohne Badge-Wand: eine Textzeile im Kurzcheck „Modellstatus:
geprüft / in Prüfung / Forschung“ oder Forschungsstufen in einen eigenen Abschnitt.

**U2 – Manuelle Suche zeigt weiter Buchmacherquoten und einen Quotenfilter**
`alternative_markets_tab_extended.py:955` `st.caption(f"Quote {quote_value:.2f}" …)` ohne
`floor_only_pricing()`-Schutz (`tests/test_manual_football_filters.py:225` erwartet „Quote 2.20“);
`manual_search_filters.py:72-79` „Nach Quote filtern / Quote von / Quote bis“, `:27` „Quoten müssen
mindestens 1,20 betragen.“ Widerspricht der Owner-Entscheidung vom 23.10.

**U3 – Falsche Zeitzone in der Multi-Sport-Suche**
`app.py:3798` `start.astimezone().strftime(…)` nutzt die Server-Zeitzone (UTC) statt Europe/Zurich wie
alle anderen Stellen (`wettfinder_surface.py:241`, `date_context.py:19`); Anpfiffe für Basketball,
Eishockey, Cricket, E-Sport erscheinen 1–2 Stunden zu früh. Gleicher Fehler in
`alternative_markets_tab_extended.py:124`.

### MITTEL

- **L4 – Nachrücken gibt ohne Kontextalter frei.** Der Scan verlangt Kontext ≤ 75 min
  (`wettfinder_automation.py:1952, 4044`); das Nachrücken übernimmt `context_stale=False` vom Scan und
  prüft `context_checked_at` nicht → um 21:15 Freigaben mit 17 h altem Kontext. Owner-Entscheid
  oder Altersgrenze.
- **L6 – Daily3 bleibt faktisch preisgegated.** `daily3_selection.py:158-161` verlangt
  `has_current_price_check` und `admitted_offer_odds` (Angebot ≥ 1,20, ≤ 24 h), die Doku vom 23.10.
  sagt „ohne Angebot erlaubt“. Da die meisten Zeilen unbepreist sind, ist Daily3 meist leer
  (heute: „Heute keine passende Daily3-Auswahl“). Owner-Entscheid oder Doku korrigieren.
- **L8 – Fail-closed auf Dokumentebene.** `_load_automated_wettfinder_document`
  (`ev_signal_sources.py:906-1300`) liefert bei einer inkonsistenten Zeile `None`. Empfehlung:
  Struktur-/Identitätsfehler → `None`; Preis-/Statusabweichung → Zeile samt Strict-Kopien verwerfen,
  im Status zählen.
- **S6 – FDR-Familie ist laufabhängig.** `_football_candidate_record` (`wettfinder_automation.py:485-497`)
  überschreibt `tested_hypotheses`/`fdr_q_value`/`statistical_release_passed` aus dem jeweiligen
  Lauf; `_football_record_release_eligible` akzeptiert jedes Vielfache von 96. Heute einheitlich
  3 360 (35 Ligen × 96), ein Teil-Refresh über wenige Ligen würde kleinere Familien mit kleineren
  q-Werten erzeugen. Empfehlung: feste Familie = Produktkatalog oder Nacht-q nur verschärfen.
- **S7 – Lead und Rang ohne Intervall.** Lead = Maximum über ≈ 40 korrelierte Marktwahrscheinlichkeiten
  (`forecast_selection.py:84`); `candidate_selection_rank` (`challenge_engine.py:642-660`) maximiert
  die verrauschte Zellverbesserung über 14 × 44 Zellen. Kein Konfidenzintervall auf Karte oder im
  Bericht. Lead-bedingte Reliabilität im Shadow messen.
- **S8 – E-Sport-Kalibrierkriterium misst gegen die Haircut-Wahrscheinlichkeit.**
  `esports_shadow.py:554-562` `gap = |hit_rate − avg_risk_adjusted_probability|` mit ≈ 25 pp
  Abschlag (`multi_sport_recommendations.py:853-873`); ein kalibriertes Modell kann nie
  „calibration_ready“ werden. `ESPORTS_RELEASE_MAX_BRIER = 0.25` ist Münzwurfniveau.
- **M5 – `evaluate_candidate_price` meldet „Alle Modell-, Evidenz-, Preis-, Risiko-EV- und
  Einsatz-Gates bestanden“, obwohl unter `floor` nur 1,20 geprüft wurde**
  (`multi_sport_recommendations.py:1043-1076`); Status `BET` mit Einsatz 0,00 bei negativem
  Risiko-EV. Text an den geprüften Regelsatz binden; bei Kelly 0 kein `BET`.
- **M6 – E-Sport-Haircut ≈ 25 pp unabhängig von der Datenlage** (`multi_sport_recommendations.py:855-873`,
  `esports_elo.py:25`): Elo-Differenz 0 → p 0,50, konservativ 24,7 % → Mindestquote 4,18. Unsicherheit
  aus Rating-Streuung ableiten.
- **M7 – Tennis-Defaults.** `tennis/model_state.py:74` `hold-proxy-v1`, `tennis/simulator.py:120` Hold als
  Punktwahrscheinlichkeit (Tiebreak 0,654 statt 0,592), `tennis/predict.py:212-216` arithmetische
  Mischung, `tennis/backtest.py:718-727` multiplikativer De-Vig. Produktion läuft auf v2; der Default
  bleibt eine Falle.
- **D6 – SQLite ohne WAL/Timeouts in drei Stores** (`challenge_store.py:782`, `clv_tracker.py:65`,
  `forecast_evidence.py:117`), Rohquittungen als BLOB ohne Retention (`context_observations.py:47-49`),
  `PRAGMA user_version` nur in `consumer_tip_history.py:258`, 23 ad-hoc `ALTER TABLE` in
  `challenge_store.py`. Plattenwächter und Retention für die 8-GB-Datei.
- **D7 – Lockfile ohne Verbraucher, Versionsangaben widersprüchlich** (`.github/workflows/tests.yml:40`
  installiert `requirements.txt`, `deploy/update_server.sh:1052-1059` prüft nur diese;
  `python-version` 3.11 vs. 3.12).
- **D8 – Releaseweg ausserhalb des Repos.** Releases laufen über `output/release-*/deploy.sh`
  (unversioniert); `deploy/README.md:267-277` kennt nur `betboy-update`; Bibel §9 zählt sieben Timer
  ohne `betboy-quotes` (acht Units). Helfer unter `deploy/` einchecken, Zählung korrigieren.
- **D9 – Schichtung.** 44/32/16/14 Funktionsimporte als Zyklus-Workaround; vier Wrapper um
  `minimum_recommendation_odds`; Settlement-Status fünfmal definiert. Leaf-Module `pricing_policy`,
  `settlement_status`.
- **U4 – Zahlenformate gemischt, sogar auf einer Karte**: „65.8 %“ (`wettfinder_surface.py:255`) vs.
  Kurzcheck „65,8 %“ (`forecast_analysis.py:313-319`), „1,20“ vs. „2.20“, „CHF 50.00“ vs.
  „15.000 €“. Ein Formatter (Schweiz: Punkt, Apostroph, CHF).
- **U5 – 15K rechnet in Euro** (`challenge_15k.py:727-729, 3721`, `ui_components.py:188`), Rest CHF.
- **U6 – Daily3-Slogan und „Ziel +CHF 150“** (`daily3_ui.py:249, 253`) suggerieren Ertrag neben dem
  eigenen Satz „Wetten sind kein verlässliches Einkommen“ (`:266`). Name ist Owner-Entscheid,
  Slogan-Hälfte und Ziel nicht.
- **U7 – Begriffe**: drei Namen für Daily3 (`app.py:132, 4820-4839`, `daily3_ui.py:322`);
  Auswahl/Markt/Tipp/Modell uneinheitlich; Fachjargon „Planungsabstand“, „Gate“, „Roll-over“,
  „Sicherheitswert“ (`challenge_15k.py:4087`, suggeriert Sicherheit), „Außenseiter-Szenario“ im
  Wettfinder; Leerzustände als rote Grossbuchstaben (`app.py:3065, 3466, 4249`, `tennis_tab.py:840`).
- **U8 – Karten-Raster mit Leerspalten** seit Quotenentfall (`editorial_theme.py:57, 111, 237`); Live
  nicht als experimentell gekennzeichnet (`app.py:115-118`, `bet_finder_ui.py:936`); Daily3-
  Fehlermeldung weit vom Formular (`daily3_ui.py:250-252` vs. `:361-385`); Kurzcheck-Fakt
  „Gegenargument“ zeigt Kategorie statt Inhalt (`forecast_compact.py:141, 202, 214`); Rechtstexte-
  Platzhalter und Betriebsjargon im Footer (`legal_notice.py:24, 37`).

### NIEDRIG

- L9 `_AUTOMATED_PRICE_STATUS_CODES` (`ev_signal_sources.py:819`) kennt `UNPRICED/BELOW_FLOOR/OBSERVED/EDGE_CAP`
  nicht; `price_status_counts` verschweigt sie. L10 `price_check_attempts` im Scan (`:4294-4300`)
  verwirft `prices:esports`/`prices:team_sports` (ein zusätzlicher Abruf). L11 `refresh_prices_only`
  (`:5052`) ohne `load_state`-Versionsprüfung.
- M8 `floor_price_status` nimmt das Maximum über alle Beobachtungen der letzten 24 h, nicht die jüngste
  je Buchmacher (`market_consensus.py:597-600`): ein 23 h altes 1,22 hält den Tipp, obwohl alle
  aktuellen Angebote 1,10 sind. M9 Dixon-Coles fällt zu Saisonbeginn für die ganze Liga aus
  (`football_dixon_coles.py:34-35, 326`). M10 Lead-Regel wählt systematisch die breitesten Märkte
  (faire Quote 1,05–1,15), für die unter `floor` kein EV-Hinweis existiert.
- S9 `tested_hypotheses = 96`, aber nur 44 unterscheidbare Hypothesen (Komplementärmärkte); BH
  numerisch unberührt; Bibel nennt 90 (`PROJEKTBIBEL.md:266, 511`). S10 Bootstrap im Marktbenchmark
  i.i.d. über korrelierte Wetten (`market_benchmark.py:294`).
- D10 Getrackte Logs (`streamlit_run*.log`, `demo_*.log`), `git-push.bat` mit `git add -A` auf `main`,
  20 lokale `claude/*`-Branches; D11 Buchmacherlinie fällt bei nicht-numerischer Eingabe auf den
  Rohstring zurück (`app.py:4293-4306`); D12 Timer-Zeitzonen gemischt; D13 Konstanten-Spiegeltests.
- U9 ß statt Schweizer ss; Englisch/Platzhalter („VS“, „Match Winner“, „BTTS %“, „Turnier?“);
  Schriftgrössen bis 0,6 rem (`editorial_theme.py:87, 142, 178`); `aria-label` auf nicht-interaktivem
  `<span>` (`wettfinder_surface.py:1039`); tote Sortiersteuerung (`tip_display_order.py:12-19`);
  Cricket ohne Icon (`editorial_theme.py:50-56`); toter Code `_render_wettfinder_card_actions`
  (`app.py:4620-4637`); RisikoBet nennt die ukrainische Liga „Premier League“ (Live-Stichprobe).

---

## 4. Was gut ist

1. **Numerik und Methodik**: Kelly, EV, Shin/Power-No-Vig, Dixon-Coles-MLE (Gradient numerisch bis
   1,1e-7 verifiziert, synthetische Parameter-Recovery), `score_matrix` normiert, `market_outcome`
   exakt, Walk-forward ohne Look-ahead, HAC mit Newey-West-Bandbreite, BH-Step-up korrekt,
   Kontextmodelle mit Train/Tune/Test und Late-Result-Ausschluss.
2. **Integrität**: HMAC-Ledger mit Owner-/Mode-/Hardlink-Prüfung, unveränderliche Evidenz-DBs per
   Trigger, Daily3 mit idempotenten `action_id`, Doppelbuchungsschutz und Worst-Case-Schranke,
   atomare Schreibvorgänge (tmp + fsync + `os.replace`), eine Sperre für Scan und Quotenlauf,
   Byte-Vergleich vor dem Schreiben.
3. **Sicherheit**: Secrets nur über `config_loader`, Units mit `NoNewPrivileges/PrivateTmp/ProtectHome`,
   Streamlit nur auf Loopback hinter Caddy mit HSTS, keine `eval/exec/yaml.load`, Deserialisierung
   mit Grössen-Grenzen, `open_trusted_pickle`.
4. **Preisregel konsequent**: Alle Produzenten gehen über eine Weiche, `gate` stellt den Altvertrag
   wieder her; Karte, Daily3, Tennis, Multi-Sport, Meine Tipps ohne Quote; Ablehnungen begründet.
5. **UX-Fortschritt**: Rechtsfooter mit 18+, SOS Spielsucht 0800 040 080 und Sucht Schweiz; keine
   Garantieversprechen; Hauptauswahl nach Owner-Regel; Paginierung ohne zerschnittene Spiele;
   Formchips mit `aria-label`, Tabellen mit `scope`, Fokusringe, 44-px-Touchziele, Mobile-Umbrüche.
6. **Testsubstanz**: 458 Dateien, 6 629 Tests, kaum ungeseedeter Zufall, kein ungemocktes Netz;
   Quick-CI mit ruff.

---

## 5. Massnahmenplan in Reihenfolge

| # | Massnahme | Aufwand | Löst |
|---|---|---|---|
| 1 | Lader: Preis-/Statusabweichung je Zeile verwerfen statt Dokument; `UNAVAILABLE` mit behaltener Quote neu bewerten; Nachrücken an `sources[…].operational_error_count` binden; 15K-Snapshot mit Zeilen-Uhr und Floor-Status; Fussball-Quotenlauf filtert Budgetmeldungen | 1–2 Tage | L1, L2, L5, L8 |
| 2 | Shadow: `'Won'`-Vergleich, Hybrid-Warm-up vor der Bewertung und nicht-terminal, veröffentlichte `candidate_id`s mitprotokollieren, HAC-Intervalle für CLV-Differenzen | 2–3 Tage | S2, S3, S5, D4 |
| 3 | Betrieb: Versuchsstempel/Toleranz im Quotenlauf, Budget als `budget_deferred`, `OnFailure=`-Alarm, `Persistent=true`, Tennis-Fallausschluss mit Diagnose (Codex) | 1–2 Tage | D2, D3, D5 |
| 4 | Tests: Policy-Fixture parametrisieren, Lader-/Publikations-/Daily3-/15K-Suiten unter `floor` in CI; Lockfile in CI und Updater | 1 Tag | D5, D7 |
| 5 | Owner-Entscheide: Daily3-Pool (RELEASED oder Research), Angebotspflicht Daily3, Kontextalter beim Nachrücken, Backup-Strategie, Währung 15K, Slogan/Ziel Daily3 | Entscheid | M1, L4, L6, D1, U5, U6 |
| 6 | Evidenz ehrlich: Label „Modell geprüft“ präzisieren oder Marktgate; Evidenzstufe als Textzeile; `evaluate_candidate_price`-Text; Risiko-EV am 1,20-Boden als Hinweis | 2 Tage | S1, U1, M5 |
| 7 | UX-Politur: Quotencaption und Quotenfilter der Manuellen Suche, Zeitzone Multi-Sport, Formatter, Begriffe, Leerzustände, Raster | 2–3 Tage | U2, U3, U4, U7, U8 |
| 8 | Hybrid vor Aktivierung: DC-Unsicherheit in Haircut/Score, ρ unter Hybrid-Likelihood oder ohne ρ-Anspruch, Kalibrier-Residualfehler als Gate | 1 Woche | M2, M3, M4 |
| 9 | Persistenz: WAL/Timeouts, Retention und Plattenwächter für `context_models.db`, `user_version` je DB | 2–3 Tage | D6 |
| 10 | Strukturell (unverändert seit 16.10.): Marktbenchmark-Kanal als Freigabebedingung, Dixon-Coles als Produktionsbasis, Haircut aus Schätzunsicherheit, Tennis-Kalibrierung, Domänenpaket ohne Zyklen | Wochen | K2, K3, H1–H3, H9 (16.10.) |

Punkt 1 ist dringend: Jede weitere Statuskombination eines Produzenten leert die Website wieder
vollständig.

*Stand 25.10.2026 abends:* Massnahmen 1 und 2 umgesetzt (`docs/audits/2026-10-25-lader-je-zeile.md`,
`docs/audits/2026-10-25-shadow-massnahme-2.md`); aus Massnahme 2 bleibt der No-Vig-CLV (S5, zweiter
Teil) offen.

---

## 6. Methodik und Kennzahlen

| Kennzahl | Wert |
|---|---|
| Python-LOC (Root, `context_models/`, `tennis/`, ohne Tests) | 114 266 |
| Grösste Module | `challenge_15k` 5 775, `challenge_store` 5 201, `wettfinder_automation` 5 130, `app` 5 118, `challenge_engine` 4 899 |
| Tests | 458 Dateien, 6 629 Tests; CI: ruff + 3 Dateien; Vollsuite ≈ 1,5 h (nicht in CI) |
| Tests unter Produktionspolicy `floor` | 20 (`tests/test_price_floor_policy.py`) |
| Gelaufene Prüfungen heute | 252 Mathematik, 93 Statistik, 72 Betrieb, 20 Preisregel, 600 Lader/Publikation/Oberfläche (im Zuge der Hotfixes) |
| Laufzeitdaten VPS | `context_models.db` 8,0 GB, `forecast_evidence.db` 462 MB, `riskobet.db` 399 MB, `wettfinder_latest.json` 21,8 MB |
| Produktion | `8e4d06f`, Releases nur manuell per No-Backup-Fast-forward (6 Releases am 23.–25.10.) |

Nicht offline verifizierbar: Produktions-Env (`/etc/betboy/betboy.env`; Code-Defaults angenommen),
Semantik des API-Football-`update`-Stempels (wird er nur bei Quotenänderung gesetzt, ist die
Closing-Erfassung an Bewegung gekoppelt), Inhalte der Shadow-Datenbanken jenseits der Zähler.

---

## 7. Offene Fragen an den Owner

1. Soll `RELEASED`/„Modell geprüft“ ohne Marktvergleich öffentlich bleiben, oder wird das Label
   präzisiert beziehungsweise das Marktgate zur Bedingung?
2. Daily3: Pool auf freigegebene Zeilen beschränken oder als Research deklarieren? Angebotspflicht
   unter `floor` streichen (dann wird Daily3 wieder befüllt)?
3. Nachrücken: Kontextalter von 75 Minuten durchsetzen (weniger Tipps am Abend) oder die Tagesregel
   akzeptieren?
4. Backup: OVH-Snapshot als Strategie, oder getrenntes Ledger-Backup aktivieren?
5. 15K: Euro bleibt (Simulation) oder CHF wie der Rest?
6. Daily3-Slogan „keeps the job away“ und „Ziel +CHF 150“: bewusst oder streichen?
