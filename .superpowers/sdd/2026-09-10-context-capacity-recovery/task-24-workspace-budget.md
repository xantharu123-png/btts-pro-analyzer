# Task24 — vollständiger fester Workspace-Reservierungsplan

12.September2026. Root besitzt ausschließlich neues
`context_storage_v2/workspace_budget.py` und dessen Testmodul.
Keine bestehenden Runtime-/Modell-/Datenquellen geändert; keine produktive
Aufrufroute, kein Serverlauf und keine globale/native Abnahme.

Der Baustein inventarisiert vorab einen geschlossenen Satz genauer Dateislots
mit festen Byteobergrenzen: neue Archive, Indizes, Datenbanken, Journale und
alle eingeplanten Fehlversuche. Ein separater fester Betrag zählt sämtliche
Verzeichnismetadaten. Bestehende externe aktive Eingaben werden zusätzlich
vollständig als unveränderte Dateiidentitäten gebunden. Reservierungen sind
ein Gesamtplan, kein frisch nutzbarer 8-GiB-Betrag je Datei oder Aufruf.

`check_quiescent()` gleicht alle benannten Workspace-Einträge samt logischer und
tatsächlich allokierter Größe ab. Unbekannte Dateien/Verzeichnisse, zusätzliche
Journale, Links/Sonderdateien, Typfehler, Dateitausch oder geänderte Limits sind
Fehler. Alle aktiven Inputceilings müssen gemeinsam unter4GiB, sämtliche
Workspaceceilings unter8GiB bleiben. Aktuell freier Platz muss darüber hinaus
die gesamte noch offene Reservierung plus echte4GiB-Reserve tragen.
`sample_free_space()` ist eine erneute tatsächliche Momentbeobachtung, kein
Schutzversprechen gegen ungemessene Fremdschreiber.

Keine Release-/Reset-/Delete-/Resize-Methode: Auch nach dem Löschen einer
Datei bleibt deren volle mögliche Maximalbelegung dem Gesamtplan zugeordnet.
Ein neuer Retrypfad muss schon als weiterer Slot im gemeinsamen Plan stehen.

## Bewusst keine vorgetäuschte Durchsetzung

Dieser Baustein ist Accounting und Zulassungsprüfung, nicht der native Writer.
Der folgende Owner muss exklusiven Auftrag, versiegelte externe Inputs,
vollständige physische Allocationhülle und feste vorab begrenzte Writerpfade
nachweisen. `FileSlot.ceiling_bytes` ist noch kein solcher Nachweis und ein
Hash keine Root-/B-Berechtigung. Offene unbenannte Dateien/TEMP/Statementjournale
können niemals allein durch diesen Diskwalk sicher begrenzt werden.

Die Quieszenzbedingung ist absichtlich explizit: ein Writer darf nicht parallel
zur vollständigen Reconciliation laufen. Während nativer Arbeit benötigt es
zusätzlich den begrenzenden Writer und die fortlaufende Reserveüberwachung.
Alle beobachteten Fehler muss der native Auftragsowner dauerhaft invalidieren;
ein späterer guter Samplingwert löscht keinen früheren Auftragsfehler.

## Bisherige lokale Tests, unabhängiges Review läuft

66/66 bestanden in0,48s. Echte lokale Dateien/Dateitausch/Hardlinks und vollständige
Namespaces; freie Platzwerte werden gezielt injiziert, nicht als VPS-Messung
ausgegeben. `.pytest_tmp/task24-workspace-01.xml`, SHA256
`885db4bd39b377f524650208d263d99e1865853ea0f2320e68aefef26f02d5d4`.

Code dieses ersten Prüfpunkts:
`4faaf6afade1a1355986cd237ba79b986cdfb9cc0bd717ef5ba2cc4f32a7f6df`;
Tests `32b19cc1a555c7c51b8e9e4c384246621a81ed10de9df882361acc28396556b3`.
Unabhängiges Review durch c_source_adapter ist beauftragt. Root hat insbesondere
ein noch mögliches Unterverzeichnis-Mount auf anderem Volume zur Reproduktion
gemeldet: eine Root-Free-Spacebilanz darf niemals Platz auf fremdem Device
substituieren. Kein endgültiges findings-free- oder Releaseurteil an dieser Stelle.

## Nachfolgender Fix und unabhängiger Abschluss

Beide echten Device-Counterproben bestätigten den Fehler. Root prüft jetzt
`st_dev` jeder Workspace-Datei UND jedes Unterverzeichnisses gegen den Root.
Externe unverändert gebundene RO-Dateien auf anderem Device bleiben zulässig;
dort wird kein Schreibslot mit fremdem freien Platz reserviert.
Ownertests nach Fix: 68 bestanden, 0,48s,
`.pytest_tmp/task24-workspace-02.xml`.
Code `b848a43d4d76bb30c0510909870046195d08b86b15a6b2d6b2d8d37aad353580`,
Tests `651db3208133c1029525944d3a8df313a58e3f597f123411ec7b68f35a8f4c25`.

Unabhängiger Schlusslauf unveränderter roter Device-Proben plus Ownertests:
90 bestanden, drei tatsächliche Windows-Symlink-Skips, 0,79s. XML
`.pytest_tmp/task24-review-394e0716612c4ee98f6d8de3a090abe0/results-after-01.xml`,
SHA `047f21397c3c634c3a39197af896c74624c87ac336cc3512e5a35ecee41d4018`.
Review `task-24-workspace-budget-independent-review.md`, SHA
`4f18f9f2ed8d8f78dc31dea0e7e46d366e87d3db065826b40013a46704e392ef`.
Keine weiteren konkreten Findings innerhalb des beschriebenen Accounting-
Vertrags. Eine absichtlich parallel zum Scan erzeugte Datei ist ausdrücklich
keine atomare Snapshotgarantie; der NativeOwner muss Quieszenz herstellen.
Physische Allokationshülle, tatsächliche native Writergrenzen und globaler
Auftrag bleiben Integrationspflichten, nicht durch diese Tests erledigt.
