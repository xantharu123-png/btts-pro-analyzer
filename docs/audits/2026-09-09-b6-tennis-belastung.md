# B6 – Tatsächliche Tennisbelastung und Erholungsgrenzen

Stand: 9. September 2026. Ausgangspunkt:
`5dcb6289eb5803b6d673e447cca90bae7b75f4de`.

## Status und Grenze

Der freigegebene B6-Merkmalsschritt ist als reine, versionierte Berechnung mit
einem source-spezifischen B1-Normalisierer implementiert. Er verändert keine
Prognose, Quote, Rangfolge, 15K-Buchung oder produktive Datenbank. Der bestehende
Legacy-Tennis-Displaypfad ist unverändert. `tennis.workload.native_workload_records`
ist ein ausdrücklich opt-in bereitgestellter Eingang für native Quelldaten,
nicht die automatische Umdeutung alter namensbasierter Shadow-Zeilen.

B7-Wirkungsmodell, B8/Betriebsanbindung, empirische Abnahme und Aktivierung sind
hiermit **nicht** abgeschlossen. Es gibt keinen eingebauten Fünfsatzabschlag und
keine Behauptung eines belegten Wettvorteils. Fehlende Quellenfelder werden nicht
synthetisch ergänzt. Cricket sowie UI, Jobs, Geldbewegungen und die gemeinsam
bearbeiteten Contracts wurden nicht verändert.

## Wiederverwendete tatsächliche Quellenantwort

Es wurden in B6 **null neue Netzabrufe** durchgeführt. Verwendet wurde die bereits
gesicherte, bereinigte ESPN-Probe mit Eingang
`2026-09-07T14:41:09.848629+00:00`, HTTP 200. Die zwei ausgewählten Matchobjekte
tragen beide den angesetzten Zeitpunkt `2026-08-24T15:05Z`. Das sind datierte
Strukturbelege, keine heutigen Spiele und keine frühzeitig beobachteten
Trainingsdaten für den 24. August.

