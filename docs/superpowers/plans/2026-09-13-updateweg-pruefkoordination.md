# Updateweg reparieren: begrenzte gemeinsame Prüfkoordination

Stand: 13.09.2026. Gelesener Reparaturstand:
`0296b09306da5e820968c23a485c25b9e12c8a2c`.

**Aktueller Nachtrag: implementiert; beide ausdrücklich freigegebenen
900-s-Diagnoseaufträge wurden ausgeführt und sind unvollständig beendet.**
Im zweiten Auftrag A400/B300/C200 bestanden A1 und A2, danach erreichte der
Steuerprozess sein 60-CPU-Limit. Ursache lokal korrigiert, kein dritter großer
Versuch, kein C/B-Pass und kein Reset eines erhaltenen Journals.
[Zweiter tatsächlicher Ausgang und verbleibende Grenzen](../../audits/2026-09-13-second-qualification.md).
Die folgenden Abschnitte erhalten den ursprünglichen Planvertrag. Die bestehenden
C-/B-/Commit-/Push-/Deploymentfreigaben werden nicht erneut verlangt; zusätzliche
Messbudgets oder eine andere Teilreserveverteilung wären neue Entscheidungen.

## 1. Zwei Probleme, zwei Nachweise

Der installierte produktive Updater erlaubt nur 64 MiB für die vollständige
Kontextdatenbank. Die am 13.09.2026 ab 18:04 UTC gemessene Datei hat
499855360 Byte, rund 476,70 MiB. Der Größencheck erfolgt dort erst nach dem
Stoppen der App. Ein Dokumentationscommit umgeht diese Prüfung nicht.
[Frischer Betriebsabgleich](../../../docs/audits/2026-09-13-daily3-vps-preflight.md)

Im Reparaturbranch existieren bereits ein ausdrücklich ausgewählter
dateibasierter Leser, ein vorgeschalteter Online-Check und ein separater
Updater-Reparaturinstaller. Sie sind noch kein vollständig abgenommener
C/B-Release. Ein weiterer bloßer Austausch von `64 MiB` gegen eine größere
Zahl ist deshalb nicht der Plan.

Zusätzlich blockiert die QA-Orchestrierung: vier vollständige Beobachtungen
aller alten QA-Verzeichnisse, davon je zwei im bisherigen Vorbereitungs- und
Steuerprozess mit jeweils insgesamt 60 CPU-Sekunden. Ein vollständiger Scan
des größten Verzeichnisses benötigte gemessen 47,558612911 CPU-Sekunden.
Zweimal derselbe Aufwand wären 95,117225822 Sekunden — eine Hochrechnung,
kein tatsächlich gemessener Doppellauf und keine garantierte Mindestlaufzeit.
[Aufrufstellen und Kosten](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-62-retained-cost-review.md)

## 2. Ziel, Nutzerbedarf und Nicht-Ziele

Als Betreiber will ich einen exakten neuen Stand prüfen können, ohne vorher
die erreichbare App wegen eines bekannten Kapazitätsfehlers abzuschalten.
Als Bearbeiter will ich jeden Abbruch mit erhaltenen Daten, tatsächlichem
Fortschritt und vollständig zugeordneten Kosten übernehmen können.

Erfolg bedeutet:

1. Alle vier bisherigen vollständigen Bestandsbeobachtungen bleiben erhalten.
2. Vorarbeit, Kopien, Scanner, Daten-Worker, Nacharbeit und Fehlerkosten haben
   ein gemeinsames begrenztes Messpaket, keine Gratisbudgets pro Prozess.
3. Kein Erfolg ohne vollständige Nachprüfung, tatsächliches Prozessende und
   extern bestätigten Abschluss; ein Teilbericht bleibt unvollständig.
4. Späterer Produktionswechsel erst nach vollständigem C/B-, Restore- und
   Release-Nachweis; der neue Online-Check läuft vor einem App-Stopp.

