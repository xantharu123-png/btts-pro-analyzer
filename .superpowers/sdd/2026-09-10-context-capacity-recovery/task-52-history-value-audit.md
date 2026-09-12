# Task 52 — Einzelwert-Zulässigkeit am echten History-Anschluss

12. September 2026. Enger unabhängiger Audit, keine Produktkorrektur.

## Ergebnis: konkrete C4/C6-Kompatibilitätslücke

**[P1] Eine alte tatsächlich source-valid und vollständig ausgewählte Zeile
wird vom neuen History-Builder allein aufgrund ihrer kanonischen
Einzelzeilenlänge abgewiesen.** Der Zweig ist nicht durch den alten Sourceowner
unerreichbar. Konkrete Fehlerstelle:
`context_storage_v2/history.py:584` / Ausnahme in `:585`.

Ein einziger unveränderter Defaultlauf belegt:

```text
normalize_tennis_status                         akzeptiert
append_observation                             persistiert
VerifiedReceiptMapping.validate_all             vollständig akzeptiert
_cold_replay_history + tatsächlicher Sourcecheck wählt genau dieselbe Zeile
build_history                                  StorageLimitError:
  one canonical history row exceeds v2 block budget
```

Das ist ein fehlender Erhalt bisheriger Zulässigkeit, keine akzeptierte
fachliche Vereinfachung. C4 in
`docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md:139`
fordert für große Altstrukturen den bisherigen Lesevertrag oder einen
eigens geprüften Adapter; die 16-MiB-Verarbeitungsblockgrenze ist dort
ausdrücklich kein behauptetes altes Payloadmaximum. C6 `:173` fordert
vollständige Gleichheit einschließlich alter Zulässigkeit und Fehlerfolgen.
Eine bestehende Testassertion für den Cap könnte diesen Vertragsunterschied
nicht aufheben; keine solche Assertion wurde zur Begründung herangezogen.

## Tatsächlicher alter Wert und Größe

Der einzige neu angelegte Offline-Fixturewert ist eine native Competition
mit normalen IDs 101/1/2, ATP-Tournament `189-2026`, `mens-singles`, gültigem
Schedule, `state="pre"`, `completed=False` und
`name="S" * 16777217`. Kein fertiger Receiptdigest und keine normalisierte
Statushülle wurden von der Probe erfunden. Der unveränderte echte
`normalize_tennis_status` erzeugt selbst Status-/Competition-/Content-
Identitäten und anschließend die vollständige B1-Zeile.

Der erzeugte Status ist `scheduled`, `issues=[]`, Workloadrefs sind leer;
es handelt sich nicht um einen ungültigen Sourcewert, der bloß ungeprüft
gespeichert wurde. Das ist **Sourcevalidität nach dem vorhandenen Ownervertrag**,
nicht die Behauptung, ESPN liefere in Wirklichkeit einen so langen Namen.
Providerwahrheit, Modellbrauchbarkeit und Produktionsvorkommen werden nicht
aus einem synthetischen Offline-Competitionwert abgeleitet.

| Tatsächliche Größe / Grenze | Bytes |
| --- | ---: |
| Native Statusname | 16777217 |
| Kanonischer Content-BLOB | 16778260 |
| Kanonische ausgewählte Einzelzeile | 16778570 |
| Vollständige alte ausgewählte Tuple, eine Zeile | 16778572 |
| Ganze physische Legacy-DB | 16838656 |
| Unveränderter neuer Default-Verarbeitungsblock | 16777216 |
| Bisherige Small-Image-Eingabegrenze | 67108864 |
| Expliziter neuer Maincap in dieser Probe | 67108864 |
| Neuer Default-Tour-Historienrahmen | 1073741824 |
| Neuer Default-Gesamteingaberahmen | 4294967296 |

