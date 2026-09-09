# D1-Nachreview: Identitätsauflösung aus vollständigem kausalem Receiptpool

9. September 2026. Disposition: **PASS für die gezielte Korrektur**.
Der ursprüngliche P2 ist geschlossen; kein neues Finding in diesem Delta.

Prüfobjekt: unveränderter, sauberer Commit
`f4649c305c653d35db054e7d6ead2058ca8af3df` im owning Worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-d1-training-20260909`.
Vergleichsbasis: `b74e2abd759a952991559709833470b3c3b160c0`.

Keine Source-, Git-, Provider-, Server-, Produktions-, Geld- oder
Aktivierungsänderung. Nur eine neue eigene Testdatei und dieser separate
Nachbericht wurden im vorhandenen Reviewer-QA-Ordner erstellt. Die beiden
ursprünglichen Reprodateien und der ursprüngliche Bericht sind bytegleich
erhalten; keine ursprüngliche Erwartung wurde angepasst.

## Geprüftes Delta

Der Drei-Dateien-Diff wurde vollständig gelesen: `context_models/replay.py`,
`tests/test_context_replay_identity_refresh.py` und der vollständige
Reviewnachtrag des Owner-Audits. Die Produktivänderung ist exakt ein bestehendes
Argument plus erklärender Kommentar: `observations=rows` wird zu
`observations=history` bei `resolve_identity_map`.

Der komplette aktuelle Replaypfad und der unveränderte owning
Identitätsresolver wurden nochmals im Zusammenhang gelesen:

- `_selected_native_rows` validiert vorher jeden übergebenen nativen B1-Beleg
  samt tatsächlicher/effectiver Zeit und prospektiver Herkunft; unbekannte,
  manipulierte oder nach dem Stichtag importierte Belege passieren diese
  Grenze nicht. Gleichzeitige unterschiedliche jüngste Revisionen bleiben
  unauflösbar.
- Das mathematische Recipe muss weiterhin exakt die jüngsten ausgewählten
  Receipt-Digests angeben, nicht den gesamten Revisionspool.
- Nur die Identitätsauflösung erhält den vollständig validierten Pool.
  Jeder verlangte Proofref wird aufgelöst und hinsichtlich Event und nativer
  Teilnehmer geprüft. Der vollständige Maphash bleibt gebunden; zusätzliche
  nicht angeforderte Map-Einträge werden nicht als geprüft behauptet.
- Aktuelles Target, Termin, Status, Wettbewerb und Native-Provenienz sowie
  tatsächliche Basismathematik verwenden unverändert ausschließlich `rows`.
  Eine frühere Aufstellung/Spielerminute wird durch den älteren Identitätsbeleg
  nicht erneut zum aktuellen Recheninput.

Die Korrektur ist damit die zuvor vom Root bestätigte schmale Lösung, kein
Schemaumbau, kein freies Alterslimit und keine Lockerung einer Quellenprüfung.

## Tatsächlich wiederholte Tests

Alle Aufrufe mit
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`
und `-B -m pytest -q -p no:cacheprovider`; jeder Basetemp war neu.

| Eigener Lauf | Inhalt | Ergebnis |
| --- | --- | --- |
| `d1-independent-rereview-original-01` | 16 neue permanente Fälle + beide unveränderten ursprünglichen Reviewerdateien mit 25 Fällen | **41 bestanden**, 32.96 s |
| `d1-independent-rereview-new-01` | zusätzliche 15 unabhängige Nachreviewfälle | **15 bestanden**, 10.74 s |
| `d1-independent-rereview-combined-01` | alle obigen Fälle plus bestehende `test_context_replay.py` und `test_context_training_identity.py` | **80 bestanden**, 88.48 s |

Die ursprünglich zwei roten legitimen Targetrefreshfälle sind dabei unverändert
grün; sämtliche 23 weiteren ursprünglichen Quellen-/Numerikfälle bleiben grün.
Kein Skip und keine Änderung an den eigenen ursprünglichen Repros.

Die vollständige Suite dieses Korrekturstands wurde im engen Nachreview nicht
nochmals unabhängig ausgeführt. Der gelesene Owner-Audit dokumentiert sie auf
diesem Stand mit **3.479 bestanden, 15 erwarteten Windows-Skips und 97
Untertests**, 178.86 s. Das ist Owner-Evidenz, nicht ein zusätzlicher eigener
Fullsuite-Lauf. Der vorausgehende unabhängige Review hatte die unveränderte
Basis bereits vollständig mit 3.463/15/97 geprüft. Die endgültige integrierte
Regression bleibt Aufgabe des Controllers.

## Neue unabhängige Gegenproben

