# BetBoy: Plan zur Behebung des Kapazitätsfehlers im Datenprüfer

Stand: 11. September 2026. **Nur Planung; keine Umsetzungsfreigabe.**

Der Nutzer verlangt ausdrücklich einen Plan und noch keinen Programmcode.
Dieses Dokument ändert weder bestehende Prüfverträge noch Ressourcenlimits.
Es autorisiert keine Tests auf dem VPS, neuen Dienste, Migrationen oder Deployments.
Eine spätere Umsetzungsfreigabe muss ihren Umfang benennen: Stufe A und/oder
die wesentlich größere Stufe B. Die bereits erteilte Commit-/Push-/Deployfreigabe
bleibt bestehen, ersetzt aber keine bestandene technische Abnahme.

## 1. Empfehlung in verständlicher Form

Wir müssen wiederholte Arbeit im **Datenprüfer** reduzieren, ohne daraus eine
andere Wettberechnung zu machen. Zunächst prüfen wir, ob bereits vollständig
bestätigte historische Zeitabschnitte innerhalb eines Prüflaufs wiederverwendet
werden können. Diese begrenzte Optimierung ist Stufe A.

Sie ist noch keine nachgewiesene dauerhafte Lösung. Jeder neue gespeicherte
Analysezustand verlangt derzeit erneut eine vollständige Historie und die
vollständige Modellnachrechnung. Deshalb braucht der Plan eine zweite Stufe:
versionsgebundene, nachprüfbare Wiederverwendung abgeschlossener Prüfungen über
mehrere Läufe hinweg. Stufe B verändert den bisherigen Vollwiederholungsvertrag
und benötigt eine separate Architekturfreigabe.

**Entscheidungsregel:** Erst Ersparnis und Gleichwertigkeit belegen. Wenn Stufe A
nicht für ein ausdrücklich definiertes Wachstumsprofil reicht, nicht weitere
kleine Varianten nacheinander entwickeln, sondern Stufe B zur Entscheidung
vorlegen. Ein knapp bestandener 31er-Lauf heißt nicht „dauerhaft gelöst“.

## 2. Gesicherter Ausgangspunkt

Lokal bei Planbeginn geprüft: sauberer Reparaturbranch
`codex/context-capacity-recovery-20260910`, HEAD
`f2763b2dda6278d21848e8f6ca97d3a895b3a55c`.
Die darin enthaltenen relevanten Produktbytes stammen unverändert aus
`72421d3bdbec4ab15a3d2953cb153e867e7e340a`.
Letzter bestätigter GitHub-/VPS-Abgleich aus dem vorherigen Arbeitsabschnitt:
`main` und VPS auf `2dd1116`; dieser Planlauf prüft den VPS nicht erneut.

| Nachweis auf Code 72421d3 | Ergebnis | Bedeutung |
| --- | --- | --- |
| Echte Kopie: 99.774 Belege, 30 Analysen | 288,095 CPU-/288,261 Wandsekunden; vollständiger erwarteter Report | Bestanden, aber nur 11,739 Sekunden Wandzeitreserve |
| Wachstum G1: 99.775 Belege, 31 unterschiedliche Analyseabfragen | 299,975 CPU-/300,165 Wandsekunden; Prozess beendet, kein Report | Nicht bestanden; tatsächliche vollständige Laufzeit unbekannt |
| Wachstum G2/G3: 32/33 unterschiedliche Abfragen | Kopien hergestellt und versiegelt | Noch nicht als vollständige D4-Läufe geprüft |
| Begrenzte G1-Diagnose: zusätzlicher Originalabruf | 1,361 CPU-Sekunden | Kein ausreichender Haupthebel |
| G1-Diagnose: Historienrekonstruktion | 48,002 CPU-Sekunden für 27 vollständige und den angefangenen 28. Aufruf | Nur ein Teil davon ist vermeidbare Wiederholung |
| G1-Diagnose: vollständige Feature-Aufrufe | 67,041 CPU-Sekunden für 27 Aufrufe | Enthält Validierung; nicht gleichbedeutend mit 67 Sekunden reiner Modellmathematik |

