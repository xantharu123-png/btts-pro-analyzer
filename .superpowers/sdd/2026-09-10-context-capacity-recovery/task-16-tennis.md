# Task 16 — expliziter Streaming-Tennisowner (C3)

12. September 2026. Enger lokaler Baustein nach bestätigter Entscheidung C.
Kein Deployment, keine HMAC-Prüfberechtigung und keine empirische Modellfreigabe.

## Geschriebener Umfang und aktueller Reviewstand

Exklusiv geändert/angelegt durch den Tennisautor:

- `context_storage_v2/tennis.py`
- `tests/test_context_storage_tennis.py`
- dieser Aufgabenbericht

Reviewfreeze vor unabhängigem Gegenlesen:

- Tennisowner SHA-256 `aa94cd18b1280544f47e8c9e9a9a2b25ebf78c42a333c7e713a2db9b19c60d2d`
- Testdatei SHA-256 `a114d7d75b8d68270c27d89c4cd12b82b34541cb23a4c0f5e95ef0dcf8cb1104`

Der unabhängige Reviewer `c_history` liest diesen Stand. Ein fertiger Autorbericht
ersetzt dessen Prüfung nicht. Etwaige spätere Korrekturen brauchen neue Hashes
und erneute Tests.

## Schnittstelle und vollständige Referenzen

`tennis_features_streaming(event, history_view, base, *, cutoff,
work_directory, limits=DEFAULT_LIMITS)` verlangt den echten vollständigen
`HistoryView` einschließlich passender Tour, Stichtag und intakter Quell- und
Lesetransaktion. Er nimmt weder ein erfundenes Tuple noch ein bloßes Iterator-
oder `complete=True`-Versprechen an. Jeder ausgewählte Beleg durchläuft vor
Ereignis-/Teilnehmerprojektion die unveränderte kalte Quellenprüfung.

Das Ergebnis ist ausdrücklich `StreamingTennisFeatures`, **kein** FeatureVector
mit leeren oder abgeschnittenen Referenzlisten. Kleine Werte, Zustände und
Coverage bleiben direkt lesbar; je Feature wird eine vollständige C2-
`RefSetDescriptor` gespeichert. `iter_refs(name)` rekonstruiert den gesamten
sortierten Satz. `iter_canonical_chunks()` und `canonical_digest()` erzeugen
exakt die kanonische vollständige alte FeatureVector-Darstellung ohne deren
gesamte Referenzlisten im RAM aufzubauen.

`materialize(max_bytes=...)` ist nur eine zusätzliche begrenzte Kompatibilitäts-
und Testoperation. Ihr neuer Maximalwert beträgt 64 MiB kanonische Ausgabebytes.
Das ist **kein historischer produktweiter FeatureVector-/Einzelwertvertrag**
und nicht die alte 64-MiB-Legacy-Eingabe beziehungsweise der getrennte Cache.
Vor dem Aufbau wird die vollständige erwartete Ausgabegröße geprüft. Ein
zu enges Limit ergibt einen Fehler, niemals eine erfolgreiche Teilausgabe.

Ergebnis und HistoryView müssen während der Verwendung offen bleiben.
`close()`/Kontextmanager schließen ausschließlich die eigene Ausgabe und
entfernen deren frisch erzeugtes privates TemporaryDirectory; Quelle und
Historien bleiben unverändert. Schließen, Commit, Rollback, Commit+BEGIN,
executescript, Factory-/Callbackänderungen, Dateimutationen und ungültige
Quell-Lebensdauer machen die Ausgabe dauerhaft unbrauchbar. Dies ist eine
lokale Eigentümer-/Lebensdauerprüfung, kein HMAC- oder Root-Rollback-Claim.

## Fachliche Äquivalenz und Speicherstrategie

- Ereignisgruppen werden in ursprünglicher erster Auftretensreihenfolge
  wiederholt gelesen, nicht als gesamte Tour oder gesamte Gruppe materialisiert.
- Alte, neue und gleichzeitig widersprüchliche Revisionen werden vollständig
  besucht. Relevanz-/Konfliktmengen halten nur die zwei Zielteilnehmer.
- Eine neueste Legacy-Gruppe wird vollständig auf gleiche gemeinsame
  Matchidentität und Teilnehmer geprüft. Erst danach wird je Spieler maximal
  ein tatsächlicher Repräsentant an den unveränderten B1/B6-Helfer übergeben.
  Unterschiedliche Identitäten bleiben Konflikte. Kein beliebiger Teil einer
  großen Gruppe wird als vollständige Gruppe akzeptiert.
- Statusbelege binden weiterhin genau die zwei verlangten Belastungsbelege;
  fehlende, zusätzliche, gekreuzte oder widersprüchliche Paare bleiben unbekannt
  beziehungsweise widersprüchlich. Spätere Teilnehmerkorrekturen können alte
  Spielerclaims nicht wiederbeleben. Der Zielspielstatus wird getrennt geprüft.
- Verwendbare Zielspielerzeilen und Referenzprojektionen liegen in privaten
  SQLite-Tabellen. Die endgültigen sortierten Vereinigungen gehen an C2.