Nicht enthalten: neue Sportmodelle, bessere Trefferquoten, zusätzliche
Verletzungs-/Müdigkeitseffekte, Daily3-Implementierung, Cricket, A0/P4b3,
Datenlöschung, kostenlose Zusatzversuche, größere Modell-Worker-Grenzen,
Server-Upgrade, neue Sporttimer oder Direkt-Pull am Updater vorbei.
Der gesonderte Tennis-Tagesfehler wird dadurch nicht automatisch behoben.

## 3. Empfohlene Architektur

Ein versionsgebundener, bedarfsgesteuerter QA-Koordinator übernimmt den gesamten
Messauftrag. Er bleibt ein kurzlebiger Prüfprozess, kein neuer Dauerdienst.
Er startet nur gepinnte Programme mit geschlossenen Eingaben, behält deren
Prozessidentität und kennt den kumulativen Verbrauch aller seiner Kinder.

| Reihenfolge | Frische Arbeit | Abschlussbedingung |
| --- | --- | --- |
| 0 — Aufnahme | Auftragsidentität, Altlasten, exakte Quellen, Platz- und Zeitkonto binden | Gesamtreservierung dauerhaft bestätigt, noch kein großer Scan |
| A1/A2 — Vorbereitung | Erste komplette Historieninventur und erneuter vollständiger Vergleich beim Katalogaufbau | Zwei getrennte frische Beobachtungen, gleiche vollständige Mitgliedschaft |
| A3 — unmittelbar vor Datenlauf | Dritter vollständiger Historienvergleich nach Vorbereitung, aktive Inputs/Runtime erneut binden | Keine Änderung; erst jetzt fachliche Daten-Worker-Zulassung |
| B — Datenlauf | Genau der bestehende einzelne 1024-Belege-Diagnoseaufruf | Tatsächliches Ende, vollständige Ausgabe oder ehrlich begrenzter Fehlerpräfix |
| C — Nachprüfung | Vierter vollständiger Historienvergleich, aktive Inputs und erzeugte Ausgaben prüfen | Echte Ergebnisprüfung, alle Prozesse beendet, externer Terminalbeleg |

Die drei A-Beobachtungen sind **nicht** durch einen früheren Hash ersetzt.
Die Verlagerung aus den bisherigen 60-CPU-Prozessen ist eine ausdrückliche
Vertragsänderung, keine angeblich unveränderte Mikrooptimierung. Ihre alten
V1-Einstiege und archivierten Belege bleiben unverändert lesbar.

Der Koordinator darf nur kleine, geschlossene Kontrollinformationen verarbeiten.
Historische Dateiinhalte werden nicht als Code importiert. Der neue Scanner
braucht den bisherigen privilegierten Nur-Lesezugriff auf alte private QA-Pfade;
er ist ausdrücklich **nicht** der unprivilegierte Modell-Worker. Kein generisches
„beliebiges Programm als root“-Interface. Der vorhandene Modell-Supervisor und
seine UID-/Prozess-/Netzwerkgrenzen werden nicht dafür aufgeweicht.

## 4. Konkrete Budgetentscheidung für genau ein neues Diagnosepaket

**Vorschlag: höchstens 900 CPU-Sekunden und 900 Sekunden Gesamtwandzeit für
ein einziges zusätzlich genehmigtes Engineering-Messpaket.** Das ist eine neue,
sichtbare Aufwandserlaubnis, kein schon vorhandenes freies 900-Sekunden-Guthaben.

| Teilreserve | Maximum CPU | Was darin enthalten ist |
| --- | ---: | --- |
| A | 300 s insgesamt | Alle drei Vorbeobachtungen samt Scanner-Start, Katalog- und Abschlussarbeit |
| B | 300 s insgesamt | Daten-Worker höchstens 240 s; Koordinator über seine gesamte Lebensdauer höchstens 60 s |
| C | 300 s insgesamt | Vollständige Nachbeobachtung samt Scanner-Start und Abschlussarbeit |
| Gesamtes Paket | 900 s | Keine Übertragung ungenutzter A-/C-Zeit an den Daten-Worker |

Falls A mehrere kurze Scannerprozesse benötigt, gilt **zusammen** weiterhin
300 s. Vor jedem Start wird höchstens der belegte Rest von A zugeteilt; niemals
erneut 300 s. Dasselbe gilt für C. Alle Start-/Abbruch-/Reaping-Kosten werden
erfasst. Ein Teilprozess bekommt nie eine neue Gesamtfrist.

