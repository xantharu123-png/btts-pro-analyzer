# Wettfinder: Folgetag, wenn heute weniger als 30 Fussballspiele gelistet sind

Datum: 02.11.2026. Owner-Entscheid im Chat („Ligen + Folgetag“). Der Wettfinder soll mindestens 30 Spiele zeigen;
3 a day bleibt bei drei Tipps, für die 15K-Liste reichen fünf am Tag. Die Ligen kamen in einem eigenen PR dazu
(`docs/audits/2026-11-02-ligenkatalog-66.md`). Von Dienstag bis Donnerstag reichen aber auch mehr Ligen nicht
sicher: Weltweit finden an diesen Tagen wenige gute Spiele statt.

## Regel

- Der tägliche Lauf (03:35) zählt nach Discovery und Kontextprüfung die heutigen Fussballspiele mit Modellauswahl.
  Liegt die Zahl unter 30 (`NEXT_DAY_MIN_GAMES`), scannt er zusätzlich den nächsten Zürcher Tag. Die Zahl 30 kommt vom
  Owner, gezählt wird nur Fussball.
- Der Folgetag läuft auf einem eigenen Zustand (`football_next_day`). Er bekommt die Kontextprüfungen, die heute
  übrig bleiben: drei Nachläufe zu je 20 Spielen, abzüglich der für heute verbrauchten. Dazu kommen die 20 Spiele aus
  seinem eigenen Scan. Heute geht damit immer zuerst.
- Auch für den Folgetag werden Preise für die 1,20-Untergrenze geholt, im Tageslauf und in jedem Quotenlauf.
- Im Dokument stehen die Morgen-Zeilen nur in `model_candidates`, dazu `next_day_search_date` und
  `sources.football.next_day` mit Status, Spielen, Zeilen und Preisprüfungen.
- Die Morgen-Spiele erscheinen nur in der Wettfinder-Liste mit Datum und Uhrzeit, der Kopf zeigt „Heute und morgen“;
  die Tennisbox behält „Heute“ (Korrektur 03.11.2026).
  Sie werden nie zu einem öffentlichen Tipp, einem 15K-Eintrag, einer 3-a-day-Wahl, einem Shadow-Eintrag oder einer
  Evidenzprognose. Im Archiv der veröffentlichten Auswahl (`tip_publication`) stehen sie erst an ihrem eigenen
  Spieltag, sonst würden sie doppelt gezählt.
- Schlägt der Folgetag fehl, fällt nur er weg. Status und Fehlerzähler von heute bleiben unverändert. Öffentlich
  steht nur die Fehlerart, nie der Fehlertext.
- Der App-Lader nimmt Morgen-Zeilen nur an, wenn alles davon zutrifft:
  - das Dokument nennt genau den nächsten Tag;
  - der Zustand des Folgetags trägt dasselbe Datum;
  - die Zeile ist eine Fussballzeile;
  - ihr Spiel hat einen geprüften Kontext im Zustand des Folgetags.

  Sonst gilt die alte Regel, und das ganze Dokument wird abgelehnt. Tipps und 15K-Zeilen auf einem anderen Tag
  lehnt der Lader immer ab.

## Grenzen

- Der Kontext der Morgen-Spiele ist am Anpfiff bis zu rund 40 Stunden alt. Am nächsten Morgen ersetzt der neue
  Tageslauf diese Zeilen durch frisch geprüfte.
- Zwischen Mitternacht und 03:35 bleibt die Seite wie bisher leer, weil das Dokument dann den Vortag nennt.
- Der Folgetag kostet einen zweiten Discovery-Lauf: je Liga ein Spielplanabruf, dazu Historie und Kontext. Unter der
  Woche liegt der Verbrauch heute bei 500–1400 von 7500 Abrufen am Tag.
