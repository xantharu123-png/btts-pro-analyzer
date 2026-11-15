# NHL-Spätspiele: Spiele um 04:00 Uhr bekommen wieder eine Prognose

Stand 15.11.2026. Owner „Ja, untersuchen“ (mit einem API-Abruf) und danach „Ja, reparieren“.

## Anlass

Am 15.11. um 10:30 waren von 121 Tipps mit Anstoss am 14.11. noch 13 offen. Alle gehörten zu drei Spielen, für die
der Lauf des Spieltags keine Prognose hatte:

- **Rotherham gegen Crawley Town und Walsall gegen Barnet** (League Two, 14.11. um 16:00, je 6 Tipps vom 13.11.
  um 18:39). Ein API-Football-Abruf mit Owner-OK (`fixtures?ids=1563858-1563862`, über
  `api_budget.api_football_get`, Label „owner probe fixture status 1563858-1563862“) zeigt beide Spiele als
  verschoben (`PST`). Der Spieltagslauf hat sie also zu Recht ausgelassen. Die Tipps bleiben offen, bis das
  Nachholspiel gespielt ist. Das ist kein Fehler.
- **Vegas gegen Nashville** (NHL, 14.11. um 04:00, 1 Tipp vom 13.11. um 18:39). Dieses Spiel hatte in keinem Lauf
  eine Prognose. Das ist eine Lücke.

## Befund

Nur gelesen, auf dem Server:

- **NHL-Tipps vom 01. bis 15.11. mit Anstoss zwischen 02:30 und 06:00 Zürcher Zeit:** 11 Spiele. 10 haben eine
  Prognose, jede aus dem Lauf des Vortags. Vegas gegen Nashville hat keine.
- **RisikoBet-Nachtläufe vom 31.10. bis 15.11.:** Ein Spiel um 04:00 am Folgetag hat nur der Lauf vom 04.11.
  modelliert, der um 04:03 endete (2 Spiele). Seit dem 06.11. enden die Läufe zwischen 03:42 und 03:49. Seither
  hat kein Lauf ein NHL-Spiel um 04:00 modelliert.
- Vegas gegen Nashville steht in keinem RisikoBet-Lauf, weder am 13.11. (03:43 bis 03:45) noch am 14.11.
  (03:44 bis 03:47).

## Ursache

1. `team_sport_forecasts.automatic_team_sport_day` zählt ein NHL-Spiel des Folgetags zum laufenden Tag, wenn es
   höchstens 24 Stunden nach der Laufzeit beginnt. Beim Lauf vom 13.11. um 03:45 endete diese Spanne am 14.11. um
   03:45. Vegas gegen Nashville um 04:00 lag 15 Minuten dahinter.
2. Der Lauf des Spieltags sieht das Spiel nicht mehr. `scanners/basketball_scanner.get_upcoming_nhl_games` holt den
   NHL-Wochenplan ab dem Zieldatum, und die NHL führt das Spiel unter dem US-Datum des Vortags (13.11., 19:00 Uhr
   Ortszeit Las Vegas).
3. Der Quotenlauf vom 13.11. um 18:39 rechnet die 24 Stunden ab seiner eigenen Uhrzeit. Deshalb erschien trotzdem
   ein Tipp. Ohne Prognose kann er nie abgerechnet werden.

Seit die Nachtläufe vor 04:00 enden, fallen damit NHL-Heimspiele an der Westküste (19:00 Uhr Ortszeit, 04:00 Uhr
Zürich) aus Modell, Liste, Evidenz und Abrechnung. Das gilt für jedes NHL-Spiel, das später als 24 Stunden nach dem
Nachtlauf beginnt.

## Änderung

`team_sport_forecasts.py`:

- `NHL_NIGHT_UNTIL = (6, 0)` und `_nhl_horizon`: Der NHL-Horizont ist 24 Stunden ab der Laufzeit, mindestens aber
  bis 06:00 Uhr Zürcher Zeit am Folgetag.
- `automatic_team_sport_day` nutzt diesen Horizont. Alle Aufrufer folgen ohne eigene Änderung: die RisikoBet-Quelle
  des Nachtlaufs, Katalog und Rangliste, der Folgetag für Eishockey, die Lader in `ev_signal_sources`.

**Unverändert:**

- Ab 06:00 Uhr gilt wie bisher die volle 24-Stunden-Spanne. Die Spanne der Quotenläufe am Tag ändert sich nicht.
- Die Ausnahme gilt weiter nur für native NHL-Spiele. API-Hockey, Basketball und alle anderen Sportarten bleiben beim
  Kalendertag.
- Der NHL-Wochenplan reicht schon heute bis zum Folgetag (`nhl_end`). Es braucht keinen zusätzlichen Abruf des
  Spielplans.

**Warum 06:00:** Die spätesten NHL-Anspiele liegen in der Regel um 19:00 oder 19:30 Uhr an der Westküste, also um
04:00 oder 04:30 Uhr Zürcher Zeit, auch in der Sommerzeit. 06:00 lässt Reserve. Das nächste NHL-Spiel des folgenden US-Tags beginnt frühestens am
Nachmittag Zürcher Zeit.

## Folgen

- Späte NHL-Spiele gehören wieder zum Tag davor, wie die Spiele um 01:00 bis 03:30. Sie erscheinen in der Liste und
  im Doublebet von heute, werden als Evidenz gespeichert und abgerechnet.
