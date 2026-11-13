# Fallenfilter: vorab festgelegter Test auf neuen Tipps

Stand 09.11.2026. Owner-Auftrag „Ja, festlegen“ vom selben Tag. Dieses Dokument legt die Regel, die Daten und die
Bedingungen fest, **bevor** ein einziger Tipp aus dem Messfenster abgerechnet ist. Danach wird nichts mehr verändert.

Am Code der App ändert sich nichts. Gemessen wird nur, mit `scripts/trap_filter_measurement.py`: Das Skript liest die
Daten, ruft nichts ab und schreibt nichts.

**Nachtrag vom 13.11.2026:** Die Zuordnung der Einstiegsquote ist berichtigt, bevor ein einziger Tipp mit Quote
gezählt war. Siehe „Nachtrag 13.11.2026“ am Ende. Der Text vom 09.11. steht unverändert da.

## Anlass

Auswertung vom 09.11.2026 auf den veröffentlichten Tipps vom 07.10. bis 09.11.2026. Gezählt wurde jede Auswahl einmal,
mit der ersten gespeicherten Einstiegsquote und dem Ergebnis Gewinn oder Verlust. Die Einstiegsquote stammt fast immer
von api-football:11 und wurde im Median 16 Stunden vor Anstoss gespeichert.

| Fall | Tipps | Treffer | Modell versprach | Quote sagte |
|---|---:|---:|---:|---:|
| Modell ≥ 5 Punkte unter der Quote | 1324 | 68,1 % | 60,1 % | 71,7 % |
| etwa gleich (± 5) | 1193 | 56,4 % | 62,9 % | 63,5 % |
| **Modell ≥ 5 Punkte über der Quote** | **566** | **47,3 %** | **61,3 %** | **49,6 %** |

- Wo das Modell deutlich mehr sieht als der Buchmacher, behält der Buchmacher recht. Diese Tipps heissen hier „Fallen“.
- Ursache bleibt offen. Getestet und widerlegt sind Wetter (`2026-11-07-wetter-schritt-5.md`), Ausfälle und Ruhetage
  (`2026-11-05-ausfaelle-ruhetage-schritt-3.md`) und die Startelf (`2026-11-09-aufstellungen-widerlegt.md`).
- Die Schwelle von 5 Punkten stammt aus genau dieser Auswertung. Deshalb gilt die Regel erst als belegt, wenn sie auf
  neuen Tipps besteht.

## Regel

- **Falle:** Modellwahrscheinlichkeit des Tipps minus 1 / Einstiegsquote ist mindestens 0,05.
  - Modellwahrscheinlichkeit: das Feld `probability` des veröffentlichten Tipps.
  - Einstiegsquote: die früheste gespeicherte Quote mit `kind = entry` in `forecast_quotes` zur `forecast_id` des
    Tipps, von welchem Buchmacher auch immer. Es ist die rohe Quote, ohne Margenbereinigung.
    (Seit 13.11.2026 gilt statt „zur `forecast_id` des Tipps“ die Zuordnung aus dem Nachtrag am Ende.)
- **Der Filter wählt keine Tipps nach Quote aus.** Er nimmt nur Tipps heraus, bei denen der Buchmacher stark
  widerspricht, so wie die 1,20-Grenze im Hintergrund. Reihenfolge und Modellwahrscheinlichkeit bleiben unverändert.
- Tipps ohne gespeicherte Einstiegsquote kann der Filter nicht prüfen. Sie zählen nicht zum Test und werden nur
  berichtet.

## Daten

- **Tipps:** jede Auswahl (Ereignis, Markt, Auswahl) aus `consumer_tips.db`, deren **erste** Veröffentlichung auf
  irgendeiner Liste im Fenster liegt. Massgeblich sind die Angaben dieser ersten Veröffentlichung.
- **Fenster:** 10.11.2026 00:00 UTC bis vor 28.11.2026 00:00 UTC.
- **Ergebnis:** das neueste Ergebnis in `forecast_results`. Es zählen nur Gewinn und Verlust; ungültige und offene
  Tipps fallen weg.
