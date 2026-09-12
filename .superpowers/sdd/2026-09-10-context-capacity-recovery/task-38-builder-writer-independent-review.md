# Task 38 — unabhängiger enger Review der Task-35-Builder

Stand: 12. September 2026. Unabhängiger lokaler Funktions-/Lebensdauerreview,
kein nativer C-Lauf, keine Ressourcenfreigabe, kein B-Nachweis oder Rollout.

## Urteil und geprüfter Umfang

Bei den nachstehend exakt gebundenen Task-35-Bytes wurde keine konkrete
verbliebene Produktabweichung innerhalb der untersuchten Buildergrenze gefunden.
Die 39 eigenen Gegenproben sind vollständig grün. Der ergänzende Kombilauf mit
den unveränderten Owner- und Root-Integrationstests ist mit 359 bestandenen
Fällen, null Fehlern und null Skips abgeschlossen. Alle geprüften Produkt- und
Testhashes wurden danach erneut gelesen und sind unverändert. Dieser enge
Review ist abgeschlossen; die äußeren Bedingungen unten bleiben offen.

Vollständig gelesen wurden History, Tennis, ihre beiden vollständigen
Owner-Testdateien, Roots Integrationstestdatei, der unveränderte SQLite-
Profilowner und der finale Task-35-Bericht. Die genehmigte C-Hülle und die
bereits gelesenen C-/B-Abgrenzungen bleiben unverändert. Root hat für den
ausdrücklich verlangten Altvergleich reine `git show`-/read-only Git-Abfragen
freigegeben. Es gab keinen Checkout, Git-Schreibvorgang oder Serveraufruf.

Geschrieben wurden ausschließlich die eigene ignorierte Probedatei und dieser
Report. Kein Produkt, kein Owner-Test und keine Task-33-Datei wurde im Review
verändert. Die Prüfung nutzt kleine tatsächlich neu erzeugte lokale Testdaten;
bestehende App-/Live-Daten wurden nicht geöffnet.

| Geprüfte Datei | SHA256 |
| --- | --- |
| `context_storage_v2/history.py` | `287ae422bdbd7925e0c09899d870a4ef953c5c11024c0dc7f98a11183a5158b8` |
| `context_storage_v2/tennis.py` | `da51aab436387021e2d2022bea71f6045c0b0e5f6a4f8efce64fa52a6f029698` |
| `context_storage_v2/sqlite_profile.py` | `05898adf9782ff06e2edcf33d45c94dd6ecce232ddba1f81ffcfaf65fca3d8bc` |
| `tests/test_context_storage_history.py` | `af0472a429ab6f2dbae7e38147798a88bc983d88ce16d876383bf1e6a74e26b6` |
| `tests/test_context_storage_tennis.py` | `93a978984a8616dc832657388743f620dac7c02905238b1a4c6098e089325e9b` |
| `tests/test_context_storage_integration.py` | `eefe446d224ae3c0b8ba1fcb11f8ad22c0ed82b1f35276cf2c60135cd1862072` |
| Task-35-Bericht | `bb7774e954a529e010ea8c55ae15b3ba9f212730a24ac5c7ec1e0faf09727014` |

## Tatsächlicher Alt-/Neu-Differential

Die freigegebenen vollständigen Commits sind
`c5912a7cb8ae095b7e7f63a0b3ce6ae2aaf9052a` und
`d643f4884bbfa6dcf88b292c6f6fbd1c666a9867`. Beide enthalten **byteidentische**
Ausgangsmodule: History SHA256
`aab750cefacbfcdd9c3165f08a8842d6f4dd378c7832bc1c44a8c170969e7c3e`,
Tennis SHA256
`aa94cd18b1280544f47e8c9e9a9a2b25ebf78c42a333c7e713a2db9b19c60d2d`.
Die Probe lädt genau diese Git-Blobbytes in getrennte Testprozess-Modulslots,
nicht einen nachgebauten Altalgorithmus. Der aktuelle Aufruf erhält explizit
seine neue Maincap; weder Produkt-API noch Type-Gates werden gelockert.
Ein zusätzliches read-only Git-Differential gegen beide Ausgangsstände zeigt
keine Codeänderungen an den verwendeten Modulen context_models/tennis.py,
tennis_v3.py, context_sources/tennis.py, tennis_status.py,
context_runtime_inventory.py, context_runtime_tennis.py,
context_runtime_transaction.py und model_artifacts.py.

16 echte Alt-/Neu-Fälle kombinieren acht tatsächlich normalisierte und
persistierte Eingabeszenarien mit Maximum-Cutoff und früherem 90-Minuten-Prefix:
leer, Legacy, gepaarter Status, gemischte Herkunft, empfindliche Float-Summen,
1-/3-/7-Tagesgrenzen, Statusrevisionen einschließlich ungültiger jüngerer
Projektion und laufendem Target sowie vollständige fremde/future Receipts.

Jeder Fall bindet gleichzeitig:

- sämtliche kanonischen Historyzeilen und deren Reihenfolge an den tatsächlichen
  unveränderten Cold-Oracle, nicht nur ausgewählte Featurezeilen;
- alle History-Bindingfelder außer dem physischen Spoolhash, einschließlich
  vollständiger Quellanzahl, Prefixgrenze, kanonischer Größe und Digest;
- den gesamten kanonischen Tennis-Bytestrom, dessen Digest und Größe sowie
  vollständige Materialisierung an den echten `tennis_features_v3`-Oracle;
- jede vollständige Referenzliste für jeden Featurekey zwischen Alt und Neu;
- echte relationale Tabelleninhalte von history/events/seen sowie
  tennis_chosen/tennis_ref_projection einschließlich der gespeicherten BLOBs;
- unveränderte ursprüngliche Quelldateibytes und unveränderte bereits gehaltene
  Quellpolicy/-generation nach jedem Builderlauf.

Physische SQLite-Header-/Seitenlayoutbytes werden dabei ausdrücklich nicht mit
kanonischen Daten gleichgesetzt. Der neue transaktionale Schemaaufbau darf den
Spoolhash ändern, ohne die Daten oder Rechenregeln zu ändern. Die Quellpolicy
wurde in dieser Testfixture absichtlich vor ihrer Validierung auf FILE und
einen anderen Cache gesetzt: Das zeigt ausschließlich, dass Task 35 den fremden
Quellowner nicht heimlich umkonfiguriert. Ein späterer nativer C-Owner muss auch
seine Quelle vor dem eigenen Pinning korrekt auf MEMORY einrichten.

## Fehler, Readback und Lebensdauer

Die weiteren unabhängigen Fälle prüfen konkrete reale SQLite- und I/O-Pfade:

- Sechs Alt-/Neu-Lebensdauerfälle beginnen einen echten Outputstream und beenden
  danach Quellgeneration, History oder Result. Der nächste Streamschritt schlägt
  jeweils fehl. Der bewusst freigegebene Lifecyclewechsel ist sichtbar: Der alte
  Tennisowner entfernt seine eigene Test-TemporaryDirectory, der neue behält
  seinen Output nach `close()`.
- Vier echte SQLITE_AUTH-Fälle blockieren über SQLite selbst die erste relevante
  INSERT-Operation. Beide Writer werden tatsächlich geschlossen; die neuen
  History- und Tennis-Builds rollen auch alle DDL zurück. Die alte History hatte
  ihre leeren Tabellen schon separat angelegt. Der alte Tennisowner löschte seinen
  fehlgeschlagenen eigenen Testoutput, während der neue ihn behält. Dies sind
  beabsichtigte, überprüfte Änderungen und keine abgeschwächten Assertions.
- Vier Fehler direkt beim echten Writer-zu-RO-Reopen verhindern einen Rückgabewert
  nach dem Commit. Bereits vollständige neue Dateien bleiben bestehen und haben
  bei separat geöffnetem SQLite-Reader vollständige Zeilen und integrity_check=ok;
  die vorherige Writerverbindung ist schon geschlossen. Diese Dateien werden
  nicht als veröffentlichtes Result interpretiert.
- Sechs neue FULL-Fälle verwenden Maincaps 4096, 8192 und 16384 Bytes für beide
  Builder und erhalten den tatsächlichen SQLite-Fehlercode SQLITE_FULL (13), bei
  Tennis über den konkreten Originalfehler in der Cause. Die Dateien bleiben
  innerhalb der kleinen Maincap erhalten. Eine zweite Anfrage an denselben
  inzwischen nichtleeren Owned-Slot wird abgewiesen und verändert keine Bytes.
- Zwei tatsächliche Writer-/Reader-Handofffälle halten zusätzlich einen normal
  registrierten Cursor über den gesamten Aufbau. Verbindung und Cursor sind
  bereits beim RO-Open wirklich geschlossen. Beide SQL-Traces beginnen mit
  MEMORY; exakt ein BEGIN IMMEDIATE liegt vor jeder DDL, genau ein COMMIT wird
  ausgeführt. Der Reader liest tatsächliche Attach-/Thread-/Defensive-/Extension-
  Einstellungen zurück. Im vorreservierten Ownedpfad liegt nur der feste Main;
  der erfolgreiche Abschluss löscht ihn nicht.

Der gelesene und zusätzlich gemeinsam getestete Ownerumfang prüft insbesondere
den bounded Compile-TEMP_STORE-Katalog, Reserveverlust an mehreren Buildphasen,
effektiv veränderte Writer-/Reader-Policy, tatsächliche refs-Savepoints und
UNION-/DISTINCT-Queries sowie erfolgloses RO-Profil nach vollständigem Commit.
Die alten fachlichen Fälle bleiben erhalten. Die zwei umbenannten Fälle machen
die absichtlichen Änderungen sichtbar: MEMORY bleibt im gehaltenen Reader
MEMORY; fehlgeschlagene neue Tennisartefakte bleiben erhalten. Bereits durch
Defensive oder ATTACHED=0 verhinderte Mutationen werden korrekt als Verhinderung
mit tatsächlichem Readback geprüft, nicht als unerkannt zugelassener Drift.

