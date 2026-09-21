# BetBoy: Produkt- und Codeaudit vom 21.09.2026

## Urteil

**Technisch erreichbar und aktuell deployed, fachlich noch nicht fertig.** Vier dringende Produkt-/Datenfehler und vier weitere offene Produktpunkte sind unten belegt. Die vorhandenen Grundmodelle rechnen tatsächlich; daraus folgt weder, dass Verletzungen und Belastung bereits wirksam eingerechnet werden, noch ein nachgewiesener Wettvorteil.

Geprüfter Commit: `1e2c6f5c19b8ba32d8a970c622109e049f8c4060`. Arbeitskopie, GitHub `main` und `/opt/betboy/app` auf dem VPS stimmen überein. Die Befunde sind deshalb nicht durch einen fehlenden Pull erklärt.

Auditzeit: 21.09.2026, ungefähr 09:30–10:10 Uhr Europe/Zurich. Laufende automatische Jobs können Datenstände während der Prüfung verändern. Cricket bleibt gemäß Auftrag ausgenommen.

## Befunde nach Priorität

### F01 — P1: 15K zeigt weiterhin gegensätzliche Auswahlen desselben Spiels

**Live reproduziert:** Unter „15K → Auswahlen und Quoten → Weitere 21 Modellprognosen“ erscheinen für Petrolul Ploiesti gegen Csikszereda unter anderem:

- Endergebnis Heimsieg und Endergebnis Auswärtssieg;
- Team 2 über 1,5 und Team 2 unter 1,5;
- Team 1 über 1,5 und Team 1 unter 1,5.

Für Manta gegen Orense stehen ein hervorgehobener Heimsieg und zusätzlich X2 im selben Katalog. Es handelt sich ausdrücklich um als Modell-Auswahlen bezeichnete Einträge, nicht um bereits gebuchte oder freigegebene Echtgeldtickets. Trotzdem widerspricht ihre gemeinsame nummerierte Präsentation der geforderten konsistenten Auswahl.

**Ursache:** `challenge_15k.py:4540` vereinigt den Katalog, `:4594` verteilt Haupt-/Zusatzkarten, `:4636` rendert alle verbleibenden Reihen. Der Kohärenzfilter wird dort nicht angewendet. `bet_finder_ui.py:366–385` enthält ihn zwar, dokumentiert in Zeile 374 aber ausdrücklich die Ausnahme für den alten 15K-Pfad.

**Abnahme einer Reparatur:** Dieselbe Kohärenzregel muss vor jeder Aufteilung und Paginierung aller konsumierenden Ansichten greifen. Eine reine Modellverteilung darf intern sämtliche Gegenereignisse enthalten, aber nicht wieder als widersprüchliche Vorschlagsliste erscheinen. Regression mit denselben Ereignissen über Wettfinder, Daily3 und 15K; RisikoBet-Szenarien müssen eindeutig als alternative Risikoszenarien statt gleichzeitige Empfehlungen geführt werden.

### F02 — P1: Die versprochene Verletzungs-/Belastungswirkung ist produktiv nicht aktiviert

**Live-Nachweis:** In `runtime_state/context_models.db` existiert kein Artefakt der Typen `context-effect-v1` oder `context-approval-v1`. Die jüngsten 100 gespeicherten Kontext-Snapshot-Header haben sämtlich `result.role = not_applied`, keinen Effekt-Hash und keinen Freigabe-Hash. Gelesen wurden vollständige gespeicherte Header, nicht die expandierten historischen Verweislisten; dies war keine vollständige Integritätsprüfung der ganzen Datenbank.

Die vorhandenen Artefakte betreffen Fußball-Originalberechnungen und Tennis-Grundmodelle/Tourzustände. Fußball- und Tennis-Effektbausteine und ihre Tests existieren im Code, sind damit aber noch keine laufende, qualifizierte Wirkung auf Nutzerprognosen.

**Code:** `context_models/activation.py:87–108` verlangt die konkrete aktive Freigabe; ohne sie gibt es keinen aktivierten Effekt. `context_snapshots.py:405–422` verwendet dann die ursprüngliche Basisverteilung und keine veränderte Marktverteilung. In der Live-Ansicht erscheinen entsprechend Hinweise wie „Kader-/Belastungseffekte nicht belegt“.

