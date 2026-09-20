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

## Live-Nachweis

Funktionscommit `f4677e2799a787de0a7f77ac32ccb9e6014a374c` auf main/GitHub/VPS.
App und Caddy aktiv, interne und öffentliche Healthchecks `ok`. Vorhandener
Wettfinder-Timer nach dem kontrollierten Codewechsel wieder aktiv.

Echter Gesamtabruf: vier NHL-Spiele geprüft und exakt zugeordnet, zwei
Auswahlquoten gespeichert, keine Abruffehler. Boston Bruins–Washington Capitals:
Boston 1,86, Washington 1,96. Quotencache: 3.023 Bytes. Das aktuelle NHL-Modell
liefert noch keine Seite/Wahrscheinlichkeit (`selection_key=open`); daher
keine der beiden Quoten als angeblich zu einer Modellauswahl gehörig angezeigt.
Die lesende Consumerprüfung renderte 116 RisikoBet-Szenarien, 35 vorhandene
Preise (Fußball), keine sichtbare Auswahl mit passender Quote unter 1,20.
Dies ist keine visuelle Browserabnahme und kein erfolgreicher Tennis-Gesamtlauf.

## Kostenlose Möglichkeiten für Tennis und E-Sport

- The Odds API wurde inzwischen vom Nutzer kostenlos registriert. Der Schlüssel
  wurde außerhalb des Repositorys übergeben und am VPS in `/etc/betboy/betboy.env`
  als `ODDS_API_KEY` installiert (root:betboy, 0640). Die neu gestartete App erhält
  ihn; native Konfigurations- und API-Prüfung erfolgreich. 500 Credits/Monat:
  https://the-odds-api.com/ und
  https://the-odds-api.com/sports-odds-data/sports-apis.html
- PandaScore Statistics enthält keine Buchmacherquoten; separates Odds-Produkt:
  https://developers.pandascore.co/docs/frequently-asked-questions
- Odds-API.io bewirbt teilweise weiterhin kostenlose Zugänge, die aktuelle
  Preisseite setzt neue kostenlose Schlüssel aber ausdrücklich unbefristet aus:
  https://odds-api.io/pricing
- FieldFunded nennt Tennis/E-Sport und einen kostenlosen Tarif mit 10.000
  Anfragen/Monat ohne Kreditkarte: https://www.fieldfunded.com/
  Die angeforderte Free-Registrierung wurde im isolierten Browser versucht;
  Anbieterformular: „Network error“, CORS-Fehler beim Preflight auf `/api/stripe/free-key`.
  Kein bestätigter Account/Schlüssel. Datenqualität, Buchmacher-Zuordnung und
  Echtbetrieb bleiben ungeprüft; kein kostenpflichtiges Abo angelegt.
- Öffentliche ESPN-Probe: die abgefragten Tennis- und NHL-Spielpläne lieferten
  keine Buchmacherquoten. Keine Quote aus Modellchance oder Favoritenlabel erfunden.

## Tennis-Aktivierung und Budgetnachweis

- Funktionscommit `8e2581ea513ba0b4377067656352f1c8d0f02ef6` auf main/GitHub/VPS.
- Bestehender gemeinsamer Budgetzähler, keine zusätzliche Datenbank/Schemaänderung:
  500 Credits pro UTC-Kalendermonat, davon 25 Reserve, höchstens 16 reservierte
  Credits pro Tag. Markt-/Regionskosten werden vor dem Abruf atomar reserviert;
  parallele Prozesse teilen das Budget. Unklare/fehlgeschlagene Abrufe bleiben
  vorsichtig mit ihrem maximalen Creditbedarf reserviert. Keine automatische
  Tarifänderung. Provider-Restkontingent kann die lokale Reserve nur senken.
- Tennis fasst identifizierte Events desselben Turniers zusammen (ein Markt,
  eine Region = höchstens ein Credit für die gemeinsame Anfrage). Doppelte oder
  fremde Event-IDs, geänderte Gegner und unpassende Starts erhalten keine Quote.
- Auch der ältere SmartBet-Abruf benutzt denselben geschützten Transport.
  Quotenbudget erschöpft bedeutet fehlende Preisabdeckung, keinen Modellfehler.
- Regression: 753 Tests und 32 Untertests grün; Monatswechsel, Parallelzugriff,
  Mehrfachkosten, Header-Abgleich, fehlende Datenbank, Schlüssel in Fehlertexten,
  Turnier-Batching sowie die bestehenden Verbraucher abgedeckt.