Die Diagnose wurde während Analyse 28/31 planmäßig beendet; sie ist kein
vollständiger Abnahmelauf. Verschachtelte Phasenzeiten nicht addieren.
Alle geprüften Eingabekopien blieben unverändert.

Es gibt **keine fachliche 30-Spiele-Grenze**. Die 30 reservierten internen
Abfrageplätze haben einen vollständigen Ausweichpfad. Zusätzlich verändert ein
neuer späterer Zeitpunkt die vorhandenen Cache-Treffer: Frühere exakte Treffer
werden teurere Rekonstruktionen aus einer größeren Historie.

Aus dem aktuellen Code folgt als Arbeitsmodell: Neben der Bestandsprüfung wächst
die Arbeit ungefähr mit der Summe der historischen Zeilen aller nachgerechneten
Analysen. Weniger doppelte Schemaabfragen reduziert den Faktor, beseitigt aber
diese Abhängigkeit nicht. Unbegrenzt wachsende Historie lässt sich bei vollständiger
Neuberechnung nicht dauerhaft mit einer festen 300-Sekunden-Garantie verbinden.

Belege: [Task10-Servermessungen](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-10-native-evidence.md),
[Task11-Ursachenanalyse](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-11-growth-analysis.md).

## 3. Ziele, Nicht-Ziele und Nutzerbedarf

### Ziele

- Vollständige, reproduzierbare Datenprüfung und anschließend ein normaler,
  überprüfbarer Deploymentweg für den tatsächlich wachsenden Bestand.
- Identische Prognosen, Featurewerte, Belegzuordnung und zulässige Ergebnisse;
  ungültige Daten dürfen durch Wiederverwendung nicht gültig werden.
- Nachgewiesener Kapazitätsbereich mit Reserve statt einer Aussage anhand
  eines einzelnen günstigen Laufs.
- Eindeutiger Status: lokal geprüft, remote gesichert, produktiv installiert
  und fachlich/empirisch validiert sind getrennte Ergebnisse.

### Nicht-Ziele

- Keine Erhöhung der aktuellen Limits, Datenlöschung oder Kürzung der Historie.
- Keine Änderung von Quotenregeln, Auswahlreihenfolge, Wettarten oder Vorhersagen.
- Keine Änderungen an mathematischen Modellen, Features, Training oder Quellen.
- Keine neue empirische Freigabe durch einen bestandenen technischen Report.
- Cricket, A0/P4b3, der gesonderte Tennis-Tagesfehler und die noch offenen
  Verletzungs-/Müdigkeitsmodelle werden durch diesen Plan nicht als erledigt erklärt.

### Nutzerbedarf

- Als BetBoy-Nutzer möchte ich verfügbare aktuelle Analysen sehen, ohne dass
  der Updateweg durch wiederholte historische Prüfungen praktisch blockiert wird.
- Als Betreiber möchte ich einen neuen Stand kontrolliert installieren und bei
  einem Fehler die bisherige App weiterbetreiben können.
- Beim Account-/PC-Wechsel muss ein anderer Bearbeiter erkennen können, welche
  exakten Code- und Datenstände tatsächlich geprüft wurden.

## 4. Lösungsoptionen und Entscheidung

