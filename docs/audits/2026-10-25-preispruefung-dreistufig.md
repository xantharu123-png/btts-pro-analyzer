# Vertragsänderung 25.10.2026: Dreistufige Preisprüfung der 1,20-Grenze

Owner-Entscheidung vom 25.10.2026 abends. Anlass: Die Karten „Mjällby–Hammarby, Team 2 1–4 Tore“
(Modell 79,7 %, beim Buchmacher 1,15) und „Sparta–Ajax, Ajax über 2,5 Ecken“ (Modell 87 %) waren
Hauptauswahlen, obwohl ihr Preis unter 1,20 lag oder nicht geprüft war. Ursache: Die 1,20-Grenze
griff nur, wo eine direkte Marktquote vorlag. Im Tagesdokument vom 25.10. hatten 112 von 353
Fussball-Auswahlen keine direkte Quote. Team- und Gesamttor-Bereiche sind zwar auf API-Football
gemappt (`Away Team Exact Goals Number`, Wert `1-4`), die Buchmacher dort bieten diese Werte aber
nicht an; Ergebnis-plus-Tore- und Oder-Märkte haben dort kein Gegenstück. Weil die Hauptauswahl
die wahrscheinlichste Auswahl ist (Entscheid 23.10.), rückten genau diese ungeprüften
Quasi-Sicherheiten nach oben (16 von 46 Hauptauswahlen am 25.10.).

Gilt nur unter `BETBOY_PRICE_POLICY=floor` (Produktion); `gate` behält den alten Vertrag.

## Die drei Stufen

1. **Direkte Quote vorhanden (bis 24 Stunden alt).** Die 1,20-Grenze wird gegen den **mittleren**
   Preis (Median) der beobachteten Buchmacher geprüft, nicht mehr gegen den besten. Grund: Die
   Quelle vergleicht bis zu neun Buchmacher (u. a. Pinnacle), der Buchmacher des Owners (ybets7)
   zahlt selten den besten Preis. Die gespeicherte Ausführungsquote bleibt das beste reale Angebot
   (Bindung an Buchmacher und Zeit unverändert, Befund L3 des Audits bleibt offen).
   `market_consensus.floor_price_status`, ebenso `quote_below_publication_floor` (RisikoBet,
   Manuelle Suche; unter `gate` weiter das beste Angebot).
2. **Tor-Bereich ohne direkte Quote.** Ein Bereich „a–b Tore“ (Heim, Gast, Spiel) ist nie
   wahrscheinlicher als „mindestens a Tore“. Aus den bepreisten Über/Unter-Linien desselben
   Spiels (No-Vig-Median, Power-Methode) wird `P(≥ a)` bestimmt; ist auch die Linie über `b`
   bepreist, gilt die Differenz `P(≥ a) − P(≥ b+1)`, sonst die Obergrenze `P(≥ a)`. Der
   abgeleitete Preis `1 / (p · 1,06)` (übliche Buchmachermarge 6 %) muss 1,20 erreichen, sonst
   wird die Auswahl zurückgehalten. Teamtor-Linien gibt es bis 2,5, Team-Bereiche sind deshalb
   immer eine Obergrenze; Gesamttor-Bereiche haben beide Linien. Die Schranke wird im Quotenlauf
   berechnet und an der Zeile gespeichert (`reference_price_bound`: Markt, Wahrscheinlichkeit,
   Basis `upper_bound`/`line_difference`, Quellmärkte, älteste Beobachtung), höchstens 24 Stunden
   gültig. Sie entscheidet vor Stufe 3, auch bei hoher Modellwahrscheinlichkeit.
   `market_consensus.derive_range_price_bound`, `wettfinder_automation._attach_floor_price_bounds`.
3. **Kein Preisbeleg.** Ohne direkte Quote und ohne Schranke entscheidet die Modellwahrscheinlichkeit:
   ab 65 % wird die Auswahl zurückgehalten, darunter bleibt sie wie bisher ohne Quote sichtbar.
   Grundlage am 25.10.: Von 94 Auswahlen mit Quote und Modell unter 65 % lag keine unter 1,20; bei
   70–80 % fast jede dritte, ab 80 % zwei von drei. Das Modell liegt bei Torlinien bis zu
   17 Prozentpunkte unter dem Markt (90 %-Quantil 8 Punkte); unter 65 % reicht dieser Abstand
   nicht bis 1,20. Gilt für alle Sportarten.

