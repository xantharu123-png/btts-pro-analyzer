# C4: Korrekturen aus dem unabhängigen Review

9. September 2026, eigener Branch `codex/kontext-c4-esports-20260909`,
Ausgangspunkt `26e891096ecee78ac962b5090a8294deefd7d395`.

Dieser Nachtrag ersetzt weder den ursprünglichen C4-Audit noch den unabhängigen
Reviewbericht. Beide bleiben bytegleich erhalten. Der Auftrag erlaubt nur die
Korrektur der belegten C4-R1-/C4-R2-Grenzen, eigene Dauertests und diesen Bericht;
keine Provider-, Produktionsdaten-, VPS-, Git-Push- oder Aktivierungsaktion.

## Unveränderter Review und selbst bestätigtes RED

Vollständig gelesener unabhängiger Bericht:
`.pytest_tmp/c4-independent-20260909/REVIEW.md`, SHA256
`201130cf5ba5a009c98c08df0f59aa79759b1c9605b47035d9ee7017a1f3f722`.

Die eingefrorenen Gegenproben wurden unverändert selbst ausgeführt:

- `test_independent_c4.py`: `1504b746aa9e19eaf44a485cf0ad391414adacfd091559a1e90cba164371bd2b`.
- `test_additional_c4.py`: `777cd1c2aabcf54777ee4df9b4395a68076d19738a2dc428e96e699bd9f0df5e`.

Ergebnis auf dem alten Sourcecode: **8 fehlgeschlagen, 59 bestanden**, 32,49 s,
JUnit `.pytest_tmp/c4-owner-review-red-01.xml`. Die acht roten Originalassertions
entsprechen exakt dem Review; keine wurde verändert oder als Skip ausgeblendet.

## C4-R1: Terminalen Serienabschluss nicht aus anderem Fakt wiederherstellen

Die frühere faktübergreifende Identität ließ den Eventstatus beim Join bewusst
weg, damit eine normale `started -> completed`-Entwicklung tatsächliche Maps
nicht zerstört. Dabei blieb im umgekehrten Fall ein alter Serienabschluss
gültig: Eine spätere echte native `started`-Meldung zusammen mit einer
abgeschlossenen Map ließ Serienanzahl 1 und vermeintlich exakte Erholung 9 h
weiter verfügbar erscheinen. Die Map belegt weder einen abgeschlossenen
Elternwettkampf noch dessen Endzeit.

Der erste enge Fix verwirft terminalabhängige alte Serien-/historische
Lineup-Fakten beim laufenden Elternstatus und verwendet einen Mapreceipt nicht
als obere Grenze eines noch nicht abgeschlossenen Serienendes. Tatsächlich
abgeschlossene einzelne Maps bleiben separat erhalten. Neue Tests prüfen
beide Teams, 1/3/7-Tage-Fenster, exakte und minimale Erholung, tatsächlichen
Empfang bei cutoff-1/0/+1 Mikrosekunde, abgelaufene Statusmeldungen und eine
neue ausdrücklich terminale Serienrevision mit neuer Endzeit.

Zusätzlicher eigener Lebenszyklusgegenlauf entdeckte danach eine eng verwandte
R1-Lücke: Eine spätere `observed_lineup(completed)` oder eine neue
`map(completed)` desselben nativen Map-Fakts konnte den bereits zurückgenommenen
alten Serienabschluss wiederherstellen. Bei derselben Map-ID verlor der
generische B1-Latest-Pfad außerdem die vorherige `started`-Revision, da der
C4-Subject bislang nur Teilnehmer, Scope und Faktart band. Der Controller
erhielt beide konkreten REDs vor einer Erweiterung des Quellenvertrags.

Originales zusätzliches Repropaket:
`.pytest_tmp/c4-owner-lifecycle/test_retraction_retention.py`, SHA256
`b9e3afa28f630060ebaa61100fedb0fc0def57a6757ac7b73e3851c8b8e4c1ec`.
Beide Repros sind in den neuen Dauertests enthalten; ein weiterer Dauertest
prüft den Erhalt der echten Zwischenrevision auch bei später gültiger
Serienabschlussmeldung.

Der Controller hat die enge Quellenidentitäts-Erweiterung ausdrücklich
freigegeben. Die interne Payload-Shape `esports-internal-native-context-v1`
ändert sich nicht. Neu ist die owning Subjectidentität
`esports-native-status-subject-v2`: Ihr Digest bindet Version, beide nativen
Teilnehmer, vollständigen bisherigen Scope und den tatsächlich normalisierten
`event.status`. Der bestehende Faktart-/Map-ID-Suffix bleibt unverändert.
Dies ist weder ein frei übergebenes Verifiziert-Flag noch eine neue B1-Tabelle
oder Änderung des generischen Selektors.

