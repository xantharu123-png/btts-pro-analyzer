# Task 24 — unabhängiger Review des Workspace-Accounting-Bausteins

Datum: 2026-09-12. Reviewer: `c_source_adapter`.
Scope: ausschließlich der von Root implementierte globale Budgetplan samt
Ownertests; eigene getrennte lokale Gegenproben und dieser Bericht.
Keine Produkt-/Ownertest-, Git-, Server-, Mount-, Dienst- oder Quotaänderungen
durch den Reviewer. Der enge Produktfix wurde ausschließlich von Root erstellt.

## Ergebnis

**Kein verbleibender konkreter Befund innerhalb des ausdrücklich begrenzten
Accounting-/quieszenten Zulassungsvertrags am unten gebundenen Endstand.**

Eine reale Architekturlücke wurde mit zwei lokalen Device-Counterproben
bestätigt: Workspace-Unterverzeichnisse bzw. reguläre Dateien auf einem
anderen Dateisystem konnten den freien Platz des Workspace-Roots verwenden.
Root hat den engen `st_dev`-Abgleich für Verzeichnisse **und** Dateien ergänzt.
Beide zuvor roten Gegenproben sind danach ohne inhaltliche Änderung grün.

Schlusslauf: **90 passed, 3 skipped** (68 Ownertests plus 22 bestandene eigene
Proben, drei eigene native Symlinkproben wegen Windows-Fehler 1314 geskippt).
93 Fälle insgesamt, keine Fehler/Failures, Konsolenlaufzeit 0,79 s;
JUnit-Suitezeit 0,742 s. Dies ist kein Linux-Mount-, Ressourcen-, Schreibquota-,
Lock-/Seal- oder Produktionsnachweis.

## Gelesener und geprüfter Byte-Stand

[workspace_budget.py](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/context_storage_v2/workspace_budget.py)
und [Ownertests](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/tests/test_context_storage_workspace_budget.py)
wurden vollständig gelesen. Nach Roots Fix wurde das vollständige Produkt
erneut gelesen und die ergänzten Ownertests gegengeprüft. Der C/B-Vertrag und
die Writer-/Plattengrenze sind im vorherigen
[Task-22-Review](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/.superpowers/sdd/2026-09-10-context-capacity-recovery/task-22-global-budget-review.md)
vollständig eingeordnet.

| Bestandteil | SHA-256 |
| --- | --- |
| Produkt vor Fix | `4faaf6afade1a1355986cd237ba79b986cdfb9cc0bd717ef5ba2cc4f32a7f6df` |
| Produkt nach Fix, 14 504 Bytes | `b848a43d4d76bb30c0510909870046195d08b86b15a6b2d6b2d8d37aad353580` |
| Ownertests vor Fix | `32b19cc1a555c7c51b8e9e4c384246621a81ed10de9df882361acc28396556b3` |
| Ownertests nach Fix, 12 192 Bytes | `651db3208133c1029525944d3a8df313a58e3f597f123411ec7b68f35a8f4c25` |
| Eigene Schlussproben, 11 100 Bytes | `1b97dec9fe1eec4d443226411adaaf26d06a20a9841977b03db0a1c6ac3546bf` |
| XML erster Gegenlauf | `1a1adfa1ca126c102f10da35116e4e89b4caddef84c9d638cd42b86486ef8637` |
| XML Schlusslauf | `047f21397c3c634c3a39197af896c74624c87ac336cc3512e5a35ecee41d4018` |

Eigene Artefakte:

- [Unabhängige Proben](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/.pytest_tmp/task24-review-394e0716612c4ee98f6d8de3a090abe0/test_workspace_independent.py)
- [Erster Gegenlauf](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/.pytest_tmp/task24-review-394e0716612c4ee98f6d8de3a090abe0/results-before-01.xml)
- [Schlusslauf](C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910/.pytest_tmp/task24-review-394e0716612c4ee98f6d8de3a090abe0/results-after-01.xml)

## Bestätigter und behobener Befund: fremdes Dateisystem

Vor dem Fix prüfte `_directory()` Typ, Link-/Reparse-Eigenschaften und
Identitätsstabilität, aber nicht die Gleichheit mit dem Device des zugelassenen
Roots. `check_quiescent()` summierte die gefundenen Dateien und ermittelte
anschließend freie Bytes nur mit `disk_usage(self.directory)`.

Reproduktion:

1. Echter neuer Windows-Testworkspace mit deklarierten Slots
   `build/main`, `build/main-journal`, `archive`.
