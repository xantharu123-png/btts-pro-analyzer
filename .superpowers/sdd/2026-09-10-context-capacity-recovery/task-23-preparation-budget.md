# Task 23: konservative Vorbereitungs-Kostenbuchung

Stand: 2026-09-12. Owner: `c_snapshot_review`. Ausschließlich neuer,
stdlib-basierter Accounting-Baustein; keine Einbindung in eine produktive
Vorbereitung, kein B-Nachweis und keine native Ausführungsfreigabe.

## Vertragsbasis und Grenze

Vollständig gelesen wurden C
`docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md`, B
`docs/superpowers/specs/2026-09-12-versionierte-pruefnachweise.md` und der globale
Integrationsplan
`docs/superpowers/plans/2026-09-12-kontextspeicher-gesamtintegration.md`.
Die Ausführungspläne halten die inzwischen erteilten Benutzerfreigaben fest;
historische Vorschlagsformulierungen der Specs sind keine neue Freigabeanfrage.

Root bestätigte diese enge Bausteingrenze: Settlement ist ausschließlich eine
Buchung für einen später vertrauenswürdig gemessenen vollständigen Prozessbaum.
Ein offenes Ticket nach unbekanntem Crash bleibt vollständig belastet und darf
in V1 dauerhaft gesperrt bleiben. Registry, Rootschutz, authentische Messung und
nativer Supervisor werden hier nicht durch Behauptungen oder Booleans ersetzt.

## Neue Dateien und eingefrorene Bytes

| Datei | SHA256 |
| --- | --- |
| `context_preparation_budget.py` | `fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478` |
| `tests/test_context_preparation_budget.py` | `91f820410422a1a8d21b419d901488c6d33264583a367abcb4f5925e7fc5e43b` |

Keine Produktimporte; keine bestehenden APIs, Produktdateien, Owner-Tests oder
Ausführungspläne verändert. Keine Git-, SSH-, Deployment- oder Serveraktion.

## API und Buchungsregeln

- `BudgetIdentity(input_digest, execution_digest, runtime_digest,
  installation_digest, profile_digest)` verlangt alle fünf exakten
  kleingeschriebenen SHA256-Werte. Die Integration muss die tatsächlich
  zutreffenden Identitäten ermitteln; das Modul beglaubigt deren Herkunft nicht.
- `PreparationBudget.create(directory_fd, identity)` legt ausschließlich einen
  neuen, exklusiven Journaleintrag an. Eine spätere geschützte Registry muss die
  erstmalige Anlage autorisieren. `open_existing(directory_fd, identity)` legt
  fehlende Dateien niemals an und initialisiert leere oder beschädigte Dateien
  niemals erneut.
- `reserve(portion_digest, cpu_ns)` bucht vor Ticket-Rückgabe eine positive
  CPU-Reserve von höchstens 300 Sekunden. Die Summe aus kumulativ bereits
  gebuchter CPU und offenem Ticket darf 1800 Sekunden nicht überschreiten.
  Wiederholungen derselben Portion erhalten unterschiedliche Journaltickets,
  aber niemals ein neues Gesamtbudget.
- `settle_claim(ticket, cumulative_cpu_ns=..., measurement_digest=...)` nimmt
  ausschließlich einen kumulativen vollständigen Auftragskosten-Claim entgegen,
  keinen isolierten Bestwert oder frei rücksetzbaren Portionszähler. Das Delta
  muss in die offene Reserve passen. Ticket/Identität/Sequenz müssen exakt
  stimmen; Mess-Claim-Digests dürfen nicht wiederverwendet werden. Die Buchung
  kann die ungenutzte Reserve einmalig aus dem Accounting entfernen. Das ist
  ausdrücklich kein Beweis der Messung und keine native Refundfreigabe.
- `stop_unmeasured()` hinterlässt einen terminalen Stop ohne Rückerstattung
  einer unbekannten Reserve. Ungültige bzw. überhöhte CPU-Claims erzeugen
  ebenfalls einen dauerhaften Stop, ohne den offenen Betrag freizugeben.
- `snapshot()` liefert historische Accounting-Daten. Selbst positive
  `remaining_cpu_ns` oder `status == "accounting-open"` erteilen keine
  Ausführungserlaubnis und sind keine aktuelle Deadline-/Messvalidierung.
- `close()` und Context-Manager schließen die gehaltenen Deskriptoren.

Alle Mengen, Versionen und Sequenzen sind echte Python-Integer in festen
Bereichen; `bool`, Float, String, implizite Konvertierungen und überlange
Integerdarstellungen werden abgewiesen. Identität und ausgegebene Dataclasses
sind von internem Zustand getrennt; Mutation einer ausgegebenen Instanz ist
keine Mutationsautorität über das Journal.

