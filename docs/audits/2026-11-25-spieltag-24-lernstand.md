# BetBoy: Referenz-Spieltag 24.11.2026

Produktionsbasis `9d8f945` (Live-Wechsel erst am 25.11. um 00:02:14 CET).
Spielbeginn am **24.11. in Europe/Zurich**; für Live gilt stattdessen der
Anzeigezeitpunkt. Die erste Nachtprobe war um ca. 00:27 CET, nach den
regulären Abrechnungen am Morgen aktualisiert (ca. 08:02–08:07 CET).
Nur die vorhandenen Archive gelesen, keine neue Anbieterabfrage.

| Fläche / Kohorte | Treffer / entschieden | Abdeckung und Abgrenzung |
| --- | ---: | --- |
| Wettfinder-Standard: Fußball-Haupttipps | 15/21 (71,4 %) | 6 weitere Fußballspiele ohne eigenständigen Haupttipp-Beleg; Ø Modell 76,1 %, ungefähr 95-%-Wilson-Intervall 50,0–86,2 % |
| Wettfinder „Automatisch“: Fußball-Haupttipps | 15/19 (78,9 %) | Separate Archivfläche mit Überschneidung; nicht zur Standardfläche addieren |
| Standard: Haupttipps alle Sportarten | 18/24 (75,0 %) | Fußball 15/21, Eishockey 2/2, E-Sport 1/1; bei 18 der 42 Spiele ist die Hauptkarte nicht belegbar |
| Standard: alle verfügbaren Märkte | 95/160 (59,4 %) | Fußball 89/147, E-Sport 4/4, Basketball 1/5, Eishockey 1/4; 40 Spiele, zusammenhängende Märkte, kein gepooltes Bernoulli-Intervall |
| Doublebet | 1/1 | Como unter 2,5 eigene Tore gegen AEK. Archivquote 2,10 war alt, keine nachgewiesene Ausführung. |
| Öffentliche Kombis | 0/3 Scheine | 3er 2/3 (Palmeiras X2 verloren); 4er 3/4 (Aston Villa X2); 5er 4/5 (Feyenoord über 0,5 eigene Tore). PARIVISION schlug GamerLegion 2:0. 9/12 Beine aus 12 Spielen; kein 6er, keine bestätigte gemeinsame Quote. |
| Live nach alter Auswahl | 15/17 (88,2 %) | Alles „Noch ein Tor“; 12 Anzeigen bis Minute 5, davon 11 Treffer. 14,48 erwartete Treffer für 17 Belege (Ø Modell 85,2 %); kein nachweisbarer Zusatznutzen. |
| RisikoBet / 15K | nicht belegbar | Kein geeigneter öffentlicher Publikationsbeleg für den 24.11.; interne Kandidaten ersetzen ihn nicht. |

Bei Live rechnete `betboy-redcard-settlement` am 25.11. um 06:05 CET alle 17
mit Exit 0 und ohne Anbieterfehler ab. Der Zwischenstand „6 per Torfolge
bestätigt, 11 unbewiesen“ ist damit überholt. Verloren: Vicenza Virtus–Carrarese
(1H 45+1′, 0:1 bis Abpfiff) und Crawley–Barnet (2′, 0:0 bis Abpfiff).
Der alte „Noch ein Tor“-Tipp bei Cardiff–Preston traf (Endstand 0:4); bei
Anzeige in Minute 2 brachte Live-xG trotzdem keinen Modellzugewinn. Für die neue Regel
lagen am 25.11. um 08:02 CET keine gespeicherten Echtbelege vor.

## Was bleibt und was geprüft wird

- **Unveränderte Basis.** Die belegten Standard-Fußball-Haupttipps vom
  21.–23.11. trafen 64/80 (80,0 %, ein weiterer belegter Tipp offen); am
  24.11. 15/21. Ecken: zuvor 5/6, jetzt 4/4, zusammen 9/10. Doppelte Chance
  und Ergebnis: zuvor 13/16 entschieden, jetzt 1/4. Unter-/Über-Tore am
  24.11. 7/9 und 3/4. Nicht nach einem Spieltag umgewichten. Künftige
  reguläre Tage mit vollständig getrennten Kohorten und bei Ecken auch
  nach Liga und genauer Linie prüfen; der 24.11. ist eine Diagnose, kein
  für die Modellauswahl wiederverwendeter Testtag.
