# BetBoy - Projekthandbuch

## Dokumentstatus

| Feld | Verifizierter Stand |
|---|---|
| Auditzeitraum | 1. bis 10. August 2026 |
| Repository | `xantharu123-png/btts-pro-analyzer` |
| Lokaler Pfad | `C:\Users\miros\Desktop\BetBoy\betboy-app` |
| Branch | `main` |
| Basis vor der Sperrketten-Diagnose vom 6. August | `4dcfba3` |
| Verifizierter Produktions-Funktionscommit | `6a59f3e` (`Harden 15K stake policy and quote consensus`) |
| Verifizierte technische Ausgangsbasis des Re-Audits | `deb35a3` (`Update handbook after production recovery check`) |
| Vor der PC-Übergabedokumentation verifizierter GitHub-/VPS-HEAD | `5fe7ef7` (`Document Claude re-audit hardening`) |
| Fachlicher Kernstand | Consumer-Wettfinder mit hartem Preis-Publishing-Gate inklusive Kurzquotenschutz, case-insensitivem Mehrbuchmachervergleich für Fußball, verständlicher Preis-Ablehnungsdiagnose, preisoffener Tennis-/E-Sport-Modellanalyse sowie persistentem 15K-Konto mit 5-%-Standard und bewusst wählbarem Hochrisikomodus |
| Verifizierter VPS-Funktionsstand | Funktionsstand `6a59f3e`; Repository-HEAD `5fe7ef7`; App aktiv, Health `ok`, alle 7 BetBoy-Timer aktiv und 0 fehlgeschlagene systemd-Units am 10. August |
| Produktions-App | `https://vps-a30a123f.vps.ovh.net/` |
| Streamlit Community Cloud | nur noch Alt-/Fallback-Deployment, nicht kanonischer Datenstand |
| Produktionsbetrieb | Ubuntu 24.04, Caddy, systemd, persistente SQLite-Daten |
| Framework | Python / Streamlit |
| Fußballkatalog | 51 eindeutige Wettbewerbe |
| Vollständiger Testlauf | 693 Tests und 5 Subtests bestanden; normale Edge-QA auf Desktop und Smartphone bestanden |
| Detailaudit | `AUDIT_KIMI_2026-08-01.md` |
| Produkt- und Entscheidungsgrundlage | `PROJEKTBIBEL.md` |
| PC-Wechsel-Runbook | `PC_WECHSEL_UEBERGABE.md` |

Dieses Dokument ist die maßgebliche technische Übergabe. Die fachliche
Produkt-, Mathematik-, UX- und Marketingleitplanke steht in
`PROJEKTBIBEL.md`; die ausführbare Rechnerübernahme in
`PC_WECHSEL_UEBERGABE.md`. Alle drei Dokumente enthalten absichtlich keine
Schlüssel, Passwörter oder Tokens. Ältere Berichte sind nur Historie, wenn sie
diesem Handbuch oder dem aktuellen Code widersprechen.

### Produktumbau vom 6. August 2026: Tipp statt Browserimport

Der lokale N1Bet-Browserimport ist **kein aktiver Produktpfad mehr**. Seine
Dateien bleiben vorerst als getestete Rollback-Historie im Repository, werden
aber weder von `app.py`, dem Wettfinder, Tennis noch der 15K Challenge
importiert. Ein Nutzer muss keine Buchmacherseite, Erweiterung oder zweites
Fenster offen halten.

Der neue verbindliche Preisweg lautet:

1. Das Modell und alle fachlichen Gates bestimmen quotenfrei die konkrete
   Auswahl und ihre Mindestquote.
2. Für exakt abbildbare Fußballmärkte lädt die App erst danach die Preise des
   API-Football-Mehrbuchmacherfeeds.
3. Ein Anbieter darf pro Markt nur einmal beitragen. Ab drei Anbietern gilt
   der Vergleich als ausreichend breit.
4. Für die Rechenfreigabe zählt nicht der werbewirksame Bestpreis, sondern das
   untere Quartil aller beobachteten Preise. Minimum, Median und Bestpreis
   werden nur transparent angezeigt.
5. Abrufzeit und Provider-Zeitstempel werden getrennt validiert: Der Abruf darf
   höchstens 90 Minuten, die letzte Provider-Beobachtung höchstens 24 Stunden
   alt sein. Damit werden frisch abgerufene, aber einige Stunden unveränderte
   Pre-Match-Märkte nicht fälschlich verworfen.
6. Fehlt der exakte Markt, ist der Vergleich zu dünn oder liegt der
   konservative Marktpreis unter der Mindestquote, darf die Auswahl nicht als
   Tagestipp erscheinen. In sportbezogenen Detailanalysen kann sie als
   ausdrücklich unfreigegebene Modellanalyse sichtbar bleiben. Es wird keine
   fremde oder synthetische Quote erfunden.

Automatisch exakt zuordenbar sind derzeit Endergebnis, Doppelte Chance, BTTS,
Gesamttore, Teamtore, Gesamt-/Teamecken und Gesamt-/Teamkarten für die jeweils
vom Provider angebotenen halben Linien. Team-Torbereiche wie `1-3`, kombinierte
Resultat/Tor-Märkte und gemischte Oder-Märkte werden modelliert, aber niemals
aus Einzelquoten synthetisiert.

Ein Produktions-Smoketest am 6. August lieferte für ein reales Spiel 8 bis 14
Anbieter. Von 80 exakt gemappten Modelllinien waren 72 im Feed vorhanden und
59 durch mindestens drei Anbieter gedeckt. Ergebnis, Doppelte Chance, BTTS,
Tor-, Teamtor- und Eckmärkte waren breit abgedeckt; Kartenmärkte waren deutlich
dünner und bleiben bei weniger als drei Anbietern gesperrt.

Tennis zeigt Match-Sieger-Modellanalyse, Modellwahrscheinlichkeit,
konservative Wahrscheinlichkeit und rechnerische Prüfschwelle. Der aktuelle
Tennis-Datenfeed besitzt noch keinen belastbaren Mehrbuchmacherpreis; ohne
bestätigten Preis ist dies ausdrücklich kein Tipp. Dasselbe gilt für E-Sport.
Der normale PandaScore-Statistikfeed enthält keine Buchmacherquoten; ein
separates Odds-Produkt wäre dafür nötig. Basketball, Eishockey und Cricket
bleiben Pre-Match fail-closed, solange kein eigenständig walk-forward-
validiertes Modell vorliegt.

