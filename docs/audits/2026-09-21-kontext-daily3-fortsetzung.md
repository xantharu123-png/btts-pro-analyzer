# Kontextwirkung und Daily3: Fortsetzung 21.09.2026

Auftrag: verbleibende Kontext-/Qualitätsarbeit erledigen; Cricket bleibt
ausgenommen. Ausgangsstand `5a6b2f9028242225bbca43546977dcc23fb9d250`.
Keine Wettbuchungen, Finanzhistorien, Backupregeln oder Anbieterzugänge ändern.

## Bereits tatsächlich erledigt

- Der zuvor offene reguläre Lauf endete 11:55:16 CEST mit Exit 0
  (Start 11:37:04). `completed`, null technische Fehler; Teildaten bleiben.
  RisikoBet veröffentlicht `riskobet-grounded-basis-v3` mit dem neuen Stand
  `2026-09-21T09:48:19.510730+00:00`. Die Textveröffentlichung ist bestätigt.
- Daily3 erhält einen echten ATP-Vergleich: derselbe gespeicherte Modellstand,
  dieselben Spieler und derselbe Zeitpunkt mit/ohne Belageinfluss sowie die
  Belag-Elo-Variante. Best-of, Aufschlagmischung und Kalibrierung bleiben im
  Vergleich erhalten. Das sind Sensitivitätsvarianten, keine unabhängigen
  Expertenmodelle und kein Nachweis eines Wettvorteils.
- Aufnahme nur mit tatsächlich bestandenen Modellvoraussetzungen, mindestens
  acht Belagsspielen je Spieler, ausreichender allgemeiner Historie und
  Kalibrierungsbasis; alle drei Varianten müssen die defensive Schwelle
  bestehen und der Belagsunterschied mindestens zwei Prozentpunkte betragen.
  Relevanzschwelle ist keine statistische Signifikanz. Preise bleiben separat.
- v4-Tennisbelastung trennt Spielende und Abrufzeit. Ein laufender Zwischenstand
  und das erste passende vollständige Endresultat begrenzen das Ende. Nur
  vollständig im Fenster liegende Zeitintervalle liefern Fensterbelastung.
  Minuten bleiben fehlend, wenn der Anbieter keine belegte Dauer liefert.
- Erholungs-Untergrenzen verwenden die erste weiterhin passende Endbestätigung,
  nicht den letzten wiederholten Abruf. Das behebt die zuvor fast identischen
  Pausenwerte. Es ist ausdrücklich keine exakte Erholung und keine vollständige
  Kenntnis aller Matches eines Spielers.
- Aktuelle v4-Snapshots referenzieren alle Revisionen aller jemals mit den
  beiden Spielern verbundenen Events. Die gesamte physische Historie bleibt
  vorab geprüft; ein unabhängiger Replay rekonstruiert die exakte Referenzmenge.
  Entfernte Teilnehmer, Absagen und Korrekturen können nicht verschwinden.
  Alte v3-Snapshots und der optionale v3-Diskstream bleiben bytekompatibel.

## Native Datenmessung, keine empirische Freigabe

Rein lesende VPS-Probe, 10:52 UTC; keine neuen Providerabfragen, Trainingsläufe
oder Datenbankänderungen:

- 1.710 tatsächliche Tennisoriginale; 205 unterschiedliche rechtzeitig
  veröffentlichte erste Prematch-Events; acht verspätete Originale ausgeschlossen.
- 125 Events haben ein eindeutig passendes normales Endresultat. Das sind
  ATP/WTA zusammen und noch vor Train-/Tune-/Testtrennung und Feature-Abdeckung.
- Sechs zeitlich gleichmäßig verteilte Fälle, ausgewählt ohne Gewinner oder
  Featurewerte anzusehen: keine vollständigen Satz-/Spiel-/Minutenpaare in den
  geprüften Fenstern. Erholungsdifferenzen dagegen z.B. +91,351, -98,831 und
  +30,700 Stunden statt praktisch null nach wiederholten Endstandsabrufen.
  Diese Unterschiede sind beobachtete Untergrenzen, keine medizinische Wirkung.
