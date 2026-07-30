# BetBoy — Folge-Audit (Stand 24. Juli 2026)

**Prüfumfang:** Änderungen seit dem Audit vom 18. Juli 2026 (Commit `0925d18` → `f05e2bf`, 17 Commits, +6 158/−1 305 Zeilen in 31 Dateien), mit Schwerpunkt auf der neuen Multi-Sport-Engine (`multi_sport_recommendations.py`), den neuen Wettfinder-Pfaden (`football_recommendations.py`, `bet_finder_candidates.py`, `bet_finder_ui.py`) und der Nachkontrolle aller offenen Befunde vom 18. Juli.
**Methode:** Code-Lektüre der geänderten Module, unabhängige numerische Nachrechnung der neuen Kernformeln in Python, vollständiger Testlauf, Git-/Secrets-Prüfung.
**Rollen:** Mathematik/Wahrscheinlichkeitsrechnung, Senior-Entwicklung, UX, 50 Jahre Wettpraxis.

---

## 1. Gesamturteil

Die Entwicklung seit dem 18. Juli ist die seltene Art von Feature-Ausbau, die das Risikoprofil **nicht** verschlechtert: Die neue Multi-Sport-Engine (Basketball, NHL, E-Sport) ist mathematisch korrekt implementiert, durchgängig fail-closed und hält die eiserne Regel „Modell zuerst, Buchmacherpreis danach" ohne Ausnahme ein. **Alle drei funktionalen Befunde des letzten Audits (HIGH-1, MEDIUM-2, MEDIUM-3) sind sauber behoben**, dazu MEDIUM-6 und drei der vier LOW-Punkte. Die Testsuite wuchs von 127 auf 190 Tests — und die neuen Tests decken genau die Stellen ab, die zuletzt gebrochen waren. Ich habe **keinen neuen HIGH- oder MEDIUM-Befund** gefunden, nur kleinere Punkte.

**Unabhängig verifiziert:** 190/190 Tests bestanden (34,5 s, Projekt-Test-venv).

---

## 2. Nachkontrolle der Befunde vom 18. Juli

