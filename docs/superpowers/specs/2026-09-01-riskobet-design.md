# RisikoBet – freigegebene Produktspezifikation

Stand: 02.09.2026
Status: Design 1–4 freigegeben, einschließlich ausdrücklicher Freigabe von Design 4; Design 1–5 implementiert, getestet und produktiv ausgerollt

## Problemstellung

Der normale Wettfinder priorisiert belastbare, eher wahrscheinliche Modellprognosen. Dadurch gehen fachlich interessante Überraschungsszenarien verloren, etwa ein Außenseitersieg, ein Remis, ein Satzgewinn oder ein Außenseitertor. RisikoBet soll diese Szenarien für Fußball, Tennis, Basketball, Eishockey, Cricket und E-Sport sichtbar machen, ohne Buchmacherquoten in die Prognose oder Sortierung einzurechnen und ohne bei fehlenden Daten Wahrscheinlichkeiten zu erfinden.

## Ziele

- Jedes Event wird pro eindeutiger Eingaberevision nur einmal geladen und modelliert; Wettfinder, 15K und RisikoBet leiten ihre Auswahlen aus demselben unveränderlichen Modellstand ab.
- RisikoBet zeigt nachvollziehbare Überraschungsszenarien mit Pro, Contra, Datenfrische, Evidenzstufe und getrenntem Preisstatus.
- Fehlende, zu niedrige, dünne oder veraltete Quoten sperren, verstecken oder sortieren keine Prognose.
- Alle sechs Sportarten besitzen einen eigenen Adapter. Fehlen Kerndaten, zeigt der Adapter den konkreten Forschungsbedarf und keine erfundene Prozentzahl.
- Jede numerische Prognose kann prospektiv, versionsgebunden und ohne Ergebnis-Leakage gespeichert und abgerechnet werden.

## Nicht-Ziele

- RisikoBet ist keine Garantie, kein „sicherer Tipp“ und keine automatische Echtgeldfreigabe.
- `VALIDATED` bedeutet Modellreife in der jeweiligen Risiko-Auswahlregion, nicht automatisch positiven Wettwert.
- Unvalidierte Verletzungs-, Wetter-, Reise-, Lineup-, Goalie-, Toss-, Roster- oder Map-Veto-Effekte werden nicht als erfundene Prozentpunkte eingerechnet.
- Eine Quote bestimmt weder Außenseiteridentität noch Kandidatenreihenfolge.
- Mehrere Modellierungen desselben Events für verschiedene Tabs sind nicht zulässig.

## Nutzererlebnisse

- Als Nutzer möchte ich sofort erkennen, welches überraschende Ergebnis plausibel sein könnte und was dafür beziehungsweise dagegen spricht.
- Als Nutzer möchte ich auch Szenarien ohne verfügbare Quote sehen, weil die Quote nur den Preis und nicht den möglichen Spielausgang beschreibt.
- Als Nutzer möchte ich bei fehlenden Kerndaten exakt sehen, was fehlt, statt eine Fantasie-Wahrscheinlichkeit zu erhalten.
- Als Nutzer möchte ich zwischen allen sechs Sportarten filtern, ohne dadurch einen neuen Providerabruf oder eine neue Modellierung auszulösen.
- Als Nutzer möchte ich RisikoBet als eigene Hauptseite auf Desktop und Mobil öffnen.
- Als Administrator möchte ich jede Modellrevision, Datenquelle, Evidenzstufe und spätere Abrechnung nachvollziehen können.

## Design 1 – Architektur

- Fußball, Tennis, Basketball, Eishockey, Cricket und E-Sport besitzen je einen Modelladapter.
- Ein `EventModelSnapshot` wird pro `event_key + model_version + input_hash` genau einmal gespeichert.
- Fußball zweigt direkt nach der vollständigen Marktberechnung und vor den normalen 58-/55-Prozent-, Walk-forward- und Freigabeschwellen ab.
- Tennis und E-Sport verwenden ihre bereits persistierten Modellzustände; sie werden nicht ein zweites Mal vom RisikoBet-Tab geladen oder modelliert.
- Wettfinder-, 15K- und RisikoBet-Kandidaten werden getrennt gespeichert und ausgewertet.
- Eine neue Eingaberevision erzeugt einen neuen Snapshot und überschreibt niemals die frühere Vorhersage.

