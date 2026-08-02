# BetBoy - Vollaudit des KIMI-Verlaufs

## Auftrag

Geprüft wurden:

1. Was KIMI im vollständigen lokalen Chat behauptet und umgesetzt hat.
2. Ob die Shadow-Systeme technisch funktionieren und fachlich etwas beweisen.
3. Ob der gewählte Modell-, Daten-, Automations- und UX-Ansatz korrekt ist.
4. Welche Änderungen vor einer professionellen Wettfreigabe nötig sind.

Der ursprüngliche Audit hat keinen Produktionscode verändert. Der
anschließende Codex-Remediation-Lauf hat die unten dokumentierten Fehler
umgesetzt und mit einem vollständigen Test- und Browserlauf verifiziert.

## Quellen und Umfang

Der vollständige KIMI-Projektverlauf liegt lokal unter:

```text
C:\Users\miros\AppData\Roaming\kimi-desktop\daimon-share\daimon\agents\main\memory\transcripts\days\
```

Verifiziert wurden neun Tagesdateien vom 24. Juli bis 1. August 2026:

- 2.862 Ereignisse
- 84 Nutzerbeiträge
- 573 Assistentenbeiträge
- 2.205 Tool-Ereignisse

Der erste Projekt- und Gesprächszeitpunkt liegt nur ungefähr eine Minute
auseinander. Für dieses KIMI-Projekt gibt es daher keinen erkennbaren
fehlenden Gesprächsanfang. Zusätzlich existiert ein vollständiges
`wire.jsonl` mit 19.141 Zeilen.

Die Chat-Aussagen wurden nicht isoliert bewertet, sondern gegen folgende
Quellen geprüft:

- Git-Historie und Remote-Stand
- aktuellen Produktionscode
- vollständige Testsuite
- SQLite-Shadow-Datenbanken
- KIMI-Automationsdefinitionen und Run-Artefakte
- Windows-Aufgabenplanung
- API-Football-Status
- aktive und alte Streamlit-URLs
- Chrome-Screenshots bei Desktop- und Smartphone-Größe

## Umsetzungsnachtrag nach dem Audit

| Auditbefund | Status am Ende des Remediation-Laufs |
|---|---|
| Freemode hebelt Vetos aus | behoben; Default ist fail-closed |
| globale Scan-Jobs | sitzungsgebunden, mit Generation, Timeout und atomarem Write behoben |
| geteilter Challenge-Stand | pro Sitzung isoliert; echtes Konto-Login bleibt offen |
| Verlust wird auf 100 Euro zurückgesetzt | behoben; Verlust bleibt im Ledger |
| Challenge-Einsatz 2 Euro/All-in-Default | behoben; Standard 25 %, Bereich 5-100 %, Risikowarnung |
| Tennis-Mindestquote | behoben: `1 / (p - edge)` |
| Tennis-Update-Leakage | behoben; beide Pre-Match-Snapshots werden eingefroren |
| fehlende Watch-Märkte melden `ok` | behoben; Status `insufficient` |
| Shadow weicht von Produktionspolicy ab | für neue Zeilen behoben; gemeinsame Preis-/Value-Gates |
| Shadow ohne Modell-/Policy-Version | behoben |
| E-Sport-Auswahl und Settlement | gehärtet; Freigabe erst ab mindestens 100 Settlements |
| Rotkarten-Korrelation und AET | pro Fixture ein Snapshot; Regulation-Logik gehärtet |
| Wett-Check übernimmt offene Signale | behoben; nur freigegebene Signalpfade |
| Basketball/NHL wirken spielbar | fail-closed bis unabhängiger Evidenz |
| doppelte/alte KIMI-Jobs | bereinigt; Tennis-Duplikat, Backfill und Watcher deaktiviert |
| CLV-Bedingung nutzt alten Pfad | behoben; Bedingung und Runner nutzen kanonischen Code |
| mobile Überlagerung und versteckter aktiver Tab | behoben; responsive direkte Navigation |
| Multi-Sport zeigt falschen Filter/Inhalt | behoben; Sportart vor Liga, sportabhängige Beispiele |
| exponierte Secrets in Historie | **offen; Rotation durch Kontoinhaber erforderlich** |
| dauerhafte Cloud-Datenbank und Login | **offen; gültige DB und Auth erforderlich** |
| Profitabilitätsnachweis | **offen; junge Shadow-Stichprobe reicht nicht** |

