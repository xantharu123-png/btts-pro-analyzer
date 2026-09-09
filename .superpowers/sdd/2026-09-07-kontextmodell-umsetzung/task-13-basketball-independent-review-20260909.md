# Unabhängiger C2-Review — eingefrorener Basketball-Mechanikstand

Datum: 9. September 2026. Disposition: **Änderungen erforderlich**.

Prüfobjekt: `8cffd12da3c4db530e76fcd94aea3eb58e1c533a`, Basis
`0d000f6d8d85a4ada11521398ca1e4b82c88fd2d`, Worktree
`C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-c2-basketball-20260909`.
Der Worktree war vor und nach der Prüfung sauber; alle geprüften Bytes blieben
unverändert. Es wurden ausschließlich die drei nachstehend genannten eigenen
Testdateien und dieser Bericht unter `.pytest_tmp/c2-independent-20260909`
erstellt. Keine Source-, Git-, Provider-, Server-, Geld- oder Aktivierungsaktion.

## Ergebnis

Ein P1 und zwei P2 sind konkret reproduziert. Die 52 eigenen Gegenproben
ergeben **8 fehlgeschlagen / 44 bestanden**; die acht Fehler gehören genau zu
diesen drei Befunden. Die vorhandene vollständige Suite ergibt separat
**3.739 bestanden, 15 übersprungen, 97 Untertests bestanden**. Die eigene
`.pytest_tmp`-Suite wird von `pytest tests` nicht mitgesammelt; die grüne volle
Suite widerlegt deshalb keinen der neu gefundenen Fehler.

Das Paket enthält substanzielle, tatsächlich gerechnete CPU-Mechanik. Die
unabhängigen numerischen Vergleiche bestätigen insbesondere die ursprüngliche
Ridge-Rechnung samt negativen Einflüssen und die gelernte Margin-Anpassung.
Es ist trotzdem weder in diesem Stand technisch zur Integration freigegeben
noch ein fertiger realer Basketball-Ausfallfeed oder ein empirisch zugelassenes
Kontextmodell. Diese Grenzen werden im Owner-Audit zutreffend benannt.

## F1 — P1: Unvollständige Teilnehmerkorrektur behauptet falsche exakte Erholung

Fundstellen: `context_models/team_sports.py:355–363`, `:455–483`, insbesondere
die ausschließliche Prüfung `state != available` in Zeile 361 und der
Teilnehmerfilter in Zeile 463.

Ein vollständiger neuerer Spielbeleg ergibt zunächst 16 Stunden beobachtete
exakte Ruhe. Eine später empfangene, unvollständige Revision desselben nativen
Events ersetzt einen Teilnehmer; beide Spielerprojektionen sind leer, und
Anfang/Ende sind ausdrücklich unbekannt. Der B1-Faktor darf für einzelne
berichtete Tatsachen `available` sein, obwohl die Sammlung unvollständig ist.
C2 verwendet diesen Status jedoch als ausreichende Bedingung, keine
Ungewissheit für die früher betroffenen Teilnehmer zu behalten. Der alte
Teilnehmer verschwindet aus dem neuen `teams`-Filter. Ein anderes, älteres
Spiel wird nun zur vermeintlich jüngsten Leistung.

Die vier direkten Repros prüfen beide Seiten getrennt und erhalten:

- `observed_recovery_exact_hours_* = 36.0` statt unbekannt;
- `observed_inclusive_minutes_complete_3d_* = 1` trotz der unaufgelösten
  neueren Spielzuordnung.

Ein fünfter Repro verwendet echte öffentliche B1-Aufrufe mit einer neuen
isolierten SQLite-Datei: Normalisierung → `append_observation` →
`observations_as_of` → Featureberechnung → tatsächlich trainierter B2-Offset →
`team_sport_context_result`. Die falsche Erholungsgrundlage passiert den
Consumer und ergibt `role=experimental` mit Vergleichsparametern statt
`not_applied` ohne numerischen Vergleich. Es wurde keine Freigabe erfunden;
die verwendete Nutzerbasis bleibt ohne Approval unverändert. Der Fehler
betrifft aber bereits die als gemessen deklarierte experimentelle Grundlage.

Repros:

- `test_c2_independent.py::test_incomplete_new_native_projection_cannot_erase_old_participant`
  — `[rest-home]`, `[rest-away]`, `[window-home]`, `[window-away]`.
