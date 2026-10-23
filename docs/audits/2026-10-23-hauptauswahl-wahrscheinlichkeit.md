# Vertragsänderung 23.10.2026 (abends): Hauptauswahl je Spiel, Karte ohne Mindestquote

Owner-Entscheidung vom 23.10.2026 (Chat, nach dem ersten Blick auf die seit dem Abend wieder
sichtbaren Tipps): Die Hauptauswahl je Spiel ist die angezeigte Auswahl mit der höchsten
Modellwahrscheinlichkeit, und die Karte nennt keine Mindestquote mehr; die 1,20-Grenze wirkt
ausschliesslich im Hintergrund. Betroffen ist die Darstellung, kein Freigabegate und keine
Modellmathematik.

## Vorher (bis PR #18)

- Die Hauptauswahl („Lead“) eines Spiels war der statistische Lead des Produzenten: der
  Markt mit dem höchsten `selection_rank` (Modellnutzen, Evidenzscore, relative
  Verbesserung, Spread, Abschlag, konservative Wahrscheinlichkeit), verglichen nur innerhalb
  derselben Teilnehmerbindung und Modellrevision (`forecast_selection.select_event_leads`).
  Wahrscheinlichkeiten verschiedener Märkte wurden ausdrücklich nicht verglichen.
- Beispiel vom 23.10.: Stuttgart–Gladbach führte „Auswärtssieg“ (16,6 %) vor „Unter 4,5“
  (78,3 %), weil der Auswärtssieg die stärkere Validierungsevidenz hatte.
- Im Wettfinder-Katalog konnten Zeilen ohne gültigen `selection_rank` (andere Sportarten,
  alte Dokumente) nie Lead sein; ein Spiel ohne vergleichbare Revision behielt seine erste
  Zeile als Lead.
- Karte unter `BETBOY_PRICE_POLICY=floor` (seit PR #14 am Nachmittag): keine Quote, kein
  Preisstatus, aber eine Zelle „Mindestquote 1,20“.

## Nachher (ab PR #19)

- **Lead = höchste Modellwahrscheinlichkeit.** Unter den angezeigten Märkten eines Spiels
  führt die Auswahl mit der höchsten Modellwahrscheinlichkeit, verglichen nur innerhalb
  derselben Teilnehmerbindung und Modellrevision (Modell- und Policy-Version, Modellzeit,
  Datenschnitt, Anpfiff, Modellumfang). Gleichstand entscheidet der stabile Marktschlüssel
  (Heim vor Unentschieden vor Auswärts, dann Marktschlüssel), nie die Eingabereihenfolge.
- `selection_rank` bleibt auf den Zeilen und ordnet weiter den Katalog
  (`wettfinder_automation._ordered_football_record_pool`) und die 15K-Liste; er wählt aber
  keinen Lead mehr.
- Fällt der Lead aus der Anzeige (zum Beispiel Marktquote unter 1,20), wird der
  wahrscheinlichste verbleibende Markt derselben Revision sichtbarer Lead. Ein Markt mit
  unbekannter oder fremder Revision kann weder Lead noch Ersatz werden; das Spiel wird dann
  ohne Hauptauswahl gezeigt (`require_comparable=True` im Katalog).
- Gilt überall, wo Spiele gruppiert werden: Wettfinder („Dein Spieltag“), Manuelle Suche und
  15K-Modellauswahl (`bet_finder_ui.consumer_event_leads`). Damit bekommen auch Zeilen ohne
  `selection_rank` einen Lead, sobald ihre Revision vergleichbar ist.
- **Karte ohne Mindestquote.** Unter `floor` zeigt die Karte Modellwahrscheinlichkeit und
  Analyse; keine Buchmacherquote, keinen Preisstatus und keine Zelle „Mindestquote“. Die
  1,20-Grenze sperrt weiter im Hintergrund (`BELOW_FLOOR`); Daily3-Vormerkung und
  Preisentscheidung prüfen eine eingegebene Quote weiterhin gegen 1,20.
- **Nachtrag (Owner, 23.10. spätabends, PR #21): auch keine Hinweise bei eigener
  Quoteneingabe.** Unter `floor` entfallen „Deine Mindestquote für eine tatsächliche Wette:
  1,20“ (Manuelle Suche, Tennis), „Mindestquote für eine Vormerkung: 1,20“ und der
  Mindestquoten-Satz im Regeltext (Daily3), die Zelle „Mindestquote“ in „Meine Tipps“ sowie
  die letzten Buchmacherquoten im Tennis-Tab („Letzte Quote“) und in der Multi-Sport-Suche
  („Quote“), die der Preisregel vom Nachmittag noch entgangen waren. Die Sperre bleibt: eine
  eingegebene oder beobachtete Quote unter 1,20 wird mit Begründung abgelehnt
  (`Keine passende Quote ab 1,20`, `Quote … liegt unter 1,20`, Daily3-Vormerkung).

## Was das bedeutet

- Die Hauptauswahl ist eine Darstellungsregel. Jede angezeigte Auswahl hat dieselben
  Modell-, Statistik- und Kontextgates bestanden; der Lead ist nur die Auswahl, die ein
  Spiel anführt. Die Wahrscheinlichkeit ist die Modellwahrscheinlichkeit der Auswahl und
  keine Aussage über Wert: eine hohe Wahrscheinlichkeit bedeutet eine niedrige faire Quote.
- Modell vor Preis bleibt unberührt: keine Quote fliesst in die Wahl ein. Die
  Richtungskohärenz (Ergebnis, BTTS) läuft unverändert vor der Lead-Wahl.
- Neu ist, dass Märkte eines Spiels nach Wahrscheinlichkeit verglichen werden. Das war bis
  zum 23.10.2026 bewusst ausgeschlossen (Docstring `forecast_selection`, Review
  `docs/audits/2026-09-08-widerspruchsfreie-auswahl-review.md`) und ist jetzt
  Owner-Entscheidung.

## Umsetzung

`forecast_selection.select_event_leads` (`_model_probability`, Parameter
`require_comparable`), `wettfinder_surface.compose_wettfinder_catalog` (Leads ohne
`selection_rank`-Filter, `require_comparable=True`), `wettfinder_surface.render_editorial_card_html`
(keine Mindestquote-Zelle unter `floor`), Kommentare in `app.py`. Tests:
`tests/test_wettfinder_statistical_leads.py` (Lead nach Wahrscheinlichkeit, Gleichstand,
fremde oder unbekannte Revision, Permutationsinvarianz, Renderer-Reihenfolge),
`tests/test_claude_ux_recheck.py` (Ersatz-Lead derselben Revision, neutrale Darstellung bei
unbekannter Revision), `tests/test_manual_statistical_selection.py` (Manuelle Suche und 15K),
`tests/test_price_floor_policy.py` (Karte ohne Mindestquote; seit PR #21 auch Modellansicht,
Daily3-Vormerkung und Tennis-Karte ohne Hinweis). Kein Schalter; der alte Vertrag ist bis
PR #18 in Git dokumentiert.
