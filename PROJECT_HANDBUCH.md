# BetBoy - Projekthandbuch und technische Übergabe

## Dokumentstatus

| Feld | Wert |
|---|---|
| Stand | 17. Juli 2026 |
| Repository | https://github.com/xantharu123-png/btts-pro-analyzer |
| Produktiv-Branch | `main` |
| Übergabe-Commit | `0925d18bb8deb97ff0f74f18930665980f122680` |
| Live-App | https://btts-pro-analyzer-atnoeulcg3jzwkghckhbth.streamlit.app/ |
| Lokaler Projektpfad | `C:\Users\miros\Desktop\BetBoy\btts-pro-analyzer` |
| Python | 3.11 |
| UI-Framework | Streamlit |

Dieses Dokument ist die maßgebliche Übergabe für die weitere Entwicklung. Es enthält bewusst keine API-Schlüssel, Passwörter oder Datenbank-Zugangsdaten.

## 1. Kurzfassung

BetBoy ist ein datengetriebener Analyse-Arbeitsplatz für Fußballwetten mit ergänzenden, ausdrücklich explorativen Multi-Sport-Scannern. Das System soll Wahrscheinlichkeiten unabhängig vom Buchmacher ermitteln und Marktquoten erst danach als Preis bewerten.

Der aktuelle Kernzustand ist technisch stabil:

- Der Code ist auf `main` committed und zu GitHub gepusht.
- Der letzte vollständige Testlauf ergab `127 passed, 5 subtests passed`.
- Mobile, Tablet und Desktop wurden mit installiertem Google Chrome geprüft.
- Die Streamlit-App wurde nach dem letzten Push erfolgreich aufgeweckt und gerendert.
- API-Football ist extern gesperrt; der Anbieter meldet `Your account is suspended`.
- Die bisherige Supabase-Verbindung ist ungültig. Die App fällt kontrolliert auf lokale SQLite-Datenbanken zurück.

Die größte noch offene Arbeit liegt nicht in der Rechenlogik, sondern in den Produktionsabhängigkeiten: API-Football reaktivieren, persistente Datenbank korrekt einrichten und Challenge-Daten nutzerbezogen speichern.

## 2. Produktziel

### 2.1 Primäres Ziel

Die App soll für anstehende Fußballspiele belastbare, nachvollziehbare Modellwahrscheinlichkeiten liefern und nur dann eine handelbare Auswahl freigeben, wenn alle erforderlichen Daten- und Validierungstore erfüllt sind.

Das gewünschte Verhalten lautet:

1. Statistische Daten und Kontext werden geprüft.
2. Das Modell schätzt Ereigniswahrscheinlichkeiten ohne Buchmacherquote.
3. Nicht belastbare Kandidaten werden verworfen.
4. Erst danach werden aktuelle N1Bet-Preise manuell ergänzt oder verifizierte Marktpreise geladen.
5. Eine Auswahl wird nur bei positivem risikoadjustiertem Erwartungswert freigegeben.

### 2.2 15K-Challenge

Die Challenge startet standardmäßig bei 100 EUR und zeigt den Fortschritt zu einem Zielwert von 15.000 EUR. Pro Tag sollen höchstens drei unterschiedliche Spiele in Frage kommen. Die gewünschte Gesamtkorridorquote liegt zwischen 2,00 und 3,00.

Wichtig: 15.000 EUR sind ein Zielwert, keine Prognose und keine Garantie. Der ursprüngliche Wunsch, Einsätze nach Verlusten zu verdoppeln oder zu verdreifachen, wurde bewusst nicht als Martingale umgesetzt. Eine solche Progression erhöht das Ruinrisiko und erzeugt keinen mathematischen Vorteil. Stattdessen verwendet die App Viertel-Kelly mit einer harten Einsatzkappe von 2 % des verfügbaren Guthabens.

### 2.3 Nicht-Ziele

- Keine Behauptung sicherer oder garantierter Wetten.
- Keine Quote als Beweis für Eintrittswahrscheinlichkeit.
- Keine Freigabe, nur damit täglich zwingend ein Tipp erscheint.
- Keine simulierten Buchmacherpreise, wenn kein echter Preis vorhanden ist.
- Keine automatische Umgehung von N1Bet-Zugriffsschutz oder AGB.
- Keine Vermischung verschiedener Sportarten oder Datenmodelle.

### 2.4 Wichtige Meilensteine

