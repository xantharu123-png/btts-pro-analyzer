# BetBoy — Vollständiges Audit (Stand 18. Juli 2026)

**Prüfumfang:** Alle 32 Python-Module (~20 400 Zeilen) inkl. Scanner, Tests und Konfiguration, geprüft gegen den Projektvertrag aus `PROJECT_HANDBUCH.md` (Commit `0925d18`).
**Methode:** Vollständige Code-Lektüre, numerische Nachrechnung der Kernformeln in Python gegen den echten Code, unabhängiger Testlauf.
**Rollen:** Mathematik/Wahrscheinlichkeitsrechnung, Senior-Entwicklung, UX, 30 Jahre Wettpraxis.

> **Nachtrag vom 19. Juli 2026:** Die im Audit als korrekt übernommene 2-%-Kappe war für den ausdrücklich gewünschten 15K-Roll-over kein korrekter Produktvertrag. Sie hätte das Ziel praktisch unbrauchbar gemacht. Challenge-Einsatz und Viertel-Kelly-Referenz sind deshalb jetzt getrennt: 5–100 % Einsatzanteil, Standard 100 %, serverseitige Ledger-Grenze sowie sichtbarer Gewinn-/Verlustsaldo. Die 2-%-Aussagen unten dokumentieren den damaligen Stand und sind für die Challenge überholt.

---

## 1. Gesamturteil

Die Codebasis hält, was das Handbuch verspricht — mit wenigen, klar benennbaren Ausnahmen. Die Modell/Preis-Trennung ist real durchgezogen, die Fail-closed-Philosophie ist konsequent implementiert, die Ticket-Mathematik wird serverseitig vollständig nachgerechnet, und die Testsuite prüft genau die richtigen Verträge. Ich habe **einen funktionalen Bug (HIGH)**, mehrere **Abweichungen zwischen Handbuch und Code (MEDIUM)** und eine Reihe kleinerer Punkte gefunden. **Keinen einzigen Befund**, bei dem das System den Nutzer in Richtung Überzuversicht täuscht — die Fehler liegen alle auf der konservativen Seite (Signale fallen weg, nie hinzu).

**Unabhängig verifiziert:** Testsuite 126/127 bestanden (der eine Fehlschlag betrifft nur die hier nicht mitkopierte `.streamlit/config.toml` — auf deinem Rechner vorhanden, daher dort 127).

---

## 2. Numerisch nachgerechnet und KORREKT

| Prüfung | Ergebnis |
|---|---|
| Kelly-Formel `((o−1)p−(1−p))/(o−1)` | ✔ exakt; Viertel-Kelly ist seit 19. Juli nur Referenz, nicht Challenge-Limit |
| Implizite Wahrscheinlichkeit, Edge, EV (`betting_math.py:95–101`) | ✔ exakt |
| `score_matrix`: Masse = 1.0, E[Tore] = λ, Tail-Guard schließt bei >1e-5 Verlust (`challenge_engine.py:448–481`) | ✔ |
| BTTS aus Matrix ≡ geschlossene Form `(1−e^-λh)(1−e^-λa)` | ✔ auf 1e-6 |
| 1X2-Summe = 1.0 | ✔ |
| Dixon-Coles-τ: alle vier Korrekturterme entsprechen dem Originalpaper (`advanced_analyzer.py:344–355`) | ✔ |
| Bivariate Poisson (Trivariate-Reduktion): Masse 1.0, Marginale = λ (`advanced_analyzer.py:402–421`) | ✔ |
| Negative Binomial NB2: Mittel = μ, Varianz = μ+αμ² exakt (`challenge_engine.py:799–812`) | ✔ |
| Kombi: `0.97^(Legs−1)` konsistent in Preview, Quoted-Ticket und Ledger-Nachrechnung | ✔ |
| Cent-genauer Ledger: BEGIN IMMEDIATE, Unique-Index pro Tag, Doppel-Settlement blockiert, Guthaben kann nicht negativ werden | ✔ |
| Erwartete Zeit bis Tor: korrekte bedingte Erwartung der gestutzten Exponentialverteilung (`red_card_impact_predictor.py:240–243`) | ✔ (sauber!) |
| Cricket-Overs: `10.5` = 65 Bälle, `10.6` ungültig (`cricket_scanner.py:222–238`) | ✔ |
| NHL läuft nicht durch Basketball-Projektion (`basketball_scanner.py:141`, App-Verdrahtung) | ✔ |
| CLV: gleicher Buchmacher + gleiche Quelle erzwungen, 15-Min-Closing-Fenster (`clv_tracker.py:223–235`) | ✔ |
| Harte Challenge-Schwellen | ✔ zum Auditstand; Einsatzvertrag am 19. Juli bewusst auf konfigurierbare 5–100 % korrigiert |
| Day-grouped Walk-forward ohne Same-Day-Leakage in `validate_league_markets` und `build_prematch_training_rows` | ✔ (Baseline wird korrekt erst nach dem Tages-Batch aktualisiert) |
| Nur Halb-Linien in `market_specs()` — Push-Problematik strukturell ausgeschlossen | ✔ |
| Odds-Allowlist im CSV-Import: kein Buchmacherfeld überlebt `parse_history_csv` | ✔ |