- Null `context-effect-v1`, `context-approval-v1`, `context-training-case-v1`.
- Separater E-Sport-Nachcheck 13:10 Serverzeit: 139 offene Beleg-Events haben
  auch im nativen Shadow-Speicher noch keine Abrechnung; keine fiktiven
  Ergebnisse aus heutigen Teamnamen oder Fremdspielen ableiten.

Der neue lesende Diagnosebaustein `context_models/readiness.py` zählt Events
statt Abrufkopien. Er bewertet keine Gewinner, trainiert nichts und erzeugt
niemals eine Freigabe. Lokaler Test prüft unveränderte Datenbankbytes.

## Echter Tennis-Tageslauf: Ursache und Abnahmegrenze

Der Lauf 07:17–07:53:52 CEST scheiterte am 2.100-Sekunden-Tages-Scanlimit.
Modellaufbau erfolgreich; Vorbereitung von 70 Vorhersagen nach 912 Sekunden,
60 veröffentlicht nach 2.034 Sekunden. Pro Karte wurden zuvor bis zu 680.802
tourweite Referenzen verarbeitet. Das ist ein gemessener Zeitfehler, kein
Beleg für ein erfolgreiches Tagesupdate. Der kompakte v4-Pfad repariert diesen
konkreten Aufwand; ein vollständiger echter Nachlauf muss die Abnahme liefern.

## Verifikation bisher

- 274 gezielte Versions-/Speicher-/Mutations-/Belastungstests bestanden,
  einschließlich unveränderter v3-Bytes und einmaliger Quellvalidierung.
- Danach 31 Daily3-/Diagnosetests bestanden, einschließlich realem Weg
  Providerfixture → Original → Snapshot → gespeicherter Prognose → App-Signal.
- Lokale Browserprobe mit klar markierten synthetischen Beispielen bei 320 und
  1.280 Pixeln: kein horizontaler Überlauf, keine Console-Fehler. Keine
  synthetischen Beispiele auf dem VPS veröffentlichen.
- Abschließende 65 betroffene Module: 2.585 bestanden, 15 erwartete Skips,
  26 Untertests bestanden; 1.283,86 Sekunden. Drei JUnit-Metadatenwarnungen,
  keine Testfehler. Der Stand wurde während dieser Prüfung nicht verändert.
- Zusätzlich 115 Fußball-Quellen-/Budget-/Publikationstests bestanden.
- Die vorherige breite Zwischenrunde hatte 6.215 bestandene und 61 fehlgeschlagene
  Tests. Alte v3-Testannahmen, mehrfache Quellvalidierung und ein während dieser
  Runde geänderter Implementierungshash wurden korrigiert. Alle betroffenen
  Fehlermodule sind in der abgeschlossenen 65-Modul-Prüfung enthalten.
- Commit/Push und native Deployment-Abnahme stehen noch aus. Die genannten
  früheren Teiltestzahlen überlappen; keine komplett grüne Vollsuite behaupten.

## Fußball: begrenztes Quellenbudget wieder nutzbar

Die lesende Produktionsprobe fand in 29 Originalbindungen 7.059 fehlende
Quellenverweise wegen des Speicherbudgets, weitere 528 ohne native Referenz.
Das sind mehrfach verwendete Verweise, keine entsprechend vielen Spiele.
Ein konkreter Fall enthält 304 von 415 benötigten Quellen. Das 1-MiB-Quellen-
budget wurde auch bei unveränderten historischen Endständen erneut verbraucht.

Der Patch verwendet ausschließlich vollständig vorhandene FT-Bündel mit
bytegleichen nativen Inhalten und ihren **alten** tatsächlichen Empfangszeiten
wieder. Er begrenzt den Lookup auf tatsächlich empfangene native Events im
gewählten Eingangsumfang. Keine Datenbank-Inventarliste ersetzt den Anbieter.
Geänderte Ergebnisse, Teilnehmer, Termine, Rohfelder, konkurrierende Revisionen
und unvollständige Bündel werden nicht wiederverwendet. A→B→A erzeugt ein neues A.
Passt eine bereits empfangene Korrektur nicht mehr ins Budget, darf auch eine
alte passende Revision dieses Events den neuen Originalnachweis nicht freigeben.
Ausfälle, kommende Spiele und Aufstellungen werden nicht künstlich aufgefrischt.

