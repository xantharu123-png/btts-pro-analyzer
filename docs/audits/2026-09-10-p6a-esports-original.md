# P6a: einmalige E-Sport-Originalaufnahme im echten Worker

## Abgrenzung und Basis

Genehmigtes enges P6a-Paket auf
`6d03ca00c487295a9a336e5917c314762e8ec637`, eigene neue Arbeitskopie
`.worktrees/kontext-p6a-esports-original-20260910`, Branch
`codex/kontext-p6a-esports-original-20260910`.

Umgesetzt: immutable preisfreier same-call Originaltransport und Verwendung
seiner tatsächlichen Elo-Werte im bestehenden Logger. Keine Providerabfrage,
native B1-/C4-Auflösung, gemeinsame Consumer-/D4-Verdrahtung, empirische
Freigabe, Default-Modelländerung, Cricket-/15K-/Abrechnungsänderung,
Produktionsdatenbank, VPS-Aktion, Push oder Vollsuite.

Der genehmigte Vorbericht und seine 13 Originalproben bleiben unverändert im
Root-QA-Pfad `.pytest_tmp/p6a-esports-original-preflight-20260909`:

- `PREFLIGHT.md`: `5634964adcc6472d76439d04fc0855329c2faa30b7713dd9729177b61c20092b`
- `test_same_call_preflight.py`: `c0ccceda30499dd48a9283514a60c2ab7397934ea362c8ec1dd531d4cb69d7eb`
- `red-01.xml`: `a07fd5b2fbf3360090b6a4e638ddf644e56604becf0830e8e8c30e4d86fca9f0`

## Tatsächliche Änderung

`esports_match_winner_candidate(..., capture_original=False)` erhält sein
bisheriges Default-Ergebnis. Der neue Parameter ist ein strikter Bool.
Explizites Capture benötigt eine aware `datetime`; gemeinsame Verwendung
mit dem alten `base_request` scheitert typisiert **vor** jeder Rechnung.

Mit `True` lautet die Rückgabe `{candidate, original}`. Kein berechneter
Kandidat bedeutet `original=None`. Ein tatsächlich berechneter Wert wird
nicht durch fehlende Transport-/Quellenabdeckung ersetzt.

`EsportsOriginal` hält ausschließlich eingefrorene kanonische JSON-Bytes.
`to_dict()` liefert eine abgelöste Kopie, `content_hash` bindet den gesamten
Transport. Die geschlossene Version `esports-live-original-v1` enthält:

- kanonische tatsächliche Decision, unveränderte Recipe-/Modellversion und
  die unveränderten Legacy-Konstanten;
- erlaubnisbasierte preisfreie Rawinputprojektion einschließlich nicht
  ausgewählter Historypositionen, originalen Uhren und primitiven Typen;
- während genau derselben Auswahl erfasste Raw-Indizes, Fenster und
  tatsächlich konsumierte geparste Werte;
- ungerundete Elo-, post-IID-, konservative und Prozent-Zwischenwerte aus
  **demselben** Kandidatenaufruf, ohne zweiten Elo-/Window-/Kandidatenlauf;
- zwingend `source_evidence='unresolved'` sowie explizite Pfade zu nicht
  transportierbaren ursprünglichen Eingaben.

Fehlende Felder, null, Integer, Float und Bool werden nicht gleichgesetzt.
Nicht-JSON-Werte werden nicht als `repr`, Klassenname, erfundener Nullwert
oder beliebiger Provider-/Preisbaum gespeichert. Ein geschlossener
Unverfügbarkeitsmarker erhält die tatsächliche Baseline unverändert;
Offline-Replay solcher unvollständigen Originale ist ausdrücklich nicht
verfügbar. Diese Marker sind kein exakter Ersatz für die verlorenen Werte.

Der neue interne Selector behält beim ursprünglichen stabilen Sortieren die
Raw-Indizes. Die öffentliche Historyfunktion behält ihre alte Rückgabe.
Das vermeidet die fehlerhafte nachträgliche Gleichheitssuche: zwei gleiche
Objekte und selbst zweimal dasselbe Objekt an verschiedenen Raw-Positionen
behalten ihre tatsächlichen Indizes. Die ursprüngliche Elo-Deduplizierung,
rohe Begin-String-Sortierung und sämtliche Cutoff-Regeln bleiben erhalten.

Der tatsächliche `EsportsShadowLog.log_predictions` verwendet diesen Capture
einmal und liest daraus `elo1/elo2`. Er berechnet keine zweite History und
keine zweite Elo. SQL-Spalten, gerundete Prozent-/Preiswerte, IDs,
Batch-Uhr, `INSERT OR IGNORE`, erste Beobachtung und Settlement bleiben alt.