Dadurch behalten `observations_as_of`-Ergebnisse tatsächliche unterschiedliche
Statusrevisionen auch dann, wenn dieselbe Map später aktualisiert wird. Der
C4-Resolver prüft terminalabhängige Fakten gegen jeden wirklich erhaltenen
jüngeren `started`-Receipt. Ein späterer anderer Fakt mit `completed` stellt
die zurückgenommene alte Serien-Endzeit nicht wieder her. Erst eine neu
empfangene terminale Serienrevision nach der Korrektur kann ihre eigene
Ergebnis-/Endzeit belegen. Ein vor dem Cutoff noch nicht empfangener Receipt
bleibt ausgeschlossen; ein abgelaufener Receipt macht seinen zuvor belegten
Widerruf nicht rückwirkend ungeschehen.

Die ursprüngliche unversionierte Subjectidentität wird nicht stillschweigend
als v2 interpretiert. Ein eigener echter B1-Gegenfall mit alten Subjectbytes
wird vom owning Rebuild typisiert abgelehnt. Es findet keine Datenmigration,
kein Umhashen historischer Receipts und kein Umschreiben früherer lokaler
C4-Referenzen statt. Der C4-Pfad ist weiterhin noch nicht produktiv freigegeben.

Eine abschließende Konsistenznegative war ebenfalls zunächst rot: Auch ein
neu empfangener Serienreceipt darf nicht Ende 09:00 behaupten, wenn eine
tatsächlich zu demselben nativen Event/Teilnehmer-/Scope gehörende abgeschlossene
Map erst um 10:00 endet. Solche widersprüchlichen Serienwerte bleiben
`conflicting`; die tatsächliche Map bleibt messbar. Nur vorhandene tatsächliche
Endzeiten werden verglichen, keine fehlende Endzeit oder Mapdauer geschätzt.
Die positive neue konsistente Serienrevision mit Ende 11:15 ergibt stattdessen
ihre eigene korrekte Erholung von 6,75 h, nicht die zurückgenommene alte von 9 h.

## C4-R2: Abgeleitete Merkmale exakt an ihre Komponenten binden

Die Produzenten berechnen bereits exakt `current - reference` beziehungsweise
`home - away`. Der Konsument verwendete fälschlich `abs_tol=1e-12`. Damit
konnte ein von den unveränderten Komponenten belegter Nullwert durch `9e-13`
ersetzt werden. Ein großer, endlicher synthetischer Koeffizient verwandelte
dies in einen deutlichen experimentellen Logit-Effekt. Ohne D2 blieb die
tatsächlich verwendete Basis korrekt unverändert; ein live aktivierter oder
empirisch gelernter Einfluss wurde hier nicht nachgewiesen.

Die Integritätsprüfung verlangt jetzt mathematisch exakt denselben Wert aus
denselben Operanden, ohne Toleranz, Rundung oder Clipping. Das gilt für
Teilnahme-, Serien-/Mapanzahl- und Erholungsdifferenzen. Permanente Negativtests
prüfen den kleinsten positiven Float über Null, +/-9e-13 und 1-ULP-Abweichungen
bei einem echten nichtnulligen Wert. Gültige exakte Nullwirkungen erhalten
Originalparameter und -märkte weiterhin bytegleich, auch bei dem großen
synthetischen Testkoeffizienten. Der B3-Pfad darf eine abweichende Differenz
nicht als experimentellen Vergleich oder normale Datenlücke durchlassen.

## TDD- und Zwischenstände

