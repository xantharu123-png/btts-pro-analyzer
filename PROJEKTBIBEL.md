# BetBoy - Projektbibel

## Status und Zweck

Stand: 24. August 2026

Kanonisches Repository: `xantharu123-png/btts-pro-analyzer`

Produktionsadresse: `https://vps-a30a123f.vps.ovh.net/`

Aktuell verifizierte funktionale Basis:
`08778fdc29a7275c21fc23671d4763290273c435`

Aktuell verifizierter GitHub- und VPS-Funktionsstand:
`08778fdc29a7275c21fc23671d4763290273c435`

Diese Projektbibel erklärt, **warum BetBoy existiert, was das Produkt leisten
darf, wie eine Empfehlung entsteht und welche fachlichen Grenzen niemals
aufgeweicht werden dürfen**. Sie ist die erste Lektüre für neue Entwickler,
Designer, Produktverantwortliche und KI-Assistenten.

Die Dokumente haben unterschiedliche Aufgaben:

| Dokument | Verbindlicher Zweck |
|---|---|
| `PROJEKTBIBEL.md` | Produktidee, Mathematik, UX, Sprache, Entscheidungsregeln und Zielbild |
| `PROJECT_HANDBUCH.md` | Technische Architektur, behobene Fehler, Evidenzstand, Tests und Betrieb |
| `PC_WECHSEL_UEBERGABE.md` | Ausführbare Übernahme auf einen neuen Windows-PC |
| `deploy/README.md` | Kurzanleitung für Installation und Updates des VPS |

Ältere Auditberichte sind historische Momentaufnahmen. Bei Widersprüchen gilt
zuerst der aktuelle Code, dann das Projekthandbuch und danach diese Bibel.

## 1. Das Produkt in einer Seite

BetBoy ist ein **Wettfinder mit nachvollziehbarer Wahrscheinlichkeitsanalyse**.
Der Nutzer soll wenige konkrete, verständliche Auswahlen erhalten, nicht ein
Monitoring-Dashboard und nicht hunderte Rohsignale.

Der Kernvertrag lautet:

1. Sportdaten erzeugen eine quotenfreie Modellwahrscheinlichkeit.
2. Datenqualität, Zeitbezug, Stichprobe, Kalibrierung und Kontext werden
   geprüft.
3. Eine konservativ bestandene Prognose darf zur transparenten Preisprüfung
   gelangen; Preisprüfung ist noch keine Tippfreigabe.
4. Die Buchmacherquote verändert die Modellwahrscheinlichkeit nicht.
5. Ein Preis entscheidet nur, ob die Auswahl zu diesem Preis mathematisch
   vertretbar ist.
6. Fehlende oder zu niedrige Quote löscht die Modellprognose nicht.
7. Ohne belastbare Modell-, Release-Kontext- und Preisfreigabe gibt es keinen
   Tipp und keinen Einsatzvorschlag.
8. Pro Suchlauf stehen zuerst höchstens drei klare Top-Auswahlen. Bis zu zwölf
   weitere berechnete Modellprognosen bleiben eingeklappt erreichbar, statt
   nach Platz drei verworfen zu werden.
9. Extreme Kurzquoten-Basislinien dürfen als nachvollziehbare Modellrechnung
   sichtbar bleiben, werden aber nie als Top-Auswahl, strikter Tipp oder
   Einsatzvorschlag beworben.
10. Je Spiel und Marktfamilie wird höchstens eine Auswahl hervorgehoben; der
    Katalog soll echte Entscheidungsalternativen statt Varianten desselben
    trivialen Ereignisses zeigen.
11. Ein gespeicherter künftiger Kandidat wird automatisch neu bepreist.
    Preisalter und Kontextalter werden getrennt behandelt; veralteter Kontext
    kann keine strikte Freigabe erzeugen.