| Ansatz | Erwartbarer Nutzen / Grenze | Entscheidung |
| --- | --- | --- |
| Noch kleinere Schleifen-/Cursoroptimierungen | Bereits gemessene Verbesserungen umgesetzt; kein neuer ausreichender Hebel belegt | Kein eigener neuer Reparaturzyklus ohne konkrete Messung |
| Weitere Originalabfragen gemeinsam abarbeiten | G1 hat nur einen zusätzlichen vollständigen Abruf von 1,361 Sekunden | Nicht der primäre Lösungsweg |
| Zusätzliche vollständige Historien im Cache | Basis belegt bereits 58.392.186 Byte; Kopien würden den gemeinsamen 64-MiB-Bereich bedrängen | Keine zweite Historienkopie |
| Bereits abgeleitete Zeitabschnitte als kleine Metadaten merken | Spart bei Wiederholung bestimmte Zeilenprüfungen, nicht die frische Dekodierung/Modellnachrechnung | Stufe A, begrenzter und zunächst unbewiesener Kandidat |
| Features oder Prognosen pauschal zwischenspeichern | Würde den eingefrorenen Modell-/Featurevertrag berühren | Nicht Teil von Stufe A oder automatisch durch diesen Plan erlaubt |
| Versionsgebundene abgeschlossene Prüfungen wiederverwenden | Kann unveränderte historische Nachrechnung aus wiederkehrenden Deployments entfernen | Stufe B als langfristige Architektur, separat freizugeben |
| Mehr Hardware, höhere Zeitlimits oder historische Daten entfernen | Ändert Kosten/Grenzen oder Datenumfang; beseitigt Wiederholung nicht | Nicht als verdeckter Reparaturweg zugelassen |

## 5. Stufe A: begrenzte Wiederverwendung innerhalb eines Prüflaufs

### A1. Vor Umsetzung: messbare Ersparnis und Grenzen bestimmen

- Exakten Code, Laufzeitumgebung und versiegelte Eingaben festhalten.
- In repräsentativen frühen und späten Zeitabschnitten trennen: erste Ableitung,
  wiederholter gleicher Zeitpunkt, frisches Dekodieren, Datenbank-/Lebensdauerprüfung,
  Belegvergleich und unveränderte Feature-/Transportarbeit.
- Gleiche und nur einmal vorkommende Zeitpunkte getrennt messen. Die größte
  gespeicherte Historie und ein Gegenprofil ohne wiederholte Zeitpunkte einbeziehen.
- Die maximal mögliche Einsparung aus den wirklich ersetzbaren Schritten
  herleiten. Die gesamten 48,002 Sekunden nicht als Einsparung verbuchen.
- Begrenzte Diagnose darf unterbrochen werden; ungemessene Restarbeit bleibt
  unbekannt. Keine Erhöhung der Abnahmegrenze, um eine vollständige Altzeit zu erhalten.

**Stop/Go A:** Wenn selbst die optimistische gemessene Obergrenze keine
ausreichende Reserve zulässt, endet A hier. Noch keinen Produktumbau starten.
Wenn die Rechnung plausibel ist, folgt ein klar abgegrenzter Äquivalenznachweis.

### A2. Neuer, ausdrücklich zu genehmigender interner Prüfvertrag

Heute wird ein bereits abgeleiteter früherer Zeitraum beim nächsten Aufruf
erneut als neue Teilhistorie geprüft. Vorgeschlagen ist:

1. Die vollständige physische Bestandsprüfung, Quellenvalidierung und unabhängige
   Validierung der gespeicherten Historienbasis bleiben erhalten.
2. Die **erste** Ableitung eines Zeitabschnitts behält alle bisherigen Zeilen-,
   Größen-, Transaktions- und Abschlussprüfungen.
3. Erst nach erfolgreichem Abschluss darf der besitzende Prüfer kleine Metadaten
   speichern: Zeitraum/Tour, Elternschlüssel, exakte Eltern-Seriennummer,
   vollständige Zeilenanzahl und kanonische Byteanzahl.
4. Bei derselben späteren Anfrage entstehen weiterhin neue verschachtelte
   Objekte und eine vollständige geordnete Historie. Die Elternidentität und
   Prüfberechtigung werden am Eintritt und vor der Rückgabe frisch bestätigt.
   Bestimmte bisherige Datenbankprüfungen vor/nach jeder dekodierten Zeile
   werden durch diesen neuen Vertrag ersetzt, nicht als weiter ausgeführt behauptet.
