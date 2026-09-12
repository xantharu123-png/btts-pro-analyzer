# Task 18 - unabhängiges C1-Kopierreview

12. September 2026. Reviewer: `c_copy_review`. Nur neue synthetische
Gegenproben und dieser Bericht; keine Produkt-/Altowner-/Git-/VPS-Änderung.
Die C-Freigabe stammt aus dem aktuellen Umsetzungsplan, nicht aus dem eingefrorenen
älteren Satz "noch nicht freigegeben" in der Entscheidungsvorlage.

## Abschlussurteil für den korrigierten lokalen C1-Baustein

**F1 und F2 geschlossen** auf `copying.py`
`27d4c8887756aeeb8f8041744814b6c9d09e576427e8f62ef9ef09c64ba129be`.
Keine weiteren Critical/Important-Befunde innerhalb des ausdrücklich
versiegelten Standalone-/privaten-Copy-Vertrags gefunden. Das ist eine
lokale Bausteinfreigabe, kein Abschluss von C, kein B-Nachweis und kein
globaler/nativer Quota- oder Ressourcen-PASS.

Der korrigierte Stand hält den exklusiv erzeugten Ausgabe-FD bis nach der
Verifikation; SQLite öffnet ihn nur noch read-only. Die eigentliche Rawkopie
liest ebenfalls über einen gehaltenen FD, bindet FD/Pfad und prüft tatsächlichen
Bytefortschritt einschließlich Shortwrites. Der tatsächliche rohe `01/01`-Header
wird vor `_HeldRead`/Schema/Seitenzugriff geprüft. Ein ursprünglicher erwarteter
Source-SHA ist verpflichtend; vollständige Source-/Copybytes müssen denselben
SHA besitzen. Der komplette typisierte Vergleich bleibt ein eigenständiger
zusätzlicher Nachweis. Windows-spezifisch verschiedene FD-/Pfad-ctime-Semantiken
werden nicht gleichgesetzt: die gesamte Pfadserie einschließlich ctime und
die gemeinsamen FD-/Pfadfelder bis mtime sind separat gebunden.

Bei beiden Zielaustausch-Gegenproben am ersten tatsächlichen `os.write` verhinderte
nun der offen gehaltene Windows-Handle den Dateiaustausch. Die alten Bytes blieben
unverändert, der erfolgreiche neue Copyhash entsprach dem erwarteten Sourcehash.
Eine tatsächlich vollzogene Ersetzung einer offenen Datei unter Linux ist hier
**nicht** ausgeführt worden. Der Source-Replacement-Fall bleibt ein ausdrücklicher
Windows-Skip. Die WAL-Probe weist nun Ablehnung **ohne** neu erzeugte
Quellbegleitdateien nach.

### Exakter Abschlusslauf

Unabhängig ausgeführt: **75 passed, 1 skipped in 9.04 s**, keine Warnungen.
Aufteilung: 17 dauerhafte Copytests, 42 Inventorytests, 17 unabhängige FD-Proben
(davon der eine Windows-Source-Replacement-Skip). Neue, vorher nicht vorhandene
Pfade: `--basetemp=.pytest_tmp/copy-independent-review-20260912-ccr01-run5`
und `--junitxml=.pytest_tmp/copy-independent-review-20260912-ccr01-run5.xml`,
JUnitfamilie `xunit1`. Kein überschriebenes oder wiederverwendetes Testverzeichnis.

| Datei/Evidenz | SHA256 beim Abschluss |
| --- | --- |
| `context_storage_v2/copying.py` | `27d4c8887756aeeb8f8041744814b6c9d09e576427e8f62ef9ef09c64ba129be` |
| `context_storage_v2/inventory.py` | `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b` |
| `context_storage_v2/contracts.py` | `d0c8d94c89a608fc7b3c59755cbe97c76ec79d66e53d2bb235608f341364fcf3` |
| `tests/test_context_storage_copying.py` | `3dff14fcc23364cb9b04adfa853df77162ff2cb7c2dd6b4f71ded10032a1a6de` |
| `tests/test_context_storage_inventory.py` | `a5d4a78069b52eb3c4a402b7e90c2d6559b50de62fd00301cef89d9db9de1871` |
| `.pytest_tmp/copy-independent-review-20260912-ccr01/test_copy_review_fd.py` | `b084d74d17279e6eff2178ba30c6f0b63cfb4c34bec4c9808701b1a69de83855` |
| `.pytest_tmp/copy-independent-review-20260912-ccr01-run5.xml` | `ff2ce2dfe537545be18aad43b2945fe3d64e1d310573124760450a0a474dc64c` |