2. Echtes Unterverzeichnis `build` und echte Datei `build/main`.
3. Gezielt injizierter, sonst vollständiger `lstat`-Wert mit anderem `st_dev`:
   einmal für Unterverzeichnis plus Datei, einmal für die reguläre Datei allein.
   Alle anderen Statfelder stammen aus dem echten Fixture.
4. Vorher akzeptierte `check_quiescent()` beide Fälle; die jeweiligen
   `pytest.raises(StorageIntegrityError)`-Assertions waren rot.

Die Device-Injektion ist offen benannt: Es wurde **kein** Linux-Bind-Mount,
Windows-Volume-Mount oder sonstiger Mount angelegt. Die Gegenprobe isoliert
genau die falsche Device-/Freiplatzzuordnung, nicht den Betriebssystem-Mountpfad.

Der Fix verwirft nun beide Fälle vor einer erfolgreichen Beobachtung:

- `_directory(path)[0]` muss gleich `self._directory_id[0]` sein;
- auch jede reguläre Workspace-Datei muss dieses `st_dev` haben.

Eine separat versiegelte **externe RO-Eingabe** auf anderem Device bleibt
dagegen zulässig und wird zum aktiven Eingabebudget addiert; sie erhält dort
keine Schreibreservation. Dies ist gesondert positiv getestet. Ein echter
fremder schreibbarer Workspace-Mount kann somit nicht mehr den Platz des
Root-Volumes ausleihen.

## Weitere Gegenproben und genaue Claimgrenze

| Fall | Ergebnis und Einordnung |
| --- | --- |
| Gleiche Dateianzahl, deklarierte Datei in unbekannten Namen umbenannt | Reales Namespace-Fixture wird trotz gleicher Anzahl verworfen; keine reine Count-Abdeckung. |
| Externe Quelle durch gleich große, bytegleiche neue Datei mit wiederhergestellter mtime ersetzt | Reale Ersetzung mit neuem Inode wird verworfen. Keine Gleichsetzung von Dateigröße/mtime mit Quelleigentum. |
| Reale Hardlinks zwischen eigenem Slot und fremdem Fixture | Verworfen; Originalinhalt bleibt unverändert. |
| Reparse-Bit bei ansonsten regulär aussehendem File/Directory | Gezielt injiziertes Windows-Statattribut wird in beiden Fällen verworfen. |
| Native Datei-/Directory-/External-parent-Symlinks | Alle drei Versuche mit Windows-Fehler 1314 nicht verfügbar; ausdrücklich geskippt, nicht grün behauptet. Keine Rechteerhöhung versucht. |
| Frozen-FileSlot nachträglich über `object.__setattr__` verändert | Name, Ceiling und aktive Mitgliedschaft werden über Planbindung verworfen. |
| Instanzcallbacks für `_check_plan`, `_encode_plan`, `sample_free_space` überschrieben | Die intern klassengebundenen Kontrollaufrufe lassen weder Planmutation noch verlorene freie Reserve passieren. |
| Limits-Validator als Instanzcallback ersetzt und Limit aufgeweitet | Die feste `StorageLimits.__post_init__`-Prüfung verwirft den manipulierten Grenzwert. |
| Bool/Float/None/negative/zu kleine freie Bytes | Verworfen; keine implizite numerische Zulassung. |
| Ein Byte Payload, aber injizierte `st_blocks` über Slot | Verworfen; wo geliefert, zählen Allokationsblöcke und nicht allein Nutzbytes. Dies ist kein gemessener ext4-Allokationsbeweis. |
| Gleich große neue Bytes in bestehendem Output-Slot | Erwartungsgemäß als Accounting weiter zulässig. Der Planhash bescheinigt keine Output-/D2-/Modellwahrheit. |
| Zusätzliche Datei während ausschließlich `sample_free_space()` läuft | Die reine Freiplatzprobe bleibt keine Namespacequota; der nächste quieszente vollständige Scan verwirft die Datei. Das ist dokumentierte Arbeitsteilung. |

### Reale Windows-Änderung während des Scans: keine Snapshotgarantie

Der erste eigene Lauf hatte neben den beiden Device-Befunden eine dritte
rote Assertion: Ein echter neuer Directory-Eintrag unmittelbar nach Ende der
Enumeration wurde unter diesem Windows-Lauf nicht bereits durch den
nachfolgenden Stat-Epochvergleich erkannt. Die erste Probe hatte fälschlich
verlangt, dass **jede** solche Mutation zwingend sofort erkannt werden müsse.