Technischer Abschlussnachweis:

```text
487 Tests bestanden
5 Subtests bestanden
Edge-QA: 390 x 844 und 820 x 1180 ohne horizontalen Seitenüberlauf
```

Die Fußball-Shadow-Datenbank enthält 250 Fixtures und 230 Bewertungen, aber
weiterhin 0 Picks. Die revidierte produktionsgleiche Policy ist erst seit
diesem Remediation-Lauf aktiv und viele große Ligen beginnen erst. Deshalb
werden Gates **nicht** gelockert. Der richtige nächste Schritt ist
versionsgetrenntes Sammeln.

## Aktuelles Gesamturteil

Der technische Kern ist jetzt konsistent fail-closed. KIMIs richtige
Grundideen - Modell vor Preis, zeitliche Validierung und konservative
Wahrscheinlichkeit - bleiben erhalten. Die riskanten Abkürzungen bei
Freigaben, Challenge-Ledger, Shadow-Policy, Jobs und UX wurden korrigiert.

Weiterhin nicht bewiesen ist ein professioneller Wettvorteil. Die offenen
Hauptaufgaben sind Secret-Rotation, dauerhafte nutzergetrennte Cloud-Persistenz
und ausreichend unabhängige Out-of-sample-Evidenz. Das ist keine Einladung zu
mehr Tipps, sondern die notwendige Grenze zwischen guter Software und
belegbarer Wettqualität.

## Aktuelle direkte Antworten

1. **Shadow ist technisch verstanden und jetzt korrekt verdrahtet.** Die
   Stichprobe der revidierten Policy ist zu jung für ein Urteil.
2. **KIMIs Kernansatz war richtig, seine späteren Freigabe-Abkürzungen nicht.**
   Diese Abkürzungen sind im aktuellen Code entfernt oder fail-closed.
3. **Besser wird das System jetzt durch Beweis, nicht durch lockerere Gates:**
   Saisonstarts abwarten, Versionen einfrieren, mindestens 100 unabhängige
   Settlements sammeln und gegen No-Vig-Closing sowie Kalibrierung prüfen.

## Gesamturteil vor Umsetzung (historisch)

KIMI hat nicht nur erzählt: Sämtliche im Verlauf genannten Commit-Hashes
existieren und liegen in der Historie von `main`. Viele Verbesserungen sind
fachlich sinnvoll, insbesondere Modell-vor-Preis, chronologische Validierung,
konservative Wahrscheinlichkeitsabschläge, strikte Datenverträge und die
bewusste Ablehnung nicht bestätigter Tennis-Matchup-Hypothesen.

Der Ansatz wurde später jedoch inkonsistent. Aus einem zunächst fail-closed
arbeitenden Forschungs- und Wettfindersystem wurde durch Freemode,
unbewiesene „spielbar“-Freigaben, All-in-Challenge und mehrere getrennte
Shadow-/Scheduler-Systeme ein Produkt, das mehr Sicherheit ausstrahlt, als die
vorliegenden Daten erlauben.

**Urteil:** gutes Forschungs- und Produktpotenzial, aber noch kein
nachgewiesener professioneller Wettvorteil und aktuell keine belastbare
Echtgeldfreigabe.

## Direkte Antworten vor Umsetzung (historisch)

### 1. Sind die Shadow-Dinge verstanden und korrekt?

Technisch sind sie verstanden. Sie sind fünf getrennte Beweissysteme:

