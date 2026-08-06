# BetBoy - Projekthandbuch

## Dokumentstatus

| Feld | Verifizierter Stand |
|---|---|
| Auditzeitraum | 1. bis 6. August 2026 |
| Repository | `xantharu123-png/btts-pro-analyzer` |
| Lokaler Pfad | `C:\Users\miros\Desktop\BetBoy\betboy-app` |
| Branch | `main` |
| Basis vor der Sperrketten-Diagnose vom 6. August | `4dcfba3` |
| Aktueller Produktionsstand vor diesem Änderungslauf | `4dcfba3` (`Add all-sports selections to betting finders`) |
| Fachlicher Kernstand | Ultra-Audit plus sportzentraler Wettfinder, automatische Tagesauswahl, sportübergreifende Mehrtagessuche und phasengenaue Fußball-Scan-Diagnose |
| Verifizierter VPS-Funktionsstand vor diesem Änderungslauf | `4dcfba3`; App und Wettfinder-Timer aktiv |
| Produktions-App | `https://vps-a30a123f.vps.ovh.net/` |
| Streamlit Community Cloud | nur noch Alt-/Fallback-Deployment, nicht kanonischer Datenstand |
| Produktionsbetrieb | Ubuntu 24.04, Caddy, systemd, persistente SQLite-Daten |
| Framework | Python / Streamlit |
| Fußballkatalog | 51 eindeutige Wettbewerbe |
| Vollständiger Testlauf | 638 Tests und 5 Subtests bestanden |
| Detailaudit | `AUDIT_KIMI_2026-08-01.md` |

Dieses Dokument ist die maßgebliche technische und fachliche Übergabe. Es
enthält absichtlich keine Schlüssel, Passwörter oder Tokens. Ältere Berichte
sind nur Historie, wenn sie diesem Handbuch widersprechen.

## 1. Produktziel

BetBoy ist ein **Wettfinder**, kein Monitoring-Dashboard und kein
Quoten-Nachahmer.

Der verbindliche Ablauf lautet:

1. Das Modell bildet eine Punktwahrscheinlichkeit ohne Buchmacherquote.
2. Datenherkunft, Aktualität, Stichprobe und zeitliche Validierung werden
   geprüft.
3. Ausfälle und Wetter werden als Pflichtkontext angewendet. H2H ist nur ein
   konservativer Gegencheck: Fehlende oder kleine Direktvergleichsstichproben
   sind neutral und können weder freigeben noch blockieren. Im Fußball-Shadow-
   Lauf kurz vor Anpfiff sind bestätigte Startaufstellungen beider Teams ein
   verbindliches Gate. Im täglichen 15K-Vorlauf sind sie Zusatzinformation;
   dort bleibt jede Ausgabe ausdrücklich `SHADOW` und keine Echtgeldfreigabe.
4. Die quotenfreie Prognose bleibt sichtbar, auch wenn ein Modellgate oder
   später die Preisprüfung scheitert.
5. Erst danach wird die exakte N1Bet-Quote als Preis erfasst.
6. Die Preisprüfung verwendet eine explizit konservative Wahrscheinlichkeit
   und mindestens 3 % risikoadjustierten EV; ein fixer Prozentpunkt-Edge ist
   kein universelles Gate.
7. `RESEARCH`, `SHADOW` und `RELEASED` sind getrennte Evidenzstufen. Nur
   `RELEASED` darf einen Echtgeld-Einsatz erzeugen.
8. Pro Suche werden höchstens wenige, klar begründete Auswahlen angezeigt.

Ein manueller 15K-Vollscan über alle 51 Ligen startet ohne zusätzliche
Bestätigungsstufe. Der serverseitige Wettfinder führt pro Zieldatum genau eine
vollständige Discovery über alle 51 Ligen aus. Seine
halbstündlichen Aufwachpunkte durchsuchen danach keine Ligen erneut, sondern
prüfen nur bereits gespeicherte Kandidaten-Fixtures im Zwei-Stunden-Fenster
vor dem Anpfiff. Die ältere Browser-Nachprüfung bleibt zusätzlich auf höchstens
zwölf ausgewählte Ligen begrenzt, solange die 15K-Seite offen ist.

Die manuelle `Eigene Suche` ist nicht auf Fußball beschränkt. Fußball, Tennis,
Basketball, Eishockey, Cricket und E-Sport verwenden denselben Zeitraum:
`Heute`, `3 Tage voraus`, `7 Tage voraus` oder `14 Tage voraus`; Standard sind
sieben Tage. Das Ende bedeutet jeweils den Kalendertag in Europe/Zurich und
wird inklusive durchsucht. Alle gefundenen Termine werden zunächst
preisunabhängig erfasst. Eine Terminliste allein ist aber keine Empfehlung:
Sport-/Marktpfade ohne validiertes Prematch-Modell bleiben fail-closed.

Eine niedrige Quote ist kein Sicherheitsbeweis. Die Quote darf das Modell nicht
erzeugen, bleibt aber nach Entfernung der Buchmachermarge ein wichtiger
Marktbenchmark und der tatsächlich bezahlte Preis.

## 2. Kurzurteil

Die App besitzt eine belastbare technische Basis und ist nach diesem Audit
deutlich ehrlicher als zuvor:

- Fachliche Vetos sind standardmäßig fail-closed.
- Scan-Jobs und lokale Resultate sind sitzungsgebunden.
- Challenge-Buchungen sind nachvollziehbar und Verluste werden nicht
  automatisch zurückgesetzt.
- Shadow sammelt produktionsgleiche, versionsmarkierte Evidenz.
- Nicht unabhängig validierte Modelle dürfen keine Wettempfehlung ausgeben.
- Kein aktiver Scanner verwendet noch einen festen Edge-Grenzwert als
  universelle Freigaberegel.
- Punktprognose, Modellabschlag, Preisstatus und Evidenzstufe bleiben bei der
  jetzt direkt am Tipp eingebauten Preisprüfung getrennt.
- Smartphone und Tablet sind ohne horizontalen Seitenüberlauf bedienbar.
- Alle 51 Fußballligen kommen aus einem gemeinsamen Katalog.
- App, Shadow-Jobs und kanonische Laufzeitdaten liegen auf einem gehärteten
  persistenten VPS; der PC oder KIMI müssen dafür nicht eingeschaltet sein.
- KIMI- und Windows-Doppelstarter sind deaktiviert. Nur der VPS schreibt die
  kanonischen Shadow-Datenbanken.
- Alle API-Football-Aufrufe teilen einen atomaren, priorisierten
  Tagesbudget-Governor.
- Manuell geprüfte N1Bet-Preise in 15K und Tennis erhalten einen
  append-only Nachweis mit Hash-Kette.
- Transaktionale SQLite-Backups laufen täglich; jedes neue Archiv wird
  automatisch wiederhergestellt und per SQLite geprüft. Der aktuelle Lauf
  verifizierte 14 von 14 Datenbanken.
- Der automatische Wettfinder entdeckt pro Zieldatum einmal alle Spiele aus
  allen 51 Fußballligen und persistiert einen mathematisch bestandenen
  Tagespool. Danach werden nur konkrete Kandidaten-Fixtures kurz vor Anpfiff
  mit H2H, Ausfällen, Wetter und Aufstellungen aktualisiert. Öffentlich
  erscheinen weiterhin quotenfrei höchstens drei noch nicht gestartete Events.
- Die automatische Tagesauswahl ist direkt im Wettfinder sichtbar. Sie nennt
  Zieldatum, Zeitpunkt des letzten echten 51-Ligen-Vollscans, gefundene und
  modellierte Spiele sowie die Zahl bestandener Fußball-Auswahlen. Ein leerer
  Fußball-Pool wird nicht als fehlender Scan dargestellt.
- Die manuelle Suche kann für alle sechs Sportarten bis 14 Tage voraus laufen;
  Ergebnis-Caches sind an Sport, Filter, Start- und Enddatum gebunden.

Trotzdem ist **kein Markt als profitabel bewiesen**. Testgrün beweist
Softwareverträge, nicht Wettvorteil. Echtgeldfreigaben bleiben von sauberer
Out-of-sample-Evidenz, Closing-Line-Vergleich und korrektem Settlement abhängig.

## 3. Was in diesem Audit behoben wurde

### Freigaben und Mathematik

- Prognose, Unsicherheitsmodell, Buchmacherpreis und Echtgeldfreigabe sind
  vier getrennte Zustände.