| Commit | Inhalt |
|---|---|
| `e7d5756` | Konfiguration, API-Schlüsseltrennung und mathematische Grundlage gehärtet |
| `cb01363` | Vollständiger Betting-Audit, responsive UX und 15K-Challenge integriert |
| `f2173b5` | Scanner-Mathematik, Providerfehler und Signal-UX weiter abgesichert |
| `0925d18` | Ultra-Audit aller Modelle, Datenverträge, Kalibrierungen und Ticketgates abgeschlossen |

Ältere Commits enthalten die schrittweise Einführung von alternativen Märkten, Red-Card-Monitoring, Multi-Sport-Scannern und der Edge-basierten Value-Logik. Die vier genannten Commits bilden die maßgebliche Härtungsphase.

## 3. Leitprinzipien

### Modell zuerst, Preis danach

Buchmacherquoten dürfen Kandidaten weder erzeugen noch deren Modellwahrscheinlichkeit erhöhen. Eine niedrige Quote ist kein Sicherheitsmerkmal. Quoten werden ausschließlich für implizite Wahrscheinlichkeit, Edge, Erwartungswert und Einsatzberechnung verwendet.

### Fail closed

Fehlende, widersprüchliche, veraltete oder falsch zugeordnete Daten führen zu keiner Empfehlung. Ein leerer Ergebnisbereich ist in diesem System besser als eine scheinbar präzise, aber nicht belegte Auswahl.

### Herkunft und Zeitstempel

Marktpreise brauchen Buchmacher, Quelle und einen zeitzonenfähigen Zeitstempel. Für eine Overround-Prüfung müssen alle Marktseiten vom selben Buchmacher und derselben Quelle stammen.

### Keine Datenleckage

Training und Walk-forward-Validierung werden chronologisch und nach Spieltag gruppiert. Spiele desselben Tages dürfen sich nicht gegenseitig als Zukunftswissen verwenden.

### Trennung von Analyse und Aktion

Explorative Sport- oder Marktindikatoren dürfen angezeigt werden, sind aber ohne belastbare Out-of-sample-Kalibrierung nicht handlungsfähig und erhalten keinen Einsatzvorschlag.

## 4. Aktuelle Benutzeroberfläche

Die App besitzt eine flache Sidebar-Navigation ohne tiefe Menüverschachtelung:

| Bereich | Zweck | Status der Signale |
|---|---|---|
| `Spiele` | Prematch-Spiele analysieren, BTTS und Evidenz filtern, Details vergleichen | Nur bei ausreichender Datenbasis |
| `Märkte` | Alternative Märkte wie Tore, Ecken und Karten untersuchen | Ohne vollständige Validierung explorativ |
| `Live` | Live-Fußball und Platzverweise prüfen | Strenge Live-Datenqualitätsstufen |
| `Modell` | Datenbestand, Validierung und Training verwalten | Administrativ |
| `15K Challenge` | Tägliche Shortlist, N1Bet-Preisprüfung, Ticket und Kontoverlauf | Strengste Freigaberegeln |
| `Multi-Sport` | E-Sport, Basketball, NHL, Tennis und Cricket getrennt anzeigen | Explorativ, kein Wettauftrag |

Die Oberflächen wurden für folgende Viewports geprüft:

- Smartphone: 390 x 844
- Tablet: 768 x 1024
- Desktop: 1280 x 720

Bei der letzten Prüfung gab es keine horizontale Seitenüberbreite und keine Streamlit-Ausnahme. Für Browser-QA wurde normales installiertes Chrome verwendet, nicht die Codex-Browsererweiterung.

## 5. Technische Architektur

### 5.1 Zentrale Module

