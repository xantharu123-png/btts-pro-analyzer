# Vertragsänderung 25.10.2026: Lader verwirft je Zeile, Quotenlauf und 15K-Snapshot mit Zeilen-Uhr

Owner-Entscheidung vom 25.10.2026 (Massnahme 1 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md`,
Befunde L1, L2, L5, L8). Hintergrund: Am 25.10. war die Website zweimal leer (06:15–07:28 und
09:15–12:02 CET), weil der App-Lader bei einer einzigen Zeile mit abweichendem Preisstatus das ganze
Tagesdokument verwarf. Zwei weitere Auslöser derselben Art standen noch im Code, und die 15K-Seite
konnte unter der Preisregel strukturell nichts zeigen. Betroffen ist die Veröffentlichungskette, kein
Modell und kein Freigabegate. Alles gilt nur unter `BETBOY_PRICE_POLICY=floor`; `gate` behält den
alten Vertrag unverändert.

## Vorher (bis PR #29)

- `ev_signal_sources._load_automated_wettfinder_document` lieferte `None` (leere Website), sobald eine
  Modell- oder veröffentlichte Zeile einen Preisstatus trug, den der Lader nicht reproduzieren konnte
  (E-Sport `OBSERVED` am 25.10. 06:15; Scan-Uhr statt Preis-Uhr am 25.10. 09:15; `UNAVAILABLE` mit
  behaltener Quote; Zähler `sources.football.operational_error_count` ≠ 0 nach einem degradierten Scan).
- `wettfinder_automation._apply_reference_quotes`: eine im Quotenlauf geprüfte Zeile ohne neue passende
  Quote behielt die alte `reference_quote`, Status `UNAVAILABLE`, ohne `reference_price_evaluated_at`;
  unter `floor` konnte der Lader diesen Status nicht reproduzieren.
- `build_scheduled_challenge_snapshot` verlangte für jede Zeile der 15K-Liste einen 45-Minuten-Konsens
  relativ zur Scan-Uhr und gab sonst `None` für den ganzen Snapshot zurück; nach dem Nachrücken (Quoten
  jünger als der Scan) war die 15K-Seite deshalb immer leer („noch kein verwendbares 15K-Ergebnis“).
- `_republish_floor_candidates` prüfte `football.operational_error_count`, der Lader
  `sources.football.operational_error_count`; der Fussball-Quotenlauf zählte Budgetmeldungen
  (`APIBudgetExceeded`) als Betriebsfehler und schaltete damit das Nachrücken ab.

## Nachher (ab PR #30)

- **Lader je Zeile.** Struktur- und Identitätsfehler (Version, Policy, Zieldatum, Schlüssel,
  Modellversion, Zeilenstatus, Wahrscheinlichkeits- und Mindestquotenfelder, Spielbeginn,
  Strict-Zeile ≠ Modellzeile) verwerfen weiter das ganze Dokument. Eine Preis- oder Statusabweichung
  (nicht reproduzierbarer `reference_price_status`, fehlende oder widersprüchliche Ausführungsfelder,
  ungültige oder rückdatierte `reference_price_evaluated_at`, Quote nicht an die Auswahl gebunden,
  Marktquote unter 1,20 bei einer veröffentlichten Zeile) hält nur diese Zeile und ihre
  veröffentlichten Kopien zurück. Die Anzahl steht als `price_inconsistent_rows` im Status
  (`AutomatedWettfinderStatus`) und im Log als Warnung.
- **Beobachtungszeilen.** `UNAVAILABLE` oder `OBSERVED` mit Quote und ohne Ausführungsfelder gilt
  als Anzeigebeleg, wenn die Quote als Floor-Code klassifiziert (`_legacy_observation_row_accepted`).
- **Behaltene Quoten im Quotenlauf.** Eine geprüfte Zeile ohne neue passende Quote behält unter
  `floor` nicht nur die alte Beobachtung, sondern wird mit ihr klassifiziert
  (`wettfinder_reference_price_status`), bekommt `reference_price_evaluated_at` und bei `PLAYABLE`
  die Ausführungsfelder; sie zählt als spielbar. Unter `gate` bleibt die Beobachtung reine Anzeige.
- **15K-Snapshot.** `_challenge_release_quote` bewertet jede Zeile der 15K-Liste mit ihrer eigenen
  Preis-Uhr (`reference_price_evaluated_at`, nie vor der Scan-Uhr) und unter `floor` mit dem
  Floor-Status statt des 45-Minuten-Konsenses; eine nicht ausführbare Zeile wird übersprungen, nicht
  der Snapshot. Die Liste bleibt auf `PLAYABLE`-Zeilen mit Ausführungsfeldern beschränkt.
- **Zähler.** Das Nachrücken verlangt zusätzlich `sources.football.operational_error_count == 0`
  (Tennis analog), also denselben Zähler wie der Lader. Der Fussball-Quotenlauf zählt nur echte
  Betriebsfehler (`_operational_quote_errors`, wie Scan und Tennis); Budgetschutz und fehlende
  Marktabdeckung bleiben Datenlücken.

## Was das bedeutet

- Ein einzelner Produzentenfehler kann die Website nicht mehr leeren; er kostet die betroffene
  Zeile und wird gezählt. Fail-closed bleibt für alles, was die Identität oder Struktur des
  Dokuments betrifft.
- Die 15K-Liste ist damit erstmals auf der 15K-Seite nutzbar; ihr Korridor (0,58–0,92,
  konservativ ≥ 0,55, bepreist) ist unverändert. Offen bleibt Befund L3 des Audits: der
  Floor-Status liefert den Bestpreis als `usable_odds`; der Ausführungspreis sollte aus der frischen
  Teilmenge kommen.
- Modell vor Preis bleibt unberührt; Reihenfolge, Freigabe und Kohärenz ändern sich nicht.

## Umsetzung

`ev_signal_sources` (`_load_automated_wettfinder_document`, `_legacy_observation_row_accepted`,
`AutomatedWettfinderStatus.price_inconsistent_rows`), `wettfinder_automation`
(`_apply_reference_quotes`, `_challenge_release_quote`, `build_scheduled_challenge_snapshot`,
`_republish_floor_candidates`, `_refresh_price_document`). Tests in `tests/test_price_floor_policy.py`:
Zeilen- statt Dokumentverwerfung mit Zähler, Strukturfehler weiter fail-closed, `gate` unverändert,
behaltene Quote klassifiziert, 15K-Zeile mit Preis-Uhr und Floor-Status, rückdatierte Uhr, Zähler des
Nachrückens, Budgetmeldung im Quotenlauf.
