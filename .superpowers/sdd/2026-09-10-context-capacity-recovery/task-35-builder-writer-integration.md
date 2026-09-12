# Task 35 — kontrolliertes Writerprofil in den neuen C3-Buildern

Stand: 12. September 2026. Enger lokaler Integrationsstand; keine native
Kapazitäts-/Ressourcenabnahme, B-Publikation oder Produktionsfreigabe.

## Umfang und Ergebnis

Nur die neuen `context_storage_v2/history.py` und `context_storage_v2/tennis.py`
sowie ihre beiden Owner-Testdateien wurden geändert. Beide Builder benutzen
jetzt das unabhängig geprüfte, unveränderte `fresh-single-main-v1` statt eigener
SQLite-Writer. Vollständig gelesen wurden beide Builder und bisherigen Tests,
Task 22, Task 27, Task 32, die genehmigte C-Entscheidung und das konkrete Profil;
zusätzlich wurden die tatsächlichen refs-Connection-/Savepoint-Bedingungen
abgeglichen. Die veraltete Freigabeüberschrift der C-Vorlage hebt die bereits
erteilte ausdrückliche Freigabe nicht auf.

Unverändert bleiben alte Produktionsowner, Auswahl-/Quellregeln, D2-Sichtschutz,
kanonische Zeilen, Featurearithmetik einschließlich Python-Summationsreihenfolge,
vollständige Referenzen und Digestverfahren. Keine Änderung an
`sqlite_profile.py`, `refs.py`, `snapshots.py`, Supervisor/Guard, Produktionsroute,
Git oder Server. Root änderte separat ausschließlich die fünf Aufrufe in seinen
Integrationstests auf explizite 4-MiB-Testcaps; diese Datei gehört nicht zu
diesem Task und wurde hier nicht geschrieben.

## Abgestimmte Schnittstelle und feste Slots

Beide APIs haben ein **zwingendes** neues Schlüsselwort `main_cap_bytes` und
optional `owned_directory`. Es gibt keinen versteckten Default und keine
stillschweigende Rundung. Zulässig sind positive ganze 4096-Byte-Seiten innerhalb
von `limits.input_bytes`; der echte `SQLiteWriterPlan` verlangt zusätzlich
`2 * main_cap_bytes <= limits.workspace_bytes`.

```python
# Ausschließlich nach vollständiger äußerer Zulassung und Reservierung:
with build_history(
    receipts, directory=job_root, owned_directory=reserved_history_directory,
    cutoff=maximum_cutoff, tour="ATP", input_identity=input_digest,
    main_cap_bytes=history_main_cap, limits=limits,
) as history:
    with tennis_features_streaming(
        event, history, base, cutoff=maximum_cutoff, work_directory=job_root,
        owned_directory=reserved_feature_directory,
        main_cap_bytes=feature_main_cap, limits=limits,
    ) as features:
        consume_complete(features)
```

`owned_directory` muss ein vorhandenes, leeres, gewöhnliches absolutes direktes
Unterverzeichnis des angegebenen Allocationroots auf demselben Device sein.
Der Builder legt in diesem Modus kein zufälliges Unterverzeichnis an. Der
NativeOwner muss diesen Modus zwingend benutzen und die Privatheit/Exklusivität
für die gesamte Lebensdauer einschließlich Seitendateien herstellen.

| Builder | Vorab bekannter Mainname | Zusätzlich zu reservierender Journalname | Cache |
| --- | --- | --- | --- |
| History | `history.sqlite` | `history.sqlite-journal` | 8192 KiB |
| Tennis | `features.sqlite` | `features.sqlite-journal` | 4096 KiB |

Vorhandene Main-, Journal-, WAL-/SHM- oder andere Einträge werden nicht als
eigener Zustand übernommen. Kein Resume, Dateiersatz oder Überschreiben. WAL/SHM
gehören nicht zum zulässigen Profil. Die EXCL-FD-/Namespace-Prüfungen des
unveränderten Profilowners gelten zusätzlich; dessen ausdrückliche private,
quieszente Namespacevorbedingung wird nicht durch eine race-free-Pfadzusage
ersetzt. Ein leeres Verzeichnis allein ist keine geschützte Capability.

