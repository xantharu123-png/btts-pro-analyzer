# Wettfinder-Referenz · 21. November 2026

**Rückkehrpunkt für die Fußball-Haupttipps:** [Produktionscommit `363ed54a74f33464a5a453aaf018ca927f63c324`](https://github.com/xantharu123-png/btts-pro-analyzer/commit/363ed54a74f33464a5a453aaf018ca927f63c324), Git-Tag `betboy-referenz-2026-11-21`, Tree `40a81f6922b9f5cb54b7fe8d79f7109cddf26df5`. Der Tag bezeichnet den **laufenden Code**, nicht den späteren Doku-Commit. [Releasebeleg](2026-11-20-haupttipp-beleg.md#release-am-20-november-2026).

**Beobachtung:** Freitag, 20.11., Schweizer Spieltag. Belegstand eingefroren am Samstag, 21.11., **08:22 CET**. [Maschinenlesbare Einzelbelege und Zählwerte](2026-11-21-wettfinder-referenz.json): exakte Modellchance, Spiel- und Prognose-ID, Anstoß, erster Anzeigezeitpunkt, Modell- und Datenuhr, Versionen, damaliger Preisstatus und Ergebnis. Aus den bestehenden Produktionsarchiven nur die hierfür benötigten Felder gelesen. Kein Datenbankabbild, keine Zugangsdaten und keine Kundenwetten.

## Der Referenzwert: Was lief am Freitag gut?

Nach dem Release um 19:45 Uhr wurde bei 14 verschiedenen Fußballspielen der erste vor Anpfiff tatsächlich gerenderte Haupttipp belegt: **12 Treffer, 2 Verluste (85,7 %; Wilson-95-%-Intervall 60,1–96,0 %)**. Die 14 Modellchancen summieren sich auf **10,804757 erwartete Treffer**, im Mittel **77,18 %**. Das sind rund 1,2 Treffer über der eigenen Prognose; weder ein Tagesziel noch eine belastbare langfristige Trefferquote. Vor dem Release wurde die Hauptrolle nicht zuverlässig archiviert. Deshalb kein Hochrechnen auf den ganzen Freitag.

Die 14 Einzelbelege stammen von **einer gemeinsamen Anzeige um 19:45:31 CET**. Es handelt sich um 14 verschiedene Spiele, nicht um 14 Kundenbesuche oder Einsätze.

| Anstoß CET | Spiel | Haupttipp | Modell | Ergebnis |
|---|---|---|---:|---|
| 20:00 | Almere City FC – NAC Breda | Gastteam unter 2,5 Tore | 81,7 % | Verlust |
| 20:00 | Den Bosch – VVV Venlo | Gastteam unter 2,5 Tore | 73,4 % | Treffer |
| 20:00 | FC Volendam – Jong Ajax | Gastteam unter 2,5 Tore | 83,6 % | Treffer |
| 20:00 | Jong Utrecht – Emmen | Gastteam unter 2,5 Tore | 75,1 % | Treffer |
| 20:00 | FC OSS – Roda | Gastteam unter 2,5 Tore | 80,5 % | Treffer |
| 20:00 | Annecy – Clermont Foot | Heimteam trifft | 74,7 % | Treffer |
| 20:00 | Metz – Boulogne | Heimteam trifft | 72,8 % | Treffer |
| 20:00 | RED Star FC 93 – PAU | Heimteam trifft | 73,3 % | Treffer |
| 20:00 | K. Lierse S.K. – Lokeren-Temse | Heimteam trifft | 73,4 % | Treffer |
| 20:30 | Austria Salzburg – Admira Wacker | Heimteam trifft | 74,5 % | Treffer |
| 20:30 | FC Andorra – Leganes | Über 1,5 Gesamttore | 80,2 % | Treffer |
| 20:30 | Hellas Verona – Cesena | Gastteam unter 1,5 Tore | 79,0 % | Verlust |
| 21:00 | Athletic Club – Espanyol | Heimteam unter 2,5 Tore | 79,0 % | Treffer |
| 22:00 | Cobresal – A. Italiano | Heimteam trifft | 79,4 % | Treffer |

- **Marktmix:** Heimteam trifft 6/6; Gastteam unter 2,5 Tore 4/5; über 1,5 Gesamttore 1/1; Heimteam unter 2,5 Tore 1/1; Gastteam unter 1,5 Tore 0/1. Zehn der zwölf Treffer stammen aus den ersten zwei Wettarten. Keine bevorzugen oder ausschließen allein aufgrund dieses Abends.
- **Preis und Rendite:** 14/14 mit Preisstatus `stale` zum belegten Veröffentlichungszeitpunkt. Die Ergebnisse zählen sportlich. Für diese Stichprobe keine Rendite zu einem damals verfügbaren Preis ausweisen und keinen nachträglich gefundenen Preis einsetzen.

## Die anderen Zahlen – nicht zum Haupttipp addieren

| Grundgesamtheit am 20.11. | Stand 21.11., 08:22 CET |
|---|---|
| Standardkatalog, sämtliche unterschiedlichen Märkte | 55 Spiele, 178 Märkte; 83 Treffer, 81 Verluste, 13 offen, 1 annulliert. 50,6 % von 164 entschiedenen Märkten. Mehrere Märkte pro Spiel sind nicht unabhängig. |
| Katalog der gerenderten Ansichten | 58 Spiele, 194 Märkte; 16 Treffer und 6 Verluste eindeutig verknüpft, 172 ohne exakte Ergebniszuordnung. Nicht als Gesamttrefferquote ausweisen. |
| Erster Haupttipp aus der jeweils **ersten** Tagesveröffentlichung | Für alle 55 bzw. 58 Spiele fehlt die Hauptrolle im Erstinventar. Später belegte Haupttipps ersetzen diese fehlenden Erstinventarbelege nicht. |
| Erste **nach Release** belegte Haupttipps | Gerenderte Ansicht: die 12/14 oben. Automatisch angebotene Standardseite: ein separat belegter Haupttipp, gewonnen. Nicht addieren: Ein Spiel kann auf beiden Flächen vorkommen. |
| Beginn der fortlaufenden Messung am Samstag | Für Spiele mit Anstoß am 21.11. waren um 08:22 CET bereits 23 Erstbelege der automatisch angebotenen Standardseite und 22 der gerenderten Ansichten vorhanden, unabhängig von der Anstoßzeit. Das sind keine Ergebnisse. |

Doublebet, 15K, RisikoBet, Shadow und andere Sportarten sind keine Ersatzstichproben für diese Fußball-Haupttippbilanz.

## Welche Auswahlregel gehört zu diesem Code?

- **Modell:** Produktionsbasis `legacy_form_strength_v1` ([Engine](../../challenge_engine.py)). Alle 14 Belege tragen `challenge-engine:legacy-form-strength-joint-calibration-v1` und `risk-ev-3pct-min-odds-1.20-v2`. Letzteres ist die gespeicherte Policy-ID, kein Nachweis einer verfügbaren Quote. Modellwahrscheinlichkeiten bleiben preisunabhängig.
- **Haupttipp:** Erst widersprüchliche Richtungen im Kandidatenbestand bereinigen, dann den vergleichbaren Modellstand je Spiel **vor** den Preis- und Ansichtsfiltern bestimmen. Bei derselben Teilnehmerbindung und Modellrevision führt der sichtbare Markt mit der höchsten ungerundeten Modellchance; bei Gleichstand stabiler Schlüssel. Kein belegbarer Ersatz aus derselben Revision: keine Hauptrolle erfinden. [Auswahl](../../forecast_selection.py) · [Darstellung und Filter](../../wettfinder_surface.py).
- **Sichtbarkeit:** Die angebotene Standardseite nutzt alle Sportarten, 70 % Mindestanzeigechance (Anzeige auf eine Dezimalstelle gerundet), erste 20 Spiele nach Anstoß. Eine gerenderte Ansicht kann andere Filter oder Seiten haben. Ein allgemeines Highlight oder eine Katalogzeile ist kein Beleg dafür, was in einem Spiel oben stand. [Angebotene Seite](../../tip_publication.py) · [Archivvertrag](../../consumer_tip_history.py).
- **Preisregel des Referenzcodes:** `floor` ist der Projektstandard, `gate` der alternative alte Vertrag. Die 1,20-Grenze, Median und zulässige Ableitung für Torbereiche sowie die Regel für völlig unbepreiste Auswahlen stehen in [market_consensus.py](../../market_consensus.py). Sichtbarkeitsregeln nicht mit dem für diese 14 archivierten Preisstatus gleichsetzen. Keine Server-Secrets oder Laufzeitumgebung exportiert.

## So vergleichen wir spätere Änderungen

1. **Ab 21.11. über komplette Spieltage** vorab dieselbe Auswahlregel fixieren. Hauptauswertung: erster vor Anpfiff angebotener Fußball-Haupttipp je Spiel auf der Standardseite; die ebenfalls gemessenen tatsächlich gerenderten Haupttipps **separat** ausweisen. Der Freitag bleibt eine eigene, spät beginnende Beobachtung. Kein Ersetzen durch spätere günstige Märkte.
2. **Vorgeschlagener erster Vergleichspunkt: 200 verschiedene entschiedene Fußballspiele der automatischen Standardseite über mehrere Wochen.** Je Fläche und Wettart: Spiele angeboten, belegt, Treffer, Verluste, offen, annulliert und nicht zugeordnet; erwartete Treffer = Summe der vorherigen Modellchancen der entschiedenen Spiele. Trefferquote mit Intervall, Anteil der beiden dominanten Referenzmärkte (`HOME_OVER_0_5`, `AWAY_UNDER_2_5`) und Preisabdeckung daneben. Finanzielle Bilanz nur bei exakt passendem, rechtzeitig verfügbarem Preis; echte Platzierungen separat. Nicht nach einer Siegesserie stoppen.
3. **Neue Idee gegen dieselben Spiele prüfen.** Alten Stand als Referenz behalten, Variante vor Anpfiff daneben protokollieren. Paare, unterschiedliche Auswahlen und ausgelassene Spiele ausweisen. Auch dann nicht nachträglich andere Tipps oder Preise aussuchen, wenn die Variante weniger Spiele bedient. 200 Spiele sind ein erster Vergleich, kein automatischer Freigabeschalter.

## Nachrechnen und gezielt zurückkehren

Die Zeitgrenze verhindert, dass spätere Abrechnungen still den Referenzwert ändern. Im bestehenden App-Verzeichnis mit den vorhandenen Archiven (lesen, kein Sportscan):

```sh
python -B scripts/selection_performance_report.py --db runtime_state/forecast_evidence.db --history-db runtime_state/consumer_tips.db --from-day 2026-11-20 --through-day 2026-11-20 --as-of 2026-11-21T08:22:00+01:00 --surface wettfinder_automatic_event_leads
python -B scripts/selection_performance_report.py --db runtime_state/forecast_evidence.db --history-db runtime_state/consumer_tips.db --matchday 2026-11-20 --as-of 2026-11-21T08:22:00+01:00 --surface wettfinder_default_inventory
```

Im ersten Bericht `first_visible_cards` prüfen (nur `sport == "football"`; für diese 14 ohne Unterschied), im zweiten `matchday.all_distinct_markets`. Für die andere Fläche jeweils `wettfinder_default_event_leads` bzw. `wettfinder_automatic` einsetzen. Die JSON-Datei bleibt auch ohne den VPS lesbar und wird nicht mit späteren Daten überschrieben. Künftige Messungen erhalten eine neue datierte Datei.

Bei Verschlechterung erst mit `git diff betboy-referenz-2026-11-21 HEAD -- forecast_selection.py wettfinder_surface.py tip_publication.py challenge_engine.py market_consensus.py` die Auswahländerungen eingrenzen; bei anderen Ursachen auch weitere geänderte Dateien und Konfiguration prüfen. Nur die ursächliche Änderung auf dem aktuellen Entwicklungsstand gezielt rückgängig machen, Beleg-/Auswahltests und Preisverträge prüfen, erst dann regulär veröffentlichen. **Kein Reset des VPS, kein Zurückrollen von Konten, Datenbanken oder neueren unabhängigen Fixes.** Der Codeanker stellt weder Live-Daten noch das damalige Sportangebot wieder her.