Die 900-Wandsekunden beginnen am ursprünglichen Kernelstart des Koordinators;
der Daten-Worker behält höchstens 240 eigene Wandsekunden. Eine bereits enger
gebundene Frist verkürzt den Ablauf zusätzlich. Vorbereitung wartet nicht
unbegrenzt auf I/O. CPU für Abschluss/Custody wird vor dem Workerstart reserviert;
fehlende Restzeit verhindert den Start, nicht erst den späteren Abschluss.

Nur zur Plausibilität: drei unverändert teure Scans allein des größten Roots
wären etwa 142,676 CPU-s in A, einer etwa 47,559 CPU-s in C. Weitere Roots,
Kopien und Schwankungen sind darin nicht enthalten. Diese Rechnung ist keine
Kapazitätsabnahme. Passt die vollständige Arbeit nicht, ist das Paket STOP;
kein neuer Versuch mit höherem Limit oder verkleinertem Umfang.

### Alte Kosten und die 1800/3600-Grenze

- Die bisherigen V1-Journale, offenen Tickets und unbekannten Kosten bleiben
  erhalten. Die beobachteten 1680 CPU-s primärer Altreservierungen sind weder
  gemessener Gesamtverbrauch noch beliebig übertragbarer Kontostand. Synthetische
  Protokolltickets und unjournalisierte Engineeringkosten werden separat gezeigt.
- Dieses vorgeschlagene 900-Sekunden-Paket ist ausdrücklich zusätzliche
  Diagnosearbeit. Sein Bericht nennt historische Belastungen **plus** neue
  Belastung; unbekannte Altanteile bleiben unbekannt und werden nicht zu null.
  Ohne diese neue bezifferte Freigabe wird es nicht gestartet.
- Die bestehende echte C/B-Vorbereitung bleibt auf 1800 CPU-/3600 Gesamtsekunden
  je gebundenem Auftrag begrenzt. Das Diagnosepaket ist kein Beweis ihrer Einhaltung.
  Arbeit, die tatsächlich den C/B-Pflichtbestand vorbereitet, darf nicht als
  „Diagnose“ ausgelagert werden, um diese Grenze zu umgehen; sie zählt dort mit.
- Keine neue Gutschrift durch Umbenennen von Verzeichnis, Run-ID, Seed oder Profil.
  Neue Codeidentität rechtfertigt keine automatische Aufwandserlaubnis. Eine
  neue ausdrücklich genehmigte Beauftragung bindet ihre Vorgänger und Kosten.

### Buchung und Messung

Ein neuer geschlossener V2-Auftragsdatensatz reserviert die drei Teilbudgets
zusammen, bevor eine aufwendige Phase beginnt. V1 hat derzeit nur ein offenes
Ticket und eine einmalige Diagnosezulassung; drei weitere V1-Journale sind
**kein** Ersatz für diesen gemeinsamen V2-Besitzer. V1 nicht neu signieren,
zurücksetzen oder nachträglich mit einer anderen Deadline versehen.

Die Aufnahme bindet zunächst den vorab deklarierten Soll-Auftrag und dessen
exakte Quell-/Eingabeidentitäten. Sie behauptet noch keine frische Inhaltsprüfung.
Das tatsächlich in A erzeugte und erneut geprüfte Inventar wird danach an
diesen ursprünglichen Auftrag gebunden; weder selbstreferenzierender Hash noch
nachträglich ausgetauschter Soll-Auftrag. Auch Parser-/Bootstrapkosten vor der
Reservierungsbestätigung gehören ab Kernelstart zur Messung und zur B-Teilreserve.

Für diese einmalige Qualifikation bleibt die ganze Reservierung konservativ
belastet, auch bei frühem Abbruch. Tatsächlich gemessene CPU wird zusätzlich
ausgewiesen, aber erzeugt keine automatische Rückerstattung oder Wiederholung.
Verbrauch aus eigenen Kernelmessungen und tatsächlich gereapten Kindern ohne
Doppelzählung zusammenführen; Worker-Selbstauskünfte sind nur Zusatzdiagnostik.
Ein nicht gereaptes Kind, fehlender Endbeleg oder beschädigtes Journal bedeutet
STOP und erhaltene Zuständigkeit, nicht Freigabe der Reserve.