- Die frühere globale 4-Prozentpunkte-Edge-Schwelle und die aktiven
  Tennis-Schwellen von 12/15 Prozentpunkten wurden aus den Produktgates
  entfernt. Edge bleibt ein Diagnosewert.
- Der gemeinsame Preisstandard ist jetzt:

```text
konservatives p = max(0, Modell-p - expliziter Haircut)
Risiko-EV = konservatives p * Quote - 1
Mindestquote = (1 + 0,03) / konservatives p
```

- Favoriten und Longshots werden dadurch in derselben Geldeinheit verglichen.
  Ein Prozentpunkt Edge entspricht bei Quote 2,00 etwa 2 % ROI, bei Quote
  6,00 dagegen etwa 6 % ROI.
- Die gemeinsame Inline-Preisprüfung übernimmt Punktwahrscheinlichkeit und
  modellzugehörigen Haircut gemeinsam. Der frühere doppelte Abschlag bei
  Fußball/E-Sport und der zu kleine Standardabschlag bei Tennis sind beseitigt.
- Automatisch übernommene Prozentwerte passen exakt auf 0,1-Prozentpunkt-
  Kontrollen. Für die Anzeige wird Modell-p abgerundet, der Haircut
  aufgerundet und die Mindestquote aus diesen konservativen UI-Werten neu
  berechnet.
- Alte Fußball- und Tennis-Preissignale werden über Policy-Versionen
  fail-closed ausgesperrt.
- Die interne manuelle Preisprüfung meldet `PREIS OK`, nicht mehr `JA`. Sie ist
  eine Rechenhilfe und keine Modell- oder Echtgeldfreigabe; die frühere eigene
  Navigationsseite existiert nicht mehr.
- Der Smart-Bet-Finder liefert nach bestandenem Preisgate nur
  `SHADOW_VALUE`; Einsatz und `actionable=True` sind entfernt.
- Der Challenge-Ledger erzwingt wie die Auswahlengine mindestens 3 %
  konservativen EV pro Leg. Der frühere interne 2-%-Bypass ist geschlossen.
- Kombis erhalten zusätzlich einen Modellrisiko-Abschlag pro weiterem Leg
  und pro Paar aus derselben Liga. Die App zeigt außerdem die
  annahmenfreie Fréchet-Untergrenze als Stresswert; sie ist keine
  Trefferprognose.
- `freemode` ist standardmäßig `False`.
- Ein Modell-Veto bleibt auch im Research-Modus ein Veto.
- Live-Fußball bleibt blockiert, bis eine unabhängige Live-Kalibrierung
  nachgewiesen und explizit markiert ist.
- Rotkarten-Prognosen bleiben nicht handlungsfähig, bis unabhängige
  Shadow-Evidenz vorliegt.
- Die Multi-Sport-Modellpfade entfernen keine Blocker mehr, um trotzdem eine
  Empfehlung anzuzeigen.
- Die Inline-Preisprüfung zeigt die Evidenzstufe jedes Signals und erzeugt
  daraus selbst keine Freigabe.
- BTTS wählt jetzt quotenfrei die wahrscheinlichere Seite `Ja` oder `Nein`;
  der Scanner ist nicht mehr strukturell auf `BTTS Ja` beschränkt.
- Gültig eingegebene N1Bet-Preise in 15K werden vor der Ticketauswahl
  protokolliert, also auch dann, wenn der Kandidat das Preisgate nicht
  besteht. Ein später gebuchtes Ticket referenziert exakt diese
  Preisbeobachtungs-IDs.

- Tennis-Kalibrierung wird immer in derselben alphabetischen Orientierung
  angewendet, in der sie trainiert wurde. Das Ergebnis bleibt beim Vertauschen
  der Spieler exakt komplementär.
- Tennis-Gegnerwerte werden vor beiden Match-Updates eingefroren. Der Verlierer
  sieht dadurch keine Information aus demselben Match.
- Fehlende beobachtete Märkte ergeben im Kalibrierungswächter
  `insufficient`, niemals ein falsches `ok`.
- Der exakte Tennis-Produktionsreplay bewertet beide Buchmacherseiten nach
  Haircut und Risiko-EV. ATP Hard mit Serve-Gate ergab 2021-22 bei 195 Picks
  +2,45 % ROI (95-%-Intervall -22,33 bis +27,23 %) und 2023-24 bei 142 Picks
  +9,78 % (95-%-Intervall -19,52 bis +39,09 %). Beide Intervalle enthalten
  deutliche Verluste; Tennis bleibt daher zwingend Shadow.

### H2H-Policy-Audit vom 3. August 2026

- Die frühere Regel blockierte fehlende H2H-Daten vollständig und entschied
  bereits anhand von drei Direktduellen. Bei einer tatsächlich korrekten
  70-%-Prognose hätte bloßes Binomialrauschen in rund 21,6 % der Fälle ein
  falsches Veto erzeugt.
- Fehlendes H2H und weniger als sechs aktuelle, marktspezifisch auswertbare
  Direktduelle sind jetzt neutral. Neue UEFA-Paarungen werden dadurch nicht
  mehr allein wegen fehlender gemeinsamer Historie ausgeschlossen.
- Ein H2H-Veto ist nur noch innerhalb eines Drei-Jahres-Fensters möglich. Die
  obere 95-%-Wilson-Grenze der beobachteten Trefferquote muss trotz eines
  zusätzlichen Abstands von zehn Prozentpunkten unter der konservativen
  Modellwahrscheinlichkeit liegen.
- H2H erhöht niemals Wahrscheinlichkeit, Rang oder Einsatz. Es kann bei
  starker Gegenbeobachtung nur ein Veto auslösen.
- Eckball- und Karten-H2H benötigt echte Statistiken des jeweiligen Markts.
  Vorhandene Torergebnisse dürfen dafür kein bestandenes Gate vortäuschen.
- Historisch vertauschtes Heimrecht wird vor Teamtor-, Eckball- und
  Kartenauswertungen auf die heutige Heim-/Auswärtsorientierung gedreht.
- Die H2H-Policy ist mathematisch konservativer, aber noch kein empirisch
  bewiesener Vorteil. Vor Echtgeldfreigabe bleibt eine versionsgetrennte
  Walk-forward-Ablation mit und ohne H2H-Veto Pflicht.

### Ultra-Audit vom 5. August 2026

- Der UEFA-Fallback kann Teamhistorie aus den jeweiligen Heimatligen laden und
  modellieren. Diese Rohwerte sind zwischen unterschiedlich starken Ligen aber
  nicht direkt vergleichbar. Eine nationale Offensivrate aus Liga A ist keine
  kalibrierte Stärke relativ zu Liga B.
- Jeder solche Wettbewerbstransfer trägt deshalb jetzt den expliziten Scope
  `cross_competition_unvalidated` und wird vor Kontext, Preisprüfung und Top-3-
  Auswahl gesperrt. Die Spiele werden weiterhin gefunden und als Forschung
  gezählt, verbrauchen aber keine der 20 teuren Kontextpositionen.
- Auch ein künstlich perfekter H2H-, Ausfall-, Wetter- und Aufstellungskontext
  kann dieses Transfer-Veto nicht überstimmen. Eine spätere Freigabe benötigt
  ein separat walk-forward-validiertes, ligenübergreifendes Clubstärkemodell.
- Der automatische Wettfinder akzeptiert Fußball nur noch als echtes
  `ChallengeCandidate`-Objekt und prüft den vollständigen Credibility-Vertrag
  unmittelbar vor der Ausgabe erneut. Unbekannte Evidenzstufen werden
  fail-closed verworfen.
- Writer und Reader des Wettfinder-Artefakts verwenden gemeinsam Version 3.
  Alte Artefakte werden nicht still als aktuelle Empfehlungen weitergereicht.
- Fußball-CLV-Kennzahlen, offene Counts und letzte Predictions werden nur aus
  exakt derselben Modell- und Policy-Version gebildet. Modellabhängige Caches
  sowie Tagesmarker tragen die Modellversion; eine alte Prediction desselben
  Fixtures blockiert keinen neuen, getrennten Shadow-Jahrgang.
- Tennis-Kennzahlen, Preis-Signale und Wochenberichte sind modell- und
  policygebunden. Ein alter Datensatz kann eine aktuelle Prognose desselben
  Matches nicht mehr verschlucken; historische offene Zeilen bleiben trotzdem
  für korrektes Settlement erhalten.
- E-Sport-Kalibrierung und Rotkarten-Statistik mischen keine alten
  Modellgenerationen mehr in den aktuellen Evidenzstand.
