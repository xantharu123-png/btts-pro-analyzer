# Nations-League-Modell: Daten- und Rücktestnachweis (24.09.2026)

## Problem

Das frühere Modell lud jüngere Länderspiele nur für die am Suchtag angesetzten
Mannschaften. Es verlangte gleichzeitig mindestens fünf Heim- und fünf
Auswärtsspiele je Team und verwendete die Club-Frischegrenze von 35 Tagen.
Neutrale Länderspiele zählten als Form, aber nicht als Prüfspiele. Im echten
VPS-Bestand waren so nur 40 zeitlich getrennte historische Prüfspiele
berechenbar; für die Marktvalidierung sind mindestens 200 erforderlich.

## Änderung

- Einmalige Wettbewerbs-/Saisonabfragen statt Teamabfragen: UEFA Nations
  League, europäische WM-Qualifikation, A-Freundschaftsspiele und WM-Endrunde;
  nur Ergebnisse der letzten 730 Tage. Keine Ergebnisse von 2022.
- Eigener A-Nationalteam-Pfad aus tatsächlichen letzten zwölf und sechs
  Länderspielen je Team. Heimvorteil wird nur aus nicht neutralen Resultaten
  geschätzt und bei markierten neutralen Partien nicht angewandt.
- Freundschafts- und Endrundenspiele ohne verifizierte Neutralplatz-Angabe
  werden als „Spielortwirkung unbekannt“ geführt, nicht als sicher neutral.
  Sie zählen als Gesamtform und Walk-forward-Ziele, aber nicht als
  nachgewiesene Heim-/Auswärtsstichproben. Spiele am selben Kalendertag
  trainieren einander nicht.
- Eigener Modell-Scope und neue Prognose-/Shadow-Version. Unmarkierte oder
  gemischte Historie erhält keine Nationalteam-Freigabe.
- Gepoolte Modellprüfung erlaubt eine sichtbare Prognose, aber ist **kein**
  Nations-League-spezifischer Nachweis für eine voll bestätigte Wette.

## Isolierter VPS-Gegencheck

Probe mit Modellversion `challenge-engine:coherent-joint-calibration-v14` im
getrennten QA-Codeverzeichnis; App und Produktionsdatenbank unverändert.

| Größe | Ergebnis |
| --- | ---: |
| Nations-League-Spiele nächste sieben Tage | 60 |
| Jüngere A-Länderspiele im Pool | 572 |
| Davon mit unbekannter Spielortwirkung | 241 |
| Mit neuem Modell berechenbare anstehende Spiele | 60 |
| Zeitlich getrennte historische Prüfspiele | 309 |
| Geprüfte Tormarktdefinitionen mit Beobachtungen | 40 |
| Normale Marktvalidierung bestanden | 9 |
| Zusätzlich strengen HAC-/FDR-Vergleich bestanden | 3 |
| Vor Kontextprüfung modellseitig bestandene Märkte | 468 aus 54 Spielen |

Der simulierte volle Auswahlpfad lieferte 173 Kontext-geprüfte Modellprognosen,
aber null vollständig bestätigte Echtgeld-Auswahlen, weil in der Simulation
Kader-/Wetter-/Aufstellungsdaten bewusst nicht als belegt vorgegeben wurden und
der separate Nations-League-Transfernachweis fehlt. Das ist **kein** Beleg für
Wettgewinn, positive Rendite oder Qualität der heute angebotenen Quoten.

## Offene Grenzen

- Der Rücktest bewertet den gepoolten A-Länderspielmarkt, nicht die Nations
  League als eigene Untergruppe mit 200 unabhängigen Testspielen.
- Die einfachen Torstärken berücksichtigen letzte Resultate und Spielort,
  aber noch keine nachgewiesenen numerischen Verletzungs-/Wettereffekte.
- Für an einen neutralen Ort verlegte Nations-League-Heimspiele braucht der
  Provider eine belastbare Neutralplatz-Kennung; aus Name und Ort allein wird
  sie nicht erfunden.
- Beobachtete Quoten bleiben eine separate Preisfrage. Keine Modellprüfung
  garantiert, dass ein marktüblicher Wettpreis ausreichend hoch ist.