5. Vollständige Belegvergleiche, bisherige Feature-Prüfgrenzen und jede
   ereignisspezifische Modell-/Transportnachrechnung bleiben unverändert.

Das ist nur dann zulässig, wenn zwischenzeitliche Änderungen, Rücksetzungen,
Wiedereintritte und Ersatz einer Historie weiterhin zuverlässig erkannt werden.
Gelingt dieser Nachweis nicht, darf diese Optimierung nicht eingesetzt werden.

### A3. Lebensdauer und Speicherbesitz

- Nur eine tatsächlich vollständig geprüfte, noch besessene Basis kann Eltern
  eines Zeitabschnitts sein. Ein beliebiger Cacheeintrag oder Aufrufer-Flag genügt nicht.
- Metadaten speichern keine Zeilen, Bytekopien, Iteratoren oder ganzen Einträge.
  Ein Zugriff darf nach Elternaustausch keine alten und neuen Daten vermischen.
- Austausch auch mit gleichen Bytes, Verdrängung, Transaktionsende, Schreiben,
  main-/temp-Schemaänderung, Schließen oder widerrufene Prüfung entwerten die Sicht.
- Kurze Metadaten-/Serienprüfungen müssen nötigenfalls jeden Zugriff absichern;
  das ist getrennt von den teuren frischen Datenbankabfragen zu untersuchen.
- Alle Metadaten und ausstehenden Reservierungen zählen im gemeinsamen
  64-MiB-Budget und den 32 Plätzen. Keine unberechneten Nebenpools.
- Verbrauchte Originalabfrage-Metadaten erst nach erfolgreicher Prüfung **aller**
  Originale freigeben. Die tatsächliche Cacheinstanz auch im Ausweichpfad beachten.
- Platzmangel oder fehlende Wiederverwendungsdaten führen zur vollständigen
  bisherigen Prüfung. Integritätsfehler führen zum Abbruch, nicht zum scheinbar
  erfolgreichen Cache-Miss. Die Basis nicht für ihre eigenen Metadaten verdrängen.

### A4. Voraussichtliche Codegrenzen nach einer späteren Freigabe

Der erste Kandidat betrifft `context_runtime_history_cache.py` und gezielte
neue Tests. Ein eng begrenzter Abschlussübergang kann in `context_runtime.py`
oder `context_runtime_tennis.py` erforderlich sein; dessen Auswahl ist vor dem
ersten Produktpatch im Aufgabenbrief festzuhalten. Die eigentliche Inventur,
Quellenvalidierung und der geschützte Transaktionshelfer bleiben unverändert.

Keine Änderung an `context_models/tennis_v3.py`, `tennis/predict.py`,
`context_sources/tennis_status.py`, `context_observations.py`, Datenbankschemata,
Schlüsseln, Markern oder Deployskripten als Nebenwirkung dieser Optimierung.

### A5. Gleichwertigkeit vor Geschwindigkeit

- Gleicher vollständiger positiver Report und unveränderte kanonische Werte
  gegenüber 72421d3, nicht nur gleich viele Treffer.
- Beschädigte Daten bleiben auch dann abgelehnt, wenn sie zukünftig, einer
  anderen Tour/Quelle zugeordnet oder unreferenziert sind. Gültige solche Daten
  werden nicht pauschal abgelehnt: vollständige Bestandsprüfung und bisherige
  zeitliche/fachliche Auswahlregeln bleiben bestehen. Geschützte ungeöffnete
  Finaldaten bleiben ungeöffnet.
- Gleiche, frühere, spätere, leere und ineinander verschachtelte Zeitabschnitte;
  inklusive Grenzen, Zeitzonen, Gleichstände und beliebige Aufrufreihenfolge.
- Frische Objektidentitäten je Verbraucher; keine nachträgliche Mutation kann
  andere Analysen beeinflussen. Direkte Teilmengenablage erzeugt keinen Beweis.
