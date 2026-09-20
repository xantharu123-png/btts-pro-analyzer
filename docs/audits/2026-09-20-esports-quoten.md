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
Zusätzlich 218 Anschlusstests auf dem synchronisierten lokalen main bestanden.
Bestehende Tennis-/Kontext-/Workerprobleme sind nicht Gegenstand dieses Anschlusses.

## Tatsächlicher VPS-Anschluss

- Funktionscommit `696635d7144d22b034f3d0863dabbfbc25bbd104` auf main/GitHub/VPS.
  Vorheriger VPS-Stand `c80d5cc`; Fast-forward ohne Überschreiben fremder Änderungen.
- Schlüssel atomar in `/etc/betboy/betboy.env` ergänzt, root:betboy 0640.
  Gegenprobe als Appnutzer: Konfiguration stimmt, Free-Tarif aktiv, App erhält
  den Schlüssel nach Neustart. Keine Ausgabe des Schlüssels oder Account-Rohdaten.
- Echter vollständiger Abruf: `complete`, null Fehler, sieben E-Sport-Spiele
  in einem Cache von 8.987 Bytes; fünf Anfragen. Vorher 238/250 Anfragen frei.
- Spiele: Sparta eSports–Inox Division, Bestia–Bounty Hunters, Team Liquid–Flyquest,
  Fennel–Cupid eSports, Galions–Saigon Warriors, Solary–Zsk und Sashi eSport–Fokus.
  CS2 und LoL lieferten in dieser Probe Preise; keine behauptete reale Dota-/
  Valorant-Abdeckung ohne Angebot. Parser beider Disziplinen separat getestet.
- Zunächst keine passenden aktuellen Modelle: der erfolgreiche morgendliche
  E-Sport-Scan ließ nur vier noch kommende Valorant-Modelle am 24./25.09. übrig,
  also außerhalb des bepreisten Fensters. Bestehenden E-Sport-Dienst einmal
  erneut ausgeführt: Ende 18:46:36 CEST, Exit 0, 30 Spiele, acht neue Modelle.
- Danach zwölf kommende Datenbankmodelle, davon zwei exakt bepreist:
  Team Liquid–FlyQuest (Team Liquid 1,267) und Galions–Saigon Warriors (Galions
  1,41). Native Karten mit diesen echten Modellen/Quoten erfolgreich gerendert;
  Wahrscheinlichkeit unverändert, weder freigegebener Tipp noch Einsatz erzeugt.
- Keine erzwungene unscharfe Zuordnung von `SPARTA` zu `Sparta eSports`.
  Fehlende Angebote bleiben unbekannt, auch wenn eine andere Quelle ähnlich heißt.
- Gemeinsamer Wettfinderlauf startete bereits 18:37:11 vor dem Codewechsel und
  läuft zum Zeitpunkt dieser Prüfung noch. Seine Veröffentlichung vom 18:18
  enthält noch keine heute kommende E-Sport-Auswahl. Daher noch kein behaupteter
  aktueller sichtbarer Tipp oder erfolgreicher Gesamtlauf. Ein neuer nativer
  Scan allein ersetzt nicht dieses abschließende Veröffentlichungsartefakt.
- App/Caddy und Wettfinder-Timer aktiv; interne/öffentliche Healthchecks `ok`.
  Auf dem VPS kein pytest installiert: keine Linux-Pytest-Suite behauptet und
  keine Pakete nachinstalliert. Stattdessen echte Abruf-/Modell-/Renderprüfungen.
- Produktionsmodelle durch den reinen Quotenabruf bytegleich geblieben.
  Modelländerungen ausschließlich durch den regulären E-Sport-Dienst.
  Keine Bereinigung, zusätzliche Produktionsdatenbank oder Backupaktivierung.

## Nachprüfung von Veröffentlichung und Nachweisspeicherung

Stand 20:45 CEST: `runtime_state/wettfinder_latest.json`, erzeugt um
20:16:46 CEST, enthält 68 Modellkandidaten und eine heute kommende E-Sport-
Auswahl. E-Sport-Quelle: acht Modelle geprüft, zwei exakt passende Preise,
sechs ohne Angebot; kein E-Sport-Abruffehler. Die ausstehende Veröffentlichung
des vorherigen Abschnitts ist damit überholt, nicht jedoch die übrigen Fehler.

Die tatsächliche öffentliche Website wurde in einer isolierten Playwright-
Sitzung geprüft; der interne Browserdienst ließ sich nicht starten. Kein
Zugriff auf den persönlichen Browser. DOM-Nachweis und Screenshots unter
`output/playwright/esports-{wettfinder,riskobet}-live-20260920.png`; null
Console-Fehler, neun Warnungen. Keine Wette erfasst oder Geldbewegung erzeugt.

- Wettfinder: LoL, Team Liquid gegen FlyQuest, Sieg Team Liquid, beste
  beobachtete Quote 1,267 (Anzeige 1,27), Buchmacher 1xbet. Modell bleibt 60,9 %.
