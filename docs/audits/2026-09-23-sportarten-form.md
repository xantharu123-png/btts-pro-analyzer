# Form-Audit aller sechs Sportarten – 23.09.2026

## Prüffrage

„Form“ bedeutet Ergebnisse, die **vor** dem Modellentscheid bekannt waren.
Eine Ergebnisliste ist nicht automatisch ein nachweislich nützlicher
Wahrscheinlichkeitsfaktor. Preis/Quote bleiben davon getrennt.

| Sport | Tatsächlicher Modellanschluss | Offene Grenze |
| --- | --- | --- |
| Fußball | Die letzten sechs Spiele fließen mit 25 % in die aktiven Torewartungen ein; alle daraus erzeugten Märkte verwenden dieselbe Grundlage. | Die Gewichtung ist implementiert, aber ein isolierter Qualitätsgewinn durch genau diesen Formanteil ist hier nicht neu belegt. |
| Tennis | Gesamt- und Belag-Elo werden chronologisch nach bekannten Matches aktualisiert; Serve-Daten haben einen eigenen zeitlichen Verfall. | Eine zusätzliche letzte-Fünf-Korrektur würde dieselben Ergebnisse möglicherweise doppelt zählen. Sie ist nicht freigegeben. |
| E-Sport | Bis zu 20 vor dem Entscheid abgeschlossene Serien pro Team gehen in das gegnerbereinigte Elo ein. Ab neuen Shadow-Einträgen werden die letzten fünf exakt verwendeten Serien je Seite zusammen mit dem Eingabe-Hash gespeichert und offen angezeigt. | Alte Shadow-Zeilen werden nicht nachträglich mit heutigem Wissen ergänzt. Die Form bekommt keinen zweiten, unvalidierten Modellaufschlag. |
| Basketball | Das Research-Modell verwendet bekannte abgeschlossene Spiele, aber keine gesonderte jüngste Formgewichtung. | Produktiver Ergebnisspeicher derzeit: 0 Basketball-Zeilen. Keine aktuelle Form belegt. |
| Eishockey | Das Research-Modell verwendet bekannte NHL-Ergebnisse, aber keine gesonderte jüngste Formgewichtung. | 1.535 eindeutige NHL-Ergebnisse gespeichert; nur 7 Spielstarts liegen in den letzten 30 Tagen. Die Vorsaison ist nicht als aktuelle Form auszugeben. |
| Cricket | Kein freigegebener Modellkern und kein Formeffekt. | Produktiver Ergebnisspeicher: 0 Cricket-Zeilen; letzter Quellenversuch fehlgeschlagen. |

## Belege

- Fußball: `challenge_engine.py` mischt Saison und Form 0,75/0,25.
- Tennis: `tennis/elo.py` aktualisiert Gesamt-/Belag-Elo chronologisch;
  `tennis/predict.py` verwendet die Ratings und das Serve-Modell.
- E-Sport: `multi_sport_recommendations.py` filtert nach tatsächlichem
  Abschlusszeitpunkt und begrenzt auf 20 Serien je Team;
  `esports_elo.py` wertet diese Ergebnisse nach Gegnerstärke aus.
- Basketball/NHL/Cricket: `sports_prematch.py` passt ein Research-Modell
  auf kausal bekannte Endergebnisse an, ohne besondere Formgewichtung.
  `scanners/completed_history.py` speichert die erste tatsächliche
  Ergebnisbeobachtung, nicht einen erfundenen Zeitpunkt nach Anpfiff.
- VPS-Bestandsabfrage nur lesend: `sports_completed_history.db` enthält
  `NHL=1535`, Basketball/Cricket=0; 7 NHL-Spielstarts innerhalb 30 Tagen.
  Der letzte gespeicherte RisikoBet-Quellenstatus führt Cricket als Fehler.
- Vor Änderung gezielt lokal geprüft: 117 Sportmodelltests bestanden. Nach
  Änderung: 236 betroffene Modell-/UI-Tests bestanden; die lang laufende
  Vollsuite wurde nicht abgeschlossen. Das ist **kein**
  Nachweis besserer Wettqualität oder eines Wettvorteils.

## Nächste technische Abnahme

1. Für Basketball, NHL und Cricket je Sport/Wettbewerb/Format eine vorab
   beobachtete, deduplizierte letzte-Fünf-Serie mit Datum aufbauen. Nur bei
   ausreichenden Spielen beider Seiten als aktuelle Form anzeigen;
   sonst ausdrücklich fehlend oder Vorsaison.
2. Einen zusätzlichen Formeffekt als eigene Research-/Shadow-Modellversion
   gegen die unveränderte Basis auf **späteren, zuvor nicht verwendeten**
   Spielen vergleichen. Erst bei belastbarer Kalibrierung und
   versionsgebundener Freigabe darf er Tippwahrscheinlichkeiten verändern.
3. E-Sport-Form nach dem nächsten regulären Scan an einem neuen, kausal
   gespeicherten Match in der Anzeige kontrollieren. Bestehende alte
   Shadow-Zeilen nicht rückwirkend anreichern.

Der Patch erzeugt keine zusätzliche Sport-API-Abfrage und ändert weder
Modellwahrscheinlichkeiten noch Preisregeln. Der Auditbericht allein verändert
keinen VPS-Zustand. Fehlende Form wird nicht erfunden.