| Datei | Verantwortung |
|---|---|
| `btts_pro_app.py` | Streamlit-Einstieg, Navigation, Seitenaufbau, Providerstatus und UI-Orchestrierung |
| `config_loader.py` | Einheitliche Konfiguration aus INI, Umgebung und Streamlit Secrets |
| `api_football.py` | Strikter API-Football-Client für Fixtures, Form, H2H und Statistiken |
| `data_engine.py` | Historische Matchdaten, SQLite-/PostgreSQL-Zugriff und Datenimport |
| `football_data_history.py` | Kontrollierter Import öffentlicher CSV-Historie von football-data.co.uk |
| `advanced_analyzer.py` | BTTS-Analyse, Evidenzscore, Dixon-Coles, bivariate Poisson-Logik und Modelltraining |
| `betboy_v3_ml_engine.py` | Feature-Modell, Ensemble, Backtesting und Kalibrierungsdiagnostik |
| `betting_math.py` | Zentrale Berechnung von impliziter Wahrscheinlichkeit, Edge, EV und Kelly |
| `best_bet_finder.py` | Auswahl bereits validierter Modellkandidaten ohne Preislogik |
| `smart_bet_finder.py` | Verifizierte Marktpreise, Overround, risikoadjustierter EV und Stake |
| `alternative_markets.py` | Wahrscheinlichkeitsmodelle für Tore, Ecken, Karten und Live-Metriken |
| `alternative_markets_tab_extended.py` | Streamlit-Darstellung alternativer Märkte |
| `challenge_engine.py` | Marktdefinitionen, Walk-forward-Validierung, Kandidaten, Kontext und Tickets |
| `challenge_15k.py` | Challenge-Provider, Scan-Ablauf und komplette Challenge-Oberfläche |
| `challenge_store.py` | Challenge-Guthaben, Tickets, Settlement und erneute serverseitige Validierung |
| `clv_tracker.py` | Opening-/Closing-Line-Daten und Closing-Line-Value |
| `ultra_live_scanner_v3.py` | Live-Fußballmodell mit expliziten Datenqualitätstoren |
| `red_card_bot.py` | Platzverweis-Erkennung, Statistikabruf und optionale Benachrichtigung |
| `red_card_impact_predictor.py` | Modelliert den Einfluss eines Platzverweises auf Restspiel und Tore |
| `scanners/*.py` | Getrennte explorative Scanner für weitere Sportarten |
| `tests/*.py` | Regressionen für Mathematik, Datenverträge, Providerfehler und Workflows |

### 5.2 Prematch-Datenfluss

1. API-Football liefert zukünftige Fixtures für exakt angeforderte Ligen.
2. Fixture-ID, Liga, Teams, Datum und Status werden strikt validiert.
3. Historische Ergebnisse kommen aus Datenbank, API-Football oder kontrolliertem CSV-Import.
4. Team-, Venue-, Form- und Ligastärken werden nur aus Spielen vor dem jeweiligen Stichtag gebildet.
5. Poisson-/Dixon-Coles- und gegebenenfalls Count-Modelle erzeugen Ereigniswahrscheinlichkeiten.
6. Day-grouped Walk-forward validiert jedes Marktmodell außerhalb der Trainingsperiode.
7. Eine konservative Wahrscheinlichkeit wird aus mehreren Modellhorizonten und Kalibrierungsabschlag gebildet.
8. H2H, Verletzungen, Wetter und bestätigte Aufstellungen werden als Kontextgates angewendet.
9. Erst die modellbasierte Shortlist wird für die N1Bet-Preisprüfung freigegeben.
10. Das Ticket wird aus Preis, konservativer Wahrscheinlichkeit, Abhängigkeitsabschlag und EV neu berechnet.
11. `ChallengeLedger` validiert alle Felder nochmals, bevor ein Ticket gespeichert wird.

## 6. Mathematik und Validierung

### 6.1 Modellfamilien

- Dixon-Coles-Korrektur für niedrige Fußballergebnisse.
- Bivariate Poisson-Verteilung für gemeinsame Torkomponenten.
- Negative-Binomial-Modelle für überdisperse Ecken- und Kartenanzahlen.
- Beta-Smoothing und Shrinkage gegen extreme Raten aus kleinen Stichproben.
- Score-Matrizen mit kontrollierter Restwahrscheinlichkeit statt still abgeschnittener Tails.
- Ensemble-/ML-Bausteine nur mit chronologischer Out-of-sample-Prüfung.

### 6.2 Harte Challenge-Schwellen

| Regel | Wert |
|---|---|
| Zielguthaben | 15.000 EUR |
| Zulässige Gesamtquote | 2,00 bis 3,00 |
| Maximale Ticket-Legs | 3 |
| Maximale Einsatzquote | 2 % des Guthabens |
| Kelly-Variante | Viertel-Kelly |
| Cross-Leg-Abhängigkeitsfaktor | 0,97 je zusätzlichem Leg |
| Mindestspiele Liga | 24 |
| Mindestspiele Heim-/Auswärtskontext | 5 je Team |
| Mindestspiele Form | 5 je Team |
| Mindestspiele H2H | 3 |
| Mindestbeobachtungen Validierung | 200 |
| Mindestanzahl gestützter Kalibrierungsbins | 3 |
| Mindestbeobachtungen je Bin | 20 |
| Maximale ECE | 0,08 |
| Maximaler Fehler eines Kalibrierungsbins | 0,12 |
| Relative Mindestverbesserung gegen Baseline | 2 % |
| Mindest-EV je Leg | 2 % |
| Mindest-EV des Tickets | 3 % |
| Maximales Alter manueller Quote | 10 Minuten |
| Mindest-Evidenzscore eines Challenge-Kandidaten | 72 % |