- Reale SQLite-Kontrollen: Writes, main/temp-DDL, Commit/Rollback/Neustart,
  Schließen, Klassen-/Methoden-/Factorywechsel während Callbacks sowie
  zwischenzeitliche Änderung mit anschließend wieder gleichem sichtbaren Zustand.
- Unterbrechungen vor Veröffentlichung, beim Wiederverwenden und nach der
  letzten Zeile; echte Speicher-/Referenzfreigabe bei Verdrängung und Ersatz.
- Aus/An/Platzmangel/Verdrängung liefern dieselben fachlichen Ergebnisse.
  Geänderte Fehlerreihenfolgen gesondert bewerten; keine stillen Erfolgsfälle.
- Zahl der vollständigen Original-, Feature- und Transportaufrufe bleibt gleich.

Neue Tests müssen zuerst den fehlenden Vertrag auf dem unveränderten Stand
sichtbar machen, danach den Kandidaten prüfen. Bestehende Regressionen nicht
anpassen, nur damit eine neue Abkürzung grün wird. Ein unabhängiger Prüfer bewertet
den exakten Diff und die früheren problematischen Callback-/Lebensdauerfälle.

## 6. Kapazitätsnachweis mit Reserve und echter Wachstumsdimension

Bestehende Grenzen bleiben: CPU 300 Sekunden, äußere Wandzeit 600 Sekunden,
gemessene CPU- und Wandzeit jeweils unter 300 Sekunden, Spitzen-RAM unter 1 GiB,
Adressraum 2 GiB, Ausgabe 1 MiB, Eingabe 1 GiB, eine vollständige Historie
256 MiB und gemeinsamer Cache 64 MiB. Abnahme über unveränderte echte CLI.

Nach Freigabe zuerst heutige Daten und die bestehenden echten 30/31/32/33er-
Profile prüfen. Dann ein Kapazitätsprofil für **mindestens sieben weitere
Betriebstage als Planungsziel** aus gemessener Schreibfrequenz und Datenmenge
ableiten; nicht als bereits zugesicherte Eigenschaft ausgeben. Zusätzlich
60/120-Verbraucher-Stressprofile mit neuen Zeitpunkten zur Kostengrenze verwenden.
Bloßes Duplizieren derselben Analyse oder Vergrößern nur der Belegtabelle reicht nicht.

Zu variieren sind Anzahl der Analysen, unterschiedliche Zeitpunkte, beide
Touren, vollständige Historienlänge, Cachebelegung und Originalabfrage-Überlauf.
Historische größere Eingaben, kleine gültige Eingaben, Berechtigungs- und
Dateiaustauschtests bleiben Teil der Abnahme.

**Vorgeschlagenes Robustheitsziel:** Aktueller Bestand plus vereinbartes
Wachstumsprofil sollen in drei getrennten Serverläufen jeweils höchstens
240 CPU-/Wandsekunden benötigen. Das sind 20 Prozent Reserve gegenüber dem
bestehenden 300er-Limit, eine neue Planungsanforderung und kein gemessener Erfolg.
Nicht nur einen Median oder den besten Lauf melden; alle Einzelwerte festhalten.
Das größere Stressprofil darf als Grenzbestimmung scheitern, darf dann aber
nicht zum behaupteten unterstützten Bereich zählen.

**Stop/Go B:** Scheitert die Gleichwertigkeit, ein Pflichtprofil oder die
vereinbarte Reserve, ist A keine belastbare Gesamtlösung. Bei jedem Checkpoint
werden Code-SHA, Eingabe-SHA, vollständiger Report, CPU/Wandzeit/RAM und
unveränderte Eingaben dokumentiert. Danach Architekturentscheidung B, keine
Ressourcenerhöhung, Historienkürzung oder wiederholte Optimierung ohne neuen Beleg.

