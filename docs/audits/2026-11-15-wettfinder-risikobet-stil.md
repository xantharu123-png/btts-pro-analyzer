# Wettfinder im RisikoBet-Stil

Stand 15.11.2026. Owner: „der Wettfinder … sieht anders aus als die anderen Scanner, ich finde die anderen besser,
zum Beispiel den vom RisikoBet“. Auswahl „Ganz wie RisikoBet“, nach der lokalen Vorschau „Passt, fertig machen“.

## Vorher

- Jedes Spiel war ein zugeklapptes Feld („Belarus vs Albania · Fußball · 15.11. 18:00 · 1 Auswahl“). Die ersten
  drei waren offen, die übrigen musste man aufklappen. Auf/Zu wurde je Spiel gemerkt.
- Darin stand die grosse Karte des Doublebet: Trikots oder Flaggen, Auswahl, Modell, „Die Auswahl im Kurzcheck“,
  danach Form und Tabellen. Weitere Märkte folgten unter „Weitere Märkte“.

## Jetzt

- Jedes Spiel ist eine offene Karte im Stil von RisikoBet. Es gibt kein Aufklappen und keinen Trikot-Kopf mehr.
- Jeder Markt des Spiels ist eine flache Zeile mit den RisikoBet-Klassen (`rb-row`):
  - Kopfzeile Sport · Liga · Anstoss
  - Spiel
  - Auswahl mit Markt
  - „Modell xx %“
  - „Grundlage“ (der bisherige Kurzcheck) und, wenn vorhanden, „Contra“
  - Die wahrscheinlichste Auswahl steht wie bisher zuerst (Owner-Entscheid 23.10.2026).
- „Tipp merken“ bleibt unter jeder Zeile.
- Form und Tabellen des Spiels folgen einmal, offen, unter den Zeilen, wie die Details bei RisikoBet.
- **Liga:** Eishockey und E-Sport bringen den Namen mit. Fussballzeilen tragen nur `league_id`. Der Lader setzt dafür
  den Katalognamen (`ev_signal_sources.row_competition`), etwa „Spain: Segunda División“ oder „UEFA Nations League“.

## Code

- `wettfinder_surface.render_wettfinder_row_html`: die Zeile. Highlights bekommen kein sichtbares Abzeichen, nur
  `data-featured`.
- `app._render_wettfinder_game`: offene Karte je Spiel (`wettfinder_game_row_<Spiel>`). Die Zeilen sitzen in
  `wettfinder_v2_game_market_<Markt>`, die Form in `wettfinder_game_details_<Spiel>`.
  `_remember_wettfinder_game_state` und das gemerkte Auf/Zu fallen weg.
- `app._with_wettfinder_risk_rows`: Das Stylesheet kopiert den RisikoBet-Abschnitt einmal unter den
  Wettfinder-Schlüsseln. Weil die Hauptspalte schmaler ist als die RisikoBet-Seite, hat die Zeile zwei Spalten,
  die Begründung steht darunter; bis 760 px ist es eine Spalte.
- `ev_signal_sources.row_competition`: Ligaanzeige aus `competition`, sonst aus `league_id` über `league_catalog`.

## Unverändert

- Auswahl, Reihenfolge (Startzeit oder Wahrscheinlichkeit), Sportfilter, Regler „Mindest-Modellchance“ (Start 70 %),
  20 Spiele je Seite, ohne ein Spiel über zwei Seiten zu teilen.
- Das Protokoll der gezeigten Auswahlen (`record_signal_catalog`), Tipps, Evidenz und Abrechnung.
- Die rechte Spalte (Doublebet, Tennis), die Doublebet-Seite und 15K behalten ihre Karten.
- Keine Buchmacherquote und keine Mindestquote in der App (`floor`).

## Prüfung

- **Neu:** `tests/test_wettfinder_risikobet_rows.py`. Geprüft werden die Kopfzeile mit Liga und das Escaping, die
  Zeile ohne Liga und ohne Begründung, „Contra“, kein Abzeichen, die Ligaanzeige aus `competition` und `league_id`
  sowie die Wettfinder-Regeln im Stylesheet.
- **Angepasst** sind Tests, die das Aufklappen festschrieben: `test_wettfinder_game_groups.py`,
  `test_workflow_integrity.py`, `test_wettfinder_surface.py`, `test_wettfinder_min_chance.py`,
  `test_sports_editorial.py`, `test_tip_display_order.py`, `test_claude_ux_recheck.py` und
  `test_tip_bookmarks.py`. Sie prüfen jetzt:
  - keine Aufklapp-Felder
  - jeder Markt in der Karte seines Spiels
  - eine Karte je Spiel mit festem Schlüssel
  - Reihenfolge, Seiten und Filter wie bisher
- **Lokale Vorschau** mit Testdaten (Fussball mit zwei Märkten, Tennis). Owner-Rückmeldung: „Passt, fertig machen“.

## Zurücknehmen

Den Merge zurücknehmen. Daten und Protokolle sind nicht betroffen.