- Aktive Versionen dieses Audits sind Fußball
  `challenge-engine-2026-08-05` / `shadow-risk-ev-v4`, Tennis
  `elo-serve-platt-v2` / `risk-ev-haircut-v3`, E-Sport `subgraph-elo-v2` und
  Rotkarte `red-card-impact-2026-08-05` / `next-goal-shadow-v1`.
- Ergebnis des Audits ist eine strengere und reproduzierbarere Pipeline, kein
  Profitabilitätsbeweis. Aktuelle Versionszähler können nach dem Wechsel wieder
  bei null beginnen; alte Daten bleiben Historie und werden nicht umetikettiert.

### Automatische Auswahl und Mehrtagessuche vom 5. August 2026

- Der persistierte VPS-Wettfinder ist jetzt im Produkt sichtbar. Sein Artefakt
  wird vor der Anzeige erneut auf Version, aktuelle Preis-Policy,
  Preisunabhängigkeit, zukünftigen Startzeitpunkt und höchstens drei Kandidaten
  geprüft. Nur `PRICE_REQUIRED`-Zeilen ohne eingebettete Buchmacherquote werden
  übernommen.
- Die Anzeige trennt den Zielspieltag vom Zeitpunkt des letzten Vollscans.
  `Letzter Vollscan` stammt aus `last_discovery_at`, nicht aus einem späteren
  Artefakt-Refresh. Dadurch kann ein Kontextlauf nicht fälschlich wie eine neue
  51-Ligen-Discovery aussehen.
- Die gemeinsame manuelle Zeitraumwahl umfasst Fußball, Tennis, Basketball,
  Eishockey, Cricket und E-Sport. Erlaubt sind heute sowie 3, 7 oder 14 Tage
  voraus. Umgekehrte oder längere Intervalle werden zentral abgelehnt.
- Fußball lädt und modelliert alle Fixtures der ausgewählten 51 Ligen im
  Zeitraum. Teure Live-Kontexte bleiben auf die aussichtsreichsten Kandidaten
  begrenzt und werden nicht für chancenlose Rohtermine verschwendet.
- Tennis führt den bestehenden täglichen, zeitlich sauberen Modelllauf für
  jeden Kalendertag des Intervalls einzeln aus. Anzeige und Datenbankabfrage
  verwenden dieselben inklusiven Start-/Endgrenzen.
- Basketball lädt kommende NBA-Termine tageweise über ESPN und den
  EuroLeague-Spielplan über die offizielle EuroLeague-API. Eishockey verwendet
  den offiziellen wöchentlichen NHL-Spielplan. Alle Termine werden vor der
  Anzeige auf Europe/Zurich und das gewählte Intervall begrenzt.
- Cricket unterstützt kommende Termine über den konfigurierten RapidAPI-
  beziehungsweise CricketData-Pfad. Ohne Schlüssel oder gültige Abdeckung
  bleibt die Ausgabe leer und nennt den Providerfehler; es werden keine
  Begegnungen erfunden.
- E-Sport paginiert PandaScore-Termine bis zur Intervallgrenze. Die
  Datumsfilterung erfolgt vor teuren Teamhistorien. Pro Spieltyp werden nur die
  drei zeitlich nächsten Begegnungen tief modelliert; weitere echte Termine
  bleiben als Spielplan sichtbar, werden aber nicht als modelliert ausgegeben.
- Kommende Basketball- und NHL-Spiele werden gefunden, erhalten aber noch
  keine Prematch-Wettempfehlung: Die vorhandenen validierten Rechenpfade sind
  live-score-/clock-abhängig. Cricket besitzt weiterhin keinen validierten
  Kandidatenkern. Diese Grenzen sind bewusst fail-closed.
- Produktionsnachweis im normalen Microsoft Edge: `E-Sport`, `3 Tage voraus`,
  `CS2` lieferte am 5. August 100 kommende Ereignisse, davon 3 mit
  Teamhistorie modelliert, Quelle PandaScore. Der direkte VPS-Providerlauf
  benötigte 1,68 Sekunden. Die Oberfläche zeigte danach die quotenfreie
  Prognose samt Shadow-Blocker und Mindestquote korrekt an.

### Sperrketten- und Markt-Audit vom 6. August 2026

Der in Produktion angezeigte Lauf `Alle 51 Ligen`, `Heute`, `Beste Märkte`
wurde mit demselben Provider und derselben Engine reproduziert. Das Ergebnis
`38 gefunden`, `37 modelliert`, `0 freigegeben` war rechnerisch möglich, aber
die bisherige Erklärung in der Oberfläche war falsch: H2H, Ausfälle und Wetter
hatten nicht gemeinsam abgelehnt, sondern wurden gar nicht erreicht.

Der tatsächliche Funnel des Laufs war:

| Phase | Ergebnis |
|---|---:|
| Spiele gefunden | 38 |
| Spiele modelliert | 37 |
| UEFA-Spiele | 37 |
| UEFA-Spiele mit Heimatliga-Fallback | 36 |
| erzeugte Ergebnis-/Tormarkt-Kandidaten | 1.480 |
| Kandidaten mit unvalidiertem UEFA-Transfer | 1.440 |
| Kandidaten mit nicht bestandenem Walk-forward-Gate | 1.430 |
| Kandidaten, die nur am UEFA-Transfergate scheiterten | 7 |
| Spiele in der H2H-/Ausfall-/Wetterprüfung | 0 |
| Freigaben | 0 |

Die Sperrgründe überlappen; ihre Summen dürfen deshalb größer als 1.480 sein.
36 UEFA-Partien wurden aus den jeweiligen Heimatligen modelliert. Dieser
Domänenwechsel ist noch nicht historisch out-of-sample validiert und bleibt
fail-closed. Das einzige im eigenen Wettbewerb modellierte Spiel scheiterte
am eigenen Walk-forward-Gate. Die sieben nur am Transfergate gesperrten Märkte
werden künftig als Diagnose und ausdrücklich **nicht als Tipps** ausgewiesen.

Der Fußballkatalog enthält 90 exakt settelbare Marktdefinitionen:

| Gruppe | Definitionen | Umfang |
|---|---:|---|
| Ergebnis | 3 | 1 / X / 2 |
| Doppelte Chance | 3 | 1X / X2 / 12 |
| Beide Teams treffen | 2 | Ja / Nein |
| Gesamttore | 10 | Über / Unter 0,5 bis 4,5 |
| Teamtore | 12 | je Team Über / Unter 0,5 bis 2,5 |
| Team-Torbereiche | 4 | je Team 1-3 oder 2-4 Tore |
| Resultat-/Tor-Kombinationen | 6 | drei UND- und drei ODER-Märkte |
| Eckbälle | 30 | Gesamt und je Team |
| Gelbe Karten | 20 | Gesamt und je Team |

Im reproduzierten Lauf waren davon 40 Ergebnis-/Tordefinitionen für mindestens
ein Spiel berechenbar. Ecken und Karten erzeugten mangels passender historischer
Zählstatistik keine Kandidaten. Die Oberfläche zeigt nun `konfiguriert`,
`berechnet` und die Zahl der tatsächlichen Prüfungen je Marktgruppe, statt
diese Lücke zu verschweigen.

Wettfinder und 15K verwenden dieselbe Diagnose. Beide unterscheiden jetzt
Spiele, Marktprüfungen, bestandene Modellkandidaten, Kontext-Spiele und
Freigaben. Optionale xG-Abdeckungshinweise werden von echten technischen
Providerfehlern getrennt. Das UEFA-Gate und sämtliche mathematischen Schwellen
wurden in diesem Änderungslauf nicht gelockert.

### Jobs, Sitzungen und Challenge

- Jobs besitzen Sitzungs-Scope, Generation-ID, Stillstands-Timeout und atomare
  JSON-Writes. Das Timeout begrenzt fehlende Fortschrittsmeldungen, nicht die
  gesunde Gesamtlaufzeit eines kalten Vollscans. Ein verworfener Worker stoppt
  beim nächsten Fortschrittspunkt kooperativ und kann keinen Neustart
  überschreiben.
- Fußball-Wettfinder, 15K und Datenverwaltung starten einheitlich mit
  `Alle (51)`. Kleinere Favoriten-Sets bleiben als ausdrücklich gezählte,
  optionale Auswahl verfügbar.
- Hintergrundscanner zeigen denselben echten Fortschrittsvertrag: Prozentwert,
  aktuelle Liga beziehungsweise Arbeitsphase und verstrichene Laufzeit.
  Markt- und 15K-Scans reichen dafür den gemeinsamen Liga-, Validierungs-,
  Modellierungs- und Kontextfortschritt bis in die Oberfläche durch. Die
  Oberfläche fragt den Job alle 0,5 Sekunden ab und zeigt auch bei sehr
  schnellen Cache-Treffern sichtbar `100 % · Abgeschlossen`, bevor das
  Ergebnis erscheint.