`test_d1_refresh_rereview.py` benutzt echte isolierte B1-Persistenz mit
ausdrücklich synthetischen Sportdaten und die öffentliche Replayfunktion.

1. Alle sechs Reihenfolgen eines dreifachen Target-Revisionpools. Der erste
   Identitätsref bleibt gültig, die mittlere und neueste XI-Position sind
   unterschiedlich. Ein Spy am tatsächlichen Originalmodell belegt genau
   einen Aufruf mit ausschließlich dem neuesten Target sowie 26 eindeutigen
   historischen Spielen. Parameter/Märkte bleiben mit der unveränderten
   ursprünglichen Rechnung vereinbar, und Recipe/Map/Inputbytes bleiben
   entsprechend ihrer getrennten Rollen gebunden und unverändert.
2. Tatsächlicher neuester Empfang bei Cutoff −1/0/+1 µs. Die beiden zulässigen
   Fälle erreichen den Identitätsresolver mit dem vollständigen Pool. Der
   zukünftige Beleg wird vorher abgelehnt; der Resolver wird nicht aufgerufen.
3. Eine wirklich in der neuesten Quelle aktualisierte Terminrevision darf bei
   gleichen nativen Teilnehmern den früheren reinen Identitätsbeleg behalten;
   der aktuelle Eventhash stammt aus dem neuen Termin. Das ist nicht die
   Erlaubnis, einen alten Termin als aktuell weiterzureichen.
4. Ein ausdrücklich synthetischer, 400 Tage älter empfangener Beleg prüft die
   Abwesenheit eines frei erfundenen Identitätsfrischelimits. Nur seine native
   Identität wird aufgelöst; der aktuelle Recheninput stammt aus dem jüngsten
   Receipt. Dies behauptet keine reale historische Quellenverfügbarkeit.
5. Mehrere ausdrücklich verlangte gültige Proofrefs werden sämtlich geprüft.
   Ein gültiger erster Ref rettet weder einen fehlenden zweiten noch einen
   zweiten Beleg eines fremden Events. Ein doppelt übergebener physischer
   älterer Receipt wird ebenfalls nach dem bestehenden Resolververtrag
   zurückgewiesen.

Diese Kontrollen ergänzen die 16 gelesenen und selbst ausgeführten permanenten
Tests, darunter veränderte aktuelle Teilnehmer, falsche Termine, alte oder
vollständige Revisionspools als Rechenrecipe sowie die vollständige aktuelle
Caseassembly mit unverändertem globalem Identitätsmaphash.

## Eingefrorene SHA-256-Werte

```text
fb7e0d581f45144c1f1b0456f828e58a7cb16ac124c1ec9683dc4f2b43fae32d  context_models/replay.py
cc3084075b601c211c632d50eab28b4b1a0f5e9134aa83cb1caae09de7f636b4  tests/test_context_replay_identity_refresh.py
5f865d5249c9333915f4bf3dc6927d202ce2338de174a5bf77a9c96d3c5c5caa  docs/audits/2026-09-09-d1-training-mechanics.md
01f5e6535015e70afaa0f9459a12e877ac23c9b4ba9be9efb48c53cb5e08d787  .pytest_tmp/d1-independent-20260909/review-d1.md
5c26c3bf49d2b4b4ab3b109ea73b8d5029a883d899deba0d2367f71dc7123a0c  .pytest_tmp/d1-independent-20260909/test_d1_independent.py
4a52a1f59408818c06d3645fffc83c64c6ddae0c404d5d0faa34eaa76a219aea  .pytest_tmp/d1-independent-20260909/test_d1_math_independent.py
58ab37e3038f5838e281ce352fe82043464184b89c58679a55219968ff193e49  .pytest_tmp/d1-independent-20260909/test_d1_refresh_rereview.py
```

Zusätzlich wurden alle **19 verschiedenen** im Owner-Audit aufgeführten
Source-/Test-/Originalreview-Dateien gegen ihre jeweils aktuellste deklarierte
SHA-Version geprüft, einschließlich der unveränderten früheren D1-Verträge,
Rechenmodule und Fixtures. Kein Hashunterschied außerhalb des freigegebenen
Deltas, kein schmutziger Worktree, `git diff --check` ohne Befund.

## Freigabeumfang

Die gezielte Korrektur ist für die weitere technische Integration akzeptiert.
Sie schließt den ursprünglichen D1-P2. Diese Disposition bestätigt weder einen
bislang fehlenden nativen Tennis-/State-Key- oder Teilnahmequellenresolver noch
reale ausreichende Trainingsdaten, D2-Empirie, numerische Live-Aktivierung oder
VPS-Deployment. Die entsprechenden offenen Grenzen des ursprünglichen D1-
Berichts gelten unverändert.