| Befund | Status | Verifikation |
|---|---|---|
| HIGH-1 — Live-xG nie geparst | ✔ **behoben** | `api_football.py:320–324` parst `expected_goals` jetzt als Float mit Obergrenze 20, inkl. Kommentar, warum Int-Parsing das Feature still tötete. Der Qualitätspfad `MEDIUM` in `ultra_live_scanner_v3.py:184–187` ist damit erreichbar. |
| MEDIUM-2 — „Heute" nach Serverzeit | ✔ **behoben** | `challenge_15k.py:41–57` leitet das Suchdatum aus `ZoneInfo("Europe/Zurich")` ab, identisch zur Provider-Zeitzone. |
| MEDIUM-3 — Zwei offene Tickets parallel | ✔ **behoben** | `challenge_store.py:375–383` blockt jede Neuplatzierung, solange ein Ticket `PENDING` ist — innerhalb von `BEGIN IMMEDIATE`, also race-sicher. Begründung im Code korrekt: Roll-over-Sizing setzt sequenzielle Wetten voraus. |
| MEDIUM-6 — Zeilenweiser TimeSeriesSplit | ✔ **behoben** | `betboy_v3_ml_engine.py:260–302` nutzt tagesgruppierte Expanding-Window-Folds plus einen unberührten finalen Holdout an einer Kalendertags-Grenze. |
| LOW-1 — ECE-Bin-Doppelzählung p=0.6 | ✔ **behoben** | `challenge_engine.py:1017–1018` definiert Bin-Kanten als Konstanten, mit Kommentar zum FP-Problem. |
| LOW-2 — Stake-Rundung HALF_UP über Cap | ✔ **behoben** | `challenge_engine.py:1887–1889` rundet den Einsatz mit `ROUND_FLOOR` auf ganze Cents — der konfigurierte Anteil kann nicht mehr überschritten werden. |
| LOW-3 — `ml_predict` still 0.5 bei Fehler | ✔ **behoben** | `advanced_analyzer.py:723–735` liefert jetzt `None` mit Docstring-Begründung; Aufrufer fallen explizit zurück. |
| MEDIUM-1 — Handbuch überverkauft DC/BV | offen (Doku) | Kosmetik im Handbuch; Code ist weiterhin ehrlich („sensitivity, not blended"). |
| MEDIUM-4 — Value-Pfad braucht Backtest-Historie | offen (by design) | Der Knopf ist ehrlich beschriftet; die Shadow-Mode-Historie ist der vereinbarte nächste Schritt. |
| MEDIUM-5 — Settlement-Konvention Karten/Ecken | offen (Wettpraxis) | Weiterhin vor echtem Geld mit den N1Bet-Regeln abgleichen. |
| LOW-4 — `fetched_at` naiv-lokal | offen (folgenlos) | — |
| LOW-5 — H2H-Sortierung von API-Reihenfolge abhängig | offen (geringes Risiko) | — |
| LOW-6 — Ungültige Quote still übersprungen | offen (UX-Hinweis fehlt) | — |

---

## 3. Numerisch nachgerechnet und KORREKT (neuer Code)

| Prüfung | Ergebnis |
|---|---|
| Gamma-Poisson-Posterior (Basketball/NHL): Shape/Rate-Update, predictive `nbinom.sf(m−1, shape, rate/(rate+r))` | ✔ gegen direkten scipy-Aufruf auf 1e-4 identisch |
| Benötigte Restpunkte `floor(Linie − Stand) + 1` bei x,5-Linien; bereits überschrittene Linie → 1.0; Restzeit 0 → 0.0 | ✔ exakt |
| Serien-Rekursion `_series_win_probability`: BO3 p=0,6 → 0,648; BO5 0:1 hinten p=0,5 → 0,3125 | ✔ exakt (klassische Werte) |
| Inversion Serie→Map per Bisektion (0,648 → 0,600) | ✔ exakt |
| `_minimum_market_odds`: `max(1/(p−e), (1+roi)/p)`, aufgerundet auf 2 Dezimalen → Gates Edge ≥ 4 pp und EV ≥ 3 % konsistent | ✔ (p=55 % → 1,97; 60 % → 1,79; 70 % → 1,52) |
| Preisgate `evaluate_candidate_price`: Quote unter Mindestquote → NO_BET mit Grund; Quote auf Mindestquote → BET mit Viertel-Kelly, Cap 2 %, Cent-Betrag | ✔ Ende-zu-Ende getestet |
| Empirical-Bayes-Shrinkage im Live-Scanner: `(Prior-Rate·Pseudo-Minuten + beobachtetes xG) / (Pseudo-Minuten + Minute)` | ✔ sauber; Qualitätsstufen MEDIUM/LOW/INSUFFICIENT fail-closed, Platzverweis ohne Modellunterstützung → INSUFFICIENT |
| Tennis/Cricket: immer NO_BET mit ehrlicher Begründung (Datenlage reicht nicht) | ✔ vorbildlich |
| E-Sport: Laplace-geglättete Raten, konservative 10/90-%-Beta-Grenzen + 5 pp Extraabschlag | ✔ sehr defensiv, korrekt umgesetzt |
| Preis-Validierung: Komma-Dezimal, Bestätigungs-Checkbox Pflicht, `evaluate_market_price`-Fehler → NO_BET statt Crash | ✔ |

---

## 4. Neue Befunde (alle LOW)

1. **„Modell 100,0 %" ist anzeigbar.** Bei fast sicheren Live-Lagen (z. B. Basketball-Über mit 155 Punkten nach 27,5 Min, Linie 200,5) liefert das Modell 99,99… %, gerundet `100,0 %` (gerundete Fair-Quote 1,00). Mathematisch ist nichts 100 % — genau die Late-Game-Totals sind die Märkte, in denen Buchmacher Fehler in den Eingangsdaten (Uhr, Punktestand) teuer machen. **Fix:** Anzeige bei ≥ 99,5 % als „> 99,5 %" kappen und/oder für Modellwahrscheinlichkeiten ≥ 97 % einen zusätzlichen Hinweis „Eingangsdaten-Risiko dominiert" zeigen. (_candidate, `multi_sport_recommendations.py:117–141`)
2. **Preisgate-Formular existiert zweimal.** `bet_finder_ui.render_price_decision` und die Inline-Variante in `btts_pro_app.py:2010 ff.` sind nahezu identisch. Zwei Stellen für dieselbe Sicherheitslogik = doppelte Wartungsfläche für genau den Code, der nie divergieren darf. **Fix:** Multi-Sport auf `render_price_decision` umstellen.
3. **Housekeeping im Repo:** `Backup/`, `Backups 18.01. Red Card/`, `.codex_test_venv/` und leere Marker-Dateien (`packages.txt`, `__init__.py` im Root) liegen im Arbeitsverzeichnis bzw. teils im Repo-Radius. Kein Sicherheitsproblem (Secrets geprüft, s. u.), aber Ablagefrage.
4. **N1Bet-Linien-Eingabe ohne eigene Bestätigung (Multi-Sport).** Die x,5-Linie tippt der Nutzer manuell; ein Tippfehler verändert die Modellwahrscheinlichkeit selbst (anders als ein Quoten-Tippfehler, den die Gates abfangen). Die Bestätigungs-Checkbox nennt zwar die Auswahl inkl. Linie im Wortlaut — das federt es weitgehend ab; ein explizites „Linie mit N1Bet abgeglichen" wäre die konsequente Krönung.

---

## 5. Sicherheit & Betrieb

- `config.ini` (mit echten Keys) ist per `.gitignore` ausgeschlossen und nicht im Index — geprüft via `git check-ignore` und `git ls-files`. Nur `config.ini.example` und `.streamlit/secrets.example.toml` sind versioniert. ✔
- Keine Secrets in den seit dem 18. Juli geänderten Dateien gefunden.
- `pickle`/`joblib`-Modellladen bleibt ein lokales Risiko; `models/` ist weiterhin ignoriert. ✔
- E-Sport ohne PandaScore-Key: eigener, früher NO_BET-Fehler in der UI statt stillem Leerbild (`btts_pro_app.py:1933–1937`). ✔
- Provider-Teilfehler werden als Warnung mit Fehlertabelle angezeigt, nicht als „keine Spiele". ✔

---

## 6. Wett-Profi-Einordnung der neuen Märkte

- **Basketball/NHL-Gamma-Poisson** ist ein solides Standardgerüst für Live-Totals — aber es erbt die übliche Schwäche: Es kennt keine Foulsituation, keine Garbage-Time-Substitution, kein Empty-Net-Taktikverhalten. Die Haircuts (8–10 pp + Zuschläge) sind dafür großzügig bemessen, und die harten Gates (keine Bewertung in OT, Mindestspielzeit, Linie muss über dem Stand liegen) schließen die gefährlichsten Lagen aus. Die Liga-Priors (NBA 231,4; NHL 6,2) sind neutrale Mittelwerte — bewusst konservativ gewählt und als solche dokumentiert.
- **E-Sport Beta-Bradley-Terry** auf öffentlichen Sieg-/Matchzahlen ist ehrlich als schwaches Modell deklariert und mit drei konservativen Stufen versehen (Laplace, 10/90-Beta-Grenzen, +5 pp). Mehr ist aus diesen Daten nicht herauszuholen — gut so.
- **Die unbequeme Wahrheit bleibt:** Auch mit der Multi-Sport-Erweiterung gilt das CLV-Urteil vom 18. Juli. Drei neue Sportarten heißt drei neue Wege, sich ohne Preisdisziplin zu ruinieren — die Architektur (Modell ohne Preis, Preisgate danach, 2-%-Cap) ist genau die richtige Antwort darauf. Erst mehrere Wochen positiver CLV rechtfertigen echtes Geld.

---

## 7. UX-Urteil (neue Oberflächen)

Die Wettfinder-Sprache bleibt konsequent ehrlich: „NICHT WETTEN" ist ein erstklassiges Ergebnis mit begründeter Blocker-Liste, nicht ein Fehlerzustand. Snapshot-Zeitstempel, Ereigniszahl, Filter und Quellen stehen über jeder Entscheidung; veraltete Snapshots (> 3 Min Multi-Sport, > 2 Min Live-Fußball, > 6 h Prematch) sind harte Gates. Die Seitennamen wurden konsequent auf „Wettfinder" umgestellt — die App sagt jetzt in jedem Titel, was sie tut. Zwei Abzüge: die „100,0 %"-Anzeige (Befund 1) und die doppelte Preisgate-Implementierung (Befund 2, Wartungs-UX). Tennis/Cricket als wählbare, aber immer blockierte Sportarten sind grenzwertig — die ehrliche Blocker-Begründung rettet es, ein „(im Aufbau)"-Label wäre noch klarer.

---

## 8. Tests

190/190 bestanden. Die neuen Suiten (`test_multi_sport_recommendations.py`, `test_football_recommendations.py`, `test_audit_fixes.py`, erweiterte `test_workflow_integrity.py`) prüfen genau die richtigen Verträge: Halblinien-Pflicht, Fail-closed-Pfade, Snapshot-Frische, Preisgate-Grenzen, Zeitzonen-Datumswahl, Ein-Ticket-Regel. Verbleibende Lücke, passend zu Befund 1: kein Test für die Anzeige-/Rundungskante bei p ≥ 99,5 %.

## 9. Priorisierte Empfehlungen

1. Anzeige-Kappe für Modellwahrscheinlichkeiten ≥ 99,5 % + Regressionstest (Befund 1).
2. Multi-Sport-Preisformular auf `render_price_decision` vereinheitlichen (Befund 2).
3. Offene Alt-Befunde abarbeiten: Handbuch §6.1 (MEDIUM-1), N1Bet-Settlement-Regeln für Karten/Ecken (MEDIUM-5), LOW-4/5/6.
4. Danach unverändert: Shadow Mode mit CLV-Sammlung über mehrere Wochen — **kein echtes Geld vor positivem CLV**, jetzt inklusive der drei neuen Sportarten.

---

*Alle Zeilenangaben beziehen sich auf den Stand vom 20./24. Juli 2026 (HEAD `f05e2bf`). Numerische Verifikation und Testlauf wurden in dieser Sitzung unabhängig ausgeführt. Kein Modell und kein Audit macht Wetten sicher; auch ein korrektes System kann verlieren.*

---

## Nachtrag vom 24. Juli 2026 (14:30) — Vollverifikation & alle Fixes umgesetzt

### Vollständige Nachrechnung aller Rechenkerne (in dieser Sitzung, unabhängig)

| Kern | Ergebnis |
|---|---|
| `score_matrix`: Masse = 1,0; E[Tore] = λ für λ = (1,5/1,2), (2,8/0,4), (0,2/3,5) | ✔ exakt |
| BTTS aus Matrix ≡ geschlossene Form `(1−e^−λh)(1−e^−λa)` | ✔ auf 1e-9 |
| 1X2-Summe = 1,0 | ✔ |
| Negative Binomial NB2: Masse 1,0, Mittel = μ, Varianz = μ+αμ² (μ=2,5/α=0,15 und μ=1,1/α=0,4) | ✔ exakt |
| Dixon-Coles-τ (4 Korrekturterme + Fallback 1,0) ≡ Originalpaper; ρ-Guard [−0,3; 0,3] | ✔ |
| Bivariate Poisson (Trivariate-Reduktion): Masse 1,0, Marginale = λ, Kovarianz = konfiguriert | ✔ exakt |
| Platzverweis-Modell: konkurrierende Poisson-Raten (Aufteilung „nächstes Tor") und E[T \| T ≤ Rest] der gestutzten Exponentialverteilung | ✔ exakt |
| Live-Shrinkage Grenzfälle: Minute 0 mit Prior → voller Prior/LOW; Minute < 15 ohne Prior → INSUFFICIENT; keine Daten → INSUFFICIENT; Minute 94 → ValueError | ✔ |
| `consecutive_wins_to_target`: minimal verifiziert (8 Siege @2,00; 5 @3,00; 13 @2,00 mit 50-%-Einsatz) | ✔ |
| Gamma-Poisson-Predictive (NBA/NHL), Serien-Rekursion, Bisektions-Inversion, Mindestquoten | ✔ (siehe Abschnitt 3) |

### Umgesetzte Fixes (Testsuite: 191/191 bestanden)

1. **Anzeigekappe ≥ 99,5 %** (`multi_sport_recommendations.py`): `format_probability_percent` / `format_fair_odds` zeigen „> 99,5 %" bzw. „< 1,005" statt gerundeter 100,0 %/1,000; Kandidaten ab 97 % Modellwahrscheinlichkeit erhalten automatisch den Evidenzhinweis, dass Eingangsdaten-Risiko dominiert. Beide Anzeigepfade (`bet_finder_ui`, Multi-Sport) nutzen die Helfer. Regressionstest in `test_multi_sport_recommendations.py`.
2. **Preisgate vereinheitlicht** (`btts_pro_app.py`): Die duplizierte Inline-Implementierung im Multi-Sport-Tab ist ersetzt durch `render_price_decision` — die Sicherheitslogik existiert nur noch einmal.
3. **Linien-Bestätigung** (`btts_pro_app.py`): Basketball-/NHL-Linie muss jetzt explizit als „mit N1Bet abgeglichen" bestätigt werden, bevor der Kandidat gebaut wird (Tippfehler in der Linie verändert die Modellwahrscheinlichkeit selbst).
4. **Handbuch 5.2 präzisiert**: aktive Wahrscheinlichkeiten = unabhängiges Poisson mit Shrinkage; DC/BV nur angezeigte Sensitivität (§6.1 stimmte bereits).

### Bei der Umstellung als bereits behoben festgestellt

- LOW-4 (`fetched_at`): nutzt jetzt `datetime.now(timezone.utc)` (`data_engine.py:399`).
- LOW-5 (H2H): wird nach Datum absteigend sortiert, bevor die letzten 10 genommen werden (`challenge_engine.py:1338–1343`).
- LOW-6 (ungültige Quote): wird mit Warnung und Nennung des Marktes angezeigt statt still übersprungen (`challenge_15k.py:1004–1009`).
- MEDIUM-1 (Handbuch DC/BV): §6.1 war bereits korrigiert.

**Offen bleiben bewusst nur:** MEDIUM-4 (Shadow-Mode/Backtest-Historie für den Value-Pfad — geplanter nächster Schritt) und MEDIUM-5 (N1Bet-Settlement-Regeln für Karten/Ecken abgleichen — manuelle Prüfung vor Echtgeld).