12. Keine Wettart wird allein wegen ihres Namens gesperrt. Team-Unter-1,5 ist
    ein normaler, vollständig tippsfähiger Markt. Modell, Kontext und die
    konkrete Quote entscheiden. Nur eine bestätigte Extrem-Kurzquote darf die
    Darstellung zurückstufen; die Prognose bleibt sichtbar.

Das Produkt darf sagen:

- welche Auswahl das Modell für am wahrscheinlichsten hält;
- wie hoch Modell-p und konservatives p sind;
- welche Daten und Gegenprüfungen verwendet wurden;
- ab welcher Quote der risikoadjustierte Erwartungswert genügt;
- ob ein verfügbarer Referenzpreis diese Schwelle erfüllt;
- warum ein Kandidat nicht freigegeben wurde.

Das Produkt darf niemals behaupten:

- eine Wette sei sicher oder garantiert;
- eine niedrige Quote sei automatisch verlässlich;
- grüne Softwaretests bewiesen einen Wettvorteil;
- ein kurzer positiver ROI beweise langfristige Profitabilität;
- Shadow-, Research- oder Backtest-Ergebnisse seien Echtgeldbeweise;
- BetBoy könne Buchmacher dauerhaft oder risikolos schlagen.

## 2. Produktpositionierung

### Für den Nutzer

BetBoy verdichtet komplexe Daten in wenige Entscheidungen:

- **Wettfinder:** eigene Suche über Sport, Zeitraum, Wettart und Wettbewerb;
- **Live:** experimentelle, klar gekennzeichnete Live-Analysen;
- **15K:** getrennte Challenge-Simulation mit eigenem Konto und Ledger;
- **Meine Tipps:** aktive Tipps und Verlauf;
- **Einstellungen:** Konto, Datenqualität, Modell- und Systemstatus.

Die erste sichtbare Ebene zeigt den Tipp. Technische Diagnostik gehört in
Details oder Einstellungen. Interne Shadow-Automation sammelt Evidenz, ist
aber nicht das Produktversprechen und darf die Nutzeroberfläche nicht
dominieren.

### Für Marketing und Vertrieb

Die glaubwürdige Positionierung ist nicht „Wettkönig“ oder „sichere Tipps“.
Sie lautet:

> Wenige, datenbasierte Sportwetten-Analysen mit klarer Mindestquote,
> konservativer Risikorechnung und transparenten Ablehnungsgründen.

Verkaufbare Differenzierung:

- Modell und Buchmacherpreis bleiben technisch getrennt.
- Bestpreise werden nicht zur Schönrechnung verwendet.
- Unsichere Daten führen zu `NO BET`, nicht zu erfundenen Lückenfüllern.
- Die App erklärt Auswahl, Datenstand, Risiko und Preisstatus.
- Mehrere Sportarten teilen dieselbe UX, aber nicht fälschlich dasselbe Modell.
- Historische Evidenz wird versionsweise und vorab protokolliert.

Vor einer App-Store- oder Google-Play-Vermarktung braucht das Produkt unter
anderem Login, geräteübergreifende Konten, belastbare Datenlizenzen,
Datenschutztexte, Alters- und Länderregeln sowie eine rechtliche Prüfung der
Darstellung von Wettanalysen. Eine Streamlit-Webseite ist noch kein fertiges
Consumer-Mobilprodukt.

## 3. Nicht verhandelbare Produktgesetze

### 3.1 Modell vor Preis

Die Quote darf nie als versteckter Modellinput verwendet werden. Die
Reihenfolge ist verbindlich:

```text
Sportdaten -> Modell-p -> Kalibrierung -> konservatives p
-> Kontextgates -> konkrete Auswahl -> Preisprüfung -> Tippstatus
```

Marktquoten dürfen später als Benchmark, zur Entfernung der Marge, für
Erwartungswert, Mindestquote und Einsatzreferenz verwendet werden.

### 3.2 Fail-closed