## Ausgeführte lokale Evidenz

Runtime: `.pytest_tmp/qa-python312-c-01/Scripts/python.exe`, tatsächlich
Python 3.12.14 / SQLite 3.53.1, Windows. `-B`, Plugin-Autoload und pytest-Cache
aus. Jeder Lauf hat eine frische, vorher nie vorhandene Basetemp und XML-Datei.
Keine frühe Evidenzdatei wurde überschrieben oder entfernt.

Eigene Probe:
`.pytest_tmp/task38-independent-20260912-1/test_task38_builders.py`, SHA256
`f1e621f04d86fe9a530002a6f91341f2daf5213e4dff62893421a1d2251688f4`.

Transparente, erhaltene Vorläufe:

- `task38-independent-20260912-1.xml`: ein Collectionfehler im eigenen Harness
  wegen fehlendem tests-Importpfad, noch kein Produkttest. SHA256
  `43279887960e7bef8861f9321796d2c78bbf40e5034ff19c4b6454b08f9c621e`.
- `task38-independent-20260912-2.xml`: fünf grün, ein eigener Fixturefehler.
  Ein winziger positiver Minutenzähler hatte durch Mikrosekundenrundung eine
  Null-Zeitspanne bekommen; der unveränderte Normalizer wies dies korrekt ab.
  Die Fixture deklariert nun tatsächlich unbekannten Start statt einen falschen
  gemessenen Zeitraum. Keine Produktänderung. SHA256
  `1e891bdd0e30388a0b51d66f27122e66d7f0de5b19d58c3f4c8b6bed5b6bc306`.

Finaler eigener Lauf `task38-independent-20260912-3.xml`:
**39 bestanden, 0 Fehler, 0 Skip**, 68,94 s (JUnit 68,935 s), SHA256
`b3167d4aec06155d7f1250c184f7202c2a87528975b8021eb74cb46fc0fe9236`.

Finaler Kombilauf `task38-combined-20260912-1.xml`:
**359 bestanden, 0 Fehler, 0 Skip**, 208,59 s (JUnit 208,574 s), SHA256
`28796f565f11f8d53ccbf4aac65ef2ac66b39f967936ad21cc2607900ffad917`.
Die tatsächliche XML-Aufteilung ist History 104, Tennis 117, SQLite-Profil 93,
Root-Integration 6 und eigene Probes 39. Die eigene Probedatei und sämtliche
oben gebundenen Produkt-/Ownertestdateien behielten ihre exakten Hashes.

Tatsächlich ausgeführter Kombibefehl:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider -o junit_family=xunit1 tests/test_context_storage_history.py tests/test_context_storage_tennis.py tests/test_context_storage_sqlite_profile.py tests/test_context_storage_integration.py .pytest_tmp/task38-independent-20260912-1/test_task38_builders.py --basetemp=.pytest_tmp/task38-combined-bt-20260912-1 --junitxml=.pytest_tmp/task38-combined-20260912-1.xml
```

Diese Namen sind jetzt belegt. Eine Wiederholung muss erneut frische,
vorher nie vorhandene Basetemp-/XML-Namen verwenden und alte Evidenz behalten.

## Unverändert offene äußere Bedingungen

Main M und zusätzliches Journal M sind **logische reservierte Dateilängen**;
die Builder sind kein globaler Reservierungs-/Physikowner. FSIZE-M, Zahl und
Identität aller Dateien, Quelle/Archive/fehlgeschlagene Versuche, Metadaten,
physische Allokation, mindestens 4 GiB Freiraum sowie die unveränderte Gesamt-
8-GiB-Hülle müssen vom äußeren geschlossenen nativen Owner zugelassen und
überwacht werden. MEMORY ist keine neue AS-/RSS-Erlaubnis oder FILE-Fallback.
Die hier durch SQLite ausgelösten lokalen Fehler sind keine Linux-Limitprobe.

`owned_directory` ist für diesen nativen Owner zwingend. Ein leeres Verzeichnis
oder eine Exception-Note ist weder Authentifizierung noch vollständige Inventur.
Die private, exklusive, quieszente Namespacevorbedingung gilt durchgehend;
offene Pfadraces/ABA werden nicht durch den beobachteten FD-/Pathvergleich
wegbehauptet. Kein Resume, Cleanup oder Slotrelease wird aus `close()` abgeleitet.

Dieser Report prüft keine nativen Guard-/Supervisor-/Budgetbytes, keinen
kompletten C-Corpus, keine C6-Profile, keine Modelländerung und keinen B-/D2-
Publikationsnachweis. Nächster zulässiger Schritt nach finalem Reviewabschluss
ist Roots getrennte bewusste Ownerintegration mit festen Slots und anschließenden
vollständig begrenzten nativen Messungen, nicht eine pauschale C-/B-Freigabe.