## 7. Stufe B: dauerhafte Skalierung der Verifikation, separate Freigabe

Diese Stufe ist ein **Architekturvorschlag**, noch kein ausführbarer Patchplan.
Sie ist nötig, wenn die vollständige historische Wiederholung im festen Budget
nicht für den vereinbarten Betriebshorizont tragfähig ist. Sie ist nicht allein
durch eine Freigabe von Stufe A mitgenehmigt.

Zielbild: Ein abgeschlossener Prüfnachweis bindet genau die geprüften Inhalte,
Abhängigkeiten und verwendeten Implementierungsversionen. Nur bei nachgewiesener
Unverändertheit dürfen bereits abgeschlossene historische Nachrechnungen gelten;
neue oder betroffene Analysen erhalten die vollständigen bisherigen Prüfer.
Das betrifft gespeicherte Prüfnachweise, nicht das Ersetzen neuer Prognosen durch
alte Ergebnisse oder das Behaupten einer empirischen Modellfreigabe.

Vor Umsetzung sind fünf konkrete Designentscheidungen zu lösen:

1. **Vollständigkeit:** Wie wird der gesamte relevante Bestand einschließlich
   fehlender, geänderter, unreferenzierter und zurückgesetzter Datensätze gebunden?
   Ein höchster Datensatzindex, Zeitstempel oder Zeilenzähler ist kein Nachweis.
2. **Versionen/Abhängigkeiten:** Welche exakten Prüfer-, Modell-, Quell- und
   Vertragsversionen samt transitiven Eingaben machen einen Nachweis gültig?
   Änderungen dürfen alte Beweise nicht pauschal über eine Hashliste freischalten.
3. **Vertrauenswürdige Veröffentlichung:** Wie kann ausschließlich ein vollständig
   abgeschlossener, begrenzter Prüflauf einen nicht fälschbaren und nicht
   zurückrollbaren Nachweis veröffentlichen? Ein Flag in derselben veränderbaren
   Datenbank reicht nicht. Speicherort, Rechte, Bindung, Backup und Wiederherstellung
   müssen separat entworfen werden; bestehende Schlüssel bleiben vorerst unberührt.
4. **Arbeitsaufteilung:** Historische Nachrechnung kontrolliert vor dem Deployment
   ausführen; Deploy akzeptiert nur einen vollständig passenden Nachweis plus
   vollständig geprüften aktuellen Zuwachs. Kein ungeprüftes Nachziehen während
   des Umschaltens, kein Erfolgszustand nach nur einem Teilstück.
5. **Kosten und Wiederanlauf:** Gesamt-CPU, Gesamtdauer, Teilbudgets und Abbrüche
   offen ausweisen. Mehrere 300-Sekunden-Prozesse sind nicht automatisch ein
   bestandener bisheriger 300-Sekunden-Volltest. Der neue Lebenszyklus muss
   ausdrücklich genehmigt werden, einschließlich Erstprüfung und Codewechsel.

Korrektheitsreferenz bleibt die vollständige kalte Prüfung. Auf kontrollierten
Beständen müssen vollständige und wiederverwendende Prüfung identisch urteilen;
Neuaufbau, fehlender Nachweis, Inhaltsänderung, Löschung, Rollback, Versionswechsel
und Absturz erhalten jeweils eigene Abnahmetests. Ungültige Nachweise bewirken
vollständige Neuprüfung oder einen ehrlichen Abbruch, niemals automatische Freigabe.

Auch B kann mit konstanten Eingabe-/RAM-/Zeitlimits nicht unbegrenzte Speicherung
versprechen. Liegt das vereinbarte Wachstumsprofil außerhalb dieser Grenzen,
ist eine weitere explizite Kapazitäts-/Speicherentscheidung erforderlich.
Automatische Löschung oder Archivmigration ist durch diesen Plan nicht erlaubt.

## 8. Reihenfolge, Zuständigkeit und messbare Liefergegenstände

