# Benfica–Celtic: erste Karte ist keine begründete Hauptempfehlung

Stand 15.10.2026. Diagnose, keine Fußball-Codeänderung. Quelle ist ausschließlich
der gespeicherte Produktionslauf, kein neuer Sport-/API-Scan.

## Tatsächlich geprüft

- VPS `4ece002b69eb5c96897d3471cc7320654608a903`; gespeicherter Lauf 02:07 UTC.
- Spiel `1636228`, Benfica–Celtic, Beginn 19:00 UTC. Sechs Modellmärkte.
- Zielgebundener Export außerhalb von Git:
  `C:/Projekt/BetBoy/output/tennis-player-index-20261015/benfica-event-readonly.json`,
  SHA256 `e6e7eff8f6872c653e0b3a9cb7f1d05200e03b39d68805fe8e36165bd0103db3`.
- Auswahl-/Darstellungsmodule stimmen zwischen Produktiv- und Arbeitsstand überein.
- Unabhängiger Offline-Replay der sechs Zeilen, ohne Netzwerk/DB/Dateischreiben:
  kein hervorgehobener Markt (`catalog.featured == ()`).

## Ursache der ersten Position

Alle sechs Zeilen haben denselben Ereignis-/Modell-/Zeitstand und dieselbe
modellseitige Zulässigkeitsklasse. Kein einzelner Heimsieg-, Remis- oder
Auswärtssiegmarkt befindet sich in diesem gespeicherten Pool. Deshalb gibt es
keinen modalen Ergebnisanker. `forecast_selection.py:21` und `:46` lösen den
Gleichstand stabil anhand des Marktkennzeichens. `DC_X2` kommt alphabetisch vor
`HOME_UNDER_0_5`, `HOME_UNDER_1_5`, `HOME_UNDER_2_5` und den beiden Kombimärkten.
Die Startzeitsortierung behält diese Reihenfolge innerhalb desselben Spiels
(`tip_display_order.py:44`). Daher steht X2 in der großen ersten Karte.

Das ist kein Nachweis, dass X2 die beste Wette ist. Auch der höchste vorgelagerte
Modellnutzwert von X2 ersetzt diese Begründung nicht. Für das UEFA-Spiel fehlt
im gespeicherten Beleg der für Hervorhebung verwendete Spiel-/Markt-Formvergleich
(`wettfinder_surface.py:555`). Die genaue frühere Ausschlussursache des fehlenden
Heimsiegmarktes lässt sich aus den sechs publizierten Zeilen nicht rekonstruieren.

## Wahrscheinlichkeit und Begründung auseinanderhalten

X2 bedeutet Remis **oder** Celtic-Sieg. 53,2799 % X2 und 46,7201 % Benfica-Sieg
sind Gegenereignisse. Höhere erwartete Benfica-Tore widersprechen dem nicht.
Eine unabhängige Poisson-Plausibilitätsprüfung mit den gerundeten 1,74:1,36
ergibt rund 53,51 % X2; das ist kein exakter Replay der kalibrierten Torverteilung.

Beide sichtbaren Fünferformen lauten 4S/0U/1N. Daraus allein folgt kein Vorteil
von Celtic gegenüber Benfica. Der gespeicherte Ansatz verwendet Heimatliga-
Statistiken; eine belastbare ligenübergreifende Gegnerstärkenwirkung ist damit
nicht belegt. Verletzungen/Aufstellungen wurden in dieser Wahrscheinlichkeit
nicht numerisch eingerechnet. Die knappe Torerwartung erklärt den ersten Platz
nicht und der sichtbare generische Gegenargument-Chip hilft dabei ebenfalls nicht.

## Quote

Die gespeicherte 4,05 ist dem richtigen Spiel und `DC_X2`/`Double Chance`/
`Draw/Away` zugeordnet: historische Marathonbet-Bestquote unter acht Anbietern,
beobachtet 00:19:19 UTC. Der spätere Abruf erneuert diese Beobachtungszeit nicht.
Kein Beleg für eine Marktverwechslung, aber auch kein aktuelles Preisangebot.

## Offen / keine vorgetäuschte Reparatur

Die erste/große Darstellung muss von einer fachlich priorisierten Auswahl
unterscheidbar sein; technische Alphabetreihenfolge darf keine Hauptempfehlung
vortäuschen. Für Doppelte Chance braucht der Kurzcheck eine marktbezogene
Begründung einschließlich des Remisanteils und des tatsächlichen Gegenarguments.
Hier nur Diagnose dokumentiert; der freigegebene Tennisindex-Plan bleibt separat.
