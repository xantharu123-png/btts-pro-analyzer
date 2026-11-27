# Doppelchance: Wie der tatsächliche Vorschlag entsteht

27.11.2026, BetBoy-VPS auf `d58e985`. Untersucht: Vorab-Fußball im automatischen Wettfinder, von den Eingabedaten bis zum Haupttipp. Vorhandene Dateien und Datenbanken nur gelesen; kein Sportscan, keine Modell-Neuberechnung auf dem VPS, kein Backup, keine App-Änderung.

## Vom Spiel zur Auswahl

1. Der Code bindet Heim und Gast an die Teilnehmer des konkreten Spiels. Für reguläre Ligaspiele kombiniert er Angriff mit der gegnerischen Defensive, bis zu zwölf Heim-/Auswärtsspiele und sechs jüngste Spiele je Team; die aktive Torbasis mischt 75 % Spielortbasis mit 25 % jüngerer Form. xG fließt ein, wenn die Abdeckung ausreicht; in anwendbaren Ligen wirkt separat die jüngste Tordifferenz. Kein Beleg für eine allgemeine Einzelgewichtung aller früheren Gegner oder dafür, dass Wetter/Ausfälle hier schon die Modellchance verschieben. Quelle: `challenge_engine.py:1165,1356–1461`.
2. Alle drei Doppelchancen stammen aus derselben kalibrierten Verteilung regulärer Endstände: 1X = 1 − P(Auswärtssieg), X2 = 1 − P(Heimsieg), 12 = 1 − P(Remis). Heim-/Gastkürzel bezeichnen Rollen, nicht eine fest bevorzugte Mannschaft. Quelle: `challenge_engine.py:898,977,2161`.
3. Danach greifen marktspezifische Evidenz und Kohärenz. Der beste **verfügbare, vergleichbare** 1X2-Kandidat bildet den Ergebnisanker; widersprechende Märkte werden entfernt. Die Hauptauswahl pro Spiel ist die höchste Modellchance unter verbleibenden vergleichbaren Auswahlen. Eine separate Hervorhebung prüft u. a. Kontext und Spielvergleich. Quoten verändern die Modellchance oder den Modellanker nicht, können aber die Darstellung eines Kandidaten ausblenden. Quellen: `wettfinder_automation.py:916`, `forecast_selection.py:40,110`, `wettfinder_surface.py:632,692,808`.

## Produktionsstichprobe: regulärer 03:35-Lauf

52 Modellpaare, 52 Spiele, 34 Ligen; der gespeicherte heutige Modellstand stammt von 03:48 Uhr (Europe/Zurich). Abgleich anhand Fixture-ID, Heim-/Gast-IDs, Anstoß und Modellversion. Zahlen unter „Roh“ und „Katalog“ sind nur Zeilen, die derselben gespeicherten 1X2-Prognose zugeordnet werden konnten; andere Revisionen und Folgetag-Zeilen sind nicht Teil dieses Vergleichs.

| Stufe | 1X | X2 | 12 | Davon schließt den wahrscheinlichsten Einzel-Ausgang aus |
|---|---:|---:|---:|---:|
| Gespeicherte Rohkandidaten | 22 | 16 | 6 | 18 (9× 1X und 9× X2) |
| Zugeordneter gespeicherter Modellkatalog | 8 | 4 | 5 | 0 |
| Veröffentlichungsbelege der Standardansicht | 4 | 3 | 5 | 0 |
| Belegte erste Hauptauswahlen der Standardansicht | 0 | 0 | 2 | 0 |

Alle zugeordneten Doppelchance-Zeilen lagen innerhalb 0,000001 Wahrscheinlichkeit beim Komplement aus derselben Verteilung. Bei allen drei archivierten X2-Auswahlen war Auswärtssieg wahrscheinlicher als Heimsieg; X2 war im überprüften Bestand kein Haupttipp. Für 12 sind als Hauptauswahlen Universitatea Cluj–Sepsi (80,87 %, Fixture 1565317) und Fixture 1585845 (77,32 %) belegt. Ein Beleg bedeutet, dass die Auswahl in dieser Ansicht bereitgestellt wurde, nicht dass sie ein Kunde gesehen oder gespielt hat. Keine Aussage zu Treffern, Rendite oder einem besseren Modell.