### 6.3 Kernformeln

Für Dezimalquote `o` und konservative Wahrscheinlichkeit `p`:

```text
Implizite Wahrscheinlichkeit = 1 / o
Erwartungswert                = p * o - 1
Full Kelly                    = ((o - 1) * p - (1 - p)) / (o - 1)
Verwendeter Einsatzanteil     = min(max(Full Kelly, 0) * 0,25, 0,02)
```

Bei Kombinationen wird die gemeinsame Modellwahrscheinlichkeit zusätzlich mit `0,97^(Legs-1)` reduziert. Kandidaten desselben Fixtures oder mit wiederholten Teams dürfen nicht gemeinsam auf ein Ticket.

### 6.4 Bookmaker-Unabhängigkeit

Die Modell-Shortlist wird quotenfrei gebaut. In der Challenge werden aktuelle N1Bet-Quoten anschließend manuell eingegeben. Jede Quote wird erneut gegen die konservative Modellwahrscheinlichkeit gerechnet. Ein niedriger Preis kann eine Auswahl deshalb nicht retten; negativer Einzel- oder Ticket-EV sperrt sie.

## 7. Unterstützte Fußballmärkte

`challenge_engine.market_specs()` ist die maßgebliche Liste. Modelliert werden nur Märkte, die aus den vorhandenen Daten eindeutig berechnet und abgerechnet werden können. Dazu gehören insbesondere:

- Endergebnis 1/X/2
- Doppelte Chance
- Beide Teams treffen
- Tor-Gesamtmärkte und Team-Tormärkte
- definierte Torbereiche
- Ecken gesamt und Teamecken
- gelbe Karten gesamt und Teamkarten

Für Over/Under werden nur Linien verwendet, deren Push-Verhalten eindeutig behandelt ist. Halb-Linien sind zweiwegig; ganzzahlige Linien dürfen nicht fälschlich wie Zweiwegmärkte behandelt werden. Die Auswahl an Märkten darf nur erweitert werden, wenn Ergebnisdaten, Settlement und Out-of-sample-Validierung vollständig vorhanden sind.

## 8. Datenqualität und Freigaben

### 8.1 Prematch-Evidenzscore

Der in `Spiele` sichtbare Evidenzscore ist keine zweite Gewinnwahrscheinlichkeit. Er bewertet Abdeckung, Stichprobengröße, Modellübereinstimmung, Aktualität und Validierung. Fehlende Formdaten begrenzen den erreichbaren Score. Modellwidersprüche senken ihn.

### 8.2 Live-Datenqualität

Live-Signale unterscheiden zwischen:

- berechenbarer Basis aus Spielstand, Minute und belastbaren Vorinformationen,
- höherer Stufe mit Live-xG und Prematch-Basis,
- unzureichenden Daten ohne handlungsfähige Ausgabe.

Fehlende Werte werden nicht mehr automatisch als Null interpretiert. Besonders bei Karten, Schüssen, xG und Restspielzeit würde das sonst systematische Fehlbewertungen erzeugen.

### 8.3 Kontextgates der Challenge

- Fixture muss zukünftig und noch nicht gestartet sein.
- Teams und Liga müssen exakt zur angeforderten Partie gehören.
- H2H darf nur Spiele der beiden konkreten Teams enthalten.
- Verletzungsdaten müssen valide und den Teams zuordenbar sein.
- Wetterdaten müssen strukturell und zeitlich plausibel sein.
- Bestätigte Aufstellungen müssen für beide Teams vorliegen.
- Jede Aufstellung benötigt genau elf eindeutige, gültige Spieler-IDs des richtigen Teams.
- Wiederholte Fixtures, Teams und veraltete Snapshots werden gesperrt.

Diese Regeln bedeuten bewusst, dass eine finale Challenge-Auswahl häufig erst nahe am Anstoß möglich ist oder vollständig ausbleibt.

## 9. Provider und Integrationen

Statusangaben beziehen sich auf die letzte Prüfung am 17. Juli 2026.