Dies verletzt jedoch die ausdrücklich erforderliche Quieszenz des API-Aufrufs.
Der Produktvertrag behauptet weder einen atomaren Filesystemsnapshot noch eine
Garantie über ein unbeobachtetes Intervall. Der Reviewer hat daher **nur die
eigene Scope-Probe** korrigiert: sofortiges Verwerfen ist erlaubt; wird der
späte Eintrag in diesem provozierten Race nicht gesehen, muss der nächste
tatsächlich quieszente Scan ihn als undeclared erkennen. Genau das geschieht.
Für diesen Fall gab es keine Produktänderung. Der erste rote XML-Beleg bleibt
erhalten; die beiden Device-Proben wurden durch diese Korrektur nicht verändert.

Daraus folgt eine konkrete Integrationspflicht, kein weiterer hier zugesagter
API-Fix: NativeOwner muss Exklusivjob-/Writerstillstand tatsächlich herstellen.
Die zusätzlichen Epochchecks sind kein Ersatz dafür. Dasselbe gilt für
Root-Seals externer Eingaben, offene unlinked FDs und FD-/Prozessbaumlebensdauer.

## Verifizierte Arbeitsteilung des Bausteins

Die Modulbeschreibung und öffentlichen Methoden sind angemessen enger als
eine native Quote formuliert:

- Der gesamte explizite feste Plan inklusive Metadaten wird vorab gerechnet;
  Löschung gibt keinen neuen Reservationstopf und es gibt keine Release-/Reset-API.
- Eigene aktive Slots und deklarierte externe Inputs bilden gemeinsam die
  4-GiB-Zulassung; alle eigenen Dateislots gemeinsam die 8-GiB-Hülle.
- Quieszenter Abgleich fordert echte freie Reserve plus verbleibende
  Reservationsbytes. Laufende Beobachtung prüft aktuellen freien Platz.
- Unbekannte/zusätzliche Dateien, Verzeichnisse, Links und fremde Devices sind
  Fehler, keine stillschweigenden neuen Slots.

Damit ist noch nicht bewiesen, dass irgendein konkreter SQLite-Writer diesen
Plan einhält. Der Caller muss alle Journale, Archive, Fehler-/Retrydateien,
Manifeste, eigene Prüfartefakte und jeden möglichen Diskspill **vorher** in
den geschlossenen Plan aufnehmen bzw. Spill durch das nachgewiesene
Writerprofil ausschließen. Native Limits gelten vor Wachstum, nicht erst
nach einem späteren `check_quiescent()`.

`directory_metadata_bytes` und Slotceilings sind deklarierte
Accounting-Allokationswerte, keine von diesem Modul berechneten universellen
Dateisystem-Obergrenzen. Insbesondere beweist ein Windows-Stat ohne
`st_blocks` nicht die physische Allokation eines Linux-Dateisystems.
Die in Task 22 beschriebene physische Hülle ist weiterhin gesondert zu belegen.

Auch ein neuer `WorkspaceBudget`-Pythonwert ersetzt kein persistentes Job-/
CPU-/Deadlinekostenbuch und keinen Root-gehaltenen Exklusivlock. Die globale
Auftragsidentität, alle alten Artefakte und das Verbot eines neuen Budgets für
denselben Auftrag bleiben beim künftigen NativeOwner. Keine HMAC-/B-Publikation
darf allein aus `plan_digest` oder einer `SpaceObservation` abgeleitet werden.

## Testausführung und Abschluss

Gebündeltes Python 3.12.14 mit `-B -m pytest -p no:cacheprovider`,
`PYTHONPATH=C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
Beide Läufe nutzten jeweils neue, zuvor nicht vorhandene Workspace-Basetemps
unter dem eindeutigen eigenen Reviewverzeichnis und getrennte JUnit-Dateien.
Es wurden keine vorhandenen QA-/Appdateien gelöscht.

Erster Lauf am ursprünglichen Produkt: 3 failed, 19 passed, 3 skipped;
davon zwei konkrete Device-Befunde und eine danach ausdrücklich korrigierte
Vorbedingungs-Assertion, wie oben vollständig erklärt.

Schlusslauf am gebundenen Root-Fix: 90 passed, 3 skipped, Exit 0.
Der konkrete Accounting-Review ist damit abgeschlossen. Nächster relevanter
Schritt bleibt die Integration in den wirklichen kontrollierten Writer und
persistenten NativeOwner samt nativen Fehler-/Ressourcenproben; nicht Git-/
Produktionsfreigabe und nicht ein aus diesen lokalen Tests abgeleiteter C6-Pass.