**Abnahme:** Zeitlich korrekt erfasste Spieler-/Belastungsdaten, echte Ergebniszuordnung, getrennte Trainings-/Prüfpopulation, gemessener Vergleich zum unveränderten Grundmodell und erst danach eine belegte Aktivierung. Live für dasselbe Spiel Basisparameter, angepasste Parameter und daraus konsistent neu berechnete Märkte nachweisen. Nicht die Freigabeprüfung entfernen oder willkürliche Abschläge als trainierten Effekt ausgeben.

### F03 — P1: Neue E-Sport-Spiele verdrängen alte Spiele dauerhaft aus der Ergebnisprüfung

**Live-Nachweis:** `esports_shadow.db` enthält 513 offene und 138 abgerechnete Datensätze. Die jüngste native Abrechnung stammt vom 01.09.2026, obwohl der Dienst am 21.09. erfolgreich lief. Bereits am 07.09. begonnene Beispielspiele wurden jeweils nur einmal vor Spielbeginn geprüft. Bei der Gegenprüfung der aktuell fälligen E-Sport-Nachweise waren 135 Quellen noch unabgerechnet.

**Ursache:** `esports_shadow.py:39` begrenzt den Lauf auf 15 Ergebnisabfragen. Die Abfrage in `:228–244` priorisiert noch nie geprüfte Datensätze, ohne zuerst künftige Spiele auszuschließen. `run_shadow_scan()` in `:501–515` fügt neue Spiele vor der Abrechnung hinzu. Der reguläre Dienst läuft laut `deploy/systemd/betboy-esports.timer:5` einmal täglich.

**Unabhängige lokale Reproduktion:** Ein alter Datensatz mit einem gültig lieferbaren 2:0-Endergebnis, davor bereits einmal geprüft; in drei aufeinanderfolgenden Läufen jeweils 15 neue künftige Spiele. Jeder Lauf fragt ausschließlich die 15 neuen Spiele ab. Der alte Datensatz wird nie beim Ergebnislieferanten angefordert, bleibt offen und bei genau einem Prüfversuch. Es wurden hierfür ausschließlich temporäre lokale Testdaten und ein deterministischer Ersatzlieferant benutzt, keine bezahlten API-Abfragen.

**Abnahme:** Terminabhängig fällige Abrechnungswarteschlange mit garantierter fairer Wiederprüfung, getrennt vom Einsammeln neuer Spiele. Ein historischer Rückstand muss mit begrenztem API-Budget nachweislich sinken. Providerfehler und „noch nicht beendet“ getrennt zählen. Ein grüner Prozess-Exit reicht nicht als fachlicher Erfolgsnachweis.

### F04 — P1: Fehlende Verletzungsdaten werden in 15K als „0/0“ ausgegeben

**Live-Nachweis:** Für Manta FC gegen Orense SC zeigt 15K „Ausfälle H/A 0/0“. Der tatsächlich zugrunde liegende Datensatz enthält jedoch `availability=not_covered`, `coverage_available=false`, `status=unavailable` und die Begründung „Verletzungsdaten werden für diese Liga nicht abgedeckt“. Das bedeutet unbekannt, nicht null Verletzte.

**Ursache:** `challenge_15k.py:4317–4338` liest fehlende Werte mit `injuries.get('home_missing', 0)` beziehungsweise `away_missing` als Null aus und ignoriert den Verfügbarkeitsstatus.

**Abnahme:** Unbekannt, nicht abgedeckt, veraltet, bestätigte Null und bestätigte Ausfälle sichtbar unterscheiden. Nur tatsächlich belegte Zahlen zeigen; identisches Ereignis muss in allen Ansichten dieselbe Aussage erhalten. Negativtest mit dem oben genannten echten Status.

### F05 — P2: Daily3 priorisiert Formabweichung statt des vereinbarten defensiven Ziels

**Code/Reproduktion:** `daily3_selection.py:106–110` sortiert zuerst nach dem Abstand zum Saison-Grundmodell, erst später nach der niedrigsten Wahrscheinlichkeit der verglichenen Modelle. Zwei gültige Auswahlen desselben Markttyps und mit gleichwertiger Aktualität ergeben folgende Reihenfolge:

| Aktives Modell | Saisonmodell | Formmodell | Formabstand | Ergebnis |
| --- | --- | --- | --- | --- |
| 74 % | 70 % | 74 % | 4 Prozentpunkte | zuerst |
| 88 % | 85 % | 88 % | 3 Prozentpunkte | danach |

Beide erfüllen die aktuellen Bedingungen. Verwendet wurden `tests/test_daily3_selection.py::football` und `daily3_choices`, nicht eine nachgebaute Sortierung. Das belegt die Priorität im Algorithmus, **nicht**, dass eine reale 88-%-Schätzung empirisch sicherer wäre.

Zudem delegiert `daily3_comparison.py:195–196` ausschließlich an den Fußballvergleich. Dieser lehnt in `:170–171` jede andere Sportart ab. Daily3 ist dadurch trotz des gemeinsamen Mehrsport-Pools faktisch auf Fußball beschränkt. Die Detailhilfe weist darauf hin; eine sportübergreifend fertige Auswahl ist es nicht.

**Abnahme:** Zuerst belastbar begründete, nicht bloß offensichtliche Kandidaten ermitteln; innerhalb dieser Menge das genehmigte defensive Ziel explizit priorisieren. Relevanz/Formabweichung und modelliertes Verlustrisiko getrennt behandeln. Keinen garantierten Tagesgewinn oder drei erzwungene Plätze konstruieren. Weitere Sportarten benötigen eigene belastbare Vergleichsadapter, keine erfundene einheitliche 50-%-Basis.

### F06 — P2: Verschobene Fußballspiele haben keinen vollständigen Ergebnis-Abgleich

**Code:** `forecast_evidence_settlement.py:205–217` nimmt Spiele mit mehreren gespeicherten Anstoßzeiten aus der Abfrage und belässt sie bei `schedule_revision_unresolved`. Auch ein geliefertes Endergebnis mit verschobenem Anstoß wird nicht automatisch zugeordnet. Der aktuelle Lauf meldet diesen Zustand weiterhin.

**Bestehende Tests bestätigen die Lücke:** `tests/test_forecast_evidence_settlement.py:135–158` erwartet auch für ein bereits beendetes Spiel mit verändertem Termin in zwei Läufen null Ergebnisse. `:202–216` erwartet bei mehreren gespeicherten Terminen sogar gar keinen Provideraufruf.

Das vorsichtige Nicht-Abrechnen bei ungeklärter Identität ist richtig; der Fehler ist der fehlende anschließende Auflösungspfad. Der alte Fehlalarm wurde entschärft, nicht jede Terminverschiebung fachlich abgewickelt.

**Abnahme:** Verifizierte Terminänderung mit gleicher Spiel-/Teilnehmeridentität nachvollziehbar zuordnen und echte Endergebnisse anschließend genau einmal erfassen. Fremde Teilnehmer, wiederverwendete IDs und noch nicht beendete Spiele müssen weiter abgelehnt werden.

### F07 — P2: Der Ergebnis- und Preisnachweis reicht nicht für die behauptete fertige Wettqualität

Frisch gelesener Bestand der gemeinsamen Prognosenachweise:

| Sport | Gespeicherte Prognosezeilen | Unterschiedliche Ereignisse | Ereignisse mit zugeordnetem Ergebnis |
| --- | ---: | ---: | ---: |
| Fußball | 81.263 | 333 | 327 |
| Tennis | 278 | 11 | 4 |
| E-Sport | 1.466 | 141 | 0 |

Die vielen Zeilen sind Wiederholungen, Revisionen und unterschiedliche Märkte, keine entsprechend große Zahl unabhängiger Spiele. Basketball/Eishockey sind in diesem Nachweisbestand nicht enthalten; daraus allein folgt nicht, dass heute zwingend ein Angebot fehlen muss.

Der vorhandene Qualitätsreport (`forecast_evidence.py:424–490`) liefert über seine Markt-/Modell-/Policy-Gruppen vier auswertbare Tennisfälle und keine auswertbaren E-Sport-Fälle. Für Fußball ergeben sich zusammen nur 19 hypothetische Fälle mit ausführbarer Einstiegsquote; kein Sport liefert in diesem Report ein Closing-Quote-Vergleichspaar. Diese Gruppensummen sind nicht als voneinander unabhängige Wetten oder Echtgeldgewinne interpretierbar.