Writer und Reader des VPS-Artefakts erzwingen gemeinsam genau einen Zürcher
Spieltag. Ein Ereignis von morgen kann nicht mehr in einer mit `Heute`
bezeichneten Auswahl erscheinen. Seit Artefaktversion 5 prüft der Reader
zusätzlich zwingend Status `RECOMMENDED`, Preisstatus `PLAYABLE`, exakte
Kandidatenzuordnung, Aktualität und Mindestquote. Ein Kandidat ohne
Referenzquote kann nicht mehr durch den Reader gelangen.

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
5. Erst danach wird, soweit exakt verfügbar, ein automatischer
   Mehrbuchmacher-Referenzpreis erfasst. Der Preis erzeugt oder ändert keine
   Prognose.
6. Die Preisprüfung verwendet eine explizit konservative Wahrscheinlichkeit
   und mindestens 3 % risikoadjustierten EV; ein fixer Prozentpunkt-Edge ist
   kein universelles Gate.
7. Der Nutzer sieht Auswahl und Mindestquote auch ohne automatische
   Preisabdeckung; die App erfindet daraus keine Preisfreigabe.
8. `RESEARCH`, `SHADOW` und `RELEASED` sind getrennte Evidenzstufen. Nur
   `RELEASED` darf einen Echtgeld-Einsatz erzeugen.
9. Pro Suche werden höchstens wenige, klar begründete Auswahlen angezeigt.

Ein manueller 15K-Vollscan über alle 51 Ligen startet ohne zusätzliche
Bestätigungsstufe. Der serverseitige Wettfinder führt pro Zieldatum genau eine
vollständige Discovery über alle 51 Ligen aus. Seine
halbstündlichen Aufwachpunkte durchsuchen danach keine Ligen erneut, sondern
prüfen nur bereits gespeicherte Kandidaten-Fixtures im Zwei-Stunden-Fenster
vor dem Anpfiff. Der automatische Preisvergleich wird ausschließlich für die
finalen Kandidaten-Fixtures ausgeführt und wiederholt keinen 51-Ligen-Scan.

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
- Automatische 15K-Referenzpreise tragen Quelle, Quellzeit, Abrufzeit,
  Anbieterzahl, konservativen Preis und Bestpreis. Der Ledger validiert diese
  Felder erneut, bevor ein Challenge-Tipp gespeichert wird.
- Transaktionale SQLite-Backups laufen täglich; jedes neue Archiv wird
  automatisch wiederhergestellt und per SQLite geprüft. Der aktuelle Lauf
  verifizierte 14 von 14 Datenbanken.
- Der automatische Wettfinder entdeckt pro Zieldatum einmal alle Spiele aus
  allen 51 Fußballligen und persistiert einen mathematisch bestandenen
  Tagespool. Danach werden nur konkrete Kandidaten-Fixtures kurz vor Anpfiff
  mit H2H, Ausfällen, Wetter und Aufstellungen aktualisiert. Öffentlich
  erscheinen höchstens drei noch nicht gestartete Events. Exakt verfügbare
  Fußballpreise werden nach der Auswahl automatisch angefügt.
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
- Writer und Reader des Wettfinder-Artefakts verwenden gemeinsam Version 5
  und Auswahlpolicy `price-gated-daily-recommendations-v5`. Alte Artefakte
  werden nicht still als aktuelle Empfehlungen weitergereicht.
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
  `elo-serve-platt-v3` / `risk-ev-haircut-v3`, E-Sport `subgraph-elo-v2` und
  Rotkarte `red-card-impact-2026-08-05` / `next-goal-shadow-v1`.
- Ergebnis des Audits ist eine strengere und reproduzierbarere Pipeline, kein
  Profitabilitätsbeweis. Aktuelle Versionszähler können nach dem Wechsel wieder
  bei null beginnen; alte Daten bleiben Historie und werden nicht umetikettiert.

### Automatische Auswahl und Mehrtagessuche vom 5. August 2026

- Der persistierte VPS-Wettfinder ist jetzt im Produkt sichtbar. Sein Artefakt
  wird vor der Anzeige erneut auf Version, aktuelle Preis-Policy, zukünftigen
  Startzeitpunkt und höchstens drei Kandidaten geprüft. Seit Version 5 werden
  ausschließlich `RECOMMENDED`-Zeilen mit eingebetteter, frischer und
  konservativ `PLAYABLE` bewerteter Mehrbuchmacherquote übernommen.
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

### Tennis-Zuordnungs- und Empfehlungsfix vom 6. August 2026

Der Produktionsfall `Shang Juncheng vs Luciano Darderi` deckte zwei gekoppelte
Join-Fehler auf. ESPN lieferte den chinesischen Namen in der Reihenfolge
`Shang Juncheng`, die historische ATP-Basis führt ihn als `Juncheng Shang`.
Dadurch wurden Shang fälschlich null Matches und null Aufschlagspiele
zugeordnet. Gleichzeitig wechselte der 2026er Referenzname des Montreal-Turniers
auf die französische Bezeichnung; `National Bank Open presented by Rogers`
wurde deshalb trotz bekanntem Hartplatz nicht getroffen.

Behoben wurden:

- eine roster-gestützte Namensauflösung, die eine Zweitoken-Reihenfolge nur
  dann dreht, wenn diese Alternative bereits in der Historie existiert;
- ein eigenes Identitäts-Gate und nicht mutierende Elo-Lookups für unbekannte
  Spieler;
- explizite Provider-Belagübernahme sowie Montreal-/Rogers-Aliasse;
- Tennis-Modellversion `elo-serve-platt-v3`, damit fehlerhafte alte Karten
  nicht mit korrigierten Vorhersagen vermischt werden;
- eine fail-closed Karte: rote Modell-Gates zeigen `KEINE EMPFEHLUNG` und
  verbergen Rohwahrscheinlichkeit, Mindestquoten und Preisfelder;
- leere statt erfundener N1Bet-Standardquoten sowie ein eindeutiger
  `SHADOW-TIPP: Sieg Spieler @ Quote` erst nach bestandenem Preischeck.