Alle Läufe mit
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`,
`-B -m pytest -q -p no:cacheprovider`, jeweils neuem `--basetemp` und JUnit.

| Lauf | Ergebnis |
| --- | --- |
| `c4-owner-review-red-01` | unverändertes unabhängiges Paket: 8 rot, 59 grün; 32,49 s |
| `c4-owner-permanent-red-01` | neue Dauertests vor Sourcefix: 24 echte REDs, 5 positive Kontrollen; 14,25 s |
| `c4-owner-green-01` | erster enger Fix: 227 grün einschließlich aller 67 unveränderten Reviewerfälle; 74,53 s |
| `c4-owner-lifecycle-red-01` | zusätzliche native Rücknahme-/Refreshfälle: 2 rot; 3,79 s |
| `c4-owner-retention-red-02` | permanente Lebenszyklus-/Belegerhaltfälle: 3 rot, 1 Kontrolle grün; 5,35 s |
| `c4-owner-green-02` | Subject-v2/Rücknahme-Fix: 233 grün einschließlich unveränderter Reviewer- und eigener Lifecycle-Repros; 82,51 s |
| `c4-owner-consistent-end-red-01` | tatsächlicher Serien-/Map-Endwiderspruch: 1 rot; alte Subjectbytes korrekt abgelehnt: 1 grün; 3,24 s |
| `c4-owner-final-focus-01` | endgültiger Code: 235 bestanden, 80,48 s; sämtliche unveränderten Reviewer-Repros und 35 neue permanente Tests |
| `c4-owner-final-full-01` | ganze Suite: 4.189 bestanden, 18 erwartete Windows-Skips, 97 Untertests; 268,62 s, Exit 0 |

Nur die beiden letzten Läufe betreffen den endgültigen Code. Sämtliche Source-
und Testhashes unten wurden nach der ganzen Suite nochmals unverändert geprüft.
Die Korrektur ist bereit für den fokussierten Commit und die unabhängige
Nachprüfung; deren Ergebnis wird hier nicht vorweggenommen.

Die finale Fokusdatei heißt `.pytest_tmp/c4-owner-final-focus-01.xml`, SHA256
`e0f8a77e78725612e950a9c2dfc00ad9113291299f708bbec82a137c0965aede`.
Die 235 Fälle bestehen aus 131 bestehenden C4-Tests, 35 neuen Dauertests,
67 unveränderten unabhängigen Reviewerfällen und zwei unveränderten zusätzlichen
Lifecycle-Probes. Die neue Dauertestdatei `tests/test_esports_context_corrections.py`
wird außerdem von der regulären ganzen Suite gesammelt.

Der vollständige Lauf erfolgte aus diesem C4-Worktree, nicht dem inzwischen
weiterentwickelten Root-Integrationszweig:

```text
C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe -B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/c4-owner-final-full-01 --junitxml=.pytest_tmp/c4-owner-final-full-01.xml
```

Vollsuite-JUnit SHA256:
`7ae60fa91b33da75ab056855244c5035c3e439c6a6ee4d6b8698d5464b54e3ff`.
Die 18 Skips wurden aus genau dieser XML gelesen: 13 Fälle ohne verfügbare
Windows-Symlinkberechtigung und fünf POSIX-Owner-/Mode-/Umask-Fälle. Kein neuer
C4-Fall wurde übersprungen. Das ist kein Linux-/Produktionsberechtigungsnachweis.
Die ursprünglichen unabhängigen Reprodateien und der erste Reviewbericht
behielten auch nach der Vollsuite ihre oben aufgeführten exakten Hashes.

## Eingefrorene Source- und Testbytes, nach der Vollsuite erneut geprüft

| Datei | SHA256 |
| --- | --- |
| `context_sources/esports.py` | `6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567` |
| `context_models/esports.py` | `c09cc9661eae812caba205119ae21184ecce0ae6150a890cd83d6ec6957d052c` |
| `tests/test_esports_context_corrections.py` | `57b1270062de31224551bb90eff148104834b32a76a2676e1d86a4364da1cc74` |

Unverändert gegenüber dem originalen C4-Paket:

| Datei | SHA256 |
| --- | --- |
| `multi_sport_recommendations.py` | `80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5` |
| `context_models/contracts.py` | `e538ddd05128504996a7bb25892e30e6d75b979397cb54343854910bd226be33` |
| `context_snapshots.py` | `746f0b2d265088fb82caf3bc884b269896bd275489a06c9f9b01dba0b89d35ee` |
| Originalaudit `2026-09-09-c4-esports.md` | `a06859f7101d4f603b80bc97d943516f96ff6eccbb28bc0c7adce176c110f9b5` |

Die tatsächlich gelaufenen roten JUnit-Belege bleiben erhalten:

| Datei unter `.pytest_tmp` | SHA256 |
| --- | --- |
| `c4-owner-review-red-01.xml` | `12f3bd5b24826a0a4ea56d71444433ae8a6e1e973bc62c2b8aba32a96a865b03` |
| `c4-owner-permanent-red-01.xml` | `69719bacc0fce4177c141c94d0359ac09330db23dbadfe753d09dcea78ca9d5a` |
| `c4-owner-retention-red-02.xml` | `972aaaca9b2f3d7e816f1a793dd02d5314d56d40cb78a2678af3181bc08f76cb` |
| `c4-owner-consistent-end-red-01.xml` | `e4a010c7aab4bd6c4610a4fa41e8ee91994cafd68f83de5a6018afc8caae67fa` |

## Unveränderte Grenzen

- Keine Änderung am alten Default-Elo-/Serienalgorithmus, dessen Ausgabe,
  Quoten-/Rankingmerkmalen, Cricket, 15K, Tickets, Abrechnung oder Alt-Snapshots.
- `esports_elo.py` bleibt im eigenen Checkout roh
  `bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140`,
  Git-Blob `ca390bc51976a5ce598c9a2a952568cd25439ca2`. Die dokumentierte
  abweichende Root-Zeilenendefassung bleibt unverändert; keine LF-Normalisierung.
- Der interne C4-Transport ist weiter kein echter PandaScore-Kontextadapter.
  Reale Roster-/Patch-/Veto-/Mapzeitdaten und native D1/D2-Assembly fehlen
  weiterhin. Synthetische Mechaniktests sind keine empirische Modellfreigabe.
- Kein gelernter fixer Müdigkeits-/Ausfallprozentsatz, keine medizinische
  Behauptung und keine Rekonstruktion tatsächlicher Dauer aus Serienständen.
- Root-Integration, erneutes unabhängiges Review und jede spätere
  Produktionsaktivierung sind getrennte Schritte. Dieser Ownerfix allein
  erklärt weder C4 insgesamt noch die Anwendung als fertig.
