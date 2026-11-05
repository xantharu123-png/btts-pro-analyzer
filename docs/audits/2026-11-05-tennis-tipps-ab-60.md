# Tennis-Tipps erst ab 60 % Modellchance

Stand 05.11.2026. Anlass: Owner-Frage „heute hatten wir viele Tennisspiele, die falsch waren, was ist los“ und
Auftrag „alles machen“ (Plan `docs/superpowers/plans/2026-11-05-bessere-prognosen.md`, Schritt 7: „Tennis
überschätzt im Band 50–60 %“). Alle Zahlen sind nur gelesen (`tennis_shadow.db`, `consumer_tips.db` auf dem VPS).
Es gab keine API-Abrufe und keine Datenbankkopie.

## Was am 4.11. passiert ist

Der Wettfinder zeigte am 4.11. elf Tennis-Tipps, alle aus dem Rolex Paris Masters. Drei davon trafen.

| Tipp | Modellchance | Ergebnis |
|---|---:|---|
| Djokovic gegen Hijikata | 77,7 % | verloren |
| de Minaur gegen Etcheverry | 74,0 % | verloren |
| Fils gegen Machac | 66,1 % | gewonnen |
| Fritz gegen Molcan | 64,7 % | gewonnen |
| Zverev gegen Musetti | 63,8 % | verloren |
| Tiafoe gegen Halys | 62,1 % | verloren |
| Tien gegen Van Assche | 59,6 % | verloren |
| Khachanov gegen Borges | 56,5 % | verloren |
| Struff gegen Tirante | 56,2 % | gewonnen |
| Bellucci gegen Rinderknech | 51,3 % | verloren |
| Humbert gegen Berrettini | 50,8 % | verloren |

Die Ergebnisse stimmen. Die Paarungen vom 5.11. bestätigen sie: Halys–Paul, Etcheverry–Hijikata,
Van Assche–Musetti, Buse–Borges, Fritz–Fils. Auch die Seite der Tipps stimmt. Jeder Tipp ist der Spieler mit der
höheren Modellchance, und die Prozentzahl im Tipp entspricht der gespeicherten Prognose. Ein Rechen- oder
Zuordnungsfehler liegt nicht vor. Die Spielerstärken sind aktuell: Beide Tour-Modelle wurden in der Nacht auf den
5.11. neu gebaut, mit Ergebnissen bis 26.10. (ATP) bzw. 1.11. (WTA).

Bei 59 veröffentlichten Tennis-Tipps mit Marktquote lag die Trefferquote bei 52,5 %. Der Markt hatte für dieselben
Spieler rund 62 % erwartet, das Modell 61 %. Die Buchmacher-Favoriten haben in diesen Tagen also genauso oft verloren.
Ein Teil ist damit Pech, vor allem in Paris.

## Was am Modell nicht stimmt

Das Modell `elo-serve-platt-v3` hat unter 60 % keinen messbaren Vorsprung vor einem Münzwurf.

Datenbasis: 2220 abgerechnete Prognosen vom 06.08. bis 04.11.2026, ohne Aufgaben. Gezählt ist jeweils die letzte
Revision je Spiel.

| Zeitraum | Band | Spiele | Tage | versprochen | eingetroffen (95 %) |
|---|---|---:|---:|---:|---|
| Hypothese Aug–Sep | unter 60 % | 640 | 52 | 54,6 % | 49,8 % (46,0–53,7) |
| Hypothese Aug–Sep | ab 60 % | 623 | 51 | 70,2 % | 69,3 % (65,7–73,0) |
| Prüfung Okt–4.11. | unter 60 % | 511 | 30 | 54,5 % | 50,9 % (46,5–55,2) |
| Prüfung Okt–4.11. | ab 60 % | 446 | 30 | 69,4 % | 67,9 % (63,6–72,3) |
| Prüfung ATP | unter 60 % | 167 | 29 | 55,0 % | 49,1 % (41,5–56,7) |
| Prüfung ATP | ab 60 % | 187 | 29 | 70,6 % | 73,8 % (67,5–80,1) |
| Prüfung WTA | unter 60 % | 344 | 30 | 54,3 % | 51,7 % (46,5–57,0) |
| Prüfung WTA | ab 60 % | 259 | 30 | 68,5 % | 63,7 % (57,9–69,6) |

