# Wettfinder zeigt immer heute und morgen (Schritt 1)

Stand 10.11.2026. Owner-Wunsch: „bei allen Tipps heute und morgen anschauen können … das bei allen Wetten und
Scannern machen“. Vereinbart ist ein Vorgehen in drei Schritten, das hier ist Schritt 1 („Ja, Schritt 1“).

## Änderung

- **Bisher:** Der Folgetag lief nur, wenn heute weniger als 30 Fussballspiele mit Auswahl gelistet waren
  (`NEXT_DAY_MIN_GAMES`, `2026-11-02-wettfinder-folgetag.md`).
- **Jetzt:** Der Tageslauf scannt den nächsten Zürcher Tag immer. Die Grenze `NEXT_DAY_MIN_GAMES` ist entfernt.
- **Alle übrigen Regeln des Folgetags bleiben:**
  - Morgen hat einen eigenen Zustand (`football_next_day`).
  - Für den Kontext bekommt morgen nur die Kontrollen, die heute übrig lässt. Heute geht also zuerst.
  - Morgen bleibt reine Modellauswahl in der Wettfinder-Liste: nie Tipp, 15K, Doublebet, Shadow, Evidenz oder
    Archiv vor dem eigenen Spieltag.
  - Ein Fehler beim Scan von morgen lässt heute unverändert.

## Kosten

- **Bisher:** API-Football verbrauchte vom 27.10. bis 9.11. zwischen 500 und 3700 Abrufe pro Tag, bei einer Grenze
  von 7500 (`api_budget.db`). An Tagen mit weniger als 30 Spielen lief der Folgetag schon bisher.
- **Neu dazu:** ein Scan von morgen auch an vollen Spieltagen, vor allem freitags bis sonntags. Geschätzt kostet das
  1000 bis 2000 Abrufe mehr pro Tag und passt in die Grenze.
- **Kein Wiederverwenden:** Jeder Spieltag wird zweimal geprüft, als Vorschau und am Spieltag frisch, weil sich
  Ergebnisse, Kontext und Quoten bis dahin ändern.
- **Volle Spieltage:** Heute braucht die drei Kontrollläufe zu je 20 Spielen oft selbst. Morgen zeigt dann vor
  allem die Spiele mit geprüftem Kontext aus seinem eigenen Scan.

## Prüfung

- **Neue Tests:**
  - `test_full_match_day_also_lists_the_next_day`: Bei 30 Spielen heute wird morgen gelistet, aber nicht als Tipp.
  - `test_next_day_has_no_game_threshold`.
  - Beide zuerst rot, dann grün.
- **Lokale Läufe:** 60 Testdateien rund um Tageslauf, Lader und Folgetag, 2112 Tests grün.
- **Fünf Fehlschläge, die schon vorher bestanden:** Sie scheitern auch auf dem unveränderten `main`.
  - `test_catalog_statistical_selection` (2×)
  - 15K-Oberfläche
  - Teamsport-Cache
  - Stufen-Reihenfolge

## Offen

- **Schritt 2:** Doublebet und 15K mit einer Morgen-Vorschau, nur zum Anschauen. Vormerken und Ticket gibt es weiter
  am Spieltag.
- **Schritt 3:** Tennis, Eishockey, E-Sport und RisikoBet mit morgen. Das Tennisquoten-Kontingent von The Odds API
  liegt bei 500 Abrufen im Monat, verbraucht werden bisher etwa 250.

## Release 20261110-4

- **Auftrag:** Owner „Ja, live stellen“, PR #112 gemergt (`544c299`).
- **Ausrollen:** No-Backup-Fast-forward `bae99ee` → `544c299` am 10.11.2026 um 21:04 CET (`output/release-20261110-4/`).
  - Offline-Importprüfung ok, auch die Prüfung „keine Grenze `NEXT_DAY_MIN_GAMES`“.
  - Health ok, Snapshots unverändert, keine Einheit geändert, kein Backup.
- **Wirkung:** ab dem Nachtlauf am 11.11.2026 um 03:35. In der Länderspielpause bis etwa 17.11. gibt es nur wenige
  Spiele.
