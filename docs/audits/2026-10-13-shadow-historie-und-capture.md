# Shadow-Historie und Quellen-Capture – 13.10.2026

Auftrag: vorhandene Historie und Schattendaten nutzen, reale Capture-/Auswertungs-
Fehler beheben. Kein neuer Sportscan, Providerzugriff, Backup oder DB-Export.

## Rein lesende Produktionsinventur

VPS-Basis47fe15a,13.10.08:38–08:49Europe/Zurich:

| Bestand | Tatsächliche Bedeutung |
| --- | --- |
| 84.025 Fußball-SHADOW-Zeilen | Wiederholte Forecast-Revisionen |
| 662 unterschiedliche Events | Fußballspiele, nicht Märkte/Revisionen |
| 588 Events mit finalem Ergebnis | Grundmodell-Auswertung möglich |
| 4.396 Event-/Markt-/Selection-Ergebnisse | korrelierte Märkte desselben Spiels |
| 5.214 Event-/Selection-/Modell-/Policy-Identitäten | keine5.214 unabhängigen Spiele |
| 101 native ORIGINAL-Bindings |8 captured,93 partial |
| Legacy Shadow |3 Prognosen/Events;3.387 Fixtures lediglich Termine |

Frühere95 waren native Bindings, keine Vollinventur.579 Shadow-Spiele besitzen
native Zielbasis vor erster Entscheidung.265 haben davor Wetterquellen
(193 mit Ergebnis),123 echte Spieler-Verfügbarkeit (88 mit Ergebnis).
Leere/nicht abgedeckte Listen sind keine Verletzungsbelege. Alle Shadow-
Kontextvollständigkeits-/numerischen Wirkungsflags sind0. Empfangsuhren allein
machen fehlende konsumierte Quellen oder Verteilungen nicht vollständig.

Shadow-Payloads besitzen skalare p-Werte, aber keine ursprünglichen Lambdas,
Joint-Zellen und vollständigen kalibrierten Replayrezepte. Native Rohhistorie
könnte eine SEPARATE Baseline rekonstruieren, nicht rückwirkend das ursprünglich
publizierte kalibrierte Joint. Alte erst am13.10.empfangene Februar-Spielerlisten
bleiben frühestens am13.10.verwendbar. Wetter-Gültigkeitszeit ist keine Ausgabe-
oder Stadion-/Dachbelegung. Keine rückdatierte Wirkung oder Prognoseänderung.

## Reparatur

1. Der chronologische Quellenflush verbrauchte1MiB an älteren FT-Historien,
   bevor später empfangene aktuelle NS/TBD/PST-Ziele gespeichert wurden. Reale
   Nachtprobe:Quellen1.048.485/1.048.576B,Originale3.126.068/3.145.728B.
   Jetzt alle tatsächlich empfangenen Revisionen expliziter nativer Ziele
   stabil zuerst, danach Historie; Korrekturautorität und FT-Reuse unverändert.
2. Globales `source_exhausted` markierte auch CSV/nie empfangene Datensätze
   pauschal als Budgetverlust. Jetzt Ausschluss-ID pro tatsächlichem Append-
   Versuch einfrieren; fehlende native Belege getrennt ausweisen.
3. `build_quality_report` lud sämtliche großen Forecast-Payloads und ungenutzte
   Quote-Payloads. Jetzt Cursor in einem konsistenten read-only SQLite-Snapshot,
   kompakte Identitäten/Zähler/Bins und kompensierte Summen. Gleiche kausale
   Erstentscheidung/actual-start/Preis-/Ergebnis-/CLV-Regeln und Reportfelder.

Python-tracemalloc-Gegentest:2.048×64KiB-Forecasts vorher137.048.974B,danach
220.753B;32×512KiB-Quote-Payloads vorher16.808.000B,danach32.102B. Dies misst
Python-Payload-Materialisierung, NICHT Gesamt-RSS/SQLite-Puffer. Identitäts-,
Ergebnis- und Quotenmetadaten wachsen weiterhin mit der tatsächlichen Kardinalität.

## Verifikation

- Echte RED-Reproduktionen:Target-Reihenfolge,CSV-Abgrenzung,globale Budgetgründe,
  Payload-Speicher. Kein bloßer Mock eines erfolgreichen Returns.
- Isolierter exakt gestagter Stand d9f54d4e6f2d838e0a1a6d0005c0c6874e825d0f:
  267/267 Release-/Nachbartests bestanden,23,39s,kein Skip/Failure.
- Frischer read-only Review des Index:keine Critical/Important/Minor-Befunde.
- Portal mit vorgesehenen `siteconfig.qa_settings`:47/47 bestanden,14,533s;
  Netzwerk blockiert. Bare pytest über Portal war kein korrekt konfigurierter
  Django-Lauf. Ein erster Portalversuch mit DEV statt QA war ebenfalls falsch
  konfiguriert und ist kein PASS. Korrekte Runde unverändert danach bestanden.
- Breiter Kernlauf:224 bestanden,6 Skips,1 Failure am Fixture-SHA; Git-Blob LF
  ist korrekt, Windows-Archiv hatte515 zusätzliche CR. QA-Archiv mit
  `core.autocrlf=false` materialisiert; keine Produktiv-/Fixtureänderung.
  Danach sind die numerischen Cricket-Replays bitgleich, der unabhängige alte
  Hockey-`_variant`-AST-Freeze-Konflikt besteht jedoch weiter. Kein Vollsuite-PASS.
- Abschließende LF-materialisierte Reparaturrunde267/267 in32,35s,0 Skips/Fehler;
  `release-lf-final.xml`. Produktionsergebnis wird unten nachgetragen.
  Rohberichte außerhalb Git unter
  `C:/Projekt/BetBoy/output/football-history-shadow-20261013`.