## Design 2 – Märkte und Auswahl

Geplante Marktgruppen:

- Fußball: Außenseitersieg, Unentschieden, Außenseiter verliert nicht, Außenseiter 1+ beziehungsweise 2+ Tore.
- Tennis: Außenseitersieg, mindestens ein Satz, +1,5 Sätze und über 2,5 Sätze.
- Basketball: Außenseitersieg; Plus-Handicap und Außenseiter-Teamtotal erst mit eigener Linien- und Settlementvalidierung.
- Eishockey: Sieg inklusive Verlängerung, Sieg/Remis nach 60 Minuten, +1,5 Puck-Line sowie 1+ beziehungsweise 2+ Tore nach eigener Marktvalidierung.
- Cricket: zunächst Außenseiter-Matchsieg; Innings- und Teamtotals erst nach eigener Validierung.
- E-Sport: Außenseitersieg und mindestens eine Map; Live-Comeback erst später.

Auswahlregeln:

- Maximal zwei Szenarien je Event.
- Gleiche einfache Märkte dürfen die Hauptkarten nicht dominieren.
- `1+ Tor`, `1+ Satz` oder `1+ Map` bleiben erlaubt, benötigen für eine Hauptkarte aber einen konkreten positiven Matchup-Faktor.
- Die Reihenfolge ist vollständig quotenfrei.
- Fehlt eine historische Überraschungsbasisrate, bleibt die Auswahl `RESEARCH` und wird hinter belegten Kandidaten geführt.
- `Alle` verwendet sportfaire Round-Robin-Komposition statt eines erfundenen sportübergreifenden Scores.

## Design 3 – Daten, Kontext und Fehlerbehandlung

Jeder Einflussfaktor speichert Quelle, Beobachtungszeit, Importzeit, Frischefrist, Abdeckung, historische Stichprobe und numerische Rolle (`MODEL` oder `DISPLAY_ONLY`).

- Fehlende einzelne Kontextfaktoren lassen eine berechenbare Prognose sichtbar und markieren den Kontext als teilweise offen.
- Widersprüchliche Faktoren werden nicht numerisch verwendet und ausdrücklich markiert.
- Der letzte nachweislich frische Stand darf bei einem Providerfehler mit Zeitstempel weiter angezeigt werden.
- Keine berechenbaren Kerndaten bedeuten `model_probability = null` und eine genaue Liste fehlender Daten.
- Harte Sperren gelten nur bei falscher oder mehrdeutiger Eventidentität, beschädigten Daten oder mathematisch nicht berechenbarer Eingabe.
- Eingabeschluss, Modellzeit und Startzeit sind zeitlich kausal; spätere Ergebnisse oder Quoten dürfen nie rückwirkend einfließen.

## Design 4 – Oberfläche

Navigation auf Desktop und Mobil:

1. Wettfinder
2. RisikoBet
3. Live
4. 15K
5. Meine Tipps

Die RisikoBet-Seite besitzt die Filter `Alle`, `Fußball`, `Tennis`, `Basketball`, `Eishockey`, `Cricket` und `E-Sport`. Filter verändern nur die Ansicht.

Jede Hauptkarte zeigt ohne Aufklappen:

- Sport, Wettbewerb, Startzeit, Begegnung, Markt und Auswahl;
- Modellwahrscheinlichkeit und vorsichtige Prognose oder ehrlich `offen`;
- Evidenzstufe und Kontextfrische;
- mindestens einen Pro- und Contra-Punkt;
- Preisstatus und gegebenenfalls beobachtete Quote als getrennte Information;
- genau eine optionale Detailstufe sowie eine optionale eigene Preisprüfung.

Zusätzliche Karten bleiben flach und zeigen ebenfalls Pro, Contra, Frische, Evidenz und Preis. Es gibt keine verschachtelten Ergebnis-Expander.

Responsive Vertrag:

- ab 1081 Pixel zwei Hauptkarten je Reihe;
- 761–1080 Pixel einspaltige Hauptkarten;
- bis 760 Pixel einspaltig mit mobiler Navigation;
- bis 430 Pixel fünf Navigationselemente weiterhin in einer Zeile;
- bis 360 Pixel Aktionen untereinander;
- kein horizontaler Überlauf bis 320 Pixel.

## Design 5 – Betrieb, Persistenz und Evidenz

### Ablauf