Ohne `owned_directory` bleibt ein ausdrücklich **nur lokaler** Conveniencepfad
mit einem neu erzeugten Unterordner. Auf Erfolg liefern `HistoryView.path` bzw.
`StreamingTennisFeatures.path` den konkreten Mainpfad. Nach Fehler steht der
behaltene Verzeichnispfad in einer Exception-Note, auch bei Fehlern unmittelbar
nach seiner Erzeugung. Diese Note ist **kein Ersatz für die vollständige äußere
Enumeration und Inventur** sämtlicher lokaler Versuche und Artefakte.

## Build und unveränderte Lesebindung

1. Der Profilowner erstellt die neue Main exklusiv und liefert weiterhin
   **exakt TrackedConnection**. MEMORY ist seine erste SQL und wird gegen
   Readback und TEMP_STORE-Compilewert geprüft; DELETE/FULL, begrenzte Seiten,
   Cache, mmap=0 sowie Attach-/Workerthreadgrenzen bleiben geprüft.
2. `BEGIN IMMEDIATE` besteht vor der ersten DDL. Historys frühere getrennte
   Schema-Commits entfallen. Alle bisherigen Tabellen, Indizes und DML bleiben
   fachlich unverändert. Tennis nutzt unverändert die echten refs-Savepoints.
3. Beide Builder prüfen Profil und beobachteten lokalen freien Raum nach dem
   Schemaaufbau, während der bisherigen begrenzten Schreibschleifen und vor
   dem einzigen `commit_build()`. History prüft außerdem bei der vollständigen
   kanonischen Digestiteration. Tennis prüft zusätzlich während der vollständigen
   UNION-/DISTINCT-Refstreams, nicht nur einmal vor dem Refset-Aufbau.
4. `commit_build()` schließt die erfassten Writer-Cursor/Blobs, Verbindung und
   eigenen FD. Danach öffnet jeder Builder eine **neue tatsächliche RO-Main-
   Verbindung**. Kein reversibles query_only-Flag ersetzt den RO-Open.
5. Die neuen Reader setzen ebenfalls MEMORY als erste SQL, prüfen Readback 2
   sowie den bounded TEMP_STORE-Compilekatalog **vor jeder TEMP-Schemaarbeit**,
   behalten die jeweilige Cachegröße und explizite Maincap, mmap=0, threads=0,
   Attach-/Workerthreadlimit 0 und deaktivierte Extensions/Trusted-Schema.
   Defensive ist eingeschaltet. Die zusätzlichen Policyfelder werden in den
   bestehenden Storage-Epoch-Bindungen mitgeführt.
6. History behält seine bestehende private `_ReadConnection` und den exakt
   gebundenen Quellowner; Tennis behält exakt TrackedConnection für die echten
   C2-Refreader. Gehaltene Lesetransaktion, Generation, Dateiidentität,
   Schema-/TEMP-/Journal-Epochen, vollständige Limits, Source-/History-Lebensdauer
   und permanente Invalidation bleiben erhalten. Es werden keine Type-Gates
   umgangen und keine Verbindung eines bereits gehaltenen Quellowners umgestellt.

Auch benötigte Quellreader müssen vom äußeren geschlossenen Workflow **vor**
ihrem eigenen Pinning richtig eingerichtet werden. Dieser Task ändert keine
bereits validierte Quellverbindung und behauptet keine neue B-/D2-Autorität.

## Fehler, Aufbewahrung und exakte Claimgrenze

Tennis verwendet nun wie History keine automatische Artefaktlöschung mehr.
`close()` beendet die jeweilige Lesebindung, löscht aber keine neue Main und
entlastet keinen globalen Slot. Auch der fehlgeschlagene Aufbau bleibt erhalten;
der nächste Convenienceversuch bekommt einen neuen Pfad, der feste Ownedpfad
kann nicht als Resume wiederbenutzt werden. Diesen engen Lifecyclewechsel hat
Root ausdrücklich bestätigt. Keine alte Datei wurde gelöscht.

