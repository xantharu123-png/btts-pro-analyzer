# BetBoy - Projekthandbuch

## Dokumentstatus

| Feld | Verifizierter Stand |
|---|---|
| Auditzeitraum | 1./2. August 2026 |
| Repository | `xantharu123-png/btts-pro-analyzer` |
| Lokaler Pfad | `C:\Users\miros\Desktop\BetBoy\betboy-app` |
| Branch | `main` |
| Basis vor diesem Audit | `b8c800b` |
| Aktive Cloud-App | `https://betboypro.streamlit.app/` |
| Alte Streamlit-URL | nicht mehr aktiv |
| Framework | Python / Streamlit |
| Fußballkatalog | 51 eindeutige Wettbewerbe |
| Vollständiger Testlauf | 500 Tests und 5 Subtests bestanden |
| Detailaudit | `AUDIT_KIMI_2026-08-01.md` |

Dieses Dokument ist die maßgebliche technische und fachliche Übergabe. Es
enthält absichtlich keine Schlüssel, Passwörter oder Tokens. Ältere Berichte
sind nur Historie, wenn sie diesem Handbuch widersprechen.

## 1. Produktziel

BetBoy ist ein **Wettfinder**, kein Monitoring-Dashboard und kein
Quoten-Nachahmer.

Der verbindliche Ablauf lautet:

1. Das Modell bildet eine Wahrscheinlichkeit ohne Buchmacherquote.
2. Datenherkunft, Aktualität, Stichprobe und zeitliche Validierung werden
   geprüft.
3. H2H, Ausfälle, Wetter und bei Bedarf bestätigte Aufstellungen werden als
   Kontextgates angewendet.
4. Nicht belastbare Kandidaten enden in `NICHT WETTEN`.
5. Erst nach der Modellfreigabe wird die exakte N1Bet-Quote als Preis erfasst.
6. Eine Wette wird nur bei positivem risikoadjustiertem Value freigegeben.
7. Pro Suche werden höchstens wenige, klar begründete Auswahlen angezeigt.

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
- Smartphone und Tablet sind ohne horizontalen Seitenüberlauf bedienbar.
- Alle 51 Fußballligen kommen aus einem gemeinsamen Katalog.

Trotzdem ist **kein Markt als profitabel bewiesen**. Testgrün beweist
Softwareverträge, nicht Wettvorteil. Echtgeldfreigaben bleiben von sauberer
Out-of-sample-Evidenz, Closing-Line-Vergleich und korrektem Settlement abhängig.

## 3. Was in diesem Audit behoben wurde

### Freigaben und Mathematik

- `freemode` ist standardmäßig `False`.
- Ein Modell-Veto bleibt auch im Research-Modus ein Veto.
- Live-Fußball bleibt blockiert, bis eine unabhängige Live-Kalibrierung
  nachgewiesen und explizit markiert ist.
- Rotkarten-Prognosen bleiben nicht handlungsfähig, bis unabhängige
  Shadow-Evidenz vorliegt.
- Multi-Sport entfernt keine Blocker mehr, um trotzdem eine Empfehlung
  anzuzeigen.
- Der Wett-Check übernimmt nur freigegebene beziehungsweise freigabefähige
  Signale.
- Die Tennis-Mindestquote verwendet jetzt bei absolutem Probability-Edge:

```text
Mindestquote = 1 / (p - Mindest-Edge)
```

- Tennis-Kalibrierung wird immer in derselben alphabetischen Orientierung
  angewendet, in der sie trainiert wurde. Das Ergebnis bleibt beim Vertauschen
  der Spieler exakt komplementär.
- Tennis-Gegnerwerte werden vor beiden Match-Updates eingefroren. Der Verlierer
  sieht dadurch keine Information aus demselben Match.
- Fehlende beobachtete Märkte ergeben im Kalibrierungswächter
  `insufficient`, niemals ein falsches `ok`.

### Jobs, Sitzungen und Challenge

- Jobs besitzen Sitzungs-Scope, Generation-ID, Timeout und atomare JSON-Writes.
- Ein alter Thread kann keinen neueren Lauf mehr überschreiben.
- Analyzer-Zugriffe aus Hintergrundthreads sind serialisiert.
- Persistierte Scanner-Signale sind sitzungsgebunden.
- Die Challenge verwendet pro Browser-Sitzung eine eigene lokale Ledger-Datei.
- Jede Einzahlung, Korrektur, Einsatzbuchung und Abrechnung landet in einer
  append-orientierten Transaktionstabelle.
- Ein Verlust bleibt ein Verlust. Es gibt keinen automatischen Neustart auf
  100 Euro.