| Provider | Verwendung | Aktueller Zustand | Nächste Aktion |
|---|---|---|---|
| API-Football / API-Sports | Hauptquelle für Fixtures, Statistiken, Form, H2H, Aufstellungen, Verletzungen, Live und Challenge | Schlüssel vorhanden, Konto vom Provider als `suspended` gemeldet | Bestehendes Abo im Dashboard prüfen und reaktivieren; nicht blind neu kaufen |
| football-data.org | Älterer/sekundärer Schlüssel | Schlüssel antwortet, wird vom aktiven Analyzer nicht verwendet | Kein bezahltes Abo nötig, solange kein eigener Adapter geplant ist |
| football-data.co.uk | Öffentliche historische CSV-Ergebnisse | Verfügbar, kein API-Schlüssel nötig | Als historische Zusatzquelle behalten |
| OpenWeather | Wetterkontext der Challenge | Lokal konfiguriert | Kontingent und Deployment-Secret prüfen |
| The Odds API | Automatische Marktpreise | Derzeit nicht konfiguriert | Optional; N1Bet bleibt aktuell manuelle Preisprüfung |
| Supabase/PostgreSQL | Persistente Matchdaten | Deployment-Verbindung ungültig; Tenant/User wird nicht gefunden | Neue korrekte Pooler-URL eintragen und Migration testen |
| PandaScore | E-Sport | Nicht konfiguriert | Nur nötig, wenn E-Sport weiterentwickelt wird |
| NBA/NHL/EuroLeague öffentliche Endpunkte | Multi-Sport-Snapshots | Ohne Schlüssel, aber extern veränderlich | Nur explorativ behandeln und Providerfehler sichtbar halten |
| SofaScore-Endpunkt | Tennis | Unoffiziell und extern veränderlich | Nicht als dauerhaft garantierten Vertrag betrachten |
| RapidAPI/CricAPI | Cricket | Nicht konfiguriert | Nur bei Priorisierung von Cricket aktivieren |
| Telegram | Platzverweis-Benachrichtigung | Nicht konfiguriert | Optional nach erfolgreichem Live-Provider-Test |

### Wichtige API-Entscheidung

`FOOTBALL_DATA_API_KEY` und `API_FOOTBALL_KEY` sind nicht austauschbar. Endpunkte, Header und Datenverträge sind verschieden. Ein Regressionstest stellt sicher, dass der football-data.org-Schlüssel niemals als API-Football-Schlüssel eingesetzt wird.

## 10. Konfiguration und Secrets

Konfigurationspriorität, von niedrig nach hoch:

1. `config.ini`
2. Umgebungsvariablen
3. Streamlit Secrets

Unterstützte Umgebungsvariablen:

```text
FOOTBALL_DATA_API_KEY
API_FOOTBALL_KEY
OPENWEATHER_API_KEY
SUPABASE_DB_URL
ODDS_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PANDASCORE_KEY
RAPIDAPI_KEY
CRICKET_API_KEY
```

Lokale `config.ini`, `.streamlit/secrets.toml`, Datenbanken und Modellartefakte sind über `.gitignore` ausgeschlossen. Keine echten Schlüssel in Dokumentation, Tests, Logs oder Commits aufnehmen.

## 11. Persistenz

### 11.1 Matchdaten

`DataEngine` bevorzugt PostgreSQL/Supabase, wenn eine gültige URL und `psycopg2` vorhanden sind. Bei Verbindungsfehlern wird SQLite verwendet. Die App bleibt dadurch bedienbar, aber Streamlit Community Cloud garantiert für lokale Dateien keine dauerhafte Speicherung.

### 11.2 Challenge

`ChallengeLedger` speichert aktuell ausschließlich in `challenge_15k.db` via SQLite. Das ist lokal funktionsfähig, aber noch nicht produktionsreif:

- Daten können bei Neustart oder Redeploy verloren gehen.
- Es gibt keine Benutzer-ID und keine Authentifizierung.
- Mehrere Nutzer würden dasselbe Guthaben und dieselben Tickets teilen.
- Der Ledger ist durch `st.cache_resource` pro Prozess gemeinsam.

Vor öffentlicher oder mehrbenutzerfähiger Nutzung muss der Ledger nach PostgreSQL migriert und an eine eindeutige Benutzeridentität gebunden werden.

### 11.3 CLV und Modelle

CLV wird derzeit lokal in SQLite gespeichert. Modellartefakte wie `*.pkl`, `*.joblib` und der Ordner `models/` werden nicht committed. Ein in der Cloud trainiertes Modell kann deshalb nach einem Neustart verschwinden. Für reproduzierbare Produktion braucht es versionierten Artefaktspeicher oder einen deterministischen Trainingsjob.

## 12. Was im Ultra-Audit behoben wurde

### Provider und Datenverträge