| Schritt nach Freigabe | Liefergegenstand | Fertig erst wenn |
| --- | --- | --- |
| 1. Referenzen und Betriebswachstum festhalten | Code-/Datenpins, Kostenanteile, definiertes Pflicht-/Stressprofil | Keine offenen Verwechslungen von Volltest und Diagnose |
| 2. Stufe-A-Wirtschaftlichkeit und Prüfvertrag beurteilen | Messbare Ersparnisgrenze und Äquivalenzargument | Genug plausibler Nutzen; andernfalls direkt B-Design |
| 3. Genau ein abgegrenzter A-Kandidat | Neue Grenztests, enger Diff, unabhängiges Review | Alle fachlichen und Lebensdauerbedingungen erfüllt |
| 4. Echte Linux-Abnahme | Alle Einzelmessungen inklusive Wachstum und Reserve | Pflichtprofile vollständig bestanden, Daten unverändert |
| 5. Falls nötig: B separat spezifizieren | Vollständigkeits-, Versions-, Nachweis- und Wiederanlaufvertrag | Unabhängig prüfbarer Entwurf und explizite Umsetzungsfreigabe |
| 6. Finalen Releasekandidaten einfrieren | Vollsuite auf exakt diesen Produktbytes plus Delta-Review | Keine Übertragung alter Testergebnisse auf geänderten Code |
| 7. Backup und kontrollierter Rollout | Wiederherstellung geprüft, exakte Git-/Updater-/App-SHAs | Alle Releasebedingungen auch mit dem frischen Bestand erfüllt |

Ein Implementierer pro Schreibbereich; unabhängiges Review auf festem Diff.
Der Controller besitzt Integration und Veröffentlichung. Keine parallelen
schweren VPS-Testläufe, keine neuen lokalen automatischen Schreiber.
Große Vollsuite erst nach bestandenem Kapazitätskandidaten, nicht nach jedem
kleinen Zwischenschritt. Zeitaufwand nach Schritt 2 neu bewerten; kein
Fertigstellungsdatum aus den bisherigen unvollständigen Messungen erfinden.

## 9. Release- und Abschlussregeln

- Nach späterer Umsetzung gezielte Änderungen committen und auf dem
  Reparaturbranch pushen; fremde/ungetrackte Ausgaben unberührt lassen.
- Vor Produktion frisches Backup aller dann vorhandenen Laufzeitdatenbanken
  und tatsächliche Wiederherstellung inklusive bestehender Kontointegrität prüfen.
  Die historische Zahl 88 ist kein Ersatz für ein frisches Inventar.
- Den frischen Datenstand erneut gegen das tatsächlich abgenommene Profil
  prüfen. Ist der Bestand weitergewachsen, darf ein alter Test ihn nicht vertreten.
- Erst dann normal auf `main` integrieren/pushen. Kein Force-Push oder Überspringen
  eines gescheiterten Prüfers, um den Rollout zu erzwingen.
- Den bereits freigegebenen Updateraustausch separat und exakt verifizieren;
  anschließend den gewöhnlichen Updater für denselben Releasecommit ausführen.
- GitHub, VPS-Code, installierten Updater, App/Caddy, Timer und beide Healthchecks
  getrennt nachweisen. Backup-/Rollbackweg muss vor dem Umschalten stehen.
- Der gesondert fehlgeschlagene Tennis-Tagesjob bleibt eine eigene offene
  Betriebsaufgabe. Ein gesundes HTTP-Ende oder aktiver Timer beweist keinen
  erfolgreichen Tageslauf und keinen guten Wetttipp.
- „Technischer Kapazitätsfehler behoben“ erst bei vollständiger Abnahme;
  „alle Kontextmodelle fachlich fertig“ ist damit ausdrücklich nicht bewiesen.

## 10. Technische Leitplanken aus Primärdokumentation

