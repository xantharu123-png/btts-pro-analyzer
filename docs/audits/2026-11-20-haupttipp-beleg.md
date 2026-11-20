# Welcher Tipp stand zuerst oben?

Für die 13 Spiele am 19. November wurde diese Rolle nicht gespeichert. Die
12 Treffer aus 18 entschiedenen Katalogmärkten sind **nicht** die Trefferquote
der 13 Haupttipps. Aus den alten Daten lässt sie sich nicht nachtragen.

## Ab der ersten Veröffentlichung mit dem neuen Code

- Der reguläre Wettfinder archiviert je Spiel den ersten belegten Hauptmarkt der
  angebotenen Standardseite (alle Sportarten, 70 %, erste 20 Spiele). Das ist kein
  Nachweis eines Besuchs. Das zweite Schreiben mit der Vorschau und reguläre
  Quotenaktualisierungen können die erste Seite verändern; auch sie werden geprüft.
  Die Vorschau für morgen ist selbst kein Haupttipp des heutigen Spieltags.
- Eine separat geführte Ansicht erfasst bei einem tatsächlichen Seitenaufruf nur
  die gerenderten Spiele der gewählten Seite und Filter. Ein globales Highlight
  und die erste verbliebene Zeile ohne belegbaren Hauptmarkt sind keine Hauptrollen.
- Eine bereits belegte Erstauswahl bleibt erhalten. Ein alter Katalog wird durch
  spätere Treffer nicht nachträglich zur bestätigten Hauptkarte. Ohne eindeutig
  passenden, rechtzeitigen Modell- und Ergebnisbeleg gibt es keinen Treffer.
- Die Belege bleiben im bestehenden Tipp-Archiv. Zwischenläufe erzeugen keinen
  zweiten Gesamtkatalog und verändern keine Kundenwette, kein Modell und keine Quote.
  Fällt die Belegerfassung beim Quotenlauf aus, bleibt der Hinweis intern;
  die veröffentlichte Datei und der anschliessende Ergebnisabgleich bleiben erhalten.

## Lokale Prüfung

492 gezielte Regressionstests im Standard-Testvertrag bestanden, darunter der
Weg vom Worker über ein temporäres Originalarchiv bis zum zeitgebundenen
Ergebnisbericht. Im separaten Lauf unter dem Produktions-Preisvertrag
`floor` bestanden 489 gezielte Tests. Das sind überlappende Prüfpakete, keine
Vollsuite und kein Nachweis einer höheren Trefferquote. Das unabhängige
Code-Review hatte nach den Korrekturen keinen blockierenden Befund.

## Abnahme nach Release

Erst nach dem nächsten normalen Lauf mit dem neuen Code im internen Spieltagbericht
`first_main_card` und `all_distinct_markets` getrennt lesen. Auf ein
abgerechnetes Ergebnis warten; kein zusätzlicher Abruf und kein Backfill.
Die historische Abnahme von PR #144 steht im [Spieltagbericht](2026-11-20-haupttipps-und-datenabdeckung.md).
