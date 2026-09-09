# C1: Wetter und beobachtete Fußballbelastung – begrenzter Softwarestand

Stand: 9. September 2026. Ausgangscommit
`ce7f0700049e8e75e7b01705ebdea7b93b52e44b`; isolierter Zweig
`codex/kontext-c1-wetter-20260909`.

## Getrennte Ergebnisse

| Nachweis | Ergebnis |
| --- | --- |
| Software | CPU-only Wettertransport/-merkmale und native beobachtete Spielzeitlinie mit B1-Receipts implementiert. Keine Anfrage, Aktivierung, persistente Laufzeitänderung oder Wahrscheinlichkeitsschätzung in diesen Bausteinen. |
| Verwendbare reale Daten | Die vorhandene, tatsächlich am 07.09. empfangene API-Football-Probe belegt zwei native Fixtures und Status/Team-/Wettbewerbskennungen. Nur eines war abgeschlossen. Sie belegt weder eine vollständige Belastungshistorie noch genaue Spielenden oder eine aktuelle Wetterantwort. |
| Wetterquelle | **Offen.** Kein geprüfter OpenWeather-Adapter für den neuen Transport, kein geteiltes geprüftes Wetterkontingent, keine belegten exakten Stadionkoordinaten/-revisionen und keine nachgewiesene Ausgabezeit im bestehenden Pfad. |
| Empirie | **Offen.** Keine neuen Koeffizienten, kein C1-Training, kein unangetasteter 200-Event-Test, keine C1-Effektfreigabe. Synthetische Tests beweisen ausschließlich Softwaremechanik. |
| Produktive Aktivierung | **Keine.** Keine Jobs, UI, bestehende Provider, Cricket-, Konto- oder Ticketregeln geändert. Kein Push, VPS-Pull oder Deployment durch diese Teilaufgabe. |

Das gesamte Paket C1 ist damit nicht als fachlich abgeschlossen auszugeben.
Ein fehlender neuer Kontextnachweis entfernt keine vorhandene Basisprognose.

## Quellenentscheidung vor Implementierung

Der vollständige C1-Plan, `source-readiness-weather.md`, der Kontext-Datenaudit,
die freigegebene Spezifikation und beide zentralen Vertragsentscheidungen wurden
gelesen. Der Controller bestätigte ausdrücklich die begrenzte CPU-only-Arbeit.

Der aktuelle Quellstand ruft OpenWeather in `ChallengeDataProvider.weather()`
direkt über `requests.get` ab. Der vorhandene `api_budget.py`-Governor schützt
API-Football, nicht eine gemeinsam kontogeprüfte OpenWeather-Quelle. Der
Wettercache ist ein Provider-RAM-Cache nach Stadt/Land/Spielstunde, kein
zeitgestempelter Rohantwortspeicher mit Stadionprovenienz. Unter der Bedingung
"nur mit garantiertem Governor" wurde deshalb **kein Wetter-GET** gesendet.
Ebenso keine weitere Football-API-Probe, kein Archivabruf, keine neue Lizenz,
kein Tarifwechsel, keine Zugangsdaten gelesen und kein TLS-Schutz verändert.