Fehlt eine Pflichtinformation, wird der betroffene Kandidat gesperrt. Es wird
nicht geschätzt, still ersetzt oder durch eine andere Sportart kaschiert.

Neutrale Daten dürfen nicht als Veto missbraucht werden. Beispiel: Ein kleiner
oder fehlender H2H-Datensatz kann weder freigeben noch blockieren. Erst eine
ausreichende und zeitlich passende Stichprobe darf als konservativer
Gegencheck wirken.

### 3.3 Keine Quote ist „sicher“

Eine Quote von 1,05 kann wirtschaftlich unattraktiv sein und bei kleiner
Modellüberschätzung negativen Erwartungswert besitzen. Eine hohe Quote ist
ebenfalls kein Value-Beweis. Entscheidend sind konservatives p, Preis und
Unsicherheit gemeinsam.

Breite Basisprognosen wie „Topteam erzielt mindestens ein Tor“ oder sehr
großzügige Unter-Linien werden weiter berechnet, aber nicht als Top-Auswahl
beworben. Die Einstufung erfolgt quotenfrei anhand des Markttyps und des
nachgewiesenen Modellnutzens. Eine niedrige oder fehlende Quote darf eine
inhaltlich aussagekräftige Modellprognose weder löschen noch herabstufen.

### 3.4 Evidenzstufen bleiben getrennt

| Stufe | Bedeutung | Darf als Echtgeldtipp erscheinen? |
|---|---|---|
| `RESEARCH` | Modell- oder Produktforschung | Nein |
| `SHADOW` | Vorab protokollierte, produktionsgleiche Beobachtung ohne Echtgeldfreigabe | Nein |
| `RELEASED` | Modell und Policy besitzen ausreichende unabhängige Evidenz | Nur mit bestandenem Preisgate |

`PLAYABLE` ist ein Preisstatus, keine Evidenzstufe. Ein spielbarer Preis kann
ein unbewiesenes Modell nicht freigeben.

### 3.5 Kein Schwellen-Tuning auf das gewünschte Ergebnis

Wenn zu wenige Tipps erscheinen, werden nicht einfach Gates gelockert.
Zuerst wird der Dropout-Funnel analysiert: Discovery, Statistik, Modell,
Kalibrierung, Kontext, Marktzuordnung, Preis und Settlement. Änderungen
benötigen eine vorab definierte Hypothese und zeitlich getrennte Prüfung.

## 4. Aktueller Nutzerfluss

### Wettfinder

Der Nutzer wählt:

- Sport oder `Alle`;
- Zeitraum `Heute`, `3 Tage`, `7 Tage` oder `14 Tage`;
- für Fußball eine konkrete Wettart oder `Beste Märkte`;
- alle Ligen, Favoriten oder eine Auswahl.

Die Suche kann Termine aller sechs Sportarten finden. Das bedeutet nicht, dass
alle sechs Sportarten bereits Tipps freigeben dürfen. Jede Sportart benötigt
ihren eigenen Modell-, Kalibrierungs-, Preis- und Settlementvertrag.

### Automatische Tagesauswahl

Der VPS führt für Fußball einmal pro Zieldatum eine Discovery über alle 51
konfigurierten Ligen aus. Spätere halbstündliche Läufe prüfen nur gespeicherte
Kandidaten kurz vor dem Anpfiff. Dadurch werden nicht alle 51 Ligen bei jedem
Aufwachpunkt erneut belastet.

Die App zeigt dezent:

- Zeitpunkt des letzten Vollscans;
- geprüfte Ligen;
- gefundene und modellierte Spiele;
- Zahl bestandener Fußball-Auswahlen;
- höchstens drei noch nicht gestartete Top-Auswahlen;
- bis zu zwölf weitere berechnete Modellprognosen in einem kompakten
  Zusatzbereich.

### 15K Challenge

Die Challenge ist ein separater Workflow mit eigenem Kontobuch:

- Zielguthaben 15.000 Euro;
- Ziel-Gesamtquote 2,00 bis 3,00;
- maximal drei Legs;
- maximal ein offenes Ticket;
- Standard-Einsatzanteil 5 Prozent;
- 10 bis 25 Prozent nur als bewusst aggressiver Simulationsmodus;
- kein Martingale und keine automatische Verdopplung nach Verlusten;
- Gewinn, Verlust und Void werden persistent verbucht;
- historische Wetten können gekennzeichnet nachgetragen werden.

Die 15K-Auswahl ist derzeit fachlich auf Fußball beschränkt. Ein Sportfilter
darf keine versteckten Ersatz-Tipps aus anderen Sportarten erzeugen.

## 5. Sport- und Marktstatus

| Sport/Bereich | Daten-/Modellstand | Produktstatus |
|---|---|---|
| Fußball Prematch | 51 Wettbewerbe, Modellmärkte, Walk-forward-Gates, Kontext und API-Football-Preisvergleich | Voll implementierter Kern; weiterhin kein empirisch bewiesener Langfristvorteil |
| Fußball Live | BTTS, Resttor und Teamtor vorhanden | `RESEARCH`, bis unabhängige Live-Kalibrierung genügt |
| Rotkarte Live | Signal- und Settlement-Infrastruktur vorhanden | `RESEARCH`, keine unabhängige Shadow-Stichprobe |
| Tennis | ATP/WTA Elo, Belag, Serve-Daten, Walk-forward-Kalibrierung und Shadow | Analysefähig; ohne belastbaren automatischen Mehrbuchmacherpreis kein veröffentlichter Tipp |
| E-Sport | PandaScore-Spielpläne, Elo/Shadow und Settlement | Shadow-Aufbau; Preis- und Kalibrierungsevidenz unzureichend |
| Basketball | NBA-/EuroLeague-Termine vorhanden | Kein leak-frei validiertes Prematch-Modell, daher fail-closed |
| Eishockey | NHL-Termine vorhanden | Goalie-/Lineup- und Prematch-Modell fehlen, daher fail-closed |
| Cricket | Scannerpfad vorhanden | Datenabo und validierter Modellkern fehlen, daher fail-closed |

Fußballmärkte im aktuellen Modell- und Mappingumfang:

- Endergebnis und Doppelte Chance;
- BTTS;
- Gesamt- und Teamtore;
- ausgewählte Torbereiche und kombinierte Tormärkte;
- Gesamt- und Teamecken;
- Gesamt- und Teamkarten.

Nur exakt beim Provider vorhandene Linien dürfen automatisch bepreist werden.
Team-Torbereiche, gemischte Oder-Märkte oder kombinierte Resultat/Tor-Auswahlen
werden nicht aus mehreren Einzelquoten synthetisiert.

## 6. Preisweg und Buchmacher-Unabhängigkeit

N1Bet bietet im Projekt keinen offiziellen direkten API-Pfad. Der aktive
Produktweg benötigt keine Browsererweiterung und kein geöffnetes
Buchmacherfenster.

Für exakt abbildbare Fußballmärkte verwendet BetBoy den API-Football-
Mehrbuchmacherfeed als konservativen Marktvergleich:

- mindestens drei verschiedene, case-insensitiv deduplizierte Anbieter;
- unteres Quartil als Rechenpreis;
- Minimum, Median und Bestpreis nur zur Transparenz;
- Abruf höchstens 90 Minuten alt;
- Providerbeobachtung höchstens 24 Stunden alt;
- exakte Markt-, Team- und Linienzuordnung;
- kein synthetischer oder geschätzter Buchmacherpreis.

Das untere Quartil reduziert den Einfluss einzelner Ausreißer. Es garantiert
nicht, dass N1Bet exakt denselben Preis anbietet. Der tatsächlich spielbare
Preis bleibt für eine reale Entscheidung maßgeblich.