SQLite isoliert getrennte Verbindungen, nicht Operationen innerhalb derselben
Verbindung. Die eigene Schlussfolgerung für diesen Plan: Eine gehaltene Transaktion
allein ersetzt keine Kontrolle von Änderungen oder Callbacks derselben Verbindung.
[SQLite: Isolation](https://www.sqlite.org/isolation.html).

`PRAGMA data_version` ändert sich nicht durch Commits auf derselben Verbindung.
Es ist deshalb für diesen Fall kein alleiniger Ersatz der bestehenden
Lebensdauer-/Änderungsnachweise. [SQLite: data_version](https://www.sqlite.org/pragma.html#pragma_data_version).
`in_transaction` beschreibt einen Transaktionszustand; die zusätzliche Bindung
an die konkrete geprüfte Generation ist eine Anforderung unseres Vertrags.
[Python 3.12: sqlite3](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.in_transaction).

## 11. Prioritäten und offene Entscheidungen

- **P0:** Vollständigkeit, unveränderte Rechenergebnisse, korrekte Entwertung,
  vollständige Pflichtprofile, frisches Backup/Restore und kontrollierter Rollout.
  Auf keines dieser Kriterien darf zur Beschleunigung verzichtet werden.
- **P1:** Kompakte interne Messberichte mit klaren Kostenanteilen und Reserve.
  Dafür ist kein zusätzlicher Block technischer Begriffe in der Nutzeroberfläche nötig.
- **P2 / nicht in dieser Reparatur:** Hardwarewechsel, Speicherauslagerung oder
  Neuaufbau der Sportmodelle. Stufe B ist hingegen bei unzureichender Kapazität
  eine erforderliche Architekturentscheidung, keine optionale Verschönerung.

| Offene Entscheidung | Zuständig | Zeitpunkt / Blockierung |
| --- | --- | --- |
| Darf der vorgeschlagene interne Wiederholungsvertrag A geändert werden? | Nutzer, auf Grundlage dieses Plans | Vor Produktcode; aktuell nur Planung beauftragt |
| Wie viel Einsparung bleibt nach frischem Dekodieren und unveränderten Feature-Prüfungen tatsächlich? | Engineering | Vor einem vollständigen A-Umbau; begrenzter Machbarkeitsnachweis |
| Welche konkrete Datenmenge bildet sieben weitere Betriebstage ab? | Engineering anhand gemessener Schreibfrequenz | Vor Festlegung des Pflichtprofils; kein pauschales Zählen von Karten |
| Wird das vorgeschlagene 240-Sekunden-Reserveziel verbindlicher Teil der Abnahme? | Nutzer im Rahmen der späteren Planfreigabe | Vor Implementierung; bisheriger Grenzwert bleibt 300 Sekunden |
| Reicht A oder benötigt der definierte Bereich Stufe B? | Engineering mit unabhängigem Review | Nach Kosten-/Äquivalenznachweis, spätestens nach Pflichtprofilen |
| Welche Nachweis- und Invalidierungsarchitektur B ist korrekt? | Engineering und unabhängiges Review, Freigabe durch Nutzer | Separat vor B-Code; nicht implizit durch A genehmigt |

## 12. Status dieses Dokuments

- [x] Reale Ausgangsbefunde und Codepfade abgeglichen.
- [x] Optionen, Empfehlung, Risiken, Abnahmen und Stoppregeln dokumentiert.
- [ ] Umsetzung von Stufe A ausdrücklich freigegeben.
- [ ] Stufe A implementiert und unabhängig geprüft.
- [ ] Kapazitätsabnahme einschließlich vereinbartem Wachstumsprofil bestanden.
- [ ] Falls erforderlich: Stufe-B-Vertrag entworfen, geprüft und freigegeben.
- [ ] Release vollständig geprüft und kontrolliert deployed.

**Die Erstellung oder Speicherung dieses Plans setzt keines der offenen
Umsetzungs-/Freigabekästchen auf erledigt.**