Mit korrekt aufgelösten Daten besitzt der konkrete Fall 190 zu 335 historische
Matches, rund 329 zu 848 zeitgewichtete Service-Games und den Belag `Hard`.
Das Modell ergibt 61,09 % Shang zu 38,91 % Darderi. Die zuvor sichtbaren
5 % zu 95 % waren ein unzulässiger Rohwert aus dem fehlgeschlagenen Join. Bei
den damaligen Platzhalterpreisen 1,50 / 2,60 wäre auch die korrigierte Rechnung
klar `KEINE WETTE` gewesen. Der aktuelle Produktpfad zeigt stattdessen den
konkreten Tennis-Tipp mit Mindestquote und benötigt keinen Browserimport.

### Historischer N1Bet-Preisimport vom 6. August 2026 - stillgelegt

Dieser Abschnitt dokumentiert den damaligen Versuch und ist **keine aktuelle
Betriebsanleitung**. Der Importer wurde am selben Tag durch den oben
beschriebenen Consumer-Preisweg aus allen aktiven Oberflächen entfernt.

API-Football Pro wurde gegen seine aktuelle Buchmacherliste geprüft: Der
Provider führt 33 Buchmacher, aber nicht N1Bet. Eine fremde Aggregatorquote
darf deshalb nicht als N1Bet-Preis etikettiert werden. Der neue Importweg ist
eine lokale Manifest-v3-Erweiterung für normales Chrome beziehungsweise Edge:

- N1Bet-Content-Script liest ausschließlich sichtbare Dezimalquoten und legt
  sie für höchstens 15 Minuten im lokalen Browser-Speicher ab;
- ein BetBoy-Content-Script übergibt den Snapshot über eine unsichtbare
  Streamlit-Komponente an die aktuelle Browser-Sitzung; Preise oder
  Zugangsdaten werden nicht auf einen separaten Importserver übertragen;
- Wettfinder, Live, Tennis und 15K besitzen eine gemeinsame kompakte
  `N1Bet sync`-Zeile; die Erweiterung liegt unter Einstellungen als ZIP bereit;
- der Python-Trust-Boundary akzeptiert nur HTTPS-Quellen von `n1bet.com`,
  gültige Dezimalquoten und aktuelle Zeitstempel;
- Pre-Match-Preise verfallen nach zehn Minuten, Live-Preise nach 60 Sekunden;
- Ereignis, beide Teilnehmer, Markt, Auswahl, Team-Scope und Linie müssen
  eindeutig passen. Konflikte, falsche Linien, Live-/Pre-Match-Verwechslungen
  und mehrdeutige Treffer werden fail-closed verworfen;
- eine manuell geänderte Quote wird niemals automatisch überschrieben;
- der Import füllt nur den Preis. Die bestehende Auswahlbestätigung,
  Modellfreigabe, Risiko-EV-Prüfung und Speicherung bleiben unverändert;
- die Erweiterung liest weder Login noch Passwort oder Wettschein und kann
  keine Wette platzieren.

Der Entwicklungsstandort erhielt beim direkten Aufruf von N1Bet eine
schweizerische HTTP-451-Sperrseite. Es wurde bewusst kein Geo-Block umgangen.
Parser, Bridge, ZIP, Streamlit-Vorbelegung und strikte Zuordnung wurden mit
synthetischen N1Bet-DOM-/Payload-Fällen getestet. Ein realer Selektor-Abgleich
ist für das aktuelle Produkt nicht mehr erforderlich; die Dateien bleiben nur
als nicht eingebundene Rollback-Historie erhalten.

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
- Die Challenge verwendet pro browserstabiler Konto-ID eine eigene lokale
  Ledger-Datei. Ein Streamlit-Neustart oder neuer Websocket erzeugt dadurch im
  selben Browser nicht mehr automatisch ein neues 100-Euro-Konto.
- Jede Einzahlung, Korrektur, Einsatzbuchung und Abrechnung landet in einer
  append-orientierten Transaktionstabelle.
- Ein Verlust bleibt ein Verlust. Es gibt keinen automatischen Neustart auf
  100 Euro.
- Manuelle Kapitalzufuhr wird getrennt als externe Finanzierung ausgewiesen.
- Der Shadow-Einsatz ist auf 5-25 % begrenzt. 5 % ist der sichere
  Produktstandard; 10-25 % müssen im Konto bewusst gewählt werden und werden
  als aggressive Challenge-Simulation bezeichnet. Die Policy-v2-Migration
  setzt alte implizite 25-%-Defaults einmalig auf 5 % zurück. All-in ist nicht
  auswählbar, und der Ledger klemmt manipulierte Altwerte weiterhin defensiv.
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
- Tennis und E-Sport bleiben interne Modellanalysen, solange kein exakt
  zuordenbarer Preisfeed vorliegt. Sie dürfen ohne frischen spielbaren Preis
  weder die öffentliche Top 3 belegen noch als konkrete Tagestipps erscheinen.
- Für Fußball werden bis zu zehn fachlich freigegebene Kandidaten exakt
  bepreist. Erst aus den Preisstatus-`PLAYABLE`-Zeilen werden eventweise
  dedupliziert maximal drei öffentliche Tagestipps ausgewählt.

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
  Eine offene Wette und ihre Ergebniswahl sind zusätzlich direkt auf der
  15K-Seite sichtbar.
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
| Wettfinder | Fußball, Tennis, Basketball, Eishockey, Cricket und E-Sport; gemeinsamer Suchhorizont bis 14 Tage; Fußball inklusive BTTS, Ergebnis, Tore, Ecken und Karten | je Modell `RESEARCH`/`SHADOW`/`RELEASED`; maximal drei konkrete Tipps; automatische Fußball-Referenzquote, sonst Mindestquote |
| Live | BTTS, Resttor, Teamtor | `RESEARCH`; bis unabhängige Live-Kalibrierung blockiert |
| 15K | bis zu drei Legs, Zielquote 2,00-3,00, automatischer konservativer Mehrbuchmacherpreis | nur modell- und preisgeprüfte Challenge-Tipps; weiterhin sehr hohes Risiko |
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
| `price_ledger.py` | append-only Nachweise für den stillgelegten manuellen Preisweg |
| `market_consensus.py` | exakte API-Football-Marktabbildung, Mehrbuchmacher-Konsens, Frische und Preisstatus |
| `challenge_engine.py` | Märkte, Validierung, Kontext und Ticketlogik |
| `football_recommendations.py` | gemeinsame Freigabepolicy |
| `bet_finder_ui.py` | kundenorientierte Tippkarte, Mindestquote und automatischer Preisstatus |
| `tip_store.py` | sitzungsisolierte Ablage preisgeprüfter `BET`-/`SHADOW`-Tipps |
| `my_tips.py` | aktive Tipps, manueller Abschluss und gemeinsame Verlaufsnavigation |
| `ev_signal_sources.py` | versionsgebundener Signalvertrag aus Punkt-p, Haircut und Evidenzstufe |
| `wettfinder_automation.py` | tägliche 51-Ligen-Discovery, Fixture-Kontext-Refresh, spieltagreine Top-3-Verdichtung und nachgelagerte Fußballpreise |
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