Die neue Zeile überschreitet den Defaultblock um **1354 Bytes**. Die ganze
Quelle bleibt dagegen unter der bisherigen 64-MiB-Small-Image-Grenze; selbst
die vollständige alte ausgewählte Tuple bleibt darunter und weit unter der
neuen 1-GiB-Tourgrenze. Es wurde kein Blockwert künstlich abgesenkt und kein
zulässiger Rahmen erweitert. Der separat explizit übergebene 64-MiB-Maincap
ist größer als die gesamte Zeile und nicht die beobachtete Fehlerursache.

## Verfolgte tatsächliche Ownergrenzen

1. `context_models/contracts.py:31` und `:73`: `_CODE`/`require_text(code=True)`
   fordern stabile nichtleere ASCII-Codezeichen ohne äußere Leerzeichen;
   sie haben keine Zeichen- oder Bytegrenze. Die Probe ersetzt diese Funktionen
   nicht und setzt keine fremde Validatorfreigabe.
2. `context_sources/tennis_status.py:39` / `:48`: `_native_status` übernimmt
   den Namen nach genau dieser Prüfung. `_status` in `:67` klassifiziert
   `pre`/False als scheduled. `normalize_tennis_status` in `:119` erzeugt
   den wirklichen Source-Record und ruft seinen eigenen Validator auf.
   `_validate_tennis_status_payload` in `:171` / `:181` prüft den Namen erneut
   nach derselben Grammar, ohne verborgenes kleineres Maximum.
3. `context_observations.py:102`: echte Legacy-Append-API erzeugt genau einen
   Content und ein Receipt in SQLite. Ihre normalen kanonischen Byte-/Hash-
   und Kollisionsprüfungen bleiben intakt; `_decode_receipt` in `:80` ist
   derselbe spätere physische Decoder. Kein direkter manuell passender SQL-
   Receipt-Insert wird als Ersatz verwendet.
4. `context_runtime_inventory.py:123`, `:167`, `:304`: Ein tatsächlicher
   `VerifiedReceiptMapping` auf der exakt gehaltenen RO-Tran­saktion absolviert
   `validate_all` mit einem validierten Content und einem Receipt. Anschließend
   liest der echte alte Historypfad denselben physischen Stand erneut.
5. `context_runtime_tennis.py:65`: `_cold_replay_history(..., max_bytes=None)`
   wählt genau ein Receipt. Das ist der vorhandene Parameterzustand des
   <=64-MiB-Altzweigs (`context_runtime.py:39`, `:557`), keine entfernte
   Pflichtgrenze. Der gesamte alte D4-/B-Verifikationslauf wurde nicht behauptet
   oder erneut ausgeführt. Für diese benannte Zulässigkeitsfrage wurden die
   wirklichen physischen Receipt- und Sourceauswahlowner ausgeführt.
6. `context_sources/tennis_status.py:314` selektiert über den wirklichen
   `validate_selected_tennis_receipt` in `:238`. Dieser wurde in der Probe
   zusätzlich direkt auf der alten ausgewählten Zeile ausgeführt. Tour,
   Empfangszeit, Identitäten und native Statussemantik werden tatsächlich
   geprüft; es handelt sich nicht um einen unbekannten Raw-only-Quelltyp.
7. `context_storage_v2/history.py:505`: `build_history` erhält dieselbe
   vollständige VerifiedReceiptMapping, denselben tatsächlichen Quellhash,
   dieselbe Tour und denselben Cutoff. Es öffnet den eigenen neuen Writer,
   decodiert/selektiert die Zeile erneut und bricht in `:585` ausschließlich
   am `len(canonical_bytes(selected)) > limits.block_bytes` ab.

Die zweite gleichartige Kopplung ist auch im veröffentlichten Lesepfad
`HistoryView._rows`, `context_storage_v2/history.py:369`, vorhanden. Sie wurde
nicht umgangen oder entfernt. Nur die Builder-Ausnahme wurde tatsächlich
ausgeführt; die weitere Readerstelle ist ein statischer Folgehinweis für
den zuständigen Implementierungsowner, kein zweiter erfundener Repro.