**Abnahme:** Ergebnisvollständigkeit pro Sport, unveränderte zeitliche Trennung, Kalibrierung und Güte gegen ein Grundmodell, sowie ausreichend viele tatsächlich passende Quoten getrennt ausweisen. Softwaretests und rohe Trefferquoten über gemischte Gegenmärkte sind kein Beleg für einen Wettvorteil. Eine bestimmte notwendige Stichprobengröße muss zur vorab festgelegten Prüffrage passen; hier wird keine willkürliche Grenze erfunden.

### F08 — P2: Kompakte UX und verständliche Begründungen sind nicht überall umgesetzt

Der normale Wettfinder gruppiert Spiele inzwischen auf-/zuklappbar und zeigt kompakte Fakten. RisikoBet und 15K verwenden aber weiterhin abweichende Darstellungen:

- `riskobet_ui.py:430–439` hängt bis zu vier ausführliche Kontextbeschreibungen außerhalb des Detailbereichs an jede Karte. Live sind lange Satz-/Pausenbeschreibungen und wiederholte Spielernamen sichtbar.
- Beispielsweise wiederholt `riskobet_candidates.py:1268` als Pro hauptsächlich die Modellwahrscheinlichkeit. Das erklärt noch nicht den konkreten Vorteil gegenüber dem Gegner.
- 15K stellt Zusatzkarten fortlaufend statt je Spiel gruppiert dar. Der Kopf behauptet „vollständig 15K-validiert“ (`challenge_15k.py:4910`), obwohl daneben unvollständige Kontextdaten und lediglich modellierte Katalogeinträge stehen. Der Hinweis in `:4619–4620` erweckt zusätzlich den Eindruck, nur noch eine Quote fehle.

**Abnahme:** Gemeinsame Darstellung von Datenzuständen; ein bis zwei belegte sportliche Gründe direkt sichtbar, Kontextdetails klickbar; Spielgruppen statt endloser Einzelkarten. Preisstatus, Modellauswertung und tatsächliche fachliche Freigabe dürfen sprachlich nicht vermischt werden.

## Was aktuell funktioniert — und was damit nicht bewiesen ist

- Der laufende Stand ist überall `1e2c6f5`. `betboy-app.service` und Caddy sind aktiv, der interne Healthcheck liefert `ok`; die öffentliche Oberfläche war im separaten Browser erreichbar.
- Dateisystem: ungefähr 21 GB frei von 38 GB. Kein aktueller Speichermangel. Die größte Laufzeitdatenbank bleibt mit rund 2,90 GiB groß; eine langfristig begrenzte Wachstumsrate lässt sich aus einem Einzelzeitpunkt nicht bestätigen.
- Sieben Timer sind aktiv. Ein laufender One-shot kann im Timer vorübergehend `NEXT=-` zeigen; das ist alleine kein neuer Timerfehler. Der Wettfinderlauf 09:07–09:27 war erfolgreich, der Folgelauf ab 09:37 war beim abschließenden Check noch aktiv.
- Der letzte vollständige Tennislauf 07:17–07:53 endete mit Fehler, **vor** dem zuletzt veröffentlichten Retirement-Fix. Danach gab es in diesem Audit keinen neuen vollständigen Tageslauf. Daher weder „Fix fehlgeschlagen“ noch „vollständig grün“ behaupten. Historische fehlgeschlagene Deployment-Units sind von der aktiven App zu unterscheiden.
- 47 lokale Module für Auswahl, Preisprüfung, Daily3/15K, Abrechnung und UI: **1.564 Tests und 85 Untertests bestanden** in 68,02 Sekunden.
- 17 zusätzliche Module für Aktivierung, Auswertung, Kontext-/Sportmathematik und E-Sport-Abrechnung: **951 Tests bestanden** in 427,57 Sekunden.
- Zusammen in diesem Audit: **2.515 Tests und 85 Untertests**, nicht die komplette Repository-Suite. Die neuen Gegenbeispiele wurden zusätzlich unabhängig von den bestehenden Erfolgstests ausgeführt.
- Die mathematischen Bausteine sind real: etwa gemeinsames Torverteilungsmodell, Tenniswahrscheinlichkeiten und begrenzte Geldrechnung in CHF-Cents. In den geprüften Tests kein neuer Rechenfehler bei CHF-50-Budget, Reservierungen und Auszahlung gefunden. Es wurden keine echten Wetten erfasst oder abgerechnet.
- Die Preisuntergrenze 1,20 und fehlende Quoten werden im geprüften normalen Auswahlpfad getrennt behandelt. Kein pauschales Wettartenverbot als Reparatur vorgeschlagen.
- Browser: Wettfinder, Daily3, RisikoBet, Live-Einstieg, 15K und Meine Tipps geladen; keine Console-Errors. Neun Browserwarnungen betrafen Iframe-/Feature-Hinweise, kein dadurch nachgewiesener Angriff. Kein horizontaler Überlauf bei den geprüften mobilen Ansichten (RisikoBet 390 px, Wettfinder/Live 320 px). Das ist kein vollständiger Accessibility- oder Geräte-Audit.

