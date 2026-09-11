# Task14 / B0 — unabhängige Instrumentenprüfung

Stand: 12. September 2026. Prüfer `/root/b0_size_review`.

## Ergebnis

**APPROVED für die exakt begrenzte native Größenmessung**, nicht für einen
D4-Pass, einen B-Produktpatch oder eine Deploymentfreigabe. Keine offenen
kritischen/wesentlichen Findings in den unten gebundenen finalen Bytes.
Der Root-Agent übernimmt serielle Ausführung, vollständige Rohaufzeichnung,
Lineageprüfung und die kumulative Ressourcenbilanz. Der Reviewer hat weder
SSH noch das Instrument oder die Tests ausgeführt und keine Produktdatei,
Git-Index oder Serverzustände verändert.

Vollständig gelesen:

- Aufgabenbrief `task-14-brief.md` sowie der konkrete B-Vertrag.
- `.pytest_tmp/probe_task14_growth_size.py`, SHA256
  `9b4d3a0f8501dda9d0ab0bb3714bcf4f59d5487d2ccdc5f23cefda56f07327f4`.
- `.pytest_tmp/test_task14_growth_size.py`, SHA256
  `eac0ef49826fdda95efe66414e414cd0022bae79c1dc8cd3f3e1cc1a963aa197`.
- Zuständige kalte Historienimplementierung, Tennis-Status-Normalisierer und
  Selektor, physischer Receiptdecoder, Artefakt-/Snapshotdecoder und die für
  diesen Bestand entscheidende frühe D2-Verzweigung; zusätzlich die bestehende
  sealed-file-Verbindung als Abgrenzung zur bloßen Größenmessung.

Root meldet die acht lokalen Owner-Eigenprüfungen auf genau diesen Bytes frisch
bestanden (0,140 s); Autor meldet acht bestanden (0,139 s). Dies sind gemeldete
Ausführungsergebnisse, keine vom Reviewer zusätzlich ausgeführten Tests und
kein nativer Leistungsnachweis.

## Präzise Messsemantik

`_cold_replay_history` zählt **die Summe der kanonischen Byteanzahl jeder
ausgewählten Zeile** vor deren Aufnahme. Es zählt nicht Tuple-Klammern,
Kommas, Python-Objektspeicher oder die SQLite-Dateigröße. `ByteCounter.add`
zählt exakt dieselben `canonical_bytes(selected_row)`; die zusätzliche
längenpräfixierte SHA-Bilanz wird nicht als Historygröße angerechnet.

Der Baselinepfad dekodiert jede physische Receiptzeile mit dem bestehenden
Decoder, bevor Quell-/Tourfilterung erfolgt. Der unveränderte Selektor prüft
anerkannte Tennisquellen vor Tourfilterung. Die einmalige Dispatchwahl anhand
des tatsächlichen Payload-Tours ändert die Summen der beiden vollständigen
Tourhistorien nicht; fehlende/ungültige Tourdaten erhalten keinen stillen Pass.
Bestehende unreferenzierte und später beobachtete Zeilen werden nicht entfernt.
Der Zukunftsstichtag liegt nach allen beobachteten Eingabe-/Artefaktzeitpunkten.

Die Originalzeitpunkte werden mit `bisect_left` in inklusive kausale Präfixe
überführt. Snapshotgrößen sind tatsächlich gespeicherte kanonische Bytes.
`reference_count_matches_current_selection` beweist ausdrücklich nur gleiche
Anzahl, nicht Gleichheit aller referenzierten IDs oder einen Snapshot-Replay.

Vor jedem Artefakt-/Receiptbody prüft der Helper die **ganze Artenliste**.
Nur `tennis-tour-state` und `tennis-live-winner-original-v1` werden zugelassen.
Unter dieser Voraussetzung liefert der zuständige aktuelle
`verify_d2_artifacts`-Zweig eine leere Schutzmenge. Darum werden die vorhandenen
`match_outcome`-Belege physisch dekodiert und erst anhand ihres Quellschemas
nicht in eine Tennisstatushistorie aufgenommen. Es gibt kein pauschales
Ergebnisdatenverbot und keinen Zugriff auf durch D2 ungeöffnete Finaldaten.
Andere/unknown/D2-/Approval-Artefaktarten stoppen den Helper vorher.

