# Marktvergleich und Kontext-Datenpfad – 17.10.2026

## Umgesetzt

- Eigenständiger rein lesender Marktvergleich über
  `scripts/selection_quality_report.py --db <forecast_evidence.db> --market-comparison`.
  Nur vollständige, exakt markt-/ereignisgebundene Quoten desselben Buchmachers
  und derselben Beobachtungs-/Abrufzeit werden proportional margenbereinigt.
  Einstiegs- und Schlussquoten bleiben getrennt. Einzelseiten werden nicht zu
  erfundenen Marktpreisen ergänzt. Wiederholte Läufe, Märkte und Anbieter werden
  innerhalb eines Spiels gemittelt; Modell-/Policy-Versionen bleiben getrennt.
- Brier-/Log-Loss-Vergleich samt gepaarter Unsicherheit. Explorative, nicht
  mehrfachtestbereinigte Kennzahlen sind keine Modellfreigabe oder Renditegarantie.
  Widersprüchliche Ergebnisbelege und fehlerhafte Identitäten/JSON-Daten werden
  nicht bewertet. Der Bericht verändert keine Prognose, Auswahl oder Wettbuchung.
- Bereits geladene native Tennis-Gegenpreise werden mit der einzelnen
  Prognosequote unveränderlich aufbewahrt. Exakte Teilnehmer, Ereignisse,
  Buchmacher und Zeitpunkte müssen zusammenpassen. Kein zusätzlicher Abruf,
  keine künstliche Gegenprognose und keine neue Datenbanktabelle.
- Separater Quoten-Worker übergibt seine bestehenden Preise jetzt an die
  Schlussquoten-Erfassung. Die erste kausale Prognose benötigt dafür keine alte
  EV-Preisfreigabe. Die bisherige erste ausführbare Prognose bleibt für den
  bisherigen hypothetischen Rendite-/CLV-Vergleich erhalten. Keine rückwirkende
  Einstiegsquote und kein neuer Modelllauf. Fehlende Datenbanken werden nicht
  durch die optionale Beobachtung angelegt; Erfassungsfehler bleiben diagnostiziert.
- Wiederholte, vollständig gebundene Tennis-Endzustände werden unter dem
  bestehenden Schreib-Lock wiederverwendet. Korrekturen und echte neue
  Beobachtungen bleiben erhalten; keine historischen Zeilen werden gelöscht.

## Nicht abgeschlossen

Verletzungs-, Wetter- und Müdigkeitseffekte sind nicht produktiv qualifiziert.
Die aktuelle Quellenprüfung und ihre konkreten technischen Ursachen stehen in
[Kontext-Abnahmebereitschaft](2026-10-17-context-activation-readiness.md).
Ein vorhandenes Endergebnis ersetzt keinen rekonstruierbaren ursprünglichen
Kontext. Null aktive Effekte werden hier nicht als erledigt umetikettiert.

## Prüfung und Veröffentlichung

Die gezielten Quoten-/Markt-Nachbarn bestanden 393 Tests; die Tennis-Pakete
236 Tests. Diese Runden überlappen teilweise und werden nicht addiert.
Gesamtabdeckung: 15.280 PASS, 98 unveränderte SKIP, 147 bestandene Untertests.
Alle 15.318 vorherigen Test-IDs und 60 neue bleiben erhalten; jede der 15.378
aktuellen Haupt-IDs erscheint genau einmal im abschließenden JUnit-Abgleich.

Der ursprüngliche vollständige Lauf bleibt ausdrücklich FAIL (19 Fälle,
Gruppen-Exitcodes `[0,1,1,1]`): 14 Subprozess-Zeitüberschreitungen, ein Prozess
ohne JSON, ein Lock-Zeitlimit und drei bei Collection eingefrorene Testquoten,
die nach über 40 Minuten korrekt als veraltet abgelehnt wurden. Für letztere
wurde ausschließlich `tests/test_bet_finder_ui.py` korrigiert, einschließlich
eines zuvor roten verzögerten Ausführungsfalls; echte Quotenlimits blieben
unverändert. Die fünf vollständigen betroffenen Testmodule bestanden danach
sequenziell mit 521 PASS und drei gleichen SKIP. Die übrigen Produkt-/Testquellen
sind zum ursprünglichen Sourcefreeze byte-identisch. Die ursprünglichen
Prozess-/Lockfehler reproduzierten sich nicht; eine allgemeine Host-Überlastung
ist durch die Messung nicht belegt. Kein Test wurde entfernt oder übersprungen,
kein Zeitlimit erhöht. Die vollständigen FAIL-, RED- und Recheck-Belege bleiben
außerhalb Git erhalten.

Die Veröffentlichung und der tatsächliche VPS-Abgleich stehen noch aus;
dieser Abschnitt ist bis dahin kein Deploymentnachweis.

Belege außerhalb Git: `C:/Projekt/BetBoy/output/context-effects-20261017/`.
Keine neuen Backups oder zusätzlichen Sport-/API-Scans. Die tatsächliche
Produktionsauswertung nach Veröffentlichung wird gesondert festgehalten;
die frühe lesende Probe (20 ältere Spiele) ist kein Beleg des aktuellen Modells.