- Manuelle Kapitalzufuhr wird getrennt als externe Finanzierung ausgewiesen.
- Der Standard-Einsatzanteil ist 25 %, nicht 2 Euro und nicht automatisch
  All-in. Im Konto kann 5-100 % gewählt werden; 100 % wird ausdrücklich als
  Totalverlustrisiko markiert.
- Eine finale Challenge-Freigabe verlangt bestätigte Startaufstellungen.

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
  sowohl aus dem Tennis-Wettfinder als auch aus dem Wett-Check.
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
- Tennis zeigt Modell- und de-viggten N1Bet-Brier auf derselben Stichprobe
  startzeitnaher Referenzquoten; ROI allein ist kein Freigabekriterium.
- Die KIMI-Bedingung verwendet jetzt direkt den kanonischen Projektcode und
  dieselben Zeitfenster wie der Runner.
- E-Sport verlangt ein explizites 0:0-Prematch-Ereignis und eine eindeutige
  Teamzuordnung.
- Offene E-Sport-Zeilen werden fair rotiert; ein temporär fehlendes Ergebnis
  wird nicht automatisch als Void entsorgt.
- E-Sport-Freigabe verlangt mindestens 100 saubere Settlements, begrenzte
  Kalibrierungsabweichung und akzeptablen risikoadjustierten Brier Score.
- Rotkarten-Signale prüfen endliche, normierte 1X2-Wahrscheinlichkeiten,
  exakt einen Platzverweis und nachvollziehbare Ereignisreihenfolge.
- Pro Rotkarten-Fixture wird nur ein unabhängiger Snapshot für die
  Evidenzstatistik gewertet.

### UX

- Auf schmalen Smartphones sind alle acht Bereiche direkt in zwei Reihen
  erreichbar; es gibt kein verstecktes Untermenü.
- Auf breiteren Smartphones stehen alle acht Ziele in einer Reihe.
- Der aktive Bereich bleibt sichtbar.
- Material-Icons ersetzen uneinheitliche Emoji-Navigation.
- Genügend Bottom-Padding verhindert die Überlagerung des Inhalts.
- Multi-Sport beginnt mit der Sportart und zeigt danach nur den zugehörigen
  Liga-/Spiel-Filter.
- Leerstaat-Beispiele sind sportabhängig. Basketball zeigt keine
  Fußball-BTTS-Wette mehr.
- Externe Team- und Markttexte werden im HTML-Beispiel escaped.

## 4. Arbeitsbereiche und Freigabestatus

| Bereich | Zweck | Aktueller Status |
|---|---|---|
| Spiele | BTTS-Prematch-Wettfinder | strikt; Quote erst nach Modellprüfung |
| Märkte | Tore, Ecken, Karten und kombinierte Märkte | marktweise Walk-forward-Gates; kein Gate, keine Wette |
| Live | BTTS, Resttor, Teamtor | Datenfinder aktiv; Wettempfehlung bis Live-Kalibrierung blockiert |
| Wett-Check | N1Bet-Preis- und EV-Entscheid | nur konditional auf freigegebene Modellwahrscheinlichkeit |
| System | Daten, Training, API-Status | administrativ; keine Wettfreigabe |
| 15K Challenge | bis zu drei Legs, Zielquote 2,00-3,00 | Ledger korrekt; weiterhin sehr hohes Risiko |
| Multi-Sport | Basketball, NHL, Cricket, Tennis, E-Sport | nicht validierte Kerne bleiben fail-closed |
| Tennis | ATP/WTA und Tennis-Shadow | anspruchsvolle Pipeline; Live-Evidenz noch nicht abgerechnet |

Konkrete Blockaden:

- Basketball braucht unabhängige OOS- und Closing-Line-Evidenz.
- NHL braucht zusätzlich belastbare Goalie- und Lineup-Evidenz.
- E-Sport bleibt bis zum Shadow-Release-Gate verborgen.
- Cricket besitzt noch keinen freigegebenen Modellkern.
- Rotkarten-Live bleibt bis zu unabhängiger Shadow-Evidenz blockiert.

## 5. Architektur

