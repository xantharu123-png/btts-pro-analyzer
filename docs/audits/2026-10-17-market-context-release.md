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

Der Benchmark ist keine Bewertung sämtlicher öffentlicher Tipps. Unterstützt
sind Fußball-1X2, BTTS und exhaustive Halbtor-/Halbeck-/Halbkartenlinien sowie
Tennis-/E-Sport-H2H. Doppelte Chance, Multigoal, überlappende Kombinationen,
Ganzzahllinien mit Rückzahlung und Basketball/Hockey/Cricket werden nicht
bewertet. Fußball benötigt vollständige konsistente Original-Märkte desselben
Laufs; selektive Kataloge und fehlende Gegenpreise bleiben ohne Urteil.
„Closing“ ist die letzte belegte vollständige Beobachtung in der letzten Stunde,
nicht garantiert die Quote am Anpfiff. Der bestehende Drei-Stunden-Preisjob kann
solche Fenster verpassen. Historische Entry-Beobachtungen sind nicht automatisch
ausführbare Angebote; alte fehlende Paare werden nicht rückwirkend ergänzt.

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

Quellcommit `702f594ed22d0d6b18dff5f8946145f5f27f0898` wurde auf main gepusht
und am 17.10. um 21:22:44 CEST per abgesichertem Fast-Forward auf dem VPS aktiviert.
Offline-Smoke bestanden; App-PID 1218486 → 1222039, App/Caddy aktiv, lokaler und
öffentlicher Healthcheck exakt `ok`, um 21:24 erneut bestätigt. Prognose-Dateien
und alle neun geprüften Jobstartstempel blieben während der Veröffentlichung
unverändert. Keine Sicherung, Migration oder zusätzlicher Sport-/API-Scan.

## Tatsächlicher Produktionsbericht

Rein lesend am 17.10.2026 um 19:23:25 UTC auf der Produktionsdatenbank ausgeführt.
56.162 Entry-Beobachtungen, null Closing-Beobachtungen, 6.671 erste kausale
Auswahlen. 440 vollständige und abgerechnete Modellmärkte; davon48 mit vollständigen
zusammengehörigen Vergleichspreisen aus 20 einzigartigen Fußballspielen.
369 inkonsistente und 2.904 unvollständige Modell-Marktgruppen wurden nicht
normalisiert oder erfunden; weitere 392 vollständige Ergebnisgruppen haben keine
vollständigen passenden Preise. Dies sind Gruppen-, nicht unabhängige Spielzahlen.

| Modellversion | Spiele | Modell-Brier | Markt-Brier |
| --- | ---: | ---: | ---: |
| coherent-joint-calibration-v13 | 10 | 0,114133 | 0,134223 |
| coherent-joint-calibration-v14 (aktueller Code) | 8 | 0,129125 | 0,138586 |
| finder-profile-continuous-history-v12 | 2 | 0,059302 | 0,045494 |

Kleinere Brier-Werte sind besser. Die kleinen, ausgewählten Gruppen erlauben
keine robuste Qualitäts-, Rendite- oder Effektfreigabe. Keine Tennis-Gegenpaare
sind im bisherigen Bestand vergleichbar. Die neue native Preis-/Closing-Erfassung
ist getestet und veröffentlicht, aber noch nicht durch einen nachfolgenden
regulären Produktionslauf nachgewiesen; alte fehlende Preise wurden nicht ergänzt.

Belege außerhalb Git: `C:/Projekt/BetBoy/output/context-effects-20261017/`.
Keine neuen Backups oder zusätzlichen Sport-/API-Scans. Die tatsächliche
Produktionsauswertung liegt in
`production-market-comparison-702f594.json`, Deploymentbeleg in
`deploy-market-context-01.txt`. Die Abschlussdokumentation wird anschließend
separat auf main gepusht und ohne weiteren App-Neustart auf dem VPS gezogen.
