# C4 R1c: Partielle native Scopekorrektur bleibt ungewiss

9. September 2026. Eigener C4-Worktree, Ausgangspunkt
`be45dab58c38f781554e0671c4205c753f343d35`.

Dieser Nachtrag dokumentiert die vom Controller bestätigte und freigegebene
Korrektur eines zusätzlichen P2 aus dem unabhängigen R1b-Nachreview. Er ersetzt
weder dessen Finding noch einen der vorherigen Audit-/Reviewberichte. Alle
ursprünglichen Bericht-, Repro- und Assertionbytes bleiben erhalten. Der
R1b-Nachreview wurde nicht rückwirkend zu einem PASS umgeschrieben.

## Tatsächlicher Fehler und getrennte Kontrollfälle

Der frühere Selektor erkannte eine unvollständige eigene Faktenrevision nur
dann als Fortbestand alter Identitätsunsicherheit, wenn sich die Menge nativer
Teilnehmer änderte. Eine neue native Saison bei gleichen Teilnehmern wurde
dagegen nicht so behandelt. Ein neuer unvollständiger Serienreceipt mit
`winner_id`, beiden Scores und beiden tatsächlichen Zeiten sämtlich null konnte
dadurch die alte Serie aus der Ziel-Saison herausfiltern. Die verbliebene ältere
Historie ergab anschließend verfügbare Nullbelastung und vermeintlich exakte
Erholung von 150 Stunden statt Ungewissheit.

Die echten temporären B1-SQLite-Fälle zeigen beide Scope-Receipts weiterhin in
der Datenbank. Es fehlte kein Quellendatensatz, sondern eine owning
Revisionsprüfung. Der Fall tritt auf beiden Zielseiten sowohl direkt als auch
nach tatsächlich empfangener Absage plus späterer anderer Mapmeldung auf.
Die vorhandene frühere Serie hatte 09:00 als Ende, Empfang 09:01; Entscheidung
war 12:00 bei Zielbeginn 18:00. Die neue unvollständige Scopekorrektur wurde um
11:30 empfangen. Bei Absage war die Serienerholung zuvor richtig unbekannt.

Vier unveränderte positive Gegenfälle belegen die andere Seite: Eine wirklich
vollständige neue native Scopekorrektur darf den alten Scope zurückziehen.
Dies wird nicht durch ein globales Saison- oder Korrekturverbot ersetzt.

## Enger Eingriff

Nur `context_models/esports.py` wurde fachlich geändert. Die schon vorher
vorhandene vollständige kanonische Ereignis-/Scopeidentität wird nun auch in
der Prüfung einer unvollständigen eigenen Serien-/Maprevision verwendet.
Sie bindet alle bestehenden nativen Eventfelder und den geschlossenen Scope.
Der tatsächliche Eventstatus bleibt wie bisher aus diesem Identitätsdigest
ausgenommen und wird separat durch die bestehenden Lifecycle-Regeln behandelt.
Damit bleiben normale `started -> completed`-Folgen gültig.

Die Identitätsfunktion wurde innerhalb desselben Selektors vor ihre erste neue
Verwendung verschoben; es gibt keinen zweiten Identitätsbegriff. Eine partielle
Revision mit früheren abweichenden Identitäten behält die bestehenden
Unsicherheits- und Quellenbelege. Eine vollständige Revision darf wie bisher
ihre Vorgänger ablösen. Derselbe-Scope-Receipts ohne exaktes Ende bleiben reine
Empfangsgrenzen und werden nicht künstlich zu exakten Zeiten aufgewertet.

Unverändert sind der Quellennormalisierer, `esports-native-status-subject-v2`,
generisches B1, persistierte Schemas und alte Receipts, B2, B3, Elo und die
Originalbasis. Keine Migration, kein neues Flag und keine Quellenabfrage.
Die alten mathematisch exakten Differenz- und Wiederherstellungsregeln werden
nicht gelockert.

## Eigene TDD und Regressionen

Neue permanente Datei `tests/test_esports_context_scope_revisions.py`:

- komplette und partielle Saisonkorrektur, beide Teams, mit/ohne Absage;
- tatsächlicher Empfang bei cutoff minus/gleich/plus einer Mikrosekunde;
- Ablaufdatum unmittelbar vor/gleich/nach dem Cutoff;
- identischer Scope mit fehlendem tatsächlichem Ende bleibt nicht-exakt.

Der unveränderte neue Dauertestlauf auf dem alten Modellhash `ddd7be07...`
ergab **7 echte RED / 8 GREEN**, 13,75 s. Alle sieben Fehler waren tatsächlich
falsch verfügbare Werte; keine Harness- oder Collectionfehler. Keine Assertion
wurde nach dieser Ausführung geändert.

Nach dem Sourcefix: neue 15 Dauertests plus beide unveränderten neuen
unabhängigen Probe-Dateien, zusammen **46 bestanden**, 36,36 s. Das umfasst
die vorherigen fünf roten Testinstanzen desselben einzelnen P2. Die alten
R1b- und R1/R2-Proben sind getrennt unverändert erhalten.

