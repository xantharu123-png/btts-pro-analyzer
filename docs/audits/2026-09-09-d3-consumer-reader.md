# D3: tatsächlicher readonly Leser gespeicherter Kontextrevisionen

9. September 2026. Neues begrenztes Lesepaket; noch keine vollständige Worker-/
Signal-/Kartenintegration und kein Release-/Empiriknachweis.

`context_consumers.load_context_market(path, reference, selected_market,
expected_event=..., expected_cutoff=..., factor_groups=...)` liest ausschließlich
eine vorhandene konkrete B3-Revision. Keine neueste Namensalias-Auflösung,
Quellenabfrage, Berechnung, Rekonstruktion oder Publikation beim Kartenöffnen.
Die optionale explizite Faktorgruppierung stammt vom owning Adapter.

Der bestehende vertrauensgeprüfte `dataset._reader` öffnet die explizite DB
mit `mode=ro`, `query_only`, `trusted_schema=OFF` und Lesetransaktion. Fehlende DB
oder Tabelle werden nicht initialisiert. Geschlossene Referenz, echte B3-Tabelle/
Spaltenform, kanonischer BLOB und gespeicherter Digest müssen übereinstimmen.
Die unveränderte reine D3-Projektion prüft Ergebnis-/Inputbindung ohne Refitting;
zusätzlich werden vollständiger erwarteter nativer Event und gespeicherter
Entscheidungszeitpunkt abgeglichen. Keine Quote gehört in diese Schnittstelle.

Die Antwort enthält getrennt `projection` und `public_summary`. Letztere wird
vom bestehenden geprüften Textprojektor erzeugt; technische Angaben bleiben
unter `admin_details`. Alte Verbraucher rufen diesen Leser noch nicht auf und
ihre Serialisierung ändert sich durch dieses additive Paket nicht.

Bekannte Grenzen: Dies ist Transport-/Revisionsintegrität, keine physische
Quellen-, originale Rechenrezept- oder empirische Approval-Zertifizierung. Der
Worker muss A1/B1/D2 tatsächlich auflösen; D4 prüft unabhängige Restoresemantik.
Der Live-Statusfilter bleibt für abgesagte/gestartete Spiele zuständig. Ein
beschädigter vorhandener Ref darf nicht unbemerkt eine Ersatzprognose erzeugen.

## Ausgeführte Tests

- 21 neue Readerfälle vor Implementierung: 21 ROT wegen fehlendem Modul,
  1,17s. Kein produktiver Fehlernachweis durch diese erwarteten API-REDs.
- Danach dieselben21 GRÜN, 1,14s; zusätzlich fünf owning Familien als echte
  gespeicherte synthetische Transportfälle, ausdrücklich keine Echtdaten.
- Fokus mit allen D3-Familientransporten, Originalevent-Bindung, Tennis-v3,
  Copy und B3: **375 bestanden, keine Skips, 25,93s**.
- Tests sperren Modellaufrufe, Fit, `compute_once`, Schreibverbindung und Netz;
  SQLite-Authorizer verbietet Daten-/Schemaänderungen. Missing/defekt/view/
  BLOBtyp/Digest, vertauschter Event, andere Entscheidung, detached Outputs,
  genaue Wahrscheinlichkeit und explizite Faktorgruppen sind geprüft.

```text
56f97df9cf133698d40b878a52be2ba27c01a69e010fc0c87e415eb38224af2b context_consumers.py
20dc712161b317d448f4c6ceefaa8c984a1cdd54e5324e913d1e2a743a553e6d tests/test_context_consumers.py
ae2f25acc2a4d0bf7db047c7546293dd51383ea3cddbc1530dd714fab24ba6fe .pytest_tmp/context-consumer-reader-red-20260909-01.xml
7fc5064c4f39128477a2fb25450f4558a34db2e8aa3aa535e2be0f77f636f5ec .pytest_tmp/context-consumer-reader-green-20260909-01.xml
b8a0ea4ecb8b003d4dac8d693763791aaba2eb4e2dcec3d94c676cb1145dd1e8 .pytest_tmp/context-consumer-reader-broad-20260909-01.xml
```

Unabhängiges Review, eigentliche Producer-/Domain-/UI-Verbindung und neue
vollständige Suite folgen separat. Cricket, Wettpreise, 15K, Historien und VPS
unverändert; kein Stagehelper wurde angefasst.