## Lebensdauer und erhaltene Evidenz

Nach Legacy-Persistenz wurde der neue Fixturewriter geschlossen. Die Quelle
hatte keine Journal-/WAL-/SHM-Datei, erhielt lokal das Readonly-Attribut und
wurde mit einem gehaltenen O_RDONLY-FD sowie einer exakten
`TrackedConnection`, `mode=ro`, query_only und BEGIN gelesen. Es wurden keine
Fremdquelle und keine bestehende DB verändert. Das belegt die lokal ruhende
Fixture-/Leselebensdauer, **keinen** Linux-DAC-/Root-Seal oder B-Schutz.

Nach dem Historyabbruch sind Source-SHA, tatsächlicher FD/Inode/Größe und
Leseepoche unverändert. Der fehlgeschlagene neue Main bleibt als
`new-history-workspace/history-ATP/history.sqlite` mit **0 Bytes** erhalten.
Es wurde kein Teilresultat/HistoryView publiziert. Dieser korrekte Abbruch
und die korrekte Artefaktaufbewahrung beheben die Zulässigkeitslücke nicht.

Exakte Inhalte:

- Content-SHA: `587b57c4d136f3e6f5f46a3459234793e0890c268935f79774186ae277204777`.
- Receipt: `405d2c4a47015236acdaa85e361417ea0e730c33dec7e2f722dc65f395c0dbd9`.
- Ausgewählte Zeilenbytes-SHA:
  `88a828a6a5f4f5599edc065079da00c8f4d0b584c91d0c4e2909c78c16f6cb67`.
- Quellfile-SHA:
  `8946c480e9388950d2640ac4cb6d59816cb28033f9e0d1c50b7b5a7cadc40e41`.

Ein einziger neuer ignorierter Helper:
`.pytest_tmp/task52-history-value-probe.py`. Er dokumentiert beide möglichen
New-Builder-Ausgänge, statt ein Finding als Testerwartung vorauszusetzen.
Tatsächlich wurde **rejected / StorageLimitError / history.py:585** beobachtet.
Die JSON-Zusammenfassung ist vollständig als JUnit-Property
`history_value_audit` erhalten; sie enthält keine riesigen Payloadtexte.