- HTTP 200 mit Provider-Fehlerpayload wird nicht mehr als leere erfolgreiche Antwort behandelt.
- Providerfehler werden im UI als Konto-, HTTP- oder Datenfehler sichtbar.
- IDs müssen positive echte Integer sein; Boolean-Werte werden abgelehnt.
- Fixture-, Liga- und Teamzugehörigkeit werden auf jeder Ebene geprüft.
- Naive, zukünftige oder veraltete Zeitstempel werden je nach Kontext abgelehnt.
- Historische Imports sind transaktional: ein fehlerhafter Batch wird nicht teilweise gespeichert.
- CSV-Felder sind allowlist-basiert; Bookmakerpreise aus historischen CSVs werden nicht als Modellfeature übernommen.

### Modell und Statistik

- Same-day Leakage in Training und Walk-forward wurde geschlossen.
- Mindeststichproben, ECE, Binfehler und Kalibrierungsabdeckung werden vollständig geprüft.
- Behauptetes `calibrated=True` reicht nicht mehr ohne passende Metriken.
- Score- und Count-Matrizen behandeln Restwahrscheinlichkeit kontrolliert.
- Sparse Samples und hohe Raten werden nicht durch willkürliche Abschneidung schön gerechnet.
- H2H, Form und Teamaggregate werden auf innere Konsistenz geprüft.

### Quoten und Tickets

- Modellwahrscheinlichkeit und Buchmacherpreis sind strikt getrennt.
- Marktseiten für den Overround müssen von derselben Quelle und demselben Buchmacher stammen.
- Preise müssen frisch und vor Anstoß erfasst sein.
- CLV vergleicht nur identischen Buchmacher und identische Quelle.
- Ticketfelder werden beim Speichern aus den Legs vollständig neu berechnet.
- Quote, EV, Abhängigkeit, Kelly, Stake, Cent-Rundung und Auszahlung werden serverseitig verifiziert.
- Pro Fixture wird höchstens ein Value-Signal verwendet.

### Challenge-Kontext

- Bereits gestartete Spiele werden blockiert.
- Doppelte Fixtures und wiederholte Teams werden blockiert.
- Fehlerhafte H2H-, Verletzungs-, Wetter- und Aufstellungsdaten schließen die Auswahl.
- Aufstellungen müssen je Team exakt elf eindeutige Spieler enthalten.
- Snapshot- und Quotenalter werden begrenzt.

### Multi-Sport und Live

- NHL-Spiele laufen nicht mehr durch Basketball-Projektionslogik.
- Cricket-Overs werden korrekt als Bälle interpretiert; `10.5` sind 65 Bälle und `10.6` ist ungültig.
- Tennis-, Cricket-, Basketball-, NHL- und E-Sport-Ausgaben sind ohne Kalibrierung nicht handlungsfähig.
- Karten-, Ecken- und Schussdaten behandeln fehlende Werte nicht mehr als echte Nullen.
- Platzverweisereignisse werden Team, Fixture und Spielminute strikt zugeordnet.

### UX

- Flache Navigation statt mehrfach verschachtelter Tabs.
- Bedienelemente sind auf Smartphone und Tablet umgebrochen.
- Kennzahlen, Tabellen und Slider besitzen stabile responsive Abmessungen.
- Providerstatus und Blocker werden direkt sichtbar.
- Quotenfreie Analyse und spätere N1Bet-Preisprüfung sind visuell getrennt.

## 13. Schwierigkeiten und ihre Ursachen

### Zwei ähnlich benannte Fußball-APIs

`football-data.org` und API-Football wurden historisch parallel konfiguriert. Dadurch bestand die Gefahr, einen gültigen Schlüssel beim falschen Endpoint einzusetzen. Die aktive App verwendet jetzt explizit API-Football. football-data.org ist kein automatischer Ersatz.

### API-Football liefert Fehler mit HTTP 200

Der Provider kann Kontofehler im JSON-Feld `errors` liefern, obwohl der HTTP-Status 200 ist. Frühere Logik interpretierte dies teilweise als leere Datenmenge. Die Antwortverarbeitung prüft nun Status, Fehlerpayload und erwartete Datentypen.

### Ungültiger Supabase-Tenant

Die hinterlegte Pooler-Verbindung meldete sinngemäß `tenant/user not found`. Die App darf deshalb nicht vollständig abstürzen und verwendet lokal SQLite. Das löst die Verfügbarkeit, aber nicht die dauerhafte Speicherung.

### Overconfidence durch kleine Stichproben

Form, H2H und seltene Märkte können extreme Prozentwerte aus wenigen Beobachtungen erzeugen. Dagegen wurden Mindestgrößen, Smoothing, Shrinkage, konservative Abschläge und Out-of-sample-Gates eingeführt.

### Zeitliche Datenleckage

