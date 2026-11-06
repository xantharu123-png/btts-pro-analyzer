# Plan „bessere Prognosen“, Schritt 3: Ausfälle und Ruhetage als Zahl, geprüft und nicht aktiviert

Stand 05.11.2026. Owner-Auftrag „Ja, Schritt 3“ (Plan `docs/superpowers/plans/2026-11-05-bessere-prognosen.md`).

Die Prüfung lief offline: keine API-Abrufe, keine Datenbankkopie, keine Code-Änderung. Skripte und Ausgaben liegen
unter `output/ausfaelle-20261105/`.

## Daten

- Aus `context_models.db` wurde ein Auszug gelesen (`export_context.py`, 885 KB). Er wurde auf dem Server danach
  gelöscht.
  - Ausfall-Meldungen (`availability`) für 1770 Spiele. Gezählt ist je Team und Spieler nur der letzte Stand vor dem
    Anpfiff.
  - Spielminuten je Spieler (`appearance`) für 2160 Spiele.
  - Spieldaten aller Wettbewerbe (`base_fixture`) für 10 244 Spiele.
- Die Torerwartung stammt aus der unveränderten Live-Rechnung `challenge_engine._fixture_model` (Ligaweg, Saison und
  Vorsaison). Als Historie dienen die am 05.11. abgerufenen Ligaergebnisse von 31 Ligen.
- Datensätze:
  - Ausfälle: 759 Spiele mit Abdeckung beider Teams und Ergebnis; davon 478 mit Minutenanteil.
  - Ruhetage: 883 Ligaspiele ab 15.09.

## Vorab festgelegt

Die Hypothesen stehen in `output/ausfaelle-20261105/HYPOTHESE.md` und wurden vor jeder Schätzung geschrieben.
- **Merkmale:**
  - Anteil der Spielminuten, der fehlenden Spielern gehört („out“ oder „suspended“, letzte bis zu 6 Spiele).
  - Ersatzweise die Zahl dieser Spieler geteilt durch 11.
  - Für Ruhetage: 1, wenn das letzte Pflichtspiel weniger als 4 Tage zurückliegt.
- **Modell:** λ' = λ_live · exp(b_eigen · M_eigen + b_gegner · M_gegner). Das entspricht dem gekoppelten Rechenweg
  q(h,a) ∝ p(h,a)·exp(dh·h + da·a).
- **Erwartet:** b_eigen < 0 und b_gegner > 0.
- **Prüfung:** Walk-forward nach Spieltag, die erste Hälfte nur zum Lernen, bewertet die zweite Hälfte in drei Blöcken.
- **Aktivierung:** nur, wenn die obere 95-%-Grenze bei Tor-Log-Likelihood und 1X2-Brier unter 0 liegt, kein Band mehr
  als 2 Punkte schlechter wird und die Richtung in allen Blöcken gleich ist.

## Ergebnis

| Merkmal | Spiele (Prüfung) | b_eigen (SE) | b_gegner (SE) | Tor-LL Differenz (SE) | 1X2-Brier Differenz (SE) |
|---|---|---|---|---|---|
| Minutenanteil | 478 (240) | +0,74 (0,44) | −0,36 (0,47) | −0,0031 (0,0047) | −0,0007 (0,0025) |
| Anzahl Ausfälle | 759 (386) | +0,31 (0,11) | −0,04 (0,12) | −0,0078 (0,0054) | −0,0026 (0,0023) |
| Ruhetage unter 4 | 883 (513) | +0,25 (0,05) | −0,11 (0,06) | −0,0130 (0,0117) | −0,0047 (0,0054) |

- Keine Verbesserung ist belegt. Alle oberen 95-%-Grenzen liegen über 0.
- Die Richtung ist umgekehrt zur Hypothese: Mehr eigene Ausfälle und kürzere Pausen gehen mit **mehr** eigenen Toren
  einher, als die Live-Rechnung erwartet.
- Das Ergebnis lautet deshalb **nicht aktiviert**. Ausfälle, Aufstellung und Belastung bleiben Sperre und Hinweis
  (`_context_probability_integration_summary` unverändert).

## Warum die Richtung umgekehrt ist

Beide Merkmale stehen vor allem für starke Teams. Für grosse Klubs gibt es mehr gemeldete Ausfälle. Kurze Pausen haben
vor allem Teams, die zusätzlich im Europapokal oder Pokal spielen. Zur Probe wurde die Teamstärke als Kontrolle
aufgenommen (Tordifferenz je Spiel in den letzten 10 Ligaspielen, `confound_check.py`). Diese Schätzung ist nur
beschreibend und nicht walk-forward.

| Merkmal | b_eigen ohne Stärke | b_eigen mit Stärke | Stärke (SE) |
|---|---|---|---|
| Anzahl Ausfälle | +0,32 (0,11) | +0,18 (0,12) | +0,117 (0,018) |
| Ruhetage unter 4 | +0,25 (0,05) | +0,16 (0,05) | +0,110 (0,016) |

Mit Kontrolle schrumpfen die Effekte deutlich. Der klare Befund ist ein anderer: **Die rohe Live-Torerwartung
unterschätzt formstarke Teams.** Je Tor Tordifferenz pro Spiel liegen die tatsächlichen Tore rund 12 % höher.

Die Kalibrierkurven je Liga und Markt gleichen davon einen Teil aus. Die veröffentlichten Bänder sind gut kalibriert
(Plan-Basiswerte: 50–60 % → 54,0 %, 70–80 % → 74,9 %). Unklar ist noch, wie viel Trennschärfe dabei verloren geht.

## Folgerungen

- Einen echten Effekt von Ausfällen und Ruhetagen kann man erst auf einem Modell messen, das die Teamstärke
  gegnerbereinigt abbildet. Das ist Plan-Schritt 4 (Hybrid mit Dixon-Coles-Struktur).
- Die Unterschätzung formstarker Teams ist ein eigener Kandidat für eine Verbesserung. Sie braucht vor jeder Änderung
  eine vorab festgelegte Hypothese und eine Walk-forward-Prüfung auf der kalibrierten Ausgabe, nicht auf der rohen.
- Die Datenmenge ist klein, vor allem beim Minutenanteil: Nur für 2160 Spiele sind Minuten gespeichert, und viele Teams
  haben weniger als 3 Vorspiele. Seit dem 10.09. kamen im Schnitt rund 220 Spiele mit Ausfall-Meldungen pro Woche dazu.