- `test_c2_receipts_and_effects.py::test_false_recovery_can_reach_real_comparison_after_sqlite_round_trip`.

Minimale Korrekturgrenze: Die unvollständige gemeinsame Eventrevision muss
Ungewissheit für alle früheren und neu betroffenen Teilnehmer bewahren.
Keine alte Teilnehmerprojektion reaktivieren, kein älteres Spiel daraus zum
belegten letzten Spiel oder das Fenster zu vollständig erklären. Die
ursprüngliche Basisprognose bleibt erhalten. Root hat F1 bestätigt.

## F2 — P2: Native Case-Kollision wird erst nach verlustbehafteter Auswahl geprüft

Fundstellen: `context_models/team_sports.py:277–290`.

Die unveränderte Legacy-Pipeline faltet IDs in Kleinbuchstaben. Das ist kein
Beweis, dass zwei native EuroLeague-IDs identisch sind. Im Gegenbeispiel kommen
`E2026_1` und `e2026_1` mit unterschiedlichen kausalen Empfangszeiten im
Eingabepool vor. Legacy behandelt die spätere als Revision derselben ID.
Der neue Export prüft `event_ids` jedoch erst für Kandidaten mit genau der
bereits ausgewählten letzten Empfangszeit; die frühere native Identität ist
dann nicht mehr im zu prüfenden Kandidatensatz.

Das Ergebnis bleibt fälschlich `basketball-margin-ridge-v1` mit verifizierten
nativen Referenzjoins. Die Basismärkte entsprechen weiterhin exakt der
unveränderten Legacy-Rechnung; gerade deren Erhalt erlaubt keine zusätzliche
Behauptung eines eindeutigen nativen Kontextrückbezugs.

Repro: `test_c2_independent.py::test_case_distinct_native_id_collisions_are_not_verified_legacy_aliases[event]`.
Die getrennte Teamkollisionskontrolle `[team]` besteht bereits.

Minimale Korrekturgrenze: Nachweis der nativen ID-Eindeutigkeit aus dem
vollständigen validierten kausalen Kollisionspool vor der verlustbehafteten
Legacy-Auswahl. Bei Uneindeutigkeit Originalbytes erhalten und Kontextprovenienz
als nicht verfügbar behandeln. Keine Änderung der Default-Legacy-Formel oder
des Cricket-Verhaltens. Root hat F2 und diese Grenze bestätigt.

## F3 — P2: Eindeutig irrelevanter alter Konflikt blockiert alle aktuellen Fenster

Fundstellen: `context_models/team_sports.py:347–354`, `:463–479`, `:481–487`.

Zwei gleichzeitig empfangene, widersprüchliche historische Lastrevisionen
haben beide eine tatsächlich deklarierte terminale Receiptobergrenze zehn
Tage vor dem Stichtag; ihr genaues Matchende bleibt unbekannt. Ein davon
unabhängiges, jüngeres Spiel hat belegtes Ende zwölf Stunden vor dem Stichtag.
Die alte Unsicherheit kann weder im aktuellen Sieben-Tage-Fenster liegen noch
das jüngste bewiesene Ende überholen. C2 reduziert sie dennoch auf eine globale
Team-Konfliktmenge ohne Zeitobergrenzen und setzt aktuelle Last/Erholung auf
`None`.

Zwei Repros in
`test_c2_receipts_and_effects.py::test_provably_old_conflicting_terminal_event_does_not_poison_current_windows`
erwarten den unabhängig belegten beobachteten Wert `18.0` Stunden bzw. ein
vollständiges beobachtetes Sieben-Tage-Fenster, erhalten aber jeweils `None`.

Root hat diesen Befund ausdrücklich als eng begrenzte Over-Rejection bestätigt:
Nur wenn **alle** kausalen terminalen Obergrenzen der konflikthaften Revisionen
sicher vor dem betrachteten Fenster beziehungsweise dem bewiesenen letzten
Ende liegen, darf der Konflikt dort ausgeschlossen werden. Konflikt- und
Ausschlussbelege bleiben gebunden. Gleichheit bleibt bei dieser
Konfliktentscheidung unsicher. Keine tatsächliche Endzeit oder Nullminuten
erfinden und keine Übertragung auf aktuelle Rotation, Starter, Spielidentität
oder die für die Basisreferenz benötigten historischen Rotationen.

Zehn eigene permanente-negative Kontrollfälle im separaten eingefrorenen
`test_c2_conflict_negative_controls.py` bestehen im Originalstand:

