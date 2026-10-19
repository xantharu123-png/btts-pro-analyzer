# BetBoy – Gesamtaudit 16. Oktober 2026

Perspektiven: Wettprofi (50 Jahre Praxis), Professor für Logik/Statistik/Wahrscheinlichkeit, Chief Developer, UX-Designer.
Geprüft: Hauptcheckout `C:\Projekt\BetBoy\betboy-app` (`main` @ `c5a6264`, 12 Dateien mit lokalem WIP), Reparatur-Worktree `.worktrees/audit-repairs-20261013` (`c110d8e`, laut Doku auf dem VPS live) und die Produktions-App `https://vps-a30a123f.vps.ovh.net/` (ohne Login erreichbar, Stichprobe 16.10.2026 ca. 05:00–06:00 UTC).
Methode: Lesen des Codes (vier parallele Tiefenprüfungen plus eigene Verifikation jeder kritischen Aussage), Nachrechnen der auf der Produktionsseite angezeigten Zahlen, gezielte Testläufe. Es wurde nichts verändert.

Alle Zeilenangaben beziehen sich auf den Hauptcheckout, sofern nicht anders vermerkt. Die drei Kernbefunde zur Mathematik wurden zusätzlich im Reparatur-Worktree verifiziert (identische Zeilen ±8).

---

## 0. Kurzurteil