| Datei | Verantwortung |
|---|---|
| `app.py` | Streamlit-Einstieg, Navigation und Scanner-Orchestrierung |
| `config_loader.py` | INI, Umgebung und Streamlit-Secrets |
| `league_catalog.py` | kanonischer 51-Ligen-Katalog |
| `advanced_analyzer.py` | BTTS-Analyse und Modellensemble |
| `challenge_engine.py` | Märkte, Validierung, Kontext und Ticketlogik |
| `football_recommendations.py` | gemeinsame Freigabepolicy |
| `bet_finder_ui.py` | N1Bet-Preisentscheidung |
| `scan_jobs.py` | sitzungsgebundene Hintergrundjobs |
| `challenge_15k.py` | Challenge-Workflow und UI |
| `challenge_store.py` | Challenge-Ledger und Transaktionen |
| `shadow_clv_automation.py` | Fußball-Shadow, Closing und Settlement |
| `clv_tracker.py` | versionsmarkierter CLV-Ledger |
| `tennis/*` | Tennis-Modell, Kalibrierung und Shadow |
| `esports_shadow.py` | E-Sport-Evidenz und Release-Status |
| `redcard_signal_log.py` | Rotkarten-Shadow und Settlement |
| `multi_sport_recommendations.py` | Basketball-, NHL- und E-Sport-Kandidaten |

Die lokale Prozessisolation ist verbessert, ersetzt aber noch keine echte
Produktionsarchitektur. Ohne Login existiert keine stabile Benutzer-ID. Ein
neuer Browser- oder Cloud-Prozess kann deshalb eine neue Challenge-Sitzung
beginnen. Dauerhafte, geräteübergreifende Konten benötigen weiterhin eine
gültige PostgreSQL-Verbindung und Authentifizierung.

## 6. Wettmathematik

Verbindliche Grundformeln:

```text
Break-even-Wahrscheinlichkeit = 1 / Quote
Erwartungswert beziehungsweise ROI = p * Quote - 1
Probability Edge = p - 1 / Quote
Full Kelly = ((Quote - 1) * p - (1 - p)) / (Quote - 1)
```

Probability Edge und erwartete Rendite sind verschiedene Einheiten. Kelly ist
nur so gut wie die kalibrierte Wahrscheinlichkeit. Bei unsicherem `p` wird mit
einer konservativen Wahrscheinlichkeit und einem Kelly-Cap gerechnet.

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

Der Einsatzregler ist deshalb eine Risikowahl, keine Optimierung. 100 % Einsatz
kann das Konto mit einer Niederlage auf null setzen. Die App darf das Ziel
visualisieren, aber niemals als realistische oder sichere Challenge verkaufen.

## 7. Shadow- und Evidenzstand

Lokaler Snapshot nach dem Audit:

| Bereich | Stand | Fachliche Aussage |
|---|---|---|
| Fußball CLV | 250 Fixtures, 230 bewertet, 0 Picks | kein CLV-/ROI-Urteil möglich |
| Tennis | 64 Predictions, 0 abgerechnet, 0 Empfehlungen | keine Live-Evidenz |
| Tennis Entwicklungsnachlauf | 909 ATP-Hard-Wetten, +8,2 % ROI, Bootstrap 95 % −2,3 bis +19,2 % | Hypothese; Intervall enthält null, kein später Holdout |
| E-Sport | 20 sauber klassifizierte Zeilen, 5 abgerechnet, 4 Treffer | n=5 ist bedeutungslos; Release bleibt gesperrt |
| E-Sport risikoadjustiert | Ø p 38,9 %, Brier 0,3711 | aktuelles Release-Gate klar nicht erfüllt |
| Rotkarten-Live | 0 unabhängige Shadow-Signale | keine Freigabe |
| Rotkarten-Historie | 1.132 Fälle | Entwicklungsdaten, kein unabhängiger Holdout |
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

Eine Freigabe darf frühestens nach mindestens 100 unabhängigen, vorab
protokollierten und korrekt abgerechneten Picks diskutiert werden. Zusätzlich
müssen Kalibrierung, Brier/Log Loss gegen einen No-Vig-Benchmark, positiver CLV
und Unsicherheitsintervalle überzeugen. ROI allein reicht nicht.

## 8. Automationen

| Automation | Status nach Bereinigung |
|---|---|
| Windows `BetBoy Tennis Daily`, 07:17 | aktiv, aktueller Projektpfad |
| KIMI Tennis Daily, ebenfalls 07:17 | deaktiviert, um Doppelverarbeitung zu verhindern |
| KIMI Fußball CLV, Bedingung alle 10 Minuten | aktiv; feuert nur bei fälliger Arbeit |
| KIMI wöchentlicher CLV-Bericht | aktiv; aktueller Pfad, Versionen getrennt |
| KIMI Statistik-Backfill | deaktiviert; `.backfill_complete` vorhanden |
| KIMI First-Pick-Watcher | deaktiviert; reines Monitoring ohne Wettfinder-Nutzen |
| KIMI E-Sport Shadow | aktiv, aktueller Projektpfad |
| KIMI Rotkarten-Harvest | aktiv, aktueller Projektpfad |