Ein einfaches zeilenweises Walk-forward kann frühere Spiele desselben Tages bereits als Training für spätere Spiele desselben Tages verwenden. Die Validierung ist deshalb nach Kalendertag gruppiert.

### Quoten als psychologischer Anker

Niedrige Quoten wirkten in früheren Darstellungen implizit sicher. Das System baut Kandidaten jetzt vollständig ohne Quoten und bewertet Preise erst in einer separaten Phase.

### Upstream-Instabilität

Mehrere Multi-Sport-Quellen sind öffentliche oder inoffizielle Endpunkte. Payloads, Ratelimits und Verfügbarkeit können sich ohne Ankündigung ändern. Jeder Scanner validiert deshalb seine Daten separat und bleibt explorativ.

### Streamlit-Schlafmodus und Browser-QA

Streamlit Community Cloud legt inaktive Apps schlafen. Das ist kein Codefehler. Für die letzte visuelle Prüfung wurde die App mit normalem Chrome aufgeweckt. Die Codex-Browsererweiterung wurde vermieden, weil sie lokal die Codex-App destabilisieren konnte.

## 14. Bekannte offene Punkte und Risiken

### Priorität 0 - vor ernsthafter Nutzung

1. API-Football-Konto im bestehenden Dashboard prüfen und reaktivieren. Kein zweites Abo kaufen, solange ein bezahltes Jahresabo möglicherweise noch gültig ist.
2. Gültige Supabase-/PostgreSQL-Verbindung einrichten und Persistenz über einen echten Redeploy testen.
3. Challenge-Ledger auf PostgreSQL und Benutzeridentität migrieren.
4. Die App mehrere Tage im Shadow Mode betreiben, ohne echtes Geld einzusetzen.

### Priorität 1 - Produktionsreife

1. API-Request-Budget pro Scan messen und im UI anzeigen.
2. Provider-Health, Ratelimit und letzte erfolgreiche Aktualisierung persistieren.
3. Automatische N1Bet-Preise nur über eine erlaubte, stabile Schnittstelle integrieren; bis dahin manuelle Eingabe behalten.
4. Ticket-Settlement gegen offizielle Resultate automatisieren und weiterhin manuelle Korrektur ermöglichen.
5. Challenge- und CLV-Migrationen versionieren.
6. Modellartefakte reproduzierbar speichern und versionieren.
7. GitHub Actions für Tests und statische Checks ergänzen.

### Priorität 2 - fachliche Weiterentwicklung

1. Weitere Ligen erst nach ausreichender historischer Abdeckung freigeben.
2. Märkte nur mit eigener Walk-forward-Kalibrierung erweitern.
3. Multi-Sport entweder mit bewährten Engines und Datenverträgen produktisieren oder klar als Monitoring belassen.
4. CLV-Auswertung und Kalibrierungsdrift als Dashboard aufbauen.
5. Request-Caching über mehrere Streamlit-Sessions hinweg verbessern.

## 15. Bewusste Einschränkungen

- Ein Markt mit weniger als 200 OOS-Beobachtungen kann trotz plausibler Modellidee gesperrt bleiben.
- Bestätigte Aufstellungen sind häufig erst kurz vor Spielbeginn verfügbar.
- Bei unvollständigen Kontextdaten kann die 15K-Challenge an einem Tag null Spiele liefern.
- Ohne The Odds API existiert kein automatischer N1Bet-Preisfeed.
- Ein positiver modellierter EV ist eine Schätzung, kein Beweis eines tatsächlichen Vorteils.
- Selbst ein kalibriertes Modell kann verlieren; Varianz und Modellfehler bleiben bestehen.

## 16. Tests und Qualitätssicherung

### Vollständiger Testlauf

```powershell
.\.codex_test_venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Letztes bestätigtes Ergebnis:

```text
127 passed, 5 subtests passed
```

### Patch-Sauberkeit

```powershell
git diff --check
git status --short
```

Vor Commit und Push müssen beide Befehle sauber sein. Datenbanken, Secrets, Modellartefakte und QA-Screenshots dürfen nicht staged werden.

### Browser-QA

Vor einer UI-Veröffentlichung mindestens prüfen:

1. `Spiele`, `Märkte`, `Live`, `Modell`, `15K Challenge`, `Multi-Sport` öffnen.
2. Smartphone, Tablet und Desktop testen.
3. Keine Root-Überbreite und keine Streamlit-Exception.
4. Providerfehler müssen als Fehler erscheinen, nicht als "keine Spiele".
5. Challenge darf bei unzureichenden Daten kein Ticket erzeugen.

## 17. Lokale Inbetriebnahme

```powershell
cd C:\Users\miros\Desktop\BetBoy\btts-pro-analyzer
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run btts_pro_app.py
```

Danach ist die App standardmäßig über `http://localhost:8501` erreichbar. Falls der Port belegt ist:

