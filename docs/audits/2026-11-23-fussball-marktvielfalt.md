# Warum Über/Unter bei den Haupttipps dominiert

Archiv der automatischen Fußballansicht für Spielbeginne 20.–22.11.2026
(Zürich), lesend ausgewertet am 23.11. um 07:29 CET. Für Haupttipps zählen
die Belege der ersten tatsächlich gerenderten Hauptkarte je Partie; am
20.11. setzt die Erfassung erst nach der Veröffentlichung ein. Katalogzeilen
belegen das verfügbare Angebot vor den persönlichen Seiteneinstellungen,
nicht, dass sie tatsächlich alle auf dem Bildschirm standen.

| Markt | Katalog, 903 Auswahlen | Erste Hauptkarten, 87 Spiele |
|---|---:|---:|
| Teamtore Über/Unter | 302 | 59 |
| Gesamttore Über/Unter | 38 | 9 |
| Sieg (Heim/Auswärts) | 107 | 1 |
| Unentschieden | 7 | 0 |
| Doppelte Chance | 62 | 13 |
| Ecken | 87 | 5 |
| Torbereiche / Multigoal | 176 | 0 |
| Ergebnis-/Tor- und Oder-Kombis | 116 | 0 |
| Beide treffen | 8 | 0 |

Reines Tore-Über/Unter: **340/903 (37,7 %) im Katalog, aber 68/87 (78,2 %) als
Haupttipp.** Aufteilung: 20.11. 14/14, 21.11. 42/57, 22.11. 12/16. Das sind
Bestandsanteile der untersuchten drei Tage, keine Zufallsstichprobe und kein
Intervall für zukünftige Tage; Märkte eines Spiels sind nicht unabhängig.

## Was verdrängt die anderen Märkte?

1. **Standardeinstellung 70 %.** Im Standardkatalog des Sonntags überstanden
   29 von 145 Fußballauswahlen die gerundete Anzeigegrenze: 22 Tore-Über/Unter,
   sechs Doppelte Chancen und eine Eckenauswahl. Keiner der 15 Siegtipps;
   der höchste lag bei 59,24 %. Ein 1X2-Sieg deckt nur einen der drei
   Spielausgänge ab; ein breites „unter 4,5“ schließt viele Spielstände ein.
   Höheres Modell-p allein sagt nichts über den passenden Preis oder die Güte
   eines Markts.
2. **Die oberste Karte nimmt den Markt mit der höchsten Modellchance.**
   Die Auswahl vergleicht zulässige Märkte derselben Modellrevision
   (`forecast_selection.select_event_leads`). Sie gibt selteneren Wettarten
   keine eigene Hauptposition. Probe mit den ohnehin vorhandenen, noch nicht
   begonnenen Fußballspielen am 23.11. um 07:32 CET: Ohne den Prozentfilter
   wären 13 1X2-Sieger und 10 Eckenmärkte sichtbar; 14 von 19 ersten Märkten
   wären weiterhin Teamtor-Über/Unter. Das war ein Lesetest, keine Änderung.
3. **Ecken benötigen einen eigenen, belegten Datensatz.** Das Modell verwendet
   historische Eckenzahlen, mindestens 24 Ligaspiele, mindestens fünf
   spielortbezogene Spiele sowie fünf Formspiele beider Teams. Torergebnisse
   sind dafür kein Ersatz. Auf der Montagstagesdatei waren 11 Eckenmärkte
   nach Zusammenführung konsistent; vor dem Preisfilter lagen nur zwei
   bei mindestens 70 %, danach einer. Das Modell enthält 96 Fußball-
   Marktdefinitionen; eine Definition ist noch kein für jede Partie geprüfter
   Markt.
4. **Die 1,20-Regel erklärt nicht das Fehlen der Sieger.** Montag:
   Von 153 konsistenten Fußball-Katalogmärkten waren 71 bei mindestens
   70 %; davon bestand bei 29 der Preisfilter. Unter den 42 ausgeschiedenen
   Märkten waren 26 reine Torlinien und 11 Torbereiche; kein Siegtipp musste
   erst an der Preisregel scheitern, um unter 70 % zu liegen.

Geprüfte Stellen: `app.py` (Archiv vor Filter/Pagination), `wettfinder_surface.py`
(Öffentlichkeits- und Prozentfilter), `forecast_selection.py` (Hauptkarte),
`challenge_engine.py` (Marktdefinitionen und Prognose-/Validierungsgrenzen),
`market_consensus.py` (öffentliche Preisregel). Archivquellen:
`wettfinder_automatic` und `wettfinder_automatic_event_leads`, getrennt von
den automatisch angebotenen Standardbelegen. Nur erstes belegtes Vorkommen
je Tag, Partie und Markt beziehungsweise erste Hauptkarte je Partie.
Die Analyse ändert keine Hauptkarten-, Prognose- oder Preisregel.

## Unterschätzt das Modell regelmäßig drei oder mehr Teamtore?

Gegenprobe vor Sonntag: 08.–21.11., aktuelle Formstärke-Modellversion, erste
vor Anpfiff belegte Auswahl „Unter 2,5 Teamtore“. In den **89 exakt gebundenen
Fällen** (83 Spiele, sieben Spieltage) erzielten Teams 24-mal mindestens drei
Tore, bei 24,13 erwarteten Fällen (26,97 % beobachtet vs. 27,11 % erwartet).
Differenz −0,15 Prozentpunkte; exploratives 95-%-Intervall mit Tagen als
Blöcken [−9,2; +11,7] Prozentpunkte. 66 weitere Veröffentlichungen hatten
keinen exakt gebundenen Modellbeleg; 47 der 89 Fälle stammen vom 08.11.
Der breitere überlappende Modellbestand ergab 55 statt 68,63 erwartete
Fälle (379 entschieden, vier offen; 252 Spiele, zwölf Tage). Das stützt
keine generelle Unterschätzung; weder der Archivvergleich noch der einzelne
Sonntag rechtfertigt eine Änderung an Modell oder Grenzwert.

## Öffentliche Tageskombis

Die Produktregel für **neu** vorgeschlagene öffentliche Kombis trennt
Spielidentitäten samt Alias über alle Scheine und begrenzt je Schein eine
Marktgruppe auf 2/2/2/3 Positionen (Größen 3/4/5/6).
Das Chancenprodukt rangiert weiterhin die sportlich zulässigen Kandidaten;
der Balken bleibt der Durchschnitt der Einzelchancen. Alte und am selben
Tag bereits eingetragene Scheine werden nie umgeschrieben. Ist kein gültiger
Schein in voller Größe verfügbar, bleibt die Größe frei. Keine neue
Anbieterabfrage, kein Backup, keine Datenmigration.
Das verhindert Überlappung, belegt aber keine höhere Trefferrate oder Rendite.