Der eigene breite Fokus ist mit **1.012 bestanden**, ohne Skips, in 167,10 s
abgeschlossen. Er enthält sämtliche bisherigen 259 C4-/unabhängigen Fälle,
die neuen 46 sowie B1-Verträge/-Beobachtungen, B2, B3, E-Sport-Shadow,
Multi-Sport-Empfehlungen, Workflow-Integrität und Marktscope. JUnit:
`.pytest_tmp/c4-scope-owner-broad-01.xml`.

Die vollständige eigene Worktree-Regression ist mit **4.220 bestanden,
18 erwarteten Plattform-Skips und 97 bestandenen Untertests** in 294,90 s
abgeschlossen. JUnit: `.pytest_tmp/c4-scope-owner-full-01.xml`, keine Fehler.
Alle 18 Skip-Gründe wurden im tatsächlichen XML geprüft: 13 fehlende Windows-
Symlinkrechte und fünf POSIX-Eigentümer-/Dateimodus-/umask-Prüfungen. Kein
numerischer C4-Fall wurde übersprungen. Ein Teststand des Controllers oder
eines anderen Worktrees wird nicht als eigener Nachweis verwendet.

`git diff --check` ist fehlerfrei. Die drei vorgesehenen Änderungen sind genau
das owning Modell, die neue Dauertestdatei und dieser Nachaudit. Source- und
Testbytes blieben während beider abschließenden Läufe eingefroren. Die
unabhängige Nachprüfung dieses Fixes erfolgt erst nach dem fokussierten Commit
und bleibt bis dahin offen; die eigenen Tests ersetzen sie nicht.

## Eingefrorene bisherige Belege

```text
8a96fb0f86c2645e01bbf86eb157b1da14f34d6dde8f7b954257620304e8e269  .pytest_tmp/c4-second-independent-20260909/REVIEW.md
30a2b0341a5337526edc8c64a68ab93bc46f914f7b6ea151dc1ee1e328d985ab  .pytest_tmp/c4-second-independent-20260909/test_second_c4.py
b7d6eed5c08e3296ffff413d3a6fe38a838503bcd12f95f25c0c3e5c947cbdaf  .pytest_tmp/c4-second-independent-20260909/test_scope_revision.py
f5dbffebf6582f0fb07c10ea41d6798f354a3446116cf1990f3212d04d32b619  .pytest_tmp/c4-second-independent-20260909/probes-01.xml
9a3fdebcB4bac18c6510d96806bbbe23a5a4e2a4e5e55b7cd89cba505d6da546  .pytest_tmp/c4-second-independent-20260909/scope-01.xml
368225251b6b3dfd8a98ce58fd3551de5daec05077adae030c143e0420157f3b  .pytest_tmp/c4-scope-owner-red-01.xml
b552b257e827c23d984d12965a7ae1969740d691a542b50923caf20f23179bc9  .pytest_tmp/c4-scope-owner-green-01.xml
f53616573eb782317683fc054e057320291a31b8070723947483cf2583da4ffb  .pytest_tmp/c4-scope-owner-broad-01.xml
fb6dd4a22c4c4e8d21bfe7434fb5122ca302149ba79a5c401b8544b1c17d2f19  .pytest_tmp/c4-scope-owner-full-01.xml
d2c95016828fde4b0c30f7849f239b647cdd12c1b97fa7a0fb7c8a287bf26e33  context_models/esports.py
d2e9bd62a7600c88cbe435db028d2da03537320eec8f45e40150acad96d5b065  tests/test_esports_context_scope_revisions.py
6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567  context_sources/esports.py (unverändert)
bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140  esports_elo.py (unveränderte rohe geladene Bytes)
```

Die ebenfalls unveränderte Git-Blobidentität von `esports_elo.py` ist
`ca390bc51976a5ce598c9a2a952568cd25439ca2`; sie ist kein Ersatz für den oben
separat aufgeführten SHA256 der tatsächlich geladenen Dateibytes.

Der eigene Nachreview vor dieser Implementierung enthielt 259 grüne
bestehende/übernommene Fälle, aber das zusätzliche qualifizierte P2. Dieser
historische Zustand bleibt korrekt dokumentiert und ist keine Fixfreigabe.

## Grenzen

Die Quelldaten dieser Tests sind synthetischer nativer Transport, keine neue
PandaScore-Erhebung. Es gibt keine neue echte Spieler-/Kaderhistorie, D1/D2-
Population, empirische Wirkungsfreigabe oder produktive Ermüdungsbewertung.
Keine Worker-/UI-/Browser- oder VPS-Aktivierung wird hier behauptet. Ohne
passende D2-Freigabe bleibt die Originalbasis in Verwendung.

Cricket, Preise und Sortierung, Echtgeld, 15K, Tickets, Abrechnung, historische
Prognosen und der VPS wurden nicht verändert. Die bekannte rohe Elo-Datei-
Bytegrenze über unterschiedliche Checkouts/Betriebssysteme bleibt bestehen;
dieser Bericht behauptet keine plattformübergreifende Rezeptidentität.
Es wurden keine Providerabfragen, Git-Pushes oder Serveraktionen ausgeführt.