Die Browsererweiterung unter `browser_extension/n1bet_importer` ist nur noch
Rollback-Historie. Sie gehört nicht zum aktiven Nutzerfluss und wird nicht für
App-Store-Nutzer vorausgesetzt.

## 7. Mathematischer Kern

Verbindliche Formeln:

```text
Break-even-p = 1 / Quote
ROI = p * Quote - 1
Probability Edge = p - 1 / Quote
Full Kelly = ((Quote - 1) * p - (1 - p)) / (Quote - 1)
Mindestquote bei 3 % Ziel-ROI = 1,03 / konservatives p
Kombi-p = Produkt der konservativen Leg-p * Modellrisiko-Faktor
Fréchet-Untergrenze = max(0, Summe der Leg-p - (Legzahl - 1))
Log-Wachstum = p*ln(1+f*(Quote-1)) + (1-p)*ln(1-f)
```

Wichtige Implementierungspolicies:

- Modell-p wird vor jeder Preisprüfung berechnet.
- Konservatives p enthält explizite Haircuts für Unsicherheit.
- Die allgemeine Kelly-Ausgabe verwendet Viertel-Kelly mit 2-%-Cap.
- Die 15K-Risikoreferenz wird zusätzlich auf höchstens 5 Prozent begrenzt.
- Der risikoadjustierte Ziel-ROI beträgt mindestens 3 Prozent.
- Mindestens drei Kalibrierungsbins und ausreichende Bin-Größen sind nötig.
- Kalibrierung und Validierung müssen zeitlich kausal sein.
- Der Kombi-Abschlag `0,97` je weiterem Leg und `0,985` je Paar derselben Liga
  ist eine konservative Policy, kein bewiesenes Korrelationsmodell.

### Ehrliche 15K-Rechnung

Bei 100 Euro, 5 Prozent Einsatz und Quote 2,50 wächst das Guthaben nach einem
Gewinn um Faktor 1,075. Ohne einen einzigen Verlust wären 70 Gewinne bis
15.000 Euro nötig.

Bei 25 Prozent Einsatz wäre der Faktor 1,375 und der reine Siegpfad benötigte
16 Gewinne. Bei einer wahren Ticketwahrscheinlichkeit von 42 Prozent liegt die
Chance auf 16 Siege in Folge nur bei ungefähr 0,0001 Prozent. Der 25-%-Modus
ist deshalb eine Hochrisikosimulation und keine professionelle
Einsatzempfehlung.

## 8. Datenquellen

| Quelle | Zweck | Bemerkung |
|---|---|---|
| API-Football Pro | Fußball-Fixtures, Resultate, Live, Statistiken, Kontext und Referenzquoten | Zentrale aktive Quelle; Tagesbudget wird prozessübergreifend verwaltet |
| football-data.co.uk | historische Fußball-CSV | Historische Modellbasis, nicht aktuelle Quote |
| OpenWeather | Wetterkontext | Nur Kontext, kein eigenständiger Tippgeber |
| PandaScore | E-Sport-Fixtures und begrenzte Teamdaten | Normaler Statistikfeed enthält keine belastbaren Wettpreise |
| ESPN | NBA-Spielpläne | Terminabdeckung, kein freigegebenes Prematch-Modell |
| EuroLeague API | EuroLeague-Spielpläne | Terminabdeckung |
| NHL Schedule API | NHL-Spielpläne | Terminabdeckung |
| RapidAPI/CricketData | Cricket | Auf Produktion derzeit nicht vollständig konfiguriert |
| SQLite auf VPS | kanonische Runtime-Ledger und Shadow-Daten | Single-Server-Wahrheit |

football-data.org ist im aktuellen Produktionspfad nicht erforderlich. Der
alte Supabase-Pooler ist nicht mehr kanonisch und darf nicht als notwendige
Produktionsabhängigkeit dargestellt werden.

## 9. Architektur und Betrieb

### Laufzeitarchitektur