Ohne Login existiert weiterhin keine geräteübergreifende Benutzer-ID. Die App
erzeugt deshalb lokal im Browser eine zufällige 128-Bit-Konto-ID und verwendet
sie nach Browser- und App-Neustarts erneut. Ein anderes Gerät, ein anderer
Browser oder gelöschte Website-Daten beginnen weiterhin mit einem neuen Konto.
Dauerhafte geräteübergreifende Konten benötigen Authentifizierung und ein dazu
passendes transaktionales Ledger; PostgreSQL ist dafür eine mögliche spätere
Umsetzung, aber kein Selbstzweck.

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

Bei 100 Euro Startguthaben, dem neuen 5-%-Standard und Ticketquote 2,50 wächst
das Guthaben nach einem Gewinn um den Faktor:

```text
1 + 0,05 * (2,50 - 1) = 1,075
```

Ohne einen einzigen Verlust wären damit 70 Gewinne nötig, um 15.000 Euro zu
überschreiten. Der bewusst wählbare 25-%-Modus hat weiterhin Faktor 1,375 und
benötigt rechnerisch 16 Gewinne. Das ist keine Prognose: Bei einer wahren
Ticketchance von 42 % liegt bereits die Chance auf diese 16 Siege in Folge nur
bei ungefähr 0,0001 %. Verluste, Korrelationen, Limits und schwankende Quoten
machen beide Pfade zusätzlich schwieriger.

Der Einsatzregler ist deshalb eine Shadow-Risikowahl, keine Optimierung. Die
App startet bei 5 % und begrenzt die bewusste Hochrisikowahl auf 25 %. Für eine
reale Risikoreferenz verwendet sie Viertel-Kelly und höchstens 5 % des
Guthabens. Auch diese Referenz ist nur so gut wie die geschätzte
Wahrscheinlichkeit. Die App darf das Ziel visualisieren, aber niemals als
realistische oder sichere Challenge verkaufen.

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

Livekontrolle am 10. August 2026: Alle sieben Timer waren mit jüngsten Läufen
und nächsten Fälligkeiten in systemd gelistet. `betboy-app.service` war
`active`, der Streamlit-Health-Endpunkt antwortete mit `ok`,
`systemctl --failed` enthielt keine Unit und das jüngste sichtbare lokale
Backup war `betboy-sqlite-20260810T011730Z.zip`.

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
657 passed
5 subtests passed
3 JavaScript tests passed
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
- Fußball-Tippkarten zeigen den automatischen Mehrbuchmacherstatus direkt.
  Ein bestandener Preis wird nur für `BET` oder `SHADOW` unter `Meine Tipps`
  abgelegt; ein Browserfenster ist dafür nicht erforderlich.
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

Produktionsverifikation der Sperrketten-Diagnose am 6. August 2026:

- Funktionscommit `fb140ba` wurde per Fast-Forward auf den VPS übernommen;
  `betboy-app.service` ist aktiv, HTTPS antwortet mit 200 und es gibt keine
  fehlgeschlagene systemd-Unit.
- Der echte Edge-Lauf verwendete `Sport: Alle`, `Zeitraum: Heute`,
  `Beste Märkte` und `Alle 51`. Der Fortschritt zählte korrekt von Liga 1/51
  über die UEFA-Heimatliga- und Validierungsphasen bis zum Ergebnis.
- Nach rund drei Minuten zeigte Produktion 1.480 Marktprüfungen aus 37
  modellierten Spielen und erklärte korrekt, dass kein Kandidat das
  Modell-/Walk-forward-Stadium verließ. H2H, Ausfälle und Wetter wurden somit
  nicht fälschlich als gescheiterte Prüfungen bezeichnet.
- Die UEFA-Zeile wies 37 gefundene Spiele, 36 Heimatliga-Modelle und ein Spiel
  ohne ausreichende Teamstichprobe aus. Die xG-Meldungen für Liga 848 und 165
  erschienen als Datenabdeckung, nicht als angebliche technische Ablehnung.
- Die lokale App wurde zusätzlich in der installierten Edge-Engine bei
  390 x 844 und 820 x 1180 geprüft: kein horizontaler Überlauf, keine
  JavaScript- oder Konsolenfehler.

Produktionsverifikation des Tennis-Zuordnungsfixes am 6. August 2026:

- Die Funktionscommits `0883677` und `f61b496` wurden per Fast-Forward auf den
  VPS übernommen. App und Tennis-Timer sind aktiv, HTTPS antwortet mit 200 und
  es gibt keine fehlgeschlagene systemd-Unit.
- Der echte ESPN-Lauf lud 69 Fixture-Einträge und speicherte 36 entschiedene
  Paarungen unter `elo-serve-platt-v3`. Alte v2-Karten werden in der aktuellen
  Finderansicht nicht mit v3 gemischt.
- `Shang Juncheng vs Luciano Darderi` steht in Produktion mit `Hard`, 190 zu
  335 Matches, rund 329 zu 848 zeitgewichteten Service-Games sowie 61,09 % zu
  38,91 %. Alle vier Modell-Gates sind grün.
- Die installierte normale Microsoft-Edge-Engine bestätigte bei 1440 x 1000
  und 390 x 844: leere N1Bet-Felder statt Platzhalterpreisen, sichtbarer
  Modellstatus, sichtbarer Sperrstatus, standardmäßig eingeklappte Nebenmärkte,
  kein horizontaler Überlauf und keine Konsolenfehler.
- API-Football und football-data.org liefern keine Tennisdaten. Der aktuelle
  Tennis-Spielplan kommt primär von SofaScore und auf dem VPS aus dem
  ESPN-Fallback; Belag und Historie werden mit der lokalen ATP-Datenbasis
  verbunden.

Produktionsverifikation des N1Bet-Browser-Imports am 6. August 2026:

- Funktionscommit `175523e` wurde per Fast-Forward auf den VPS übernommen;
  `betboy-app.service` ist aktiv, interne und öffentliche Health-Endpunkte
  antworten mit `200 ok`, und es gibt keine fehlgeschlagene systemd-Unit.
- Manifest, Content-Scripts, Streamlit-Bridge und der serverseitig erzeugte
  Erweiterungsdownload sind im Produktions-Checkout vorhanden.
- 657 Python-Tests, 5 Subtests und 3 JavaScript-Tests bestehen. Darunter sind
  End-to-End-Vorbelegung des Streamlit-Preisfeldes, Quellen-/Altersprüfung,
  Tennis-Sieger, Fußballmärkte, Team-Scope, Linien, Konflikte und Schutz einer
  manuellen Eingabe.
- Der echte N1Bet-DOM konnte aus dem Schweizer Entwicklungsnetz wegen HTTP 451
  nicht geprüft werden. Produktion wird deshalb nicht als live-DOM-verifiziert
  bezeichnet; dieser eine Browser-Abnahmeschritt bleibt offen.

Diese Verifikation beschreibt nur den damaligen Zwischenstand. Der
Browserimport wurde mit `8d9b447` aus allen aktiven Nutzerpfaden entfernt und
ist keine Produktvoraussetzung mehr.

Produktionsverifikation des Consumer-Wettfinders am 6. August 2026:

- Funktionscommit `8d9b447` wurde per Fast-Forward auf den VPS übernommen.
  `betboy-app.service` ist aktiv, interne und öffentliche Health-Endpunkte
  antworten mit HTTP 200, der Wettfinder-Timer ist aktiv und enabled, und es
  gibt keine fehlgeschlagene systemd-Unit.
- Der erzwungene erste Artefakt-v4-Lauf endete erfolgreich. Er durchsuchte alle
  51 Fußballwettbewerbe, fand 38 Spiele und modellierte 37 davon. UEFA-Duelle
  blieben wegen der noch nicht validierten ligenübergreifenden Übertragung
  gesperrt; dies ist ein fachliches Fail-closed-Ergebnis und kein Scanfehler.
- Das Artefakt trägt Version 4 und Auswahlpolicy
  `daily-discovery-context-refresh-v4`. `target_search_date`, Fußball-Suchdatum
  und alle drei ausgegebenen Kandidaten liegen ausschließlich am 6. August in
  der Zeitzone Europe/Zurich. Der frühere Heute/Morgen-Leak ist damit auch in
  Produktion ausgeschlossen.
- Die drei aktuellen Tageskandidaten sind zwei Tennis-Match-Sieger und ein
  E-Sport-Match-Sieger. Sie zeigen Auswahl, Modellwahrscheinlichkeit,
  konservative Wahrscheinlichkeit und Mindestquote direkt. Weil kein
  Fußballmarkt die fachlichen Gates passierte, enthält dieser konkrete Lauf
  erwartungsgemäß noch keine automatische Fußball-Referenzquote.
- Der vollständige Stand besteht 666 Python-Tests, 5 Subtests und 3
  JavaScript-Tests. Die normale installierte Microsoft-Edge-Engine bestand die
  sichtbare Abnahme bei 1440 x 1000, 820 x 1180 und 390 x 844 ohne horizontalen
  Überlauf, ohne Konsolenfehler und ohne sichtbare N1Bet-Abhängigkeit.

Produktionsverifikation des harten Preis-Publishing-Gates am 8. August 2026:

- Ausgangsfehler war `DOTA2 · Level UP vs Team Lynx`: 68,15 %
  Modellwahrscheinlichkeit wurden wegen 25,72 Prozentpunkten Unsicherheit auf
  42,43 % konservativ reduziert. Daraus folgt rechnerisch die Mindestquote
  2,43. Bei einer angebotenen Quote um 1,30 wären jedoch bereits der rohe
  Modell-EV rund -11,4 % und der konservative EV rund -44,8 %. Die Rechnung
  war korrekt, die Veröffentlichung als `Tagestipp` war falsch.
- Ursache war die Reihenfolge: Zuerst wurden sportübergreifend drei
  Modellkandidaten gewählt; erst danach wurde nur für die enthaltenen
  Fußballmärkte eine Quote geladen. `TOO_LOW`, `UNAVAILABLE` und
  Shadow-Kandidaten blieben dadurch sichtbar und belegten Plätze.
- Artefaktversion 5 prüft nun zunächst bis zu zehn finale Fußballkandidaten
  preislich. Nur ein frischer, exakt zugeordneter Mehrbuchmacherpreis mit
  Status `PLAYABLE` gelangt anschließend in die maximal drei öffentlichen
  Empfehlungen. `BORDERLINE`, `TOO_LOW`, `THIN`, `STALE` und `UNAVAILABLE`
  werden nicht veröffentlicht.
- Der Reader wiederholt das Preisgate unabhängig: `quote_required=true`,
  Status `RECOMMENDED`, Preisstatus `PLAYABLE`, Kandidaten-ID, Mindestquote und
  Preisalter müssen gemeinsam stimmen. Ein manipuliertes oder altes Artefakt
  fällt geschlossen aus.
- Der erste echte v5-Produktionslauf durchsuchte 51 Wettbewerbe, fand 58
  Spiele, modellierte 39 und ließ drei Fußballkandidaten durch die fachlichen
  Gates. Der aktuell fällige Preischeck ergab einmal `TOO_LOW`; veröffentlicht
  wurden deshalb korrekt null Tagestipps. Level UP und alle unbepreisten
  Tennis-/E-Sport-Kandidaten fehlen vollständig im öffentlichen Array.
- Funktionscommit `d7fc216` läuft auf dem VPS. 669 Tests und 5 Subtests
  bestehen. Die normale Microsoft-Edge-Engine bestätigte die Produktions-App
  bei 1440 x 1000 und 390 x 844: strikter Leerzustand, kein `MODELLTIPP`, kein
  falscher `Tagestipp 1`, null horizontaler Überlauf, null Konsolenfehler und
  erfolgreicher Navigationswechsel `Meine Tipps` zurück zum `Wettfinder`.

Produktionsabgleich der Preis-Ablehnungsdiagnose am 8. August 2026:

- Das Feld `bookmaker_data_used` bedeutete bisher fälschlich
  „mindestens ein Tipp veröffentlicht“. Dadurch stand es bei einer real
  vorhandenen, aber zu niedrigen Quote auf `false`. Es bedeutet jetzt korrekt
  „mindestens ein exakter Preisvergleich wurde verwendet“. Preis-Evidenz und
  Veröffentlichungszahl sind getrennte Größen.
