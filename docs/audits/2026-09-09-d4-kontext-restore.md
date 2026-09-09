# D4 – Kontextdaten prüfen, sichern und Modellzeiger zurücksetzen

Stand: 09.09.2026. Isolierter Branch `codex/kontext-d4-restore-20260909`
auf `796232284a12b46dbd38e93df4df05ccebd467d1`. Dieser Nachweis betrifft nur
lokale temporäre Dateien, keine produktiven Daten und keine empirische Freigabe.

## Ergebnis und ausdrückliche Restgrenzen

Die mechanischen D4-Teile sind implementiert: read-only Struktur-/Referenzprüfung,
atomarer nichtdestruktiver Modellslot-Rollback und wirklicher
SQLite-Online-Stage-/Archiv-/Restore-Gegenlauf. **D4 als vollständige produktive
Freigabe bleibt offen**: D2-Evaluationsauflösung und der vollständige D3-
Snapshot-Eingabeumschlag existieren noch nicht. Der Prüfer erfindet diese nicht.
Linux-/POSIX-QA und die spätere Einbindung in den vertrauenswürdigen Deploypfad
bleiben gesonderte Controlleraufgaben. Keine UI-, Job-, Cricket-, Quoten-,
15K-, Finanz-, SSH-, Provider- oder VPS-Änderung in diesem Auftrag.

## Vor Implementierung bestätigte Controllerentscheidungen

1. Das bestehende A1-Manifest und sein Hash aus `predecessor`, `slots` und
   `published_at` bleiben unverändert. Keine unsichtbare Bestandsmigration.
2. Rollback = **neue** Manifestrevision mit der **exakten kompletten** früheren
   Slotmenge. Neu hinzugekommene Zeiger verschwinden aus dieser aktiven Menge;
   sämtliche alten und neueren Artefakte bleiben erhalten. Vorgänger ist das
   aktuelle erwartete Manifest, nicht das historische Ziel.
3. Eine neue optionale `context_model_rollbacks`-Tabelle speichert den
   kanonischen geschlossenen JSON-Payload mit eigenem SHA256:

   ```text
   schema = 1
   expected_manifest = aktueller CAS-Stand
   target_manifest = tatsächlich früherer Stand derselben Historie
   new_manifest = neu veröffentlichter Stand
   reason = operator-requested-model-rollback
   published_at = tatsächliche Veröffentlichung der neuen Revision
   ```

   Audit, Manifest und Zeigerupdate laufen in **einer** Transaktion. Eine
   veraltete Erwartung erzeugt weder eine Audit-Tabelle noch einen Eintrag.
4. Die gekoppelte Wirkung wird anhand des A1-Kinds `context-effect-v1` und des
   exakten `effect_hash` bestimmt, nicht aus geratenen Effektslotnamen. Die
   Approval gehört exakt in `context-approval:<effect_hash>` und benötigt
   ihren Wirkungspartner im selben Manifest. Ein Effekt ohne Approval bleibt
   als experimentelles Artefakt möglich. Neues und altes Modell werden nicht
   mit fremden Freigaben zusammengestellt.
5. Bestehendes generisches `compute_once`-JSON bleibt ausschließlich
   transportprüfbar. Es werden keine fehlenden Event-/Base-/FeatureVector-
   Eingaben rekonstruiert und keine alten Snapshots umgeschrieben.
6. `verification_level=structural` bedeutet bekannte Speicherstruktur und
   auflösbare Strukturreferenzen, niemals D2-Empirik. `transport_only` meldet
   die fehlende Bindung ausdrücklich. CLI: 0 für structural, 2 für unvollständig,
   1 für Integritäts-/Pfadfehler. `empirical_approval_verified` ist immer false.

## Umfang der Prüfung

`verify_context_database(path)` öffnet ausschließlich vorhandene Dateien in
`mode=ro` mit `query_only`, ohne A1-Initialisierung, CREATE, Reparatur oder
Verzeichniserstellung. Geprüft werden:

- Reale vertrauenswürdige Datei und Vorfahren, keine Symlinks/Junctions oder
  Mehrfach-Hardlinks; POSIX-Besitzer und Schreibrechte gemäß bestehender
  Runtime-Pfadverwaltung, Windows gemäß vorhandener ACL-Grenze.
- Vollständiger SQLite-Integritäts- und Fremdschlüsselcheck, genau die bekannten
  A1/B1/B3-/Rollbacktabellen, kein unerwarteter Trigger/View/Schemastand.