```text
Browser
  -> HTTPS / Caddy
  -> Streamlit app.py auf 127.0.0.1:8501
  -> Modell-, Preis- und Ledger-Module
  -> persistente SQLite-Dateien unter /opt/betboy/app

systemd timer
  -> Wettfinder
  -> Fußball Shadow/CLV
  -> Tennis
  -> E-Sport
  -> Rotkarten-Settlement
  -> Rotkarten-Historie
  -> tägliches SQLite-Backup
```

Produktionsorte:

| Element | Ort |
|---|---|
| App | `/opt/betboy/app` |
| Python-Venv | `/opt/betboy/venv` |
| System-Environment | `/etc/betboy/betboy.env` |
| Lokale Runtime-Konfiguration | `/opt/betboy/app/config.ini` |
| Backups | `/var/backups/betboy` |
| Öffentliche URL | `https://vps-a30a123f.vps.ovh.net/` |

Der VPS ist die einzige kanonische schreibende Instanz. Lokale Windows- oder
KIMI-Automationen dürfen nicht parallel aktiviert werden.

### Wichtigste Module

| Modul | Rolle |
|---|---|
| `app.py` | Streamlit-Einstieg, Navigation und UI-Orchestrierung |
| `betting_math.py` | gemeinsame Wettmathematik |
| `market_consensus.py` | exakte Fußball-Preiszuordnung und Konsens |
| `challenge_engine.py` | 15K-Modell, Gates und Ticketkonstruktion |
| `challenge_store.py` | transaktionales Challenge-Ledger |
| `wettfinder_automation.py` | tägliche Discovery, quotenfreier Nutzwert-Katalog und separates Preisgate |
| `shadow_clv_automation.py` | Fußball-Shadow, Closing und Settlement |
| `tennis/*` | Tennis-Daten, Elo, Serve, Kalibrierung und Shadow |
| `multi_sport_recommendations.py` | gemeinsame fail-closed Multisport-Policy |
| `api_budget.py` | atomarer API-Football-Budget-Governor |
| `scripts/backup_runtime_databases.py` | Backup und Wiederherstellungsprüfung |

## 10. Persistenz und Identität

Die Runtime-Datenbanken und Scan-Artefakte sind absichtlich nicht in Git.
Sie liegen auf dem VPS und werden dort gesichert.

Ohne Login verwendet BetBoy eine zufällige 128-Bit-ID im Browser-
`localStorage`. Dadurch bleiben Konto und Tipps im selben Browser nach einem
Neustart erhalten. Ein anderer Browser, ein neuer PC oder gelöschte
Websitedaten erzeugen eine neue ID und damit ein neues sichtbares Konto.

Das ist beim PC-Wechsel besonders wichtig:

- Git und VPS-Daten gehen nicht verloren.
- Das alte 15K-Konto ist weiterhin als Datenbank auf dem VPS vorhanden.
- Der neue Browser kann es ohne die alte Browser-ID aber nicht automatisch
  zuordnen.
- Vor Abschalten des alten Browserprofils muss entschieden werden, ob die
  15K-Historie übernommen oder ein neues Konto begonnen wird.

Ein produktreifer Mehrgerätebetrieb benötigt Authentifizierung und eine
serverseitige stabile Benutzer-ID. Das ist eine offene P0-Aufgabe.

## 11. Was bereits gelöst wurde

Die wichtigsten Umbauten des Projekts:

- Navigation von vielen Spezialscannern auf fünf verständliche Bereiche
  reduziert.
- Wettfinder auf alle sechs Sportarten und bis zu 14 Tage erweitert.
- Alle Fußballbereiche auf denselben 51-Ligen-Katalog vereinheitlicht.
- Tagesgrenzen konsequent auf `Europe/Zurich` umgestellt.
- Fortschritts- und Hintergrundjob-Logik gegen Seitenwechsel gehärtet.
- Automatische Scans vom schlafenden Streamlit-Hosting auf den OVH-VPS
  verlagert.