- Ein alter Thread kann keinen neueren Lauf mehr überschreiben.
- Analyzer-Zugriffe aus Hintergrundthreads sind serialisiert.
- Persistierte Scanner-Signale sind sitzungsgebunden.
- Die Challenge verwendet pro Browser-Sitzung eine eigene lokale Ledger-Datei.
- Jede Einzahlung, Korrektur, Einsatzbuchung und Abrechnung landet in einer
  append-orientierten Transaktionstabelle.
- Ein Verlust bleibt ein Verlust. Es gibt keinen automatischen Neustart auf
  100 Euro.
- Manuelle Kapitalzufuhr wird getrennt als externe Finanzierung ausgewiesen.
- Der Shadow-Einsatz ist auf 5-25 % begrenzt; bestehende Sitzungen oberhalb
  25 % wurden serverseitig geklemmt. All-in ist nicht mehr auswählbar.
- Neben der Challenge-Simulation zeigt die App eine separate
  Viertel-Kelly-Risikoreferenz mit hartem 5-%-Cap. Negatives erwartetes
  Log-Wachstum und ein Shadow-Einsatz oberhalb dieser Referenz werden
  ausdrücklich gewarnt.
- Die tägliche 15K-Ausgabe verlangt Modell, Walk-forward, H2H, Ausfälle und
  Wetter. Aufstellungen werden angezeigt, wenn sie bereits vorliegen, blockieren
  den täglichen Shadow-Vorlauf aber nicht. Der Fußball-CLV-Lauf kurz vor Anpfiff
  verlangt sie weiterhin verbindlich.
- `wettfinder_automation.py` trennt Discovery und Kontext strikt. Eine
  Discovery läuft höchstens einmal pro Zieldatum über den gemeinsamen
  51-Ligen-Katalog und modelliert bis zu 400 eindeutige Fixtures. Ein
  fehlerhafter Tageslauf darf erst nach zwei Stunden erneut versucht werden.
- Der persistierte Fußball-Tagespool enthält höchstens 20 Events und höchstens
  acht mathematisch bestandene Märkte pro Event. Alle 30 Minuten wird nur
  geprüft, welche dieser exakten Fixture-IDs in den nächsten zwei Stunden
  starten. Ausschließlich diese IDs erhalten neue H2H-, Ausfall-, Coverage-,
  Wetter- und Aufstellungsabfragen; Spielplan- und Ligascans sind in diesem
  Pfad ausgeschlossen.
- Kontext gilt im automatischen Wettfinder höchstens 75 Minuten als frisch.
  Die öffentliche Auswahl wird eventweise dedupliziert und bleibt auf maximal
  drei Vorschläge begrenzt. Bis 23:00 Europe/Zurich bleibt der aktuelle
  Spieltag aktiv; danach wird einmal der Folgetag vorbereitet.
- Tennis und E-Sport werden aus ihren eigenen täglichen, persistierten
  Modellläufen übernommen. Basketball und NHL bleiben in ihren vorhandenen
  Live-Pfaden ereignisgetrieben; ein künstlicher täglicher Prematch-Kandidat
  wird nicht erzeugt. Cricket bleibt ohne validiertes Modell blockiert.
- Die Auswahl wird ohne angebotene Quote nach Evidenzstufe und konservativer
  Wahrscheinlichkeit sortiert, pro Event dedupliziert und auf drei begrenzt.
  Jeder Eintrag bleibt `PRICE_REQUIRED`; die exakte N1Bet-Quote wird direkt
  am ausgewählten Tipp erfasst.

### Shadow und Settlement

- Fußball-Shadow wendet dieselbe risikoadjustierte Preisprüfung wie die
  produktive Challenge an.
- Pro Fixture wird höchstens der beste preislich freigegebene Kandidat
  protokolliert.
- Fehlende Quote, fehlender Kontext oder temporärer Loggingfehler werden bis
  zum finalen Fenster erneut geprüft.
- Regulation-Wetten werden nur bei Providerstatus `FT` abgerechnet, nicht
  versehentlich nach Verlängerung oder Elfmeterschießen.
- Modell- und Policy-Version werden in jeder neuen Prediction gespeichert.
- Tennis speichert Provider-Event-ID, Quelle und exakte UTC-Startzeit.
  Gestartete oder zeitlich unverifizierbare Spiele verschwinden fail-closed
  sowohl aus dem Tennis-Wettfinder als auch aus internen Preis-Signalquellen.
- Alte Tennis-Matches erscheinen nur noch im ausdrücklich getrennten
  Shadow-Abrechnungsbereich und nicht als Wettvorschlag.
- Der Tennis-Tageslauf rechnet eindeutig normale ESPN-Finals inklusive
  getrackter Satzmärkte automatisch ab. Aufgaben, Walkover und unklare
  Ergebnisse bleiben fail-closed zur manuellen Prüfung.
- Ein Tennis-Preis-Edge darf bei einem roten Modell-Gate keine Empfehlung mehr
  persistieren.
- Tennis-CLV zählt nur mit einer zeitgestempelten N1Bet-Referenzquote aus den
  letzten 60 Minuten vor dem angesetzten Start. Nachträgliche Quoten bei der
  Ergebnisabrechnung sind ausgeschlossen.
- Tennis speichert Entry- und Closing-Preise als N1Bet-Nachweis-IDs. Closing
  wird vor dem Start eingefroren; Datenbank-Trigger verhindern spätere
  Änderungen. Alte Quoten ohne neue Nachweis-ID zählen nicht als aktuelle
  Preis- oder CLV-Evidenz.
- Tennis zeigt Modell- und de-viggten N1Bet-Brier auf derselben Stichprobe
  startzeitnaher Referenzquoten; ROI allein ist kein Freigabekriterium.
- Die KIMI-Bedingung verwendet jetzt direkt den kanonischen Projektcode und
  dieselben Zeitfenster wie der Runner.
- E-Sport verlangt ein explizites 0:0-Prematch-Ereignis und eine eindeutige
  Teamzuordnung.
- E-Sport-Signale mit alter Modellversion, fehlender Startzeit oder bereits
  erreichtem Anpfiff werden aus dem automatischen und interaktiven Wettfinder
  fail-closed entfernt.
- Offene E-Sport-Zeilen werden fair rotiert; ein temporär fehlendes Ergebnis
  wird nicht automatisch als Void entsorgt.
- E-Sport-Freigabe verlangt mindestens 300 saubere Settlements. Trefferquote
  und Brier allein reichen nicht mehr: Ohne zeitgestempelte Eröffnungs- und
  Schlussquoten, CLV und Rendite-Konfidenzintervall bleibt
  `price_evidence_ready=False`.
- Rotkarten-Signale prüfen endliche, normierte 1X2-Wahrscheinlichkeiten,
  exakt einen Platzverweis und nachvollziehbare Ereignisreihenfolge.
- Pro Rotkarten-Fixture wird nur ein unabhängiger Snapshot für die
  Evidenzstatistik gewertet.

### UX

- Die Hauptnavigation besteht nur noch aus `Wettfinder`, `Live`, `15K` und
  `Meine Tipps`. Auf Smartphones stehen diese vier Ziele in einer festen
  Bottom-Navigation; auf Tablet und Desktop zusätzlich in der Seitenleiste.
- `Einstellungen` ist kein fünfter Hauptbereich, sondern liegt separat hinter
  dem Zahnrad beziehungsweise dem Zurück-Button.
- Die früheren Seiten `Spiele`, `Märkte`, `Wett-Check`, `Multi-Sport` und
  `Tennis` sind aus der Navigation entfernt. Ihre fachlichen Funktionen liegen
  jetzt im gemeinsamen Wettfinder oder in `Meine Tipps`.
- Der Wettfinder zeigt zuerst die automatische, persistierte Tagesauswahl samt
  dezentem Zeitpunkt des letzten echten Vollscans. Danach folgt die manuelle
  `Eigene Suche`.
- Die manuelle Suche beginnt mit Sportart und Zeitraum. Fußball, Tennis,
  Basketball, Eishockey, Cricket und E-Sport teilen `Heute`, `3 Tage voraus`,
  `7 Tage voraus` und `14 Tage voraus`; sieben Tage sind der Standard.
  Sportartspezifische Felder erscheinen erst danach und bleiben flach.