**Wettprofi:** Mit diesem System würde ich heute kein Geld setzen, und die Projektbibel sagt das an mehreren Stellen selbst. Die Disziplin (Modell vor Preis, fail-closed, HMAC-Ledger, Fréchet-Stress) ist beeindruckend. Aber das Freigabe-Gate beweist nur, dass das Modell besser ist als die Ligahäufigkeit, nicht dass es den Buchmacher schlägt. Haircut plus Preisgate selektieren systematisch die Spiele, in denen das Modell am weitesten vom Markt entfernt ist, also die mit dem grössten erwarteten Modellfehler (Winner's Curse). Auf der Produktionsseite sah ich heute einen 15K-Kandidaten mit negativem Erwartungswert und eine Tagesauswahl mit veraltetem Kontext.

**Professor:** Die Numerik ist sauber (Normierung, lgamma, Walk-forward ohne Leakage, HAC-Standardfehler, Benjamini-Hochberg). Die Modelle darunter sind einfach: additive Torraten aus 12/6 Spielen ohne Gegnerbereinigung und ohne Zeitgewichtung, unabhängiges Poisson ohne Dixon-Coles, pauschale Prozentpunkt-Abschläge statt Schätzunsicherheit, Tennis-Kalibrierung auf einer anderen Population als der gewetteten. Keiner dieser Punkte ist ein Rechenfehler, alle sind Strukturfehler. Genau diese Punkte stehen bereits im Audit vom 2. September; sechs Wochen und rund 60 Worktrees später ist keiner davon umgesetzt.

**Chief Developer:** Produktionsnaher Prototyp mit professionellem Deploy, aber ohne Paketstruktur, CI, Linter oder Lockfile. 145 Module flach im Root, 14 Importzyklen, Funktionen mit 750 bis 1500 Zeilen, 160 stille `except Exception`. Der Hauptcheckout liegt 27 Commits hinter dem deployten Stand. Kritisch: Die drei heute aktiven API-Schlüssel sind byteidentisch mit denen, die im Januar 2026 in das öffentliche GitHub-Repo committed wurden. Der tägliche Produktions-Backup-Timer ist laut eigener Doku seit Wochen inaktiv.

**UX-Designer:** Ein Analyse-Backend mit Magazin-Typografie, noch kein Consumer-Produkt. Die Hauptkarte zeigt Modell-p und Quote, aber nicht die Mindestquote, nicht das konservative p und nicht den Preisstatus, also genau das, was die Bibel als Produktversprechen definiert. Die erste Karte, die ein Besucher heute sieht, ist ein E-Sport-Münzwurf (52,3 %) mit dem Hinweis "Modellstand nicht aktuell belegt". Kein Onboarding, kein Glossar, kein Altershinweis, kein Spielsucht-Hinweis, kein Impressum in der App, sieben Navigationspunkte, die auf dem Handy horizontal wegscrollen.

**Gesamtnote:** Technisch-integritätsseitig überdurchschnittlich, wettfachlich unbewiesen, produktseitig halb fertig. Vor einem bezahlten Start (Stripe-Preise 9.90/19.90/29.90 CHF sind bereits angelegt) fehlen ein Marktnachweis, die Sicherheitsrotation und die Consumer-Pflichtseiten.

---

## 1. Stand gegenüber dem Audit vom 2. September 2026

| Befund 02.09. | Status 16.10. | Beleg |
|---|---|---|
| B1 Release-Gate gegen Basisrate statt Markt | **unverändert** | `challenge_engine.py:2303` `baseline = (successes+1)/(totals+2)` |
| B2 Haircut + Preisgate = Winner's Curse | **unverändert** | `challenge_engine.py:2642-2650` |
| B3 Additives Tormodell, unabhängiges Poisson, keine Zeitgewichtung | **unverändert** | `challenge_engine.py:1241`, `:720-753`, `:925-985` |
| B6 Fréchet-Untergrenze als Gate | **unverändert** | `challenge_engine.py:3973-3984` |
| C2 Proportionaler No-Vig | **unverändert** | `betting_math.py:157` |
| C3 CLV als Rohquotenverhältnis bei Bet365 | **unverändert** | `clv_tracker.py:707`, `shadow_clv_automation.py:81-83` |
| C6 Tennis 15 pp Haircut, nur Hartplatz | **unverändert** | `tennis/predict.py:43,48` |
| Kalibrierung v2 | geprüft, bewusst nicht aktiviert | `TODO_AKTUELL.md` 13.10. |
| Reparaturpaket 13.10. (Auszahlung, Settled-Daten, Decimal, Tennis-Kausalität, Merkliste) | umgesetzt | `TODO_AKTUELL.md` 13.10. |

Die Arbeit seit September floss fast vollständig in Kontext-Infrastruktur (Kader, Belastung, Wetter, Transport, Provenienz). Das ist handwerklich sauber, aber laut Bibel §3.9 ändern diese Achsen die Modellwahrscheinlichkeit numerisch nicht. Der Hebel für bessere Wettergebnisse liegt weiterhin in B1 bis B3.

---

## 2. Befunde nach Schwere

### KRITISCH

**K1 – API-Schlüssel in der öffentlichen Git-Historie, nie rotiert**
Beleg: Commits `6161875` (12.01.2026), `93bf91f`, `b0d73b9` enthalten `config.ini` und `.streamlit/secrets.toml` mit Klartext-Schlüsseln; entfernt erst in `e7d5756` (11.07.2026). Vergleich der heutigen Dateien gegen die Historie (nur Länge und Identität geprüft, keine Werte ausgegeben): `api_key`, `weather_key`, `api_football_key` sind **identisch** mit den committeten Werten. Das Repo `xantharu123-png/btts-pro-analyzer` ist laut GitHub-API `PUBLIC`.
Wirkung: Jeder kann das API-Football-Tageskontingent (7500 Aufrufe, `api_budget.py:21`) und die anderen Dienste auf eure Kosten nutzen oder leeren; damit fallen Scans aus.
Fix: Alle drei Schlüssel heute rotieren (football-data.org, OpenWeatherMap, API-Football); PandaScore prüfen. Schlüssel nur noch per Umgebungsvariable (`config_loader.py:91-96` kann das). Optional `git filter-repo` plus Force-Push, aber Rotation ist das Entscheidende.

**K2 – Release-Gate beweist "besser als Basisrate", nicht "besser als der Markt"**
Beleg: `challenge_engine.py:2256-2336` `_walk_forward_market_records`, Baseline Zeile 2303. Paired-Brier, HAC-Untergrenze und BH-FDR (`model_loss_statistics.py`) vergleichen ausschliesslich gegen diese Laplace-Basisrate. `MIN_RELATIVE_BRIER_IMPROVEMENT = 0.02` (`:78`). Ein No-Vig-Marktbenchmark existiert im Freigabepfad nicht; `proportional_no_vig_market` wird nur in `scanners/smart_bet_finder.py` genutzt.
Wirkung: `RELEASED` ist eine Softwareaussage, keine Marktaussage. Jedes Poisson-Modell schlägt die Ligahäufigkeit. Ein freigegebener Tipp kann ein Modell sein, das den Markt systematisch unterläuft.
Fix: Zweiter Validierungskanal mit historischen Closing-Quoten (football-data.co.uk liefert Pinnacle-Closing für die Kernligen seit 2019). Paired Brier Modell vs. No-Vig-Closing mit derselben HAC/FDR-Maschinerie. Erst ein positiver Konfidenzrand gegen den Markt darf `RELEASED` setzen.

**K3 – Haircut + Preisgate selektieren Modellfehler (Winner's Curse), Abschlag nicht skaleninvariant**
Beleg: `challenge_engine.py:2636-2650`: `haircut = min(20, max(3 + 0.5·spread + Stichprobenstrafe + Frischestrafe, max_calibration_error·100))`, `conservative = min(active, season, form) − haircut`. Der Abschlag hängt nicht von der Abweichung zum Markt ab; es gibt kein Shrinkage zum Markt, keine Kappung der zulässigen Abweichung. `ev_calculator.py:10` 5 pp, `tennis/predict.py:48` 15 pp, `riskobet_candidates.py:1705` 10 pp.
Rechnung (5 pp Abschlag, 3 % Ziel-ROI): p = 0,15 → Mindestquote 10,30 statt fair 6,67 (+54 %); p = 0,50 → 2,29 statt 2,00 (+14 %); p = 0,85 → 1,29 statt 1,18 (+9,5 %). Die Stichprobenunsicherheit in Prozentpunkten ist bei 0,15 und 0,85 gleich gross, die ökonomische Wirkung nicht.
Wirkung: Aussenseiter (Remis, Auswärtssieg, RisikoBet) sind faktisch unspielbar; Favoriten und Team-Totals passieren das Gate am leichtesten, genau dort ist die relative Marge am grössten. Eine Wette wird nur gespielt, wenn das Modell den Markt um Haircut plus 3 % plus Marge übertrifft; solche Abweichungen sind, wenn der Markt die Modellinformation ebenfalls kennt, überwiegend Modellfehler.
Fix: Entscheidungswahrscheinlichkeit als Mischung im Log-Odds-Raum `logit(p_dec) = w·logit(p_modell) + (1−w)·logit(p_markt)`, `w` walk-forward geschätzt; zusätzlich Edge-Cap (z. B. Modell-p darf No-Vig-Markt-p um höchstens 8 pp übertreffen, darüber "Modell prüfen"). Modell-p bleibt roh gespeichert.

**K4 – Daily3: Echtgeld-Reservierung ohne EV-Gate und mit veraltetem Kontext**
Beleg: `daily3_selection.py:28` `MIN_MODEL_PROBABILITY = 0.70`; Zeilen 101-125 prüfen nur Preisfrische, Publikationsboden 1,20, Zeitfenster und Modellgates; kein ROI-, kein Mindestquoten- und kein Evidenzstufen-Check. `daily3_ui.py:168` "Ziel +CHF 150, nicht garantiert". `PROJECT_HANDBUCH.md:565` verlangt "Nur RELEASED darf einen Echtgeld-Einsatz erzeugen".
Produktion 16.10.: Tagesauswahl "Djurgårdens IF Team-Total Unter 2,5", Modell 76,7 %, letzte Quote 1,55. Nachgerechnet: λ = 1,67 → P(≤2) = 0,767, stimmt. Die Quote impliziert 64,5 % (no-vig ≈ 62 %), also λ ≈ 2,2. Das Modell behauptet 12 bis 15 pp Vorsprung vor dem Markt in einer liquiden Allsvenskan-Partie. Dieselbe Karte zeigt "Ausfälle veraltet", "Aufstellung offen", "Spielinformationen nicht aktuell belegt".
Wirkung: Ein Konsument reserviert reales Geld (CHF-50-Budget) auf eine Auswahl, die weder preisgeprüft noch kontextaktuell ist. Bei p = 0,70 und Quote 1,20 ist der EV −16 %.
Fix: Reservierung nur, wenn die erfasste Quote ≥ `minimum_recommendation_odds(p, haircut)`; Kontextveto (veraltet/offen) blockiert die Tagesauswahl; p ≥ 0,70-Filter durch EV-Rangfolge ersetzen.

**K5 – 15K-Kandidat mit negativem Erwartungswert prominent angezeigt**
Beleg Produktion 16.10.: "Radnik Surdulica Team-Total Über 0,5", Modell 76,4 %, letzte Quote 1,27. Nachgerechnet: λ = 1,44 → P(≥1) = 0,763, stimmt. Implizierte Wahrscheinlichkeit 78,7 % > Modell 76,4 % → EV = 0,764 × 1,27 − 1 = **−3,0 %**, vor Haircut. `challenge_15k.py:3655` erklärt daneben "70 Gewinne in Folge bei Quote 2,50 … Kein Versprechen, nur Mathematik". Bei p ≈ 0,45 je Wette ist 0,45^70 ≈ 10^-24.
Wirkung: Die 15K-Seite präsentiert eine Auswahl, die mathematisch nicht spielbar ist, als "Modellauswahl". Dass die Quote erst bei Erfassung zählt, ist für den Nutzer nicht erkennbar. Die 15K-Challenge ist in ihrer Konstruktion (100 € → 15 000 € über Singles mit Quote 2 bis 3) eine Lotterie-Inszenierung, die der Bibel-Positionierung "keine sicheren Tipps" widerspricht.
Fix: Kandidaten mit bekannter Quote unter `minimum_recommendation_odds` nicht als Modellauswahl, sondern als "Preis reicht nicht" zeigen; die Challenge als Simulation deklarieren oder mit Ruinwahrscheinlichkeit beschriften.

**K6 – Tägliches Produktions-Backup inaktiv**
Beleg: `TODO_AKTUELL.md` 13.10. "Backupdienst/-timer weiterhin inactive, 21GiB frei" und drei weitere Stellen; Backup nur vor Deploys (`deploy/update_server.sh:2046-2056`, 82 SQLite-Dateien im Archiv).
Wirkung: Zwischen Deploys kein Restore-Punkt für Geld-Ledger (`challenge_store.py`) und Kundendaten.
Fix: `betboy-backup.timer` aktivieren, Restore-Probe dokumentieren, Offsite-Kopie.

### HOCH

**H1 – Tormodell strukturell unter Marktniveau**
`challenge_engine.py:1172-1300` `_fixture_model`: `season_home = (home_scored + away_conceded)/2` (additiv statt multiplikativ wie Maher/Dixon-Coles); Stärke aus den letzten 12 Venue-Spielen (Prior-Gewicht 4) und 6 Formspielen (Prior 3), Mischung 0,75/0,25; keine Gegnerbereinigung der Historie; keine Zeitgewichtung (`_team_observations` gewichtet gleich, `_league_goal_means` mittelt die gesamte Historie). `score_matrix` (`:720-753`) ist unabhängiges Poisson, `DixonColesModel` existiert nur in `advanced_analyzer.py:347` als Legacy. Beispiel Ligamittel 1,5, Heimangriff 2,2, Gästeabwehr 2,0: additiv 2,10, multiplikativ 2,93. Mindestens 5 Venue-Spiele reichen (`MIN_VENUE_MATCHES = 5`): bei n = 5 und Prior 4 ist die Schätzung zu 45 % Prior.
Fix: Dixon-Coles per Maximum-Likelihood je Liga (Angriff, Abwehr, Heimvorteil, ρ, exponentieller Zeitdecay) über mehrere Saisons; xG-Blend 0,6 beibehalten. `football_opponent_strength.py:250-271` enthält bereits ein log-lineares Modell offline. Walk-forward, Kalibrierung und Gates bleiben.

**H2 – Haircut ist kein statistisches Intervall; Dreifachzählung von Modellstreit**
`challenge_engine.py:2636-2650`: `min()` der drei Varianten, plus `0,5·spread`, plus Block bei `spread > 12` (`:2665`). Der Kalibrier-Haircut nimmt den schlechtesten Bin des gesamten Validierungssatzes, unabhängig vom Bin des Kandidaten (bei n ≈ 40 pro Bin reines Rauschen ±8 pp); `adaptive_bin_threshold` erlaubt genau diesen Wert, womit Stichprobenrauschen direkt als Abschlag verbucht wird. Evidenzscore `35/15/20/10/20` (`:2652-2658`) und Schwelle 72 sind gesetzte Zahlen.
Fix: Unsicherheit per Delta-Methode/Bootstrap über die 12/6-Spiele-Stichprobe, unteres Quantil; Kalibrierunsicherheit nur aus dem Bin des Kandidaten.

**H3 – Tennis: Kalibrator auf anderer Population als die gewettete, 15 pp Pauschale, Belagsregel aus dem Backtest**
`tennis/backtest.py:663-690, 766-767`, `tennis/model_state.py:188-200`: Platt-Kalibrator auf allen ATP-Zeilen (alle Beläge, inkl. Elo-only), gewettet wird nur Hartplatz mit Serve-Daten und ≥ 20 Matches (`predict.py:43, 299-312`). Kommentar `:45-47` gibt die Überkonfidenz zu, die der 15 pp-Abschlag kaschiert: p_cal 0,60 → 0,45 → Mindestquote 2,29 statt fair 1,67. `ALLOWED_SURFACES = ("Hard",)` "weil Clay/Grass im Backtest negativ" ist Schwellen-Tuning nach dem Ergebnis (Bibel §3.5 verbietet das).
Produktion 16.10.: Karte "Ruud vs. Jodar", Auswahl Jodar 54,6 % (Betfair 1,85), darunter der Satz "Die Aufschlag- und Rückschlagdaten sprechen eher für Casper Ruud." Ruuds "letzte 5 Spiele" reichen vom 18.03. bis 07.10.2026, also fehlen Monate an Daten.
Fix: Kalibrierung auf der gewetteten Population oder Belag/Serve-Verfügbarkeit als Kovariaten; Haircut aus Kalibrier-SE; Belagsregel durch vorregistrierte Ablation ersetzen; Datenlücken auf der Karte als Veto.

**H4 – Legacy-Tiebreak-Formel verwendet Hold- als Punktwahrscheinlichkeiten**
`tennis/simulator.py:120` `p_tb_a = (p_hold_a + (1 − p_hold_b))/2` ist dimensional falsch (Hold ≈ 0,8 vs. Punkt ≈ 0,65); bei Hold 0,85/0,75 ergibt das ≈ +7 pp Tiebreak-Überschätzung für den stärkeren Aufschläger. Der Code-Default ist noch `market_model_version = "hold-proxy-v1"` (`model_state.py:74`); die Produktionsartefakte laufen laut `docs/audits/2026-10-03-auswahlbilanz.md` auf `serve-points-joint-v2` (korrekte Inversion `_point_set_distribution_cached`).
Fix: v2 als Default; Legacy nur für Replay.

**H5 – CLV misst das Falsche und kann strukturell kaum messen**
`shadow_clv_automation.py:81-83` Referenz Bet365 (Softbook), `:837-869` Closing nur im 15-Minuten-Fenster; `clv_tracker.py:707` `clv = opening/closing − 1` roh verviggt, ohne Konfidenzintervall, ohne Markt-/Ligatrennung; `market_consensus.py:60-62` API-Football aktualisiert Prematch-Quoten etwa alle 3 Stunden. `PROJECT_HANDBUCH.md:1305` "0 Entry-Quotes, 0 Closings".
Fix: Pinnacle (The Odds API liefert ihn) als Referenz, beidseitig de-viggt (Shin für 3-Wege, Power für 2-Wege), CLV = `p_close_novig · Quote − 1` mit HAC-Intervall je Markt und Liga; Feed mit Minutentakt für Opening/Closing.

**H6 – Keine Stichprobe, die eine Rendite belegt oder widerlegt**
Lokale Datenbanken: `saved_tips` 0, `challenge_tickets` 0, `shadow_clv.predictions` 0, `consumer_tips` 0 (5 Publikationen). Produktionsprobe 30.09.–02.10. (`docs/audits/2026-10-03-auswahlbilanz.md`): 181 Prognosen, 107 gewonnen, Brier 0,2128, Log-Loss 0,6106; einzige abgerechnete bepreiste Teilmenge: 11 Tennispreise, **−2,00 Einheiten**. Ein konstanter Prädiktor mit der Trefferrate 0,59 hätte Brier 0,242; der Vorsprung ist Klimatologie-Skill, kein Marktskill. 113 von 181 Preisen fehlten, 56 waren veraltet.
Fix: Siehe K2; bis dahin kein Pfad `RELEASED`.

**H7 – Hauptcheckout 27 Commits hinter dem deployten Stand, WIP auf veralteter Basis, 60 Worktrees**
`git rev-list --count HEAD...origin/main` = 0/27; 12 modifizierte und 16 untrackte Dateien im Root; `git worktree list` zeigt 60 Einträge, die Doku erklärt eine Worktree-Kopie der TODO zur "autoritativen". 28 MB Garbage-Pack in `.git/objects/pack`.
Wirkung: Niemand ausser dem Autor weiss, welcher Checkout gilt; Mergekonflikte und verlorene Arbeit sind vorprogrammiert.
Fix: WIP auf Branch committen, `main` fast-forwarden, Worktrees auf unter fünf reduzieren, `git gc`.

**H8 – Keine CI, kein Linter, keine Lockdatei, Tests nur manuell**
Kein `.github/workflows`, kein `pyproject.toml`, kein `pytest.ini`, kein `ruff`/`mypy`; `requirements.txt` pinnt nur Streamlit; drei venvs. QA-Nachweis sind 16 `.pytest-*`-Ordner im Root und 52 `.qa-*`/`.form-contract-*`-Ordner im Parent, nicht gitignored, teils mit Datenbanken. 97 Tests sind Linux-only (`fcntl`), der Produktionspfad wird auf dem Windows-Dev-PC nicht getestet.
Fix: `pyproject.toml` mit pytest/ruff, GitHub-Action auf Linux, `uv lock`, Artefaktordner löschen und ignorieren.

**H9 – Importzyklen und God-Functions**
14 Zwei-Zyklen, stark zusammenhängende Komponenten der Grösse 13 (`context_runtime*`), 7 (`challenge_engine` ↔ `football_joint_calibration` ↔ `daily3_comparison` ↔ …), 7 (`challenge_15k` ↔ `wettfinder_automation` ↔ …). `football_joint_calibration.py:30` importiert `challenge_engine` in einer Funktion, `challenge_engine.py:1861` umgekehrt. `run_wettfinder` 1183 Zeilen (`wettfinder_automation.py:3279-4462`), `_apply_app_styles` 1507 Zeilen CSS als Python-String bei jedem Rerun (`app.py:415-1922`), `ChallengeLedger._initialize` 879 Zeilen, `scan_daily_challenge` 758 Zeilen mit 232 `st.*`-Referenzen (UI, Scan und Datenzugriff gemischt).
Fix: Reine Domänenfunktionen (`market_outcome`, Kalibrierung, Settlement) in ein zyklenfreies `betboy/domain/`-Paket; `import-linter`; CSS nach `assets/app.css`; `run_wettfinder` in Phasenfunktionen.

**H10 – UX: Mindestquote, konservatives p und Preisstatus fehlen auf der Hauptkarte; Preisprüfung nicht verdrahtet**
`wettfinder_surface.py:931-965` `render_editorial_card_html` rendert Markt, Auswahl, Modell-p, Quote, Kurzcheck, Form. `value_threshold`, `cautious_probability`, `price_label`, `evidence_label` werden nur in `_top_card_markup`/`_compact_row_markup` (`:743/:783`) benutzt, die keine Aufrufstelle in `app.py` haben. `_render_wettfinder_card_actions` (`app.py:4608-4624`) mit `render_price_decision` ("Eigene Quote prüfen") wird nirgends aufgerufen; in Produktion existieren "Tipp merken"-Buttons (quotenfreie Merkliste, Worktree-Stand), aber keine Preisprüfung auf der Karte. Der freigegebene Wireframe (`docs/ux/wettfinder-v2/WETTFINDER_WIREFRAME_V1.md:56-69`) verlangte "Value ab …", Evidenz- und Preisstatus.
Wirkung: Der Nutzer sieht "Modell 76,7 %" und "Quote 1,55" und kann nicht beurteilen, ob 1,55 reicht. Das Produktversprechen aus Bibel §1 (Mindestquote, konservatives p, Ablehnungsgrund) ist auf der ersten Ebene nicht eingelöst.
Fix: Vierte Zelle "Value ab X.XX" plus Statusbadge plus eine Zeile Preisnotiz; `render_price_decision` in `_render_wettfinder_game` verdrahten.

**H11 – UX: Kein Onboarding, kein Glossar, keine Pflichthinweise**
Grep über alle UI-Module nach Glossar/Willkommen/Sucht/18: 0 Treffer; Produktionsseite: kein Impressum, kein Datenschutz, kein Altershinweis, kein Beratungslink; einziger Hinweis ist der Footer "Modellwerte sind Schätzungen. Wetten können zum Verlust des Einsatzes führen." (`app.py:5057-5059`). Begriffe wie Gegenrisiko, Value-Grenze, Risiko-EV, Modell-Unsicherheitsabschlag nur per `help=`-Tooltip (20 Stück; `docs/ux/sports-editorial/DESIGN.md:60` verbietet hover-only).
Fix: Einmaliges "So liest du eine Auswahl"-Panel, Glossar-Popover, Footer mit Impressum, Datenschutz, 18+ und Beratungslink (z. B. SOS Spielsucht). Für die Schweiz vor einem bezahlten Start rechtlich zwingend.

**H12 – UX: Erste Karte des Tages ist ein E-Sport-Münzwurf, beide Seiten werden als "Auswahl" gezeigt**
Produktion 16.10.: Wettfinder-Karte 1 "VALORANT Team Vitality vs. LOUD", "Sieg Team Vitality 52,3 %", Quote "–", Form beider Teams 4S/1N, "Modellstand nicht aktuell belegt". RisikoBet zeigt dasselbe Spiel als "Aussenseitersieg LOUD 47,7 %". Die Bibel stuft E-Sport als "Shadow-Aufbau; Preis- und Kalibrierungsevidenz unzureichend" ein. `riskobet_candidates.py:279`: Aussenseiter wird aus dem eigenen Modell bestimmt, nicht aus dem Markt.
Wirkung: 2,3 pp Abstand zum Münzwurf sind Rauschen; dass beide Seiten in zwei Tabs als Auswahl erscheinen, zerstört Vertrauen. Sortierung nach Startzeit statt Evidenz setzt die schwächste Sportart ganz oben.
Fix: Sportarten ohne Evidenzfreigabe nicht in der Standardansicht; Aussenseiter marktdefiniert; Standardsortierung nach Evidenz und Preisstatus.

**H13 – UX: Zwei Design-Systeme übereinander, Mobile-Navigation, Portal-Bruch, Währungsmix**
`app.py:418-1913` (1496 Zeilen CSS, 75 `!important`, 68 `data-testid`-Selektoren) plus `editorial_theme.py:13-251` (239 Zeilen) mit neuen Werten für dieselben Tokens; drei verschiedene Grüns (#16784b, #154d39, #27874b). Sidebar komplett versteckt (`editorial_theme.py:20`), obwohl `_render_sidebar` dort "Suche läuft" schreibt; laufende Scans sind nach Seitenwechsel unsichtbar. Sieben Nav-Einträge horizontal scrollend statt fester 5er-Bottom-Nav (DESIGN.md:52-55 beschreibt sie, 0 `position:fixed` im Code). Django-Portal mit anderer Palette und Schrift, Login nur dort, App nur Deutsch, Portal DE/EN, Rücksprung hart auf `/de/`. `challenge_15k.py` 23× Euro, Daily3 und Portal CHF. Dezimaltrennzeichen gemischt ("1,95" vs. "1.82").
Fix: Ein Token-Set; Scan-Indikator in der Hauptnavigation; echte Bottom-Nav mit maximal fünf Zielen; Konto-Link im App-Header; eine Währung; ein Formatter-Modul.

**H14 – Kundenzugang opt-in statt fail-closed**
`customer_access.py:29-30`: Zugang nur erzwungen bei `BETBOY_CUSTOMER_ACCESS_REQUIRED=1`; sonst clientseitig erzeugte 128-Bit-ID (`account_identity.py:24-60`). Die Produktions-App ist heute ohne Login erreichbar.
Fix: Default fail-closed, Dev-Bypass explizit.

### MITTEL

**M1 – Fréchet-Untergrenze als Gate macht Kombis tot, Ticketwahl optimiert das falsche Ziel**
`challenge_engine.py:3973-3984` Stress über `Σp − (n−1)`; drei Legs à 0,70 → 0,10 → Mindestquote 10,3. Die Fréchet-Grenze modelliert maximal negative Abhängigkeit zwischen verschiedenen Spielen; das reale Risiko (gemeinsamer Modellfehler) ist positiv korreliert. Ticketwahl `max(joint_probability, …)` statt Log-Wachstum. Dokumentierter 10–25 %-Modus ist nicht spielbar, weil `risk_managed_ticket_stake` auf 5 % kappt.
Fix: Stress über gemeinsamen Kalibrierfehler (alle Legs um δ verschieben); Fréchet nur anzeigen; Rangfolge nach erwartetem Log-Wachstum; Doku bereinigen.

**M2 – Kein Portfolio-Kelly, Korrelation zwischen Märkten eines Spiels ignoriert**
`betting_math.py:234-239` Viertel-Kelly auf Haircut-p ist korrekt, aber nur Referenz. `selection_coherence.py:466-537` prüft logische Vereinbarkeit, nicht Korrelation (Over 2,5 und BTTS Ja desselben Spiels beide zulässig). Cross-Leg-Faktoren 0,97/0,985 sind Policy ohne Empirie.
Fix: Gemeinsame Kelly-Rechnung aus der bereits existierenden Score-Matrix (Simulation).

**M3 – Ecken/Karten: Dispersion aus 24 Beobachtungen, unabhängige Randverteilungen**
`challenge_engine.py:1640-1650` `alpha = (var − mean)/mean²` aus ≤ 24 Werten, Clip [0,03; 1,5], kein Shrinkage. Ecken beider Teams sind tendenziell negativ, Karten positiv korreliert; für Gesamtmärkte ist die Varianz der Summe falsch.
Fix: α je Liga/Familie per ML; Gesamtmärkte direkt auf der Summe modellieren.

**M4 – Joint-Kalibrierung: Zielerreichung nicht diagnostiziert, flache Extrapolation**
`football_joint_calibration.py:14-26, 64-76`: Objektiv mischt Mittelwert über ~40 Märkte mit Summe über Hunderte Atome; `prior_anchor 1.0` laut Docstring "declared design choice"; kein Residual-Zielfehler in der Diagnostik. `MarketCalibration.__call__` (`challenge_engine.py:2045-2051`) extrapoliert flach jenseits des obersten Bins, also genau im Challenge-Korridor.
Fix: Residual-Zielfehler ausgeben und als Gate nutzen; logit-lineare Extrapolation.

**M5 – Multiples Testen nur innerhalb der Liga**
BH über die ~90 Märkte einer Liga (`challenge_engine.py:2342-2396`), nicht über Ligen × Märkte, obwohl Freigaben über alle Zellen selektiert werden. Historie: Saison plus Vorsaison, also 300 bis 700 Spiele je Liga für Walk-forward, Kalibrierung (ab 100 Samples, 10 Bins) und Signifikanz gleichzeitig; kaum Power.
Fix: BH über die gesamte Familie; mindestens fünf Saisons Historie (football-data.co.uk); hierarchische Kalibrierung (Markt-global mit Liga-Offset).

**M6 – E-Sport-Elo nicht konvergiert, 25 pp Gesamtabschlag**
`esports_elo.py:20-25, 98-111`: K = 40, zwei Durchläufe über ≤ 20 Spiele je Team, Start 1500 → pfadabhängig, doppelt gezählte Form. `multi_sport_recommendations.py:853-873`: `expected_score(fav − 150) − 5 pp` → bei Gleichstand 0,50 → 0,247. `ELO_UNCERTAINTY_MARGIN = 150` ist nicht aus der Rating-Varianz abgeleitet.
Fix: Glicko/Bradley-Terry mit Unsicherheit; Haircut aus Rating-SD.

**M7 – Rote-Karte-Priors inkonsistent mit eigenen Daten und Literatur**
`red_card_impact_predictor.py:67-78`: Gegner ×1,45, Zehn-Mann ×0,40 (×0,90/0,95 zusätzlich); Gesamterwartung sinkt von 2,70 auf ≈ 2,4 Tore, während Vecer et al. 2009 / Titman et al. 2015 eine leicht steigende Gesamterwartung finden. Eigener Kommentar `:82-83` nennt 2,81 vs. 0,69 pro 100 min bei 11v10, was ×1,9 impliziert, nicht ×1,45. `actionable = False` (`:533`) ist korrekt.
Fix: Hazard-Regression mit Kontrolle für Prematch-Stärke und Spielstand.

**M8 – Persistenz zersplittert, Logging fehlt, stille Fehlerfänge**
99 `sqlite3.connect` in 64 Dateien, ~35 DB-Namen, zwei Pfad-Registries (`db_paths.py`, `runtime_paths.py`), WAL nur in drei Modulen, Migrationen pro Modul ohne Runner. 160 `except Exception` im Produktionscode, 46 mit nacktem `pass` (z. B. `app.py:3489-3490`, `:4020-4021`, `data_engine.py:35/154`); 384 `print()` gegen 28 Logger-Aufrufe.
Fix: DB-Inventar und Konsolidierung; `logging.getLogger(__name__)` je Modul, `logger.exception`; systemd-Journal als Senke.

**M9 – Hintergrund-Scans als Daemon-Threads im Streamlit-Prozess**
`scan_jobs.py:210-212` `threading.Thread(daemon=True)` mit globalem Lock, `app.py:2076` pollt alle 2 s per Fragment und löst Voll-Reruns aus (Flackern). Neustart = Scanverlust.
Fix: Scans in die vorhandenen systemd-Worker; Streamlit nur lesend.

**M10 – Dokumentation ist ein Log-Friedhof**
`TODO_AKTUELL.md` 264 KB / 87 H2-Blöcke, `PC_WECHSEL_UEBERGABE.md` 239 KB, `PROJECT_HANDBUCH.md` 128 KB mit Funktionsstand vom 21.09.; jeder neue Block erklärt alle darunter für historisch. Kein `README.md` im Root. 19 Markdown-Dateien im Root, sechs Audit-Berichte.
Fix: README plus ARCHITECTURE.md (≤ 10 Seiten: Modulkarte, DB-Inventar, Start/Test/Deploy); Logs nach `docs/changelog/`; TODO auf offene Punkte kürzen.

**M11 – UX: Informationsdichte, Schriftgrade, Kontraste, Fehlertexte**
Pro Karte 20 bis 30 Datenpunkte und bis zu vier verschachtelte Aufklapp-Ebenen (Expander → `se-market-details` → `wf-fact` → `form-opponent-row`); der Wireframe verlangte höchstens eine Ebene. Schriftgrade bis 8 px (`.se-image-credit .5rem`), Labels "MODELL"/"QUOTE" 9,3 px mobil; Muted-Text ≈ 4,7:1 (AA knapp). Rohe Exceptions als Fehlermeldung (`daily3_ui.py:194`, `tennis_tab.py:662/755`, `my_tips.py:34/43`). Englische Enums RELEASED/SHADOW/RESEARCH und Begriffe wie "3 a day keeps the job away", "Roll-over", "VS" im Nutzertext; Grossbuchstaben-Befehlston ("NICHT WETTEN:", "KNAPP — Finger weg."). Durchgehend ß statt Schweizer ss. Kein Dark Mode, Streamlit-Toolbar versteckt. Kaltstart der Produktionsseite über 10 Sekunden ("Running get_analyzer(...)").
Fix: Drei Fakten sichtbar, Rest in einem Detailbereich; 12 px Minimum; Exception-zu-Nutzertext-Mapping; zentrales Label-Mapping wie `_EVIDENCE_COPY` in `riskobet_surface.py:56-80`; Entscheidung ss/ß.

**M12 – Toter und duplizierter Code**
`alternative_markets.py` (1154 Zeilen) und `alternative_markets_improvements.py` werden von keinem Modul importiert; `betboy_v3_ml_engine.py`, `advanced_analyzer.py` (11 `except Exception`, zieht Postgres-Pfad), zwei identische 962-KB-Datenbanken im Root, 411 getrackte `.superpowers/`-Artefakte, 8 ATP-CSVs à 4–5 MB in der Historie.
Fix: Löschen oder nach `legacy/`; Daten per Download-Skript.

### NIEDRIG

- **N1** `_fixture_score`/`_is_completed_before` (`challenge_engine.py:683-697`) prüfen `goals`, nicht `status.short`; AET/PEN-Tore würden als 90-Minuten-Ergebnis zählen, abgesichert nur durch den Fetch-Filter. Status-Guard einbauen.
- **N2** Arithmetische Mittelung abhängiger Wahrscheinlichkeiten (`tennis/predict.py:212-216` Elo/Serve 0,7/0,3 im p-Raum; `advanced_analyzer.py:963`). Logit-Pooling.
- **N3** Multiplikativer De-Vig im Tennis-Backtest (`tennis/backtest.py:456-464`) verzerrt Aussenseiter-Edges nach oben. Shin/Power.
- **N4** Pickle-Laden ohne Signatur ausserhalb von Tennis (`advanced_analyzer.py:704`, `shadow_clv_automation.py:581/649/671`); `open_trusted_pickle` überall nutzen.
- **N5** Buchmacher-Realität (Limits, Kürzungen, Kontoschliessungen) nirgends adressiert; bei Skalierung relevant. Limit-Protokoll je Buchmacher im `price_ledger`.
- **N6** RisikoBet ist Heuristik (Schwellen 0,15/0,18/0,30–0,75, Multiplikatoren ×1,20/×0,45/×0,8/×0,3 in `riskobet_candidates.py:54-68, 304-441`), korrekt als Research deklariert; "vorsichtige Prognose" `p − 1,96·√(p(1−p)/n)` ist bei n = 8 praktisch immer 0.
- **N7** Formular "Externe Wette nachtragen" verlangt ISO-Zeitstempel mit Zeitzone (`daily3_ui.py:130`); für Freizeitwetter unbedienbar.
- **N8** `render_settings` (`app.py:4963-4985`, Modellvalidierung, Datenbestand) wird in `main()` nicht aufgerufen; Datenstand nur über "Stand:"-Zeitstempel sichtbar.

---

## 3. Produktionsstichprobe 16.10.2026 (eigene Beobachtung)

| Bereich | Beobachtung | Bewertung |
|---|---|---|
| Wettfinder, Karte 1 | VALORANT Vitality vs. LOUD, Sieg Vitality 52,3 %, Quote "–", "Modellstand nicht aktuell belegt" | Münzwurf ohne Evidenz als erste Auswahl |
| RisikoBet, Karte 1 | Dasselbe Spiel, Aussenseitersieg LOUD 47,7 % | Beide Seiten als Auswahl |
| Daily3 | Djurgården Team-Total Unter 2,5, 76,7 %, Quote 1,55; Kontext "veraltet/offen/nicht aktuell belegt" | 12–15 pp Abstand zum Markt, Kontext stale, Echtgeld-Reservierung möglich |
| 15K | Radnik Surdulica Team-Total Über 0,5, 76,4 %, Quote 1,27 | EV −3,0 % vor Haircut |
| Tennis | Ruud vs. Jodar, Sieg Jodar 54,6 %, Betfair 1,85; Karte widerspricht sich (Serve-Daten "eher für Ruud"); Ruuds Historie mit Monatslücken | Datenlücke, inkohärente Begründung |
| Meine Tipps / Live / Manuelle Suche | Leer ("Noch keine Tipps gemerkt", "Noch keine Live-Suche") | Leere Zustände ohne Führung |
| Rechtliches | Kein Impressum, Datenschutz, 18+, Spielsucht-Hinweis; nur Footer-Satz | Vor bezahltem Start zwingend |
| Mobile 375 px | Sieben Nav-Punkte horizontal scrollend, Karte funktioniert | Bottom-Nav fehlt |
| Ladezeit | Kaltstart > 10 s | Streamlit-Rerun-Modell |

Mindestquote nach Produktregel (3 % Risiko-ROI, Haircut aus Karte nicht sichtbar, hier 5 pp angenommen): Daily3-Pick 1,03/0,717 = 1,44 (Quote 1,55 passt), 15K-Pick 1,03/0,714 = 1,45 (Quote 1,27 passt nicht). Keine dieser Zahlen ist auf der Karte zu sehen.

---

## 4. Was gut ist

1. **Trennung Modell/Preis ist in Code und UI konsequent**: `WettfinderCard` immutable, Preis verändert nie Reihenfolge (`wettfinder_surface.py:614-645`); RisikoBet: "Der Wettpreis verändert diese Prognose nicht."
2. **Numerik und Fail-closed**: `score_matrix` mit lgamma, Tail-Toleranz, Normierung; Walk-forward mit Tagesgruppierung und Refit erst nach Tagesende (kein Leakage); HAC mit Newey-West-Bandbreite und BH-FDR korrekt implementiert; Isotonie via PAVA mit Shrinkage.
3. **Kontexteffekte werden empirisch gefittet, nicht erfunden**: Ridge-Offsets ohne Intercept, Alpha per Tune-Brier, Freigabe nur bei ≥ 200 Events, HAC-Untergrenze > 0, BH über das ganze Register; Aktivierung fail-closed (`context_models/activation.py`).
4. **Ledger-Integrität**: HMAC-Hash-Kette, SQLite-Trigger gegen Mutation abgerechneter Daten, cent-genaue Decimal-Buchführung (`challenge_store.py`, `daily3_math.py`); ausführbarer Preis statt synthetischer Bestquote (`market_consensus.py:329-343`).
5. **Deploy und Portal sind paranoid im guten Sinn**: `update_server.sh` mit Lock, Pre-Update-Backup, Byte-Manifest, Trap-Recovery, Health-Check; Portal erzwingt 48-Zeichen-Secret, HTTPS, HSTS, `compare_digest`.
6. **Testsubstanz**: 5808 Testfunktionen, Test-LOC ≈ 1,14× Produktions-LOC, 1865 `parametrize`, kaum ungeseedeter Zufall, kein ungemocktes Netz. Eigener Lauf heute: 244 Tests der Mathematik-, Kalibrier- und Settlement-Module in 20 s grün; Vollsuite laut Doku 13 781 bestanden (13.10., Linux).
7. **Ehrliche Sprache**: "kein bewiesenes Gewinnsystem", "Kein Versprechen, nur Mathematik", Verlauf inkl. Verluste, Landingpage ohne erfundene Monatsbilanz.
8. **Formchips mit Buchstabe + Resultat + Farbe**, Fokus-Ringe, 44-px-Touchziele, `aria-label` auf Karten.

---

## 5. Massnahmenplan in Reihenfolge

| # | Massnahme | Aufwand | Löst |
|---|---|---|---|
| 1 | API-Schlüssel rotieren, nur Env; Backup-Timer aktivieren, Restore-Probe | 1 Tag | K1, K6 |
| 2 | Daily3 und 15K: bekannte Quote gegen `minimum_recommendation_odds` prüfen; Kontextveto; Kandidaten unter Mindestquote als "Preis reicht nicht" | 2 Tage | K4, K5 |
| 3 | Impressum, Datenschutz, 18+, Spielsucht-Link, Kundenzugang fail-closed | 2 Tage | H11, H14 |
| 4 | Marktbenchmark-Kanal: historische Pinnacle-Closings laden, Shin/Power-No-Vig, paired Brier Modell vs. Markt, CLV-Backtest der Gate-Policy über ≥ 5 Saisons. Bis dahin kein `RELEASED`. | 1 Woche | K2, H5, H6 |
| 5 | Dixon-Coles per MLE (Angriff, Abwehr, Heimvorteil, ρ, Zeitdecay) als aktive λ-Quelle; Paritätstests | 1–2 Wochen | H1, M3 |
| 6 | Entscheidungs-p als Log-Odds-Mischung mit Markt plus Edge-Cap; Haircut aus Schätzunsicherheit | 1 Woche | K3, H2 |
| 7 | Hauptkarte: "Value ab", Status, Preisnotiz; Preisprüfung verdrahten; Sportarten ohne Evidenz aus der Standardansicht; Aussenseiter marktdefiniert | 1 Woche | H10, H12 |
| 8 | `main` synchronisieren, Worktrees und Artefakte aufräumen, README + ARCHITECTURE.md, CI mit ruff/pytest auf Linux, Lockfile | 1 Woche | H7, H8, M10 |
| 9 | Tennis: Kalibrierung auf gewetteter Population, v2 als Default, Belagsregel durch Ablation ersetzen | 1 Woche | H3, H4 |
| 10 | Domänenpaket ohne Zyklen, `run_wettfinder` und CSS zerlegen, Logging, DB-Konsolidierung | 4–8 Wochen | H9, M8, M9, M12 |
| 11 | Ein Design-System, Bottom-Nav, Portal-Verzahnung, Währung, Formatter, Glossar | 2–3 Wochen | H13, M11 |

Punkt 4 ist Voraussetzung für 5 und 6: Ohne Marktbenchmark lässt sich nicht feststellen, ob ein besseres Tormodell oder ein anderer Haircut etwas bringt.

---

## 6. Testlauf und Kennzahlen

- Gezielter Lauf (`test_ev_calculator`, `test_daily3_math`, `test_football_joint_calibration`, `test_model_loss_statistics`, `test_riskobet_settlement`, `test_calibration`): **244 passed, 19,9 s**.
- Vollsuite im Hauptcheckout (Windows, `main` @ `c5a6264` mit lokalem WIP): **67 failed, 13 643 passed, 98 skipped, 115 Subtests in 1:37:27**. Verteilung der Fehlschläge: 48 `tests/test_context_runtime_tennis_live.py`, 17 `tests/test_tennis_live_training.py`, 1 `tests/test_workflow_integrity.py`, 1 `tests/test_basketball_context.py`. Fehlerbild: 45× `ArtifactIntegrityError: context database verification failed`, 43× `original Tennis code has no supported exact replay`, 13× `original calculation has no supported exact source replay`. Alle Tennis-Fehlschläge sind code-identitätsgebundene Replay-Prüfungen; `tennis/live_context.py` und `tennis/predict.py` tragen genau hier uncommitted WIP (siehe H7). Der Reparatur-Worktree meldet laut Doku 0 Fehler; der Hauptcheckout ist damit nachweislich nicht der Stand, der deployt ist. Lauf bis zum ersten Fehler: **1 failed, 224 passed, 6 skipped in 13,8 s**; Fehlschlag `tests/test_basketball_context.py::test_frozen_default_cricket_matches_before_change_on_same_cpu` (AST-eingefrorener Golden-Test: die Funktion `_variant` in `sports_prematch.py` weicht von der eingefrorenen Legacy-Kopie ab; die beteiligten Dateien tragen keine lokalen Änderungen, der Drift ist also auf `main` @ `c5a6264` committet). Letzter dokumentierter Linux-Volllauf 13.10. im Reparatur-Worktree: 13 781 bestanden, 97 Skips, 0 Fehler. Golden-Tests über Quelltext-Hashes sind fragil (siehe H7: welcher Checkout gilt?).
- Keine `test_betting_math.py` und keine `test_esports_elo.py` als eigene Dateien; `betting_math` wird in 7, `esports_elo` in 4 Testdateien mitgetestet.

| Kennzahl | Wert |
|---|---|
| Python-LOC Root-Module | 83 623 in 145 Modulen |
| Pakete (context_models, context_storage_v2, tennis, scanners, context_sources, portal) | ≈ 40 100 LOC |
| Tests | 141 351 LOC, 393 Dateien, 5808 Funktionen |
| Grösste Module | challenge_15k 5664, challenge_store 5138, app 5063, wettfinder_automation 4632, challenge_engine 4563 |
| Längste Funktionen | `_apply_app_styles` 1507, `run_wettfinder` 1183, `ChallengeLedger._initialize` 879, `scan_daily_challenge` 758 |
| `except Exception` / mit `pass` | 160 / 46 |
| `print()` / Logger | 384 / 28 |
| Importzyklen | 14 Zwei-Zyklen, SCCs 13/7/7/7/5 |
| SQLite | 99 `connect` in 64 Dateien, ~35 DB-Namen, 10 `.db` im Root, 82 im Prod-Backup |
| Custom-CSS | ≈ 1735 Zeilen, 75 `!important`, 68 `data-testid`-Selektoren, 0 `prefers-color-scheme` |
| `unsafe_allow_html` | 24 |
| Kartendarstellungen | ≥ 6 verschiedene, 2 HTML-Familien |
| Git | 959 Commits, 56 Branches, 60 Worktrees, main 0/27 hinter origin, 12 M + 16 ??, 28 MB Garbage-Pack |
| Doku im Root | 19 .md, 630 KB in drei Logs, kein README |
| Abhängigkeiten | 13 Einträge, 1 Pin, 3 venvs, keine Lockdatei, kein CI |

---

## 7. Offene Fragen an den Autor

1. Welche Marktreferenz ist geplant (Pinnacle via The Odds API; das 500/Monat-Budget reicht nicht für Minutentakt)?
2. Ist die Daily3-Reservierung ohne EV-Gate Absicht ("nur Buchhaltung") oder Lücke? Die UI präsentiert sie als Modellauswahl.
3. Welcher `market_model_version` ist in den produktiven Tennis-Tour-States gesetzt (Doku sagt v2, Code-Default ist hold-proxy)?
4. Soll der 10–25 %-Modus der 15K bewusst tot bleiben (Cap 5 %)?
5. Gibt es irgendwo eine Auswertung "Modell-p vs. No-Vig-Konsens" über die 898 evaluierten Fixtures? Das wäre der schnellste Winner's-Curse-Test.
6. Wann wird der Hauptcheckout mit `origin/main` synchronisiert, und welche der 60 Worktrees sind noch lebendig?

---

## Anhang A – Nachrechnungen

**A1 Haircut-Wirkung** (Ziel-ROI 3 %, Abschlag 5 pp): Mindestquote = 1,03 / (p − 0,05).
p = 0,15: 10,30 (fair 6,67, +54 %) · p = 0,30: 4,12 (3,33, +24 %) · p = 0,50: 2,29 (2,00, +14 %) · p = 0,70: 1,58 (1,43, +11 %) · p = 0,85: 1,29 (1,18, +9,5 %).
Mit 8 pp Produktionshaircut: p = 0,30: 4,68 (+40 %) · p = 0,70: 1,66 (+16 %).

**A2 Daily3-Pick** Djurgården Unter 2,5 Teamtore: λ = 1,67 → P(0,1,2) = e^−1,67 · (1 + 1,67 + 1,394) = 0,188 · 4,064 = 0,764 ✓ (Karte 76,7 %, inkl. Kalibrierung). Quote 1,55 → 64,5 % implizit, ≈ 62 % no-vig → λ_Markt ≈ 2,2. Differenz 0,5 erwartete Tore.

**A3 15K-Pick** Radnik Surdulica Über 0,5: λ = 1,44 → 1 − e^−1,44 = 0,763 ✓. Quote 1,27 → 78,7 % implizit. EV = 0,764 · 1,27 − 1 = −0,030.

**A4 Additiv vs. multiplikativ**: Ligamittel 1,5; Angriff 2,2; Abwehr 2,0. Additiv (2,2 + 2,0)/2 = 2,10; multiplikativ 2,2 · 2,0 / 1,5 = 2,93. Schwach/schwach 0,9/0,8: additiv 0,85, multiplikativ 0,48.

**A5 Tiebreak-Proxy** Hold 0,85/0,75: Proxy-Punkt-p = (0,85 + 0,25)/2 = 0,55 → Tiebreak ≈ 0,65. Korrekt invertiert (Punkt-p ≈ 0,66/0,61) ≈ 0,58. Abweichung ≈ +7 pp.

**A6 15K-Ziel** 100 € → 15 000 € bei 5 % Einsatz und Quote 2,5: (1,075)^n = 150 → n = 69,3 → 70 Siege in Folge. Bei p = 0,45: 0,45^70 ≈ 6·10^−25; bei p = 0,60: 3·10^−16.

**A7 Produktionsprobe 30.09.–02.10.**: 181 Prognosen, Trefferrate 0,59, Brier 0,2128. Konstanter Prädiktor mit p = 0,59: Brier = 0,59 · 0,41 = 0,242. Relative Verbesserung ≈ 12 % gegen Klimatologie; gegen den Markt unbekannt. 11 bepreiste Tennisabrechnungen: −2,00 Einheiten.