Neue synthetische ATP-Zeilen entstehen über den echten Statusnormalisierer,
werden in genau die physische Rowhülle kodiert, durch den echten Decoder
zurückgelesen und vom echten Selektor angenommen. IDs sind neue feste Breite,
die bestehende Eingabe wird vorab auf Namespacekollisionen geprüft. In den
kleinen Eigenprüfungen entspricht diese Hülle tatsächlichem Append/Read;
Idempotenz und die Grenzfälle einer zulässigen/leeren/vorzeitig übergroßen
kalten Historie werden ebenfalls geprüft. Die native Messung schreibt diese
neuen Zeilen selbst **nicht** in eine Datenbank.

## Eingabe, Quelle und Betriebsgrenzen

- Ausschließlich Quelle724 unter
  `/var/lib/betboy-capacity-code-5es6n672/source`.
- Ausschließlich frische versiegelte Eingabe
  `/var/lib/betboy-live-backup-ssfvf5xs/context-current.db`, 270233600 Bytes,
  SHA256 `73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa`.
- UID997 vor Produktimporten; root-eigene unveränderbare Ancestry, keine
  Symlinks, einzelne reguläre0440-Eingabedatei, keine SQLite-Companions.
  Feste Owner-SHAs und Datei-/Directoryidentitäten werden vor und nach der
  Messung geprüft. Verzeichnis-mtime wird zu Recht nicht als Datenmutation
  behandelt. Der ganze Eingabedateihash wird erneut verglichen.
- Ausführungsmetadaten nennen Python-/SQLiteversion und SHA des tatsächlichen
  Interpreterziels; dessen Hash wird am Ende nochmals verglichen. Dies ist
  bewusst **keine vollständige authentisierte B-Runtimeclosure**.
- Rein read-only/immutable nur auf dieser tatsächlich versiegelten Datei,
  gehaltene Lesetransaktion, query_only, begrenzte SQLite-Einzelwerte und Cache,
  temp_store=MEMORY. Kein Live-DB-immutable, Netzwerkzugriff, Modell-/Feature-
  Replay, Root-Produktimport, Datenbankaufbau, Secret- oder Payloadausgabe.
- Pro Prozess CPU300 hart, AS2GiB, kooperative CPU/Wallunterbrechung280/285 s;
  Ergebnisannahme nur bei CPU/Wandzeit<300 s und RSS<1GiB. Ausgabe≤1MiB und
  ≤520 Datensätze; Fehler enthalten nur Klassennamen, keine Persistenzwerte.
- Geplanter Root-Transport: cleared env, `sudo -n runuser -u betboy`, GNU timeout
  TERM310 s/KILL+10 s, GNU time um `/opt/betboy/venv/bin/python -I -B -`.
  GNU time liefert ergänzende CPU/RSS/Wallwerte auch bei fehlendem Helperende.
  Kein neuer Roothelper und kein neuer nativer Schreibpfad.

## Bindende Annahmeregeln nach Ausführung

1. Nur vollständige Abschlussphase mit Exit0, `measurement_completed:true`,
   `resources_ok:true`, unveränderten Eingabe-/Quell-/Ancestor-Seals und passenden
   Pins darf in den nächsten Messschritt eingehen. Frühe Teilphasen allein sind
   keine gültige Baseline. Abbruch/fehlender Abschluss bleiben unvollständig.
2. BASE/PRIOR und `upstream_evidence_sha256` sind externe diagnostische Lineage,
   keine selbstauthentisierten Nachweise. Root muss sämtliche Vorgängerausgaben
   behalten und die tatsächlichen Baseline-ATP-/kumulativen Tageswerte exakt
   übertragen. Eine beliebige syntaktisch gültige SHA genügt außerhalb dieses
   überwachten Ablaufs nicht. Das Instrument ist kein Produktions-Proof-API.