- **Preisabdeckung vor Aussagen zur Rendite.** 0/21 entschiedene
  Fußball-Standardhaupttipps hatten eine frische Archivquote. Bei allen
  21 war der HTTP-Abruf höchstens vier Minuten alt (Median 3,87 min), der
  Anbieterstempel dagegen 123–167 min (Median 158,25 min). Beispiel
  Charlton–Lincoln: Anbieter 01:14:16, Abruf 03:43:43, Veröffentlichung
  03:47:35 CET. Im regulären 25.11.-Tageslauf wieder 12/12 alt (Median
  Abruf 3,37 min; Anbieter 138,74 min). Die strikten 35/45 Minuten bleiben
  erhalten. `floor`-Anzeige / `forecast_quotes.executable` ist kein
  Nachweis eines frischen Abschlussangebots. Im 24.11.-Standard waren nur
  3/24 entschiedene Haupttipps mit frischem Preis belegt, alle ausserhalb
  Fußball. Eine Tagesgesamtrendite oder Echtgeldbilanz daraus wäre falsch.
- **Konkrete Lücke für einen separaten Preis-Patch.** Beim regulären
  06:15-Lauf am 25.11. wurden alle zwölf Partien wegen anderer Märkte
  erfolgreich abgerufen, aber ihre Hauptmärkte waren nach dem 03:39-Abruf
  noch innerhalb der 165-Minuten-Marktsperre und wurden nicht erneut
  ausgewertet. Die bestehenden Abrufe liefern ganze Fixture-Seiten. Für
  bereits ausgewählte Fixture-IDs könnten exakt passende weitere Märkte
  aus derselben Antwort geprüft werden, ohne zusätzliche Requests und ohne
  die Sperre für neue Abrufe zu verändern. Ob diesmal wirklich frische
  Preise geliefert wurden, ist ohne archivierte Rohantwort nicht beweisbar.
  Spätere Preise dürfen Originalbelege nicht ersetzen.
- **Vorschau ist keine Tagesprognose.** Die Automatik hat 151 von 186
  Katalogzeilen ohne exakte Zuordnung, darunter fünf Basketball-Vorschauen
  vom Vorabend mit einem anderen Snapshot als am 24.11. Nicht rückwirkend
  mit passendem späteren Endstand oder neuer Modellrevision auffüllen.

## Wiederholbarer Archivvergleich

```bash
python -B scripts/selection_performance_report.py \
  --db runtime_state/forecast_evidence.db --history-db runtime_state/consumer_tips.db \
  --from-day 2026-11-21 --through-day 2026-11-24 \
  --as-of 2026-11-25T08:07:00+01:00 --market-review
```

Alternative Ansicht ausdrücklich mit `--surface wettfinder_automatic`
auswerten. Das Script prüft nur abgeschlossene Zürcher Tage und liefert je
Tag und aggregiert Treffer, erwartete Treffer, nicht belegte Hauptkarten,
Quotenstatus und veraltete Anbieter-/Abrufstempel je Wettart. Die optionale
Rendite ist eine hypothetische Gleich-Einsatz-Rechnung ausschliesslich für
entschiedene Fälle mit frischem Preis bei ihrer ursprünglichen Publikation.
Kein neuer Job, kein Browseraufruf, keine Kundenoberfläche und keine Änderung
an Modell, Quotenprüfung oder Spielauswahl.

Abnahme: 283 Archiv-, Evidenz- und Publikationstests bestanden. Der geprüfte
Report wurde unverändert im Speicher eines netzwerkisolierten VPS-Prozesses
auf dem originalen Archiv ausgeführt: 18/24 Haupttipps, 95/160 Katalogtipps,
21 durch den Anbieterstempel veraltete Fußballpreise und keine
Integritätsfehler im Standardarchiv am gefrorenen Stichtag. Der separate
Vollsuite-Versuch stoppt nach 99 bestandenen Tests am bereits auf der
Produktionsbasis belegten Eishockey-Preistest
`test_native_conflicting_role_ids_fail_before_any_request`.