- Alle 1/3/7-Tage-Fenster bei Obergrenze genau auf dem Beginn oder 1 µs danach
  bleiben unbekannt, jeweils für beide Teilnehmer geprüft.
- Obergrenze genau auf dem bewiesenen jüngsten Ende oder 1 µs danach behauptet
  keine exakte Ruhe.
- Eine alte, aber tatsächlich benötigte Referenzrotation bleibt bei Konflikt
  unvollständig; zeitliche Irrelevanz für ein Lastfenster heilt sie nicht.
- Ein aktueller Rotationskonflikt wird nicht aus alten Mitgliedern geheilt.

## Unabhängig bestätigte Mechanik und Grenzen

- Sechs unterschiedliche Ziel-/Neutralitätsfälle aus drei deterministischen
  Datenvarianten: unabhängige augmentierte SVD/Lstsq-Ridge-Lösung statt Aufruf
  der Implementierungsfunktion. Eigene Designmatrix, Strafmatrix, Hat-Matrix,
  negative Zieleinflüsse, Koeffizienten, effektive Freiheitsgrade und
  Residualskala stimmen überein. Keine Normierung negativer Gewichte zu einem
  konvexen Mittel. Die engen numerischen Toleranzen gehören nur zum Vergleich
  zweier verschiedener QA-Löser, nicht zu einem gelockerten Produktvertrag.
- Fünf echte B2-Identity-Fits mit zwei Koordinaten und Alpha
  `0, .01, .1, 1, 10`: Vergleich mit unabhängig gelöster geschlossener Ridge-
  Normalgleichung und Gradiententest. C2 liefert denselben additiven Mittelwert
  und dieselbe Originalskala; beide Siegerseiten stammen aus derselben
  Normalverteilung. Konsistent vertauschte Feature-/Scale-/Koeffizientenachsen
  erhalten die Zahl, ändern aber korrekt die Modellidentität.
- Neun unabhängige Grenzfälle des tatsächlichen Endes bei 1/3/7 Tagen ±1 µs
  bestätigen halboffene Fenster. Drei OT-Fälle mit 0/1/3 echten Perioden
  verändern nur die separat gemessenen inklusiven Minuten, nicht die
  Regulation-Rotationsreferenz.
- Drei echte SQLite-Receipt-Rückspiele bei Cutoff −1/0/+1 µs bestätigen die
  kausale Auswahl. Sechs unabhängige Mutationen an Inhalt/Receipt/Revision/
  Zahlen/Quelle/Team werden vom öffentlichen Featureproducer zurückgewiesen.
- Der eingefrorene 515-Zeilen-Legacy-Quelltext wurde zusätzlich byteweise gegen
  `git show 0d000f6:sports_prematch.py` verifiziert. Er ist exakt das vollständig
  gelesene Präfix des aktuellen Moduls, nicht eine neu geschriebene Nachbildung.
  Neun reale Old/New-Cricket-Läufe auf derselben CPU sind kanonisch bytegleich:
  Standard, ODI, Preise, Seitenwechsel, Zukunftskorrektur, leere Historie,
  ununterstütztes Testformat, später Import und simultaner Ergebniskonflikt.
  Eingaben bleiben unverändert.
- Die vorhandenen umfangreichen Gegenproben für Originalbytes/Nulleffekte,
  geschlossene B1-Margin-Typen, Vergleichsmutationen, Familien-/Formatgrenzen,
  doppelte Anpassung und die 16 additive Zeilen umfassende B3-Bindung wurden
  unabhängig ausgeführt und im vollständigen Sourcezusammenhang gelesen.
  Die B3-Erweiterung bindet tatsächliches Original, Event, vollständigen
  FeatureVector und verifiziertes Effekttransportobjekt; sie erzeugt keine
  D2-Genehmigung.

## Laufprotokoll

