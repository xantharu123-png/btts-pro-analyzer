# Quotenversorgung – 10.10.2026

## Auftrag und belegte Ursachen

Die neue manuelle Preisfilterung ersetzt keinen funktionierenden Abruf. Echte
Quoten werden unabhängig vom Modell beschafft und exakt an Ereignis, Auswahl,
Markt und Anstoßzeit gebunden; weder Wahrscheinlichkeiten noch Rangfolge werden
aus einem Buchmacherpreis abgeleitet.

- Automatischer Fußball und Preis-only-Refresh verwendeten noch die
  Zehn-Fixture-Grenze, obwohl der veröffentlichte Modellkatalog erheblich größer
  ist. Ein Offline-Replay zeigt 90 Modellspiele, aber nur zehn Preisabrufe.
- Auf dem VPS bestätigt der gespeicherte Tagesstand vom 10.10. um 02:12 UTC:
  946 Fußballkandidaten, 144 geprüfte Märkte aus zehn Spielen. Das war kein
  Beleg, dass alle veröffentlichten Spiele auf einen Preis geprüft wurden.
- Der normale Tennis-Siegerabruf war bereits ein vollständiger Sportbatch.
  Sein Gegenpreis-Cache bewahrte aber nur zehn Ereignisse/20 Seiten. Bei einem
  späteren Favoritenwechsel verloren sechs von 16 Spielen gelieferte Quoten.
- Die manuelle Tennis-Suche startete das Modell, holte aber keine neuen Preise.
  Sie las ausschließlich den gespeicherten automatischen Preisstand.
- Der gemeinsame Doppelte-Chance-Parser verstand `Home/Draw`, aber nicht die
  ebenfalls in vorhandenen Provider-Fixtures enthaltene Schreibweise `1X`.
  Diese Alias-Lücke ist lokal reproduziert; keine Aussage über den Wortlaut
  einer heute live neu angeforderten Providerantwort.
- Serieller Fußball- und sportübergreifender Tennis-Abruf verwendeten die Uhr
  des Batchbeginns. Später empfangene aktuelle Quoten erschienen so fälschlich
  als zukünftige Beobachtungen. Der Preis-only-Refresh wertete außerdem vor
  statt nach dem tatsächlichen Abschluss aus.
- E-Sport- und Basketball/Eishockey-Preisproducer waren beim quotenfreien
  Modellumbau deaktiviert worden; lesende Consumer existieren weiterhin.

## Begrenzte Reparatur

- Fußball prüft den vollständigen zuordenbaren, bereits begrenzten Modellpool
  mit maximal 1.200 Fixtures statt der ersten zehn. Ein Request je Spiel,
  nicht je Wettart. Bestehender API-Budgetschutz bleibt unverändert.
- Tennis bewahrt maximal 1.200 aktuelle Ereignispaare/2.400 Seiten und höchstens
  8 MiB. Keine Preisgeschichte und keine zusätzlichen Requests für Gegenquoten.
  Der vollständige Cache wird einmal am Batch-Ende zusammengeführt, nicht
  nach jedem Spiel erneut geparst/kopiert. Ein größerer nativer Ereignispool
  meldet die Grenze vor HTTP, statt erfolgreich geladene Preise still zu verlieren.
- Explizite manuelle Tennis-Suche fragt reale H2H-Preise nach dem Modelllauf ab.
  Beide Seiten landen nur im Job-/Sitzungsergebnis. Datumsfensterwechsel nutzt
  wieder den passenden gemeinsamen Cache; Filter/Rerender bleiben lesend.
- Doppelte Chance normalisiert nur die drei exakten Token `1X`, `X2`, `12`
  im vollständigen `Double Chance`-Markt. Halbzeitmärkte, fremde Spiele und
  falsche Seiten werden nicht als Ersatz zugelassen; Buchmacher bleiben dedupliziert.
- Reale Antwort-Empfangszeiten werden je Response verwendet. Explizite
  historische Testuhren bleiben deterministisch; Abrufzeit wird nicht durch
  Rendern oder Filteränderungen erneuert.