- Der validierte Reader akzeptiert deshalb auch ein leeres Empfehlungsarray
  mit echter Preis-Evidenz. Umgekehrt bleibt jeder veröffentlichte Kandidat
  ohne `bookmaker_data_used=true`, `PLAYABLE`-Status und erneut validierte
  Referenzquote gesperrt.
- Die automatische Tagesauswahl nennt bei null Tipps nun den konkreten
  Preisgrund: unter Mindestquote, exakt passender Markt nicht verfügbar, nur
  einzelne Anbieter ausreichend, zu wenige Anbieter, veraltet oder ungültige
  Mindestquote. Die Modell- und Kontextgates wurden nicht gelockert.
- Der echte VPS-Folgelauf unter `9486e0f` verwendete den vorhandenen
  51-Wettbewerbe-Tagespool ohne unnötigen Vollscan: 58 Spiele gefunden, 39
  modelliert, drei fachlich bestandene Fußballmärkte, drei exakte
  Mehrbuchmachervergleiche, alle drei `TOO_LOW`, null veröffentlichte Tipps.
  Das Artefakt trägt korrekt `bookmaker_data_used=true`.
- 671 Tests und 5 Subtests bestehen. Die normale installierte Edge-Engine
  bestätigte bei 1440 x 1000 und 390 x 844 die sichtbare Zeile
  `3 Modellmärkte geprüft · 3 unter der Mindestquote`, alle sechs Sport-Tabs,
  den aktiven Wechsel Fußball/Tennis, die ehrliche 15K-`Alle`-Grenze, null
  horizontalen Überlauf und null Konsolenfehler.

Produktionskorrektur der marktbezogenen Freigabe am 8. August 2026:

- Eine zu niedrige Quote sperrt ab Auswahlpolicy v6 nur noch den konkreten
  Markt, nicht mehr die gesamte Begegnung. Beispiel: Ist `Sieg Bayern` zu
  billig, bleiben fachlich bestandene Alternativen wie `Unter 4,5 Tore`,
  Teamtore, Doppelte Chance, Ecken oder Karten für denselben Preisvergleich
  erhalten.
- Wettfinder und 15K halten bis zur Preisprüfung bis zu zehn Spiele mit
  jeweils höchstens acht glaubwürdigen Märkten. API-Football wird weiterhin
  nur einmal je Spiel abgefragt; alle exakten Märkte werden aus derselben
  Antwort gelesen. Erst nach den Statuswerten `PLAYABLE`, `TOO_LOW`,
  `UNAVAILABLE` und so weiter wird auf höchstens einen Markt je Spiel und drei
  öffentliche Empfehlungen reduziert.
- Der 15K-Worker verwendet denselben Mehrmarkt-Pool. Die sichtbare kompakte
  Modell-Shortlist bleibt klein, die finale Ticketberechnung darf aber eine
  spielbare Alternative desselben Spiels wählen, wenn der zunächst stärkste
  Modellmarkt preislich ausscheidet.
- Der erste v6-Vollscan deckte zusätzlich einen Laufzeituhrfehler auf: Bei
  einem zwölf Minuten dauernden Scan blieb die interne Uhr auf der Startzeit
  stehen und behandelte später geprüfte Kandidaten als Zukunftsdaten. Der
  Runner aktualisiert die Echtzeit nun nach Discovery, Kontext und
  Quotenabruf; das gewählte Spieltagsdatum bleibt dabei stabil.
- Der korrigierte VPS-Lauf unter `1574e6c` verwendete den vorhandenen
  51-Ligen-Tagespool: 54 Spiele gefunden, 36 modelliert, neun glaubwürdige
  Märkte aus drei Spielen gespeichert und alle neun preisgeprüft. Acht waren
  `TOO_LOW`, einer `UNAVAILABLE`, daher korrekt null Empfehlungen. Zuvor waren
  wegen des Uhrfehlers nur drei Märkte aus einem Spiel geprüft worden.
- 676 Tests und 5 Subtests bestehen. Die normale installierte
  Microsoft-Edge-Engine bestätigte die Produktion bei 1440 x 1000 und
  390 x 844: korrekte Preisdiagnose, Sport- und 15K-Wechsel, null
  horizontaler Überlauf und null Konsolenfehler.

Verbindlicher Abdeckungsabgleich und letzter Quotenpfad am 8. August 2026:

- `Alle (51)` bedeutet alle 51 im BetBoy-Katalog konfigurierten
  Fußballwettbewerbe, nicht jede weltweit bei API-Football vorhandene Liga.
  Der automatische Tageslauf fragt alle 51 für genau seinen Zielspieltag ab.
  Im verifizierten Lauf wurden 54 Spiele gefunden und 36 mit ausreichender
  Historie modelliert. Fehlende oder ungültige Historie wird nicht erfunden.
- Alle gültig modellierbaren Fußballspiele durchlaufen die lokale
  Modellrechnung. Teurer Pflichtkontext bleibt auf die besten 20 Spiele
  begrenzt; die automatische Preisprüfung auf die besten zehn Spiele mit
  höchstens acht glaubwürdigen Märkten je Spiel. Somit bedeutet
  `alle Spiele modelliert` nicht `jedes Spiel vollständig kontext- und
  quotengeprüft`.
- Der Audit fand nach der v6-Umstellung noch einen alten Pfad in `Eigene
  Suche`: Dort wurden Preise weiterhin nur für die bereits auf einen Markt je
  Spiel reduzierte Shortlist geladen. Commit `7706708` führt nun auch dort den
  Mehrmarkt-Pool bis zum Preisgate, verwirft nur den konkreten zu billigen
  Markt und wählt erst danach einen spielbaren Markt je Begegnung. Die drei
  Fußballpfade Automatische Tagesauswahl, 15K und Eigene Suche verwenden damit
  dieselbe Reihenfolge.
- `Sport: Alle` im Wettfinder öffnet sechs Sport-Tabs. Es startet keinen
  gemeinsamen automatischen Vollscan über alle Sportarten. Fußball ist
  derzeit der einzige vollständig automatisierte Prematch-Empfehlungspfad.