Ein reproduzierbarer Test scheiterte vor der Anbindung und besteht danach:
Lauf 1 speichert ein von zwei historischen Spielen; Lauf 2 übernimmt dieses
ohne erneuten Speicherverbrauch und ergänzt das zweite mit demselben Budget.
Nach einem zu großen neuen Bündel werden spätere kostenlose Wiederverwendungen
weiter geprüft. Mengenlimits, Reservekonto und API-Budgets bleiben unverändert.
Das behebt eine technische Sammellücke, ist aber noch keine Modellqualifikation.

## Nicht als erledigt melden

### Produktionsabnahme c936310 und native Nachfolgereparatur

`c9363109c44d3560717353c624130574fc592d43` ist committed, auf main gepusht
und auf dem VPS eingesetzt. App/Caddy und lokale/öffentliche IPv4-Healthchecks
sind gesund, Compute-Timer wieder aktiv. Keine Backups, Datenmigration oder
Bereinigung. Der Gesamtlauf muss trotzdem getrennt bewertet werden:

- Tennisstart 13:51:03 CEST; Zustandsaufbau erfolgreich, Scan 13:52:42–14:08:33
  (951 Sekunden), Gesamtschluss 14:08:50. Kein 2100-Sekunden-Timeout.
- 85 vorbereitete Karten, 82 gespeicherte v4-Revisionen, 38 neue Elternzeilen;
  16 enthalten den echten ATP-Modellvergleich. Keine Aussage über 16 Tipps.
- Tatsächliche Referenzmengen 1–11.219 statt bis zu 680.802 pro Karte.
  Physische Snapshot-Payloads 29.644–333.913 Bytes, separat geteilte
  Referenzblöcke ausdrücklich nicht darin enthalten.
- Exit 1 wegen WTA 183996: alter Gegner Julia Avdeeva, aktuell nativ Ayla
  Aksu gegen Yuki Naito, dazu neuer Spielbeginn. Kein Überschreiben oder
  Abrechnen der alten Avdeeva-Prognose. Ein neuer Original-/Kontextnachweis
  liegt bereits vor, war aber noch nicht als eigene Shadow-Linie angebunden.
- Regulärer Wettfinder 14:07:00–14:26:13: Fußballaktualisierung abgeschlossen,
  insgesamt degraded (23 Modellkarten, null bestätigte Tipps). Drei gemeldete
  Tennis-Refreshfehler, IDs 1588/1562/1573. Lesende Einzelfallreproduktion:
  1588 und 1573 haben neu einen offenen Teilnehmer statt früher benannter
  Spielerin; 1562 lässt sich danach wieder binden. Keine pauschale Reparatur
  der Anbieterdaten oder erfolgreicher Gesamtlauf behauptet.

Lokaler Nachtrag in Abschlussprüfung: echte spätere native Gegnerwechsel
werden als neue Prognose-Elternzeile angehängt. Die erste unveränderliche
Revision verweist auf die vorherige Revision. Neue Namen allein erlauben
keinen Wechsel; erforderlich sind andere native Spieler-IDs im gleichen
Wettbewerb/Event/Tour, frühere Originalveröffentlichung und aktueller
Worker-Nachweis. A→B→A erzeugt drei Linien. Aktive Leser unterdrücken alte
Linien erst ab der tatsächlichen Nachfolgeveröffentlichung, auch nach
Abrechnung des Nachfolgers; volle Auditansichten behalten sie. Alte Preise,
Ergebnisse und Originalzeilen bleiben unverändert. Ergebnisbindung erfolgt
nur zur tatsächlich empfangenen Paarung, niemals nach dem Gewinner.

Abschlussprüfung: 1.461 bestanden, drei erwartete Skips in 42 betroffenen
Tennismodulen. Nachtrag für die ältere Tennisansicht: 92 überlappende
Fixture-/Refresh-/UI-Tests bestanden; diese Zahl nicht zur Suite addieren.
Aktive Abrechnungseingänge behalten die ursprünglichen Modell-/Preiswerte,
Auditansichten alle Altzeilen. Kein vollständiger neuer App-Gesamttest daraus
abgeleitet. Dieser Nachtrag ist als
`30f31ed1944c6c7e879fc30224377b9548a527ab` auf main/GitHub/VPS.

### Tatsächlich abgeschlossene native Abnahme und letzter Leserschutz