## Was die beiden Validatoren beweisen

`validate_esports_original` prüft geschlossen Form, Primitive-Typen,
Inputhash, Markerbestand, Raw-Positionsbindungen, Auswahl-/Prozenttransport
und feste Recipeidentität. Er berechnet weder Elo noch History noch neue
Serienchancen und qualifiziert weder Quellen noch empirische Wirkung.

`replay_esports_original` ist ein **expliziter Offline-Aufruf**. Er baut nur
aus vollständigen transportierten Inputs den Originalaufruf nach und
vergleicht dessen vollständige Werte. Ein kohärent neu gesetzter Elo-Wert
kann die bloße Formprüfung bestehen, scheitert aber am frischen Replay.
Capture und Logger rufen diesen Replay nicht auf. Der alte qualifizierte
C4-`base_request` behält seine bisherigen zusätzlichen Prüf-Replays.

Die zwei Modelliterationen *innerhalb* eines Elo-Aufrufs bleiben bestehen.
Eine Berechnung bedeutet nicht eine statt bisher zwei historischer
Iteration. Konservativ bleiben es die alten heuristischen 150 Elo-Punkte
plus 5 Prozentpunkte; das sind keine neu gemessenen Verletzungs-/Roster-
Effekte und keine nachgewiesene individuelle Untergrenze.

## Echte Originalvergleiche und Ersatz des alten Alias-Tests

Die neuen Tests laden mit `git show` die tatsächlichen Pythonmodule des
gepinnten Elterncommits und führen sie getrennt aus. Sie vergleichen:

- Default und Capture gegen die vollständigen Parent-Candidates;
- `float.hex()` der Werte für prematch/live und BO1/3/5/**BO7**;
- echte alte/neue SQLite-Schemata und komplette Zeilen nach erster
  Beobachtung, ignoriertem Zweitscan und idempotenter Abrechnung;
- AST des unveränderten gesamten Elo-Moduls, der Serien-/Map-Rechnung,
  `_candidate`, allgemeinen `build_candidate` und des eigentlichen
  mathematischen Kandidatenblocks;
- AST von Loggerinitialisierung, Connection, Settlement, Summary,
  Release-Status und echtem Scan-Runner.

Der frühere
`test_logged_elo_uses_the_same_causal_twenty_rows_as_the_candidate` prüfte
nur den Shadow-lokalen Alias. Er verlangte damit den jetzt entfernten
Zusatzaufruf, nicht eine Gesamtberechnung. Er ist im unveränderten Parent-
Gitblob `987d9c27598d613c4d5fda9b1716bd5d05fef2a6` weiterhin vorhanden.
Die originale unabhängige Vorprobe zeigt unverändert dessen 1 Aliasaufruf
bei 2 echten Elo-Aufrufen.

Der eng genehmigte Ersatz testet das **originale Elo-Codeobjekt über alle
Aliase**, exakt eine Berechnung, beide exakten 20er-Listen, tatsächliche
Raw-Indizes und ungerundete Elo-Bits. Kein Rechenergebnis wird gemockt.

## RED/GREEN und Regressionsumfang

Alle XML-/Originalproben sind erhalten, kein Überschreiben oder xfail:

| Stufe | Ergebnis |
| --- | --- |
| Erste neue API-Tests vor Implementierung | 40 RED, 1 grün, 2 Basetemp-Harnessfehler |
| Nach Anlegen des eigenen QA-Elternverzeichnisses, weiterhin vor Sourceänderung | **41 RED / 2 grün**, 2.17 s |
| Erste Implementierung | **43 grün**, 2.75 s |
| Zusätzliche JSON-/Offline-Kanten: erster Lauf | Collectionfehler nur durch pytest-ID für 5001-stellige Testzahl |
| Feste Test-IDs, vor Typkorrektur | **5 echte RED / 51 grün**, 3.10 s |
| Typkorrektur plus gesamte Shadowtests | **71 grün**, 3.22 s |
| Zwei unveränderte funktionale `required_once`-Vorproben gegen neuen Stand | **2 grün**, 1.58 s |
| Gebundener E-Sport-/C4-/Legacy-Consumerfokus | **382 grün / 26 Untertests**, 103.72 s, keine Skips |

Die beiden unverändert herangezogenen Originalfälle sind
`test_required_once_actual_log_predictions_has_no_second_elo_calculation`
und `test_required_once_real_scan_runner_reuses_candidate_elo`. Ihre reale
Runnerprobe benutzt einen lokalen synthetischen Scanner und echtes SQLite;
keinen echten Provider. Der alte Sourcepin-/Ist-two-Zeuge wird **nicht** zu
einem heutigen Grünnachweis umetikettiert.

Fokus: alle zwölf Dateien aus `rg --files tests -g '*esport*'
-g '*multi_sport*' -g '*signal_source*' -g '*riskobet_cand*'`.
Enthält neue Originalaufnahme, alle vorhandenen C4-Revisions-/Scope-/
Cancellation-/B3-/D3-Kontrollen, alte Kandidaten-/Shadow-/Readerfälle und
unveränderte Cricket-Goldens. Keine vollständige Projektregression,
Provider-/Daten-/Empirik-/UI-/VPS-Freigabe wird daraus abgeleitet.

Jeder Aufruf verwendete das vorhandene Quality-Python mit `-B -m pytest
-p no:cacheprovider`, eigenem neuen `--basetemp` und eigenem XML. Die beiden
ursprünglichen Zeugen wurden direkt aus ihrem unveränderten Root-QA-Pfad
mit `--rootdir=.` und `-o 'pythonpath=. tests'` ausgeführt.

## Finale fünf Source-/Test-Hashes

| Datei | SHA256 |
| --- | --- |
| context_models/esports_live.py | 6fa58ed4fc31ff3a0ea85403a997468f8cdec888dc89654f0d3f8673d624ac93 |
| multi_sport_recommendations.py | 7430075ff384a13af34fdfa44a796daae41f40016aecf1517ed21cb2837239b1 |
| esports_shadow.py | f911bb17cc0bff0970d113e04521a45295083d1f487e7ccc20bdfa1be7279bf9 |
| tests/test_esports_live_original.py | 2258403afebc07e86f023cb3e41b6fcb4fae2a9f3734d20dceff32f148c900aa |
| tests/test_esports_shadow.py | cb11305dc30f8ba462c33ab2f616816e2093a123bcef98bb7bfc1f2e0ae6b4ec |

Wichtige XML-Hashes, relativ zum eigenen `.pytest_tmp`:

- `p6a-red-02.xml`: `d5804a6483949cac088790b0653c8a5e19f508c04bb649dc076e49b5b8ed4b37`
- `p6a-boundary-red-02.xml`: `5ced7f6c8cddfda4756e73bc389122956f80fd160f28a1b7cdf70b91082398f9`
- `p6a-green-02.xml`: `2093fffe97848f90683978db8df42d4b82a5e655b172f55c11f0f6ab89b6322a`
- `p6a-original-green-01.xml`: `b92dbf2f3e3734aa6d00293cd3e74ccd31bd6ce7a35b33ab7b97ca7433f032d5`
- `p6a-focused-01.xml`: `7b7d6b36ccbdfc2375923e0fdf13db8419ec49500c65e84317be7b97b872f78d`

## Noch offene Anschlüsse und Bytegrenze

Kein nativer Event, Season-/Title-/Competition-/Roster-/Patchbeleg wird aus
den alten reduzierten Scannerinputs erfunden. Native PandaScore-Ganzstatus-
Capture, echte B1-Auflösung, Quellen-/Featurebezug, gemeinsamer Consumer,
D1/D2 und D4 bleiben separate Aufgaben. Eine Callback-/Flagbehauptung kann
den neuen Originaltransport nicht in eine native Quellenfreigabe verwandeln.

C4 bindet bereits den gesamten rohen `multi_sport_recommendations.py`-Hash.
Dieser ändert sich durch die additive API trotz AST-/Float-Parität der
Mathematik. Alte gespeicherte C4-Referenzen dürfen daher nicht still mit
neuen Codehashes umgeschrieben oder als durch diesen Test wiederhergestellt
behauptet werden; tatsächliche Restore-Kompatibilität ist separat zu prüfen.

Die neue Arbeitskopie wurde mit `core.autocrlf=false` aus den tatsächlichen
Gitblobs erstellt. Manche Rohbytes unterscheiden sich deshalb bereits beim
Checkout von den alten CRLF-Dateien im Root-Arbeitsverzeichnis. Es wurde
keine Legacydatei normalisiert. `esports_elo.py` blieb unveränderter Blob
`ca390bc51976a5ce598c9a2a952568cd25439ca2`, lokaler SHA256
`bd431e06926a319a68d5803749771595bbf72bb8561d39da2b8ee841d2af7140`.
Der geschützte Helper blieb exakt
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Disposition: enges P6a-Mechanikpaket bereit für unabhängiges Review. Nicht
gemergt, gepusht oder deployed; keine Behauptung vollständiger P6-Abnahme.