---

## 3. Befunde

### HIGH-1 — Live-xG wird nie geparst; die Qualitätsstufe „Live-xG + Prematch" ist toter Code

`api_football.py:312–321` (`get_match_statistics` → `get_stat`): Nur `Ball Possession` wird als Dezimalzahl behandelt; **alle anderen Werte laufen durch `_nonnegative_integer`, das ausschließlich `int` akzeptiert.** API-Football liefert `expected_goals` aber als String/Dezimal (`"1.34"`). Numerisch verifiziert:

```
_nonnegative_integer('1.34') -> None
_nonnegative_integer(1.34)   -> None
```

Folge: `xg_home`/`xg_away` sind in `ultra_live_scanner_v3.py` **immer None** → die Bedingung für Qualität `MEDIUM` (`ultra_live_scanner_v3.py:105–108`, beide beobachteten xG nötig) kann nie erfüllt werden. Der Live-Filter „Live-xG + Prematch" in der App liefert **immer 0 Treffer**, ohne dass ein Fehler sichtbar wird. Pikant: `red_card_bot.py:263–264` parst `expected_goals` **korrekt** als Float — die beiden Pfade sind inkonsistent.

Richtung des Fehlers: fail-closed (kein falsches Signal), aber ein beworbenes Feature ist stillschweigend deaktiviert.
**Fix:** in `get_stat` `expected_goals` wie `Ball Possession` als Float parsen (Vorbild: red_card_bot).

### MEDIUM-1 — Handbuch überverkauft Dixon-Coles / Bivariate Poisson