| Shadow | Zweck | Tatsächlicher Stand |
|---|---|---|
| Fußball CLV | Modellpick gegen Bet365-Einstieg und Closing | 0 Picks |
| Tennis | Vorhersage, Preis, Ergebnis und Kalibrierung | 64 offen, 0 settled |
| E-Sport | Prematch-ELO gegen Ergebnis | 5 saubere Settlements |
| Rotkarte | Nächstes Tor nach Signal | leere lokale DB |
| 15K | reale N1Bet-Tickets und Guthaben | 0 Tickets |

Sie beweisen aktuell nichts über Profitabilität. Hinzu kommt, dass lokale
KIMI-Datenbanken, Windows-Task, Cloud-SQLite und Streamlit-Threads nicht
dieselbe Laufzeit oder denselben Speicher teilen.

### 2. War KIMIs Ansatz korrekt?

**Teilweise ja.**

Korrekt:

- Modellwahrscheinlichkeit vor Buchmacherpreis
- Walk-forward statt zufälligem Split
- keine Zukunftsdaten desselben Spieltags
- Brier/ECE als Kalibrierungsmetriken
- konservative Haircuts
- echte Quote erst im Preisgate
- kein erzwungener täglicher Tipp
- Lefty-/Stil-Hypothesen nach negativem Test nicht eingebaut

Nicht korrekt oder nicht belegt:

- dieselben Daten für Hypothese, Faktorwahl und Erfolgsnachweis
- Marketingaussagen aus kleinen oder getunten Backtests
- Probability Edge und ROI teilweise gleichgesetzt
- Shadow-Auswahl weicht von Produktionsauswahl ab
- Freemode hebelt harte Modellgates aus
- 100-%-Roll-over als professioneller Einsatzstandard
- Rotkarten-Kontext auf demselben Datensatz entwickelt und „kalibriert“
- CLV-Unsicherheit ohne beobachtete Streuung pauschal angegeben
- Brier-Verhältnis als „Marktschärfe“ bezeichnet

### 3. Was ist besser zu machen?

Zuerst Integrität, dann Volumen:

1. Geheimnisse rotieren und Freemode abschalten.
2. Einen Scheduler, eine Datenbank und eine API-Budgetstelle schaffen.
3. Produktions- und Shadow-Policy identisch machen.
4. Guthaben, Einzahlung, Einsatz, Auszahlung und Reset sauber buchen.
5. Modelle vor einem unabhängigen Beweisfenster einfrieren.
6. Erst nach ausreichender Kalibrierung und positivem CLV Echtgeldstatus geben.
7. UX klar zwischen `Forschung`, `Preis prüfen` und `WETTEN` unterscheiden.

## Ausgangsbefunde vor Umsetzung (historisch)

### P0 - Sicherheitsvorfall

Der KIMI-Chat enthält echte Produktionszugänge im Klartext. Alte
`config.ini`-Blobs in der öffentlichen Git-Historie enthalten reale
API-Schlüssel. Im aktuellen Tree sind die Dateien entfernt und korrekt
ignoriert; die historischen Werte bleiben dennoch abrufbar.

Erforderlich:

1. Datenbankzugang rotieren.
2. Telegram-Token rotieren.
3. Alle API-Schlüssel rotieren.
4. alle Laufzeit-Secrets aktualisieren.
5. danach Git-Historie bereinigen.

### P0 - Freemode widerspricht dem Produktversprechen

`config_loader.py` setzt Freemode standardmäßig auf `True`. Auch ein
Konfigurationsfehler fällt in `app.py` auf `True` zurück.

Im Freemode werden unter anderem folgende Vetos zu Warnungen:

- BTTS unter 58 %
- Evidenz unter 70 %
- zu kleine Venue-/Form-Stichprobe
- zu großer ML-/Statistik-Abstand
- Live-Wahrscheinlichkeit unter 55 %
- unzureichende Live-Daten
- Rotkartenqualität unter `MEDIUM`

Das widerspricht der Vorgabe „nur wenn alle Kriterien treffen“. Ein pauschaler
Haircut ersetzt weder Daten noch Kalibrierung.

### P0 - Öffentliche Nutzer teilen Zustand

