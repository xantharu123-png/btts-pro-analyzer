# Befund 22.10.2026: Der Fussball-Shadow sammelt seit Anfang Oktober keine Evidenz

Nachkontrolle nach dem Release von `fd45176` (Hybrid-Kohorte, Edge-Cap-Protokoll). Nur lesend
erhoben auf dem VPS (Journal der Unit `betboy-football-shadow`, `shadow_clv.db`,
`runtime_state/api_budget.db`); Belege ausserhalb Git unter
`output/hybrid-shadow-20261022/shadow-check-0[2-7].log`. Beide Ursachen bestehen unabhängig vom
Release und betreffen die Legacy-Kohorte genauso wie die neuen Protokolle.

## 1. API-Football-Kontingent seit 19.10.2026 bei 100 Aufrufen je Tag

| Tag | Tageslimit laut Provider | Rest (Schätzung / beobachtet) |
|---|---:|---:|
| 08.10. bis 18.10. | 7 500 | 2 579 bis 7 117 |
| 19.10. | **100** | 99 / 99 |
| 20.10. bis 22.10. | **100** | 99 / 99 |

Die Schlüsselrotation war am 17.10.; am 17. und 18.10. meldete der Provider noch 7 500.
Der Wechsel auf 100 kam am 19.10., also ein Abonnement-/Zahlungsereignis beim Anbieter, nicht
die Rotation. `api_budget` hält für Empfehlungs-Abrufe eine Reserve von 750 und für
Hintergrund-Abrufe 2 500 Aufrufe frei; bei 100 je Tag wird damit fast alles blockiert
(20.10.: 510 blockiert, 1 abgeschlossen; 21./22.10.: je 238 blockiert, 54 abgeschlossen).
Folgen im Shadow: Spielplanabruf für 21. bis 23.10. gescheitert (keine Zeile in
`shadow_fixtures`), Fixture-Details und Historien fehlen, alle Läufe enden `partial`/Exit 1.

## 2. Öffnungsquote: Frischeregel verhindert seit Wochen jede Protokollierung

Seit dem 1.9.2026 wurden genau zwei Tipps protokolliert (28.09., 03.10.), obwohl allein vom
1. bis 18.10. rund 950 Spiele als bewertet markiert wurden. Am 17./18.10. lieferte das Modell
in jedem Bewertungsfenster glaubwürdige Kandidaten (1 bis 6 je Lauf), und jeder Versuch endete
mit „keine aktuelle Bet365-Quote mit Providerzeit; Retry“, bis das Spiel aus dem Fenster fiel.
Ursache: `CLVTracker.OPENING_QUOTE_MAX_AGE` verlangt eine Provider-Aktualisierung (`update`)
höchstens zehn Minuten vor dem Lauf; API-Football aktualisiert Vorab-Quoten deutlich seltener.
Das ist bewusstes Fail-closed (Vertrag der CLV-Evidenz), führt aber dazu, dass Legacy-,
Hybrid- und Edge-Cap-Kohorte praktisch leer bleiben.

## 3. Was das für die Prüfpläne bedeutet

Die 300 Paare (`docs/superpowers/plans/2026-10-22-hybrid-aktivierung.md`) und die 300 Tipps je
Gruppe (`docs/superpowers/plans/2026-10-21-edge-cap.md`) sind unter diesen Bedingungen nicht
erreichbar. Beide Punkte brauchen Owner-Entscheidungen:

1. **Kontingent:** Abonnement beim Anbieter prüfen (Dashboard api-sports); erst mit dem
   7 500er-Plan laufen Spielplan, Details, Historien und Quoten wieder. Alternativ die
   Reserven in `api_budget` für einen 100er-Plan neu festlegen; damit liesse sich aber nur ein
   Bruchteil der Ligen bedienen.
2. **Frischeregel** (entschieden am 23.10.2026: drei Stunden, Alter je Tipp, Policy v6;
   `docs/audits/2026-10-23-oeffnungsquote-frischeregel.md`): Entscheiden, ob eine provider-gestempelte Öffnungsquote auch älter als
   zehn Minuten als Evidenz gilt (etwa bis drei Stunden, Alter wird mitprotokolliert) oder ob
   eine zweite Quelle mit häufigeren Aktualisierungen nötig ist. Das ändert einen
   Evidenzvertrag (`clv_tracker`) und wird daher nicht ohne Freigabe umgesetzt.

Nebenbefund: 91 Zeilen in `shadow_fixtures` aus Juli/August stehen noch auf `evaluated = 0`;
sie liegen ausserhalb jedes Fensters und sind wirkungslos, aber Datenmüll.