Unverändert: höchstens 4 GiB aktiver Eingabesatz, 8 GiB gesamter neuer QA-Bereich,
4 GiB freier Platz zusätzlich zu offenen Allokationen und Backup-/Rollbackreserve.
Adressraum 2 GiB und beobachtetes RSS unter 1 GiB je begrenztem Arbeitsprozess;
gleichzeitigen Gesamtbedarf zusätzlich messen. Es läuft höchstens ein Blattprozess
neben dem Koordinator. Diagnose-Logs zusammen höchstens 1 MiB; bestehende
gesonderte Kontroll-Dateigrenzen bleiben Teil der vollständigen Platzbilanz.
Kein Server-Secrets- oder Datenbanktransfer auf den PC.

## 5. Vollständigkeit, Frische und der bekannte FIFO-Test

Jede Beobachtung liest alle regulären historischen Dateien über gehaltene
No-follow-Identitäten vollständig; Hardlink-Metadaten und belegter Platz bleiben
enthalten. Historische Symlinks werden nicht verfolgt. Eltern- und
Mitgliedschaftsepochen, tatsächliche deklarierte Journale und komplette Summen
werden frisch verglichen. Ein alter Manifestdigest ist nur Vergleichsbasis,
keine Behauptung eines neuen Scans. Kontrolldateien des neuen Auftrags gehören
in vorher deklarierte Slots außerhalb seines historischen Vergleichsbestands.

Der bekannte historische Negativtest enthält genau diesen FIFO:
`/tmp/betboy-context-retained-task62-6eb267a-01/green/fixtures/test_native_fifo_refused_witho0/fifo`.
Vorschlag für den **neuen historischen V2-Codec**: exakt diesen Pfad mit vorher
festgehaltener Eltern-/Dateiepoch und Typ `fifo` vollständig als Metadatenobjekt
erfassen; nie öffnen, lesen, ausführen oder seine Existenz auslassen. Er besitzt
keinen zu hashenden regulären Dateikörper. Änderung von Pfad, Typ, Inode,
Elternidentität oder zweiter FIFO führt zum Fehler. Keine Wildcard-Ausnahme.
Alle regulären Inhalte bleiben voll gehasht; unbekannte Spezialdateien und
FIFO in aktiven Eingaben, Code oder neuen Corpusdaten bleiben abgelehnt.
Dieser V2-Umgang ist neu vorgeschlagen, nicht bereits implementiert.

Frische zwischen Prozessen wird durch eigene gebundene Kontroll-FDs, exakte
Quell-/Laufzeitidentität, abgeschlossene tatsächliche Scanneraufrufe und erneute
Vergleiche belegt. Kein frei setzbares `checked=True`, fremdes `success.json`
oder später neu geöffneter gleichnamiger Pfad übernimmt Prüfautorität.

## 6. Umsetzungsreihenfolge und konkrete Abnahme