- E-Sport sowie Basketball/Eishockey verwenden wieder ihre vorhandenen
  kontingent- und cachebegrenzten Preisproducer. Implizite Requests nur für
  Produktion mit eingerichtetem Schlüssel und Modell-/Snapshot-Ereignissen;
  isolierte Replays bleiben offline. Exakte E-Sport-Cachepreise werden übernommen.
  Cacheübernahme behauptet keinen neuen nativen Einzelversuch; der echte
  Refreshbericht ist separat. `bookmaker_data_used` berücksichtigt diese Fakten.
  Der vorhandene Teamsport-Budgetrahmen bleibt acht Ereignisse je Sport /
  35 Sekunden; keine vollständige Preisabdeckung darüber behaupten.

## Abdeckung bleibt eine Tatsachenfrage

Aktuell sind 80 von 90 Fußballdefinitionen direkt zugeordnet. Zehn Bereichs-
und Kombinationsmärkte haben kein verifiziertes Provider-Mapping. Das beweist
eine fehlende Anbindung, nicht, dass der Provider diese Märkte anbietet. Keine
Quote aus Modellwahrscheinlichkeit, ähnlicher Linie oder Einzelkomponenten
erfinden. Der Anbieter garantiert auch nicht für jedes Ereignis und jeden
Markt ein aktuelles Buchmacherangebot:

- [API-Football: Coverage, Pre-Match-Odds und Marktendpunkte](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
- [The Odds API: angebotene Märkte und Ereignisantworten](https://the-odds-api.com/liveapi/guides/v4/)

Ein aktiver expliziter Preisbereich kann nur tatsächlich erhaltene passende
Preise vergleichen. Dieser Patch sperrt unbepreiste Modellprognosen außerhalb
dieses Filters nicht pauschal und führt keine neue Echtgeldfreigabe ein.

## Prüfung und Veröffentlichung

Test-first-Reproduktionen und unabhängige Gegenprüfung: vollständiger
Fußballpool, erhaltene Tennis-Gegenseiten, exakte DC-Zuordnung, Antwortuhren,
manueller Job-/Sitzungsübergang, keine Rerender-Abfrage, keine Secret-Ausgabe.
Frische gemeinsame Abnahme nach allen Codeänderungen: **724 bestanden in
39,30 s**. Darin echte Parser mit offline Provider-Fixtures, Job/Sitzungs-
Integration, Quoten-/Prozentfilter, Refreshguards, Kontingent/Cooldown,
Daily3, gemeinsame Oberfläche und unveränderte Modelle. Kein echter API-Request.
Unabhängiger Abschlussreview: keine verbleibenden bestätigten P1/P2 im
begrenzten Patch; zusätzlich zehn eigene In-Memory-Gegenprüfungen bestanden.
Veröffentlichung wird anschließend mit ihrem eigenen Nachweis ergänzt.

Die geerbte Vollsuite aus dem vorherigen UI-Turn ist beendet: 12.810 bestanden,
zwei Fehler, 97 Skips und 143 Untertests in 54:14 Minuten. Der Checkout wurde
währenddessen weiterbearbeitet; deshalb ist dies keine Vollabnahme des finalen
Patches. Beide Fehler betreffen `AppTest.from_function(_manual_screen)`:
generiertes Skript ruft eine nicht definierte Funktion auf. Die zwei Fälle
laufen im frischen 724er-Lauf grün; Ursache wird separat geprüft, nicht durch
Ändern des Produktivcodes oder Abschwächen der Assertions kaschiert.
Zeitstempel bestätigen den gemischten Lauf: Start 09:45:01 UTC, Testdatei
09:48:04 UTC geändert, AppTest-Fehler erst 10:32:19 UTC. Streamlit liest beim
Aufruf `inspect.getsourcelines` erneut, während das Funktionsobjekt aus dem
früher importierten Modul stammt. Kein fehlender Produktiv-Renderer nachgewiesen.
Kein neues Backup, zusätzlicher Sportscan,
Preis-only-Produktionslauf, Datenmigration oder Bereinigung für diesen Patch.

Die vorhandenen Sportdienst-Fehlzustände sind separate offene Aufgaben:
Der reguläre Football-Shadow um 12:22 meldete eine fehlende aktuelle
Bet365-Beobachtung sowie zwei alte nicht vollständig gültige abgerechnete
Belege. Seine Daten wurden nicht verändert. Ein UI-/Abrufcode-Deployment
bestätigt weder die Reparatur dieser Daten noch bessere Wett-Rendite.