```powershell
streamlit run btts_pro_app.py --server.port 8502
```

Für lokale Konfiguration `config.ini.example` nach `config.ini` übertragen und Werte nur lokal eintragen. Für Streamlit Cloud `.streamlit/secrets.example.toml` als Schema verwenden und die echten Werte in den App-Secrets pflegen.

## 18. Deployment

Der produktive Code liegt auf `main`. Ein Push auf `main` stößt das Streamlit-Deployment an.

```powershell
git add -A
git commit -m "Beschreibende Commit-Nachricht"
git push origin main
```

Nach dem Push:

1. GitHub-Remote-Hash gegen lokalen Hash prüfen.
2. Streamlit einige Minuten für den Build geben.
3. Schlafende App über die Live-URL aufwecken.
4. Providerstatus und alle Hauptseiten in normalem Chrome prüfen.
5. Keine Secrets oder vollständigen Providerpayloads in Logs ausgeben.

## 19. Arbeitsregeln für Claude oder weitere Entwickler

Diese Regeln dürfen nicht still gelockert werden:

1. Quoten niemals als Feature zur Erzeugung oder Erhöhung der Modellwahrscheinlichkeit verwenden.
2. `FOOTBALL_DATA_API_KEY` niemals an API-Football-Endpunkte senden.
3. Providerfehler nicht als leere erfolgreiche Datenmenge behandeln.
4. Keine erfundenen Quoten, Zeitstempel, Lineups oder Statistiken einsetzen.
5. Boolean, NaN und Infinity nicht still als Zahlen akzeptieren.
6. Alle produktiven Zeitstempel zeitzonenfähig und bevorzugt in UTC verarbeiten.
7. Walk-forward chronologisch und nach Spieltag gruppieren.
8. Validierungsmetriken vollständig prüfen; ein einzelnes `calibrated`-Flag reicht nicht.
9. Fehlende Sportdaten nicht automatisch zu Null machen.
10. Explorative Signale ohne OOS-Validierung erhalten keinen Kelly-Stake und keine Fair-Price-Behauptung.
11. Challenge-Gates nicht lockern, nur damit eine tägliche Auswahl erscheint.
12. Vor Änderungen bestehende Tests und Datenverträge lesen.
13. Dirty Worktree respektieren und fremde Änderungen nicht zurücksetzen.
14. Keine Secrets, SQLite-Dateien oder Modell-Binaries committen.
15. Nach Änderungen Tests, `git diff --check` und responsive Chrome-QA ausführen.
16. Glücksspiel nie als sicher, garantiert oder risikofrei vermarkten.

## 20. Empfohlener nächster Arbeitsauftrag

Der nächste sinnvolle Entwicklungsblock ist die Produktionspersistenz:

1. Neue gültige Supabase-Verbindung einrichten.
2. `ChallengeLedger` hinter ein Storage-Interface stellen.
3. PostgreSQL-Implementierung mit Benutzer-ID ergänzen.
4. Bestehende SQLite-Tests als Vertragsbasis behalten.
5. Migration, Neustart und Mehrbenutzerszenario testen.
6. Erst danach API-Football im Shadow Mode aktivieren und reale Datenqualität beobachten.

## 21. Übergabeprompt für Claude

```text
Lies zuerst PROJECT_HANDBUCH.md vollständig und behandle es als aktuellen
Projektvertrag. Prüfe danach git status, den letzten Commit und die betroffenen
Tests. Bewahre insbesondere Modell/Preis-Trennung, Fail-closed-Datenverträge,
day-grouped Walk-forward, die 2-%-Stake-Kappe und die Trennung der beiden
Fußball-APIs. Ändere keine Schwelle nur mit dem Ziel, mehr Tipps auszugeben.
Arbeite bis Implementierung, Tests und eine klare Zusammenfassung abgeschlossen
sind. Committe oder pushe nur, wenn dies ausdrücklich beauftragt wurde.
```

## 22. Übergabestatus

Der Codezustand `0925d18` ist die aktuelle belastbare Basis. Die mathematischen und technischen Audits sind umgesetzt. Noch offen sind primär externe Providerfreigabe, dauerhafte Speicherung, Benutzertrennung und längere reale Shadow-Mode-Beobachtung. Diese offenen Punkte dürfen nicht mit einer Modellgarantie verwechselt werden.
