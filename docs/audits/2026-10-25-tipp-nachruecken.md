# Vertragsänderung 25.10.2026: Öffentliche Tipps folgen dem Quotenlauf (Nachrücken)

Owner-Entscheidung vom 25.10.2026 (Chat, nach dem Nachtcheck): Wenn der Quotenlauf einen
öffentlichen Tipp wegen einer Marktquote unter 1,20 entfernt, rückt die nächste freigegebene
Auswahl nach derselben Auswahlregel nach. Betroffen ist die Veröffentlichung im Quotenlauf
(`wettfinder_automation`), nicht die Modellmathematik und kein Freigabegate.

## Vorher (bis PR #25)

- Der Tagesscan (03:35) wählte die bis zu drei öffentlichen Tipps aus dem Modell-Ledger
  (`select_candidates`, Reihenfolge des Ledgers, eine Auswahl je Spiel), bevor irgendeine Quote
  vorlag; `_floor_playable_rows` konnte deshalb noch nichts unter 1,20 ausschliessen.
- Jeder Quotenlauf (alle drei Stunden, `--quotes-only --quote-sport all`) leerte anschliessend
  `candidates` und `challenge_release_candidates` vollständig (`_refresh_price_document`,
  „Do not manufacture a release during this display-only operation“), weil eine Freigabe unter
  dem alten Vertrag einen frischen ausführbaren Preisbeleg brauchte. Bis zum nächsten Nachtscan
  gab es dann keinen öffentlichen Tipp mehr. Am 25.10. fielen so die drei Tipps von 03:59 um
  06:15 weg (Marktquote unter 1,20), obwohl 166 von 353 Zeilen die statistische Freigabe
  bestanden; die 15K-Liste war aus demselben Grund praktisch immer leer.

## Nachher (ab PR #25, nur unter `BETBOY_PRICE_POLICY=floor`)

- Nach jedem Quotenlauf läuft dieselbe Auswahlregel wie im Tagesscan noch einmal über das
  gespeicherte Modell-Ledger (`_republish_floor_candidates`): Fussballzeilen mit verifiziertem
  Spielkontext, bestandener Freigabe (`_football_record_release_eligible`: Modellversion,
  HAC/BH-FDR-Belege, Kontext, Hypothesenfamilie) und ohne Marktquote unter 1,20; Tenniszeilen
  mit `PLAYABLE`-Quote. Voraussetzung wie im Scan: Fussball-Lauf `completed` ohne Betriebs- und
  Quotenfehler, Kontextstatus vorhanden.
- `select_candidates` wählt in Ledger-Reihenfolge die ersten drei, eine je Spiel, nur noch nicht
  begonnene Spiele des Zieldatums. Ein entfallener Tipp (unter 1,20, Spielbeginn) wird so durch
  die nächste freigegebene Auswahl ersetzt; die Ledger-Reihenfolge selbst (statistischer Rang)
  bleibt unverändert, Preis sortiert nichts um.
- Die veröffentlichten Zeilen sind Kopien der Modellzeilen mit den Überlagerungen `RECOMMENDED`,
  `RELEASED` und `release_contract`; der App-Lader prüft sie wie Scan-Veröffentlichungen
  (gleiche Felder, Preisstatus, Ausführungsfelder bei `PLAYABLE`).
- Die 15K-Freigabeliste wird mit derselben Regel wie im Scan neu besetzt: `PLAYABLE`-Zeilen mit
  Wahrscheinlichkeit 0,58–0,92 und konservativer Wahrscheinlichkeit ≥ 0,55, höchstens 15. Da
  Quoten erst im Tagesverlauf eintreffen, ist sie damit erstmals regulär gefüllt.
- Zähler `published_recommendation_count` und `challenge_release_candidate_count` in `sources`
  folgen der Neubesetzung. Unter `gate` bleibt alles wie bisher (Listen geleert).

## Begleitkorrekturen (gleicher Vertrag, ohne sie wäre das Nachrücken unsichtbar)

- **App-Lader, öffentliche Signale** (`ev_signal_sources.automated_wettfinder_signals`): Bis PR #25
  wurde eine veröffentlichte Zeile nur dann zum öffentlichen Tipp, wenn ihre Quote `PLAYABLE`
  war, und nur innerhalb von 150 Minuten nach dem Scan (`AUTOMATED_WETTFINDER_MAX_AGE`, der alte
  Preisvertrag). Unter `floor` wird jede veröffentlichte Zeile zum Tipp, deren Quote nicht unter
  1,20 liegt, auch ohne beobachtete Quote (`UNPRICED`); bei `PLAYABLE` müssen die
  Ausführungsfelder weiter zur Quote passen. Die Altersgrenze der öffentlichen Tipps ist unter
  `floor` die des Modelldokuments (24 Stunden, `_strict_signal_max_age`); Spielbeginn und
  Zieldatum je Zeile halten sie aktuell. Unter `gate` bleiben 150 Minuten und `PLAYABLE`.
- **Karte** (`wettfinder_surface.build_wettfinder_card`): `quote_floor_excluded` war „keine
  zugelassene Quote“, womit jede Prognose ohne beobachtete Quote aus „Dein Spieltag“ fiel (am
  25.10. 44 statt 84 Spiele). Unter `floor` ist nur noch eine Marktquote unter 1,20
  ausgeschlossen; Prognosen ohne Quote bleiben sichtbar, wie es die Preisregel vom 23.10.
  verlangt.

## Was das bedeutet

- Die öffentlichen Tipps spiegeln jederzeit die ersten drei freigegebenen, noch nicht
  begonnenen Auswahlen des Tages, abzüglich derer unter 1,20. Im Tagesverlauf rücken spätere
  Spiele nach, sobald frühere begonnen haben; ohne Quotenlauf ändert sich nichts.
- Kein neues Gate, keine neue Rangfolge: Freigabe und Reihenfolge stammen aus dem Nachtscan,
  der Quotenlauf wendet sie nur erneut an. Modell vor Preis bleibt unberührt.
- Grenze: Höchstens drei öffentliche Tipps (`MAX_AUTOMATED_RECOMMENDATIONS`) bleiben, ebenso der
  Takt der Quotenläufe (alle drei Stunden).

## Umsetzung

`wettfinder_automation._republish_floor_candidates` (Aufruf am Ende von `_refresh_price_document`
für Einzelsport-Läufe und von `_refresh_scheduled_prices` für den geplanten Lauf). Tests in
`tests/test_price_floor_policy.py`: Nachrücken nach `BELOW_FLOOR`, begonnene Spiele und nicht
freigegebene Zeilen, unverifizierter Kontext und Lauf mit Fehlern, 15K-Korridor, `gate`-Verhalten,
Ladbarkeit des neu besetzten Dokuments. Kein Schalter; der alte Vertrag ist bis PR #24 in Git
dokumentiert und gilt weiter unter `gate`.
