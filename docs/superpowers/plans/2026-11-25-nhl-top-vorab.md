# NHL-Siegertipps – Vorabvertrag für den Top-Vergleich

**Ziel:** NHL nicht pauschal ausschliessen, aber auch nicht wegen eines hohen
Modellwerts fördern. Gegenstück ist die modellunabhängige Zweierchance des
Buchmachers für **Sieg inklusive Verlängerung und Shootout**. Keine Regel
für europäisches Hockey, Doublebet, Quotenfilter oder Fußball geändert.

**Pilot (nur Abdeckung):** Spielbeginn 12.–24.11.2026 Zürich, nach dem
NHL-Audit vom 11.11.; fester Archivstichtag 25.11.2026 10:31 CET. Bereits
bekannte Teilresultate machen ihn zu einem Rückblick. Keine Auswertung von
Sieg/Verlust für die neue Hypothese und keine Freigabe aus diesem Fenster.

**Prospektiver Prüfzeitraum:** 26.11.2026–31.03.2027 Zürich, Öffnung einmalig
nach dem festgelegten Ergebnisstichtag 03.04.2027 00:00 Zürich. Bis dahin nur
Abdeckung lesen. Kein Retuning und kein weiterer Ergebnisblick auf eine
zu kleine Teilstichprobe. Bei unterdecktem Stichtag keine Freigabe; einen
späteren Prüfvertrag zuerst ohne Kenntnis der gepaarten Ergebnisse festlegen.

## Eingefrorene Auswahl

- Nur `sports-prematch-research-v1` / `team-sport-descriptive-v1`, native
  Quelle NHL, `H2H`, eindeutige Reihenfolge beider Teams. Die erste
  nachweisbar vollständige kausale Modellrevision eines Spiels wählen;
  Seiten müssen aus derselben Revision kommen und sich zu 1 ergänzen.
  Einmal pro Spiel die höhere Modellchance, keine spätere Ersetzung
  durch attraktivere Prognose oder Quote. Keine Gleichstände.
- Ursprünglicher `entry`-Beleg dieser eingefrorenen Revision, Zeitart
  `observed ≤ fetched ≤ decision < kickoff`, vorhandene 35/45-Minuten-Regel
  an der Entscheidung; native vollständige Preise beider Seiten desselben
  Buchmachers und desselben Abrufs, identische Partie, Periode und Anstoss.
  Nimm zuerst den frühesten gültigen Abruf und mittlere Quote der vorhandenen
  Bücher an diesem Abruf. 1,20-Untergrenze am Median, keine Auswahl nach
  späterem Preis. Je Buch proportional entmargen, dann Median der fairen
  Seitenwahrscheinlichkeiten. API-Hockey protokolliert die Abrufzeit als
  Beobachtungszeit: Das belegt einen empfangenen Marktstand, keinen
  eigenen Buchmacher-Zeitstempel, Ausführungspreis oder Closing-Preis.
- **Datenvoraussetzung:** mindestens 200 gepaarte entschiedene NHL-Spiele
  mit Modellfavorit ab 60 % und Absicherung in mindestens 50 entschiedenen
  Spielen ab 70,0 % (angezeigte Rundung). Mindestens 30 unterschiedliche
  Zürcher Spieltage im grossen und 15 im 70er-Kollektiv. Fehlende,
  mehrdeutige, widersprüchliche oder ungültige Abrechnungen zählen nicht.
- **Kennzahl:** Paarweiser Brier-Unterschied Markt minus Modell für dieselben
  Spiele in Anstossreihenfolge, bestehende einseitige 95-%-Untergrenze mit
  HAC. Beide Untergrenzen müssen positiv sein. Auch dann nur Empfehlung zur
  separaten Gleichstellung im selben Top-Vergleich, kein automatisches Flag,
  keine Aussage zur Rendite und keine Sportquote.

## Umsetzung und Abnahme

Bestehende Hash-, Zeit- und Native-Markt-Prüfer aus `selection_performance`
und `forecast_market_comparison` verwenden. Read-only-Modul und CLI für
Abdeckung / eine feste Zukunftsöffnung, Tests für erste Revision, fehlende
oder falsch zugeordnete Gegenquote, blindes Abbrechen bei zu wenigen Spielen
und gepaarte Statistik. Pilot gegen VPS-Archiv im netzwerkisolierten Prozess
ohne neue Sportabrufe, Datenkopie, Änderung der laufenden App oder Backups.
