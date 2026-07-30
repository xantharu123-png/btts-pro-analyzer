# BetBoy Umbau-Plan — Von der BTTS-App zur Wettplattform

Stand: 30.07.2026 · Status: **UMGESETZT am 30.07.2026** (Phasen 0–3 abgeschlossen,
Suite 327/327 grün; Details im AUDIT_BERICHT_2026-07-30.md)

## Warum umbauen?

Die App ist faktisch längst keine BTTS-App mehr: **50 Fußball-Ligen** inkl. skandinavischer
1./2. Ligen und Finnland, UEFA CL/EL/ECL inkl. Qualifikation, **Tennis-Modul** (ATP live,
WTA Shadow), 15k-Challenge, Ultra-Live-Scanner, Red-Card-Bot, alternative Märkte
(Ecken/Karten), xG-Engine, CLV-Tracking, Kalibrierungs-Wächter. Name und Struktur sagen
aber noch „BTTS Pro Analyzer" — das verwirrt Nutzer und bremst jede Vermarktung.

## Leitplanken

1. **Kein Big Bang.** Kleine, einzeln testbare Schritte — nach jedem Schritt läuft die
   komplette Suite (aktuell 327 Tests).
2. **Datenbestand ist heilig:** SQLite-DBs, Shadow-Tracking, Kalibrierungen und der
   xG-Cache werden nie gelöscht, nur migriert (mit Fallback auf die alte Datei).
3. **Automatisierung darf nicht brechen:** Windows-Aufgabe „BetBoy Tennis Daily" (07:17)
   und deaktivierte Kimi-Automationen enthalten harte Pfade — sie werden bei jedem
   Pfad-Umzug am selben Tag nachgezogen.

## Phase 0 — Branding in der UI (risikolos, sofort)

- App-Titel, Header, Sidebar, Tab-Namen: durchgehend **„BetBoy"**, Begriffe wie
  „BTTS Pro" verschwinden aus sichtbaren Texten.
- Sidebar/Navigation nach **Sportart → Markt** ordnen (Fußball · Tennis · Live ·
  Challenge · Tracking), nicht nach gewachsenen Modulnamen.
- `PROJECT_HANDBUCH.md` und Doku-Texte angleichen.
- **Keine** Datei- oder Ordnernamen ändern sich. Aufwand: klein.

## Phase 1 — Struktur bündeln (geringes Risiko)

- `scanners/`-Ordner konsequent nutzen: `ultra_live_scanner_v3.py`, `smart_bet_finder.py`,
  `best_bet_finder.py` dorthin verschieben, kleine Import-Shims im Root hinterlassen.
- Schichten im Handbuch festschreiben:
  **data** (api_football, football_data_history, xg_backfill) →
  **model** (betboy_v3_ml_engine, challenge_engine, tennis/) →
  **gates** (Kalibrierung, Kontext) → **ui** (app + *_tab.py).
- `config.ini.example` und Handbuch spiegeln die Schichten.

## Phase 2 — Namen angleichen (mittleres Risiko)

- `btts_pro_app.py` → `app.py` (Streamlit-Start + alle Verweise; Shim-Datei mit
  Deprecation für eine Übergangszeit).
- `btts_data.db` → `betboy_data.db` per **Migrations-Skript** (liest alt, schreibt neu,
  verifiziert Zeilenzahlen; alter Pfad bleibt als Fallback lesbar).
- Nach jeder einzelnen Umbenennung: Suite laufen lassen. Aufwand: mittel.

## Phase 3 — Ordner/Repo (höheres Risiko, nur geplant)

- Ordner `btts-pro-analyzer` → `betboy-app`.
- **Achtung harte Pfade:** `run_daily.bat`, `register_daily_task.ps1`, die
  Windows-Aufgabe und die deaktivierten Kimi-Automationen → am selben Tag
  neu registrieren/zeigen lassen, sonst läuft der 07:17-Scan ins Leere.
- Git: `git mv` (Historie bleibt), Remote ggf. umbenennen.

## Offene Punkte vor Vermarktung

- **Tennis-Abstract-Lizenz (CC BY-NC-SA):** WTA-Boxscores dürfen nicht kommerziell
  genutzt werden — vor jeder bezahlten Vermarktung Lizenz klären oder Quelle ersetzen.
- **N1Bet-Aufgaberegel** aus den AGB verifizieren (Annahme „1 Satz = Wette gilt" steht
  so in den Empfehlungen).
- Finaler Markenname „BetBoy" bestätigen? Logo/Farben aus dem UX-Audit übernehmen?