- Der Folgetag für Eishockey zeigt diese Spiele nicht mehr als „morgen“, weil sie jetzt zum laufenden Tag gehören.
  So wird kein Spiel doppelt gelistet.
- **Mehr Team-Quoten:** Für die zusätzlichen NHL-Spiele holt der Quotenlauf Quoten bei API-Hockey
  (`team_sport_prices`, nach Budget). API-Hockey lag am 10. bis 12.11. bei 16, 49 und 83 Abrufen am Tag. Nach dem
  Release beobachten.

## Prüfung

- **Tests** in `tests/test_nhl_overnight_window.py`:
  - Lauf um 03:35: Ein Spiel 24 h + 1 s später gehört dazu, ebenso 05:59:59 und 06:00 am Folgetag. 06:00:01 gehört
    nicht dazu.
  - Lauf um 12:00: Es gilt weiter die 24-Stunden-Grenze.
  - Sommer- und Winterzeitwechsel: Die Nachtgrenze ist 06:00 Ortszeit, die Tagesgrenze 24 h.
  - Ende-zu-Ende vom RisikoBet-Lauf über Katalog, Evidenz und Lader für ein Spiel um 04:00 am Folgetag (der Fall
    vom 14.11.).
- `tests/test_wettfinder_next_day_other_sports.py`: Ein Spiel um 04:30 am Folgetag gehört zum laufenden Tag, eines um
  06:00:01 zum Folgetag.
- **Trockenlauf auf dem Server** (nur gelesen, Branch-Modul unter anderem Namen geladen):
  - Vegas gegen Nashville mit der Laufzeit vom 13.11. (03:45:30): alte Regel nicht heute, neue Regel heute.
  - Tagesdokument vom 15.11.: keine NHL-Zeile wechselt den Tag.
  - Horizont um 03:35, 03:45 und 04:10 bis 06:00 am Folgetag; um 06:15, 12:15 und 21:15 unverändert 24 h.

## Grenzen

- **Wirkt erst nach dem Release.** Der offene Tipp auf Vegas gegen Nashville bleibt offen. Nachträglich darf keine
  Prognose entstehen.
- Die verschobenen Spiele Rotherham gegen Crawley Town und Walsall gegen Barnet bleiben offen, bis sie nachgeholt
  sind. Bekommt das Nachholspiel andere Märkte, bleiben einzelne Tipps auch danach offen, wie ein Tipp bei
  Millonarios gegen Alianza Valledupar vom 12.11.

## Zurücknehmen

In `team_sport_forecasts.automatic_team_sport_day` wieder `starts_at <= now + timedelta(hours=24)` prüfen und
`NHL_NIGHT_UNTIL` mit `_nhl_horizon` entfernen. Gespeicherte Prognosen bleiben gültig.

## Release 20261115-1

Owner „Ja, live stellen“ am 15.11.2026.

- **Merge:** PR #127 um 14:34 CET, `origin/main` = `d19e75549703b95d31f3d9c5594a8872aaf9f383`. Die CI war grün
  (ruff und schnelle Teilmenge; Lader, Publikation, Daily3 und 15K unter `floor` und `gate`).
- **Dateien:** 11, alle von `7efa8f5` bis `d19e755`. Code: `team_sport_forecasts.py`, dazu nur Kommentare in
  `ev_signal_sources.py` und `wettfinder_automation.py`; sonst Tests und Doku (darunter das Protokoll PR #126).
  Keine Einheit, kein `.sh`, keine Requirements.
- **Generator:** `output/release-20261115-1/gen_deploy53.py`, abgeleitet von `gen_deploy52.py` über `make_gen.py`.
  Neu: `team_sport_forecasts` in der Importliste; Asserts `NHL_NIGHT_UNTIL == (6, 0)`, `_nhl_horizon` vorhanden und
  in `automatic_team_sport_day` benutzt; Vegas gegen Nashville mit der Laufzeit vom 13.11. gehört zum laufenden Tag,
  ein Spiel um 06:00:01 nicht.
- **Offline-Prüfung lokal** gegen einen Worktree von `d19e755`: `OFFLINE_RELEASE_IMPORTS=ok`.
- **Hochladen:** sha256 auf dem Server gleich (`deploy-20261115-1.sh` `9b71f4e2…`, `run_release-20261115-1.sh`
  `4f63bcce…`).
- **Ausrollen:** Fenster um 14:36:10 (Abstand zum nächsten Shadow-Lauf 350 s). Ergebnis `HEAD=d19e755…`,
  `APP_PID=1625050->1638757`, `NO_NEW_BACKUP=yes`, `UNITS_UNCHANGED=yes`, `DEPLOY_EXIT=0`. Log
  `output/release-20261115-1/deploy-01.log`.
- **Danach (14:36):** Health lokal und öffentlich `ok`, App und Caddy aktiv, alle 7 Timer aktiv, keine neue
  fehlgeschlagene Einheit (die 8 alten vom September bleiben), die Live-Seite lädt mit Inhalt.
- **Offen:** Der Nachtlauf am 16.11. um 03:35 ist der erste mit der neuen Grenze. Ein NHL-Spiel des 17.11. vor
  06:00 Uhr gehört dann zum 16.11. Prüfen, ob es Prognose und später ein Ergebnis bekommt, und die API-Hockey-Abrufe
  je Tag beobachten.