- Die Sportauswahl `Alle` öffnet im Wettfinder alle sechs bestehenden Finder
  in einer einzigen Tab-Ebene. Multi-Sport-Buttons, Hintergrundjobs,
  Guthabenfelder und Ergebnisse sind dabei pro Sportart isoliert.
- Die Fußball-Wettarten `Beste Märkte`, `Ergebnis`, `Tore`, `Beide treffen`,
  `Ecken` und `Karten` filtern den vollständigen Kandidatenpool vor der
  Kontext-Shortlist. Es handelt sich nicht nur um einen Anzeige-Filter auf
  einer bereits gekürzten Top-3-Liste.
- Live verwendet eine einzige Wettart-Auswahl. Die technische Wahl der
  Live-Datenbasis ist entfernt; das strenge Daten-Gate wird automatisch
  angewendet.
- Der separate Wett-Check ist entfernt. N1Bet-Quote und exakte Auswahl werden
  unmittelbar am Modellkandidaten bestätigt.
- Preisgeprüfte `BET`- und `SHADOW`-Tipps werden sitzungsisoliert unter
  `Meine Tipps` gespeichert. `RESEARCH` und abgelehnte Preise erscheinen dort
  nicht. 15K- und Tennis-Verläufe sind im selben Bereich erreichbar.
- Die 15K-Seite enthält keinen verschachtelten Bereichsschalter mehr;
  Verlauf liegt unter `Meine Tipps`, Kontoeinstellungen hinter dem Zahnrad.
- Die 15K-Sportauswahl enthält ebenfalls `Alle` und dieselben sechs
  Sportarten. `Alle` bedeutet dort strikt alle Modelle, die den vollständigen
  15K-Ticketvertrag erfüllen; aktuell ist das nur Fußball. Nicht freigegebene
  Sportarten erzeugen keine ersatzweisen oder versteckten Fußballtipps.
- Der aktive Bereich bleibt sichtbar.
- Material-Icons ersetzen uneinheitliche Emoji-Navigation.
- Genügend Bottom-Padding verhindert die Überlagerung des Inhalts.
- Die früheren großen „So funktioniert ...“-Leerstaatkarten und illustrativen
  Beispielwetten sind aus den produktiven Finderflächen entfernt.
- Externe Team- und Markttexte werden im HTML-Beispiel escaped.

## 4. Arbeitsbereiche und Freigabestatus

| Bereich | Zweck | Aktueller Status |
|---|---|---|
| Wettfinder | Fußball, Tennis, Basketball, Eishockey, Cricket und E-Sport; gemeinsamer Suchhorizont bis 14 Tage; Fußball inklusive BTTS, Ergebnis, Tore, Ecken und Karten | je Modell `RESEARCH`/`SHADOW`/`RELEASED`; maximal drei Empfehlungen und Inline-Preischeck; zusätzliche Termine sind keine Tipps |
| Live | BTTS, Resttor, Teamtor | `RESEARCH`; bis unabhängige Live-Kalibrierung blockiert |
| 15K | bis zu drei Legs, Zielquote 2,00-3,00 | nur Shadow-Tickets; weiterhin sehr hohes Risiko |
| Meine Tipps | aktive preisgeprüfte Tipps sowie Fußball-/15K-/Tennis-Verlauf | sitzungsisoliert; Research und No-Bet werden nicht als Tipp gespeichert |
| Einstellungen | Daten, Training, API-Status und 15K-Konto | administrativ; keine Wettfreigabe |

Konkrete Blockaden:

- Basketball braucht unabhängige OOS- und Closing-Line-Evidenz.
- NHL braucht zusätzlich belastbare Goalie- und Lineup-Evidenz.
- E-Sport bleibt bis zu Kalibrierungs- **und** Price-Evidence gesperrt.
- Cricket besitzt noch keinen freigegebenen Modellkern.
- Rotkarten-Live bleibt bis zu unabhängiger Shadow-Evidenz blockiert.

## 5. Architektur

| Datei | Verantwortung |
|---|---|
| `app.py` | Streamlit-Einstieg, Navigation und Scanner-Orchestrierung |
| `config_loader.py` | INI, Umgebung und Streamlit-Secrets |
| `api_budget.py` | prozessübergreifender API-Football-Tagesbudget-Governor |
| `league_catalog.py` | kanonischer 51-Ligen-Katalog |
| `advanced_analyzer.py` | BTTS-Analyse und Modellensemble |
| `betting_math.py` | kanonische Quote-, No-Vig-, Risiko-EV-, Mindestquote- und Kelly-Mathematik |
| `price_ledger.py` | append-only N1Bet-Preisnachweise mit Hash-Kette |
| `challenge_engine.py` | Märkte, Validierung, Kontext und Ticketlogik |
| `football_recommendations.py` | gemeinsame Freigabepolicy |
| `bet_finder_ui.py` | N1Bet-Preisentscheidung |
| `tip_store.py` | sitzungsisolierte Ablage preisgeprüfter `BET`-/`SHADOW`-Tipps |
| `my_tips.py` | aktive Tipps, manueller Abschluss und gemeinsame Verlaufsnavigation |
| `ev_signal_sources.py` | versionsgebundener Signalvertrag aus Punkt-p, Haircut und Evidenzstufe |
| `wettfinder_automation.py` | tägliche 51-Ligen-Discovery, Fixture-Kontext-Refresh und quotenfreie Top-3-Verdichtung |
| `alternative_markets_tab_extended.py` | Fußball-Wettarten und manuelle Intervallsuche bis 14 Tage |
| `scan_jobs.py` | sitzungsgebundene Hintergrundjobs |
| `challenge_15k.py` | Challenge-Workflow und UI |
| `challenge_store.py` | Challenge-Ledger und Transaktionen |
| `shadow_clv_automation.py` | Fußball-Shadow, Closing und Settlement |
| `clv_tracker.py` | versionsmarkierter CLV-Ledger |
| `tennis_tab.py`, `tennis/*` | Tennis-Intervallsuche, Modell, Kalibrierung und Shadow |
| `esports_shadow.py` | E-Sport-Evidenz und Release-Status |
| `redcard_signal_log.py` | Rotkarten-Shadow und Settlement |
| `multi_sport_recommendations.py` | fail-closed Basketball-, NHL-, Cricket- und E-Sport-Kandidatenlogik |
| `scanners/basketball_scanner.py` | NBA-, EuroLeague- und NHL-Spielpläne sowie bestehende Live-Daten |
| `scanners/cricket_scanner.py` | kommende Cricket-Termine und bestehende Live-Daten |
| `scanners/esports_scanner.py` | PandaScore-Spielpläne, Paginierung und begrenzte Teamhistorien |
| `scripts/run_football_shadow_due.py` | API-schonender Football-Fälligkeitsrunner |
| `scripts/backup_runtime_databases.py` | SQLite-Backup, Restore-Prüfung und Retention |
| `deploy/systemd/*` | App-, Worker- und Timer-Units |
| `deploy/bootstrap_server.sh` | Ubuntu-Härtung und Erstinstallation |
| `deploy/update_server.sh` | reproduzierbares Fast-Forward-Deployment |

Die aktuelle Produktionsarchitektur ist bewusst ein einzelner persistenter
VPS: Caddy vor einer loopback-gebundenen Streamlit-App, systemd-Worker und
kanonische SQLite-Ledger im selben Dateisystem. Das ist für den heutigen
Single-User-Betrieb einfacher und konsistenter als ein vorschneller
Datenbankumbau.

Ohne Login existiert weiterhin keine stabile Benutzer-ID. Ein neuer Browser
kann deshalb eine neue Challenge-Sitzung beginnen. Dauerhafte
geräteübergreifende Konten benötigen Authentifizierung und ein dazu passendes
transaktionales Ledger; PostgreSQL ist dafür eine mögliche spätere Umsetzung,
aber kein Selbstzweck.

## 6. Wettmathematik

Verbindliche Grundformeln:

```text
Break-even-Wahrscheinlichkeit = 1 / Quote
Erwartungswert beziehungsweise ROI = p * Quote - 1
Probability Edge = p - 1 / Quote
Full Kelly = ((Quote - 1) * p - (1 - p)) / (Quote - 1)
konservatives p = max(0, Modell-p - Haircut)
Mindestquote bei 3 % Ziel-ROI = 1,03 / konservatives p
Kombi-p = Produkt der konservativen Leg-p * Modellrisiko-Faktor
Fréchet-Untergrenze = max(0, Summe der Leg-p - (Anzahl Legs - 1))
Log-Wachstum = p * ln(1 + f * (Quote - 1)) + (1 - p) * ln(1 - f)
```