| Schritt | Enger Umfang / geplante Dateien | Fertig erst wenn |
| --- | --- | --- |
| Q1 — Vertrag und Konto | Neue QA-V2-Protokolle, z.B. `tests/native_context_qa_budget.py`; bestehende V1-Parser unverändert | Drei Teilreserven sind atomar gebunden; Altlasten/Frist bleiben erhalten; keine Startzulassung aus Teilzustand |
| Q2 — historischer V2-Scanner | `tests/native_context_receipt_diagnostic_catalogue.py` mit ausdrücklich separatem V2-Einstieg und neue Scanner-Tests | Alle vier Beobachtungen, Frische, vollständige Bytes und exakt begrenzter FIFO-Fall geprüft; V1-Tests unverändert |
| Q3 — Koordinator | Neue `tests/native_context_qa_coordinator.py`; eng begrenzter Adapter zum bisherigen Diagnose-Parent | Keine versteckten Doppel-/fehlenden Scans; A/B/C kumulativ gemessen; Worker weiterhin genau einmal und unverändert begrenzt |
| Q4 — lokale und kleine native Gegenproben | Neue isolierte Tests für Budget, CPU-Übergabe, Teilberichte und Pfadaustausch | Tatsächliche Limits/Exit/Reaping nachgewiesen; kein alter Task58-/Task60-Gesamtlauf als Beschäftigung erneut gestartet |
| Q5 — genau eine vollständige Qualifikation | Eingefrorene Quellen, geschlossener vollständiger historischer Bestand, bestehendes 1024-Profil | A1/A2/A3/B/C alle beendet, externe Exitbeobachtung, Daten unverändert, vollständige Kosten- und Platzbilanz |
| R1 — C/B fertig integrieren | Bestehender C-Speicher-/B-Nachweisplan; keine neue Mathematik | Pflichtwachstum und Original-/Snapshot-/Featuregleichheit, Gesamtbudget, voller Nachweisbesitz und Restore tatsächlich bestanden |
| R2 — Updater-Einführung | Vorhandene `deploy/repair_context_updater.sh`, `deploy/update_server.sh`, `scripts/verify_context_runtime.py` und zuständige Tests | Geprüfter B/C-Einstieg auch im Installer; frischer Online-/Stillstandscheck, keine 64-MiB-Speicherabkürzung oder ungültiger alter D4-Fallback |
| R3 — Release | Finale Suite/Review, frisches Backup und tatsächlich ausgeführter Restore, exakter Git-Stand | Erst root-eigenen Updater kontrolliert ersetzen, danach normaler exakter App-Update; Hashes, App, Caddy, Timer und beide Healthchecks verifiziert |

Die neuen Dateinamen sind Planstellen, noch keine existierenden Implementierungen.
Vor jedem Patch ein enger Aufgabenbrief, danach Review des tatsächlichen Diffs.
Der Root-Bearbeiter besitzt Git/Serverintegration. Keine zusätzliche Delegation
oder Arbeit gestartet durch dieses Dokument.

Q5 verwendet ausdrücklich den vorhandenen versiegelten Task61-Ausgangsbestand
mit 270233600 Byte, nicht automatisch die inzwischen rund 477 MiB große
Live-Datenbank. Der aktuelle reale Release-Bestand und das vollständige
Pflichtwachstum werden in R1 gesondert frisch aufgenommen und geprüft. Das
kleinere Diagnoseresultat darf diese Abnahmen nicht ersetzen.

### P0-Regressionsmatrix

- A verbraucht durch zwei Kinder zusammen mehr als 300 CPU-s: STOP, obwohl
  jedes Kind einzeln unter 300 bleibt. Unverbrauchte C-Zeit hilft A nicht.
- Neustart/zweiter Tab/zweiter Koordinator/gleicher Auftrag: kein frisches Budget.
  Fehlende, gekürzte oder umgeschriebene Journale nicht neu initialisieren.
- Bootstrapkosten, sehr schneller Kind-Exit, CPU während Ausgabe/Nachprüfung,
  abgelaufene Gesamtfrist, Uhr-/Bootwechsel: keine verlorenen Kosten/Fristen.
- Kind-Exit 0 ohne Nachprüfung, abgeschnittener Kontrollbericht, Teilwrite,
  fehlgeschlagenes fsync, Signal, OOM, unreaped child: kein Erfolg/Refund.
- Dateiinhalt bei gleichem Namen/Count ändern, Inode/Eltern tauschen, Hardlink,
  Symlinkziel, unbekannte Datei oder historische Journalzeile ändern: erkannt.
- Genau bekannter historischer FIFO wird nur metadatengebunden; zweiter,
  ausgetauschter oder aktiver FIFO bleibt abgelehnt.
- Alter Workeraufruf, Quelldaten, 1024-Profil und fachliche Ergebnisse bleiben
  exakt. Der Qualifikationsbericht behauptet weder volle 490000-Zusatzbelege
  noch abgeschlossene C/B-/empirische Freigabe.
- Produktionsgrenze: Übergröße, fehlender passender Nachweis oder unvollständige
  Online-Sicherung verhindert den App-Stopp. Ein Fehler nach Stilllegung startet
  nicht ungeprüft neu; bestehende Marker-/Wiederherstellungsregeln bleiben maßgeblich.