- Tennis läuft täglich und liefert persistierte Modell-/Shadow-Signale, besitzt
  im automatischen Tagespublisher aber noch keinen exakten automatischen
  Marktpreis. E-Sport läuft ebenfalls täglich, bleibt bis zur eigenen
  Kalibrierungs- und Preisevidenz ein Shadow-Modell. Basketball und Eishockey
  besitzen nur nicht freigegebene Live-/Suchpfade, kein validiertes
  Prematch-Publishing. Cricket bleibt ohne validiertes Modell gesperrt.
- Das reine 3-%-Risiko-EV-Gate konnte bei extrem hoher Modellwahrscheinlichkeit
  rechnerische Mindestquoten um `1,05` zulassen. Diese Mathematik bleibt für
  Forschung und Diagnose unverändert; als sichtbare Produktempfehlung sind
  solche Preise wegen ihrer asymmetrischen Verlustwirkung nicht mehr zulässig.
- Normale Wettfinder-, Live-, Tennis- und Multi-Sport-Tipps benötigen jetzt
  mindestens Dezimalquote `1,20`; jedes 15K-Leg mindestens `1,25`. Die
  mathematisch berechnete EV-Mindestquote gilt weiterhin, falls sie höher ist.
  Ein zu kurzer Markt sperrt nur diesen Markt. Andere Märkte desselben Spiels
  bleiben im Mehrmarkt-Pool und können nach Preisprüfung nachrücken.
- Die Regel ist in Kandidatenbau, automatischem Mehrbuchmacher-Publisher,
  manueller Preisprüfung, 15K-Ticketauswahl, Tennis-Siegern, Tennis-Satzmärkten
  und dem produktionsgleichen Tennis-Policy-Replay identisch umgesetzt. Neue
  Policy- und Snapshot-Versionen verwerfen alte, inkompatible Empfehlungen und
  erzwingen im VPS-Lauf einen frischen Tagespool.
- 690 Tests und 5 Subtests bestehen. Normales Microsoft Edge bestand erneut
  1440 x 1000 und 390 x 844 mit allen sechs Tabs, korrekter Preisdiagnose,
  null horizontalem Überlauf und null Konsolenfehler.

### 15K-Konto- und Abrechnungsreparatur vom 8. August 2026

- Ursache des wiederholten 100-Euro-Stands war kein Rechenfehler im
  Auszahlungsledger, sondern die zufällige Streamlit-Sitzung als Konto-ID. Jede
  neue Sitzung zeigte deshalb eine andere leere Ledger-Datei. Der Speicher-Scope
  kommt nun aus einer zufälligen browserlokalen 128-Bit-ID; Job-Scopes bleiben
  weiterhin bewusst sitzungsspezifisch.
- Beim offiziellen 15K-Tagestipp werden vor dem Speichern der tatsächlich
  gespielte Einsatz und die tatsächliche Gesamtquote erfasst. Der Einsatz wird
  sofort centgenau abgezogen. Ein Gewinn bucht `Einsatz × Gesamtquote`, ein
  Verlust keine Auszahlung und ein Storno den Einsatz zurück.
- Offene 15K-Wetten zeigen Auswahl, Einsatz, Quote und mögliche Auszahlung
  direkt auf der 15K-Seite. `Gewonnen`, `Verloren` und `Storniert` werden dort
  gewählt und mit `Ergebnis verbuchen` abgeschlossen; der Umweg über einen
  versteckten Verlauf ist nicht mehr nötig.
- Eine bereits gespielte, zuvor nicht gespeicherte Wette kann mit Datum,
  Beschreibung, Einsatz, tatsächlicher Quote und Ergebnis nachgetragen werden.
  Sie aktualisiert dasselbe Transaktionsledger, bleibt aber sichtbar als
  `Nachgetragen` markiert und wird nicht als Modellnachweis ausgegeben.
- Das Schema migriert bestehende Ledger automatisch um `played_odds` und
  `entry_source`. Die tatsächliche Quote steuert die Auszahlung, während die
  ursprüngliche Referenzquote getrennt erhalten bleibt.
- Die Streamlit-1.59-Komponentenbrücke akzeptiert den aktuellen Rendervertrag,
  bei dem Parent-Nachrichten kein `isStreamlitMessage`-Flag mehr tragen. Das
  repariert neben der Konto-ID auch den vorhandenen N1-Import-Handshake.
- 690 Tests und 5 Subtests bestehen. Normales Microsoft Edge verifizierte
  25,00 Euro Einsatz bei Quote 2,40 als Guthabenpfad 100,00 → 135,00 Euro,
  denselben Stand nach vollständigem Browser-Neustart, die direkte Abrechnung
  einer offenen Wette sowie 390 × 844 ohne horizontalen Überlauf oder
  Konsolenfehler.

### Wiederanlauf- und Produktionskontrolle vom 9. August 2026

- Der vollständige PC-Absturz unterbrach weder einen offenen Codeumbau noch
  Commit, Push oder Deployment. Vor dieser reinen Dokumentaktualisierung
  zeigten lokales `HEAD`, `origin/main`, GitHub und der VPS identisch
  `7129e52`; darin ist der 15K-Funktionscommit `434ba86` enthalten.
- Die Produktions-App läuft unabhängig vom lokalen PC. Der Dienst war bei der
  Kontrolle `active`, HTTPS lieferte Status 200, es gab 0 fehlgeschlagene
  systemd-Units und alle sieben BetBoy-Timer hatten aktuelle beziehungsweise
  geplante Läufe.
- Im lokalen Arbeitsbaum existieren keine offenen Quellcodeänderungen. Nur die
  bekannten Laufdateien `logs/pipeline_2026-07-31.log` und
  `logs/pipeline_2026-08-02.log` bleiben absichtlich unversioniert.
- Ein lokaler Streamlit-Testserver ist nach einem PC-Neustart erwartungsgemäß
  beendet und für den VPS-Betrieb nicht erforderlich.
- Status der 15K-Reparatur: technisch repariert, getestet und produktiv aktiv.
  Eine vor der Reparatur nie gespeicherte Wette kann nicht rückwirkend erraten
  werden und muss einmal über `Vergangene Wette nachtragen` erfasst werden.

### Claude-Re-Audit und Randfall-Härtung vom 9. August 2026

- Der Mehrbuchmacher-Parser dedupliziert Anbieter jetzt bereits beim Aufbau
  mit normalisiertem, case-insensitivem Namen. Bei Feed-Dubletten wie `Bet365`
  und `bet365` zählt der Anbieter einmal; die niedrigere der doppelten Quoten
  bleibt als konservative Beobachtung erhalten. Build und Reload verwenden
  damit denselben Identitätsvertrag.
