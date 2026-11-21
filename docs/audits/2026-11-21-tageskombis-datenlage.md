# Tageskombis: Welche vorhandenen Daten tragen einen Chancenbalken?

**Stand: Samstag, 21.11.2026, 11:16 CET.** Die Prüfung liest archivierte Einzelangebote, keine Konten. Keine zusätzlichen API-Abfragen, Sicherungen, Scheinplatzierungen oder Produktionsänderungen.

## Bestand und Herkunft

Auf dem VPS vorhandene Entry-Angebote aus `forecast_quotes` über den Primärschlüssel an `forecast_rows` gebunden. Stabile Buchmacher-ID, Dezimalquote mindestens 1,20, Anbieteruhr, Abruf- und Archivzeit vor Anpfiff. Anbieterstand zur damaligen Archivierung höchstens 45 Minuten alt, Abruf höchstens 35 Minuten alt. Je Modellversion, Zürcher **Anstoßtag** und Buchmacher verschiedene Event-IDs gezählt. Die Zahlen poolen den ganzen Tag, verlangen also noch **keinen** gemeinsamen Entscheidungszeitpunkt; Auswahlqualität, vollständig abgerechnete Ergebnisse, Wettbewerb/Teilnehmer und Überlappungen sind hier ebenfalls nicht geprüft.

| Modellversion | Qualifizierende Preiszeilen | Anstoßtage mit solchen Zeilen | Tage mit ≥3 / ≥4 / ≥5 / ≥6 Spielen bei einem Buch am selben Tag |
|---|---:|---:|---:|
| Fußball `challenge-engine:legacy-form-strength-joint-calibration-v1` | 55 | 2 (08. und 19.11.) | 0 / 0 / 0 / 0 |
| Tennis `elo-serve-platt-v3` | 1.896 | 28 (01.10.–21.11.) | 13 / 11 / 6 / 5 |

Das sind günstige Obergrenzen **für diesen Archivpfad und jeweils diese Modellversion**, keine Ticketzahlen, keine Auswertung aller verfügbaren Angebote eines Buchmachers und kein Nachweis, dass es live an einem bestimmten Tag keine Kombi gäbe. Fußball und Tennis nicht anhand gleicher Anzeigenamen oder Ziffern sportübergreifend zusammenzählen. Spieltage im alten Fußballmodell sind kein unabhängiger Test der aktuellen Produktionsbasis.

## Technischer Befund

**Gegenprüfung Freitag, 20.11. (Zürcher Anstoßtag):** Die frühere Aussage „keine drei Spiele“ beschreibt nicht das Buchmacherangebot. Beim selben Archivschnitt (Entry, aktuelles Fußballmodell, Quote ≥1,20, Anbieterzeit ≤ Abrufzeit < Anstoß, **ohne** die 45/35-Minuten-Grenzen) sind diese Buchmachernamen direkt in den Preisbelegen gespeichert:

| Anbieter | Verschiedene Spiele |
|---|---:|
| Bet365 | 40 |
| 1xBet, Marathonbet, Betano, Pinnacle | je 38 |
| Betfair | 37 |
| BetVictor | 36 |
| SBO, William Hill, Dafabet | je 26 |

Ein Spiel zählt je Buch einmal, nicht einmal je Markt. Das ist keine Stichprobe geschlossener Scheine und kein Beleg für zeitgleich platzierbare Kombis. Der interne sportliche Vergleich bleibt unabhängig vom Alter eines Preisstands; der bepreiste Vergleich sucht separat nach gemeinsamen zeitgerechten Einzelangeboten.