Die Tests unterscheiden ausdrücklich:

- Fehler **vor** Commit: auch neue DDL wird vollständig zurückgerollt, keine
  Teil-View und kein Teil-Featureobjekt; neuer fehlgeschlagener Main bleibt.
- Fehler **nach** erfolgreichem Build-Commit, etwa verlorener Reserve oder
  fehlgeschlagenem Readerprofil: vollständige Bytes können bereits vorhanden
  sein, aber kein Ergebnisobjekt wird ausgegeben. Diese unzugelassenen Bytes
  werden weder als erfolgreich publiziert markiert noch entfernt.

Main-M und Journal-M sind weiterhin nur eine lokale **logische Planung**.
max_page_count ist keine Journal-, Dateianzahl- oder physische Quota. NativeOwner
muss FSIZE, die geschlossene Datei-/API-Menge, sämtliche Inputs/Fehlläufe/Archive,
physische Allokation und Metadaten global bilanzieren und die unveränderten
CPU-/AS-/RSS-/Ausgabe-/Kosten-/Deadline-Grenzen durchsetzen. MEMORY erlaubt kein
zusätzliches RAM und keinen FILE-Fallback bei Speichermangel. Reconciliation
und vollständiger Worker-/Handleabschluss bleiben äußere Pflichten.

Die lokalen Freiplatzchecks beobachten die vereinbarte tatsächliche Reserve;
sie sind keine Garantie gegen fremde Schreiber zwischen Messpunkten. Der
NativeMonitor bleibt auch während langer nativer SQLite-Aufrufe zuständig.
4 GiB aktive Eingaben/8 GiB Gesamt-QA werden nicht pro History-/Tennisdatei neu
vergeben. Vorab bekannte Slots, lokale Dateilängen oder grüne Unit-Tests sind
keine globale oder native Zulassung.

## Lokale Evidenz

QA: neues vorhandenes venv `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`,
Python 3.12.14 / SQLite 3.53.1, Windows. `-B`, Plugin-Autoload aus, kein pytest-
Cacheprovider; jeder Lauf benutzt neue, nie zuvor vorhandene Basetemp-/XML-Namen.
Keine SSH-/native VPS-Ausführung und keine Löschung früherer Artefakte.

Erhaltene Zwischenevidenz:

- `task35-builders-01.xml`: **148 bestanden, 3 rot**, 106,58 s. Alle drei roten
  Annahmen betrafen nun verhinderte Reader-Journaländerungen: Defensive ließ
  OFF nicht zu, der echte Readback blieb `delete` bzw. `memory`. Die Tests
  bestätigen jetzt genau diese Verhinderung und die unveränderte Lesbarkeit.
  Die neuen Policy-Driftfälle prüfen zusätzlich tatsächliche Mutationen.
- `task35-builders-02.xml`: **212 bestanden, 1 rot**, 120,62 s. Der Test erwartete
  fälschlich FULL bei einer 64-KiB-Decke; die echte kleine neue Tennisdatei war
  nur **36.864 Bytes** groß. Der vollständige erfolgreiche Output blieb korrekt
  innerhalb der Decke. Nur die Erschöpfungsfixture wurde auf 24 tatsächlich
  normalisierte Spiele vergrößert; kein Produktcap wurde gelockert.
- `task35-newcases-03.xml`: **64 bestanden**, 157 bewusst nicht ausgewählte
  Fälle, 15,13 s. Gerichteter Zwischentest, keine vollständige Regression.