- Doppelstarter auf Windows und in KIMI deaktiviert.
- Modell und Buchmacherpreis technisch getrennt.
- Automatischen Mehrbuchmacher-Konsens für exakt abbildbare Fußballmärkte
  eingeführt.
- Unpraktische Kurzquoten aus veröffentlichten Tipps entfernt.
- Tennis-Belag, Erfahrung, Serve-Daten und Walk-forward-Kalibrierung
  transparent gemacht.
- Multisport-Scanner bei fehlendem validierten Modell fail-closed gestellt.
- 15K-Konto persistent, abrechenbar und transaktional gemacht.
- 15K-Standard von 25 auf 5 Prozent korrigiert und 68 bestehende Konten auf
  Policy v2 migriert.
- Cent-Floor, Quoten-Konstanten und Buchmacher-Dedup vereinheitlicht.
- Mobile UX in normalem Microsoft Edge auf Desktop und Smartphone geprüft.
- Tägliche Datenbankbackups mit Restore- und SQLite-Integritätsprüfung
  eingerichtet.

## 12. Schwierigkeiten und Lehren

| Schwierigkeit | Verbindliche Lehre |
|---|---|
| Streamlit Community Cloud schlief | Automationen gehören auf einen persistenten Server |
| Supabase-Pooler war ungültig | Keine unbenötigte Cloud-DB als Pflichtabhängigkeit behandeln |
| 28/44/51-Ligen-Divergenzen | Ein einziger kanonischer Ligakatalog |
| Heute/Morgen-Verwechslungen | Datum immer als Zürich-Kalendertag durchreichen und testen |
| Providerlimits bei Vollscans | Discovery einmal täglich, danach Fixture-Refresh |
| Tiefe Quote wurde als Sicherheit gelesen | Modell-p und Preis strikt trennen |
| Fehlende Tennis-Metadaten | Oberfläche darf fehlende Coverage nicht verschleiern |
| Multisport-Menü versprach mehr als Modelle konnten | Termine und Tippfreigabe getrennt ausweisen |
| 25-%-Challenge-Default | Defaults sind Produktempfehlungen und müssen mathematisch geprüft werden |
| Browserimport war für Consumer ungeeignet | Aktiver Produktpfad darf kein offenes Buchmacherfenster verlangen |
| PC-/Browserwechsel | Identität darf langfristig nicht nur in `localStorage` leben |

## 13. Aktueller Evidenzstand

Die jeweils aktuelle, vollständig isolierte Testsuite belegt
Implementierungsverträge, nicht Profitabilität. Der exakte Zähler und das
Datum stehen im `PROJECT_HANDBUCH.md` und im PC-Wechsel-Runbook.

Der bisherige Shadow-Stand ist jung und je Sport unterschiedlich. Fußball,
Tennis, E-Sport und Rotkarten besitzen noch keine ausreichende unabhängige,
versionsgleiche Stichprobe für eine seriöse Langfristbehauptung. Eine spätere
Echtgeldfreigabe benötigt mindestens:

- mindestens 300 eindeutige Fixtures mit vorab protokolliertem Pick, gültigem
  Opening/Closing und korrekter Abrechnung je Modell-/Policy-Version;
- eine separate Prüfung der statistischen Abhängigkeit, insbesondere Cluster
  nach Liga, Team und Spieltag; Eindeutigkeit allein beweist Unabhängigkeit
  nicht;
- Kalibrierung, Brier Score und Log Loss gegen einen vollständigen No-Vig-
  Marktbenchmark;
- positiven Closing-Line-Value mit überzeugender Untergrenze;
- Renditeintervall, dessen Untergrenze die Entscheidung trägt;
- korrekt geprüfte Settlementregeln des tatsächlich verwendeten Anbieters.

Bis dahin ist BetBoy ein technisch ernstzunehmender Wettfinder im
Evidenzaufbau, aber kein bewiesenes Gewinnsystem.

