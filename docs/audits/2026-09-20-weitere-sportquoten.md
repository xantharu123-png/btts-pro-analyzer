# Weitere Sportquoten – 20.09.2026

## Umsetzung

- Basketball (NBA/Euroleague) und Eishockey (NHL): automatische Vorab-Quoten
  über die bestehenden kostenlosen API-Sports-Zugänge, kein zusätzliches Abo.
  Der echte Zugang lieferte Spiele und Buchmacherquoten beider Sportarten.
- Ein zentraler Abruf im vorhandenen Wettfinder-Worker, Wiederverwendung in
  Wettfinder, Daily3 und RisikoBet. Kein neuer Timer, keine neue Datenbank.
- Auch RisikoBet-Spiele ohne vollständige Modellprognose werden über ihre
  vorhandene Identität bepreist. Eine Quote erzeugt keine Wahrscheinlichkeit.
- Exakt gebunden: ursprünglicher Anbieter und Spiel-ID, Beginn, Gegner,
  Heim-/Gastseite und Matchsieg einschließlich Verlängerung/Penaltyschießen.
  NHL-Abkürzungen werden anhand des ursprünglichen NHL-Spiels aufgelöst,
  nicht durch unscharfe Namensvergleiche. Mehrdeutige Zuordnungen entfallen.
- Kein Ersatz durch Dreiweg-, reguläre Spielzeit-, Halbzeit- oder Periodenmärkte.
- Diese API-Antworten enthalten keinen Buchmacher-Aktualisierungszeitpunkt.
  Anzeige deshalb „Quote abgerufen“ und tatsächlicher Abrufzeitpunkt. Keine
  automatische Einsatzfreigabe aus diesem Abrufbeleg. Unter 1,20 gilt weiterhin
  der gemeinsame Vorschlagsfilter; Modellwerte bleiben unverändert.
- Wiederholung frühestens nach drei Stunden, höchstens acht Events je Sport
  pro Runde, vorhandener atomarer Quotenbudgetzähler mit 100 Tagesanfragen und
  15 reservierten Anfragen. Namensauflösung und Tagesabfrage werden pro Runde
  wiederverwendet. Bereits begonnene Spiele übernehmen keine Vorab-Preise.
- Ein atomar ersetzter Cache, maximal 2 MB, ohne Historienanhang; keine
  Verdoppelung pro Modellrevision. Abgesagte/verschobene oder nicht mehr
  angebotene Spiele verlieren nach erfolgreicher erneuter Prüfung alte Preise.

## Prüfungen

- Betroffene breite Regression: 1.122 Tests und 58 Untertests bestanden.

- 37 neue Regressionen: Originalidentität, Marktzeitraum, Seitenwechsel,
  doppelte Anbieter, ungültige Gegenquote, 1,20 ohne Rundungsloch, Herkunfts-
  und Zeitbindung, Korrekturen, Parallelzugriff, Wiederverwendung, Tagesbudget,
  Datengeheimnisse in Fehlern sowie echte Consumer-Karten.
- Native VPS-Vorprüfung: NJD–NYI vom 20.09.2026, 17:00 UTC anhand NHL-ID
  auf New Jersey Devils–New York Islanders / API-Sports-Spiel 444565 gebunden.
  Der Anbieter lieferte hierfür zu diesem Zeitpunkt keine Quoten, keinen Fehler.
  Dies ist kein Beleg, dass jedes NHL-Spiel ein Angebot erhält.
- Basketball: tatsächlicher Quotenendpunkt erfolgreich geprüft; der aktuelle
  App-Bestand enthielt keine NBA-/Euroleague-Modellspiele. Parser/Consumer sind
  separat mit Regressionen geprüft, nicht als aktuelle Live-Auswahl ausgegeben.
- Keine Modell-, Verletzungs-/Müdigkeits- oder allgemeine Jobreparatur in diesem
  Patch. Vor Deployment waren Wettfinder- und Tennisdienst bereits fehlgeschlagen.

## Kostenlose Möglichkeiten für Tennis und E-Sport

- Vorhandenes The-Odds-API-Feld weiterhin ohne Schlüssel. Der Anbieter bietet
  Tennis im kostenlosen Starter-Tarif mit 500 Credits/Monat; Registrierung und
  eigener Schlüssel erforderlich: https://the-odds-api.com/ und
  https://the-odds-api.com/sports-odds-data/sports-apis.html
- PandaScore Statistics enthält keine Buchmacherquoten; separates Odds-Produkt:
  https://developers.pandascore.co/docs/frequently-asked-questions
- Odds-API.io bewirbt teilweise weiterhin kostenlose Zugänge, die aktuelle
  Preisseite setzt neue kostenlose Schlüssel aber ausdrücklich unbefristet aus:
  https://odds-api.io/pricing
- FieldFunded nennt Tennis/E-Sport und einen kostenlosen Tarif mit 10.000
  Anfragen/Monat ohne Kreditkarte: https://www.fieldfunded.com/
  Neuer Account/Schlüssel erforderlich. Datenqualität, konkrete Buchmacher-
  Zuordnung und Echtbetrieb sind ohne Zugang noch nicht überprüft. Kein Abo,
  kein Account angelegt und keine ungetestete Quelle als live behauptet.
- Öffentliche ESPN-Probe: die abgefragten Tennis- und NHL-Spielpläne lieferten
  keine Buchmacherquoten. Keine Quote aus Modellchance oder Favoritenlabel erfunden.

Cricket bleibt ausgenommen. Automatische Tennis-/E-Sport-Quoten sind ohne
zusätzlichen Zugang weiterhin nicht vollständig erledigt.
