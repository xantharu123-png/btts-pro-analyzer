# Heute und morgen, Schritt 3a: Eishockey, Basketball und E-Sport

Stand 11.11.2026. Owner-Entscheid vom 10./11.11.2026: Jede Liste zeigt die Tipps für heute und morgen (Zürcher Tag).
Fussball listet morgen seit dem 02.11. und seit dem 10.11. immer (`docs/audits/2026-11-10-folgetag-immer.md`). Dieser
Schritt 3a bringt den nächsten Tag auch für Eishockey, Basketball und E-Sport in die automatische Wettfinder-Liste.
Tennis folgt als eigener Schritt, weil dort das Scan-Kontingent die Grenze ist. Cricket bleibt gesperrt.

## Änderung

- **E-Sport:** Der E-Sport-Scan um 03:10 speichert die nächsten sechs Spiele je Game. Spiele von morgen lagen damit oft
  schon vor und fielen nur am Tagesfilter heraus. Der Tageslauf listet sie jetzt als eigene Morgen-Liste.
  - Die Preise werden zur Veröffentlichungszeit neu eingestuft, wie heute schon für die heutigen Zeilen
    (`_revalidate_publication_price_overlays`).
- **Basketball und Eishockey:** Ist die Teamsport-Recherche fällig, liest der Tageslauf zusätzlich die Spielpläne für
  morgen und rechnet dieselben Modelle.
  - Das Zeitfenster umfasst heute und morgen, denn ESPN und die NHL führen ein Abendspiel unter dem
    nordamerikanischen Datum, in Zürich beginnt es nach Mitternacht. Danach bleibt nur der nächste Zürcher Tag.
  - Ein NHL-Spiel innerhalb von 24 Stunden bleibt wie bisher ein Spiel von heute (`automatic_team_sport_day`).
  - Ohne neue Recherche werden die gültigen Morgen-Zeilen des letzten Laufs aus ihren eigenen Snapshots neu
    abgeleitet (`source: reused`).
- **Kennzeichnung im Dokument:** `next_day_search_date` und je Sportart `sources.<sportart>.next_day` mit
  `search_date`, `status` (`listed`, `empty` oder `failed`), Anzahl Zeilen und Spiele. Der Lader akzeptiert Morgen-Zeilen
  einer Sportart nur mit `status: listed` für genau diesen Tag. Fussball braucht weiter seinen eigenen
  `football_next_day`-Zustand, ist aber nicht mehr die einzige Freigabe (`automated_next_day_sports`).
- **Fehler bleiben bei morgen:**
  - Eine ungültige Morgen-Zeile hält der Lader einzeln zurück, statt das ganze Dokument zu verwerfen.
  - Das gilt für Status, Wahrscheinlichkeit, Mindestquote, Teamsport-Snapshot und Preisstatus.
  - Morgen-Zeilen können nie Tipp oder 15K-Zeile sein, denn diese Listen müssen auf heute liegen. Darum ändert das
    Zurückhalten keine Entscheidung über heute.
  - Für das ganze Dokument bleiben fail-closed: Struktur, Schlüssel, Modellversion, Kontext-Referenz,
    Sportart-Quelle-Vertrag, Obergrenzen und die Kennzeichnung selbst. Eine Morgen-Zeile ohne passende Kennzeichnung,
    eine Tennis-Zeile für morgen und jede ungültige Zeile von heute verwerfen das Dokument weiter.
  - Ein Fehler beim Teamsport-Scan für morgen erscheint nur in `sources.<sportart>.next_day` und lässt heute
    unverändert.

## Ausschlüsse

- Morgen-Zeilen sind nur Modellauswahlen in der Wettfinder-Liste. Sie werden nie:
  - öffentlicher Tipp (`candidates`),
  - 15K-Zeile,
  - Doublebet-Auswahl,
  - Shadow-Eintrag,
  - Evidenz-Prognose (`record_forecast_run` läuft vor dem Anhängen),
  - archivierte Veröffentlichung vor dem eigenen Spieltag (`listed_next_day_signal`, jetzt für alle gelisteten
    Sportarten).
- RisikoBet bleibt bei heute: Die Morgen-Snapshots gehen nie in den RisikoBet-Lauf, seinen Katalog oder seine
  Preisziele.
- Je Sportart nimmt morgen nur, was die Obergrenze des Laders (1200 Zeilen) nach heute übrig lässt. So kann morgen das
  Dokument nicht über die Grenze heben.

## Kosten pro Tag

Der Morgen-Scan läuft in jedem Tageslauf mit fälliger Teamsport-Recherche, also normalerweise einmal am Tag.

- **Basketball:**
  - ESPN-Spielplan: 2 Abrufe mehr (heute und morgen, frei).
  - EuroLeague-Saisonplan: 1 Abruf mehr (frei).
  - Ergebnishistorie: dieselben zwischengespeicherten Monats- und Saisonfenster wie heute, normalerweise 0 Abrufe mehr.