Die unabhängigen FD-Proben prüfen vollständige Rawdateien/alle typisierten
Inventare in UTF-8/UTF-16le/UTF-16be einschließlich NUL/0x1a/Zeilenumbrüchen,
leere Pflicht- und vollständige Schemata, Sollhashablehnung vor Ausgaben,
WAL-Nebenwirkungsfreiheit, Shortwrites/Nullfortschritt und tatsächlich auf
4096 Bytes begrenzte Raw-I/O-Anforderungen. Echte commit-/rollback-/script-
Transaktionswechsel und close während des ersten Write führen ohne Receipt zum
Abbruch; die Sourcebytes bleiben unverändert. Fehlversuchsausgaben werden nicht
als vollständig ausgegeben oder automatisch gelöscht.

Frühere korrigierte Probe: run3 **12 passed/1 skipped in 2.95 s** mit zwei reinen
JUnit-Metadatenwarnungen; run4 **16 passed/1 skipped in 3.41 s**, ohne Warnungen.
Beide waren bereits auf demselben unveränderten Copy-SHA, sind aber keine
zusätzlichen nativen Pflichtwiederholungen. Die nachfolgenden Abschnitte bewahren
die ursprünglichen Findings und deren tatsächliche RED-Evidenz.

## Erster exakt geprüfter Stand

| Datei | SHA256 |
| --- | --- |
| `context_storage_v2/copying.py` | `d3de42233878e9e1f6d621044f0f86cfc42cc05e0340d47cdea4a536694dec13` |
| `context_storage_v2/inventory.py` | `7e099cd9ed5e5b336519a23cc891e85c2136dda9fa6324c6f433f61bb37e967b` |
| `context_storage_v2/contracts.py` | `d0c8d94c89a608fc7b3c59755cbe97c76ec79d66e53d2bb235608f341364fcf3` |
| `tests/test_context_storage_copying.py` | `ce63b22b933a28e2dd0c156819cb156a567a2bc8b3e8872b404f1ac71c840fc5` |

Zusätzlich vollständig gelesen: C-Entscheidung und Umsetzungsplan,
`context_runtime_transaction.py`, relevante unveränderte Schema-/Pfadowner.
Runtime der eigenständigen Proben: Windows, Python 3.12.14, SQLite 3.53.1.

## F1 - bestehende Datei kann vor späterer Ablehnung überschrieben werden

**Important, konkret reproduziert.** Im ersten Stand schließen Zeilen 184-185
den exklusiv neu angelegten Ausgabe-FD. Zeile 188 öffnet denselben Namen danach
erneut schreibend mit SQLite. An diesem echten Wiederöffnungspunkt wurde das
leere neue Ziel durch einen Hardlink auf eine bereits bestehende synthetische
Datenbank ersetzt. Die echten SQLite-Operationen überschrieben deren Bytes,
bevor die nachträgliche `st_nlink`-Prüfung ablehnte. Bei einem regulären
Dateiaustausch wurde sogar ein `CopyReceipt` zurückgegeben.

Die Probe verändert nur das Dateisystem am beobachteten Öffnungspunkt. Sie
ersetzt weder SQLite-Ergebnisse noch Inventare/Integritätsprüfungen.

- Vorheriger SHA: `1c69ab927234720fbfd53c3f1c2b2cb38694d51d1bac31774860b1ebe5c8acd6`.
- Nachheriger SHA: `331869df34b8be0ce8a2fbd97ea9a411d3b8864eff7cb3634093596eae2ae417`.
- Beide Gegenproben verletzt; bestehende synthetische Nutzdaten geändert.

Enger akzeptabler Fix: ausschließlich bereits versiegelte standalone Eingabe;
gehaltene Quell-/Ziel-FDs, blockweise vollständige Rawbytes, keine schreibende
SQLite-Wiederöffnung des Ausgabewegs. Beide FD-/Pfadidentitäten vor/nach
Arbeitsschritten binden. Den tatsächlichen erwarteten Quellhash vom versiegelnden
Owner vorgeben lassen; Hashgleichheit ersetzt dessen Autorität nicht. Quelle und
fertige Kopie danach unabhängig mit dem vollständigen Typ-/Schlüssel-/Byteinventar
vergleichen. Eine Pfadzeichenfolge allein bindet keine bereits offene Verbindung.

## F2 - geschlossene WAL-Datei erzeugt beim Ablehnen Quellbegleitdateien

**Important, konkret reproduziert.** Eine ordentlich geschlossene/checkpointete
WAL-Datenbank hat weiterhin Headerbytes `02/02`, aber zunächst keine `-wal`-/`-shm`-
Datei. `_no_companions` akzeptiert sie zunächst; die nachfolgende `_HeldRead`-
Schemaabfrage lässt echtes read-only SQLite die Begleitdateien neben der Quelle
erzeugen. Erst eine spätere Prüfung lehnt ab. Die zugesicherte Quellennebenwirkungs-
freiheit gilt damit an dieser Ablehnungsgrenze nicht.

Fix: den tatsächlichen Rohheader über den gebundenen Read-FD lesen und
Standalone-Header `01/01` sowie gültige Seitendimensionen vor `_HeldRead` und
jedem SQLite-Schema-/Seitenzugriff verlangen. Vorhandene Begleitdateien weiter
vor jedem potenziellen Recovery-Zugriff ablehnen.