- Reale VPS-Probe nach Aktivierung: WTA Singapore Open, sechs zukünftige Events.
  Kasatkina–Sasnovich (21.09.2026 03:00 UTC), beste Angebote 1,68 / 2,40, jeweils
  sieben Buchmacher; keine Abruffehler. Kontingent anschließend 499/500.
  Diese reine Anschlussprüfung wurde nicht als Modellprognose/Tipp gespeichert.
- Native App-Umgebung enthält den neuen Schlüssel, interner Healthcheck `ok`.
  Der laufende Sportscan wurde nicht beendet. Kein neuer Nachweis eines
  erfolgreichen vollständigen Tennis-Modelllaufs oder verbesserter Wettqualität.

Cricket bleibt ausgenommen. E-Sport-Quoten sind weiterhin offen.

## E-Sport-Fortsetzung: Zugangsvoraussetzung geprüft

- FieldFunded-Free-Formular erneut mit der freigegebenen Nutzeradresse versucht.
  Wieder CORS-Preflightfehler auf `https://api.fieldfunded.com/api/stripe/free-key`,
  also weiterhin kein bestätigter Schlüssel. Getrennte Playwright-Sitzung;
  kein persönliches Browserprofil und keine Umgehung der Anmeldesperre.
- Bestehender The-Odds-API-Zugang: `GET /v4/sports?all=true` lieferte HTTP 200
  und 179 Einträge, keinen Eintrag für E-Sport/CS/Dota/LoL/Valorant. Diese
  kostenlose Katalogprüfung ließ das Kontingent auf 499.
- OddsPapi wurde als Alternative anhand offizieller Dokumentation und des
  tatsächlichen Anmeldeformulars geprüft. Formular: Free, alle Sportarten und
  Buchmacher, 250 Anfragen/Monat; Passwort und hCaptcha sind erforderlich.
  Der Nutzer erhielt die Anmeldeseite für den internen Browser und eine
  zugriffsbeschränkte Schlüsseldatei außerhalb des Repositorys. Kein Schlüssel,
  Passwort oder anderweitiges Kontogeheimnis in diesem Bericht.
- Aktueller Blocker: Nutzerregistrierung/CAPTCHA und Schlüsselübergabe. Keine
  abgeschlossene Registrierung, keine kostenpflichtige Bestellung, keine neue
  Produktionsanbindung und kein realer OddsPapi-Quotenabruf nachgewiesen.

Anschlussvertrag nach Schlüsselübergabe:

1. Mit dem kostenlosen `GET /v4/account` die aktive Free-Subscription und das
   tatsächliche Restkontingent prüfen; dessen Antwort enthält den Schlüssel und
   darf weder protokolliert noch als Testfixture übernommen werden.
2. Disziplin, Event, Teilnehmerseiten, Beginn und vollständigen Match-/Serien-
   Sieg exakt binden. Kein Ersatz durch einzelne Maps, ein gleichnamiges Team
   einer anderen Disziplin, Prediction-Market-Preise oder Modellquoten.
3. Identifizierte Buchmacher, aktive Angebote, Dezimalquoten und Anbieterzeiten
   prüfen. Datenbeispiele aus einer Anleitung sind kein aktuelles Live-Angebot.
4. Gemeinsam für alle Verbraucher abrufen, vorhandenen Budgetzähler nutzen,
   keine neue Historien-Datenbank. OddsPapi zählt auch Sport-/Spiel-/Marktkataloge
   und Fehlerantworten; höchstens der freigegebene Free-Tarif, keine Tarifänderung.
5. Gegen falsche Seite/Disziplin/Map, doppelte Events, unklare Zuordnung, alte
   Preise, Quote unter 1,20, Quotenbudget und Schlüssel in Fehlern testen.
   Erst nach tatsächlichem Anschlussnachweis Produktionsfreigabe behaupten.

Primärquellen:

- Registrierung: https://oddspapi.io/us/sign-up
- E-Sport-Angebot: https://oddspapi.io/blog/esports-odds-api-guide-how-to-get-pinnacle-cs2-lol-data-for-free/
- Anfragekosten: https://oddspapi.io/us/docs/requests-and-quota
- Kontoprüfung: https://oddspapi.io/us/docs/get-account