- RisikoBet: dieselbe Serie, Außenseiter FlyQuest, Serien-Sieg mit Quote 3,80.
  Keine zweite unabhängige Bestätigung und keine historisch bestätigte Empfehlung.
- RisikoBet-Map-Szenario: weiterhin ohne passende Quote. Serien-Sieg-Preis wird
  weder auf einzelne Maps noch auf „mindestens eine Map“ übertragen.
- Daily3: keine passende Auswahl. Keine Auffüllung mit zusätzlichen Scheintipps.

Ein konkreter Restfehler war trotz sichtbarer Preise reproduzierbar: Bei der
prospektiven Quotenaufzeichnung fehlte `competition` in `quote_identity`.
Der korrekte Disziplinvergleich lehnte deshalb die echte E-Sport-Quote ab
(`quote_rejected_count=1`). Der zuerst fehlschlagende Regressionstest zeigt
dieselbe Ablehnung. `94fa36f` erhält die Disziplin ausschließlich für neue
E-Sport-Datensätze, wenn sie vorhanden ist. Andere Sportarten und bestehende
E-Sport-Identitäten ohne dieses Feld bleiben unverändert. Keine Schemaänderung,
keine Neuschreibung alter Prognosen und keine Preis-Einsatzfreigabe.

421 betroffene Tests bestanden, einschließlich falscher/fehlender Disziplin,
unveränderter Altidentitäten, wiederholter Aufnahme und `executable=0` für reine
Abrufbeobachtungen. Der Parallel-Budgettest startet auf einem initialisierten
WAL-Zähler wie die Produktion; ein nicht verfügbarer Zähler wird separat als
Abbruch ohne Anbieteranfrage geprüft. Keine behauptete Reparatur gleichzeitiger
Erstanlage einer leeren SQLite-Datei und kein behaupteter Vollsuite-Lauf.

Die abgeschlossene gemeinsame Runde 20:07–20:24 CEST endet weiterhin degraded
mit 17 operationalen Fehlermeldungen: 16 im Fußball und ein Tennis-Sammelfehler.
Der Tennis-Refresh versuchte acht Prognosen (1523–1530), keine davon erfolgreich;
alle melden `ContextIntegrityError`. Fußball enthält sechs nicht aktualisierte
Spielmodelle und weitere Kontext-/Abdeckungsmeldungen. Diese Fehler sowie die
vollständige Verletzungs-/Müdigkeitswirkung sind **nicht** durch den E-Sport-
Quotenanschluss behoben. Vor Deployment den laufenden Worker auch im Zustand
`activating` als beschäftigt behandeln, nicht nur `active` prüfen.

Funktionskorrektur `94fa36fd194b839350af4b6ad1d56476231b1e79` auf lokalem main,
GitHub main und VPS verifiziert. Weitere 142 direkte Anschlusstests auf main
bestanden. Deployment am 20.09. um 20:55 CEST erst nach Ende des laufenden
Workers (20:37:20–20:53:20, weiterhin Exit 1/degraded), unter Deployment-Lock,
sauberem Produktionscheckout und kurz angehaltenem, anschließend wieder
aktiviertem Wettfinder-Timer. Kein Worker abgebrochen. Nur Code-Fast-forward
und App-Neustart; keine Datenmigration, Sicherung oder Bereinigung.

Native read-only Gegenprobe aus der aktuellen Veröffentlichung 20:46:26 CEST:
Disziplin LOL, Sieg Team Liquid, ein Anbieterpreis 1,267 wird akzeptiert,
`executable=0`; dieselbe Quote mit falscher Disziplin CS2 wird abgewiesen.
Modell unverändert, null Datenbank-Schreibvorgänge und null Anbieteranfragen.
Bestehende Nachweiszeilen werden nicht rückwirkend umgeschrieben. Der nächste
reguläre gemeinsame Lauf nutzt den korrigierten Aufnahmeweg.

App und Caddy aktiv, interner und öffentlicher Healthcheck `ok`. Wettfinder-
Timer aktiv, nächster Termin 21:07 CEST. Während des geplanten Neustarts erhielt
die bestehende Browserverbindung vorübergehende WebSocket-/502-Meldungen; nach
frischem Start der isolierten Sitzung null Console-Fehler (neun unveränderte
Browserwarnungen). Team Liquid weiterhin sichtbar mit Quote 1,27. Daily3 auch
in der echten Ansicht ohne passende Auswahl; Tagesbudget wurde nicht bestätigt.

## Primärquellen

- https://oddspapi.io/us/docs/get-account
- https://oddspapi.io/us/docs/requests-and-quota
- https://oddspapi.io/us/docs/get-fixtures
- https://oddspapi.io/us/docs/get-markets
- https://oddspapi.io/us/docs/get-odds-by-tournaments