3. Gesamtvorbereitung einschließlich Backup, fehlgeschlagener Versuche, aller
   Teile und Wiederholungen≤1800 CPU-/3600 Gesamtsekunden; keine parallelen
   schweren Serverläufe und kein Neustart als Budgetreset.
4. Beim ersten vollständig gemessenen `storage_stop:true` endet diese Probe.
   Die gerade überschreitende Zeile gehört zum notwendigen Größenbeweis.
   Keine weitere volle Historie, Datenbank oder Snapshotmenge anlegen und keine
   Grenze für einen Pass erhöhen. Ein noch nicht überschrittener Teilumfang
   beweist seinerseits keine vollständige Profilzulässigkeit.

## Nicht zu behaupten

Die 70000 zusätzlichen eindeutigen ATP-Statusbelege pro Tag sind eine
**konzentrierte synthetische Größen-/Grenzprobe**, keine repräsentativ gemessene
siebentägige Produktionsentwicklung. Sie teilen bewusst nicht entlastend auf
ATP/WTA auf und behaupten keine realen Spielpläne oder Providerlieferungen.
Ein notwendiger Größenfehler dieses zugelassenen synthetischen Inhalts zeigt,
dass der definierte unveränderte Vertrag dieses Profil nicht tragen kann.
Er beweist weder einen heute eingetretenen Live-Ausfall noch den genauen Tag
eines zukünftigen Produktionsausfalls.

`snapshots_generated:0`, `growth_database_written:false` und
`complete_verification_claimed:false` sind korrekt. Insbesondere wurde kein
vollständiger199-Snapshot-D4-Bestand erzeugt, keine Gesamtdateigröße dieses
Bestands gemessen, kein Feature-/Modellpass erteilt und keine sieben Tage
Betrieb oder B-Implementierung abgenommen.

## Während des Reviews korrigiert

Der Erstentwurf `c972d87a...` band den tatsächlich importierten Tennis-Liveowner
und den D2-Schutzentscheidungsowner nicht ausdrücklich im SHA-Dict, nannte
keine Runtimeidentität und wiederholte am Ende nur den Eingabedateivergleich.
Die finalen oben vollständig erneut gelesenen Bytes ergänzen diese Pins,
Runtime-Metadaten/Interpreterhash und vollständige erneute Preflightidentitäten.
Post-Sealfehler werden dabei fail-closed als Klassenname erfasst. Diese eng
begrenzten Korrekturen ändern weder Generator, Bytebudget noch Produktsource.

## Ergebnisgegencheck — tatsächlich abgeschlossene Baseline

Nach Freigabe hat Root die native Baseline ausgeführt. Der Reviewer hat nur die
gespeicherte vollständige Ausgabe gelesen, deren SHA erneut ermittelt und
Summen/Formeln read-only gegengeprüft:

- `evidence/task14-baseline-20260912.log`, SHA256
  `a6ebff9d0b08c617ed51948cc77d5ded2a62a948fc4b5177e36038f545877189`.
- 100553 physisch dekodierte Receipts. Artenanzahlen summieren exakt dazu.
  ATP:42099 ausgewählte Zeilen/58390805 kanonische Bytes;
  WTA:54819/75669070. Die verbleibenden3635 sind1915 Availability,
  518 Basefixtures,1162 bestätigte Aufstellungen und **40 Match-Outcomes**.
  Der frische Bestand enthält also40 statt der vorher erwähnten6 Outcomes;
  der Helper hat sie erhalten, nicht ausgeschlossen oder umgeschrieben.
- 31 tatsächliche Snapshot-Ausgaben,16 unterschiedliche Zeitpunkte:
  Payloadsumme66373102 Bytes; Referenzarray-Summe61392466 Bytes und916305
  Referenzen. Alle31 Arraygrößen entsprechen exakt `67*n+1` für die sortierten
  eindeutigen64-Hex-Strings. Alle ausgegebenen Anzahlvergleiche sind wahr,
  bleiben aber ausdrücklich keine Referenzmengen-/Replayvalidierung.
