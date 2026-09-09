# Fußball: vorhandene Ergebnisabrufe mit früheren Kontextbelegen verbinden

9. September 2026. Eigenes Teilpaket auf `caa230f73705f5bf8aadcc25394cd136963e858d`.
Keine neue Abfrage, kein neuer Endpunkt, keine Modell-/Preisänderung, keine
historische Rückdatierung und noch keine Produktivaktivierung.

## Fehlende Verbindung

Der bisherige Capture bewahrte explizite Spiel-/Ausfallabrufe und zugehörige
NS-Discovery auf. Die ohnehin vorhandenen `recent_ft_results`- und
Saisonhistorienabrufe mit `status=FT` wurden ignoriert. Ein früher vor dem
Spiel gespeicherter Kontext erhielt dadurch nicht automatisch den später in
diesem vorhandenen Abruf gelieferten Ergebnisbeleg. Die vorhandenen Tests
belegten eine Erfassung von Ergebnissen nur bei expliziten Fixture-ID-Abrufen.

Die Erweiterung verarbeitet genau die bestehenden FT-Requestformen:
Liga/Saison/FT oder Liga/Saison/FT/von/bis/Zeitzone. HTTP 200, vollständiger
einseitiger Envelope, eindeutige native IDs, exakter nativer FT-Status sowie
Liga/Saison und gegebenenfalls lokale Datumsgrenzen werden vor Speicherung
geprüft. AET/PEN werden nicht als reguläres FT umgedeutet. Die ursprüngliche
Antwort und ihr Verhalten im bestehenden Basis-Worker bleiben unverändert.

## Enger Speicherumfang und Zeitvertrag

Ein FT-Historienabruf erzeugt nur Belege für native Event-IDs, für die bereits
ein vollständiger, owning-validierter nativer Base-Receipt tatsächlich VOR
seinem damaligen geplanten Beginn gespeichert wurde. NS/TBD/PST gelten hier
als bekannte geplante Ereignisse, nicht als bestätigte Aufstellung. Ein erst
nach Beginn empfangener NS-Datensatz oder ein gegenüber dem Ergebnisempfang
zukünftiger Receipt genügt nicht. Es gibt keine neue Watchlist-Tabelle,
keine Registrierung aufgrund einer Ergebniszeile und keine Speicherung aller
unbeobachteten Spiele aus einem Ligaabruf.

Die schon vorhandenen geprüften A1/B1-Pfadregeln werden über den vorhandenen
read-only Reader verwendet. Eine fehlende DB wird nicht erstellt; eine echte
A1-DB ohne beide B1-Tabellen bleibt unverändert. Teilweise fehlende B1-Tabellen,
beschädigte Inhalts-/Receiptbytes oder ungültige bekannte Quellendatensätze
werden nicht zu „keine früheren Belege“ umgedeutet. Dieser Live-Ingestionsreader
ist ausdrücklich KEIN label-freier D2-Inventarpreflight: native B1-Bodyprüfung
ist Teil der Quelle, nicht das Öffnen eines Experiments durch den Evaluator.

Die vorherige native Event-ID begrenzt ausschließlich den Erfassungsumfang.
Sie bescheinigt NICHT, dass ein neuer korrigierter Termin/Teilnehmer/Scope zu
einer alten Prognose passt. Der neue Ergebnisreceipt trägt die tatsächliche
aktuelle native Identität, den aktuellen Ergebnisstand und die echte neue
Empfangszeit. Die vorhandene owning Outcome-/D1-Prüfung muss weiter die volle
Identität mit dem jeweiligen eingefrorenen Event abgleichen. Ein Dauertest
belegt explizit, dass eine erfasste Terminänderung nicht zur alten Prognose
gejoint werden kann.

Ergebnisse, native Basisdetails und gegebenenfalls tatsächlich mitgelieferte
Spielerstatistiken gehen weiterhin durch die bestehenden Normalisierer.
Keine tatsächliche Spieldauer wird aus dem Receipt oder einem Testzeitpunkt
abgeleitet. Keine Veröffentlichung wird erfunden. Korrekturen und erneute echte
Empfänge werden append-only gespeichert; gleiche Bytes bei gleichem Empfang
bleiben idempotent. Vorherige Prognosen, Tickets, Ergebnisse und Konten werden
nicht geändert. B1-Atomarität bleibt wie zuvor pro Receipt, nicht eine erfundene
Transaktion über alle Endpunkte.

## TDD und tatsächliche Prüfungen

Neue permanente Datei `tests/test_context_football_result_capture.py` mit
28 Fällen. Die ersten22 auf dem unveränderten Ausgangscode ergaben
**17 RED / 5 GREEN**, 2,89s. Die Fehler belegten fehlende Ergebnis-/Scope- und
Integritätsprüfung; kein Setup-/Collectionfehler, keine Assertionkorrektur.