- **Eishockey:**
  - NHL-Wochenplan: 1 Abruf mehr (frei).
  - API-Sports Hockey: 1 Abruf mehr für das Datum von morgen. Das Datum von heute ist 3 Stunden zwischengespeichert und
    wird mit der heutigen Recherche geteilt.
  - Ligahistorie: nur innerhalb der bestehenden Grenzen (8 je Aufruf, 48 pro Tag, Zwischenspeicher).
  - Grenze von API-Sports Hockey: 100 Abrufe pro Tag.
- **E-Sport:** 0 Abrufe mehr. PandaScore-Scan und OddsPapi-Abruf bleiben unverändert.
- **Quotenläufe:** Teamsport-Zeilen von morgen kommen in den bestehenden Preisabruf, der schon bis 3 Tage voraus prüft.
  - Grenze: höchstens 8 Spiele je Sportart und Lauf, heutige Spiele zuerst, Budget von 100 Abrufen pro Tag.
  - Dadurch sind mehr Preisabrufe möglich, aber nur innerhalb dieser Grenze.

## Prüfung

- **Neue Tests** `tests/test_wettfinder_next_day_other_sports.py` (21), zuerst rot, dann grün:
  - E-Sport und Teamsport von morgen erscheinen als Modellauswahl und nie in Tipps, 15K, Doublebet, Evidenz oder
    Archiv. Heute bleibt identisch mit einem Lauf ohne morgen.
  - Ein NHL-Spiel innerhalb von 24 Stunden bleibt heute und erscheint nur einmal.
  - Ungültige Morgen-Zeilen werden einzeln zurückgehalten, ungültige heutige Zeilen verwerfen das Dokument weiter,
    ebenso Morgen-Zeilen ohne Kennzeichnung.
  - Fussball ist nicht mehr die einzige Freigabe.
  - Ein Fehler beim Teamsport-Scan für morgen lässt heute unverändert.
  - Ein späterer Lauf ohne Recherche übernimmt die Morgen-Zeilen.
  - Die Obergrenze je Sportart wird eingehalten.
  - Die Standardquellen lesen je ein Zeitfenster, und ein Scan mit fortlaufender Uhr behält seine Zeilen.
- **Lokale Läufe:** 47 Testdateien rund um Tageslauf, Lader, Folgetag, Teamsport, E-Sport, Tipp-Archiv, RisikoBet und
  Workflow, dazu ruff auf den geänderten Dateien.
  - Preisvertrag `gate`: 2044 grün, 2 rot.
  - Preisvertrag `floor`: 2027 grün, 19 rot.
- **Schon vorher bestehende Fehlschläge:** Sie scheitern genauso auf dem unveränderten `main` `c835ec4` (dort 2023
  beziehungsweise 2006 grün).
  - `gate`: `test_forecast_consumer_reuses_exact_cached_price_without_network`,
    `test_production_stages_preserve_document_order_and_private_callbacks`.
  - `floor`: dieselben 19 Tests in `test_team_sport_prices` (6), `test_team_sport_forecasts` (5),
    `test_esports_prices` (5), `test_hockey_esports_clock` (2) und `test_wettfinder_stage_diagnostics` (1).

## Offen

- **E-Sport-Abdeckung für morgen:** Es erscheint nur, was der Scan um 03:10 bereits rechnet, also höchstens die
  nächsten sechs Spiele je Game. Eine volle Abdeckung bräuchte ein Zeitfenster im Scan mit mehr PandaScore-Abrufen.
  Das ist ein eigener Owner-Entscheid.
- **Release:** App und Worker müssen gemeinsam auf diesem Stand laufen, bevor der Nachtlauf Morgen-Zeilen schreibt. Ein
  alter Lader verwirft ein Dokument mit Teamsport- oder E-Sport-Zeilen von morgen ganz. Das gilt auch für ein Zurückrollen
  bis zum nächsten Lauf.
- **Schritt 3b:** Tennis mit morgen (Scan-Kontingent). Schritt 2 (Doublebet- und 15K-Vorschau) bleibt offen.

## Release 20261111-2

- **Auftrag:** Owner „Ja, live stellen“ am 11.11.2026, PR #115 zusammen mit PR #114 (`555797b`).
- **Ausrollen:** No-Backup-Fast-forward `544c299` → `555797b` um 09:02 CET (`output/release-20261111-2/`).
  - Beide Teile laufen zusammen live. Die App und der Tageslauf tragen damit dieselbe Version, bevor ein Nachtlauf
    Morgen-Zeilen anderer Sportarten schreibt.
  - Ein zuvor vorbereitetes Release nur mit PR #114 (`release-20261111-1`) wurde nie ausgerollt.
- **Offline-Prüfung:** Lokal fand sie eine veraltete Kontrolle auf `_listed_day`. Diese wurde durch
  `listed_next_day_row` ersetzt. Danach ok, auch auf dem Server.
- **Server:** Health ok, Snapshots unverändert, keine Einheit geändert, kein Backup.
- **Live-Seite (`live-heute-und-morgen.jpg`):**
  - „Heute und morgen“ mit Türkei gegen Belgien am 12.11., Regler 70.
  - Am 11.11. noch keine Doublebet-Vorschau, weil morgen keine Wette alle Bedingungen erfüllte.
- **Erste Morgen-Zeilen für Eishockey, Basketball und E-Sport:** ab dem Nachtlauf am 12.11.2026 um 03:35.