## Zeit, Crash und Parallelität

Die erste gültige Clock-Beobachtung setzt einmalig die Deadline auf
`boot_before_ns + 3600 * 10**9`. Ein Reopen erhält diese Deadline inklusive
Unterbrechung und Ruhezeit. Der Linux-Pfad nutzt den Boot-ID-Wert sowie
`CLOCK_BOOTTIME`, der Suspend-Zeit einschließt, und klammert eine Realtime-Lesung
zwischen zwei Bootzeit-Lesungen ein. Jede Klammer muss höchstens 50 ms breit sein.
Die Schnittmenge aller beobachteten Realtime/Bootzeit-Offsets muss bestehen
bleiben; Bootwechsel, erkennbare Rücksprünge, widersprüchliche Uhren,
unmessbar breite Beobachtungen und Deadline-Ablauf werden konservativ gestoppt.
Es gibt keinen laufend erneuerten 3600-Sekunden-Zeitraum und keine anwachsende
Uhrsprungtoleranz. Zusätzliche Nachprüfungen nach `fsync` behalten ihre letzten
Beobachtungen innerhalb des Handles, auch wenn sie keinen eigenen Datensatz
erzeugen. Die Persistenzgrenze bleibt die letzte vollständig geschriebene
Journalbeobachtung; Voll-VM-Rollback ist nicht gelöst.

Zeit wird nach dem Sync erneut geprüft: Läuft die Deadline während einer
Reservierungsbuchung ab, wird kein Ticket ausgegeben. Die bereits geschriebene
Reserve bleibt vollständig belastet. Ein aus einer anderen Öffnung stammendes
offenes Ticket ist in V1 dauerhaft gesperrt, auch wenn der Aufrufer anschließend
einen plausibel aussehenden Settlement-Claim vorlegt. Es gibt keinen
Resume-/Repair-/Reset-Pfad für dieses Ticket.

Eine nichtblockierende Operationssperre verhindert gleichzeitige Methoden auf
demselben Handle; eine lokale Inode-Registry verhindert zweite Handles im
selben Prozess. Der native Linux-Pfad hält zusätzlich `flock(LOCK_EX|LOCK_NB)`
für die Lebensdauer des offenen FDs. Geerbte Handles werden anhand der
tatsächlichen Prozess-ID verweigert.

## Bounded Journal und tatsächliche Datei-I/O

Format V1 ist ein geschlossenes kanonisches ASCII-JSON-Zeilenprotokoll mit
Sequenz, Vorgänger-Digest und eigenem Digest. Nur `init`, `reserve`,
`settle-claim`, `stop` sind zulässige Ereignisse. Maximal 256 Datensätze zu je
4096 Bytes, maximal 1 MiB pro Journal; Dateilesungen erfolgen in begrenzten
Chunks. Reservieren benötigt zusätzlich Platz für Abschluss und Stop-Marker.
Es gibt keine Kompaktierung, keine automatische Rotation und keine zweite
Budgetdatei bei Erschöpfung.

Parserprüfungen weisen fehlende/zusätzliche Felder, doppelte JSON-Schlüssel,
unbekannte Ereignisse/Versionen, nichtkanonische Kodierung, falsche Hashes,
Reihenfolgefehler, Duplikate, Float/Bool-Zahlen, Größenüberschreitungen und
unvollständige letzte Zeilen zurück. Die Hashkette belegt nur interne
Konsistenz, nicht Authentizität oder Aktualität gegenüber einem Angreifer.

Schreibreihenfolge: begrenzt lesen und validieren, vorgeschlagenes gesamtes
Journal vorprüfen, vollständig appendieren, Datei synchronisieren, im nativen
Pfad auch das gehaltene Verzeichnis synchronisieren, Ergebnisbytes erneut
prüfen, Uhr nachprüfen, erst dann Ticket zurückgeben. Bereits geschriebene
Teilbytes bleiben bei Fehler erhalten. Auch ein vollständig sichtbarer
Reservierungssatz mit fehlgeschlagenem Sync liefert kein Ticket; auf späterem
Reopen bleibt sein offener Betrag gesperrt. Weder beschädigte Daten noch eine
leere Datei nach gescheiterter Initialisierung werden gelöscht oder repariert.

Der öffentliche Erwerb ist Linux-only: gehaltenes dupliziertes Verzeichnis-FD,
relative deterministische Namensauflösung, `O_NOFOLLOW`, `O_CLOEXEC`,
`O_NONBLOCK`, exklusive Neuanlage, private caller-eigene Datei, reguläre
Single-Link-Datei, laufender Inode-/Directory-Entry-Vergleich und Dateisperre.
Diese Mechanismen sind keine Parent-Seal-/Root-Namespace-Authentifizierung.

