# Wettfinder: widerspruchsfreie sichtbare Auswahl

Stand: 8. September 2026. Funktionaler Commit: `acc5d7200630c17ae23354226ef6857bbedae587`.

## Anlass und Ursache

Der Nutzer zeigte FC Porto gegen Manchester City mit Heimsieg und Auswärtssieg als zwei gleichartigen Auswahlkarten. Das war ein Fehler der Produktausgabe, nicht durch fehlende Quoten oder das Etikett „Modellprognose“ zu rechtfertigen. Die anschließende ausdrückliche Freigabe umfasst Korrektur, Regression, Commit/Push und VPS-Deployment.

Der Rohkatalog berechnete mehrere mögliche Marktausgänge desselben Spiels. Die Oberfläche begrenzte wiederholte Spiele aber nur innerhalb der drei Topkarten; alle übrigen Zeilen konnten in Zusatzkarten und auf weiteren Seiten erscheinen. Im manuellen Fußballpfad gab es dieselbe Lücke. Frühere Tests prüften Vollständigkeit und Top-Diversität, nicht die Widerspruchsfreiheit der gesamten sichtbaren Auswahlmenge. Damit war trotz grüner Tests eine entscheidende Produktanforderung ungeschützt.

Die originale Beobachtung stammt aus dem echten Snapshot vom 08.09.2026, 18:07:15 UTC, Fixture `1635654`: `RESULT_HOME=0.46361` und `RESULT_AWAY=0.211739`. Die Fußballprognosen waren nicht vollständig bestätigte Wettempfehlungen; diese Unterscheidung entschuldigt die widersprüchliche Darstellung nicht. Die Einzelwahrscheinlichkeiten werden mit diesem Fix nicht nachträglich umgerechnet.

## Geänderter Vertrag

- Eine vorhandene preisneutrale Primärauswahl wird je identifiziertem Ereignis verankert. Weitere sichtbare Auswahlen müssen mit der gesamten bereits behaltenen Menge gemeinsam möglich sein.
- Prüfung vor Top-/Zusatzaufteilung, Pagination, manuellem 25er-Limit und nachgelagerter Preisaufteilung.
- Die 90 bestehenden Fußballmarktdefinitionen bleiben jeweils einzeln zulässig. Keine Quote, Wahrscheinlichkeit, Mindestquote oder Wettartenbezeichnung entscheidet im neuen Kern, welche Richtung gewinnt.
- Der vollständige gespeicherte Modellpool, die Originalobjekte, Wahrscheinlichkeiten, Quoten und Preisentscheidungen bleiben unverändert. Nur die nutzerseitige Zusammenstellung wird kohärent.
- Verlässliche Ereignis- und Teilnehmer-IDs haben Vorrang vor veränderlichen Anzeigenamen. Vollständige UTC-Zeiten und exakte Aliasbindungen verhindern, dass eine schwach identifizierte Kopie als zweites Spiel am Schutz vorbeikommt. Unterschiedliche starke native IDs werden nicht per Namensähnlichkeit zusammengeführt.
- Unbekannte oder widersprüchliche Markt-/Teilnehmerbindungen rechtfertigen keine zusätzlichen Karten. Ein alleiniger primärer Eintrag wird dadurch nicht als statistisch validiert erklärt.
- Logische Vereinbarkeit ist keine Aussage über statistische Unabhängigkeit, gemeinsame Gewinnchance oder die Eignung als Kombiwette.

Der neue Kern `selection_coherence.py` verwendet die unveränderte `challenge_engine.market_outcome`-Semantik und den Schnitt der möglichen Ergebnisse, getrennt für Tore, Ecken und gelbe Karten. Die endlichen Repräsentanten erhalten alle vorhandenen Grenz-, Gleichheits- und Ergebnisbedingungen; sie schneiden keine Modellwahrscheinlichkeit ab. Das verhindert auch global unmögliche Dreiermengen, deren einzelne Paare noch vereinbar sind.

## Geprüfter Umfang