In jedem Monat liegt das Band 50–60 % zwischen 47,7 und 52,9 % Treffern. Die Bänder darüber treffen ungefähr wie
versprochen: 60–65 % → 61,6 %, 65–70 % → 69,5 %, ab 70 % → 75,1 %.

Die veröffentlichten Wettfinder-Tipps zeigen dasselbe Bild:

| Tipps | unter 60 % | ab 60 % | gesamt |
|---|---|---|---|
| seit 05.10. | 44 von 95 (46,3 %) | 55 von 82 (67,1 %) | 99 von 177 (55,9 %) |
| seit 28.10. | 15 von 42 (35,7 %) | 18 von 30 (60,0 %) | 33 von 72 (45,8 %) |

## Vorab-Hypothese und zeitlich getrennte Prüfung

AGENTS.md verlangt für eine Grenze eine vorab definierte Hypothese und eine zeitlich getrennte Prüfung.
- **Hypothese:** Unter 60 % hat die Tennis-Siegerwahl keinen Vorsprung vor einem Münzwurf, ab 60 % schon. Sie stammt
  aus dem Plan vom 05.11. (Band 50–60 %: 55,1 versprochen, 48,1 eingetroffen, n=183) und aus den Monaten August und
  September (n=1263).
- **Prüfung:** auf den Spielen ab 1.10., die nicht zur Hypothese beigetragen haben (n=957), getrennt nach Tour.
- **Grenze:** 60 % ist die Bandgrenze aus dem Plan. Sie wurde nicht auf den Zeitraum ab Oktober angepasst.

Bestätigt: Unter 60 % enthält das 95-%-Intervall in beiden Zeiträumen und auf beiden Touren die 50 %. Ab 60 % liegt
es klar darüber.

## Nicht übernommen: Kalibrierung je Tour

Getestet wurde eine Walk-forward-Korrektur je Tour (Steigung auf den Log-Odds, ohne Achsenabschnitt), gelernt nur aus
Spielen, die mindestens zwei Tage zurückliegen (`output/tennis-20261105/recal_study.py`).
- Gesamt: Log-Loss 0,6605 → 0,6602, Differenz −0,0002 (SE 0,0013).
- ATP wird schlechter: +0,0059 (SE 0,0032).
- WTA wird etwas besser: −0,0034 (SE 0,0012).
- Das Band 50–60 % bleibt auch danach bei 51 bis 54 %.

Eine Steigung kann diesen Knick nicht abbilden. Der Nutzen ist zu klein für eine Änderung der Prognosen.

## Umsetzung

- `ev_signal_sources.tennis_model_signals`: Ein Tennis-Siegertipp entsteht nur ab einer Modellchance von 60 %
  (`TENNIS_WINNER_MIN_PROBABILITY`), unabhängig von der Seite. Der Pfad speist Wettfinder (automatisch und
  Grundbestand), die Tennis-Spalte und Doublebet.
- Unverändert:
  - Prognosen, Shadow-Speicher und Tennis-Finder.
  - RisikoBet (`adapt_tennis_shadow`).
  - Der alte preisgebundene Pfad `tennis_signals` mit dem Urteil „WETTE“.
  - Modell- und Policy-Version.
- Wirkung auf den 5.11.: Von sieben Tennis-Tipps bleiben drei, nämlich Paul (62,9 %), Musetti (63,9 %) und
  Shelton (70,5 %). Fils (53,8 %), Etcheverry (52,2 %), Borges (56,0 %) und Ruud (57,5 %) fallen weg.
- Test: `tests/test_ev_signal_sources.py::TennisSignalTests::test_model_signal_starts_at_sixty_percent_for_either_side`.

## Messung und Rückweg

- Gemessen werden die Trefferquote der Tennis-Tipps ab Release und das Band ab 60 % im Shadow, mit denselben
  Abfragen wie oben. Erwartet werden rund 68 % Treffer bei 67 % versprochen.
- Rückweg: Release auf den vorherigen Stand. Die Grenze ändert keine gespeicherten Daten.
- Das Modell selbst wird damit nicht besser. Dafür bräuchte es Daten zur Turnierstufe (WTA 125, Qualifikation) und
  einen Abgleich mit dem Markt (Plan Schritt 6, Owner-Entscheid).