## Reproduzierte Schwachstellen

- **Die Ergebnisrichtung hängt an einer überlebenden Marktzeile.** Kontrollfall: Heimsieg 40,68 %, Remis 27,75 %, Auswärtssieg 31,57 %. Mit der Heimsieg-Zeile scheidet X2 aus. Fehlt sie vor dem Kohärenzschritt, kann X2 mit 59,32 % in einer niedrig gefilterten Ansicht führen. Ein Preisfilter allein kann diesen Richtungswechsel nicht auslösen. Eine fehlende Zeile kann allerdings auch sachlich gerechtfertigt sein: Getestet wurde ein echtes marktspezifisches Direktduell-Veto mit synthetischen Daten. Maskierter Datenverlust und begründetes Veto müssen deshalb unterscheidbar bleiben. Ein X2, das den wahrscheinlichsten Einzel-Ausgang Heimsieg ausschließt, kann höchstens 66⅔ % erreichen; der Standardfilter von 70 % verhindert dort diesen Fall. Kein solcher veröffentlichter Fall in der oberen Produktionsstichprobe.
- **Die sichtbare Begründung erklärt die Doppelchance nicht.** Die flache Karte verwendet bei allen drei Richtungen dieselbe Torprognose als Grundlage (`forecast_compact.py:115`, `wettfinder_surface.py:1224`). Das erklärt weder, warum das gewählte Team nicht verlieren soll, noch warum ein Remis bei 12 unwahrscheinlich sein soll. Das Gegenrisiko ist dagegen mathematisch korrekt. Der Kartenkopf übernimmt außerdem den übergebenen Auswahltext unabhängig vom Marktcode: Synthetisch ließ sich `DC_X2` mit Überschrift `1X` und Gegenrisiko „Heimsieg“ rendern. Kein Hinweis auf diese Fehlbeschriftung in der kontrollierten Produktion.
- **Widersprüchliche Endstände können falsch abgerechnet werden.** Offline mit dem echten Abrechnungspfad: Status FT, `goals=2:1`, `score.fulltime=1:1` → die normale Abrechnung bewertet 1X als Treffer, X2 als Verlust und 12 als Treffer statt den Widerspruch offenzulassen. Der neue Vergleichsspeicher weist denselben Input zurück. Zusätzlich akzeptierte der normale Pfad in einem gezielt inkonsistenten Archivdatensatz `football:8` mit nativem Provider-Spiel `9` bei gleichen Teamrollen. Der normale Produzent erzeugt passende IDs; das ist ein nachgewiesener Validierungsmangel, kein Nachweis bereits falsch abgerechneter echter Tipps. Quellen: `challenge_engine.py:783,1039`, `forecast_evidence_settlement.py:61,379,411`, `football_form_comparison.py:185`.

## Empfehlung

Keine pauschale Sperre und kein Modellwechsel. Erst widersprüchliche Endstände/IDs in der Abrechnung zurückweisen. Dann die publizierte Doppelchance in Klartext und mit der tatsächlichen 1X2-Verteilung erklären („Bologna oder Remis“, „kein Remis“); vorhandene passende Formwerte getrennt ergänzen, ohne Scheinkausalität. Schließlich zustandsbezogen festhalten, ob eine fehlende 1X2-Zeile durch Evidenz/Veto oder technisch fehlt; einen belegten Kontextwiderspruch nicht durch eine starre Seitenregel übergehen.

Prüfung: breiter lokaler Lauf 613 bestanden, zwei alte Ilves-Testdaten ohne das seit 02.11. erforderliche `target_search_date` und ein Sandbox-Hardlink-Test fehlgeschlagen. Beide Ilves-Varianten teilen denselben fehlenden Pflichtwert; mit ergänztem Datum im unveränderten In-memory-Test liefert der Reader die erwarteten vier Märkte. Eigener Wiederholungslauf des Hardlink-Tests bestanden. Getrennter Lauf unter der Produktions-Preisregel (`floor`): 235 Tests bestanden.