- **Auswertung:** am 30.11.2026, zusammen mit der Formstärke-Messung.
- **Kein Blick vorher:** Bis zur Auswertung läuft das Skript nur mit `--count-only`. Diese Ausgabe zeigt Anzahlen,
  aber keine Trefferquoten.

## Bedingungen

Gerechnet werden nur Tipps mit Einstiegsquote. Der Filter gilt als **bestanden**, wenn alle drei Punkte erfüllt sind:

1. **Genug Daten:** mindestens 150 abgerechnete Fallen.
2. **A, Fallen treffen seltener als versprochen:** z = (Summe Modellwahrscheinlichkeiten − Treffer) /
   √(Summe p · (1 − p)) über die Fallen, mit z ≥ 1,645 (einseitig, 5 %).
3. **B, Fallen treffen seltener als die übrigen Tipps:** Zwei-Anteile-Test, übrige Tipps mit Quote gegen Fallen,
   mit z ≥ 1,645 (einseitig, 5 %).

**Zu wenig Daten:** Liegen am 30.11. weniger als 150 Fallen vor, wird das Fenster um je 7 Tage verlängert. Geprüft wird
dann wieder nur mit `--count-only`, längstens bis Fensterende 26.12.2026. Sind es auch dann weniger als 150, ist der
Test unentschieden und der Filter kommt nicht.

**Zusätzlich berichtet, ohne Einfluss auf das Ergebnis:**

- Trefferquote aller Tipps mit und ohne Filter, auch mit den Tipps ohne Quote.
- Wie viele Tipps pro Tag wegfallen.
- „Quote sagt“ bei den Fallen.
- Fallen nach Sport und Liste.

## Folgen

- **Bestanden:** Der Fallenfilter ist Kandidat. Er kommt nur mit Owner-OK in einem eigenen PR, als Sperre im
  Hintergrund. Die App zeigt weiterhin keine Buchmacherquoten. Wie die Sperre Tipps behandelt, deren Quote erst nach der
  Veröffentlichung kommt, regelt dieser PR, so wie bei der 1,20-Grenze („rücken nach jedem Quotenlauf nach“).
- **Nicht bestanden:** Der Filter ist verworfen.
- **Kein Nachjustieren:** Es kommt keine Variante, egal ob der Test besteht oder nicht. Ausgeschlossen sind zum
  Beispiel eine andere Schwelle (3, 4, 6, 8 Punkte), Margenbereinigung, nur bestimmte Märkte, Ligen oder Listen,
  Schlussquote statt Einstiegsquote oder ein anderes Fenster.
- **Modell geändert:** Ändert sich das Modell oder die Auswahl der Tipps im Fenster, nennt der Bericht das. Die Tipps
  zählen trotzdem, denn der Filter wirkt auf das, was die App veröffentlicht.

## Was der Filter bringen kann und was nicht

Rückblick auf die bekannten Tipps vom 07.10. bis 09.11.2026, mit dem Skript nachgerechnet
(`--since 2026-10-07 --until 2026-11-09T12:00`):

| | Tipps | Treffer |
|---|---:|---:|
| alle abgerechneten Tipps | 4668 | 58,7 % |
| davon mit Einstiegsquote | 3083 | 59,8 % |
| Fallen | 566 | 47,3 % |
| alle ohne Fallen | 4102 | 60,2 % |
| mit Quote, ohne Fallen | 2517 | 62,5 % |
| ohne Einstiegsquote | 1585 | 56,6 % |

- Etwa 17 Tipps pro Tag fielen weg. Die Trefferquote der App steigt um rund 1,5 Punkte, bei Tipps mit Quote um rund
  3 Punkte.
- **70 % erreicht der Filter nicht.**
- Ein Drittel der Tipps hat keine gespeicherte Einstiegsquote, darunter 1283 Fussballtipps. Bei diesen Tipps kann der
  Filter nichts ausrichten.
- Die Prozentzahlen der App werden ehrlicher: Bei den Fallen versprach das Modell 61 %, getroffen haben 47 %.

## Grenzen

- Die Einstiegsquote stammt meist von einem einzigen Buchmacher und liegt im Median 16 Stunden vor Anstoss. Die
  Schlussquote ist für zu wenige Tipps gespeichert (854 Schlussquoten gegen 81 103 Einstiegsquoten).