Der CLV-Runner und seine Bedingung verwenden nun beide
`betboy-app\shadow_clv_automation.py`. Der Standard umfasst alle 51 Ligen und
höchstens 60 fällige Fixtures pro Lauf. Die alte Asset-Kopie in KIMIs
Automation-Verzeichnis ist nicht mehr Ausführungsquelle.

Es fehlt weiterhin ein zentraler API-Budgetmanager über Streamlit, KIMI und
Windows. Das Pro-Limit von API-Football muss deshalb betrieblich beobachtet
werden, ohne daraus ein Nutzer-Monitoringprodukt zu machen.

## 9. API- und Datenstand

API-Football war beim Audit als Pro-Abo aktiv:

| Merkmal | Stand |
|---|---|
| Plan | Pro |
| Laufzeit laut Providerprüfung | bis 19. Oktober 2026 |
| Tageslimit | 7.500 Requests |

API-Football ist die zentrale Quelle für Fixtures, Ergebnisse, Live-Daten,
Kontext, Statistiken und Referenzquoten. Das Abo liefert Datenqualität und
Abdeckung, aber keinen garantierten Wettvorteil.

Ein separater football-data.org-Schlüssel ist im aktuellen Produktionspfad
nicht nötig. Historische CSV-Daten kommen überwiegend von
football-data.co.uk. Ein zweites Abo sollte erst aktiviert werden, wenn eine
konkrete fehlende Datenart und ein messbarer Nutzen feststehen.

Die Cloud meldete zuletzt einen lokalen Datenbankersatz, weil der alte
Supabase-Pooler-Zugang ungültig war. Der Code fällt funktionsfähig lokal zurück,
aber echte Persistenz, Konten und geräteübergreifende Challenge-Stände sind
damit nicht gelöst.

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

## 11. Test- und UX-Nachweis

Vollständiger Lauf:

```text
487 passed
5 subtests passed
```

Reproduzierbarer Windows-Befehl:

```powershell
New-Item -ItemType Directory -Path .pytest_tmp -Force
.\.codex_test_venv\Scripts\python.exe -m pytest -q `
  -p no:cacheprovider --basetemp .pytest_tmp\full
```

Edge wurde direkt per Playwright mit der installierten normalen Edge-Engine
getestet, nicht über den Codex-In-App-Browser:

| Viewport | Ergebnis |
|---|---|
| 390 x 844 | kein horizontaler Seitenüberlauf; zwei Reihen mit 4 Touch-Zielen |
| 820 x 1180 | Sidebar und Hauptinhalt ohne Überlauf; Bottom-Navigation korrekt verborgen |

Zusätzlich verifiziert:

- 15K zeigt bei 100 Euro Startguthaben standardmäßig 25 Euro Einsatz.
- Alle acht Arbeitsbereiche bleiben direkt erreichbar.
- Multi-Sport zeigt Sportart und danach Liga.
- Basketball zeigt ein Basketball-Beispiel.
- Keine sichtbaren Button- oder Label-Überläufe in den geprüften Ansichten.

## 12. Offene Prioritäten

### P0 - extern und vor ernsthafter Echtgeldnutzung

1. Alle historisch exponierten Secrets rotieren.
2. Gültiges dauerhaftes PostgreSQL/Supabase-Projekt anbinden.
3. Authentifizierung und stabile `user_id` für Konten und Ledger einführen.
4. N1Bet-Regeln für Void, Verlängerung, Early Payout und Marktlinien
   schriftlich gegen die Settlement-Implementierung prüfen.

### P1 - Evidenz

1. Die eingefrorene Shadow-Policy über die beginnenden Ligen laufen lassen.
2. Dropout-Funnel nach Modell-, Kontext- und Preisgrund versionsweise
   auswerten.
3. Keine Schwelle auf demselben Zeitraum wählen und beweisen.
4. Erst nach ausreichender Stichprobe CLV, Kalibrierung und No-Vig-Benchmark
   beurteilen.

### P2 - Betrieb

1. API-Budget zentralisieren.
2. Cloud-Persistenz und Neustartverhalten testen.
3. Nach jedem Push die echte Streamlit-App auf Commitstand und Mobilansicht
   prüfen.

## 13. Betrieb und Übergabe

Lokale App:

```powershell
.\.codex_test_venv\Scripts\python.exe -m streamlit run app.py
```

Vor einem Commit:

```powershell
git status --short
git diff --check
```

Die ungetrackte Datei `logs/pipeline_2026-07-31.log` ist bestehender Laufoutput
und darf nicht committed oder gelöscht werden.

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