## Warum die bisherigen grünen Tests das nicht verhindert haben

1. Die 15K-Ausnahme ist im Code bewusst beibehalten; ein erfolgreicher Kohärenztest des normalen Wettfinders prüft diese zweite Darstellung nicht automatisch mit.
2. Einzelne erfolgreiche Abrechnungen prüfen keine Warteschlange, in die jeden Tag neue noch nicht fällige Spiele gelangen. Der mehrtägige Gegenversuch zeigt den Unterschied.
3. Kontext-Tests belegen gültige Rechen- und Freigabeverträge mit Testartefakten. Sie belegen keine tatsächlich trainierte und aktive Produktionsversion.
4. Einige Tests sichern ausdrücklich den Zwischenzustand „bei Terminverschiebung offen lassen“ ab. Ohne nachfolgenden End-to-End-Fall für eine verifizierte Verschiebung bleibt der fachliche Ablauf unvollständig.
5. Die defensive Produktpriorität und die Bedeutung von unbekannten Daten müssen als gemeinsame, ansichtenübergreifende Abnahmekriterien geprüft werden, nicht nur als einzelne Formatierungs- oder Grenzwerttests.

## Reparaturreihenfolge

1. F01/F04: Gegensätzliche 15K-Vorschläge und falsche Null-Ausfälle in allen Ansichten verhindern.
2. F03/F06: Ergebniswarteschlange und verifizierte Terminänderungen abschließen; historischen Rückstand kontrolliert nachholen.
3. F05: Daily3 nach der genehmigten defensiven Priorität ordnen und den tatsächlichen Sportumfang klar festlegen.
4. F02/F07: Kontextmodelle mit echten zeitlich korrekten Daten qualifizieren, Wirkung und Ergebnisqualität messen; erst belegte Effekte aktivieren.
5. F08: Gemeinsame kompakte Karten-/Begründungskomponenten durchziehen; Abnahme an gerenderten Beispielen aus allen Bereichen.

Keine pauschale Marktverbannung, kein blindes Erhöhen von API-Limits und kein Entfernen der fachlichen Integritätsprüfungen als Abkürzung.

## Auditspuren und Grenzen

- 15K mit geöffnetem Zusatzkatalog: `.playwright-cli/page-2026-09-21T07-50-10-148Z.yml`.
- Desktop-Wettfinder: `.playwright-cli/page-2026-09-21T07-35-43-123Z.png`.
- RisikoBet mobil: `.playwright-cli/page-2026-09-21T07-43-02-723Z.png`.
- Wettfinder 320 px: `output/playwright/audit-20260921-wettfinder-320.png`.
- SQLite-Prüfungen auf dem VPS verwendeten `mode=ro` und `query_only`. Es wurden keine neuen Sportdatenabfragen oder manuellen Scans angestoßen. Normale automatische Serverläufe blieben aktiv.
- Kein umfassender Penetrationstest, keine echte Buchmacher-Abgabe, keine Garantie sämtlicher Geräte/Ligen/Spielsituationen und kein erneut ausgeführter vollständiger Tennis-Tageslauf.
- Gespeichert wurden nur dieser Auditbericht und lokale Browser-Prüfartefakte. **Kein Produktivcode geändert, kein Commit, Push oder Deployment.** Vorhandene fremde/unversionierte Arbeitsdateien bleiben erhalten.