- Referenzarrays belegen92,496% der **aktuell gemessenen** Snapshot-Payloadbytes.
  Dies ist keine Hochrechnung eines künftigen199-Snapshot-Bestands.
- `dbstat` summiert65975 Seiten beziehungsweise270233600 Bytes. Das entspricht
  exakt `page_count*4096` und dem gepinnten Eingabedateiumfang. Freelist=0.
- Vollständiger Abschluss: Exit0, `measurement_completed:true`, unveränderte
  Eingabe-/Quell-/Ancestor-Seals, `resources_ok:true`, keine Gesamtprüfbehauptung.
  Helper83,984632 CPU-/83,993663 Wandsekunden; äußeres GNU time84,00 CPU-/84,06
  Wandsekunden,177556 KiB RSS. Für den Auftrag zählen die äußeren Werte.
- Interpreter `/usr/bin/python3.12`, SHA256
  `1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118`,
  Python3.12.3, SQLite3.45.1; identischer InputSHA/Source724 wie freigegeben.

Der gespeicherte Backup-Metadatensatz bestätigt zuvor88 Datenbanken mit
vollständigem Backup/Restore/HMAC,40,78 CPU-/41,52 Wandsekunden,632128 KiB RSS
und derselben frischen Kontextdatei. Der Reviewer hat nur Metadaten gelesen,
keinen Schlüssel oder Backupinhalt. Bis einschließlich Baseline sind damit
124,78 äußere CPU-Sekunden verbraucht; die wallweite Auftragsdeadline bleibt
zusätzlich Aufgabe des Root-Koordinators.

Für Tag1 sind somit exakt BASE42099/58390805, PRIOR0/0 und der obige vollständige
Baseline-Loghash zulässig. Die tatsächlich anschließenden Wachstumsmessungen
sind nachfolgend getrennt gegengeprüft.

### Abgeschlossene Tagesmessungen und erste exakte Grenze

Alle nachstehenden Logs wurden vollständig gelesen, ihre SHA256 erneut
ermittelt und ihre Summen sowie Abschluss-/Input-/Runtimebindungen read-only
verglichen. Keine zweite Ausführung durch den Reviewer.

| Tatsächlich gemessener Teil | Neue ATP-Zeilen | Neue kanonische Bytes | Gesamte kausale ATP-Historie |
| --- | ---: | ---: | ---: |
| Baseline | — | — | 42099 Zeilen / 58390805 Bytes |
| Tag1 vollständig | 70000 | 100170000 | 112099 / 158560805 |
| Tag2 vollständig | 70000 | 100170000 | 182099 / 258730805 |
| Tag3 bis erster Überschreitung | 6782 | 9705042 | 188881 / 268435847 |

Tatsächliche Rohlogidentitäten:

- `evidence/task14-day1-20260912.log`:
  `da22a2fc6da40c360691312915f1d136842e8a4532c39d2ddfd833885ab96007`.
- `evidence/task14-day2-20260912.log`:
  `59c226e2c3a45cee89af496667de8ae03347af7dd2958b7d7c8b3b84f3db342d`.
- `evidence/task14-day3-20260912.log`:
  `d4cccc6a20926893ad34847aee67f8f808ab672eb4466f30648011cb2ffc194a`.

Jeder Tageslog referenziert exakt den vollständigen SHA seines Vorgängerlogs;
Tag1 den oben genannten Baselinelog. BASE bleibt42099/58390805. PRIOR ist
0/0,70000/100170000 und140000/200340000. Alle vier abgeschlossenen Prozesse
benennen dieselben Source724-, Input- und Interpreter-SHAs, unveränderte
Eingabe-/Quell-/Ancestor-Seals, erfolgreiche Ressourcenprüfung, genau eine
vollständige Mess- und eine Abschlussphase sowie Exit0.