Funktional geändert wurden genau acht Source-/Testdateien. Ihre exakten SHA256 stehen im [unabhängigen Review](2026-09-08-widerspruchsfreie-auswahl-review.md). Root und Reviewer bestätigten diese acht Hashes vor und nach dem finalen Test-/Reviewlauf. Der Stage-Backuphelper blieb unverändert bei SHA256 `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Die Garantie dieser Änderung gilt für den normalen automatischen Wettfinder-Katalog einschließlich der dort vertretenen Sportarten und die manuelle Fußball-Mehrmarktauswahl. Die separate manuelle Tennis-Preisprüfung, RisikoBet, Live und 15K werden nicht als neu geprüft oder korrigiert ausgegeben. Insbesondere kann der bestehende separate Tennis-Preischeck eine andere Gewinnerseite als passende Quote benennen; das ist kein zweiter paralleler Modellkatalog und bleibt ein gesondert zu prüfender Produktpfad.

Keine Änderungen an Modellberechnung, Quotenabrufen, Jobs, Datenbanken, Tickets, Einsätzen oder Abrechnung. Der unfertige numerische Verletzungs-/Müdigkeitsausbau bleibt auf seinem eigenen Featurebranch. Cricket-Modell und Cricket-Datenanbindung sind unverändert.

## Regression und unabhängige Gegenprüfung

Root reproduzierte zuerst fünf fehlende Schutzfälle im Ausgangsstand als RED, später zusätzlich die Weitergabe stabiler Teilnehmer-IDs. Hinzu kamen RED-Gegenfälle aus dem Core- und manuellen Implementierungspfad. Vor dem Freeze gefundene Namensorientierungs- und schwache-ID-Lücken wurden geschlossen und erneut geprüft.

Finaler Root-Lauf auf den unveränderten freigegebenen acht Dateien:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -rs -p no:cacheprovider --basetemp=.pytest_tmp/coherence-full-01
```

**1.991 bestanden, 11 erwartete Windows-Skips, 97 Untertests bestanden; 67,47 Sekunden, Exit 0.** Die Skips betreffen Symlink-/POSIX-Nachweise in Backup-, Serverjob- und Tennis-Cache-Tests. Keine Erwartung gelockert, um diesen Fehler grün zu bekommen. Diese Zahl gehört zum Produktionsbranch; die größere separate Kontext-Suite enthält noch nicht ausgelieferten Code.

Weitere tatsächliche Nachweise:

- Root-Fokus: 31 Surface- und 13 manuelle Tests bestanden. Der manuelle Test ruft die tatsächliche Renderfunktion mit isolierten Abhängigkeiten auf, nicht nur einen unverbundenen Helper.
- Core-/Integrationslauf: 337 Tests bestanden. Ein vorheriger konkurrierender Collection-Lauf hatte einen temporären Windows-Dateisystemfehler; der vollständig wiederholte Lauf und der getrennte Root-Gesamtlauf waren grün.
- Unabhängiger Reviewer: 221 Tests bestanden; 90 Einzelmärkte, 8.100 geordnete Marktpaare, 400 vollständige unterschiedlich sortierte 90er-Pools und 13 Identitäts-/Gewinner-Gegenfälle geprüft. Ein Fehler im eigenen zusätzlichen Probehelper wurde transparent korrigiert; die vollständig erfolgreiche Wiederholung ist im Review dokumentiert.
- Originale Porto-Richtung in beiden öffentlichen Auswahlpfaden erhalten, Gegenauswahl entfernt; keine Umkehr durch eine bessere Quote. Derselbe Schutz gilt über drei Zusatzseiten.
- Globale Gegenfälle: alle drei Doppelchancen gemeinsam; `BTTS_NO` zusammen mit beiden Teams über 0,5; Gesamt über 2,5 zusammen mit Heim unter 0,5 und Auswärts unter 2,5.
- Lastprobe: 110.400 Eingaben und ebenso viele bevorzugte Anker in 2,395 Sekunden, identische Originalobjekte und Reihenfolge. Keine quadratische Suche je Ereignis.
- `git diff --check` sauber. Unabhängiger Abschluss: **APPROVED, keine offenen Findings im eingefrorenen Fix**.

## Gerenderte Oberfläche

Der Playwright-Skill wurde für die tatsächliche Browserprüfung verwendet. Die isolierte lokale Vorschau verwendet den echten App-Renderer und dessen CSS; nur der Daten-Snapshot ist ausdrücklich als synthetischer Prüfdatensatz gekennzeichnet. Kein Anbieterabruf, keine aktuellen Wettempfehlungen, keine Veränderung der Produktionsdaten.

31 absichtlich eingespeiste Beispielprognosen ergeben 29 sichtbare, logisch vereinbare Karten. Auf Seite 1 erscheinen drei Topkarten plus 20 Ergänzungen, auf Seite 2 drei Topkarten plus sechs Ergänzungen. In beiden Ansichten bleibt exakt eine Porto-Karte mit Heimsieg; Auswärtssieg und die gegensätzliche Doppelchance tauchen nicht als weitere Auswahl auf. Begründung und Gegenrisiko sind sofort sichtbar.

Nach erneutem Laden des endgültigen Source-Freeze bei 390 und 320 Pixeln geprüft; anschließend Desktop bei 1440 Pixeln und echter Seitenwechsel über die Selectbox. Kein horizontaler Überlauf, keine Console-Fehler. Die tatsächlich betrachteten Bilder liegen ungetrackt unter `output/playwright/selection-coherence/`, unter anderem `porto-390.png`, `porto-final-320.png` und `porto-final-1440.png`. Die mobile Illustration ist kein behaupteter erneuter Live-Nachweis des bereits gestarteten Porto-Spiels.

