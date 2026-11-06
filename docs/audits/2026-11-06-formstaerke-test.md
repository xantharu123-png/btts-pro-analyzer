# Formstärke in der Torerwartung: vorab festgelegter Test bestanden

Stand 06.11.2026. Owner-Auftrag „Ja, vorbereiten“ nach dem Befund aus Plan-Schritt 3
(`docs/audits/2026-11-05-ausfaelle-ruhetage-schritt-3.md`): Die rohe Live-Torerwartung unterschätzt formstarke Teams.

Die Prüfung lief offline: keine API-Abrufe und keine Datenbankkopie. Am Code der App ändert sich nichts. Skripte und
Ausgaben liegen unter `output/formstaerke-20261106/`.

## Vorab festgelegt

Die Datei `output/formstaerke-20261106/HYPOTHESE.md` wurde vor jeder Rechnung auf den Testdaten geschrieben.

- **Herkunft:** Auf Ligaspielen ab 10./15.09.2026 lag der Koeffizient bei 0,117 (SE 0,018) bzw. 0,110 (SE 0,016) je
  Tor Tordifferenz pro Spiel. Diese Spiele gehören nicht zu den Testdaten.
- **Merkmal s je Team:** mittlere Tordifferenz pro Spiel in den letzten 10 Ligaspielen dieser Liga vor Anpfiff. Unter
  5 Spielen gilt kein Zuschlag.
- **Variante:** λ_Heim' = λ_Heim · exp(κ · (s_Heim − s_Gast)), λ_Gast' = λ_Gast · exp(κ · (s_Gast − s_Heim)).
  - κ ist fest 0,11.
  - Der Faktor gilt für aktive, Saison- und Formrate.
  - Es gibt keine weitere Variante und kein Nachjustieren.
- **Weg:** der unveränderte Validierungsweg der App `challenge_engine._walk_forward_market_records`.
  - Walk-forward mit Kalibrierkurven je Liga, die nur aus früheren Spielen gelernt sind.
  - Beide Arme lernen ihre Kurven aus den eigenen Rohwerten.
  - Bewertet werden die **kalibrierten** Wahrscheinlichkeiten der Tormärkte.
- **Daten:** Ligaergebnisse der 31 am 05.11.2026 abgerufenen Ligen vor dem 01.09.2026, je Liga eine Gruppe.

## Ergebnis

16 634 Spiele aus 31 Ligen, 529 960 Marktprognosen. Die Standardfehler sind nach Liga gebündelt.

| Bedingung | Ergebnis | erfüllt |
|---|---|---|
| 1. Brier besser, obere 95-%-Grenze unter 0 | 0,19599 → 0,19463, Differenz −0,00136 (SE 0,00017), Grenze −0,00103 | ja |
| 1. Log-Loss besser, obere 95-%-Grenze unter 0 | 0,57448 → 0,57114, Differenz −0,00334 (SE 0,00039), Grenze −0,00257 | ja |
| 2. Log-Loss in mindestens zwei Dritteln der Ligen besser | 30 von 31 Ligen (nur Liga 106 Polen +0,0014) | ja |
| 3. Kein Band mehr als 2 Punkte schlechter | grösste Verschlechterung +0,24 Punkte | ja |
| 4. 1X2-Log-Loss nicht schlechter | 1,0291 → 1,0179 (n=13 249) | ja |

Kalibrierung über alle Tormärkte (versprochen → eingetroffen):

| Band | live | mit Formstärke |
|---|---|---|
| 10–20 % | 15,4 → 14,8 | 15,4 → 15,1 |
| 30–40 % | 35,1 → 34,5 | 35,1 → 34,8 |
| 50–60 % | 55,0 → 55,4 | 55,1 → 55,1 |
| 70–80 % | 74,3 → 74,4 | 74,4 → 74,2 |
| 80–90 % | 84,6 → 85,2 | 84,5 → 84,9 |

Der Gewinn ist klein, aber sehr gleichmässig. Zum Vergleich: Das stärkere Kalibriergesetz v2 aus Schritt 2 war um
+0,0006 Brier schlechter. Die Formstärke ist um −0,0014 besser und hat den grössten Teil davon im 1X2-Markt.

## Folgen und offene Punkte

- Laut Vorab-Regel ist die Formstärke damit **Kandidat**. Live geht sie erst nach Owner-OK und einer zusätzlichen
  Prüfung auf Spielen ab November 2026. Dafür sind die gespeicherten Ergebnisse in `context_models.db` nutzbar, ohne
  neue Abrufe.
- **Umsetzung:**
  - Die Torerwartung aller Ligaspiele ändert sich. Das braucht eine neue Vorhersage-Version, weil die gespeicherten
    Kalibrierkurven und Validierungen (`challenge_model_cache.db`) zur alten Rohrechnung gehören.
  - Die Version `coherent-joint-calibration-v15` ist schon für das verworfene Gesetz v2 vergeben. Die neue Version
    braucht einen eigenen Namen.
  - Der Faktor gehört als geprüfte Annotation an das Spiel, wie bei der Ligastärke. Dazu kommen Pins, ORIGINAL-Feld,
    Shadow-Kohorten und Cache-Neuaufbau.
- **Grenzen der Prüfung:**
  - Nur Ligaspiele der 31 Ligen mit abgerufener Historie.
  - Nur Tormärkte; Ecken und Karten sind nicht bewertet.
  - Für Europapokal-Spiele ist der Faktor nicht geprüft.
  - κ stammt aus 2026/27 und wurde auf 2024–2026 bestätigt. Ob er ab November gleich bleibt, zeigt erst die
    Zusatzprüfung.
