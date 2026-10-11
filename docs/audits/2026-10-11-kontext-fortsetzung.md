# BetBoy: Betriebsreparatur und tatsächliche Modellgrenzen

11.10.2026. Ausgang lokal, GitHub und VPS: `d26c1346ad727f825bc6639aeef4d48e13d43937`.
Der Übergabe-Prüfskill wurde zur Rekonstruktion und zum Erhalt vorhandener
ungetrackter Arbeit verwendet. Keine neue Sicherung, kein zusätzlicher
Sport-/API-Scan, keine Datenbereinigung, keine Änderung von Geldbuchungen.

## Tatsächlich implementiert

### Tageslauf: physischer Decoder

Der 45-Minuten-Abbruch vom 11.10. ist im systemd-Journal belegt. Die
Kontextinventur dekodiert 2.547.645 physische Receipts; deren komplette
Normalisierung und wiederholte Serialisierung kosten einen großen Teil der
Laufzeit. Der bereits kanonische JSON-Inhalt wird jetzt ohne zweite Baumkopie
direkt gegen denselben geschlossenen Vertrag geprüft. Hashes, Quell-/Empfangs-
zeiten, Preisfreiheit, alle physischen Indexbindungen und Inventurabdeckung
bleiben gleich. Kein vorgezogener Filter versteckt beschädigte History-Zeilen.

Rein lesende 512-Receipt-Probe auf dem VPS: fünf Wiederholungen, alter Decoder
0,6114 s, neuer 0,4931 s. Gleiche Ergebnisse, etwa 19 % weniger Decoderzeit;
**keine Hochrechnung als bewiesener erfolgreicher Gesamtlauf**.
Unabhängiger Differentialtest: 4.550 Fälle, null Akzeptanz-/Ergebnisabweichungen
und keine Eingabemutation. Fokus 156 bestanden, breiter 498 bestanden.

### Tennis: wiederholte Turnierdraws

ESPN-Antworten verschiedener Tage können denselben vollständig abgeschlossenen
Turnierdraw wiederholen. Innerhalb genau eines Capture-Batches wird die
inhaltlich identische terminale Wiederholung nicht als neuer Sportbefund
gespeichert. Die erste echte Empfangszeit bleibt erhalten. Neue Scores,
Teilnehmer, Starttermine, Siegerflags, Rücknahmen und sonstige reale Revisionen
werden weiterhin gespeichert. Geplante/laufende Spiele behalten ihre separaten
Zeitbeobachtungen. Der Vergleichscache endet beim Drain; er ist kein
laufübergreifender Frischecache. Vorhandene Receipts bleiben unverändert.

Ein unabhängiger Angriff mit ungültigem Siegerflag `1e400` deckte einen Abbruch
im optionalen Hashvergleich auf. Exakt bool/null wird verglichen; andere Typen
werden nicht dedupliziert und bleiben für die Ergebnisquelle unbestimmt.
Kein Gewinner wird dadurch geraten. 115 fokussierte Fälle und 344 unabhängige
Nachbarregressionen bestanden. Das begrenzt eine konkrete Quelle neuer
Mehrfachspeicherung, nicht rückwirkend das gesamte Datenbankvolumen.

### Fußball: neue Gegnerstärkerechnung wirklich angebunden

Der gemeinsame regularisierte Angriff-/Gegnerdefensive-/Spielort-Fit erhält
eine eigene Rezept-, Eingabe-, Fit- und Modellidentität. Der bestehende
same-call-Originalpublisher kann dazu jetzt einen Vergleich mit allen 40
Tormärkten aus einer gemeinsamen Ergebnisverteilung speichern. Dafür werden
ausschließlich die bereits eingefrorenen nativen Quellen und ihre tatsächlichen
Empfangszeiten verwendet; spätere Revisionen und freie Empfangszeitfelder sind
kein früherer Beleg. Ein Vergleich benötigt gemessen 2.997 Bytes, maximal
16.384 Bytes; Spielhistorie und Scorezellen werden nicht nochmals kopiert.

Original und Vergleich werden atomar unter dem bisherigen gemeinsamen
Bytebudget veröffentlicht. Das Original hat Vorrang, der optionale Vergleich
kann entfallen. Ein legitim nach Anpfiff fertiggestelltes altes Original darf
nicht wegen des neuen optionalen Vergleichs abstürzen; ein solcher Vergleich
gilt als nicht prospektiv verwendbar. Quellen-/Hashverletzungen bleiben Fehler.