## Produktionsnachweis

Der funktionale Commit wurde per Fast-forward auf `main` übernommen und gegen `git ls-remote origin refs/heads/main` exakt bestätigt. Zielrepository: `https://github.com/xantharu123-png/btts-pro-analyzer.git`. Deployment ausschließlich über den vorhandenen root-eigenen `/usr/local/sbin/betboy-update`, nicht über ein Skript aus dem App-Checkout. Die sieben Timer rechnen Daten; sie pullen oder deployen keinen Code.

Der normale Updater beendete das funktionale Deployment erfolgreich auf `acc5d7200630c17ae23354226ef6857bbedae587`. Anschließend wurden dieser vollständige Hash und ein sauberer getrackter Checkout erneut lesend bestätigt. Alle acht Source-/Test-SHA256 und der unveränderte Stage-Helper stimmen auf dem VPS exakt mit den oben gebundenen Bytes überein. Anforderungen unverändert, kein pip-Lauf. Der erste Hashaufruf als Operator war nicht berechtigt; die Wiederholung mit dem vorgesehenen App-Lesekonto bestätigte alle Dateien, ohne Berechtigungen zu ändern.

Verifizierte Archive mit jeweils **87 Datenbanken**:

- `/var/backups/betboy-update/betboy-preupdate-20260908T205331Z-4f3ecd5db75c.zip`
- `/var/backups/betboy/betboy-sqlite-20260908T205411Z.zip`

`betboy-app.service` und Caddy sind aktiv und enabled. Interner und öffentlicher `/_stcore/health` liefern `ok`; alle sieben Timer sind aktiv/enabled und haben einen nächsten Termin. Die weiterhin als failed geführten `betboy-tennis.service` und `betboy-wettfinder.service` wurden weder zurückgesetzt noch als durch diesen Fix repariert ausgegeben. Der UI-Release ändert ihre Modell-/Settlement-Verarbeitung nicht.

Die echte Produktionsseite wurde nach dem Neustart neu geladen: BetBoy/Wettfinder mit einer aktuellen sichtbaren E-Sport-Karte (`VALORANT · FlyQuest RED vs Shopify Rebellion Gold`), ohne horizontalen Überlauf bei 1440 und 320 Pixeln. Zum Prüfzeitpunkt war Porto bereits gestartet; die Original-Porto-Reproduktion ist deshalb ausdrücklich der getrennte lokale Browsernachweis und keine erfundene aktuelle Produktionskarte. Console: **0 Fehler, 9 bestehende Warnungen** (acht nicht unterstützte Browserfeatures und die bestehende Account-iframe-Sandboxwarnung). Ein erster Browseraufruf während der geplanten Neustartpause scheiterte vorübergehend; die erneute Navigation nach erfolgreichem Updater lief korrekt. Die Live-Artefakte liegen unter `output/playwright/selection-coherence/live-1440.png` und `live-320.png` und bleiben ungetrackt.

Der folgende Dokumentationsrelease muss denselben unveränderten funktionalen Stand enthalten und ebenfalls exakt auf Main/GitHub/VPS abgeglichen werden. Ein erfolgreicher App-Healthcheck ist keine empirische Modellprüfung oder Behebung bestehender Tennis-/Settlement-Jobfehler.

## Fortsetzung ohne Kontextverlust

Der getrennte Kontextbranch `codex/kontextmodell-20260907` ist aktuell bei `0328fd70b893223822365621ef382693be51efee` lokal und remote gesichert. A1–A4 sind als Software geprüft; reale statische ATP/WTA-Builds mit den Juli-Startdaten und Linux-Restore wurden nach den ATP-Admission-Korrekturen nachgewiesen. B1 und B2 sind integriert, volle Kontextregression 2.324/15/97. Das beweist weder aktuelle Datenfrische noch trainierte Verletzungs-/Müdigkeitswirkung oder Produktionsaktivierung.

B3 ist die nächste freigegebene Aufgabe, noch nicht begonnen; B4–D5 und empirische/Betriebsfreigaben bleiben offen. Vor Fortsetzung den aktuellen Main-Fix kontrolliert in die Kontext-Arbeitskopie integrieren und erneut prüfen. Keine unfertigen Kontextdateien in diesen Produktionsfix übernehmen. Maßgeblich bleiben die dortige `progress.md`, `task-7-brief.md` sowie die Kontext- und Validierungsvertragsentscheidungen. Historische Übergabetexte, die B1/B2 noch als ausstehend bezeichnen, sind überholt.