Interpreter in allen Läufen:
`C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
Jeder Aufruf nutzte `-B -m pytest -q -p no:cacheprovider` mit einem neuen
`--basetemp=.pytest_tmp/<Name>`. Alle Läufe waren lokal/CPU-only; keine
pytest-Anwendungs- oder Quellenfehler mussten im Reviewer-Harness korrigiert
werden.

| Lauf / frisches basetemp | Auswahl | Ergebnis |
| --- | --- | --- |
| `c2-independent-focus-01` | Basketball, Prematch, Contracts, Snapshots, Offset | 661 bestanden, 23.07 s |
| `c2-independent-attacks-01` | erste eigene Datei | 5 fehlgeschlagen / 19 bestanden, 4.66 s |
| `c2-independent-effects-01` | zweite eigene Datei | 3 fehlgeschlagen / 15 bestanden, 7.85 s |
| `c2-independent-conflicts-01` | enge F3-Negativkontrollen | 10 bestanden, 2.53 s |
| `c2-independent-combined-01` | alle drei unveränderten Reviewerdateien | 8 fehlgeschlagen / 44 bestanden, 12.55 s |
| `c2-independent-full-01` | vollständiges `tests` | 3739 bestanden / 15 Skips / 97 Untertests, 98.66 s |

Die 15 Skips entsprechen dem eingefrorenen Owner-Vergleichsstand. Dieser
Windows-Lauf behauptet keine zusätzliche Linux-/Provider-/Browserabnahme.

## Vollständige geprüfte SHA-256-Bindung

Alle acht Deltafiles wurden vollständig gelesen (die Legacy-Datei zusätzlich
über exakt nachgewiesene vollständige Bytegleichheit mit dem gelesenen
Originalpräfix). Genehmigte Spezifikation, vollständiger Task13brief,
Controller-Rulings und vollständiger Owner-Audit wurden gelesen. Alle elf
folgenden Source-/Audit-/Nachbarhashes wurden vor und nach den Tests verglichen:

```text
763b105a712418c8963b6f620ecea75eb8b42fec54b3775f9587c6e235737b9d  context_models/contracts.py
410fddf37b42f61e1d1cf6044df1e0636a912701be8193c4666a2ea075870605  context_models/team_sports.py
6caa81aa7ac7f188cfef689b688cc0deb452515b8ba8f7fad2f8e5b2f27d6dac  context_snapshots.py
da6dd98b15a8cbb55f508b6c7980c22acc4cd2055ec0a3e06b76028822b6b12b  context_sources/basketball.py
b7903fd7796241f37b443a8b17da19074fb097f6122dea1b6a536d0135b54f15  docs/audits/2026-09-09-c2-basketball-mechanik.md
fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7  sports_prematch.py
b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677  tests/fixtures/context/basketball/sports_prematch_legacy_0d000f6.py
0e52913cd9b3e57a080a646b34a2d5f1ba20855fb307bb76ad038440ff3a43e4  tests/test_basketball_context.py
05371eff84e0d0f91824ca08a5134e4a0b241c6f6e2d30f037f4335eb6de3064  scanners/basketball_scanner.py
9f318672c0a18054d8fb9cae95ecbd6402a49ca0f17699eef8bb6a93beb1e264  scanners/completed_history.py
027939cc5f7c05648177bfc94605bdc5f0fabac10e215d346a6e9ba1b37ec7a7  context_models/offset.py
```

Zusätzlich gelesene Root-Rulingdatei:
`../kontextmodell-20260907/.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-13-controller-rulings-20260909.md`
SHA `b97ea32db6c5d25ac1196b6ac1cca5eb584e65b7863a93c9b2f16f8ac87d45bd`.

Unveränderliche eigene Repros, alle relativ zu diesem Berichtsordner:

```text
4d21d7b3930dd64f4f965e05e6e776bf6fe1382576a528afd800db807ef9563d  test_c2_independent.py
1d1f0e054e523a29816bf9c602f63e24982e5cf2a6970707d217097efe920b94  test_c2_receipts_and_effects.py
f2bf5075611553425b4d65ecfa52c9bc3592c7804f52ab1bf1b021ec62be27c3  test_c2_conflict_negative_controls.py
```

## Abschluss und offene Anschlussarbeit

Alle Findings und Originalrepros sind jetzt eingefroren. Owner-Korrektur und
anschließender unveränderter Gegentest sind erforderlich. Keine Änderung des
Wettpreises, kein Marktverbot und keine Lockerung empirischer Grenzen gehört
zur Fehlerbehebung.

Auch nach erfolgreichem Fix bleiben echte Basketball-Quellenanbindung,
historische verfügbare Rotation-/Ausfallreceipts, D1-Case-/Outcome-Integration,
D2-Abnahme und Worker-/Nutzeraktivierung eigenständige offene Arbeiten. Ein
geschlossener interner Transport und erfolgreiche synthetische Fits belegen
diese Punkte nicht. Cricket bleibt unverändert; der VPS wurde hier nicht
berührt.