- Echter Tageslauf 14:50:33–15:05:20 CEST: Exit 0, **Scan OK, Gesamt OK**.
  86 Prognosen fertig verarbeitet, zwei neue Elternzeilen. Hauptscan endet
  15:05:05, Modell-/History-Veröffentlichung dauert 771 Sekunden. Gesamtpeak
  3,0 GiB, kein OOM oder 2100-Sekunden-Timeout. Das ist noch kein beliebig
  kleiner Speicherverbrauch; keine neue Bereinigung vorgenommen.
- WTA 183996: alte Zeile 1585 (Julia Avdeeva/Yuki Naito, sieben unveränderte
  Revisionen) bleibt erhalten. Neue Zeile 1637 (Ayla Aksu/Yuki Naito) referenziert
  deren vorherige Revision; nur 1637 im aktiven Leser. Beide unabgerechnet;
  keine erfundene Auszahlung, Stornierung oder alte Quote übernommen.
- Vorab rein lesender Native-Probetest validierte das echte Original, seine
  Snapshot-Referenz und die alte Revision. Eine zunächst falsche Diagnosequery
  behandelte geteilte Snapshot-Bytes als JSON; nach Verwendung des owning
  Decoders grün. Das war kein Datenbankdefekt und erzeugte keine Schreibzugriffe.
- Zusätzliche echte Leserlücke: eine native zurückgezogene/offene Paarung
  durfte nicht nur beim Refresh scheitern und trotzdem als aktuelle Karte
  stehen bleiben. `current_native_forecasts` prüft vorhandene native Fakten
  einmal je Event im Lesebatch, ohne Netzaufruf, Training oder Publikation.
  Nur weiterhin exakt passende zukünftige Paarung/Termin bleibt aktuell;
  alte Auditansichten und manuelle Abrechnung werden nicht zur Prematch-Ansicht
  umgedeutet. Legacy-Daten erhalten keine erfundene native Bestätigung.
- Letzte Regression dieses Leserschutzes: 55 Module, **1.897 bestanden,
  drei erwartete Skips, 26 Untertests**, 221,82 Sekunden. JUnit liegt unter
  `output/playwright/tennis-availability-final-20260921.xml`; kein Addieren
  überlappender vorheriger Läufe, keine behauptete gesamte App-Vollsuite.
- Erneute reine Zählung 15:13:02 CEST: **244** unabhängige rechtzeitige
  Originalevents, **144** passend zugeordnete normale Endresultate vor jeglicher
  Train-/Tune-/Testtrennung. Null Effekt-/Freigabeartefakte. Die Probe stoppt
  nach der Inventarphase; keine wiederholte Merkmalsauswertung, kein Training.

Commit/Push/VPS-Übernahme des letzten Leserschutzes stehen zum Zeitpunkt dieser
Notiz separat an. Die folgenden fachlichen Punkte bleiben ausdrücklich offen:

1. Keine empirisch qualifizierte Verletzungs-/Müdigkeitswirkung aktiv. Die
   festgelegten mindestens 200 unberührten Testevents über drei Zeitblöcke,
   Train-/Tune-Trennung, Brier-Verbesserung, Kalibrierung und Mehrfachtestprüfung
   sind nicht erfüllt. Softwaretests ersetzen diese Prüfung nicht.
2. Fußball benötigt weiterhin den exakten Live-Jointmodell-Replay und die
   Verbindung zur Kontextanwendung. 29 Originalbindungen sind keine
   Freigabe des vorhandenen älteren Raw-Poisson-Trainingspfades.
3. Daily3 außerhalb Fußball: ATP implementiert; WTA, Basketball, Eishockey und
   E-Sport besitzen weiterhin keinen belegten defensiven Vergleichsadapter.
4. Weitere reguläre Wettfinderläufe separat bewerten: offene native Teilnehmer
   sind kein erfundener technischer Erfolg. Der Tennis-Gesamtlauf selbst ist
   jetzt wie oben nachgewiesen erfolgreich abgeschlossen.

Es gibt keine künstlichen drei Tipps, erfundenen Verletzungsabschläge oder
abgesenkte Qualitätskriterien. Fehlende Ausgangsdaten bleiben offen sichtbar
in interner Diagnose; die normale Nutzeransicht erhält keinen Diagnosekatalog.