Stufen 2 und 3 sitzen in `wettfinder_reference_price_status` (`_unpriced_floor_status`). Damit
urteilen Karte und Hauptauswahl (`wettfinder_surface`, über die Quotenbindung mit
Wahrscheinlichkeit und Schranke), App-Lader und Signale (`ev_signal_sources`), Nachrücken,
Nachtscan und Nachprüfung (`wettfinder_automation._floor_withheld`) gleich. Zurückgehaltene
Auswahlen erscheinen wie bisher die unter 1,20 nicht (Code `BELOW_FLOOR`, Begründung im
`market_basis`: `derived-range-bound` oder `model-guard`). Die 15K-Liste verlangt weiter eine
spielbare direkte Quote; für sie wirkt nur der Median.

## Wirkung am Tagesdokument vom 25.10.

| Hauptauswahl der 46 Fussballspiele | vorher | neu |
|---|---|---|
| mit geprüfter Quote ab 1,20 | 30 | 43 |
| ungeprüft oder vermutlich unter 1,20 | 16 | 0 |
| ohne Quote, Modell unter 65 % | 0 | 2 |
| ohne Hauptauswahl | 0 | 1 |

Beispiele: Mjällby–Hammarby führt mit „Hammarby unter 2,5 Tore“ (Median über 1,50), Sparta–Ajax
mit „Sparta trifft mindestens einmal“. Von 64 Team-Bereichen hatten 49 eine Schranke (21 belegt
ab 1,20, 28 zurückgehalten), 15 fielen auf Stufe 3. Der Median nimmt gegenüber dem besten Preis
weitere 12 Auswahlen heraus. Trockenlauf auf dem VPS gegen das Live-Dokument (nur gelesen): Bis
zum nächsten Quotenlauf hält der neue App-Lader 12 als `PLAYABLE` gespeicherte Zeilen zurück
(Median unter 1,20, Zähler `price_inconsistent_rows`), danach keine; 3 öffentliche Tipps, die
15K-Liste schrumpft von 15 auf 10.

## Grenzen

- Die 1,20-Grenze erlaubt weiter Auswahlen knapp darüber; am 25.10. sahen 14 der neuen
  Hauptauswahlen 80 % oder mehr. Das folgt aus der Grenze, nicht aus fehlenden Daten.
- ybets7 hat keine öffentliche Quoten-Schnittstelle (eingebettete eigene Web-App); ein
  automatisches Auslesen wäre ein Zugriff auf eine interne Schnittstelle und wird nicht gebaut.
  Wer die ybets7-Quote selbst einträgt, wird schon heute unter 1,20 gesperrt.
- Ecken-, Karten-, Ergebnis-plus-Tore- und Oder-Märkte ohne Quote haben keine Ableitung; für
  sie gilt Stufe 3. Die Manuelle Suche prüft eigene Eingaben weiter selbst; Stufe 3 wirkt dort
  nur, wo die Auswahl die Wahrscheinlichkeit mitträgt.

## Umsetzung und Tests

`market_consensus` (Konstanten `FLOOR_UNPRICED_MAX_PROBABILITY = 0.65`,
`FLOOR_DERIVED_MARGIN = 0.06`; `floor_price_status`, `valid_price_bound`,
`derive_range_price_bound`, `_unpriced_floor_status`, `quote_below_publication_floor`),
`wettfinder_automation` (`_attach_floor_price_bounds` am Ende von `_apply_reference_quotes`,
`_floor_withheld` in `_floor_playable_rows`, `_revalidate_publication_price_overlays`,
`_republish_floor_candidates`), `ev_signal_sources` (`ModelSignal.reference_price_bound`),
`wettfinder_surface` (Quotenbindung mit Wahrscheinlichkeit und Schranke). Tests in
`tests/test_price_floor_policy.py`: Median statt Bestpreis (auch für gespeicherte Zeilen und die
Anzeigeregel, `gate` unverändert), Schranke aus Teamlinien (Hammarby-Fall), aus Unter-Linie, als
Differenz zweier Gesamttor-Linien, veraltete Linie, fremder Markt, Modellschutz an der 65-%-Grenze
und in Prozent, Ende-zu-Ende über Quotenlauf, Nachrücken, App-Lader, Signale und Karte.