- Der maximale Einsatz wird zentral und wie im Ledger abgerundet. Dadurch kann
  das UI bei krummen Centguthaben nicht mehr einen Cent mehr anbieten, als die
  Buchung akzeptiert. Die tatsächliche Gesamtquote verwendet im UI dieselben
  `TARGET_ODDS_MIN/MAX`-Konstanten wie der Ledger.
- Eine freiwillige Eingabe unter 5 % kann die Gewinnpfad-Projektion nicht mehr
  mit `ValueError` abbrechen. Der 5-%-Mindestwert gilt für die gespeicherte
  Challenge-Policy, nicht für einen vorsichtiger eingegebenen realen Einsatz.
- Neue Konten starten bei 5 %. Bestehende Policy-v1-Konten werden genau einmal
  auf 5 % migriert; danach kann der Nutzer 10-25 % im Konto erneut bewusst
  wählen. Lesen und Geldpfad begrenzen auch manipulierte Legacy-Werte weiterhin
  hart auf 25 %.
- Eine nachgetragene Alt-Wette verwendet den tatsächlich damaligen Einsatz und
  wird deshalb nicht am heutigen Prozentregler gemessen. Sie darf das aktuell
  verfügbare Guthaben nicht überschreiten, bleibt als `MANUAL` markiert und
  zählt nie als Modell- oder Performanceevidenz. Eine lückenlose historische
  Zwischenbankroll kann ohne damalige Buchungen weiterhin nicht rekonstruiert
  werden.
- Die isotone Kalibrierung bleibt absichtlich regularisiert: 25
  Pseudo-Beobachtungen ziehen kleine Bins zur Modellidentität. Das ist keine
  Behauptung vollständiger Bias-Korrektur. Eine Änderung dieser Schrumpfung
  benötigt einen vorab festgelegten Out-of-sample-Vergleich von Brier,
  Log-Loss und Stabilität; ein einzelnes synthetisches Beispiel ist dafür kein
  belastbarer Tuningnachweis.
- 693 Tests und 5 Subtests bestehen. Regressionstests decken nun explizit
  1-%-Einsatz, Cent-Floor, 90-%-Legacywert, Policy-v2-Migration,
  Buchmacher-Casing und historische Einsätze oberhalb des heutigen
  Prozentstandards ab.
- Normales Microsoft Edge verifizierte 1440 × 1000 und 390 × 844 ohne
  horizontalen Überlauf: 5-%-Startwert, Warnung beim Wechsel auf 10 % und
  Nachtragsfeld mit 5-Euro-Vorbelegung bei 100 Euro zulässigem Ist-Guthaben.
  Der einzige blockierte Request war ein externes Material-Symbol von
  `fonts.gstatic.com` durch die lokale Netzwerksandbox; es gab keinen
  Seitenfehler und die relevanten Bedienelemente blieben sichtbar.

## 12. Offene Prioritäten

### P0 - extern und vor ernsthafter Echtgeldnutzung

1. Alle historisch exponierten Secrets rotieren.
2. Unabhängiges Offsite-/OVH-Backup aktivieren, den Preisledger-Kopf-Hash
   extern verankern und einen Wiederanlauf nach vollständigem VPS-Verlust
   testen.
3. Authentifizierung und eine geräteübergreifend stabile `user_id` für Konten
   und Ledger einführen. Die heutige Browser-ID löst Neustarts auf demselben
   Gerät, ersetzt aber kein Login.
4. Die Regeln des tatsächlich verwendeten Anbieters für Void, Verlängerung,
   Early Payout und Marktlinien schriftlich gegen die Settlement-
   Implementierung prüfen. Der Referenzfeed ersetzt diese Regelprüfung nicht.

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

Für einen Rechnerwechsel gilt zusätzlich das vollständige Runbook
`PC_WECHSEL_UEBERGABE.md`. Neue Entwickler und KI-Assistenten lesen zuerst
`PROJEKTBIBEL.md`, dann das PC-Runbook und erst danach die technischen Details
dieses Handbuchs.

Lokale App:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Produktion:

```text
URL: https://vps-a30a123f.vps.ovh.net/
App: /opt/betboy/app
Venv: /opt/betboy/venv
Backups: /var/backups/betboy
Verifizierter Funktionscommit: 6a59f3e
Repository-/VPS-HEAD vor Übergabedokumentation: 5fe7ef7
Letzte Livekontrolle: 10. August 2026
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

Die ungetrackten Dateien `AUDIT_BERICHT_2026-08-09.md`,
`logs/pipeline_2026-07-31.log` und `logs/pipeline_2026-08-02.log` bleiben
unangetastete lokale Historie. Die validierten Auditbefunde sind in diesem
Handbuch und der Projektbibel enthalten; die Logs sind Laufoutput. Sie werden
nicht versehentlich committed oder gelöscht.

Ohne Login ist das persönliche Konto an die Browser-ID
`betboy.account.v1` im `localStorage` gebunden. Ein neuer PC oder Browser zeigt
deshalb standardmäßig ein neues Konto. Die alte Serverdatenbank bleibt
vorhanden, ist ohne die bisherige Browser-ID aber nicht automatisch
zugeordnet. Das alte Browserprofil darf nicht gelöscht werden, wenn die
vollständige Historie noch übernommen werden soll.

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

## 14. Dokumenthierarchie für die Übergabe

| Reihenfolge | Dokument | Frage, die es beantwortet |
|---|---|---|
| 1 | `PROJEKTBIBEL.md` | Was ist BetBoy, welche Regeln gelten und wohin soll das Produkt? |
| 2 | `PC_WECHSEL_UEBERGABE.md` | Wie wird ein neuer PC sicher und vollständig arbeitsfähig? |
| 3 | `PROJECT_HANDBUCH.md` | Wie ist der aktuelle technische Stand entstanden und verifiziert? |
| 4 | aktueller Code und Tests | Was ist tatsächlich implementiert? |
| 5 | ältere Auditberichte | Warum wurde eine frühere Entscheidung getroffen oder verworfen? |

Bei Widersprüchen zählen Implementierung und reproduzierbare Tests mehr als
alte Chatbehauptungen. Der aktuelle `origin/main`-Stand muss vor jeder Arbeit
gegen den lokalen Checkout und vor jedem Deployment gegen den VPS geprüft
werden.