Die erste Implementation verwendete zunächst die rohe B1-Zeile statt des
benötigten vollständigen Selected-Row-Transports. Das erzeugte11 Fehler und55
positive Fälle. Die Source wurde korrigiert, nicht die Assertion: dieselbe
tatsächliche Empfangszeit wird explizit gebunden, die beiden Zeitgrenzen werden
weiter separat geprüft. Anschließend **66 bestanden**, 4,42s, einschließlich
aller44 bereits bestehenden Fußball-Capturetests.

Sechs zusätzliche Kontrollen für zukünftige Belege, geänderte Termine, den
wirklichen automatischen Worker/FT-Tail, fehlende Tabelle und geänderte äußere
Indexfelder sind ebenfalls grün. Letzter fokussierter Gesamtlauf:
**426 bestanden**, keine Skips, 8,01s. Enthält beide Capturedateien, B1, Outcomes,
Fußball-Provider/-Quellen, Workflow, Marktscope und Wettfinder-Automation.
Der echte vorhandene HTTP-Callback wird benutzt und die Aufrufanzahl geprüft;
eine freie Behauptung `already_fetched=True` gibt es nicht.

```text
030d20c2114bffdea53c23556d8367181efa4c84df2257ec9761f63a61bff0ac  context_sources/football_capture.py
ba4bbd37a64829071266e91ccbf21ca306295917b04274b2c494b3f744856799  tests/test_context_football_result_capture.py
6c32bd0ede632061a67f6617522bb779e6053d06bb18865949fd80d05ed3b882  .pytest_tmp/result-capture-red-20260909-01.xml
bee454455f77f11f4496e4eb2163d3b9fa91256c09bc5a15cca444f357003ea9  .pytest_tmp/result-capture-focus-20260909-01.xml
```

Unabhängiges Review, zusammengeführte Vollsuite und Produktivnachweis bleiben
noch ausstehend. Synthetische native Antworten belegen Softwaremechanik, keine
neue Live-Erhebung oder empirisch bessere Wetten. Insbesondere fehlen weiterhin
ausreichende unverfälschte Daten, native CSV-/Spielerjoins und vollständige
gemeinsame Worker-/Kartenanbindung. Cricket und Geldregeln bleiben unverändert.

## Unabhängiger Befund F1 und enger Fix

Die unabhängige Prüfung von `684865e583bcf4377df588aaa911b23832f23e57`
hat einen echten P2-Befund reproduziert: ein beschädigter Source-/Kind-Index
konnte durch die frühe SQL-Selektion als fehlender Watch verschwinden. Bei
einem zweiten gültigen Watch wurden sogar weitere Ergebnisbelege gespeichert,
obwohl die vorhandene Datenbank beschädigt war. Originalbericht und sechs
unveränderte RED-Proben werden erhalten; die 426 grünen Bestandsprüfungen
waren kein Gegenbeweis. Zwei zusätzliche Defekt-Witnesses sind ausdrücklich
Schadensnachweise, keine Reparaturtests.

Der Fix entfernt nur den vorgeschalteten SQL-Filter. Jede tatsächliche B1-Zeile
wird zunächst mit `_decode_receipt` auf Typen, Hash und Index-/Inhaltsbindung
geprüft; erst danach werden Source/Kind/Schema ausgewählt. Die vollständige
Prüfung läuft vor jeglicher neuer Ergebnisveröffentlichung. Dies bleibt ein
owning Live-Capture-Reader und wird nicht als label-freier D2-Preflight benutzt.
Quellen, B1-Schema, Wettmodelle und Preis-/Geldregeln bleiben unverändert.

Acht neue permanente Wiederholungen (vier Indexänderungen jeweils mit/ohne
zweiten gültigen Watch) ergaben vor dem Fix **8 RED**, danach mit den sechs
unveränderten unabhängigen Reparaturerwartungen und allen vorhandenen
Fokusfällen **496 bestanden, 0 Skips, 10,18s**. Die neuen Fälle prüfen die
Unverändertheit beider SQLite-Tabellen nach dem korrekt propagierten Fehler.
Unabhängiges Nachreview und integrierte Vollsuite stehen noch aus.

```text
fa4adf76c31fb1fa84f2296f8ba735ca0877fc3d181ff7c62ce53e51a3faccec  context_sources/football_capture.py
1475c0074d3ecee12157ed2770de84c54b32afbb3cd8dae0ceebbd86b17d16af  tests/test_context_football_result_capture.py
5fa0c50f9fd7313574c56c07a76e2ca2def9896928bfb1c87660a67475dcb528  .pytest_tmp/result-capture-index-red-20260909-01.xml
23dbbb415bf1e574a66c4674cca22e119f1d0f54fa97766ed336ad2beabff307  .pytest_tmp/result-capture-fix-green-20260909-01.xml
8ca1924fc5882c7df0bd48e7e97f3b07e6f300fe6b5cfd575797253a0946fd54  original independent REVIEW.md
```