- Kanonische BLOB-JSON-Werte ohne doppelte Schlüssel, tatsächliche SQLite-Typen,
  Artefakt-/Manifest-/Receipt-/Snapshot-/Rollbackidentitäten.
- Ganze aktive Manifestkette einschließlich jeder historischen Referenz,
  keine Lücken, Zyklen oder abgetrennten Manifeste. Deklarierte Erstellungs-,
  Build- und Veröffentlichungszeiten müssen zusammenpassen.
- ATP/WTA über die vorhandenen `state_codec`-/`tour_state`-Validatoren, richtige
  Tourzuordnung, Coverage und endliche rekonstruierte Prognosen. Legacy-
  Sammelzustände werden nicht als gültige Tourzustände umetikettiert.
- EffectArtifact-Head-/Scope-Struktur, Preprocessing-Artefaktreferenzen,
  Approval-Transport-/Effektbindung sowie echte verlinkte A1-Report- und
  Experimentidentitäten. D2s fehlende Reportsemantik wird **nicht** zertifiziert.
- Alle B1-Inhalte und echten Receipts einschließlich der denormalisierten
  Indizes, keine verwaisten Contents und keine erfundenen Empfangszeiten.
- B3-Transporthash bindet Key und unveränderten Payload. Erkennbare
  ContextResults werden zusätzlich über ihren existierenden geschlossenen
  Strukturvalidator und ihre tatsächlichen Effekt-/Receipt-/Approvalreferenzen
  geprüft. Ihre fehlende ursprüngliche Eingabebindung bleibt trotzdem offen.
- Rollback-Audit und Ziel-/Vorgänger-/neues Manifest müssen exakt übereinstimmen.

Ein Live-WAL wird nicht mit `immutable=1` übergangen. Ein normaler read-only
SQLite-WAL-Open könnte SHM-Begleitdateien erzeugen/verändern; daher verlangt
dieser Prüfer bei WAL oder nichtleerem Journal die bereits existierende
**Online-Stage**. Ihr DELETE-Snapshot wird vollständig read-only geprüft.
Es gibt keine neue Stage- oder Wiederherstellungsautorität.

`verify_context_backup_location(path, application_root=...)` prüft den
**ausdrücklich gelieferten tatsächlichen** Runtime-Pfad gegen die vorhandenen
Discovery-Wurzeln/-Ausnahmen. Ein außerhalb liegender Pfad ist ein Fehler,
keine implizite Erweiterung der Leserechte. Der CLI-Parameter `--backup-root`
ermöglicht diesen begrenzten Zusatzcheck. Der tatsächliche VPS-Konfigurations-
pfad wurde hier bewusst nicht abgefragt oder als bereits belegt ausgegeben.

CLI-Ausgaben enthalten stabile Status-/Fehlerklassen, Zahlen, bekannte Tour-
und Hashfelder. Beliebige Slotnamen und rohe Quell-/Fehlerdaten werden nicht
ausgegeben. Die exakte Slotmenge ist für vertrauenswürdige API-Aufrufer verfügbar,
im CLI nur ihr Hash und ihre Anzahl.

## Echte lokale Wiederherstellung und Gegenfälle

Ein temporäres Appverzeichnis enthält `runtime_state/context_models.db` mit
zwei typisierten Tourzuständen, strukturell korrekten synthetischen Effect- und
Approval-Transports, ausdrücklich opaken Report-/Experimentfixtures, echten
B1-Ingestionsreceipts und einem durch B3 erzeugten Snapshot. Die Dummy-
Experimentwerte sind kein Trainings- oder 200-Event-Nachweis.

Ein zusätzlicher Receipt bleibt zunächst in einem echten uncheckpointeten
WAL. Anschließend werden die **unveränderten** `stage_databases`,
`create_archive` und `verify_archive` ausgeführt. Erst nach Prüfung wird exakt
das erwartete einzelne DB-Mitglied in ein **neues** Restoreverzeichnis
geschrieben – kein `extractall`, kein memberbestimmter Zielpfad, kein
Überschreiben einer Runtime-Datei. Artefakt-/Manifest-/Beobachtungs-/Snapshot-
Zeilen bleiben bytegleich; beide Tourzustände liefern dieselben Prognosen.
Die wiederhergestellte Kombination ist ehrlich weiterhin `transport_only`.

Weitere Regressionen:

- Parallel offener WAL-Schreibvorgang: Stage enthält die vollständige alte
  Transaktion; nach Commit enthält eine neue Stage den vollständigen neuen
  Stand einschließlich Artefakt und zugehörigem Manifest.
- Zwei gleichzeitige Rollbacks: genau ein CAS-Gewinner und ein Auditeintrag.
- Gezielter Fehler nach Audit-INSERT vor Pointerupdate: alle Änderungen samt
  neu angelegter Audittabelle verschwinden atomar; ursprüngliche DB bytegleich.
- Neue Receipts und Snapshots bleiben bei Rollback erhalten, ein bestehender
  Snapshot wird nicht nachberechnet. Eine separate Finanz-Sentineldatenbank
  bleibt bytegleich; dies erweitert keine Echtgeld- oder Ledgerfunktion.
- Fehlende/vertauschte Artefakte, fremde Approvals, falsche Slots, falsche
  Reporttypen, ungültige Heads, verwaiste Receipts, manipulierte BLOBs/Hashes,
  Bool-/Float-Schemawerte, ungültige Tourzustände, Zeitumkehr, fehlende Pfade
  und nicht sichere Dateipfade werden zurückgewiesen.
- Opaque Snapshots und unbekannte Artefaktschemas erreichen nie CLI Exit 0.

## Test- und Bytebelege

- Initiales echtes RED: **2 Fehler** (fehlende Rollback-/Verifier-APIs).
- Zweite konkrete RED-Runde: **4 Fehler** (unmögliche deklarierte Publikations-
  reihenfolge und frei gewählte Slotnamen in CLI-Ausgaben).
- Fokus-/Regressionslauf einschließlich A1/B1/B3, Tourcodec, Stage/Archiv,
  Serverjobs und 15K: **762 bestanden**, **15 erwartete Windows/POSIX-Skips**,
  **71 Untertests bestanden**, 33,84 s.
- Ganze Suite auf dieser Arbeitskopie: **2.940 bestanden**, **18 erwartete
  Windows/POSIX-Skips**, **97 Untertests bestanden**, **0 Fehler**, 67,77 s.
- Eigene D4-Datei: **64 Fälle**, davon **61 bestanden** und **3 platformbedingt
  übersprungen**. Die zwei realen Symlink- und ein POSIX-Modustest sind kein
  Linux-Nachweis. Kein Testfehler wurde zu einem Skip umetikettiert.
- Testinterpreter: `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`.
  Vollaufruf: `-B -m pytest -q -rs -p no:cacheprovider
  --basetemp=.pytest_tmp/d4-full-01`.

| Datei | SHA256 der geprüften Bytes |
| --- | --- |
| `model_artifacts.py` | `6cd072f4cf77a9405091fbdc166580cd403ba15e232c915414be493de9fd6d16` |
| `context_runtime.py` | `fc37ac1987650a9377c2b2382cec0d7a4d0bdb7f53f689687f89c37ce66c7a21` |
| `scripts/verify_context_runtime.py` | `c1dab7debf1d5e50df640d99f7de6871468cf3db8a80972aeef6e2d58045f410` |
| `tests/test_context_runtime_backup.py` | `cc7d30a24a8903d61b934fc22cf74452263dacced025e80ea4c5245388252aad` |

Unveränderte privilegierte Bestandsbytes, per Git-Diff gegen den Ausgangscommit
und Dateihash kontrolliert:

| Bestehende Autorität | unveränderter SHA256 |
| --- | --- |
| `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |
| `scripts/backup_runtime_databases.py` | `b37d11a1eec4ebb129797a942ad68ea13861dd3a2b41bfe14644e9f06add5604` |
| `deploy/update_server.sh` | `a07ad24c92f207c9d1124acee37fb4b0e443dae39876dad6c1948b55bb725cbb` |

Die öffentlichen SHA256 liefern überprüfbare Inhaltsidentitäten, keine
Authentisierung gegen einen Akteur, der eine komplette DB samt allen Hashes
ersetzen kann. Keine Übertragung der gesonderten 15K-HMAC-Sicherheitsbehauptung
auf A1. Auch die neue Rollback-Audittabelle wird nur über die API append-only
behandelt; sie ist keine externe Signatur oder unverlierbarer Loganker.

Unabhängiges Abschlussreview, Controllerintegration und spätere Deployment-
Anbindung sind noch separat nachzuweisen. Dieser Auftrag hat nichts gepusht
oder auf dem VPS ausgeführt.
