# BetBoy Audit-Bericht — 30.07.2026

Scope: Vollständiger Umbau (BTTS-App → BetBoy-Wettplattform), 6 neue Ligen,
Live-Wettfinder-Reparatur, intensives Fach-Audit (Mathematik, Wahrscheinlichkeit,
Logik, Wettprofi-Logik, UX). Suite: **327/327 Tests grün.**

---

## 1. Umbau (Phasen 0–3, abgeschlossen)

| Phase | Ergebnis |
|---|---|
| 0 Branding | Sichtbare App-Identität durchgehend „BetBoy" (Tab „Spiele Wettfinder", page_title war bereits BetBoy); Marktname „BTTS" bleibt als Wettmarkt korrekt bestehen |
| 1 Struktur | `smart_bet_finder.py`, `best_bet_finder.py`, `ultra_live_scanner_v3.py` per `git mv` nach `scanners/`; Root-Shims mit Re-Exports — keine Import-Brüche |
| 2 Namen | `btts_pro_app.py` → `app.py` (Shim leitet alte Startbefehle per `runpy` um; Tests importieren kanonisch `app`). `btts_data.db` → `betboy_data.db` über `db_paths.ensure_primary_db()` — **Kopie statt Verschieben**, Zeilenzahlen verifiziert identisch (3 299 Matches, 176 Teams), alte Datei bleibt Backup |
| 3 Ordner | `btts-pro-analyzer` → `betboy-app`; 12 Dateien mit harten Pfaden aktualisiert, Windows-Aufgabe „BetBoy Tennis Daily" neu registriert (nächster Lauf 31.07. 07:17), Kimi-Automation-Entry korrigiert, stale `.pyc`-Caches geleert (Alter Pfad in `co_filename` brach `inspect.getsource`) |

## 2. Ligen: 44 → 50

Neu (IDs live gegen `/leagues` verifiziert): SWE2 Superettan (114), NOR2 1. Division (104),
DEN2 1. Division (120), IS1 Úrvalsdeild (164), FIN1 Veikkausliiga (244), FIN2 Ykkönen (245).
UEFA CL/EL/ECL-**Qualifikation läuft bereits** unter den vorhandenen IDs 2/3/848
(live geprüft: 76/44/152 Fixtures Juli/August). Saison-Modi (Kalenderjahr vs. Rollover)
korrekt gesetzt und per Test abgesichert.

**Coverage-Befund (ehrlich):** Fixture-Statistiken/xG liefert der Provider für die neuen
2. Ligen praktisch nicht (getestet: Superettan ~50 %, NOR2/DEN2/IS1 ~0 %). Scanner und
Quoten laufen trotzdem (Fixtures + Quoten vorhanden); das Modell nutzt dort
Tormodell/Form statt xG — konservativer, aber ehrlich.

## 3. Live-Wettfinder repariert

**Befund (Nutzer-Screenshot):** „Kein Live-Spiel erfüllt Filter" bei ~30+ Live-Spielen,
plus irreführende Warnung „both teams are required" (das ist schlicht fehlende
Provider-Coverage für eine einzelne Partie, kein Fehler).

**Ursachen:** (a) Kein Board — nur Gate-Passanten sichtbar; (b) Einzel-Fixture-Fehler
als globale Warnung; (c) kein Fortschritt während des ~1-minütigen Scans.

**Fixes:**
- **Live-Überblick:** Tabelle ALLER unterstützten Live-Spiele (Spiel, Liga, Stand,
  Minute, BTTS %, Ü 2,5 %, Markt-Signal %, Datenqualität), sortiert nach
  Signalstärke; immer sichtbar, auch bei null Kandidaten (dann aufgeklappt).
