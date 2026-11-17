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

## Release 20261115-2

Owner „Ja, live stellen“ am 15.11.2026.

- **Merge:** PR #129 um 21:58 CET, `origin/main` = `7f35c23733935935c88f9cfa3b35a68851a7675d`. Die CI war grün
  (ruff und schnelle Teilmenge; Lader, Publikation, Daily3 und 15K unter `floor` und `gate`). Der Baum ist gleich
  dem PR-Stand `545cbfb`.
- **Dateien:** 16 von `d19e755` bis `7f35c23`. Code: `app.py`, `wettfinder_surface.py`, `ev_signal_sources.py`;
  sonst Tests und Doku (darunter das Protokoll PR #128). Keine Einheit, kein `.sh`, keine Requirements.
- **Generator:** `output/release-20261115-2/gen_deploy54.py`, abgeleitet von `gen_deploy53.py` über `make_gen.py`.
  Neue Asserts: `render_wettfinder_row_html` vorhanden, `row_competition` für Liga 5 und für `competition`, im
  `app.py` die Stylesheet-Kopie und die neuen Zeilen ohne `_remember_wettfinder_game_state`, `app.py` parsebar.
- **Offline-Prüfung lokal** gegen einen Worktree von `545cbfb` (gleicher Baum): `OFFLINE_RELEASE_IMPORTS=ok`.
- **Hochladen:** sha256 auf dem Server gleich (`deploy-20261115-2.sh` `5c0940f8…`, `run_release-20261115-2.sh`
  `6b682c61…`).
- **Ausrollen:** Fenster um 22:02:41 (Abstand zum nächsten Shadow-Lauf 559 s). Ergebnis `HEAD=7f35c23…`,
  `APP_PID=1638757->1642925`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`. Log
  `output/release-20261115-2/deploy-01.log`.
- **Danach:** Health lokal und öffentlich `ok`, App, Caddy und alle 7 Timer aktiv, keine neue fehlgeschlagene
  Einheit (die 8 alten vom September bleiben). Die Live-Seite zeigt die offenen Karten, zum Beispiel
  „Fußball · UEFA Nations League · 16.11. 16:00“, Kazakhstan gegen Slovakia, Über 1.5, Modell 79.8 %, Grundlage und
  Contra, darunter die Form.

## Nachtrag: Kontext als kleine Zeile

Auf der Live-Seite stand der Kontext als grosses Abzeichen in Grossbuchstaben, und das bei jedem Markt. Live ist
er ein langer Satz, zum Beispiel „H2H geprüft, kein belastbares Veto · Ausfälle nicht verfügbar · Wetter geprüft ·
Aufstellungen für vollständige Bestätigung noch offen“.

- Der Kontext ist jetzt eine kleine graue Zeile „Kontext: …“ unter Grundlage und Contra (Klasse `rb-row-missing`,
  wie „Fehlt:“ bei RisikoBet). Ein Abzeichen gibt es nicht mehr.
- Er steht nur in der ersten Zeile eines Spiels (`render_wettfinder_row_html(show_context=)`).
- Tests in `tests/test_wettfinder_risikobet_rows.py`: keine Abzeichen, die Zeile lässt sich weglassen, „ausstehend“
  wird nicht gezeigt, und bei einem Spiel mit zwei Märkten steht der Kontext nur in der ersten Zeile.

## Release 20261116-1

Owner „Ja, live stellen“ (15./16.11.2026) für PR #130.

- **Merge:** PR #130 um 00:32 CET, `origin/main` = `2b572e0a9d378b6a8ef4d5faf2813dcb5e01e7ee`. Die CI war grün.
- **Dateien:** 5 von `7f35c23` bis `2b572e0`: `app.py`, `wettfinder_surface.py`, `STATUS.md`, dieser Bericht und
  `tests/test_wettfinder_risikobet_rows.py`. Keine Einheit, kein `.sh`, keine Requirements.
- **Generator:** `output/release-20261116-1/gen_deploy55.py`, abgeleitet von `gen_deploy54.py` über `make_gen.py`.
  Neue Asserts: `show_context` in `render_wettfinder_row_html`, `show_context=position == 0` in `app.py`.
- **Offline-Prüfung lokal** gegen einen Worktree von `2b572e0`: `OFFLINE_RELEASE_IMPORTS=ok`.
- **Hochladen:** sha256 auf dem Server gleich (`deploy-20261116-1.sh` `55493991…`, `run_release-20261116-1.sh`
  `ba400717…`).
- **Ausrollen:** Fenster um 00:33:20 (Abstand zum nächsten Shadow-Lauf 520 s). Ergebnis `HEAD=2b572e0…`,
  `APP_PID=1642925->1644442`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`. Log
  `output/release-20261116-1/deploy-01.log`.
- **Danach:** Health lokal und öffentlich `ok`, App, Caddy und alle 7 Timer aktiv, keine neue fehlgeschlagene
  Einheit (die 8 alten vom September bleiben).
- **Live-Seite nach Mitternacht leer:** Die Seite zeigte „Aktuell ist noch kein automatisches Ergebnis verfügbar.“
  Der Grund ist der Datumswechsel, nicht das Release. Seit 00:00 ist der Spieltag der 16.11., das Tagesdokument ist
  aber vom 15.11. (03:44), und der nächste Nachtlauf kommt um 03:35. Mit der Uhr 15.11. 23:00 liefert der Lader auf
  dem Server 42 Prognosen, alle mit Liga.
- **Darstellung auf dem Server geprüft** (nur gelesen, Daten mit Uhr 23:00, gerendert wie der Wettfinder): 15 Spiele,
  27 Zeilen, 0 Abzeichen, 11 Kontextzeilen, also höchstens eine je Spiel. Die erste Kopfzeile lautet
  „Eishockey · NHL · 16.11. 01:30“.

## Nachtrag 17.11.2026: Karte und Raster wie RisikoBet

Owner am 17.11.2026: „bin leider mit der Darstellung noch immer nicht zufrieden, es sieht halt nicht wirklich wie
das vom RisikoBet aus, wenn du vergleichst, siehst du massive Unterschiede“.

### Vergleich

Beide Seiten live nebeneinander angesehen, bei 1280 px Breite und in der Handy-Ansicht (375 px).

| Stelle | RisikoBet | Wettfinder bis 17.11. |
|---|---|---|
| Liste | zwei Karten nebeneinander | eine breite Karte je Zeile |
| Überschrift der Liste | „Risiko-Szenarien“ in der Titelschrift | „Spiele“ klein |
| Über der ersten Zeile der Karte | nichts | eine Linie |
| Unter der Zeile | nichts | „Tipp merken“ über die ganze Kartenbreite |
| Details | „Multigoal & Sieg-Kombis“ mit Umschalter 5/10, Hinweiszeile, Tabelle „Gesamttore“ | Block „Aktuelle Form“ mit farbigen Ergebniskacheln und Gegnerlisten je Team, darunter die Tabelle mit kleiner Überschrift |
| Form | je Team eine Textzeile | Kacheln |
| Weitere Angaben | geschlossene Schublade „Analyse anzeigen“ | drei kleine Aufklapper nebeneinander |

### Jetzt

- **Raster:** Die Spiele stehen wie bei RisikoBet zu zweit nebeneinander (`wettfinder_game_grid`), ab 1081 px Breite.
  Darunter steht eine Karte je Zeile. Die Reihenfolge im Raster ist die Lesereihenfolge, auch auf dem Handy.
- **Überschrift:** „Spiele“ ist dasselbe Element wie „Risiko-Szenarien“ (`## Spiele`).
- **Karte:** keine Linie mehr über der ersten Zeile. Eine Linie trennt nur weitere Märkte desselben Spiels.
- **Details in der Reihenfolge von RisikoBet** (`app._render_wettfinder_game_details`):
  1. „Multigoal & Sieg-Kombis“ mit dem Umschalter 5/10, der Hinweiszeile und der Tabelle „Gesamttore“. Das Markup
     ist dasselbe wie auf der RisikoBet-Seite (`sports_form.render_goal_history_html`).
  2. Die Form als Textzeile je Team (`forecast_compact.compact_form_lines`), im Wortlaut der RisikoBet-Karte:
     - Fussball: „Wales: 1S · 0U · 4N (5) / 3S · 3U · 4N (10); Gegner (10): Norway 1:3; …“
       (`sports_form.form_text_lines`). Bei mehr als 600 Zeichen fällt die Gegnerliste auf fünf Spiele zurück.
     - Tennis: „Belag: …“ und je Spieler nur die Bilanz, „4/5 Siege · 6/10 Siege“, ohne Gegnerliste.
     - Eishockey, Basketball und E-Sport: der Satz, den auch RisikoBet zeigt (er steht schon im Fakt
       „Letzte Spiele“, zum Beispiel „…; zuletzt: S 3:2 gegen …“ oder „Letzte 5 Serien: …“).
  3. Sichtbare Warnungen als graue Zeile.
  4. Die geschlossene Schublade „Analyse anzeigen“ (`forecast_compact.compact_analysis_lines`), ein Absatz je
     Zeile. Darin stehen Gegenrisiko, Basis, Gegenargument, Ausfälle und Aufstellung mit ihren Details und jedes
     bekannte Ergebnis genau einmal mit Datum, Gegner, Spielort und Wettbewerb. Die Ergebnisse standen bisher
     hinter den Kacheln. Zählt ein Markt-Fakt dieselben Spiele als Details auf, entfallen sie dort.
- **Vorher offen, jetzt in der Schublade:** Gegenrisiko, Basis, Ausfälle und Aufstellung standen bisher mit ihrem
  Kurzwert offen auf der Karte. Jetzt stehen sie erst nach dem Öffnen da, wie bei RisikoBet. Bei Fussball nennt
  die Zeile „Contra“ das Gegenrisiko weiter offen.
- **„Tipp merken“** bleibt unter jeder Zeile, jetzt als kleiner Knopf statt als Balken über die Kartenbreite.
- **Text aus Daten** geht als reiner Text in die Zeilen (`wettfinder_surface.plain_markdown`). Ein Name wie
  „1. FC Köln“ wird damit nicht zu einem Listenpunkt.

### Unverändert

- Auswahl, Reihenfolge, Sportfilter, Regler, 20 Spiele je Seite, das Protokoll der gezeigten Auswahlen.
- Die Zeile selbst (`render_wettfinder_row_html`) mit dem Kontext als kleiner Zeile.
- Die rechte Spalte (Doublebet, Tennis). Weil sie bleibt, sind die zwei Karten schmaler als bei RisikoBet; die
  Zeile hat deshalb zwei Spalten, die Begründung steht darunter.
- Doublebet und 15K behalten ihre Karten mit Kacheln (`render_compact_analysis_html`, `render_form_html`).
- Die RisikoBet-Seite selbst.

### Bekannte Unterschiede zu RisikoBet

- RisikoBet stellt bis zu drei hervorgehobene Szenarien als grosse Karte dar (`render_riskobet_card_html`), wenn
  Kontext und Preis aktuell geprüft sind. Am 17.11. zeigte die Live-Seite keine. Der Wettfinder hat diese Karte
  nicht; seine Highlights sind Zeilen wie alle anderen (Entscheid vom 15.11.).
- RisikoBet zeigt den Kontext als Abzeichen, der Wettfinder als kleine Zeile (Nachtrag vom 15.11.).
- Der Wettfinder hat „Tipp merken“, den Regler und die rechte Spalte.

### Prüfung

- **Neu** in `tests/test_wettfinder_risikobet_rows.py`:
  - Tabelle im RisikoBet-Aufbau und mit demselben Markup wie `riskobet_ui._football_goal_history_html`; zehn
    Spiele nur mit zehn Ergebnissen je Seite.
  - Formzeilen: Fussball mit Gegnern und Rückfall auf fünf, Tennis nur mit Bilanz, Mannschaftssport mit dem Satz
    aus „Letzte Spiele“.
  - Schublade: jedes Ergebnis einmal, zwei gleiche Ergebnisse bleiben zwei Spiele, keine leere Schublade.
  - Im Renderpfad: Reihenfolge Tabelle, Formzeilen, Warnung, Schublade; keine Kacheln; interne Notizen bleiben
    draussen; „Tipp merken“ je Markt in dessen Container; eine Schublade je Spiel mit eigenem Schlüssel; Tennis.
  - Raster mit zwei Karten je Zeile, reiner Text, Regeln im Stylesheet.
- **Angepasst:**
  - `test_wettfinder_game_groups.py`, `test_wettfinder_surface.py`, `test_workflow_integrity.py`: Das Spiel ist nie
    ein Aufklapper, erlaubt ist nur die geschlossene Schublade „Analyse anzeigen“.
  - `test_wettfinder_game_groups.py` (echter Streamlit-Lauf) und `test_wettfinder_min_chance.py`: als Aufklapper
    kommt nur „Analyse anzeigen“ vor.
  - `test_workflow_integrity.py` prüft neu auch die Überschrift „## Spiele“, die Spaltengruppen des Rasters und
    die verbotenen Wörter im Text von Formzeilen, Warnung und Schublade.
  - `test_tip_bookmarks.py` lädt die neue Funktion in den ausgeführten Namensraum.
- **CI:** `tests/test_wettfinder_risikobet_rows.py` läuft neu im Job für beide Preisregeln.
- **Vier unabhängige Prüfer** (Python, CSS, Gleichheit mit RisikoBet, Tests und Regeln): kein Blocker. Ihre
  Befunde sind eingearbeitet: Tennis ohne Gegnerliste, kein doppeltes Ergebnis in der Schublade, die Schublade als
  ein Element, Wortlaut für Mannschaftssport, die Überschriftgrösse nur ab 761 px, keine kopierte Zwei-Spalten-Regel
  auf dem Detailblock.
- **Lokale Vorschau** mit Testdaten (Fussball mit zwei Märkten, Fussball mit sieben Ergebnissen, Tennis) bei
  375, 960, 1280 und 1920 px, neben der Live-Seite von RisikoBet.
