# P6a: E-Sport same-call Original und tatsächlicher Shadow-Worker

Read-only Vorprüfung, 2026-09-10. Keine Implementierung, kein Commit, kein
Volltest, kein Providerzugriff, keine echte Datenbank und kein Servereingriff.
Alle neu erzeugten Dateien liegen ausschließlich im eigenen ignored QA-Pfad.

## Gebundener Ausgangsstand und Auftrag

Worktree: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontextmodell-20260907`

HEAD: `6d03ca00c487295a9a336e5917c314762e8ec637`.

Die vorhandene Änderung an `scripts/stage_runtime_databases.py` und sämtliche
fremden ungetrackten Output-/Bootstrapdateien wurden weder gelesen für diese
Änderung noch verändert. Root führt seinen gesonderten Integrationstest aus;
diese Vorprüfung startet keine konkurrierende Vollsuite.

Vollständig gelesen: genehmigte Kontext-Spezifikation, vollständiger C-Plan,
Task-15-Brief und Controller-Rulings; ursprünglicher C4-Audit,
C4-Korrekturaudit, partielle Scopekorrektur, Cancellation-Retention und
D3-E-Sport-Transportaudit; historisches Source-Readiness-Dokument. Deren
Source-/Empirikgrenzen werden nicht durch diese rein lokale Probe aufgehoben.

## Ergebnis: reale doppelte Berechnung, nicht nur ein vermuteter Aufruf

`log_predictions()` berechnet derzeit einen Kandidaten und danach dieselben
zwei Historyfenster und dieselben Elo-Werte nochmals. Zwei unabhängige
Solltests sind am unveränderten Code tatsächlich RED:

1. Der echte `EsportsShadowLog.log_predictions()` schreibt eine neue Zeile,
   führt dabei aber **2** Aufrufe von `esports_elo.subgraph_ratings` aus.
2. Der echte `run_shadow_scan()` erreicht denselben Doppelaufruf; sein
   Scanner ist ausschließlich ein lokaler Test-Doppel ohne Netzwerk. Scan,
   Logging, tatsächliches SQLite und Settlement-Abfrage werden ausgeführt.

Gemessen wurde mit `sys.setprofile` auf dem originalen Python-Codeobjekt,
nicht durch Ersatz einer Wahrscheinlichkeit oder eines Rechenergebnisses.
Die Messung erfasst beide importierten Funktionsaliase. Der Profiler wird
immer zurückgesetzt. Nur die Worker-Uhr wird auf den expliziten synthetischen
Entscheidungszeitpunkt `2026-09-09T12:00:00+00:00` fixiert.

Ein Elo-Aufruf enthält weiterhin die vorgeschriebenen **zwei getragenen
historischen Iterationen**. Das Ziel ist ein solcher Aufruf, nicht das
Entfernen einer dieser beiden Modelliterationen.

| Tatsächlicher Pfad | Kandidaten | Elo-Aufrufe | History-Auswahl |
| --- | ---: | ---: | ---: |
| Direktes altes Kandidaten-API | 1 | 1 | 1 |
| Echter Logger | 1 | 2 | 2 |
| Echter Scan-Runner | 1 | 2 | 2 |
| Zu wenig History im Logger | 1 ohne Prognose | 0 | 1 |
| Alter `base_request`, keine nativen Receipts | 1 | 1 | 1 |
| Alter `base_request`, vollständige synthetische B1-Receipts | 1 | 4 | zusätzlich Referenzprüfung |

Die letzten vier Elo-Aufrufe stammen aus Originalrechnung, Export-Replay,
Referenzvalidator-Replay und Basisvalidator-Replay. Das sind getrennte
Prüfungen des alten qualifizierten C4-Exports; sie sind **nicht** der neue
same-call Capture und sollen nicht unbemerkt dessen schnellen Pfad werden.
Diese Vorprüfung verlangt nicht, die vorhandenen Offlineprüfungen zu löschen.

Der bestehende Test
`test_logged_elo_uses_the_same_causal_twenty_rows_as_the_candidate` bleibt
unverändert und grün: Er beobachtet nur den Shadow-lokalen Alias, dessen
Aufrufzahl tatsächlich 1 ist. Eine neue grüne Kontrolle beweist gleichzeitig
`shadow_alias.call_count == 1` und die echte Gesamtzahl 2. Der alte Test
beweist gleiche ausgewählte Zeilen, aber nicht eine einzige Gesamtberechnung.

## Rechenbytes und bisherige Datenverträge

Konkreter synthetischer Logger-Zeuge:

- Elo A: `1632.4488432405124`, Hex `0x1.981cb9d8ffc20p+10`.
- Elo B: `1391.9758911662868`, Hex `0x1.5bfe750038ea1p+10`.
- 40 tatsächlich beitragende Subgraph-Serien.
- Ungerundeter ausgewählter Prozentwert: `0x1.3fdedf1ea01a4p+6`.
  Der gespeicherte Prozentwert ist dagegen weiterhin `round(raw, 2)`.
- Konservativer direkter Serienwert: `0x1.4132281fed10fp-1`;
  nach der originalen Map-Inversion/Serienrechnung:
  `0x1.4132281fed10ep-1`. Selbst hier ist Ersetzen durch den direkten Wert
  nicht bytegleich.

Die konservativen Werte sind die **bestehende Heuristik** (150 Elo-Punkte
und weitere 5 Prozentpunkte), keine individuell gemessene Verletzungs- oder
Rosterwirkung und keine empirisch nachgewiesene Untergrenze. P6a darf diese
Bedeutung weder ändern noch als neue Kontextwirkung etikettieren.

Die Definition des Originals muss den tatsächlichen post-IID-Wert auf
Team-A-Seite erhalten, den ausgewählten Favoriten getrennt benennen und
ungekürzte Zwischenwerte separat transportieren. Kein `rounded / 100`, keine
Neuberechnung aus sichtbaren Karten oder alter Datenbank-Elo.

Unverändert zu erhalten:

- Elo-Basis 1500, Scale 400, K 40, BO1-Faktor .75, zwei getragene Iterationen;
  70 Schritte der Map-Inversion und originale Serien-/Scorearithmetik.
- Zwei neueste kausal abgeschlossene 20er-Fenster; stabile Reihenfolge bei
  gleichen Endzeiten. `begin < end < decision`; prematch zusätzlich
  `end < kickoff`. Keine neue Cutoff-Gleichheitsregel einführen.
- Deduplizierung erst im Elo-Subgraph: Side-A-Fenster vor Side-B-Fenster,
  erstes gültiges Match-ID-Vorkommen gewinnt; anschließend originale
  Sortierung nach **rohem Begin-String** und Match-ID. Keine hübschere
  Zeitzonen-/ID-/Case-Normalisierung unterschieben.
- `log_predictions`: tatsächliche positive Integer-IDs, 0:0-prematch,
  eine tatsächliche Batch-Uhr, `INSERT OR IGNORE`, bestehende Teamzuordnung,
  unveränderte SQL-Spalten und bereits gerundete Prozent-/Preiswerte.
- Zweiter Scan überschreibt keine erste Beobachtung. Settlement-ID,
  normale/abgesagte Ergebnisse, atomare Erstabrechnung, History und
  Modellgenerationen bleiben unverändert. Dafür gibt es echte SQLite-
  Wiederholungs- und Settlement-Kontrollen.
- Das alte API akzeptiert auch andere ungerade Formate, insbesondere BO7,
  während qualifiziertes C4 nur BO1/3/5 kennt. Capture darf ein solches
  Legacy-Ergebnis erhalten, aber nicht als C4-qualifiziert ausgeben.
- Der allgemeine `_candidate` bleibt unverändert: Er betrifft weitere
  Sportarten und die Rundungs-/Anzeigewerte. Kein Cricketpfad wird angerührt.

## Engste vorgeschlagene API (Entwurf, noch nicht implementiert)

1. Additives `capture_original: bool = False` am vorhandenen
   `esports_match_winner_candidate(match, *, now=None, base_request=None, ...)`.
   Default: exakt derselbe Candidate wie heute. Explizites Capture verlangt
   dieselbe bewusste aware Entscheidungszeit wie der Worker und liefert
   `{"candidate": candidate, "original": original_or_none}`. Ein geblockter
   Kandidat bleibt unverändert, ohne erfundene Rechenwerte. Gleichzeitiges
   `capture_original=True` und `base_request` ist ein früher typisierter
   Vertragsfehler, kein zufällig gewählter Replaymodus.

2. Enger interner History-Selector liefert beim **selben** Auswahlvorgang
   sowohl Zeilen als auch ihre ursprünglichen Raw-Indizes. Die bestehende
   öffentliche `esports_history_window` behält ihre alte Rückgabe. Kein
   nachträgliches zweites Window für den Logger. Kein `list.index(dict)`:
   Der adversariale Zeuge enthält zwei verschiedene gleiche Objekte an
   Indizes 1 und 3; Gleichheitssuche gibt für beide 1 zurück. Future-/invalid-
   Zeilen vor diesen Objekten dürfen den Index nicht verschieben.

3. Eigener schmaler `context_models/esports_live.py`-Baustein baut einen
   geschlossenen internen Originaltransport aus **bereits errechneten**
   Werten, nicht über einen weiteren Kandidatenaufruf, `_replay`, Elo-Fit,
   Provider, SQLite, latest Manifest oder Dateirekonstruktion.
   Vorgeschlagene Inhalte:

   - schema/kind/Recipeversion, kanonische tatsächliche Decision;
   - vollständige erlaubnisbasierte, preisfreie Originalinputprojektion;
   - Reihenlängen, rohe History-Indizes und original ausgewählte Zeilen;
   - verwendete Integer-IDs, Score/Best-of und Legacy-Konstanten;
   - exakte `elo1/elo2/subgraph_size`, direkte A-Serienchance,
     A-Mapchance, tatsächliche post-IID-A-Chance, Auswahlseite;
   - exakte konservative Zwischenwerte, `probability_percent`,
     `adjusted_probability`, tatsächlicher `haircut` vor `_candidate`;
   - Input-/Transporthash; ausdrücklicher Status `unresolved`, keine
     verifizierten nativen History- oder Roster-Referenzen.

   Inputprojektion: tatsächliche Event-ID-Auswahlfelder `game_id/match_id/id`,
   Teamnamen/IDs, Game-Label, Status, Start, beide Scores, `series_type`,
   von diesem Modell gelesene Stats-Felder; je Raw-Historyposition nur
   `match_id/begin_at/end_at/opponent_id/won/number_of_games`. Fehlen,
   null und tatsächliche Primitive-Typen bleiben unterscheidbar. Auch
   verworfene Raw-Positionen bleiben im Inputinventar belegbar. Keine
   unbeschränkten Unknown-Providerdicts und keine Quotes/Bookmaker/Preisfelder
   in diesem Rechenhash. Nicht transportierbare Legacywerte dürfen keine
   neue andere Prognose erzeugen; die Originalaufnahme bleibt dann explizit
   unvollständig/typisiert, die bisherige Baseline nicht neu interpretiert.

   Der reine Capturevalidator beweist Form/Hashes/individuelle Bindungen,
   nicht freie Behauptungen über Quellen oder eine frisch nachtrainierte
   Elo. Ein explizit gesonderter Offline-Replay darf das komplette Rezept
   nachrechnen und kohärent umgeschriebene Resultate zurückweisen. Er läuft
   **nicht** unbemerkt im Capture/Worker/Renderer. Exakte öffentliche Shape
   ist vor Implementation als schmaler Controller-Vertrag festzulegen.

4. Der **echte** Logger ruft Capture einmal mit seiner vorhandenen Batch-Uhr
   auf und schreibt `original.elo1/elo2` aus genau diesem Aufruf. Candidate-
   Felder und alle übrigen INSERT-Parameter bleiben alt. Er ruft weder
   History-Window noch Elo erneut auf. Keine neuen historischen Zeilen,
   Schema-/ID-Migration oder Modellversions-Umetikettierung. Erst eine
   separate Consumer-Aufgabe bindet diesen Originaltransport an gemeinsame
   B1/B3/A1-Snapshots; dieses Paket behauptet noch keine solche Nutzung.

Die breite Sperre eines Baselinesports wegen fehlender Quellen ist weder
erforderlich noch erlaubt. Bestehender rechenbarer Originalwert und nicht
qualifizierte Kontextwirkung sind getrennte Zustände.

## Noch fehlende, ausdrücklich getrennte Anschlüsse

`scanners/esports_scanner.py:168` lädt bestehende Endpunktantworten;
`_format_match:259` verwirft native Scopefelder und andere Status;
`_get_team_history:517` reduziert auf fertige Serien und sechs Felder.
Der resultierende Modelinput besitzt keine echte HTTP-Receiptzeit,
Title-/Competition-/Season-ID, vollständige aktuelle Statusrevision,
Appearance, Stand-in, Patch-/Veto- oder Map-Duration-Abdeckung.

- `game='CS2'` oder `source='PandaScore'` ist kein nativer C4-Scopebeweis.
- Der heutige modelldefault BO3 ist kein empfangenes Format. Eine geplante
  Zeit ist weder Veröffentlichungs- noch Receiptzeit.
- Zwei Raw-Positionen mit gleicher Match-ID können 20 Windowzeilen, aber
  nur 19 beitragende Serien ergeben; der Zeuge ergibt insgesamt 39 statt
  40 Subgraph-Serien. P6a dokumentiert die alte Rechnung, korrigiert nicht
  still ihr Rezept. Qualifizierte native Widersprüche sind später vom
  vollständigen kausalen Sourceinventar zu prüfen.
- Warm Scanner-Cache ist ein ursprünglicher Modelinput, kein rückwirkend
  neu erstellbarer B1-Beleg. Ganzstatus-/Teilnehmer-/Scopekorrekturen dürfen
  nicht nachträglich aus den schon gefilterten sechs Historyfeldern
  rekonstruiert werden.
- Die heute gespeicherten Shadowzeilen werden von
  `ev_signal_sources.py:516` für normale Auswahlen und
  `riskobet_candidates.py:1328` für RisikoBet gelesen. Letzterer leitet
  weitere Map-Szenarien aus gerundeten Serienwerten ab; daraus entsteht
  keine C4-Freigabe neuer Märkte. Beide lesen noch keinen gemeinsam
  belegten P6-Original-/Kontextsnapshot. Root muss den späteren owning
  Consumer einschließlich tatsächlichem Worker prüfen, nicht nur einen
  synthetischen Wrapper.

Native PandaScore-Statuscapture, B1-Auflösung, C4-Basis-/Featurebezug,
D1/D2-Wirkungsfreigabe, D4-Capability und gemeinsamer Consumer bleiben
separate offene Pakete. Kein eigener Providerfetch oder Sourcebudget nötig
für die hier vorgeschlagene P6a-Rechenaufnahme.

## Belege und Testdisposition

Eigene unveränderliche Datei: `test_same_call_preflight.py`, SHA256
`c0ccceda30499dd48a9283514a60c2ab7397934ea362c8ec1dd531d4cb69d7eb`.

Original RED: `red-01.xml`, SHA256
`a07fd5b2fbf3360090b6a4e638ddf644e56604becf0830e8e8c30e4d86fca9f0`:
**2 failed / 11 passed / 2.93 s**. Die beiden oben genannten Solltests sind
echte funktionale REDs. Sie werden weder xfailed noch nachträglich auf 2
umgedeutet. Der separate grüne Ist-Zeuge ist bewusst als Iststand benannt.

Kleiner bestehender Legacy-/C4-Fokus: `focus-01.xml`, SHA256
`363cd3c4feb08b259925656311039848c290226e26dc9508a343da3e79a39671`:
**30 passed / 14 deselected / 2.84 s**. Kein Skip. Enthält echte
First-observation-/Settlement-/Racing-Kontrollen, bestehende E-Sport-Modelle,
unveränderte Cricket-Goldens, originalgetreuen Native-Fallback und
Preisneutralität. Das ist keine Vollsuite und keine empirische Evaluation.

Befehle: vorhandenes Quality-Python mit `-B -m pytest -p no:cacheprovider
-o 'pythonpath=. tests'`; eigene neue Basetemps `run-01` und `focus-01`.
Fokusdateien: `test_esports_shadow.py`,
`test_multi_sport_recommendations.py`, der unveränderte
`test_frozen_full_legacy_and_cricket_parity`,
`test_no_native_receipts_preserves_original_candidate_and_available_base`
und `test_price_mutations_do_not_enter_original_native_base_or_features`,
mit `-k 'esports or subgraph or series'`.

## Unveränderte Source-/Altprobe-Hashes

| Datei | SHA256 |
| --- | --- |
| multi_sport_recommendations.py | 80c545cf82a577bd4d1540bbd2619a12171662781373161d6db4c80ba38615c5 |
| esports_elo.py | e02bfd45d1e2b63901461a2162592af7cc7353b70cd9683ec6be63c0b6658eff |
| esports_shadow.py | d2e5fd53b25332f0070d3d36f3221c40523a14d80838b1a4f7c8d8e1a1b22725 |
| context_models/esports.py | d2c95016828fde4b0c30f7849f239b647cdd12c1b97fa7a0fb7c8a287bf26e33 |
| scanners/esports_scanner.py | 88154b79be09dd11c09c45c8b09d45c6ffde277fe197911576dcffa14834fc8d |
| esports_shadow_automation.py | 9b647a17f5e288e0f8c8704ed7afcaecf4d8398f3e7cd1dae6ce76b66bfb3917 |
| ev_signal_sources.py | 26970cb596d38b0458fdb42b1d62c822c8d9bd2b080d2601ec23b3a8cd83e705 |
| riskobet_candidates.py | a28bbd628d6f410259b293f6675c87db698305c3a6dc09f0a9c80efca82ebb2c |
| wettfinder_automation.py | 360e4515f6b3a14e3ee523e3b6ac4988a8bd8ba12009dc291af1ce9670fc6367 |
| tests/test_esports_shadow.py | 581f3adf1c44cc477e352f2d60acb1289f68faa25cbdcca4c81199b8335f13cf |
| tests/test_esports_context.py | 9995c77e8b2d68eff410b6361d2ed8258622da84052119f8e5475323bcebe331 |
| tests/test_esports_context_model.py | 5c4911a2de028ba69346b27caa9f36513de82e6b0dcc00a6125a7d7dbf1faac9 |

Hashes sind tatsächliche lokale Bytes inklusive vorhandener CRLF/LF-Form,
nicht eine normalisierte Gittextrepräsentation. Keine Altdatei normalisiert.

Disposition: **Implementierung von P6a ist konkret vorbereitet, aber noch
nicht ausgeführt.** Zwei ursprüngliche REDs bleiben bis zum getrennt
beauftragten Fix erhalten. Keine Produktiv-/Source-/Empirikfreigabe.