- `market_consensus.MarketConsensus.points` und `quote_matches_candidate` erlauben eine exakte Bindung je Einzelangebot. Der angezeigte beste oder mittlere Preis einer Auswahl ersetzt keine gemeinsame Buchmacher-ID für alle Auswahlen. Nachträglich aktualisierte oder nur beobachtete Daten nicht auf den ursprünglichen Zeitpunkt zurückdatieren.
- Hockey-, Basketball- und E-Sport-Quoten dieses Pfads tragen Abrufbeobachtungen statt bestätigter Preisuhren. Solche Daten können den Vertrag für eine aktuelle Buchmacherquote nicht unverändert erfüllen.
- `challenge_engine.ticket_dependency_factor` und `ticket_stress_probability` betreffen die 15K-Challenge mit bis zu drei Spielen. Heuristischer Abschlag und mathematische Untergrenze sind keine auf vergleichbaren gesamten 3er-/4er-/5er-/6er-Scheinen nachgewiesene Gewinnwahrscheinlichkeit.
- Die vorhandenen Wettfinderveröffentlichungen belegen einzelne Tipps. Die ursprüngliche Zusammenstellung dieser neuen Kombis wurde nicht erfasst. Auch 12/14 getroffene Einzeltipps am Freitag ersetzen das nicht.

**Folge:** Noch keine historische Freigabe einer Scheingröße oder eines öffentlichen Wahrscheinlichkeitsbalkens. Exakte Ticketentscheidung vor Anpfiff bei regulären Läufen im bestehenden Datenfluss festhalten, zuerst intern auswerten, Modell und Referenz getrennt führen. Eine geschätzte unabhängige Produktzahl oder die 15K-Untergrenze nicht als geprüfte Kombichance veröffentlichen.

## Kontrollabfrage (gleicher Archivbestand)

Unabhängig nachgerechnet, ohne Anbieterzugriff. Die Zeilengrenze 88.719 fixiert den damaligen Anhangestand dieses vorhandenen Archivs; sie ist keine portable ID einer anderen Datenbank. Die folgende Prüfung gruppiert nur innerhalb derselben Sportart direkt nach der archivierten Buchmacher-ID. Sie validiert weder die Identität über mehrere Sportarten noch eine angenommene Buchmacherkombi. Als Ausgabe müssen beim unveränderten Bestand die zwei Tabellenzeilen oben entstehen.

```python
import sqlite3,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict,Counter
db=sqlite3.connect('file:/opt/betboy/app/runtime_state/forecast_evidence.db?mode=ro',uri=True,timeout=2)
db.execute('PRAGMA query_only=ON')
end=time.monotonic()+22  # Schutzschranke: kein langer Lesezugriff auf Produktion
db.set_progress_handler(lambda:int(time.monotonic()>end),20000)
events=defaultdict(set); offers=Counter()
for s,b,o,f,e,d,k,h,fx in db.execute("""select r.sport,q.bookmaker_id,q.observed_at,q.fetched_at,r.event_key,r.decision_at,r.starts_at,json_extract(r.payload_json,'$.recorded_at'),json_extract(r.payload_json,'$.quote_identity.fixture_id') from forecast_quotes q cross join forecast_rows r on q.forecast_id=r.forecast_id where q.rowid<=88719 and q.kind='entry' and q.odds>=1.20 and q.bookmaker_id<>'' and julianday(q.fetched_at)-julianday(q.observed_at)<0.031251 and ((r.sport='football' and r.model_version='challenge-engine:legacy-form-strength-joint-calibration-v1') or (r.sport='tennis' and r.model_version='elo-serve-platt-v3'))"""):
 if not all((o,f,d,k,h)):continue
 o,f,d,k,h=map(datetime.fromisoformat,(o,f,d,k,h))
 if not(o<=f<=d<=h<k and (h-o)<=timedelta(minutes=45) and (h-f)<=timedelta(minutes=35)):continue
 events[s,k.astimezone(ZoneInfo('Europe/Zurich')).date(),b].add(str(fx) if s=='football' and fx not in (None,'') else e);offers[s]+=1
for s in sorted(offers):
 days={}
 for (sp,day,b),ids in events.items():
  if sp==s:days[day]=max(days.get(day,0),len(ids))
 print(s,offers[s],len(days),[sum(v>=k for v in days.values()) for k in [3,4,5,6]],flush=True)
```