## Tests und klare Evidenztrennung

Finaler isolierter Lauf auf dem gebündelten Windows-Python:

```powershell
$env:PYTHONPATH='C:\Projekt\BetBoy\betboy-app\.venv\Lib\site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pytest tests/test_context_preparation_budget.py -q -p no:cacheprovider -o junit_family=xunit1 --basetemp=.pytest_tmp/task23-budget-run-20260912-3 --junitxml=.pytest_tmp/task23-budget-run-20260912-3.xml
```

Ergebnis: **67 passed, 1 skipped**, Pytest 5,28 s; JUnit 68 Fälle, 0 Fehler,
0 Fehlschläge, 1 Skip in 5,231 s. JUnit-SHA256:
`f836875765c8216e873da8ec3537a984c719cbb8f7788ced77924baf2f5991e4`.

Die grüne lokale Evidenz umfasst tatsächliche Windows-Dateideskriptoren,
Append-Lesezyklen, `fsync`, Dateiinhaltserhalt bei echten Teilwrites, Wiederöffnen,
Struktur-/Identitätsprüfung, Shared-Handle-Thread-Konkurrenz und externe
Dateiveränderungen. Kernel-Uhrdaten werden in diesen Protokolltests ausdrücklich
simuliert; Fehler nach Teilwrite und Sync-Ausfälle werden injiziert. Diese
Tests sind weder ein echter Stromausfallnachweis noch Linux-Dauerhaftigkeits-,
Cross-Process-Lock- oder Prozessbaum-Messevidenz.

Eine separate native Probe würde echte Linux-FDs, Verzeichnis-`fsync`,
Kernel-Uhren und einen konkurrierenden Python-Prozess prüfen. Sie ist unter
Windows ausdrücklich übersprungen. Auch deren späteres Bestehen würde noch
keine vollständige native CPU-Messung oder C-Vorbereitung beweisen.

Erstlauf: 57 bestanden, 1 übersprungen, 1 falsche Kapazitätserwartung im Test.
Der Test hatte nach 126 Paaren fälschlich Erschöpfung verlangt, obwohl noch
Reservierung, Settlement und Stop passten. Die korrekte Grenze nach 127 Paaren
ist jetzt geprüft; keine Produktgrenze wurde gelockert. Danach kamen getrennte
Regressionsproben für nichtjournalisierte Nach-Sync-Uhren, echte gleichzeitige
Handle-Aufrufe, positive Uhrklammern und fehlgeschlagene Initialisierung hinzu.
Alle Läufe benutzten neue, zuvor nicht vorhandene Temp-/JUnit-Ziele.

## Bewusst offen: keine C/B-Abnahme

1. Geschützter dauerhafter Registry-Owner, exakte gebundene Eingabe-/Ausführungs-
   und Runtime-Abschlussidentitäten, Installations-/Profilauthentizität sowie
   Parent-Seals/Root-Namespace bleiben Integration. Ein deterministischer
   Identity-Dateiname verhindert weder privilegiertes Löschen und Neuanlegen
   noch Austausch des gesamten Journals oder vollständigen VM-Rollback.
2. Der spätere native Owner muss die gesamte Vorbereitung vor jeglicher
   eigentlicher Arbeit binden, einschließlich Bootstrap-Kosten, sämtlicher
   Kindprozesse, Writer, Prüfungen, Fehlversuche und Wiederholungen. Er muss
   Messbarkeit, authentische kumulative CPU und Quieszenz vor jeder
   Settlement-/Refundentscheidung tatsächlich herstellen. Dieses Modul nimmt
   lediglich einen entsprechend bezeichneten Claim entgegen.
3. Nativer Supervisor, Prozessgruppen-/Nachkommenkontrolle, harte CPU-/AS-/RSS-
   und Ausgabegrenzen, Deadline-Abbruch während laufender Arbeit sowie die
   globale 4-GiB-Eingabe-/8-GiB-Arbeitsbereich-/4-GiB-Freiraumkontrolle fehlen.
   Ein Accounting-Ticket löst keinen Prozessstart aus und autorisiert ihn nicht.
4. Echte Linux-Dauerhaftigkeit und Cross-Process-Tests, Crash-/FS-Verhalten und
   die Anbindung an einen geschützten Journal-Owner sind noch auszuführen.
5. Keine B-Nachweisausstellung/-Wiederverwendung, keine historische Semantik-
   Validierung, kein nativer Pflichtkorpuslauf, kein Deployment und keine
   Produktionsfreigabe ergeben sich aus diesen 67 lokalen Tests.

Nächster Schritt: unabhängiger Review dieser eingefrorenen Bytes durch Root;
danach Integration mit dem weiterhin erforderlichen geschützten nativen Owner.