Hintergrundjobs verwenden globale Prozessschlüssel. Das Challenge-Ledger ist
ein global gecachtes lokales SQLite-Objekt. Es gibt weder Login noch `user_id`.
Auf einer öffentlichen App sind damit Job- und Bankroll-Zustände nicht sauber
pro Nutzer getrennt.

### P0 - Challenge verschleiert Kapitalnachschuss

Nach einem verlorenen Ticket setzt die Auto-Abrechnung Start- und Guthaben
wieder auf 100 Euro. Es entsteht keine Einzahlungsbuchung. Die Kurve kann
deshalb wie ein durchgehender Versuch aussehen, obwohl tatsächlich ein neuer
100-Euro-Versuch begonnen wurde.

Bei Quote 2,50 sind sechs Siege in Folge nötig:

```text
P(Erfolg) = p^6
```

Selbst bei einer sehr optimistischen wahren Ticketwahrscheinlichkeit von
45 % beträgt die Erfolgschance eines Versuchs nur ungefähr 0,83 %.

### P1 - Automationen sind Split-Brain

Aktiv oder vorhanden sind:

- KIMI Tennis täglich 07:17
- Windows Tennis täglich 07:17
- KIMI CLV alle zehn Minuten
- KIMI Statistik-Backfill
- KIMI Rotkarten-Harvest
- KIMI E-Sport zweimal täglich
- KIMI Wochenbericht
- KIMI Shadow-Wache
- einmalige Challenge-Auswertung

Verifizierte Fehler:

- CLV-Condition liest alte DB, Runner schreibt neue DB.
- Condition feuert deshalb nach 09:00 alle zehn Minuten.
- 19 CLV-Runs am 1. August.
- Backfill zeigt auf alten Ordner und schlägt beim Import fehl.
- Wochenbericht und Wache enthalten alte Pfade.
- Tennis läuft doppelt über KIMI und Windows.
- kein gemeinsames Tagesbudget.

### P1 - Cloud-Persistenz fehlt

Die aktive App zeigt `Datenbank: lokaler Ersatz`. Challenge, Tennis, E-Sport,
CLV und Rotkarten verwenden jeweils lokale SQLite-Dateien. Streamlit Cloud
kann diese bei Neustart verlieren und sieht lokale KIMI-Daten nicht.

### P1 - Shadow validiert nicht dieselbe Policy

Der Fußball-Shadow:

- wählt primär höchste konservative Wahrscheinlichkeit,
- verlangt nicht dieselbe preisadjustierte Produktionsauswahl,
- loggt eine vorhandene Referenzquote ohne identisches Edge-/EV-Gate,
- markiert einen Kandidaten terminal, auch wenn Quote oder Logging fehlen.

Damit beantwortet ein späterer CLV-Wert nicht exakt die Frage, ob die
Produktionsentscheidung profitabel gewesen wäre.

## Mathematische Detailbefunde vor Umsetzung (historisch)

### Tennis-Mindestquote

Produktionslogik:

```text
edge = p - 1 / quote
edge >= 0,15
```

Daraus folgt:

```text
Mindestquote = 1 / (p - 0,15)
```

Der Wochenreport verwendet dagegen:

```text
(1 + 0,15) / p
```

Das ist ein 15-%-ROI-Gate und nicht dasselbe. Bei `p=0,65` ergeben sich
1,77 gegenüber korrekt 2,00.

### Tennis-Update-Leakage

Im Serve/Return-Modell wird zuerst der Sieger und danach der Verlierer
aktualisiert. Die Gegneradjustierung liest den aktuellen Gegnerzustand.
Dadurch nutzt der Verlierer bereits die Siegerdaten desselben Matches.
Beide Gegnerzustände müssen vor beiden Updates gesnapshottet werden.

### Kalibrierungswächter

Fehlen alle beobachteten angebotenen Märkte, ergibt `offered_drift=False` und
damit `status=ok`. „Nicht messbar“ wird fälschlich zu „kein Drift“.

### E-Sport