Probability Edge und erwartete Rendite sind verschiedene Einheiten. Kelly ist
nur so gut wie die kalibrierte Wahrscheinlichkeit. Bei unsicherem `p` wird mit
einer konservativen Wahrscheinlichkeit und einem Kelly-Cap gerechnet. Der
Haircut ist ausdrücklich ein Robustheitsabschlag und kein behauptetes
statistisches Konfidenzintervall. Ein Preisgate kann ein Shadow-Signal
qualifizieren, aber niemals fehlende Out-of-sample-Evidenz ersetzen.

Der aktuelle Kombi-Modellrisiko-Faktor ist eine vorsichtige Policy:
`0,97` pro weiterem Leg und zusätzlich `0,985` pro Leg-Paar aus derselben
Liga. Das ist kein empirisch bewiesenes Korrelationsmodell. Die
Fréchet-Untergrenze ist dagegen mathematisch annahmenfrei, häufig aber null
und deshalb nur ein Stresswert. Für eine konkrete Einsatzquote wird das
erwartete Log-Wachstum separat berechnet.

### 15K-Rechnung

Bei 100 Euro Startguthaben, 25 % Einsatzanteil und Ticketquote 2,50 wächst das
Guthaben nach einem Gewinn um den Faktor:

```text
1 + 0,25 * (2,50 - 1) = 1,375
```

Ohne einen einzigen Verlust wären 16 Gewinne nötig, um 15.000 Euro zu
überschreiten. Das ist keine Prognose. Bei einer wahren Ticketchance von 42 %
liegt die Chance auf 16 Siege in Folge nur bei ungefähr 0,0001 %. Verluste,
Korrelationen, Limits und schwankende Quoten machen den Pfad zusätzlich
schwieriger.

Der Einsatzregler ist deshalb eine Shadow-Risikowahl, keine Optimierung. Die
App begrenzt ihn auf 25 %. Für eine reale Risikoreferenz verwendet sie
Viertel-Kelly und höchstens 5 % des Guthabens. Auch diese Referenz ist nur so
gut wie die geschätzte Wahrscheinlichkeit. Die App darf das Ziel
visualisieren, aber niemals als realistische oder sichere Challenge verkaufen.

## 7. Shadow- und Evidenzstand

Kanonischer VPS-Evidenzstand mit ausdrücklich datierten Prüfpunkten. Die
Zähler verschiedener Modelle wurden nicht künstlich auf denselben Zeitpunkt
umetikettiert:

| Bereich | Stand | Fachliche Aussage |
|---|---|---|
| Fußball CLV, Stand 02.08. | bestehender Verlauf migriert; 58 neue Fixtures geplant, 12 in den ersten drei VPS-Läufen bewertet, 0 Picks | Läufe fehlerfrei; kein CLV-/ROI-Urteil möglich |
| Tennis aktuelle DB, Stand 02.08. | 144 Predictions, 38 abgerechnet, 0 Picks der aktuellen Policy | Brier 0,2382; kein Closing-Benchmark, keine Price-Evidence |
| Tennis Policy-Replay 2021-22 | 195 ATP-Hard-Picks, +2,45 % ROI, 95 % −22,33 bis +27,23 % | Hypothese; Intervall enthält null |
| Tennis Policy-Replay 2023-24 | 142 ATP-Hard-Picks, +9,78 % ROI, 95 % −19,52 bis +39,09 % | späteres Fenster ebenfalls nicht beweiskräftig |
| E-Sport, Stand 05.08. | 58 Prematch-Prognosen, 20 abgerechnet, 13 Treffer, 37 offen, 1 void | Roh-Trefferquote 65,0 % bei sehr kleiner Stichprobe; keine Echtgeldfreigabe |
| E-Sport risikoadjustiert, Stand 05.08. | Ø p 37,1 %, Brier 0,3041; Kalibrierungsabstand 27,9 Prozentpunkte | 20/300 Fälle; keine Opening-/Closing-Price-Evidence; Release bleibt gesperrt |
| Rotkarten-Live | 0 unabhängige Shadow-Signale | keine Freigabe |
| Rotkarten-Historie | 1.199 Fälle aus 7.010 Spielen; Backlog 2.011 | Entwicklungsdaten, kein unabhängiger Holdout |
| 15K | keine belastbare Echtgeldhistorie | kein Erfolgsnachweis |

Wichtig zur jungen Stichprobe:

- Die vorhandenen Fußball-Fixtures reichen vom 24. Juli bis 1. August.
- Die **revidierte produktionsgleiche Price-/Policy-Version** ist erst seit
  diesem Audit aktiv.
- Viele große Ligen starten erst noch; bestätigte Aufstellungen fehlen weit vor
  dem Anpfiff erwartbar.
- Null Picks sind derzeit kein Beweis für ein schlechtes Modell und kein Grund,
  Schwellen zu lockern.
- Die nächsten Schritte sind sammeln, Dropout-Gründe zählen und Versionen
  getrennt auswerten.

Eine Freigabe darf frühestens nach mindestens 300 unabhängigen, vorab
protokollierten und korrekt abgerechneten Picks der **gleichen Modell- und
Policy-Version** diskutiert werden. Zusätzlich müssen Kalibrierung, Brier/Log
Loss gegen einen vollständigen No-Vig-Benchmark, positiver CLV und die unteren
Konfidenzgrenzen von CLV und Rendite überzeugen. ROI allein reicht nicht.

## 8. Automationen

| VPS-Automation | Zeitplan Europe/Zurich | Verifizierter Status |
|---|---|---|
| Automatischer Wettfinder | alle 30 Minuten um Minute 07/37 | Fußball-Discovery einmal je Zieldatum über 51 Ligen; danach nur exakte Kandidaten-Fixtures; Status und Top-Auswahl im Wettfinder sichtbar |
| Fußball Shadow/CLV | Fälligkeitsprüfung alle 10 Minuten | erfolgreich; maximal 60 fällige Fixtures |
| Rotkarten-Settlement | alle 30 Minuten | erfolgreich; aktuell 0 offene Signale |
| E-Sport Shadow | täglich 08:23 | Scan und Settlement einmal täglich |
| SQLite-Backup | täglich 03:17 | erfolgreich; Restore und `quick_check` automatisch, 14 Tage lokal |
| Rotkarten-Historie | täglich 05:41 | erfolgreich; Budget 350 Provider-Calls |
| Tennis-Pipeline | täglich 07:17 | erfolgreich; montags zusätzlich Wächter und Wochenreport |

Produktionsverifikation am 2. August 2026: Der erste Artefakt-v2-Lauf
verarbeitete den Discovery-Scope mit 51 Ligen, fand und modellierte die zwei
noch ausstehenden Fixtures, speicherte drei mathematische Discovery-Märkte und
prüfte den Kontext beider Events. Fußball blieb wegen der strengen Gates bei
null Freigaben; die öffentliche Top 3 kam aus dem persistierten
E-Sport-Shadowlauf. Der direkte Folgelauf brauchte rund drei Sekunden, meldete
`daily_discovery_current` und `context_status=not_due` und verbrauchte keinen
weiteren API-Football-Aufruf. Das verifiziert den Scheduling-Vertrag, nicht die
Profitabilität eines Modells.

Erneute Produktionsverifikation am 5. August 2026: Artefaktversion 3 war um
11:37 Europe/Zurich aktuell und bezog sich auf den 5. August. Der letzte echte
51-Ligen-Vollscan stammte von 01:49, fand 13 Spiele, modellierte alle 13 und
gab 0 Fußball-Auswahlen frei. Der kombinierte öffentliche Pool enthielt drei
noch nicht gestartete E-Sport-Shadow-Kandidaten. Die UI zeigt diese Tatsachen
getrennt: `Letzter Vollscan`, `51/51 Ligen geprüft`, gefunden, modelliert und
Fußball-Auswahlen. Die exakte N1Bet-Quote bleibt anschließend manuell.

Die neue 14-Tage-Auswahl ist ein **manueller Prematch-Suchbereich**, kein neuer
stündlicher Vollscan aller Sportarten. Automatisiert laufen derzeit Fußball,
Tennis und E-Sport gemäß Tabelle. Basketball, NHL und Cricket besitzen zwar
echte kommende Spielpläne im Finder, aber noch keinen automatisierten
Prematch-Evidenzlauf, weil dafür zuerst ein validierter Modell- und
Settlementvertrag benötigt wird.