```text
Provider -> Sportadapter -> unveränderlicher EventModelSnapshot
                              |-> Wettfinder-Katalog
                              |-> 15K-Katalog
                              `-> RisikoBet-Katalog

Ergebnisquelle -> versionsgebundene Shadow-Abrechnung -> Evidenzregister
Quotenquelle   -> separates Preis-Overlay, niemals zurück ins Ranking
```

Der vorhandene Wettfinder-Timer bleibt Aggregator. Ein zusätzlicher öffentlicher Timer ist für Version 1 nicht erforderlich. Breite Discovery erfolgt höchstens einmal pro Zürcher Kalendertag; fällige Kontextrevisionen erzeugen neue Snapshots. Der RisikoBet-Tab führt selbst keine Provideraufrufe aus.

### Persistenz

- `runtime_state/riskobet.db`: Läufe, unveränderliche Snapshots, Kandidaten, Settlements und Evidenzübergänge.
- `runtime_state/riskobet_latest.json`: atomar publizierte, rein lesende Consumer-Ansicht.
- Eindeutigkeit: `event_key + model_version + input_hash` für Snapshots und `candidate_id + snapshot_id` für Kandidaten.
- Preisbeobachtungen bleiben getrennt und dürfen Kandidateninhalt, Evidenzstufe oder Reihenfolge nicht verändern.
- Runtime-Daten werden von der bestehenden Backup-Inventarisierung erfasst.

### Evidenzstufen

- `RESEARCH`: mathematisch berechenbarer, aber noch nicht ausreichend validierter Vertrag; bei fehlenden Kerndaten ohne Prozentzahl.
- `SHADOW`: deterministischer Settlementvertrag, prospektiv gespeicherte Auswahl und automatische Abrechnung.
- `VALIDATED`: ausschließlich nach eigener, versionsgleicher RisikoBet-Validierung.

Es gibt keine direkte Promotion von `RESEARCH` nach `VALIDATED`. Eine neue Modell- oder Policyversion beginnt erneut mindestens in `RESEARCH` beziehungsweise `SHADOW`. Quoten, Profit und CLV verändern die Evidenzstufe nicht.

Für `VALIDATED` sind mindestens erforderlich:

- kausales Walk-forward-Verfahren in der tatsächlichen Außenseiterregion;
- vorab festgelegte ausreichende Stichprobe;
- positiver gepaarter Brier-Loss-Vorteil mit HAC-Untergrenze über null;
- BH-FDR-korrigiertes `q <= 0,05` über alle geprüften Risikomärkte;
- ausreichende Tail-Kalibrierung, keine aktive Drift und keine unzulässige Settlementquote;
- mindestens zwei zeitlich getrennte Auswertungsblöcke, bei E-Sport mehrere Patchperioden.

### Settlement

- Pro Event/Markt zählt genau ein vorher festgelegter Snapshot als Validierungsbeobachtung.
- Fußball verwendet die bestehende Markt-Outcome-Semantik; AET/PEN werden marktgerecht getrennt.
- Tennis speichert Gewinner und Satzstand; Retirement/Walkover folgt einer versionierten Void-Regel.
- Basketball unterscheidet Matchsieg inklusive Overtime von regulären Märkten.
- Eishockey trennt inklusive Overtime und nach 60 Minuten.
- Cricket definiert Tie, No Result, DLS und Super Over vor dem Shadow-Start.
- E-Sport trennt Serie, Map, Forfeit und Cancellation.
- Providerlücken bleiben `OPEN/UNRESOLVED`; Zeitablauf allein erzeugt weder Gewinn, Verlust noch Void.

## P0-Anforderungen und Abnahmekriterien

- [x] RisikoBet ist eine eigene Hauptseite und auf Desktop/Mobil in identischer Reihenfolge erreichbar.
- [x] Der Orchestrator führt alle sechs fest definierten Sportadapter aus, sobald ihre Quelle fällig ist; der öffentliche Snapshot enthält nur unveränderliche Modellresultate und bereinigte Fehler. Fehlende Kerndaten erzeugen keine Wahrscheinlichkeit.
- [x] Fußball-Risiken zweigen vor den normalen Wettfinder-Gates aus dem gemeinsamen Modelllauf ab.
- [x] Pro Event werden höchstens zwei Szenarien veröffentlicht.
- [x] Quote fehlt/zu niedrig/veraltet verändert weder Sichtbarkeit noch Reihenfolge.
- [x] Research, Shadow und Validated werden nie vermischt.
- [x] Pro und Contra sowie Datenfrische sind ohne Aufklappen sichtbar.
- [x] Consumer-Fehlertexte enthalten keine internen Provider-, Liga-, Kandidaten- oder Gate-Diagnosen.
- [x] RisikoBet-Persistenz ist idempotent, revisionsfest und atomar lesbar.
- [x] Mindestens Fußball, Tennis und E-Sport besitzen prospektive Shadow- und Settlementpfade.
- [x] Basketball, Eishockey und Cricket besitzen echte Research-Adapter; sie geben nur mit ausreichenden historischen Kerndaten eine Prozentzahl aus.
- [x] Vollständige Python-, Syntax-, Diff-, Browser-, Backup- und Produktionsprüfungen bestehen.

## Produktionsabnahme 02.09.2026

- Implementierungsfolge: `a086adf`, `5d5fe51` und `765008c`; revisionsfeste Wiederholungsläufe: `049d079a8f15031dccab0285000dd549db1f2388`; HTTP/1.1-kompatibles Deployment: `7d6f0e8060534b3f4d420b3c556321c7f7d022c9`.
- Regression: 1.423 Tests bestanden, 8 erwartete Skips und 97 Untertests; alle 182 versionierten Python-Dateien kompiliert.
- Gerenderte Produktionsprüfung bei 1440, 1080, 768, 430, 390, 360 und 320 Pixeln: kein horizontaler Überlauf, keine Console-Fehler oder -Warnungen, sechs funktionsfähige Sportfilter mit exakten Anzahlen und fünfteilige Mobilnavigation.
- VPS-Funktionsabnahme für `7d6f0e8060534b3f4d420b3c556321c7f7d022c9`: interner und öffentlicher Healthcheck `ok`, sieben Timer aktiv und aktiviert, Backup mit 86 Datenbanken verifiziert. Spätere reine Dokumentationscommits ändern diese Funktionsbasis nicht, müssen aber weiterhin exakt gepusht und deployed werden.
- Frischer RisikoBet-Lauf: `PARTIAL` ausschließlich wegen der fehlenden Cricket-Quelle; 48 Snapshots, 62 Kandidaten und 47 Events. Veröffentlicht wurden Fußball (30), Tennis (31) und E-Sport (1); Basketball und Eishockey wurden vollständig geprüft, lieferten aber keine Szenarien.
- Für Cricket fehlen produktiv weiterhin `RAPIDAPI_KEY` beziehungsweise `CRICKET_API_KEY` samt gültigem Anbieterzugang. Der Adapter erfindet deshalb weder Wahrscheinlichkeit noch Kandidat. Diese externe Konfiguration bleibt erforderlich, ist aber keine Modell-, Qualitäts- oder Quotensperre.

## P1

- Historische Pre-Match-Modellstates für Basketball, Eishockey und Cricket weiter aufbauen und chronologisch validieren.
- Automatische, exakt gebundene Preisoverlays je unterstütztem Markt ergänzen.
- Eigene Adminansicht für Dropout, Datenfrische, Settlement und Evidenzpromotion.

## P2

- Live-Comeback-Märkte, Push-Benachrichtigungen und personalisierte Risikopräferenzen.
- Backend-API und native App nach Stabilisierung des Modellvertrags.

## Erfolgsmessung

Frühe Qualitätsmetriken:

- 100 Prozent der sichtbaren Karten besitzen stabile Event-/Kandidatenidentität und eine prüfbare Datenzeit.
- 0 Fälle, in denen Preisstatus Kandidatenreihenfolge oder Modellwahrscheinlichkeit verändert.
- 0 erfundene Wahrscheinlichkeiten bei fehlenden Kerndaten.
- 0 doppelte Modellierungen derselben Eingaberevision.
- 100 Prozent der Shadow-Kandidaten besitzen einen deterministischen Settlementvertrag.
- Kein horizontaler Überlauf bei 1440, 1080, 768, 430, 390, 360 und 320 Pixeln.

Langfristige Evidenzmetriken werden ausschließlich pro Sport, Marktfamilie, Modellversion und Policyversion ausgewertet; sportübergreifende Mischwerte sind unzulässig.