Die Serienrekursion ist mathematisch korrekt unter einer i.i.d.-Map-Annahme.
Die 150-ELO- und 5-Prozentpunkte-Abschläge sind jedoch Handregeln. Map-Veto,
Rosterwechsel, Formatunterschiede und zeitliche Stärkeänderung sind nicht
empirisch kalibriert.

Die saubere Live-Stichprobe umfasst nur fünf abgerechnete Matches. Vier
Treffer sind kein Beweis. Ein 95-%-Intervall ist bei n=5 extrem breit.

### Rotkarten

Die Poisson- und konkurrierende-Prozess-Mathematik ist grundsätzlich
nachvollziehbar. Das Evidenzdesign ist das Problem:

- 1.132 Fälle dienten zum Erkennen und Einstellen der Faktoren.
- ein unberührter zeitlicher Holdout fehlt.
- mehrere Minuten-Snapshots desselben Spiels sind korreliert.
- die Statistik zählt sie dennoch einzeln.
- `actionable=True` kann bei `calibrated=False` entstehen.
- lokale Shadow-Belege fehlen.

### Basketball und NHL

Das Gamma-Poisson-Update selbst ist korrekt. Der aktive Informationssatz ist
zu dünn:

- Basketball: fixer NBA-/EuroLeague-Gesamtprior plus Live-Pace.
- NHL: fixer 6,2-Tore-Prior plus Live-Stand.
- keine aktive Teamstärke.
- keine Lineups beziehungsweise Possessions.
- keine Goalies oder Special-Team-Stärke im NHL-Modell.

Ein 8- bis 13-Prozentpunkte-Haircut macht daraus keinen validierten
Wettvorteil.

### Wett-Check

EV, Break-even und erwarteter Gewinn sind algebraisch korrekt, sofern `p`
korrekt ist. Der Wett-Check übernimmt aber:

- beide Seiten offener Tennis-Predictions unabhängig von deren Gates,
- E-Sport-Rohwahrscheinlichkeit statt konservativer Wahrscheinlichkeit,
- gespeicherte Fußballsignale aus globalen Scan-JSONs.

Der Text „Preis ist falsch zu deinen Gunsten“ ist ohne validiertes `p` zu
absolut. Korrekt wäre „unter deiner Modellannahme rechnerisch positiv“.

## UX-Befunde vor Umsetzung (historisch)

Positiv:

- klare Hauptbereiche
- verständliche Modell-vor-Preis-Reihenfolge
- gute Desktop-Lesbarkeit
- große mobile Bedienflächen
- Scanner können beim Seitenwechsel weiterlaufen

Negativ:

- acht feste Bottom-Navigationselemente sind auf 390 Pixel zu eng
- CSS überschreibt das notwendige Bottom-Padding
- Floating-Widgets verdecken weitere Navigation
- große Anleitungskarten verbrauchen den ersten mobilen Viewport
- `Freemode` wird nicht als grundsätzlich anderer Risikomodus erklärt
- „WETTEN“ und „JA“ erscheinen auch bei nicht bewiesenen Modellen zu endgültig
- lokale und Cloud-Shadow-Stände wirken wie ein System, sind aber getrennt

Zielbild:

- vier Primärziele: `Spiele`, `Live`, `15K`, `Mehr`
- `Mehr` öffnet Märkte, Wett-Check, Tennis, Multi-Sport und System
- kompakter Ergebnis-first-Screen
- einheitliche Statusstufen:
  `KEINE DATEN`, `FORSCHUNG`, `PREIS PRÜFEN`, `NICHT WETTEN`, `WETTEN`
- `WETTEN` nur für validierte Modelle

## KIMI-Aussagen, die korrigiert werden müssen