Alle sieben Timer und `betboy-app.service` sind in systemd `enabled`; nach
einem Neustart laufen sie ohne Benutzeraktion weiter. Der automatische
Wettfinder darf in seinen Zwischenläufen ausschließlich den persistierten
Tagespool lesen und konkrete Fixture-IDs nachprüfen. Der Football-Shadow-Runner
prüft ebenfalls vor teurer Arbeit, ob ein Ereignisfenster fällig ist.

Der lokale Windows-Task `BetBoy Tennis Daily` und **alle** BetBoy-Automationen
in KIMI sind deaktiviert. Ihre Definitionen wurden nicht gelöscht. Vor der
KIMI-Bereinigung liegt ein Backup unter
`C:\tmp\kimi-betboy-automations-before-vps-20260802`.

App und Worker teilen dasselbe API-Football-Tageslimit über
`runtime_state/api_budget.db`. Jede Anfrage wird vor dem Provideraufruf atomar
reserviert. Hintergrundarbeit stoppt bei geschätzten 2.500 Rest-Calls,
interaktive Empfehlungen bei 750 und kritisches Closing/Settlement bei 50.
Provider-Header und `/status` können die konservative Restschätzung nur
absenken, nicht innerhalb desselben UTC-Tages künstlich erhöhen. Der
Rotkarten-Harvester läuft ebenfalls über diesen Governor; sein eigenes
350-Call-Lauflimit bleibt eine zusätzliche Grenze.

## 9. API- und Datenstand

API-Football wurde vom VPS live gegen den Provider geprüft:

| Merkmal | Stand |
|---|---|
| HTTP-/Kontostatus | 200, keine Providerfehler, aktiv |
| Plan | Pro |
| Laufzeit laut Providerprüfung | bis 19. Oktober 2026 |
| Tageslimit | 7.500 Requests |
| Prüfpunkt 02.08., ca. 15:11 Europe/Zurich | 1.523 Requests verbraucht, 5.977 verbleibend |
| Prüfpunkt 02.08., 22:39 nach 51-Ligen-Lauf | konservativ 2.188 verbraucht, 5.312 verbleibend |

API-Football ist die zentrale Quelle für Fixtures, Ergebnisse, Live-Daten,
Kontext, Statistiken und Referenzquoten. Das Abo liefert Datenqualität und
Abdeckung, aber keinen garantierten Wettvorteil.

Weitere Prematch-Provider, geprüft am 5. August 2026:

| Sport | Quelle | Produktionsstand |
|---|---|---|
| E-Sport | PandaScore | Schlüssel vorhanden; CS2-Dreitagesfenster live verifiziert |
| Basketball NBA | ESPN Scoreboard | schlüssellos; kommende Termine werden tageweise geladen |
| Basketball EuroLeague | offizielle EuroLeague-API | schlüssellos; Saisonspielplan wird datumsgefiltert |
| Eishockey NHL | offizielle NHL Schedule API | schlüssellos; Wochenpläne werden bis zum Enddatum verfolgt |
| Cricket | RapidAPI Cricbuzz oder CricketData | aktuell kein Schlüssel auf Produktion; Finder bleibt transparent leer |

Providerabdeckung und Modellfreigabe sind getrennt. Ein korrekt geladener
NBA-, EuroLeague-, NHL- oder Cricket-Termin beweist weder eine kalibrierte
Wahrscheinlichkeit noch einen Wettvorteil.

Ein separater football-data.org-Schlüssel ist im aktuellen Produktionspfad
nicht nötig. Historische CSV-Daten kommen überwiegend von
football-data.co.uk. Ein zweites Abo sollte erst aktiviert werden, wenn eine
konkrete fehlende Datenart und ein messbarer Nutzen feststehen.

Der alte Supabase-Pooler-Zugang bleibt ungültig und wird nicht mehr für den
Single-User-Produktionsbetrieb benötigt. Kanonische SQLite-Daten liegen
persistent unter `/opt/betboy/app` auf dem VPS. Die vorhandenen Laufzeitdaten
wurden über den verschlüsselten SSH-Kanal übertragen und die Einzeldateien per
SHA-256 geprüft. Der aktuelle Produktionslauf erfasste 14 Datenbanken. Alle
14 wurden aus dem ZIP zurückgelesen und bestanden `PRAGMA quick_check`; diese
Restore-Prüfung ist jetzt Teil jedes neuen Backup-Laufs.

Das löst Neustartpersistenz und zentrale Shadow-Daten, aber noch keine
Mehrbenutzer-Authentifizierung oder gerätegetrennte Konten. Ein unabhängiges
Offsite-Backup beziehungsweise OVH Automatic Backup muss im OVH-Panel separat
aktiviert und verifiziert werden; das lokale Backup auf demselben VPS allein
schützt nicht vor vollständigem Serververlust.

Die Preis-Hash-Kette erkennt normale Updates, Löschungen und partielle
Manipulation. Sie ist jedoch weder extern signiert noch unveränderbarer
WORM-Speicher: Ein Angreifer mit Root- und Codezugriff könnte Daten und
Hash-Kette gemeinsam neu schreiben. Für stärkere Beweiskraft muss der tägliche
Kopf-Hash künftig außerhalb des VPS verankert werden.

## 10. Sicherheit

Im früheren KIMI-Chat und in alter öffentlicher Git-Historie standen echte
Zugangsdaten. Aktuelle Secret-Dateien sind ignoriert, doch das entfernt keine
bereits veröffentlichten Geheimnisse.

Extern erforderliche Schritte:

1. Supabase-/Datenbankzugang rotieren.
2. Telegram-Token rotieren.
3. API-Football-, Wetter-, PandaScore- und weitere Schlüssel rotieren.
4. Neue Werte nur in Streamlit Secrets beziehungsweise lokaler `config.ini`
   speichern.
5. Danach die öffentliche Git-Historie bereinigen.

Rotation kommt vor Historienbereinigung. Diese Schritte kann der Code nicht
selbstständig erledigen, weil dafür die Providerkonten benötigt werden.

VPS-Härtung, verifiziert am 2. August 2026:

- SSH nur für `ubuntu` mit ED25519-Schlüssel; Passwort-, Keyboard-Interactive-
  und Root-Login sind effektiv deaktiviert.
- UFW erlaubt eingehend nur 22/TCP, 80/TCP und 443/TCP; Fail2ban ist aktiv.
- Streamlit lauscht nur auf `127.0.0.1:8501`; Caddy terminiert öffentliches
  HTTPS und erzwingt HTTP-zu-HTTPS.
- `config.ini` gehört `betboy:betboy` und hat Modus `600`; Laufzeitordner
  haben Modus `700`. Schlüssel wurden nicht committed oder protokolliert.
- Ubuntu-Sicherheitsupdates, Zeitzone Europe/Zurich und 2 GB Swap sind aktiv.

## 11. Test- und UX-Nachweis

Vollständiger Lauf:

```text
638 passed
5 subtests passed
```

Reproduzierbarer Windows-Befehl:

```powershell
New-Item -ItemType Directory -Path .pytest_tmp -Force
.\.codex_test_venv\Scripts\python.exe -m pytest -q `
  -p no:cacheprovider --basetemp .pytest_tmp\full
