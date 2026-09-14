# 14.09.2026 – leere Tagesauswahl und verlorene Kontextdaten

## Tatsächlich gemessener Ausgangspunkt

Produktion und beide lokalen Checkouts: `ccab6603bdd222d020a68adffb57cc9eae9b4172`.
Um 12:41 UTC war die Ausgabe von 12:37 UTC aktuell, aber sämtliche 69 darin
gespeicherten Modelle (65 Fußball, 4 E-Sport) waren für Daily3 älter als dessen
150-Minuten-Grenze. Der gemeinsame Import lieferte alle 69 Modelle korrekt;
`daily3_choices` lieferte 0. Fehlende Quoten waren nicht diese Ursache.

Der Fußball-Hintergrundlauf erneuerte Kontext, nicht die ursprüngliche
Mitternachtsrechnung. Die bisherigen alten Modellzeitstempel waren deshalb
richtig; ein bloßes Umstempeln wäre keine Reparatur.

Der erneut gestartete reguläre Tennisdienst lief 14:48:33–15:04:00 CEST:
Rebuild Exit 1, Tages-Scan erneut Timeout bei 900 s, Wochenkontrolle und Report
Exit 0. Vorbereitet waren 58 Prognosen. Während des Scans wurden über 3 GB und
rund 1,6 Millionen Schreibaufrufe gemessen. Die alte Einzelzeilen-Speicherung
öffnete/präparierte/committete die Datenbank für jede Beobachtung erneut.

Live-Inventar vor dieser Änderung: 14.245 Fußball-Ausfallreceipts, 6.780
Aufstellungsreceipts, 3.139 native Basisreceipts, 405 Ergebnisse; **keine
Spieler-Einsatzreceipts**. Tennis: 159.014 Status- und 129.228 Belastungsreceipts.
A1 enthielt nur 31 Tennis-Originale und 3 Tourstände: kein trainiertes
Kontexteffekt-Artefakt und keine empirische Effektfreigabe.

## Reparatur

- Gezielte Fußball-Neuberechnung bereits entdeckter Spiele über denselben
  vollständigen Modell-/Kalibrierungspfad, maximal 20 Spiele pro vorhandenem
  Kontextstapel. Keine zweite breite Ligasuche, kein neuer Timer. Gespeicherte
  Historie plus aktueller nativer Ergebnistail werden erneut berücksichtigt.
- Nach 90 Minuten wird bei einem fälligen Kontextstapel wirklich neu gerechnet;
  das lässt Abstand zur unveränderten Daily3-Grenze. Alle Wettarten werden
  erneut abgeleitet, nicht nur die frühere Auswahl kopiert. Optionale neue
  xG-Netzabrufe bleiben bei dieser Wiederholung auf 0 begrenzt.
- Nur ausdrücklich neu berechnete Fixture-IDs erhalten neue Modell-/Cutoff-
  Zeiten und eine neu gebundene Analyse. Reiner Kontext behält alte Zeiten.
  Fehlerhafte/fehlende Modellinputs behalten alte Modelle, statt sie frisch zu
  etikettieren. Bestätigte Absagen/Terminänderungen werden berücksichtigt.
- Ein Kontextfehler startet nicht mehr die erfolgreiche breite Tagesentdeckung
  erneut. Die vorhandene begrenzte Fixture-Aktualisierung bleibt zuständig.
- Empfangsspeicherung in atomaren Stapeln von höchstens 512 Beobachtungen;
  gleiche Normalisierung, Quellzeiten, Hashes, Kollisions- und Readback-Prüfung.
  Keine Historienlöschung, Schemamigration oder Abschwächung der Modellfreigabe.
- Der bereits budgetierte Fußball-Ergebnisabruf speichert jetzt auch tatsächlich
  gelieferte Spieler-Minuten/Aufstellungen in der Kontext-Historie. Er führt
  dafür keinen zusätzlichen Netzabruf aus. Daten nach Empfang bleiben nach
  Empfang: keine rückdatierte Verfügbarkeit und kein erfundener Verletzungseffekt.
- Tennis protokolliert den Übergang zwischen Empfang, Speicherung und gemeinsamer
  Prognoseveröffentlichung, damit ein Timeout seinen Arbeitsschritt erkennen lässt.

## Prüfung vor Auslieferung

**945 gezielte Tests und 32 Untertests bestanden**, 32,36 s. Enthalten:
Wettfinder, Daily3, reale gemeinsame Importkette, Fußballmodell/-historie,
Kontextquellen, Kontinuität alter Receipts, Evidenzabrechnung, Tennisworker und
operative Bereitstellungsprüfung. XML: `.pytest_tmp/refresh-scoped-final.xml`.
Die vollständige etwa 10.000er-Matrix wurde bei rund 8 % beendet; sie ist
ausdrücklich NICHT als vollständige bestandene Suite ausgewiesen.

Neue Regressionen reproduzierten zunächst fehlende Neuberechnung/Batch-API.
Gegenfälle prüfen unveränderte alte Evidenz, kaputte native Identität,
Absagen, echte Wahrscheinlichkeitsänderung bei anderen historischen Ergebnissen,
kein neuer Ligenscan, unveränderte Quote-Unabhängigkeit sowie atomaren Abbruch.
Der native Ergebnisempfänger übernimmt im gebundenen Beispieldatensatz 46
Spielerbeobachtungen mit einem einzigen ohnehin benötigten GET.

Lokaler isolierter Vergleich mit 512 synthetischen Receipts: Einzelweg 2,979 s,
Stapelweg 0,046 s (64,17-fach); Receipt-IDs und sämtliche gespeicherten Zeilen
exakt gleich. Dies ist **noch kein** Nachweis des vollständigen VPS-Tennislaufs.

## Abgrenzung und Auslieferungsbeleg

Diese Reparatur aktiviert keine empirisch ungeprüften Verletzungs-/Müdigkeits-
koeffizienten. Fußball-Live-Effektanbindung/Training, zusätzliche Sportadapter
und der statistische Verbesserungsnachweis bleiben offen. Cricket unverändert.
Die WTA-Quelldatei ist weiterhin separat auf Erreichbarkeit zu prüfen.

Dieser Bericht dokumentiert den geprüften Code vor dem Deployment. Der danach
tatsächlich erreichte Commit-/VPS-/Laufstatus wird ohne weitere Codeänderung in
`output/playwright/selection-refresh-release-20260914.md` festgehalten. Frühere
„alles erledigt“-Aussagen ersetzen weder diesen Laufbeleg noch empirische Tests.