- Fortschrittsbalken während des Scans; Zähler „ohne gültigen Spielstand".
- Provider-Hinweis aggregiert („x von y ohne Live-Statistik") statt Einzelfehler.
- **Echttest gegen die API:** 35 Live-Spiele global, 29 in unseren Ligen,
  12/12 Stichprobe fehlerfrei analysiert.

**Unverändert (Wettprofi-Disziplin):** Die Wett-Gates bleiben strikt — das Board zeigt
Analysen, die Empfehlung bleibt „nur wenn alles passt". Live-Wetten sind **nicht**
„sicherer" — sie sind schneller; das Modell bestraft dünne Datenbasis (LOW-Qualität)
konsequent über Haircuts.

## 4. Mathematik-Audit (Zeile für Zeile)

| Modul | Prüfung | Ergebnis |
|---|---|---|
| `betting_math.evaluate_market_price` | implied prob = 1/q ✓; Edge = p − 1/q ✓; EV = p·q − 1 ✓; Kelly = (b·p − q)/b ✓; ¼-Kelly, Cap 2 % Bankroll ✓; negative Kelly → 0 ✓ | **korrekt** |
| `challenge_engine.score_matrix` | Poisson-PMF in Log-Raum (lgamma) ✓; λ=0-Sonderfall ✓; Tail-Massen-Wächter + Renormierung ✓ | **korrekt** |
| `_negative_binomial_pmf` (Ecken/Karten) | α = (Var−μ)/μ² (Momentenschätzer) ✓, NB2-PMF ✓, Clamp [0,03; 1,5] ✓ | **korrekt** |
| `_shrunk_mean` | Empirical-Bayes-Shrinkage (Prior 3–4 Spiele) ✓ | **korrekt** |
| Kalibrierung | ECE auf Quantil-Bins (korrekter Schätzer bei schmalem p-Bereich), Isoton/linear interpoliert, pro Markt | **korrekt** |
| `_minimum_market_odds` | Mindestquote = max(Edge-Preis 1/(p−0,04), ROI-Preis (1+r)/p), aufgerundet → beide Gates erfüllt | **korrekt + streng** |
| `evaluate_candidate_price` | Dreifach-Gate (4 pp Edge + 3 % EV + Mindestquote) + Kelly > 0, alles auf risikoadjustierte p | **korrekt** |
| Kandidaten-Mathematik | konservativ = min(aktiv, Saison, Form) − Haircut (max(strukturell, Kalibrierungsfehler), Cap 20 pp); Preisvergleich gegen konservativste Schätzung | **wettprofi-sauber** |

**Dokumentierter Designpunkt (kein Fehler):** Zwei Edge-Einheiten koexistieren —
Fußball/Multi-Sport: **4 Prozentpunkte absolut** (nach teils 20-pp-Haircut, also de
facto sehr streng); Tennis: **15 % relativ** (Shadow-Phase). Beide sind in der UI
gelabelt; für den Nutzer gilt: Einheiten nicht vergleichen.

**Unabhängige-Poisson-Annahme:** leichte Untergewichtung von 0:0/1:1 möglich;
durch ligenweise Kalibrierung aufgefangen (Walk-forward-Gate würde Drift melden).

## 5. Logik-Audit

- Saison-Logik: Kalenderjahr vs. Rollover-Monat pro Liga, tests abgesichert ✓
- Dedupe: `already_stored` (Match-Datum+Paarung), doppelte Provider-Fixtures verworfen ✓
- Gates: Diversifikation (max. 2 Kandidaten/Fixture), Vertrags-Revalidierung bei
  Selektion (`candidate_is_credible`), Verletzungs-Gate (fehlend=1, fraglich=0,5,
  Schwellen 5/3) ✓
- Aufgabe-Regel N1Bet: „1 Satz" ist **Annahme** — AGB-Check steht noch aus (User).

## 6. UX-Abnahme

- Leere Fehlerseiten abgeschafft (Live-Überblick, Board statt Sperrbildschirm) ✓
- Einheitliche Sprache: ein Verdikt pro Karte, Gründe in Alltagssprache
  (test_ux_rendering deckt das ab) ✓
- Navigation: Sportart/Markt-Struktur (Spiele · Märkte · Live · 15K · Multi-Sport ·
  Tennis · System) ✓
- Slider „Max. geprüfte Spiele" entfernt: ALLE Spiele werden modelliert (lokal,
  kostenlos); teure Kontext-Checks bleiben gedeckelt (MAX_CONTEXT_FIXTURES=8) ✓

## 7. Offene Punkte (bewusst)

1. N1Bet-Aufgaberegel aus den AGB bestätigen (Annahme in Tennis-Empfehlungen).
2. Tennis-Abstract-Lizenz (CC BY-NC-SA) vor kommerzieller Vermarktung klären.
3. Live-xG-Coverage kleiner Ligen ist Provider-Limit — kein App-Fehler; Board macht
   das jetzt transparent statt es zu verstecken.
4. Streamlit-Cloud-Deployment (Live-URL) nutzt weiterhin den alten Repo-Namen —
   Umbenennung auf GitHub wäre separater Schritt (Remote + Secrets).