178 breite Fußballfälle, zwei Schlussfälle und 17 unabhängige Reviewfälle
bestanden. Die aktive 75/25-Kundenberechnung, bisherige Kalibrierung und alte
Originalprognosen bleiben unverändert. Der neue Vergleich trägt ausdrücklich
`experimental-not-applied`, keine Effektfreigabe. Das ist eine reale Anbindung
zur getrennten Abnahme, **noch kein aktiver Modellwechsel oder Renditenachweis**.
Der vollständige historische D4-Verifikator erkennt den neuen Vergleichstyp
noch nicht als eigenen abgenommenen Schemafall; Aktivierungsprüfungen lassen
daraus keine aktive Effektfreigabe entstehen.

### Eishockey: NHL 2026/27

Der native Saisonvertrag akzeptiert die ausdrücklich geprüften Saison-/Regel-
paare 2025/26 und 2026/27. Alte Regelkennung mit neuer Saison, unklare native
Saison oder unbekannte Jahre bleiben ungültig. Die bestehende Modellrechnung
wird nicht verändert. Alte Effekte erhalten keine automatische neue
Saisonabdeckung. 896 breite Fälle plus ein neuer Event-ID-Fall bestanden,
ein erwarteter Skip. Die
[offizielle NHL-Regelquelle](https://media.nhl.com/site/asset/public/ext/2026-27/2026-27Rules.pdf)
wurde im Arbeitsspeicher geprüft, nicht dauerhaft gespeichert.

Schweiz/weitere Top-20-Ligen sind damit nicht angebunden. Dafür fehlen geprüfte
native Liga-IDs und passende Schedule-/Historien-/Ergebnis-/OT-/SO-/Marktadapter;
keine IDs oder Angebotsabdeckung wurden erfunden.

### Eishockey: unmögliche gespeicherte Siegerwahrscheinlichkeit

Ein unabhängiger mathematischer Gegentest reproduzierte einen weiteren Fehler:
`TeamSportForecast` akzeptierte 95 % Gesamtsieg bei 20 % Regulationssieg und
10 % Remis. Verlängerung/Penaltyschießen kann aber nur die Remis-Masse verteilen.
Der owning Datenvertrag verlangt jetzt
`Regulationssieg <= Gesamtsieg <= Regulationssieg + Remis`, mit derselben
1e-12-Toleranz wie der bereits bestehende Komplementprüfer. Kein Clamping,
keine neue Modellchance oder Unabhängigkeitsannahme. Bei null Remis-Masse muss
der Gesamtsieg dem Regulationssieg entsprechen. Alte Originale ohne
Regulationskomponenten bleiben unverändert; daraus wird keine neue OT-Evidenz
abgeleitet. Der native Producer verlangt weiterhin separat vorhandene OT-Daten.

227 Tests plus vier Untertests bestanden. Die fünf älteren Routing-Mocks hatten
beliebige injizierte Gesamtsiegchancen mit unveränderten Regulationswerten;
deren synthetische Komponenten wurden konsistent gemacht, ohne einen Fall oder
eine bestehende Assertion zu entfernen. Unabhängig: 126 Tests und 10.000
generierte Grenzfälle bestanden. 20.808 Fußball-Linienentscheidungen zeigten
keine Abweichung; Tennis-BO3/BO5 bleibt sauber getrennt.

Rein lesende Produktionsabnahme aller **12.706 gespeicherten RisikoBet-
Snapshots**: physischer Hash und rekonstruierte ID gültig; 188 Hockeybelege,
davon sechs mit konsistenter vollständiger Verteilung und 182 alte ohne beide
Regulationskomponenten. Null Verletzungen des neuen Guards. Das ist keine
Qualifikation der damaligen Prognosen, sondern Rückwärtskompatibilität.

### Fußball-Abrechnung: alter Fehlerbericht, bereits korrigierter Code

Der gespeicherte `football:event_snapshot_ambiguous`-Bericht stammt vom
10.10.02:12 UTC. Fixture 1565480, Veres Rivne gegen Kudrivka, hat dieselbe native
ID und dieselben Teilnehmer, aber eingefrorene Starts am 12.09. und 03.10.
Der schon deployte Commit `5467b88` behandelt diese Terminrevision und verlangt
passende native Identität, einen belegten eingefrorenen Start sowie gültige
Modell-/Ergebniszeiten. Kein weiterer Quellcode-Umbau ist dafür nötig.

Eine Vollinventur überschritt zunächst das 45-Sekunden-Auditbudget. Danach
bestanden die begrenzte, hashgeprüfte Projektion und die vollständigen
Kandidaten-/Stage-/Settlement-/Run-Mitgliedschaftsprüfer für alle vier betroffenen
Kandidaten und 35 abgeschlossene Run-Mitgliedschaften. Kein widersprüchlicher
nativer Football-Snapshotverband gefunden. Ergebnis, Abrechnung und alter
Bericht wurden nicht neu geschrieben; tatsächlicher Abschluss bleibt dem
regulären Ergebnislauf vorbehalten.

## Was für tatsächliche Kontexteffekte fehlt

Die rein lesende Produktionsinventur vom 11.10. fand 4.983 Tennis-Original-
publikationen für 941 verschiedene Ereignisse, davon 805 mit passendem
Endergebnis: ATP 250, WTA 555. Diese Zahlen sind **kein** train/tune/test-Nachweis
und zählen teilweise zusammengehörige Tage. 20 verspätete Originale wurden
nicht nachträglich als gültige Vorabprognosen behandelt.

Im Artefaktbestand gibt es keine `context-effect-v1`- oder
`context-approval-v1`-Freigabe. Zwei erfolgreich berechnete native
Merkmalsproben hatten weder ausreichend abgegrenzte Satzbelastung noch
Spieldauern. Ihre beobachtete Mindest-Erholung liegt bei null beziehungsweise
ungefähr vier Sekunden Unterschied: das ist eine Empfangszeitgrenze, kein
belegter physischer Müdigkeitsvorteil. Der dritte Fall überschritt das feste
100-Sekunden-Lesebudget. Daher keine vollständige 805-Fall-Merkmalsabdeckung
behaupten. Fehlende Zeiten werden nicht in null Belastung umgedeutet.

Fußball hat 88 Originalbindungen, davon 80 teilweise und acht vollständig
quellengebundene verschiedene Ereignisse. Acht ist nur eine obere Grenze vor
Rekonstruktion/Ergebnisabnahme, kein unabhängiger Testbestand. Bestehende
retrospektive Vergleiche und alte Kalibrierung werden nicht für die neue
Gegnerstärkerechnung als prospektive Freigabe umetikettiert.

Die physisch hashgeprüften Bindungen enthalten 70 Budgethinweise (25.599
fehlende Referenzen), neun fehlende History-Referenzbindungen (528 Referenzen)
und eine ungültige Quellenprovenienz (777 Records, davon 441 mit und 336 ohne
native Referenz). Die neun History-Fälle haben einen nativen Targetbeleg;
ihre fehlende Historie wird dadurch nicht belegt. Teilweise Bindungen betreffen
32 benannte Ereignisse insgesamt; Gruppenzahlen überschneiden sich, zusätzlich
42 unbenannte Target-Records. Keine gespeicherte native Revisionsmehrdeutigkeit.

Wichtige Diagnosegrenze: Der Budgethinweis wird aktuell nach einem Überlauf
laufweit verwendet. Er beweist nicht, dass jede einzelne fehlende Referenz an
der 1-MiB-Grenze scheiterte. Aus diesen Metadaten allein lassen sich alte Cache-
Historien und nie empfangene API-Historien nicht unterscheiden. Daher kein
pauschales "Budget erhöhen löst die 80 Fälle" oder rückwirkendes Signieren.

Numerische Verletzungs-, Wetter- und Müdigkeitseffekte brauchen verwertbare,
zeitgebundene Merkmale sowie die genehmigte unabhängige Abnahme mit mindestens
200 unangetasteten Testereignissen zusätzlich zu Training/Abstimmung.
Die Erhöhung eines API-Kontingents, ein Softwaretest oder wiederholtes Fitten
derselben fehlenden Merkmale ersetzt dies nicht. Aktuell nicht fertig.

## Veröffentlichung und Gesamtabnahme

Die Vollsuite wird auf dem eingefrorenen Endstand ohne zusätzliche Provider-
aufrufe ausgeführt. Zwei noch laufende Vorversuche wurden nach den abschließenden
Randfallkorrekturen gezielt beendet und zählen nicht als bestandene Läufe.
Ergebnis, Commit und Deployment werden nach Abschluss hier ergänzt.

Separater Portalrunner in bestehender `.portal-venv`, QA-In-Memory-Datenbank,
lokaler Testmail und blockiertem externen Netz: **47 Tests bestanden**, 15,501 s,
keine Installation oder echte Stripe-/Mail-/Kundendatenaktion. Der erste Aufruf
in der Sportvenv scheiterte am dort erwartungsgemäß fehlenden Django und wird
nicht als Portaltest gerechnet.

Geplanter Deploy: nur geprüfter Git-Fast-forward, kein Backup/Migration/Scan;
kein Sportdienst wird unterbrochen. App/Health, Revisionen, Timer und die
bytegleichen gespeicherten Wettfinder-/RisikoBet-Dateien werden getrennt geprüft.
Ein neuer erfolgreicher Tageslauf bleibt der nächste reguläre Lauf, kein
manuell gestarteter Scan. GitHub-Push allein ist kein Serverdeploy.

Belege außerhalb von Git: `C:/Projekt/BetBoy/output/context-audit-20261011/`,
`day-timeout-20261011/`, `hockey-seasons-20261011/` sowie
`opponent-publication-20261011-test04.xml` und `-test05.xml`.