Finaler Kombilauf `task35-combined-04.xml`: **580 bestanden, 0 Fehler,
0 übersprungen**, Konsole 144,55 s, JUnit 144,529 s. Davon History 104,
Tennis 117, SQLite-Profil 93, refs 99, snapshots 96 und ref_chunks 71. Die
History-/Tennisdateien enthalten damit 151 erhaltene Fälle plus 70 neue Fälle.
Keine Warnung im finalen Konsolenergebnis. Dies sind lokale funktionale Tests,
kein kompletter Corpus-/Sieben-Tage-/C6- oder nativer Ressourcenlauf.

Tatsächlich ausgeführter finaler Befehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider tests/test_context_storage_history.py tests/test_context_storage_tennis.py tests/test_context_storage_sqlite_profile.py tests/test_context_storage_refs.py tests/test_context_storage_snapshots.py tests/test_context_storage_ref_chunks.py --basetemp=.pytest_tmp/task35-combined-bt-04 --junitxml=.pytest_tmp/task35-combined-04.xml
```

Diese Evidenznamen sind jetzt belegt. Jede Wiederholung braucht neue zuvor
nicht existierende Basetemp-/XML-Namen; vorhandene Ergebnisse werden nicht
überschrieben oder gelöscht. Produkt-/Testhashes wurden nach Abschluss erneut
gelesen und stimmen mit dem gestarteten, eingefrorenen Stand überein.

Geprüfte neue Fälle umfassen FIRST-SQL/Compileprüfung, genau eine Build-Epoche
vor DDL, abschließend tatsächlich geschlossenen Writer, echte Savepoints und
ausgeführte UNION-/DISTINCT-Abfragen mit nachgewiesenem TEMP B-TREE, vollständige
Cold-/v3-Byte- und Digestdifferentiale, feste Main-/Journalslots, fehlende/ungültige
Caps, fremde/nonempty/nichtdirekte Ownedpfade, reale SQLITE_FULL-Fehler und deren
vollständigen Rollback, beobachteten Reserveverlust während des Aufbaus sowie
vor/nach Commit, fehlgeschlagenes RO-Profil und Writer-/Reader-Policydrift.
Alle bisherigen fachlichen Fälle bleiben erhalten. Die große Einzelevent-
Fixture misst weiter ausdrücklich nur Python-Allokationen, nicht native RSS/AS.

Eingefrorene und final geprüfte Produkt-/Testbytes:

| Datei | SHA256 |
| --- | --- |
| `context_storage_v2/history.py` | `287ae422bdbd7925e0c09899d870a4ef953c5c11024c0dc7f98a11183a5158b8` |
| `context_storage_v2/tennis.py` | `da51aab436387021e2d2022bea71f6045c0b0e5f6a4f8efce64fa52a6f029698` |
| `tests/test_context_storage_history.py` | `af0472a429ab6f2dbae7e38147798a88bc983d88ce16d876383bf1e6a74e26b6` |
| `tests/test_context_storage_tennis.py` | `93a978984a8616dc832657388743f620dac7c02905238b1a4c6098e089325e9b` |
| Unverändertes `context_storage_v2/sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |
| `.pytest_tmp/task35-combined-04.xml` | `68971958fe34d33c9f299f7e5e82a9c29457dd2dac47728d3ff7730a2e13dbef` |
| `.pytest_tmp/task35-newcases-03.xml` | `913248a91d689a41056da63f2ffbc712fd35f2738f51eafbbd74469844c9da93` |
| `.pytest_tmp/task35-builders-01.xml` — erhaltene rote Testannahmen | `e30715b483dbbe1e7f704c126939663fc445093e2f8e29fa0051ef5d953c9375` |
| `.pytest_tmp/task35-builders-02.xml` — erhaltene falsche FULL-Erwartung | `2c96a547ff9de95a4a1332b18038dd7247e0dbe2ee7e47bf27d924301e0efd0f` |

Nächster Schritt: unabhängiges Review dieses Deltas und Roots bewusste globale
Ownerintegration mit festen Slots; danach kontrollierte echte native Messung
und vollständige C6-Profile. Kein Gesamtabschluss oder Rollout wird daraus
abgeleitet.
