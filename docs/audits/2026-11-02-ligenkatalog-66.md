# Ligenkatalog: 14 Ligen dazu (66 statt 52)

Datum: 02.11.2026. Owner-Wunsch im Chat: Der Wettfinder soll mindestens 30 Spiele zeigen. Daily3 bleibt bei 3
Tipps, für die 15K-Liste reichen bis zu 5 am Tag. Owner-Entscheide „Ja, Ligen prüfen“ und „Ligen + Folgetag“. Der
Folgetag kommt in einem eigenen PR.

## Befund

Abfrage mit 8 Hintergrundabrufen über den Budgetzähler (7 × `/fixtures?date` für 2.–8.11., 1 × `/leagues?current=true`).
Skript und Rohdaten liegen ausserhalb von Git unter `output/ligen-20261102/`.

| | Mo | Di | Mi | Do | Fr | Sa | So |
|---|---|---|---|---|---|---|---|
| Spiele weltweit | 241 | 225 | 240 | 136 | 319 | 1437 | 1168 |
| in den 52 Katalogligen | 42 | 30 | 20 | 40 | 39 | 127 | 158 |
| davon UEFA | 0 | 9 | 10 | 35 | 0 | 0 | 0 |
| mit den 14 neuen Ligen | 54 | 40 | 29 | 49 | 67 | 182 | 193 |

Der Wettfinder zeigt rund 60–75 % der gefundenen Spiele. Am 1.11. waren es 68 von 114, am 2.11. 28 von 38
Fussballspielen. Viele Sommerligen im Katalog enden bis Dezember.

## Neue Ligen

Alle 14 Ligen haben beim Anbieter Aufstellungen und Quoten, alle ausser der Challenge League auch Statistiken. Die
Saison läuft von Juli/August bis zum Frühling, der Saisonwechsel im Juli passt (`rollover_month=7`).

| ID | Code | Liga |
|---|---|---|
| 141 | ESP2 | Spanien: Segunda División |
| 136 | ITA2 | Italien: Serie B |
| 62 | FRA2 | Frankreich: Ligue 2 |
| 80 | GER3 | Deutschland: 3. Liga |
| 204 | TUR2 | Türkei: 1. Lig |
| 95 | POR2 | Portugal: Segunda Liga |
| 145 | BEL2 | Belgien: Challenger Pro League |
| 219 | AUT2 | Österreich: 2. Liga |
| 208 | SUI2 | Schweiz: Challenge League |
| 307 | KSA1 | Saudi-Arabien: Pro League |
| 383 | ISR1 | Israel: Ligat Ha'al |
| 318 | CYP1 | Zypern: 1. Division |
| 172 | BUL1 | Bulgarien: First League |
| 288 | RSA1 | Südafrika: Premier Soccer League |

Japans J1 und J2 bleiben draussen. Seit dem Wechsel auf den Herbst-Frühling-Rhythmus nummeriert der Anbieter die
Saison uneinheitlich (J1 2027, J2 2026 für dieselbe Spielzeit), `season_utils` bildet das nicht ab.

## Wirkung

- Wettfinder, Shadow und Rotkarten-Monitor übernehmen den Katalog ohne weitere Änderung. Die Discovery fragt je Liga
  einmal ab, also 14 Spielplanabrufe mehr je Scan. Die Historie für das Modell kommt aus `fixtures` mit Status FT,
  ein bis zwei Abrufe je Liga. Ecken- und Kartenhistorie von Football-Data gibt es nur für die bisherigen
  europäischen Ligen; für die neuen Ligen fallen diese Märkte am Walk-forward-Filter durch.
- Die FDR-Familie über Ligen × Märkte wächst von 52 auf 66 Ligen. Ligen ohne gültigen Test zählen mit p = 1
  (`cross_league_fdr.py`). Top-Tipps und die 15K-Liste werden dadurch etwas strenger.
- Der Kontext ist auf höchstens rund 80 Spiele je Tageslauf begrenzt (`MAX_CONTEXT_FIXTURES` plus drei Nachläufe zu
  je 20). Am Wochenende bleiben deshalb mehr Spiele ohne geprüften Kontext und damit unsichtbar. Unter der Woche
  reicht die Grenze.
- Weil sich die Liste der Discovery-Ligen ändert, wird nach dem Release ein neuer Tagesscan fällig
  (`discovery_league_ids`).
- API: Am Wochenende liegt der Verbrauch heute bei 2300–2400 von 7500 Abrufen am Tag.