Alle146782 wirklich neu erzeugten, normalisierten, physisch dekodierten und
ausgewählten ATP-Zeilen messen jeweils1431 kanonische Bytes. Daher ist die
gemessene erste Grenze auch rechnerisch exakt:

- Nach146781 zusätzlichen Zeilen:
  `58390805 + 146781*1431 = 268434416` Bytes, noch1040 Bytes unter256MiB.
- Nach146782 zusätzlichen Zeilen:
  `58390805 + 146782*1431 = 268435847` Bytes, **391 Bytes über**268435456.

Der Tag3-Prozess meldet folgerichtig `storage_stop:true`,
`day_completed:false`, `measurement_completed:true`. Das widerspricht sich
nicht: Die notwendige Größenprüfung ist vollständig bis zum ersten Fehler
abgeschlossen; der dritte volle Wachstumstag und damit die gesamte
Sieben-Tage-Probe sind ausdrücklich nicht erzeugt oder bestanden.

### Tatsächliche Kostenbilanz und Schlussfolgerung

| Tatsächlich ausgeführte native Phase | Äußere CPU-Sekunden | Äußere Wandsekunden | RSS KiB |
| --- | ---: | ---: | ---: |
| Frisches Backup/Restore/HMAC | 40,78 | 41,52 | 632128 |
| Baseline | 84,00 | 84,06 | 177556 |
| Tag1 | 98,44 | 98,63 | 44908 |
| Tag2 | 97,20 | 97,24 | 45040 |
| Tag3 bis StorageSTOP | 11,74 | 11,76 | 44904 |
| Summe | **332,16** | **333,21** | kein additiver RAMwert |

Die Bytezähler wurden nativ mit sehr viel weniger als1GiB RSS ausgeführt;
keine große vollständige Python-Historie musste dafür angelegt werden.
Das hebt weder die256MiB-Historyzulassung auf noch misst es den RAMbedarf
eines späteren vollständigen Owner-Replays dieser nicht materialisierten
übergroßen Historie.

Root hat außerdem die chronologische Auftragsdauer konservativ von23:19:00
bis zum tatsächlich gemeldeten Ende23:46:11 UTC erfasst:1631 Sekunden,
einschließlich Zwischenzeit, nicht bloß Summe der nativen Prozesszeiten.
Der Reviewer hat die Differenz gegengerechnet; diese Uhrpunkte stammen aus
Roots Ablaufbilanz, nicht aus den inhaltsbezogenen synthetischen Tagesstempeln.
332,16 gemessene äußere CPU-Sekunden und1631 chronologische Sekunden liegen
unter dem freigegebenen Vorbereitungslimit1800/3600. Root bestätigt den Stopp
ohne weitere native Läufe nach der ersten Größenüberschreitung.

**Ergebnis: B0 StorageSTOP für dieses konkrete konzentrierte synthetische
ATP-Profil.** Die Stoppregel ist eingehalten und nachvollziehbar belegt;
die unveränderte B-Eingabe-/Speichergrenze kann dieses Profil nicht tragen.
Das ist keine bloße lineare Dateigrößenhochrechnung, sondern ein gezählter
Owner-gültiger notwendiger Historygrößenfehler. Es ist weiterhin keine
Repräsentativitäts- oder Produktionsausfallprognose und kein Nachweis einer
vollständig erzeugten199-Snapshot-Datenbank. Kein D4-/Modell-/Feature-Pass,
keine sieben tatsächlichen Betriebstage, keine größere Dateieingabeabnahme.

Der vertraglich richtige nächste Schritt ist deshalb die separate
Speicher-/Eingabevertragsentscheidung vor B-Produktcode. Historienkürzung,
Altdatenumschreibung, bloßes Anheben der Grenzzahl oder ausschließliches
Komprimieren von Snapshotreferenzen wären keine durch diese Messung erlaubte
Reparatur der vollständigen kanonischen Historygrenze.
