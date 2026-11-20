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

## Release am 20. November 2026

Owner-Freigabe: „live stellen“. Start 19:44:58 CET, abgeschlossen 19:45 CET. Fast-forward ohne Backup
von `87f2434` auf `363ed54a74f33464a5a453aaf018ca927f63c324` (PR #144 und #145). Der VPS-Commit
entsprach GitHub `main` und dem lokal geprüften Dateibaum.

| Prüfung | Direkt nach dem Release |
|---|---|
| Release-Helfer | Exit 0. Offline-Importprüfung (52 Module) und synthetischer Haupttipp-Test bestanden, lokal und auf dem VPS. |
| Betrieb | App-Prozess von `1675324` auf `1700767` gewechselt; App und Caddy aktiv, interner und öffentlicher Healthcheck `ok`. |
| Timer | Alle sieben fachlichen Timer aktiv. Keine systemd-Einheit geändert. |
| Erster regulärer Shadow-Lauf | 20.11.2026, 19:52:11–19:54:08 CET: regulär beendet, Exit 0, systemd `success`. Journal: null technische Fehler, ein Datenhinweis (`partial`). Kein manueller Start. |
| Kundenansicht | Im separaten Headless-Browser: HTTP 200, Titel BetBoy, gerenderte Wettfinder-Liste „1–20 von 45 Spielen“, Analysedetail aufgeklappt; keine Konsolen- oder Seitenfehler im Test. |
| Veröffentlichte Daten | SHA-256 vor/nach dem Deploy identisch: Wettfinder `6414a5…8cdf`, RisikoBet `f938b7…acc1`. Kein Backup, kein zusätzlicher Sportscan. |

Die anschliessende, rein lesende Produktionszählung seit 19:45:10 CET ergab **14 Erstbelege für die
gerenderte Wettfinder-Ansicht** und **0 für die automatische Standardseite**. Die beiden Flächen sind
getrennt. Das sind keine 14 Kundenwetten oder Gewinne. Der erste Standardseiten-Beleg aus einem regulären
Wettfinder-/Quotenlauf und die spätere Abrechnung stehen noch aus.