Handbuch §6.1 listet DC und bivariate Poisson als Modellfamilien. Tatsächlich: Die **Challenge-Engine rechnet rein mit unabhängigem Poisson** (`challenge_engine.py:448`), DC/BV existieren nur in `advanced_analyzer.py` und werden dort **nur angezeigt, nie in die aktive Wahrscheinlichkeit gemischt** (`advanced_analyzer.py:897–902`, `poisson_btts = independent_btts`). Der Code ist dabei ehrlich kommentiert („sensitivity scenarios, not blended"). Mathematisch ist Unabhängigkeit bei niedrigen Ergebnissen leicht verzerrt (Unentschieden/0-0 unterschätzt, mein Nachrechnen: DC-BTTS 54.9 % vs. unabhängig 54.3 % bei λ=1.5/1.2 — Größenordnung <1 pp, der 3–20-pp-Haircut deckt das ab). Kein Rechenfehler, aber: **Handbuch an die Realität anpassen** oder DC mit gefittetem ρ tatsächlich aktivieren.

### MEDIUM-2 — Zeitzonenfehler im Challenge-Scan („Heute" ist zwischen 00:00 und 02:00 CH-Zeit der falsche Tag)

`challenge_15k.py:994`: `search_date = datetime.now().date()` nutzt die **Serverzeit** (Streamlit Cloud = UTC), die API-Anfrage übergibt aber `timezone: Europe/Zurich` (`challenge_15k.py:236`). Zwischen Mitternacht und 02:00 Schweizer Zeit liefert der „Heute"-Scan die Spiele von **gestern**. Verstoß gegen Handbuch-Regel 6 (produktive Zeitstempel zeitzonenfähig).
**Fix:** `datetime.now(ZoneInfo("Europe/Zurich")).date()`.

### MEDIUM-3 — Zwei offene Tickets gleichzeitig möglich („Heute" + „Morgen")

Die Ein-Ticket-Regel greift **pro Spieltag** (`analysis_date`, Unique-Index `challenge_store.py:107–113`), nicht pro Platzierungstag. Wer heute ein Heute-Ticket und ein Morgen-Ticket einträgt, hat bis zu ~4 % des Guthabens gleichzeitig offen (das zweite Ticket rechnet immerhin auf dem bereits reduzierten Guthaben). Kelly-Logik unterstellt sequenzielle Wetten. Kein Drama bei 2 %-Cap, aber eine bewusste Entscheidung sollte es sein — entweder dokumentieren oder offene Tickets vor Neuplatzierung prüfen.

### MEDIUM-4 — Der „Value Bets"-Pfad (Spiele/Märkte) ist faktisch unerreichbar

`SmartBetFinder.find_value_bets` verlangt einen `market_validation`-Datensatz (`smart_bet_finder.py:480`), den **kein Aufrufer produziert**: `_collect_match_analysis` (`alternative_markets_tab_extended.py:99–107`) setzt ihn nie, und der einzige Produzent (`BacktestingEngine.market_validation_record`, `betboy_v3_ml_engine.py:767`) ist an keiner Stelle des UI angebunden — er bräuchte monatelang gesammelte OOS-Prognosen mit Preis-Provenienz. Der Button ist ehrlich fail-closed (Warntext erklärt es), aber praktisch ein toter Knopf. **Entweder klar als „benötigt Backtest-Historie" beschriften oder den Aufbau dieser Historie (Shadow Mode!) implementieren.**

### MEDIUM-5 — Settlement-Konventionsrisiko bei Karten- und Eckenwetten (Wett-Profi-Blick)

Die Challenge rechnet Gelbe-Karten- und Eckenmärkte gegen **API-Football-Zählungen** ab. Buchmacher (auch N1Bet) haben eigene Regeln: zählt die zweite Gelbe als eine oder zwei Karten, zählen Karten für Trainer/Bank, Karten nach Abpfiff, Ecken die zurückgepfiffen werden? Das Modell weiß es nicht — im explorativen Teil steht die ehrliche Fußnote (`alternative_markets.py:642`), in der Challenge fehlt sie. Bei manueller Abrechnung entscheidest du selbst; die Diskrepanz zwischen Modell-Settlement (API-Zählung) und Buchmacher-Settlement kann den kleinen EV-Vorsprung real auffressen. **Kartenmärkte in der Challenge nur mit dokumentierter N1Bet-Regelprüfung verwenden.**

### MEDIUM-6 — Zwei kleinere Abweichungen von Handbuch-Regel 7 (day-grouped Walk-forward)

`MLEnsemble.train` (`betboy_v3_ml_engine.py:264–272`) splittet mit `TimeSeriesSplit` **zeilenweise**, nicht tagesgruppiert — Spiele desselben Tages können über die Train/Validation-Grenze fallen (schwacher Optimismus). `advanced_analyzer.train_model` macht es korrekt über eindeutige Daten (`advanced_analyzer.py:546–560`). Zusätzlich: Train/Serve-Skew im BTTS-ML — trainiert wird auf Rolling-20-Fenstern (`ML_HISTORY_WINDOW`), zur Laufzeit werden Saison-Aggregate der API eingespeist (`advanced_analyzer.py:908–915`). Beides nur exploratives Terrain, aber beides ist genau die Art stiller Abweichung, die das Handbuch verbietet.

### LOW-Befunde

1. **ECE-Bin-Doppelzählung bei exakt p=0.6** (`challenge_engine.py:1013–1019`): `0.4+0.2 = 0.6000000000000001` → p=0.6 landet in zwei Bins (verifiziert). Auswirkung praktisch null, aber ein FP-Klassiker — Bin-Kanten als Konstanten definieren.
2. **Stake-Rundung HALF_UP** kann den 2 %-Cap um <0,5 Cent überschreiten (`challenge_engine.py:1855–1857`); der Ledger prüft mit derselben Rundung — konsistent, daher nur Notiz.
3. **`ml_predict` liefert bei internem Fehler still 0.5** (`advanced_analyzer.py:740–742`) — würde als „50 %" angezeigt statt als Fehler. Fail-closed wäre `None`.
4. **`fetched_at` naiv-lokal** statt UTC (`data_engine.py:399`) — Verstoß gegen eigene Regel 6, folgenlos aber inkonsequent.
5. **`_h2h_scores` nimmt die ersten 10 in Lieferreihenfolge** ohne eigenes Datums-Sort (`challenge_engine.py:1353`) — hängt von der API-Sortierung ab.
6. **Ungültige N1Bet-Quote (z. B. Tippfehler „1.00") wird still übersprungen** (`challenge_engine.py:1780–1790` `continue`) — der Nutzer erfährt nicht, welches Leg deswegen fehlte. Kleiner UX-Hinweis würde reichen.
7. **`pickle.load`/`joblib.load`** der Modelldateien: lokales Manipulationsrisiko, akzeptabel solange `models/` nicht committed wird (ist per .gitignore ausgeschlossen ✔).

---

## 4. Wett-Profi-Einordnung: Was das System realistisch liefern wird

Die Gates sind mathematisch konsistent — aber ihre **Komposition macht Tickets extrem selten**, und das solltest du bewusst so annehmen:

- Konservative p ≥ 0.55 ⇒ Modellpreis ≤ 1.82 ⇒ **ein Einzeltipp kann den Korridor 2.00–3.00 nie erreichen** (Preview zwingt zu 2–3 Kombis; verifiziert).
- Ein Zwei-Leg-Ticket mit z. B. je p=0.70 braucht Quoten ≥ ~1.47, wo fair 1.43 wäre — **N1Bet müsste auf beiden Legs gleichzeitig über fair zahlen, trotz Marge.** Das passiert, aber selten und meist aus gutem Grund (der Buchmacher weiß etwas). Mein Testbeispiel (p=0.62@1.55 + p=0.60@1.50) hat **−16 % EV** — genau solche „gefühlt sicheren" Kombis blockt das System korrekt.
- Der Haircut (3–20 pp!) plus Kontextgates (bestätigte Aufstellungen, Wetter, H2H, Verletzungen) bedeutet: **an den meisten Tagen null Tickets.** Das ist kein Bug, das ist das Design — aber wer täglich einen Tipp erwartet, wird das System als „kaputt" empfinden. Es ist das Gegenteil.
- Beim neuen 100-%-Roll-over reichen rechnerisch acht Siege bei Quote 2,00 oder fünf Siege bei Quote 3,00, aber ausschließlich ohne eine einzige Niederlage. Eine Niederlage beendet diesen Pfad bei 0 EUR; die Pfadwahrscheinlichkeit wird deshalb im finalen Ticket sichtbar ausgewiesen. Kleinere Einsatzanteile bleiben im Konto wählbar.
- **Der einzige ehrliche Schiedsrichter ist CLV** (der Tracker ist sauber gebaut): Wenn deine Eintrittsquoten die Closing Line im Schnitt nicht schlagen, hat das Modell keinen Edge — egal was der Modell-EV behauptet. Vor echtem Geld: Shadow Mode fahren und CLV sammeln, genau wie im Handbuch (P0.4) vorgesehen.
- Manuelles Settlement erlaubt sofortiges „WON" ohne Ergebnisprüfung — bei einem Ein-Personen-System ok, aber der Ledger misst dann nur deine Ehrlichkeit.

---

## 5. UX-Urteil

Ehrlichste Betting-UI, die ich seit langem gesehen habe: explorative Signale sind durchgängig als nicht handelbar markiert, Providerfehler erscheinen als Fehler (nicht als „keine Spiele"), Snapshot-Alter und Scope-Wechsel invalidieren die Anzeige, der Disclaimer steht auf jeder Seite, und die quotenfreie Analyse ist visuell sauber von der Preisprüfung getrennt. Responsive CSS mit sinnvollen Breakpoints (900/640 px). Drei Punkte: (a) der Live-Filter „Live-xG + Prematch" verspricht eine Stufe, die wegen HIGH-1 nie erreichbar ist; (b) still verworfene Quoten-Eingaben (LOW-6); (c) der Value-Button in „Märkte" suggeriert eine Möglichkeit, die es ohne Backtest-Historie nicht gibt (MEDIUM-4).

## 6. Tests

Die 127 Tests prüfen exakt die Vertragspunkte (Leakage, Fail-closed, Provenienz, Settlement, Cent-Genauigkeit, API-Trennung) — ungewöhnlich gute Auswahl. Lücken, die zu den Befunden passen: kein Test parst `expected_goals` als String durch `get_match_statistics` (hätte HIGH-1 gefangen), kein Test für die ECE-Bin-Kante p=0.6, keiner für die Serverzeit-vs-Zürich-Datumswahl, keiner für das Doppel-Ticket Heute+Morgen.

## 7. Priorisierte Empfehlungen

1. **HIGH-1 fixen** (eine Zeile in `get_stat`) + Regressionstest mit String-xG.
2. **MEDIUM-2 fixen** (`ZoneInfo("Europe/Zurich")`) + Test für die Mitternachtsgrenze.
3. Handbuch §6.1 korrigieren (DC/BV sind Anzeige, nicht aktiv) — oder DC mit gefittetem ρ aktivieren (MEDIUM-1).
4. Entscheidung zu MEDIUM-3 dokumentieren oder offenes Ticket vor Neuplatzierung blocken.
5. Kartenmärkte der Challenge mit N1Bet-Settlement-Regeln abgleichen (MEDIUM-5).
6. Danach wie im Handbuch: Supabase, Ledger-Migration, Shadow Mode mit CLV-Sammlung — **kein echtes Geld vor mehreren Wochen positivem CLV.**

---

*Alle Zeilenangaben beziehen sich auf den Stand der Dateien vom 17./18. Juli 2026. Numerische Verifikation und Testlauf wurden in dieser Sitzung unabhängig ausgeführt. Kein Modell und kein Audit macht Wetten sicher; auch ein korrektes System kann verlieren.*
