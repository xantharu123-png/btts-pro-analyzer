# Betrieb: Zeitüberschreitungen bei API-Football und RisikoBet-Anpfiff während des Laufs

Stand 07.11.2026. Owner-Auftrag „alles machen“. Anlass sind die Alarme vom 06. und 07.11.2026.

## Befund

| Zeit (CET) | Einheit | Ursache |
|---|---|---|
| 06.11. 03:55 | Wettfinder Exit 1 | `Marktquoten Spiel 1585819: ReadTimeout` |
| 06.11. 11:52 | Shadow Exit 1 | `Details 1555548: ReadTimeout` |
| 06.11. 15:42 | Shadow Exit 1 | `Coverage Liga 283: ReadTimeout` |
| 07.11. 04:06 | Wettfinder Exit 1 | `Stats Fixture 1374212: Read timed out (read timeout=20)` und RisikoBet `FrozenRevisionError` |

- API-Football antwortet seit dem 06.11. zeitweise langsam. Die Fussball-Suche dauerte am 07.11. 894 statt 478 Sekunden.
- Eine einzige Zeitüberschreitung zählt als Betriebsfehler. Damit endet der ganze Lauf mit Exit 1 und löst einen Alarm
  aus.
- **RisikoBet:** Die Quellen wurden um 03:58:29 gelesen. Atlante FC – Santos Laguna (Liga MX) begann um 04:00, und die
  Runde war erst um 04:01:16 fertig.
  - Der Speicher lehnt einen SHADOW-Kandidaten nach Anpfiff ab („SHADOW candidates must be stored before event start“).
  - Dadurch scheiterte die **ganze** RisikoBet-Runde des Tages.
  - Der Speicher selbst ist intakt. Schema, Zeiger und `riskobet_latest.json` sind gültig, nur gelesen geprüft am
    07.11.

Mit den Releases vom 05./06.11. hängt das nicht zusammen. Der erste Fehler vom 06.11. um 03:55 lag vor dem Release
20261106-1.

## Änderung

- **`api_budget.api_football_get`:** Nach einer Zeitüberschreitung beim Verbinden oder Lesen (`requests.Timeout`) gibt
  es genau einen zweiten Versuch nach 3 Sekunden.
  - Jeder Versuch hat seine eigene Budget-Reservierung, damit der Zähler ehrlich bleibt.
  - Andere Fehler und eine zweite Zeitüberschreitung gehen unverändert nach oben.
  - Das gilt für alle API-Football-Abrufe: Fussball-Suche, Statistik, Marktquoten, Shadow-Details und Coverage.
  - GET-Abrufe sind wiederholbar, ein zweiter Versuch schätzt nichts.
- **`riskobet_automation.run_riskobet`:** Ein Ereignis, das zwischen dem Lesen der Quellen und dem Abschluss der Runde
  beginnt, fällt mit allen Kandidaten und seinem Snapshot heraus. Der Rest der Runde wird gespeichert.
  - Früher gespeicherte Revisionen dieses Ereignisses bleiben unberührt.
  - Die Speicherregel bleibt unverändert: Ein SHADOW-Kandidat nach Anpfiff wird weiter abgelehnt.

## Prüfung

- Neue Tests:
  - `tests/test_api_budget.py`: Wiederholung mit eigener Reservierung, keine dritte, keine Wiederholung bei anderen
    Fehlern.
  - `tests/test_riskobet_automation.py::test_event_that_starts_while_the_run_is_built_drops_out_alone`. Er bildet den
    Fehler vom 07.11. ohne die Änderung genau nach.
- Betroffene Suiten (RisikoBet, Budget, Quoten, Wettfinder, Fussball-Kontext): 486 und 135 bestanden.