- Summen bleiben originale Python-`sum`-Aufrufe über exakt gleich geordnete
  Disk-Generatoren. Es gibt weder SQL-Summen noch schrittweises `+=` als
  Ersatz für Python-Floatsummation.
- Fenster, unbekannte Endzeitgrenzen, Erholung, Coverage und v3-Overrides
  bleiben in derselben logischen Reihenfolge. Insbesondere wird v2-Timing
  bestimmt, bevor der v3-Konflikt-/Unbekannt-Override seine Werte verwirft.

Der Owner begrenzt seine eigene SQLite-Allokation, den SQLite-Cache, einzelne
gelesene Zeilen und die freie Reserve. Er baut keine andere Tour, keine
Quotenregel und keine neue Verletzungs-/Müdigkeitsgewichtung. Die komplette
Mehrdatei-, RSS-/CPU- und Vorbereitungsbilanz bleibt Aufgabe der übergeordneten
C/B-Integration. Ein Alt-Einzelwert größer als die neue 16-MiB-Blockgrenze
benötigt weiterhin einen eigens geprüften Adapter; diese Implementation gibt
dafür keinen Erfolg vor.

## Tatsächlich ausgeführte Tests

Bundled Python mit bereits vorhandenen Repository-Abhängigkeiten:

```powershell
$env:PYTHONPATH='C:/Projekt/BetBoy/betboy-app/.venv/Lib/site-packages'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& 'C:/Users/miros/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -m pytest tests/test_context_storage_tennis.py -q --disable-warnings --basetemp=<neuer eindeutiger Pfad innerhalb .pytest_tmp>
```

- Erster funktionaler Lauf: 71 bestanden, ein Testharnessfehler beim
  impliziten SQLite-Commit von `executescript`; der Test wurde korrigiert.
- Erweiterter Lauf: **193 bestanden in 98,96 s** — 74 neue Tests plus
  `test_tennis_status_v3.py` und `test_tennis_context_features.py` unverändert.
- Nach der rein begrifflichen Korrektur des neuen optionalen 64-MiB-Helpers:
  **74 neue Tests bestanden in 93,14 s**.
- Das unabhängige Review fand anschließend eine echte P2-Kante: auf der alten
  Writerconnection konnte DDL nach vorübergehendem `query_only=OFF` und
  `journal_mode=OFF` ohne Änderung von `total_changes` verborgen bleiben.
  Korrigiert durch echte `mode=ro`-Neuöffnung sowie explizite Bindung von
  Main-/TEMP-Schemaversion und Journalmodus. **76 neue Tests bestanden in
  84,46 s**.
- Das Gegenreview verlangte zusätzlich die Datenbankliste, beide Journalmodi
  und die unveränderliche Limits-Feldidentität. Diese sowie Ressourcen-PRAGMAs
  und eine feste Klassenvalidierung gegen Instanzcallback-Shadowing sind nun
  gebunden. **83 neue Tests bestanden in 94,95 s**, exakt zu den oben genannten
  aktuellen Hashes; das abschließende Gegenreview läuft.

Die neuen Fälle vergleichen vollständig Werte, Zustände, Coverage, alle
Referenzlisten und den kanonischen Gesamtdigest. Enthalten sind leere Historie,
ATP/WTA, Legacy/Status/Mischbestand, echte datierte ESPN-Fixtureform, Rest- und
Fenstergrenzen, gleiche Empfangszeit, nachgelieferte und zukünftige Zeilen,
Teilnehmer-/Zeitplan-/Statuskorrekturen, fehlende/überschüssige Paare, Walkover,
Retirement, Floatreihenfolge, große gleichzeitige Konfliktgruppen sowie
Materialisierungs-, Ressourcen-, Mutations- und Lebensdauerfehler.

Ein vorheriger Versuch ohne eigenes `--basetemp` scheiterte bereits an den
Windows-Temp-Verzeichnisrechten; das war keine Produktprüfung. Keine Installation
oder Umgehung von TLS/Abhängigkeiten wurde vorgenommen.

## Unveränderte Originalowner, frisch gehasht

- `context_models/tennis.py`: `313ffafacc367e7370312f478327d6453860ac0bf17bbcaf8102acdda49e4bab`
- `context_models/tennis_v3.py`: `ec6461b87656ecc5731992cc26f0ae69d20e878982706ebe3f1fd0599c43305c`
- `context_sources/tennis.py`: `80f1621f60e0b3daecef8abb5e44efeebd2c2bc6bc0df8161032daab78ceb739`
- `context_sources/tennis_status.py`: `8c2a8093aa2113564c34088227e5fb0a8c70faf9d52428e74c4995c505a57581`

## Noch nicht behauptet oder erledigt

Kein Nachweis des vollständigen Sieben-Tage-Profils oder nativer 240-s-Abnahme;
keine Aussage zu realer Wettgüte, Verletzungsgewichten oder dem separaten
Tennis-Tagesjob. Kopie-/Snapshotgesamtintegration, B-Proofs/Publisher/Bootstrap,
Backup/Restore, Rückweg, volle Produktregression und VPS-Rollout stehen beim
Root. Der Tennisautor hat weder Git, SSH noch Serverbefehle ausgeführt.