Genau ein enger Lauf, keine Wiederholung/breite Suite:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& '.pytest_tmp/qa-python312-c-01/Scripts/python.exe' -B -m pytest -q -s -p no:cacheprovider -o junit_family=xunit1 .pytest_tmp/task52-history-value-probe.py --basetemp=.pytest_tmp/task52-history-value-bt-20260912-01 --junitxml=.pytest_tmp/task52-history-value-20260912-01.xml
```

Tatsächliches Kommandoergebnis: **1 passed in 2.99s**, 0 Skips/Errors;
JUnit 2,930 s. Dies bedeutet, dass der Auditablauf samt alten Prüfungen
erfolgreich durchlief und den neuen Fehler aufzeichnete — **kein bestandener
C-Gleichheitstest** und keine wieder grüne Kompatibilitätsfreigabe.

## Bytebindung und offener Arbeitsbedarf

| Gegenstand | SHA256 |
| --- | --- |
| Unveränderte `context_storage_v2/history.py` | `287ae422bdbd7925e0c09899d870a4ef953c5c11024c0dc7f98a11183a5158b8` |
| Unveränderte `context_storage_v2/tennis.py` | `da51aab436387021e2d2022bea71f6045c0b0e5f6a4f8efce64fa52a6f029698` |
| Unveränderte `context_sources/tennis_status.py` | `8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581` |
| Unveränderte `context_observations.py` | `9fb1ec38ac12dd3b142ab1b23e9c49cf605e77cd931e38c503f69026d0cec226` |
| Unveränderte `context_runtime_inventory.py` | `2425653f02b1ff4b11fd6ec39f13bb9a3ca5061b3185af65cc41c44a816e36de` |
| Unveränderte `context_runtime_tennis.py` | `1bf3ebaf37b13cd0173ac795a2ddc5ea01918dafe6730881625322c6bf205bed` |
| Unveränderte `context_models/contracts.py` | `7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8` |
| Unveränderte `model_artifacts.py` | `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16` |
| Unveränderter C-Vertrag | `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba` |
| Neuer eigener Probehelper | `4d6666895ade39925ef9eadc06a4704c8dbfea1e659767cf3b1c7633dd308eaf` |
| Neues eigenes JUnit-XML | `b9ac0a41af1139d9a173bd726ea371adcb4190a693149e2db4b05aa31399fbdc` |

Die Skill `systematic-debugging` führte zu genau diesem rückverfolgten
Owner-für-Owner-Repro. Sie führte **nicht** zur eigenmächtigen Phase einer
Produktkorrektur. Keine Produkt-/Ownertest-/Spec-/Git-/Serveränderung und keine
Agentendelegation. Task48 bleibt alleiniger Implementierungsautor.

## Engste Reparaturoption: gebundene alte Einzelrow, kein größerer C-Block

Auf ergänzenden Auftrag wurde nur gezielt weitergelesen; **kein zweiter Lauf
und keine Produktkorrektur**. Für den konkret belegten Wert genügt als
Reparaturansatz ein expliziter, interner Source-backed-Large-row-Modus im
bestehenden Historyowner. Ein selbständiger neuer Chunkstore ist dafür nicht
zwangsläufig nötig. Das ist eine begründete Implementierungsoption, noch kein
geprüfter Fix und kein Nachweis für jede denkbare große Altstruktur.

Der Grund ist eine bereits bestehende, nicht neu zu erfindende Lebensdauer:
`history.py:190-249` bindet den echten vollständig validierten
`VerifiedReceiptMapping`, die exakte gehaltene `TrackedConnection`,
Validierungsepoche, geschützte Referenzen, Dateistand und vollständige
Eingabeidentität. `HistoryView.assert_intact` in `:338` prüft diese Source
auch beim späteren Lesen. Der Spool ist ausdrücklich schon heute **nicht**
unabhängig von dieser offenen Source (`:11`, `:343`, `:637`).

Der enge Vorschlag hat folgende notwendige Teile:

1. **Vollständige Auswahl unverändert, nur andere private Ablage.** Der ganze
   physische Vorlauf, `seen`, die tatsächliche alte Auswahl in `:582` und alle
   alten Sourcefehler bleiben bestehen. Erst eine wirklich decodierte und
   erfolgreich ausgewählte Zeile darf bei Übergröße in einen ausdrücklich
   markierten Source-Modus gehen. Kein allgemeiner Exception-Fallback, kein
   stilles Verwerfen, keine Rettung defekter bekannter Quellen und kein
   Bodyöffnen geschützter D2-Finals. Die private History hält dafür
   Receiptidentität, Inhaltsidentität, dieselben Ordnungs-/Eventfelder und
   exakte ausgewählte kanonische Länge/Byteidentität statt eines neuen großen
   Payloadblocks. Kleine Inlinezeilen bleiben ein anderer expliziter Modus;
   ein Moduswechsel darf keine mehrdeutige Sentinel-Heuristik sein.
2. **Wirklicher alter Reader bei jeder Auflösung.** Die Source-Zeile wird an
   genau derselben gehaltenen Quelle mittels festem Receiptkey erneut gelesen
   und vom echten alten `_decode_row`/`_decode_receipt` decodiert
   (`context_runtime_inventory.py:297-312`). Die vorhandene direkte
   Basis-SQL-/Methodenbindung ist beizubehalten, nicht durch einen freien
   Caller-Loader oder eine andere Connection zu ersetzen. Der echte
   `select_tennis_observations` (`tennis_status.py:314-333`) rekonstruiert die
   ausgewählte Zeile mit den wirklichen Auswahlfeldern und Sourceprüfung.
   Indexfelder, Länge, kanonische Identität, Tour und Cutoff müssen dabei
   passen. Kein bloßes Nachschlagen einer Hashhülle und kein Wiederverwenden
   eines vom Konsumenten mutierbaren großen Dicts als Prüfungsersatz.
3. **Alle tatsächlichen Iterationen auf denselben Resolver führen.**
   `HistoryView._rows` (`history.py:361-382`) braucht beide eindeutig geprüften
   Ablagemodi; nur `:584` zu entfernen scheitert anschließend an `:369`.
   Der Resolver muss auch von `as_of` (`:387-427`), `iter_events`/`event`
   (`:430-459`) und `EventHistory.iter_rows`/`iter_latest_rows` (`:496-502`)
   erreicht werden. Gesamtreihenfolge `observed_at,digest`, Eventreihenfolge
   nach erster Beobachtung und der echte maximale Empfangszeitpunkt pro
   Cutoff bleiben unverändert. Weder eine gesamte Historytuple noch eine
   vollständige Revisionsgruppe darf zum Ersatz materialisiert werden.
4. **Ausgewählter Digest bleibt der Digest der vollständigen ausgewählten
   Bytes.** Build-Endpass `history.py:608-615` und Präfixpass `:408-423` müssen
   für beide Modi genau dieselbe Folge
   `uint64_be(len(canonical_row)) || canonical_row` verarbeiten. Count und
   1-GiB-Tourbilanz zählen die vollständigen Zeilenbytes, nicht die kleinere
   Locatorgröße. Eine Verkettung gespeicherter Einzel-SHAs, Receipt-/Content-
   Digests oder unveränderte alte Bindungswerte wäre nicht derselbe Digest.
   Der alte Kanonisierungsowner `model_artifacts.py:24-33` bleibt Byteoracle.
5. **Source-Lebensdauer bleibt eine harte Abhängigkeit.** Vor und nach dem
   erneuten Sourcezugriff sowie nach Wiederaufnahme jedes Yields bleiben die
   bestehenden Owner-, Transaktions-, Schema-, Datei- und Limitprüfungen
   wirksam. Ende/Änderung der echten Source oder des Eltern-Views beendet auch
   Prefix-/Event-/Featurekonsumenten. Kein Reopen nur anhand eines Pfads, kein
   überlebender öffentlicher Digest als Ersatz und keine neue Freigabe aus
   einem Callerflag. Der äußere gehaltene/sealende Sourceowner bleibt
   zuständig; die Source bleibt vollständig im aktiven Inventar und Budget.

### Unmittelbar folgende Tennisgrenze gehört zum selben Fix

`context_storage_v2/tennis.py:670-673` validiert absichtlich **alle** ausgewählten
Zeilen vor Event-/Spielerprojektion und weist dieselbe kanonische Übergröße
erneut ab. Die in dieser Probe gemessenen 16778570 Bytes liegen auch dort über
demselben unveränderten Defaultblock. Der Abschnitt wurde statisch gelesen,
nicht durch einen vorgetäuschten reparierten HistoryView erneut ausgeführt.
Ein reiner Historyfix würde daher den anschließenden Featureowner weiter
stoppen. Die kalte Sourceprüfung in `:671` darf nicht entfallen; lediglich die
pauschale Blockgleichsetzung in `:672` muss den tatsächlich implementierten,
lebensdauergebundenen Large-row-Pfad anerkennen.

Der konkrete scheduled-Status mit leeren Workloadrefs ist kein zu speichernder
Workload in `tennis_chosen`: Als Zielstatus wird er über
`_target_state`/`EventHistory` (`tennis.py:104-130`) gelesen; als anderes
relevantes Statusereignis führt der bestehende leere Workloadref-Fall in
`_paired_status` (`:179-180`) ohne Row-Staging weiter. Die große native
Namenszeichenfolge darf dabei weder gekürzt noch aus der validierten Zeile
entfernt werden. Die bestehende Eventstreamauflösung reicht für diesen
Payloadtransport aus.

Für die allgemeine Anschlussgrenze muss der Implementierungsowner zusätzlich
`_stage_usable` in `tennis.py:249-256` und `_rows` in `:262-269` berücksichtigen:
Tatsächlich gewählte Workloadrows werden dort erneut vollständig kanonisiert
und als BLOB gespeichert. Falls ein alter zulässiger großer Workload diese
Stelle erreicht, wäre auch dort eine feste Historyreferenz mit derselben
gebundenen Row-Auflösung nötig, nicht bloß ein Wegfall des Vorlaufchecks.
Das ist ein aus dem Writer-/Readerpfad abgeleiteter Reparaturumfang, **kein**
hier zusätzlich reproduzierter großer Workloadfall. Die vorhandenen maximal
zwei echten Paarrepräsentanten in `:133-167`/`:170-213` bleiben fachlich
dieselben; begrenzte Anzahl bedeutet ausdrücklich nicht begrenzte Rowbytes.

### Warum dies die 16 MiB nicht still erweitert; wann ein Chunkadapter nötig wäre

Große alte Zeilen dürfen ausdrücklich weiterhin vom wirklichen alten
Einzelrow-/Kanonisierungsowner materialisiert werden, nicht als angeblich
kleiner neuer Verarbeitungsblock gelten. Neue C-Ablage-/Referenzblöcke bleiben
höchstens 16 MiB; vollständige ausgewählte Bytefolgen können aus dem echten
alten kanonischen Wert blockweise gehasht werden. **Das zerlegt nicht
nachträglich dessen ursprüngliche RAM-Allokation.** Alte JSON-Decodierung,
Validierung und `canonical_bytes` erzeugen weiterhin große Einzelobjekte und
gegebenenfalls mehrere temporäre Kopien. Diese Ausnahme muss explizit als
bisheriger Lesevertrag geführt, ohne Gesamthistorycache genutzt und unter den
unveränderten realen AS-/RSS-/CPU-Grenzen geprüft werden. Keine pauschale
Blockvergrößerung, kein behaupteter Native-Peak aus der vorliegenden Probe.

Insbesondere sind 64 MiB die nachgewiesene **alte Gesamteingabegrenze dieses
Fixtures**, kein daraus abzuleitender produktweiter Einzelwertcap. Der neue
Modus darf damit weder weitere alte zulässige Werte abschneiden noch größere
Werte beliebig zulassen; die C4-Pflicht zu festen geprüften Einzelwert- und
Blockanzahlregeln bleibt beim Implementierungsowner offen und darf die alte
Zulässigkeit nicht überschreiben. Hier ist nur gezeigt, dass dieser Wert den
echten alten Reader passieren kann und keinen größeren C-Block benötigt.

Ein eigener geprüfter Chunk-/Byteadapter wäre dagegen notwendig, wenn der
neue Spool ohne diese gehaltene alte Source selbständig lesbar werden soll
oder wenn die große alte Einzelwertmaterialisierung nicht mehr unter ihrem
bisherigen Readervertrag und der wirklichen Workerhülle ausgeführt werden
kann. Chunkablage allein löst Letzteres noch nicht: Die heutigen alten
Sourcevalidatoren und Tennisregeln erwarten tatsächliche vollständige
Rowdicts; ein Lazy-Proxy oder abgeschnittener Ersatz wäre keine gleichwertige
Schnittstelle. Ein solcher weitergehender Adapter bräuchte eigene kanonische
Byte-, Reassembly-/Verbraucher- und Lebensdauerbelege. Für den nun belegten
Fehler ist das nicht der engste erste Reparaturschritt.

Damit ist die konkrete Alt-/Neudifferenz belegt und eine eng begründete
History-**und**-Tennis-Reparaturgrenze beschrieben. Umsetzung und deren
Differential-/Lebensdauernachweise bleiben offen. Keine native RSS-/CPU-,
Gesamt-C/B-, Modellqualitäts- oder Deploymentaussage.