Der bestehende Wetterpfad übernimmt einen ausgewählten `list.dt` als
`forecast_at`; er erfasst weder dessen Ausgabezeit noch eine belegte
Gültigkeitsdauer. Die zuvor dokumentierte Unterscheidung von Vorhersagepunkt und
Ausgabezeit darf nicht durch `issued_at=forecast_at` umgangen werden. Die
[offizielle bisherige Forecast-Dokumentationsadresse](https://openweathermap.org/api/forecast5)
lieferte beim Webwerkzeug-Recheck am 09.09. lediglich eine allgemeine
Anwendungsseite; der verlinkte API-Einstieg verwies auf eine andere API-Version.
Dadurch wurden **keine neuen Feld-, Intervall-, Lizenz- oder Kontingentannahmen**
verifiziert. Es wurde insbesondere nicht auf ein anderes Wetterprodukt gewechselt.

## Neue Softwaregrenzen

### Wetter

`context_sources/weather.py` besitzt ausschließlich den ausdrücklich internen
Transport `football-weather-transport-v1`. Das ist kein Parser für einen frei
übergebenen OpenWeather-Rohblob. Ein zukünftig geprüfter owning Source-Adapter
muss zuvor Quelle, tatsächlichen Empfang, Event-/Stadionzuordnung, Einheiten und
Zeitsemantik feststellen. Hashes beziehungsweise gültige JSON-Felder ersetzen
diesen Quellenbeweis nicht.

- Geschlossenes Datenobjekt mit vollständigem Eventhash, getrennter
  Stadion-/Koordinaten-/Dachrevision und expliziten Celsius, m/s und mm/3h.
- `forecast`, `forecast_archive`, `actual` und `reanalysis` bleiben verschieden.
  Nur die ausdrücklich aktuelle Vorhersagevariante ist für diese Merkmale
  vorgesehen. Archivfreigabe/Resolver bleiben eine eigene offene Aufgabe.
- Ausgabezeit, Vorhersagepunkt und belegtes halboffenes Gültigkeitsintervall sind
  getrennt. Unbekannte Ausgabe beziehungsweise unbekanntes Intervall bleiben
  `null`. Ein bloßer Punkt wird ohne Endgrenze aufbewahrt, nicht auf drei Stunden
  verbreitert. Es wird keine historische Veröffentlichung behauptet.
- Prospektive B1-Receipts, unveränderte Drei-Stunden-Frische, aktueller Termin,
  explizite Ausgabe vor Entscheidung und Intervallabdeckung sind erforderlich.
  Eine neue unbekannte Revision kann keine alte numerische Beobachtung auffrischen.
- Fehlende Stadion-/Dachbelege bleiben fehlend. Belegt geschlossenes Dach macht
  ausschließlich diesen **Outdoor-Wetterfaktor** nicht anwendbar; daraus folgt
  keine Behauptung über Hallentemperatur oder allgemeine Wetterunabhängigkeit.
- Temperatur, Wind, Niederschlag, Schnee und Prognosehorizont bleiben separate
  Merkmale. Fehlender Regenwert ist nicht null Millimeter. Vorhandene gemessene
  Null bleibt Null. Keine Wetterprozente und kein Wahrscheinlichkeitsabschlag.

Sämtliche qualifizierten Wettertransports in den Tests sind ausdrücklich
**synthetisch** und werden nicht als reale Providerfixtures ausgegeben.

### Spielbelastung

`context_models/football_load.py` besitzt eine getrennte native Spielzeitlinie.
`normalize_football_schedule` übernimmt beim real belegten API-Schema ausschließlich
Fixture-/Team-/Wettbewerbs-/Saisonkennungen, Status und angesetzten Beginn plus
tatsächlichen Antwortempfang. Spielende, Spielbeginn und Dauer werden dabei
**nicht** aus `date`, `elapsed=90`, `extra` oder Halbzeitfeldern erfunden.

Der zusätzliche `football-completed-transport-v1` ermöglicht nur die Mechanik
eines später intern quellenaufgelösten tatsächlichen Endes/Dauerwerts. Seine
synthetischen Nachweise sind keine neue Providerabdeckung. Fehlende Spieldauer
ist `null`, nie null Minuten; eine nachgewiesene Matchdauer ist außerdem keine
pauschale Spielerminute für alle Kaderspieler.

- Vollständige gemeinsame Matchrevision pro beiden nativen Teams; keine
  Namenszuordnung, keine national/international doppelt gezählten Fixtures.
- CSV-Pseudokennungen und explizite fremde CSV-Herkunft werden nicht als native
  API-Football-Belege akzeptiert. Unbekannte/Preisfelder des echten Rohschemas
  werden aus der ausdrücklich erlaubten Sportprojektion weggelassen. Der
  geschlossene interne Transport lehnt Zusatzfelder ab.
- Neuere Teilnehmer-/Termin-/Nichtgespielt-Revisionen verdrängen alte
  Abschlussbehauptungen eventweit. Teilprojektionen dürfen keine alte Gegenseite
  ausleihen; gleichzeitige widersprüchliche Revisionen bleiben widersprüchlich.
- Nur vor der Entscheidung empfangene Abschlüsse; tatsächliches Ende muss vor
  dem Cutoff liegen. Ein Spielende exakt am Cutoff ist keine frühere Leistung.
- Fenster sind `[cutoff-N*24h, cutoff)` für 1/3/7 Tage, zugeordnet nach belegtem
  tatsächlichem **Ende**, nicht nach Empfang oder Termin. Unbekanntes Ende darf
  solche Fenster nicht numerisch füllen.
- Mindestpause zum nächsten angesetzten Beginn aus tatsächlichem
  Ergebnisempfang; exakte Pause nur relativ zu vollständig zeitbekannten
  **beobachteten** Spielen. Keine Behauptung einer vollständigen Teamhistorie,
  Reisezeit, individueller Ermüdung oder medizinischen Diagnose.
- Signierte Heim-minus-Auswärts-Merkmale verwenden exakt die vereinigten
  Referenzen ihrer beiden Operanden. Eine fehlende Seite wird nicht zu null.

Eine echte, vollständige native Zeitlinie desselben Teams über nationale und
internationale Spiele wurde mit den verfügbaren zwei Realbeispielen **nicht**
nachgewiesen; die Deduplizierungsrechnung ist dafür lediglich synthetisch getestet.

### Identität und anschließende Modelle

Die additiven Funktionen sind:

```text
normalize_weather(event, response, *, observed_at, source_kind)
weather_window(*, issued_at, valid_from, valid_until, decision_at, kickoff)
normalize_football_schedule(rows, *, observed_at, source_schema=...)
football_schedule_features(event, completed, *, cutoff, base)
football_weather_features(event, observations, base, *, cutoff)
```

Beide Merkmalsvektoren binden `football-context-reference-v2` mit dem Hash der
**vollständig validierten Basis**, dem Hash des **vollständig validierten
Events** und `preprocessing=[]`. Bekannte native Basisteams bleiben auch bei
unaufgelöster historischer Kaderzuordnung bindend. Die Basis wird nicht verändert.

Neue Versionen `football-observed-load-v1` und `football-weather-features-v1`
werden vom bestehenden injury-only B5-Effekt ausdrücklich **nicht** akzeptiert.
Ein künftiges separates Wetter-/Belastungsartefakt, Ablationen,
Interaktionsvarianten sowie D1/D2 müssen gesondert implementiert und bewertet
werden. Es wird keine alte Effektfreigabe übertragen.

## Reale, sanitierte Quellprojektion

Fixture: `tests/fixtures/context/football/c1-schedule-20260907.json`.
Original: `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/football-source-probe-20260907.json`.
Original-SHA256:
`5314091f34eb0927cab41ba0b22fb4cea45eebbb57ceaf181b735859e3c0aab4`.
Tatsächlicher Empfang: **2026-09-07T14:46:05.939454+00:00**.

Die Projektion bewahrt die relevanten Originalwerte für 1570343 (FT) und
1593305 (damals NS). Ein Test vergleicht die Projektion Feld für Feld mit den
Originalbytes. Bei beiden ist `fixture.venue.id=null`; Koordinaten, Dachzustand,
genaues Matchende und Wetterausgabe sind nicht belegt. Der Septemberempfang des
Augustresultats wird nicht auf August zurückdatiert.

## TDD und Regression

- Erste Sammlung: erwartetes RED wegen fehlendem `context_sources.weather`.
- Erste Grünstufe: 65 C1-Fälle bestanden. Ein vorausgehender Lauf traf nur den
  noch nicht angelegten `.pytest_tmp`-Elternpfad; nach Anlegen dieses isolierten
  Testverzeichnisses wurde mit neuem Basistemp vollständig wiederholt.
- Weitere eigene sechs RED: zu breite Delta-Referenzen, bekannte
  Basisteamorientierung in beiden Joinzuständen, Abschluss exakt am Cutoff,
  Konfliktfortpflanzung und frische Terminabsage. Alle anschließend korrigiert
  und permanent regressionsgeprüft.
- Insgesamt **87 neue C1-Fälle** einschließlich reiner CPU-Ausführung,
  Unveränderlichkeit der Eingaben, exakter Realfixtureprojektion und ausdrücklicher
  Nichtübernahme des injury-only B5-Effekts.
- Erweiterter Fokuslauf: **811 bestanden** (C1, B5, B1-Verträge/-Beobachtungen,
  B2-Offset, B3-Snapshots und B6-Merkmale), 10.62 Sekunden,
  `.pytest_tmp/c1-focused-01`.
- Vollständige isolierte Regression: **3.094 bestanden, 15 übersprungen,
  97 Untertests bestanden**, 67.82 Sekunden, `.pytest_tmp/c1-full-01`.
  Übersprungene plattformspezifische Tests sind kein Linux-/VPS-Nachweis.
  Der staged Diff wurde zusätzlich mit `core.autocrlf=false diff --cached --check`
  ohne Fehler geprüft. Die fünf Dateien sind die vollständige Commitgrenze.

## Geprüfte Implementierungsbytes

| Datei | SHA256 |
| --- | --- |
| context_sources/weather.py | a2a9fdb838a4d4f5f05e39d43dd0dd7f15c8c9f05bdf74c77e4d8fad76ec11a0 |
| context_models/football_load.py | 3535654c39c7b6f706b71c27d7001c1647484136470871524405c189e5acdc58 |
| tests/test_football_weather_features.py | 1bde629bba4d036cac28f0a39e441de44b513268d577d039dca59efc7b9e2c0a |
| tests/fixtures/context/football/c1-schedule-20260907.json | dd21398ef1e6e05802b9666cfd0b34ddd051d55e0b9d83a6f66d9b15656b21f3 |

Controllerorganisierte unabhängige Prüfung bleibt vor Integration erforderlich.