1. Der Katalog hat aktuell 51, nicht 44 oder 48 Ligen.
2. Die alte lange Streamlit-URL ist nicht die aktive App.
3. Ein Windows-Tennis-Task existiert tatsächlich; zusätzlich läuft KIMI.
4. API-Football Pro endet am 19. Oktober 2026, nicht nach einem Jahr.
5. „5 % Edge = 5 % ROI“ ist falsch.
6. Eine pauschale CLV-Standardabweichung ohne Daten ist unbelegt.
7. Ein Brier-Verhältnis ist keine „95-%-Marktschärfe“.
8. Ein auf denselben Daten getunter Backtest ist kein Profitabilitätsbeweis.
9. Fünf E-Sport-Settlements erlauben keine Wettfreigabe.
10. Ein Haircut kompensiert Modellrisiko nur numerisch, nicht empirisch.

## Umsetzungsplan und Status

Die meisten Codepunkte aus Phase 1 bis 3 sind umgesetzt. Offen bleiben
Secret-Rotation, dauerhafte Datenbank/Auth, ein zentraler API-Budgetmanager
und vor allem Phase 4: der unabhängige empirische Beweis.

### Phase 1 - Stabilisieren

- Secrets rotieren.
- Freemode default-off und fail-closed.
- alte und doppelte Automationen pausieren.
- einen zentralen API-Budgetzähler einführen.
- Challenge-Reset als Einzahlung buchen oder entfernen.
- aktive URL in App und Dokumentation vereinheitlichen.

### Phase 2 - Produktionskern

- gültiges PostgreSQL aufsetzen.
- Benutzeridentität einführen.
- Queue mit Job-ID, Owner-ID, Generation und Timeout.
- atomare Ergebniswrites.
- ein Scheduler für alle periodischen Läufe.
- Modell- und Policy-Version in jedem Snapshot.

### Phase 3 - Mathe und Settlement

- Tennis-Formel und Gegnerupdate korrigieren.
- Shadow exakt auf Produktionspolicy umstellen.
- Abrechnung nur reguläre Spielzeit, inklusive `elapsed + extra`.
- pro Fixture nur eine vorab definierte Rotkarten-Entscheidung werten.
- E-Sport mit Zeitgewicht, Roster-/Formatkontrolle und konservativem `p`.
- Basketball/NHL bis zu Team-/Lineup-/Goalie-Modellen als Forschung markieren.

### Phase 4 - Beweis

- Modell und Schwellen einfrieren.
- mindestens 100 unabhängige Picks pro Produkt sammeln.
- Brier und Log Loss gegen No-Vig-Closing-Benchmark.
- Kalibrierung mit Unsicherheitsintervallen.
- CLV mit Bootstrap- oder robustem Konfidenzintervall.
- ROI erst danach und nur sekundär.

## Abschluss nach Umsetzung

BetBoy ist jetzt ein wesentlich konsistenterer Wettfinder: fachliche Blocker
bleiben Blocker, Preis und Modell sind getrennt, Jobs und Ledger vermischen
keine öffentlichen Sitzungen mehr, und die UI erzeugt keine Empfehlung aus
reinem Monitoring. Die App hat reales Potenzial als disziplinierte
Entscheidungs- und Forschungsplattform.

Der professionelle nächste Schritt ist dennoch nicht, täglich drei Tipps zu
erzwingen. Die revidierte Shadow-Policy muss durch die beginnenden Ligen
laufen. Erst belastbare Kalibrierung, Closing-Line-Leistung und korrekt
abgerechnete unabhängige Picks können eine Echtgeldfreigabe begründen.

## Abschluss vor Umsetzung (historisch)

Das Tool hat Potenzial als disziplinierter Wettfinder und Forschungsplattform.
Seine stärkste Idee ist die Trennung von Wahrscheinlichkeit und Preis. Seine
größte aktuelle Schwäche ist nicht eine einzelne Formel, sondern fehlende
Einheitlichkeit: verschiedene Scheduler, lokale Datenbanken, abweichende
Shadow-Policies und Freigaben ohne unabhängigen Beweis.

Der professionelle nächste Schritt ist deshalb nicht „mehr Tipps“, sondern ein
kleinerer, einheitlicher und beweisbarer Kern. Erst wenn dieser Kern Closing
Lines und Kalibrierungsbenchmarks belastbar schlägt, sollte die App aus
`FORSCHUNG` ein echtes `WETTEN` machen.