```

Edge wurde direkt per Playwright mit der installierten normalen Edge-Engine
getestet, nicht über den Codex-In-App-Browser. Am 5. August wurden die neue
Vierer-Navigation, der separate Einstellungsweg und die zentralen Finderpfade
in beiden Viewports geprüft:

| Viewport | Ergebnis |
|---|---|
| 390 x 844 | vier Bottom-Navigationsziele sichtbar; Wettfinder, Meine Tipps, 15K und mobiler Zahnradweg bedienbar; kein horizontaler Überlauf, keine Exception, keine Konsolenfehler |
| 820 x 1180 | exakt vier Sidebar-Ziele; Wettartwechsel auf Ecken, Sportwechsel auf Tennis und Zahnradweg bedienbar; kein horizontaler Überlauf, keine Exception, keine Konsolenfehler |

Zusätzlich verifiziert:

- 15K zeigt bei 100 Euro Startguthaben standardmäßig 25 Euro Einsatz.
- Der 15K-Einsatzregler hat in Produktion exakt Maximum 25; alter
  100-%-/All-in-Text ist nicht mehr vorhanden.
- Die Hauptnavigation enthält exakt vier Arbeitsbereiche.
- Der Fußball-Wettartwechsel erreicht einen eigenen Markt-Scope; Ecken und
  BTTS sind keine separaten Seiten mehr.
- Der Sportwechsel öffnet Tennis, Basketball, Eishockey, Cricket und E-Sport
  im gemeinsamen Wettfinder.
- Fußball, Tennis, Basketball, Eishockey, Cricket und E-Sport zeigen denselben
  Zeitraumwähler mit `Heute`, `3 Tage voraus`, `7 Tage voraus` und
  `14 Tage voraus`; Standard ist `7 Tage voraus`.
- Der gemeinsame Zeitraum und die sportartspezifischen Folgefelder wurden bei
  1440 Pixel Desktopbreite und 390 Pixel Smartphonebreite ohne horizontalen
  Überlauf geprüft.
- Keine sichtbaren Button- oder Label-Überläufe in den geprüften Ansichten.
- N1Bet-Preisprüfung bleibt direkt am Kandidaten erreichbar; ein bestandener
  Preis wird nur für `BET` oder `SHADOW` unter `Meine Tipps` abgelegt.
- Die echte VPS-App zeigt im normalen installierten Microsoft Edge
  `Statistikmodell aktiv; ML gesperrt` und `Live-API aktiv (Pro)`. Damit ist
  das aktive Basismodell nicht mehr mit dem gesperrten optionalen ML verwechselt.
- HTTPS liefert 200, HTTP leitet permanent auf HTTPS um.
- Backup-Erstellung und Test-Restore aller 14 enthaltenen SQLite-Dateien
  wurden auf dem VPS ausgeführt; der Job prüft dies künftig automatisch.

Produktionsverifikation des Ultra-Audits am 5. August 2026:

- Auditcode `b30ee1f` und die folgenden Produktänderungen bis `bc6b97e` wurden
  per Fast-Forward auf den VPS übernommen;
  `betboy-app.service` ist aktiv, HTTPS antwortet mit 200, null systemd-Units
  sind fehlgeschlagen und alle sieben Timer sind geladen.
- Der erzwungene Wettfinderlauf endete erfolgreich nach rund 101 Sekunden und
  schrieb Artefaktversion 3 für den 5. August.
- Der Lauf fand 13 Spiele und modellierte alle 13. Darunter waren fünf
  UEFA-Qualifikationsspiele; alle fünf erhielten Heimatliga-Historie. Diese
  Fälle wurden am unvalidierten Wettbewerbstransfer blockiert und nicht als
  fehlende Kalenderspiele ausgegeben.
- Fußball-Wettfinder und `15K` zeigen in Smartphone und Tablet jeweils
  `Alle (51)`. Kein Buttontext lief aus seinem Container.
- Der echte Produktionslauf `E-Sport` / `3 Tage voraus` / `CS2` zeigte
  100 anstehende Ereignisse, 3 tief modellierte Teamhistorien, PandaScore als
  Quelle und anschließend eine quotenfreie Prognose mit Shadow-Blocker. Der
  Test lief in der installierten Microsoft-Edge-Engine, nicht in einer
  Browsererweiterung.

## 12. Offene Prioritäten

### P0 - extern und vor ernsthafter Echtgeldnutzung

1. Alle historisch exponierten Secrets rotieren.
2. Unabhängiges Offsite-/OVH-Backup aktivieren, den Preisledger-Kopf-Hash
   extern verankern und einen Wiederanlauf nach vollständigem VPS-Verlust
   testen.
3. Authentifizierung und stabile `user_id` für Konten und Ledger einführen.
4. N1Bet-Regeln für Void, Verlängerung, Early Payout und Marktlinien
   schriftlich gegen die Settlement-Implementierung prüfen.

### P1 - Evidenz

1. Die eingefrorene, versionsmarkierte Risiko-EV-Policy über die beginnenden
   Ligen laufen lassen.
2. Dropout-Funnel nach Modell-, Kontext- und Preisgrund versionsweise
   auswerten.
3. H2H-Veto per zeitlich sauberer Ablation gegen dieselben Picks ohne H2H
   vergleichen; die Policy nur behalten, wenn sie out-of-sample Kalibrierung
   oder Log-Loss verbessert.
4. Keine Schwelle auf demselben Zeitraum wählen und beweisen.
5. Erst nach ausreichender Stichprobe CLV, Kalibrierung und No-Vig-Benchmark
   beurteilen.
6. Für UEFA- und andere ligenübergreifende Duelle ein zeitlich sauberes
   Clubstärkemodell mit gemeinsamen Gegnern oder hierarchischem Liga-Rating
   entwickeln und separat out-of-sample validieren.
7. Die heutige Ausfallregel aus bloßen Spieleranzahlen durch vorab verfügbare,
   versionsmarkierte Spielerstärke und erwartete Minuten ersetzen. Sechs
   Reservisten dürfen nicht schwerer wiegen als ein fehlender Schlüsselspieler.
8. Wettergrenzen und die Kombi-Abschläge `0,97` beziehungsweise `0,985` per
   vorregistrierter Ablation prüfen; bis dahin bleiben sie konservative
   Heuristiken und keine geschätzten Korrelationen.
9. Vor einer späteren Tennis-, E-Sport-, Basketball-, NHL-, Cricket- oder
   Rotkarten-Freigabe pro Sport und Markt eigene Kalibrierung,
   No-Vig-Benchmark, CLV, Renditeintervall und korrektes Settlement nachweisen.
10. Für Basketball, NHL und Cricket eigene leak-freie Prematch-Modelle bauen.
    Die vorhandenen Basketball-/NHL-Rechenpfade benötigen Live-Score und Uhr
    und dürfen nicht durch Nullstände in scheinbare Prematch-Modelle verwandelt
    werden.
11. Erst nach einem validierten Modell- und Settlementvertrag die tägliche
    automatische Auswahl auf weitere Sportarten ausdehnen. Reines regelmäßiges
    Laden von Spielplänen ohne Wettkandidaten ist kein Produktziel.

### P2 - Betrieb

1. PostgreSQL erst einführen, wenn Mehrbenutzerbetrieb oder horizontale
   Skalierung den zusätzlichen Fehlerraum rechtfertigt.
2. Nach jedem Push die echte VPS-App auf Commitstand und Mobilansicht
   prüfen.
3. Systemd-, Backup- und Quota-Fehler an einen externen Kanal alarmieren.
4. Bei einer Änderung des API-Plans die drei Budgetreserven bewusst neu
   festlegen und testen.
5. Ein Cricket-Datenabo erst aktivieren, wenn das Prematch-Modell definiert ist
   und ein Coverage-Test den konkreten Mehrwert gegenüber den vorhandenen
   Quellen belegt.

## 13. Betrieb und Übergabe

Lokale App:

```powershell
.\.codex_test_venv\Scripts\python.exe -m streamlit run app.py
```

Produktion:

```text
URL: https://vps-a30a123f.vps.ovh.net/
App: /opt/betboy/app
Venv: /opt/betboy/venv
Backups: /var/backups/betboy
Verifizierter Commit: bc6b97e
```

Update nach einem Push:

```bash
ssh -i C:\Users\miros\.ssh\betboy_ovh_ed25519 ubuntu@141.95.41.27
sudo /opt/betboy/app/deploy/update_server.sh
systemctl --failed
systemctl list-timers --all 'betboy-*'
sudo systemctl start betboy-wettfinder.service
journalctl -u betboy-wettfinder.service -n 50 --no-pager
```

Der VPS ist die einzige kanonische schreibende Instanz. Lokale/KIMI-Runner
dürfen nicht parallel reaktiviert werden, solange ihre Datenbanken nicht
explizit auf eine gemeinsame transaktionale Datenquelle umgestellt sind.

Vor einem Commit:

```powershell
git status --short
git diff --check
```

Die ungetrackten Dateien `logs/pipeline_2026-07-31.log` und
`logs/pipeline_2026-08-02.log` sind bestehender Laufoutput und dürfen nicht
committed oder gelöscht werden.

Verbindliche Übergaberegeln:

- Keine Geheimnisse in Chat, Git, Tests, Screenshots oder Dokumentation.
- Kein `WETTEN` ohne belastbare Modell- und Preisfreigabe.
- Kein „sicher“, „bewiesen“ oder „profitabel“ ohne unabhängige Evidenz.
- Backtest und Testgrün sind keine Echtgeldfreigabe.
- Ein Haircut ersetzt keine fehlenden Daten.
- Preis und Modell bleiben getrennt.
- Monitoring darf intern Evidenz sammeln, ist aber nicht das Nutzerprodukt.
- Junge Shadow-Daten werden gesammelt, nicht schöngeredet und nicht durch
  gelockerte Gates künstlich vergrößert.