Originalartefakt:
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/espn-source-probe-20260907.json`.
SHA-256 der lokal gelesenen Bytes:
`6f990047b9dde1012b3245a0899890692cef4a533cb94847aa656fce19bd489d`.
Die kompakte, namenfreie Regressionstestfixture liegt unter
`tests/fixtures/tennis_context_espn_20260907.json` und benennt ihren Ursprung und
das unveränderte Empfangsdatum ausdrücklich.

| Native ESPN-Match-ID | Native Spieler-IDs | Beobachtete Sätze | Beobachtete Games insgesamt | Dauer / tatsächlicher Start / tatsächliches Ende |
| --- | --- | --- | --- | --- |
| 184607 | 2012, 11685 | 2 | 22 | jeweils nicht geliefert |
| 184626 | 3204, 2009 | 2 | 17 | jeweils nicht geliefert |

Die IDs stammen aus `competition.id` beziehungsweise `competitors[].id`.
`athlete.id` wird nicht vorausgesetzt. Tiebreak-Punktestände werden nicht als
zusätzliche Games gezählt. `date` wird als angesetzter Beginn erhalten;
`startDate`, Turnier-`endDate` und `format.regulation.periods` liefern keinen
Beleg für tatsächlichen Beginn, tatsächliches Ende, Dauer oder Best-of-Format.
Die tatsächlich gelieferten Satzlinien werden gezählt, nicht `periods=5`.

Der im Quellenbericht datierte SofaScore-403 wurde nicht umgangen oder erneut
angefragt. Die vorliegenden zwei ATP-Beispiele belegen keine WTA-Gesamtabdeckung,
keine Aufgabenquelle, keine Verfügbarkeit, keine Reise und keine vollständige
Spielerhistorie über Wettbewerbe hinweg.

## Implementierter Datenvertrag

- `espn-scoreboard-v1` liest ausschließlich die verifizierte bestehende
  ESPN-Competition-Struktur mit ausdrücklich übergebenem Tour-/Turnierkontext.
- `tennis-shadow-native-v1` akzeptiert vom besitzenden Ingestion-Pfad bereits
  gemessene, native Daten derselben bestehenden ESPN-Quelle. Er verlangt native
  Teilnehmer und Tour. Der aktuelle namenbasierte Shadow-Bestand erfüllt diese
  Schnittstelle nicht; dessen fehlende IDs werden nicht erraten.
- Beide Wege erzeugen denselben geschlossenen B1-Source-Schema-Vertrag
  `espn-tennis-workload-v1`. Ein Match erhält pro nativem Teilnehmer eine
  Beobachtung. IDs sind nach Quelle, Sport und ATP/WTA getrennt.
- Eigene Inhalte-/Terminbindungen ergänzen die unveränderte B1-Receipt-Prüfung.
  Beobachtungszeit bleibt tatsächlicher Eingang. Re-Import, Ergebnisempfang und
  tatsächliches Matchende sind unterschiedliche Uhren.
- Zahlen werden ausschließlich aus der endgültigen B1-`usable_refs`-Auswahl
  erzeugt. Audit-only-Refs, spätere retrospektive Importe und unbekannte
  Source-Schemas werden nicht zu numerischen Merkmalen befördert.
- Gleiche native Events werden über Seiten/Native-Shadow-Wiederholungen genau
  einmal gezählt. Eine spätere kausale Revision ersetzt den vorherigen Stand;
  gleichzeitige widersprüchliche Inhalte oder Terminrevisionen bleiben
  `conflicting`. Eine neue Walkover-Korrektur kann kein altes gespieltes Match
  wieder auferstehen lassen. Fremde Quellen-IDs werden nicht anhand von Namen
  zusammengeführt; ein ungeprüfter Cross-Provider-Alias ist kein nativer Join.

## Fenster, Summen und Abdeckung

Die vom Controller präzisierte und als `tennis-performed-load-v1` versionierte
Fensterdefinition lautet exakt **[cutoff − N × 24 Stunden, cutoff)** in UTC für
N = 1, 3, 7. Die Zuordnung erfolgt anhand des belegten tatsächlichen **Endes**.
Es handelt sich um absolvierte beobachtete Belastung, nicht um die Menge der
neu eingegangenen Meldungen. Dieser erste Schritt erfindet bei unbekanntem Ende
keine genauere Intervallzuordnung aus dem Ergebnisempfang.

Für beide Teilnehmer werden beobachtete Sets/Games/Minuten und deren signierte
A-minus-B-Differenzen mit eigenen Beobachtungsreferenzen erzeugt. Eine fehlende
Dauer bleibt `None`; ein fehlender Gamewert entfernt nicht einen separat
beobachteten Satz. Fehlende Satz-Gewinnerflags bedeuten unbekannte Satzvollendung,
nicht null Sätze. Eine leere unvollständige Historie erzeugt keine Null-Last.

`observed_<metric>_complete_<N>d_<side>` beschreibt ausschließlich die vollständige
Messung der vorliegenden, eindeutig zeitlich zuordenbaren Beobachtungen. Das ist
**nicht** vollständige Spielerhistorie. `history_complete_<N>d_<side>` bleibt bei
vorliegenden Quelldaten ausdrücklich 0, ohne vorliegende Fakten unbekannt.
Die aktuelle Quelle kann `complete=True` nicht selbst bestätigen. Bei fehlenden
Endzeiten bleibt auch die beobachtete Fensterabdeckung unvollständig. Bereits
gemessene Roh-Sätze/Games bleiben trotzdem im unveränderlichen B1-Payload erhalten.

Aufgaben tragen nur den tatsächlich beobachteten Teil bei. Abgeschlossene Sätze
und bereits gespielte Games eines unvollständigen Satzes sind getrennt erkennbar;
der Match-Unvollständigkeitszähler bleibt erhalten. Walkover erzeugen keine
fiktiven Sätze, Games, Minuten oder eine behauptete Erholungsbeobachtung.

## Erholung und nicht belegte Faktoren

`recovery_bounds` liefert zum **angesetzten nächsten Beginn**:

- `minimum_hours = next_start − result_observed_at`,
- `exact_hours = next_start − actual_end`, ausschließlich bei belegtem Ende.

Naive Zeiten, Ergebnisempfang nach dem Import, tatsächliches Ende nach Empfang,
Start nach Ende oder eine Dauer größer als das belegte tatsächliche Intervall
werden abgelehnt. Bereits eingeplante zukünftige Matches zählen nicht als
gespielte Leistung. Die signierte Differenz zweier Empfangs-Untergrenzen ist ein
eigenes beobachtetes Merkmal, nicht selbst eine mathematische Untergrenze der
wahren Erholungsdifferenz.

Die Merkmale heißen ausdrücklich `observed_recovery_*`: Sie betreffen nur die
identifizierten beobachteten Matches und behaupten ohne vollständige Historie
nicht, der tatsächlich letzte absolvierte Wettkampf sei lückenlos bekannt.
Exakte beobachtete Enden, reine Empfangsgrenzen, fehlende Erholung und bekannte/
partielle/fehlende Endzeitabdeckung tragen unterschiedliche Coverage-Identitäten.
Ein für exakte Erholung trainierter Koeffizient darf daher nicht stillschweigend
einen Empfangsgrenzwert erhalten.

`availability`, `return_from_absence` und `travel_hours` bleiben `missing`, weil
kein freigegebener, überprüfter Meldeadapter sie belegt. Ein freies `verified`
oder eine Aufgabe diagnostiziert keine Verletzung und keine betroffene Person.
Turnierorte erzeugen keinen Reisezeitpunkt oder Jetlag. Belag und Halle sind
Basiseingaben und erhalten hier keinen zusätzlichen pauschalen Zahlenaufschlag.

## TDD und Regression

Erstes RED: fehlendes Modul `context_models.tennis` bei der Prüfung der
Empfangs-Erholungsgrenze. Weitere echte RED-Gruppen deckten fehlende Setflags,
doppelte Terminrevisionen, native Source-Bindung, Dauer-/Zeitwidersprüche,
Walkover-Korrektur, getrennte Zeitabdeckung und unvollständige Gamequellen ab.

Der abschließende fokussierte Lauf umfasst **329 bestandene Tests**, davon 56
neue B6-Fälle, außerdem Tennis-Revisions-/Pending-Refresh- und B1-Observation-/
Contract-Regressionen. Basetemp: `.pytest_tmp/b6-final-focused-01`, Python aus
`.codex_test_venv/quality/Scripts/python.exe`, `-B`, kein pytest-Cache.

Vollständiger Gegenlauf auf unveränderten Quell-/Testdateien:
**2.576 bestanden, 15 erwartete Windows-/POSIX-Skips, 97 Untertests bestanden**,
59,77 Sekunden, Exit 0. Basetemp: `.pytest_tmp/b6-final-full-01`; Aufruf
`python -B -m pytest -q -rs -p no:cacheprovider` mit diesem eigenen Basetemp.
Das unabhängige Controller-Review steht vor Integration noch aus. Synthetische
Tests beweisen Mechanik, keine reale historische Vollständigkeit und keinen
gelernten Müdigkeitseffekt. Für diesen reinen Merkmalschritt wurde weder ein
Browser geöffnet noch eine UI-/VPS-Freigabe behauptet.

## Offene reale Daten / empirische Abnahme

Die aktuell nachgewiesenen Antworten liefern keine tatsächlichen Start-/Endzeiten,
keine Minuten und keine vollständige native Cross-Competition-Spielerhistorie.
Sie reichen nicht für eine zeitstrenge 200-Event-/Drei-Block-Abnahme oder eine
validierte Dauer-/Erholungswirkung. Im am 07.09. datiert inspizierten Bestand waren
alle 1.239 gespeicherten Matchdauern NULL, native Teilnehmer- und echte Ende-Spalten
fehlten. Dieser alte Messbefund wird hier nicht als frischer VPS-Check ausgegeben.
Weitere Datenbeschaffung, B7-Training, D1/D2-Prüfung und produktive Anbindung bleiben
explizit nachfolgende Arbeitspakete. Basisprognosen bleiben davon unberührt.
