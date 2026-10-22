# Vertragsänderung 23.10.2026: Frischeregel der Öffnungsquote im CLV-Ledger

Owner-Entscheidung vom 23.10.2026 nach dem Befund `docs/audits/2026-10-22-shadow-befund.md`.
Betroffen ist der Evidenzvertrag des Shadow-/CLV-Ledgers (`clv_tracker.CLVTracker`), nicht
die Modellmathematik, nicht die Preisfreigabe und kein Echtgeldpfad.

## Vorher (bis 22.10.2026, Policy `shadow-model-first-v5`)

- Eine Öffnungsquote galt nur als Evidenz, wenn ihr Provider-Zeitstempel (`update` der
  Bet365-Antwort) höchstens **zehn Minuten** vor dem Ledger-Zeitpunkt lag
  (`OPENING_QUOTE_MAX_AGE`). Ältere Stempel wurden verworfen, das Spiel bis 30 Minuten vor
  Anpfiff erneut versucht und dann ohne Eintrag abgehakt.
- Wirkung: API-Football aktualisiert Vorab-Quoten deutlich seltener als alle zehn Minuten.
  Seit dem 1.9.2026 wurden zwei Tipps protokolliert, obwohl rund 950 Spiele bewertet wurden;
  am 17./18.10. scheiterte jeder Versuch mit „keine aktuelle Bet365-Quote mit Providerzeit“.

## Nachher (ab 23.10.2026, Policy `shadow-model-first-v6`)

- Der Provider-Zeitstempel darf bis zu **drei Stunden** vor dem Ledger-Zeitpunkt liegen
  (`CLVTracker.OPENING_QUOTE_MAX_AGE = 3 h`; der alte Wert bleibt als
  `OPENING_QUOTE_MAX_AGE_V1` dokumentiert). Unverändert: Stempel aus der Zukunft, Quoten ohne
  Providerzeit und Quoten nach Anpfiff bleiben keine Evidenz; Buchmacher und Quelle von
  Öffnungs- und Schlussquote müssen identisch sein; die Schlussquote braucht weiterhin einen
  Stempel innerhalb von 15 Minuten vor Anpfiff.
- **Alter je Tipp:** jede neue Ledger-Zeile trägt `opening_quote_age_seconds` (Ledger-Zeit
  minus Provider-Stempel). Die Statistik (`get_clv_statistics`) prüft den gespeicherten Wert
  gegen die Zeitstempel der Zeile (Toleranz eine Sekunde); eine widersprüchliche Angabe
  macht die Zeile zu `invalid_quote_provenance` und sperrt die Freigabediskussion, wie bisher
  bei jeder Provenienzlücke. `get_recent_predictions` und das Run-Artefakt (`recent`) zeigen
  das Alter; das Artefakt nennt die geltende Grenze (`opening_quote_max_age_seconds`).
- **Kohorten:** `shadow_clv_automation.SHADOW_POLICY_VERSION` wechselt auf
  `shadow-model-first-v6`. Zeilen unter v5 bleiben in ihrer Kohorte, erfüllen die gelockerte
  Prüfung ebenfalls und werden nicht umgeschrieben; Zählung, Verdikt und paarweise Auswertung
  (Legacy/Hybrid, Edge-Cap) beginnen für v6 bei null. Beide Shadow-Kohorten nutzen dieselbe
  Policy-Version, der Paarvergleich bleibt deshalb möglich.

## Was die Evidenz jetzt bedeutet

Der CLV bleibt der Vergleich zweier provider-gestempelter Preise desselben Buchmachers:
Öffnungsquote beim Protokollieren, Schlussquote höchstens 15 Minuten vor Anpfiff. Eine bis zu
drei Stunden alte Öffnungsquote kann vom Markt zum Ledger-Zeitpunkt bereits abweichen; der
gemessene CLV enthält damit auch die Marktbewegung zwischen Stempel und Protokollierung. Vor
einer Freigabediskussion ist der CLV deshalb nach `opening_quote_age_seconds` zu schichten
(etwa ≤ 10 min, ≤ 1 h, ≤ 3 h) und mit dem No-Vig-Closing-Benchmark zu vergleichen; die
Schwellen der Prüfpläne (300 Paare, 300 Tipps je Gruppe) bleiben unverändert.

## Umsetzung

`clv_tracker.py` (Konstanten, Spalte `opening_quote_age_seconds`, Erfassung, Prüfung,
Ausgabe), `shadow_clv_automation.py` (Policy v6, Artefakt), Tests
`tests/test_opening_quote_age.py`, angepasste Erwartungen in `tests/test_shadow_markets.py`
und `tests/test_clv_versions.py`. Keine Migration nötig: die Spalte wird beim ersten Start
ergänzt, alte Zeilen behalten `NULL`.