## 7. Releasegrenzen und bewusst kein neuer Nebenweg

Der Reparaturbranch besitzt derzeit einen 1-GiB-Sealed-File-Updater, während
C den größeren vollständigen aktiven 4-GiB-Satz getrennt regelt. Diese beiden
Größen sind nicht austauschbar. R1/R2 müssen den tatsächlich unterstützten
Eingangsmodus und die vollständige B/C-Generation gemeinsam binden. Ein
`MAX_IMAGE=4 GiB` ohne vollständigen passenden Leser/Nachweis reicht nicht.

Der erste Updateraustausch muss selbst den passenden neuen Prüfweg verwenden;
der aktuelle Installer mit zu teurem kaltem D4-Aufruf kann sich nicht allein
durch einen Git-Push erfolgreich installieren. Nie den Kontextcheck abschalten,
nie ein Checkout-Skript ungeprüft als root ausführen und nie das App-Repository
direkt fast-forwarden, um den vorgeschriebenen Updateweg zu umgehen.

Daily3 bleibt davon getrennt. GitHub-main enthält seine Dokumentation
(`f84d9a6`, beim letzten Abgleich); die beauftragte Funktionsentwicklung ist
noch offen. Diese Planung führt weder den VPS-Pull noch einen Testlauf aus.

## 8. Erfolgsmessung, P1/P2 und nächste Entscheidung

Früher Erfolg: neue Gegenproben zeigen null Budget-/Frische-/Custody-Verstöße;
das eine vollständige native Diagnosepaket schließt innerhalb seiner Hülle ab.
Späterer Erfolg: C/B-Abnahmen und der kontrollierte Updateweg funktionieren auf
dem tatsächlichen Release-Datenstand. Kein Lieferdatum vor dieser Messung;
900 Sekunden sind eine Abbruchgrenze, keine versprochene Laufzeit oder Fertigstellungszeit.

P1: knappe Admin-Fortschrittsanzeige mit Phase, verbrauchter/reservierter CPU,
Frist und letztem vollständigem Kontrollpunkt. P2: spätere Aufbewahrungsstrategie
mit eigener Freigabe; keine Historienbereinigung für einen grünen Test.

Zur Umsetzung neu freizugeben: gemeinsamer V2-Koordinator, genau ein zusätzliches
900-CPU-/900-Wandsekunden-Engineeringpaket und der exakt begrenzte historische
FIFO-Metadatenvertrag. Keine neue C/B-, Echtgeld-, Modell- oder Deploymentregel
und keine Neufreigabe der schon akzeptierten Daily3-Übernachtregel.

## 9. Technische Grundlagen

Ein CPU-Limit gilt für einen Prozess; Ressourcen eigener und beendeter,
abgewarteter Kindprozesse werden getrennt bereitgestellt. Deshalb sind
Phasenlimits allein kein gemeinsamer Verbrauchsnachweis.
[Python resource](https://docs.python.org/3/library/resource.html)

CPU-Zeit und abgelaufene Zeit sind unterschiedliche Größen; für die gemeinsame
Deadline wird eine geprüfte Bootzeitbasis verwendet, kein wiederholt neu
gestarteter relativer Timer.
[Python time](https://docs.python.org/3/library/time.html)

Ein Online-Abbild benötigt eine vollständig abgeschlossene konsistente Sicherung;
ein normales Kopieren der gleichzeitig beschriebenen Datenbank ersetzt sie nicht.
[SQLite Online Backup API](https://www.sqlite.org/backup.html)

Quellen am 13.09.2026 gelesen. Historische native Zahlen stammen aus den konkret
verlinkten Projektbelegen, nicht aus heute wiederholten Messläufen.

Dokumentationsprüfung dieser Fortsetzung: interne Dateiverweise aufgelöst,
Teilbudgets 300+240+60+300=900 und Scan-Hochrechnung unabhängig von Wandzeit
nachgerechnet, `git diff --check` ohne Befund. Das ist eine Eigenprüfung des
Plans, kein unabhängiges Architekturreview oder bestandener Produkt-/Nativtest.