## Unabhängige RED-Evidenz

Probe: `.pytest_tmp/copy-independent-review-20260912-ccr01/test_copy_review.py`,
SHA nach Ergänzung der siebten Probe
`7275b0e7c3277021ada780214621f9d256bd7076d7984e0a33966b836ee68264`.
Jeder Lauf nutzte ein eigenes zuvor nicht vorhandenes `--basetemp` und JUnitziel.

- `copy-independent-review-20260912-ccr01-run1.xml`: **2 failed, 3 passed,
  1 skipped in 0.88 s**. Beide Zielaustauschproben RED; vollständiges leeres
  Pflichtschema und vollständiges leeres optionales Schema kopiert; deserialisierte
  Nicht-Dateiquelle abgelehnt.
- `copy-independent-review-20260912-ccr01-run2.xml`: **1 failed, 6 deselected
  in 0.31 s**. WAL-Header-Gegenprobe RED.
- Der Source-Replacement-Test wurde ausdrücklich übersprungen, weil Windows
  `os.replace` auf der offenen SQLite-Quelle verweigerte. Das ist kein ausgeführter
  Linux-/VPS-Nachweis derselben Austauschoperation.

Root erhielt beide Befunde vor der Korrektur. Die historischen RED-Proben bleiben
erhalten; die separate FD-Regression und der oben dokumentierte Abschlusslauf
prüfen den korrigierten Stand. Der erste Stand selbst wird nicht nachträglich
als grün umgedeutet.

## Kleinster nächster Schritt zur globalen C-Ressourcenhülle

Ein einziger vorbereitungsweiter Budgetowner mit exklusivem Job-Lock und festen
reservierten Slots ist ein geeigneter nächster Prototypabschnitt. Alle Writer,
Teilprozesse und Wiederholungen müssen dieselbe Reservierung teilen; kein neues
8-GiB-Budget pro Datei oder Versuch. Geladene/reservierte Bytes sowie begrenzte
Metadaten bleiben belegt, auch wenn eine Datei bereits unbenannt ist, solange
ein Writer/Handle sie noch hält. Der Diskwalk dient dem Abgleich, nicht als
alleinige Zuteilungsgrenze.

Ein vollständiges unveränderliches Generationsverzeichnis bindet Quellen,
eigene Indizes, Referenzblöcke und Manifeste samt Bytezahl, Reihenfolge und
Identität an **einen** aktiven Eingabesatz von höchstens 4 GiB. Sämtliche neuen
QA-/Aufbau-/Ausgabeartefakte einschließlich Fehlversuchen und reserviertem
Maximalwachstum teilen höchstens 8 GiB. Der alte vollständige Stand bleibt
erhalten; Freigabe erfolgt erst nach vollständiger Verzeichnis-/Coverageprüfung.

Feste SQLite-Dateislots allein lösen die versteckten Allokationen nicht:
`max_page_count` begrenzt die einzelne DB; `journal_size_limit` begrenzt keine
Transaktionsspitze. `temp_store` ist mit dem tatsächlichen SQLite-Build abzugleichen;
`temp_store_directory` ist kein harter Quota-Ersatz. [SQLite PRAGMA-Verträge](https://www.sqlite.org/pragma.html).
SQLite verwendet unter anderem getrennte Statementjournale, TEMP-Datenbanken,
temporäre Indizes und Mehrdatenbankjournale. [SQLite Temporary Files](https://sqlite.org/tempfiles.html).

Vor einem globalen Claim müssen alle solchen Schreibpfade entweder ausdrücklich
in demselben Budgetowner begrenzt sein oder in einem tatsächlich verifizierten
No-Disk-Temp-Profil entfallen. Ein journalfreier Weg ist höchstens für vollständig
verwerfbaren privaten Aufbau vertretbar, nicht für Quelle/veröffentlichten Stand:
`journal_mode=OFF` hebt Rollback und Absturzatomizität auf. [SQLite journal_mode](https://www.sqlite.org/pragma.html#pragma_journal_mode).

Die mindestens 4 GiB freie Reserve frisch vor und während jeder Reservierung
prüfen, zusätzlich zu vollständigem Backup-/Rollbackbedarf. Eine vorallozierte
Reserve-Datei ist belegter, nicht freier Platz. Eigene vorher reservierte
Worst-Case-Schreibmengen lassen sich begrenzen; fremde Hostwriter können zwischen
Messpunkten freien Platz verbrauchen. Ohne nachgewiesenen nativen Owner daher
keine kontinuierliche hostweite Garantie behaupten.

Dieser Review autorisiert weder OS-Dienst/VM/Quota noch Geheimnisse, neue Limits,
Migration, Veröffentlichung oder Serverarbeit. Vollständige reale Wachstumsprofile,
native RAM/CPU/Plattenmessung, B-Isolierung/Authentisierung/Coverage, Restore und
die drei abschließenden nativen Wiederholungen bleiben getrennte offene Gates.
