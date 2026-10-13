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

- Echten Qualitätsreport RO am Serverbestand durchführen; Modelle/Märkte getrennt.
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
Commit,Push,VPS-FF,Import,Health und RO-Messung werden nach tatsächlichem Erfolg
nachgetragen. Kein Backup,DB-Kopie oder zusätzlicher Sport-/API-Lauf.