## Noch offene Abnahmen

- Echte Qualitätsauswertung unten durchgeführt; Modelle/Märkte getrennt halten.
  Hypothetischer Einsatz-ROI ist weder echter Gewinn noch neue Strategiequalität.
- Priorisierte Capture-Publikation erst im nächsten REGULÄREN Sportlauf belegen.
- Separate3MiB-Originalgrenze/Readiness-Streaming und gemeinsame Quellreuse lösen.
- 200 unberührte unabhängige Kontext-Testspiele über3 Zeitblöcke zusätzlich zu
  Training/Abstimmung und freigegebenen Qualitätsvergleich erfüllen.662 Shadow-
  Grundmodellspiele ersetzen diese vollständigen Kontextfälle nicht.
- Numerische Verletzungs-/Wetter-/Müdigkeitswirkung ist weiterhin0 aktiv.
  Kein Fit,Approval,neuer Datensatz oder höheres API-Budget in diesem Release.

## Veröffentlichung

Ausgang47fe15ab7524ac34216ec8322c88384b31e4a115. Nur6 gezielt gestagte
Code-/Testdateien plus diese Doku/zentraler TODO/Übergabe. Shared Publisher enthält
weiterhin fremdes unstaged WIP; es darf nicht als Ganzes gestagt werden.
Codecommit **d47c9b09903b9445541745a583e12c98552bc6bf** ist committed,auf main
gepusht und13.10.,11:02CEST auf dem VPS per Fast-forward veröffentlicht.
Offline-Imports auf Linux ok; App/Caddy aktiv,7 bestehende Timer aktiviert,
beide Healthchecks ok. Kurze lokale Connect-Retries direkt beim Neustart liefen
innerhalb der begrenzten Healthprüfung aus; final beide `ok`,kein Rollback.
Wettfinder-JSON SHA256f20422a802fd61461d8f8ab548f85228a1d083bdba92c51a0615bf9364a81bd4
undRisikoBet-JSON6f0c5f3158fb2bbe08bc8b7692636a0f16847e90c32742a7f7497346b644e8f1
vor/nach bitgleich.21GiB freier VPS-Speicher; keine Bereinigung erforderlich.
Deploymenthelper separat reviewt:>480s freies Timerfenster umfasst Erfolgsweg
UND späte code-only Recovery. Reguläre Jobs nicht gestartet/abgeschaltet.
Backupservice/-timer bleiben inactive. Kein Backup,DB-Kopie oder Zusatzscan.

## Tatsächlicher gespeicherter Qualitätsreport

Zeit13.10.,11:02:56,864Europe/Zurich,exakt releasede Funktion auf vorhandenem
Produktionsbestand,ein Read-only-Snapshot. DB-Präsenz zwingend geprüft,
Provider-Sockets gesperrt,serverseitiger90s-Timeout.10,423s Gesamtlauf,
87.004KiB=84,965MiB Peak-RSS; reine Prozessmessung,keine allgemeine RAM-Zusage.
131 Modell-/Markt-/Policy-Gruppen,129 besitzen gescorte Entscheidungen.

| Sport | Spiele | mit irgendeinem Ergebnis | noch ohne Ergebnis |
| --- | ---: | ---: | ---: |
| Fußball |662|588|74|
| Tennis |241|213|28|
| E-Sport |365|354|11|
| Eishockey |7|0|7|

Scoring:erste kausale Entscheidung proEvent/Selection/Modell/Policy;
Preisreturns separat erste kausale ausführbare Entscheidung. Tatsächlicher
Anpfiff und Aufnahmeuhren bleiben maßgeblich. Vorsicht:Scoreanzahl/Quote sind
keine Gesamtzahl unabhängiger Spiele über korrelierte Märkte hinweg.

| Beispiele getrennten Modell-Scores | gescorte Entscheidungen | Brier | Log-Loss |
| --- | ---: | ---: | ---: |
| Fußball,v14,Heimmannschaft unter2,5Tore |175|0,132524|0,429089|
| Fußball,v12,Heimsieg |127|0,221861|0,633809|
| Tennis,elo-serve-platt-v3,H2H |206|0,217468|0,625527|
| E-Sport,subgraph-elo-v3,H2H |345|0,231311|0,653833|

Keine Rangliste dieser unterschiedlichen Ereignisse/Wettarten und kein neuer
Train/Test- oder pairedKontextvergleich. Insbesondere ein hohes Unter2,5-
Trefferniveau beweist weder interessante Quoten noch einen Müdigkeitsvorteil.
Gegenquoten-/ROI-Stichproben meist0,einzeln2–4; einzelne positive/negative
hypothetische Returns werden ausdrücklich NICHT als belastbare Rendite behandelt.
213 Tennis-Ergebnisse enthalten7Void-Fälle;H2H-Score206 ist daher nicht213.
Die vollständigen Ergebnisgrundlagen dieser konkreten Messung bestehen in der
DB; gespeicherte Report-Summary mit20 größten Gruppen außerhalb Git:
`C:/Projekt/BetBoy/output/football-history-shadow-20261013/quality-report-summary.json`.

Fazit:vorhandene Historie/Shadow ist jetzt tatsächlich messbar benutzt,nicht nur
gezählt. Sie ersetzt die noch fehlende vollständige numerische Kontextkette
und deren zeitgetrennten Qualitätsnachweis nicht. Keine Prognose/Geldbuchung
wurde geändert. Nächste echte Capture-Abnahme beim regulären14.10.-Tageslauf.