- Die rohe Quote enthält die Marge des Buchmachers. 5 Punkte über 1/Quote sind bereinigt etwas mehr. Das bleibt so,
  weil der Anlass auf der rohen Quote beruht.
- Im Fenster liegt die Länderspielpause bis etwa 17.11. In dieser Zeit gibt es weniger Ligaspiele.

## Nachtrag 13.11.2026: Einstiegsquote über die Auswahl

Owner-Auftrag „B“ vom 13.11.2026. Es ist die einzige Änderung an dieser Festlegung.

**Befund vor der Änderung** (13.11., 08:32, `--count-only`, 3,3 Tage im Fenster): 58 abgerechnete Tipps, davon
0 Fallen, 0 übrige mit Quote und 58 ohne Quote.

**Ursache:**

- Seit PR #112 (live seit 10.11., „Folgetag immer“) erscheint ein Fussballtipp meist schon am Vortag auf der Liste
  `wettfinder_automatic`. Diese Morgen-Zeilen tragen keine `forecast_id`, weil sie nach Regel nie Evidenz sind.
- Die Messung suchte die Quote nur über die `forecast_id` der ersten Veröffentlichung. Für jeden Tipp, der zuerst am
  Vortag erschien, fand sie deshalb nie eine Quote, auch wenn zur selben Auswahl später eine gespeichert wurde.
- PR #112 ging am ersten Tag des Fensters live, einen Tag nach dieser Festlegung. Die Regel scheiterte also an einer
  Nebenwirkung dieses Umbaus, nicht an den Daten.
- Dazu kommt die Länderspielpause: Am 10. und 11.11. wurde keine Einstiegsquote gespeichert, am 12. und 13.11. je
  rund 20 Prognosen mit Quote. Details: `docs/handoffs/2026-11-13-claude-uebergabe-codex.md`, Abschnitt 3.

**Was niemand angesehen hat:** Trefferquoten nach Falle oder Nicht-Falle. Mit der alten Zuordnung war kein einziger
Tipp eingeordnet. Geprüft wurde nur die Struktur: Anzahl je Sportart und Liste, und ob eine Quote vorhanden ist.

**Neue Zuordnung, für das ganze Fenster:**

- Einstiegsquote eines Tipps ist die früheste gespeicherte Quote mit `kind = entry` über **alle** Prognosen in
  `forecast_rows` mit demselben Ereignis, demselben Markt und derselben Auswahl wie der Tipp (`event_key`,
  `market_key`, `selection`). Die `forecast_id` des Tipps spielt für die Zuordnung keine Rolle mehr.
- Haben zwei Prognosen derselben Auswahl eine Quote mit gleichem Zeitstempel, zählt die mit der kleineren
  `forecast_id`. So hängt das Ergebnis nicht von der Reihenfolge in der Datenbank ab.

**Unverändert:** die Schwelle 0,05, die rohe Quote, die Modellwahrscheinlichkeit aus der ersten Veröffentlichung, das
Fenster, das Ergebnis, die drei Bedingungen, die Verlängerung bei zu wenig Daten, die Folgen und „Kein Nachjustieren“.

**Was das bedeutet:**

- Die Quote kann nach der ersten Veröffentlichung gespeichert sein. Bei einem Tipp vom Vortag liegt sie höchstens
  24 Stunden vor Anstoss, der Tipp erschien früher. Das war schon vorher möglich und ist unter „Folgen“ geregelt.
- Für Tipps mit eigener `forecast_id` und Quote ändert sich nur etwas, wenn eine frühere Prognose derselben Auswahl
  eine noch frühere Quote hat.
- Der Bericht nennt zusätzlich, wie viele Tipps ihre Quote nur über die Auswahl haben.
- Der Rückblick oben (07.10. bis 09.11., 566 Fallen) ist mit der alten Zuordnung gerechnet und bleibt so stehen.
- Ob bis zum 28.11. 150 Fallen zusammenkommen, ist auch mit der Berichtigung offen.
- Bis zur Auswertung gilt weiter: nur `--count-only`.