## 14. Sicherheit und Geheimnisse

Niemals committen, chatten oder screenshotten:

- API-Schlüssel;
- Telegram-Token und Chat-ID;
- Datenbank-URLs;
- private SSH-Schlüssel;
- produktive `config.ini`, `.env` oder `.streamlit/secrets.toml`;
- Runtime-Datenbanken mit Nutzer- oder Wetthistorie.

Git enthält nur `config.ini.example` und
`.streamlit/secrets.example.toml`. Produktionswerte bleiben in
`/etc/betboy/betboy.env` beziehungsweise der ignorierten Server-
`config.ini`.

Historisch veröffentlichte Schlüssel gelten bis zur Rotation als
kompromittiert. Rotation kommt vor einer Bereinigung alter Git-Historie.

## 15. Verbindliche Roadmap

### P0: vor breiter Vermarktung

1. Historisch exponierte Provider- und Telegram-Secrets rotieren.
2. Das seit 16. August aktive OVH-Standardbackup auf Retention und
   Wiederherstellbarkeit prüfen, einen Totalverlust-Restore testen und den
   Backup-Hash extern verankern.
3. Login und geräteübergreifende Benutzerkonten implementieren.
4. Daten- und Quotenlizenzen für kommerzielle Nutzung klären.
5. Datenschutz, Altersgrenzen, Länder- und Glücksspielrecht prüfen.
6. Settlementregeln für N1Bet beziehungsweise den tatsächlichen Anbieter
   schriftlich abbilden.

### P1: Modellbeweis

1. Eingefrorene Versionen weiter im Shadow sammeln.
2. Dropout-Funnel je Sport und Markt auswerten.
3. CLV, No-Vig-Benchmark und Kalibrierung unabhängig bewerten.
4. Heuristiken wie H2H-Veto, Wettergrenzen und Kombi-Abschläge per
   vorregistrierter Ablation prüfen.
5. Erst danach Sport-/Marktpfade auf `RELEASED` stellen.

### P2: Consumer-Produkt

1. Backend-API aus dem Streamlit-Kern extrahieren.
2. Native oder hochwertige Cross-Platform-Mobile-App aufbauen.
3. Push-Benachrichtigungen nur für echte freigegebene Tipps einführen.
4. Admin-, Nutzer- und Evidenzdaten sauber trennen.
5. System-, Quota- und Backupfehler extern alarmieren.

## 16. Entscheidungsregeln für künftige Arbeit

Vor jeder Änderung sind diese Fragen zu beantworten:

1. Verbessert sie den Nutzer als Wettfinder oder nur internes Monitoring?
2. Bleibt Modell-p vollständig unabhängig vom Buchmacherpreis?
3. Ist klar, welche Evidenzstufe die Ausgabe besitzt?
4. Wird bei fehlenden Daten fail-closed gearbeitet?
5. Sind Datum, Zeitzone und Startstatus korrekt?
6. Gibt es eine sport- und marktspezifische Validierung?
7. Sind Preisquelle, Marktlinie, Frische und Anbieterzahl nachweisbar?
8. Bleiben Ledger, Kontostand und Settlement transaktional korrekt?
9. Sind Desktop und Smartphone ohne Überlauf und unnötige Erklärflächen
   bedienbar?
10. Gibt es Regressionstests für den veränderten Vertrag?
11. Wurde der VPS nach dem Push auf denselben Commit gebracht?
12. Wird keine Profitabilität behauptet, die die Evidenz nicht trägt?

## 17. Übergabe in einem Satz

BetBoy ist heute ein auf einem persistenten VPS laufender, mathematisch
konservativer Wettfinder mit starkem Fußballkern, ehrlichem Shadow-Aufbau und
noch offenen Beweisen für langfristigen Wettvorteil; der nächste Rechner muss
nur Entwicklung, SSH und sichere Geheimnisverwaltung übernehmen, nicht die
laufenden Serverjobs.
