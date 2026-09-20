# E-Sport-Quotenanschluss – 20.09.2026

## Geprüfter Umfang

Der Nutzer hat den OddsPapi-Schlüssel außerhalb von Git übergeben. Der echte
Account meldet einen aktiven kostenlosen Tarif mit 250 Anfragen und deaktivierter
automatischer Verlängerung. Es wurde kein kostenpflichtiger Tarif bestellt.

Native Katalogzuordnung: Dota 2 sportId 16 / Winner 161, Counter-Strike 17 / 171,
League of Legends 18 / 181, Valorant 61 / 611. Die beiden Ergebnis-IDs werden
explizit gebunden, nicht durch die Reihenfolge eines JSON-Objekts bestimmt.

Erster realer Einzelabruf: Sparta eSports–Inox Division, Pinnacle 2,50 / 1,48.
Das war ein Anschlussnachweis, kein neu erzeugtes Modell und keine Empfehlung.

## Anbietergrenzen tatsächlich geprüft

Die veröffentlichte Dokumentation für `odds-by-tournaments` entspricht nicht
vollständig dem echten Endpunkt: Er verlangt `bookmaker` (singular), genau einen
Buchmacher und maximal fünf Turniere. Beide Grenzen wurden durch native 400-
Antworten bestätigt. Fixtures-Abfrage über alle Sportarten im 47-Stunden-Fenster
lieferte 2.235 Events, davon elf gültige E-Sport-Events aus acht Turnieren.

Der Transport bündelt daher höchstens fünf Turniere je Anfrage; Pinnacle und
1xbet werden getrennt geladen. Die gesamte benötigte Restmenge muss im vorhandenen
Tages-/Monatsbudget liegen. Keine automatische Ausweitung auf einen Bezahlplan.
Eine vollständige Runde braucht eine Spielabfrage plus zwei Abfragen je Turnier-
paket. Bei mehr als drei Anfragen wird das Aktualisierungsintervall 24 statt
zwölf Stunden. Höchstens sieben reservierte Anfragen/Tag, 25 Monatsreserve.
Fehlerantworten zählen konservativ; `/account` ist laut Anbieter unberechnet.

## Gemeinsamer Verbraucherpfad

- Ein atomar ersetzter Cache, maximal 2 MB, keine zusätzliche Historien-Datenbank.
- Nur vollständiger Serien-/Match-Sieg mit zwei aktiven Seiten. Keine einzelnen
  Maps, Spielerwetten, Exchange-Preise oder falsche Disziplin mit gleichem Teamnamen.
- Exakter Spielbeginn innerhalb fünf Minuten, beide Teilnehmer und ursprüngliche
  PandaScore-Spielkennung. Mehrdeutige Events bekommen keine Quote.
- Gleicher Cache für Wettfinder, Daily3 und RisikoBet. Kein Preis verändert eine
  Modellwahrscheinlichkeit oder die gewählte Modellrichtung.
- Die Nutzergrenze 1,20 wird nach der Richtungsprüfung angewandt. Fehlende oder
  unpassende Quoten werden nicht als niedrige Quote interpretiert.
- Zeitangabe ist die tatsächliche Abrufbeobachtung. `changedAt` zeigt nur die
  letzte Preisänderung; daraus wird keine aktuell ausführbare Buchmacherquote
  erfunden. Anzeige maximal 24 Stunden und nie nach Spielbeginn.
- Kein Timer hinzugefügt, keine Geldbewegung, kein Modell neu freigegeben.
- Konfiguration: ausschließlich geschütztes `ODDSPAPI_KEY`, nicht im Repository.

## Tests und Release

Gezielte Tests zur Spiel-/Disziplin-/Marktbindung, nativen Stapelgrenze und
Oberfläche: 199 bestanden. Abschließende breite Regression: 1.358 Tests und
111 Untertests bestanden (inklusive finanzieller Altverträge und direktem
Vergleich mit dem historischen E-Sport-Code). Kein Claim eines Vollsuite-Laufs.
VPS-Nachweis wird vor Abschluss unten ergänzt. Bestehende Tennis-/Kontext-/
Workerprobleme sind nicht Gegenstand dieses Quotenanschlusses.

## Primärquellen

- https://oddspapi.io/us/docs/get-account
- https://oddspapi.io/us/docs/requests-and-quota
- https://oddspapi.io/us/docs/get-fixtures
- https://oddspapi.io/us/docs/get-markets
- https://oddspapi.io/us/docs/get-odds-by-tournaments
