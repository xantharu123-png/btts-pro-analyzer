# Tennis-Terminrevision: begrenzter Settlement-Fix

Stand: 9. September 2026. Basis: `a0fc89cdef1c3a7bebfb237e8aaed1ecb0ee1028`.
Eigene Arbeitskopie: `.worktrees/tennis-terminrevision-20260909`.
Status: lokal implementiert und getestet; unabhaengiges Review, Integration,
Push und VPS-Deployment sind noch nicht Bestandteil dieses Nachweises.

## Verifizierte Ursache

Die rein lesende Produktionspruefung am 9. September gegen 07:15-07:23 UTC
fand den aktuellen Main-Stand auch auf dem VPS, ohne versionierten Drift.
Der Wettfinder-Snapshot von `2026-09-09T07:07:10.334089+00:00` ist degraded,
obwohl Football und Forecast-Evidenz keinen Betriebsfehler melden.
Einziger operativer Fehlercode ist `tennis:event_snapshot_ambiguous`.

Die bestehenden Store-Verifikationsfunktionen wurden ohne Konstruktor oder
Migration ueber eine SQLite-Verbindung mit `mode=ro` und `query_only` gelesen.
Ergebnis: 202 eindeutige Ziele plus 96 mehrdeutige Kandidatengruppen, insgesamt
298 faellige Kandidaten. 19 Tennis-Events besitzen jeweils zwei gleich native
gebundene Kandidaten mit unterschiedlichen eingefrorenen Startzeiten.
Event-Key, Teilnehmerorientierung und `tennis_prediction_id` stimmen ueberein.

Die Kandidaten-ID enthaelt die Auswahlpolicy. Alte `riskobet-selection-v1`-
Kandidaten bleiben daher neben `riskobet-evidence-order-v2` erhalten. Die alte
Startzeit dieser 19 Gruppen ist jeweils `2026-09-07T04:00:00+00:00`; die
spaetere Revision enthaelt den konkreten Start am 7. oder 8. September.
Die gemeinsame Event-Abfrage verlangte bisher identische Startzeiten und
lehnte deshalb beide Kandidaten ab.

Ein exakter Beleg ist Prediction 1269, ESPN-Event 182682, Darderi/Zverev:

- v1-Snapshot `snapshot_de1b326a28af2df1610809c716f0b3277c685acb0f1b582b98c9ec397648c29d`,
  Start 7. September 04:00 UTC.
- v2-Snapshot `snapshot_6d8adc54ce8c1b5a39b395cf3e1ba597ccd5b2d40248c3d6195fcc9d153ce032`,
  Start 8. September 00:30 UTC.
- Dieselbe Quellzeile enthaelt bereits ein regulaeres Ergebnis mit
  `result_observed_at=2026-09-09T05:18:31.406357+00:00`.

Diese Diagnose hat keine Ergebniszuordnung geschrieben. Die 96 gleichzeitigen
mehrdeutigen Kandidatengruppen sind ein anderer Fall und bleiben geschlossen.

## Begrenzte Aenderung

Nur `riskobet_settlement_automation.py` wird funktional geaendert:

1. Die Event-Gruppierung akzeptiert unterschiedliche Startzeiten nur fuer
   Tennis und nur bei identischem Event-Key, exakt gleicher Teilnehmerreihenfolge
   und genau einer gemeinsamen eingefrorenen Prediction-ID.
2. Ein solcher Request setzt das neue, rueckwaertskompatibel standardmaessig
   falsche Feld `requires_native_identity`. Der echte Tennis-Reader verlangt
   dann nicht-leere native Provider-/Eventfelder und bindet sie wie bisher an
   den exakten Event-Key, die Prediction-ID und die Teilnehmerorientierung.
   Ein synthetischer Legacy-Fallback aus einer lokalen Zeilennummer genuegt
   nicht fuer diese Ausnahme. Injizierte ResultLoader muessen ebenfalls den
   in diesem Request ausgedrueckten Quellenvertrag beachten.
3. Ein Ergebnis wird einmal gelesen, aber jeder Kandidat wird vor dem
   Schreibpfad separat gegen seine eigene eingefrorene Startzeit und seinen
   unveraenderten Settlement-Vertrag geprueft. Ein Ergebnis zwischen den
   Startzeiten erreicht ausschliesslich den zeitlich zulaessigen Kandidaten.
4. Doppelte Ergebnisbeobachtungen bleiben geschlossen. Der echte Reader
   verweigert zudem doppelte physische Ergebniszeilen fuer dieselbe
   Prediction-ID, statt in einem fehlerhaften Quellschema die erste zu waehlen.
   Solche physischen Duplikate wurden als lokaler Gegentest konstruiert;
   es gibt keinen Nachweis, dass sie auf Produktion existieren.

Keine Aenderung an RisikoBet-Store, Schema, Kandidaten-/Snapshot-Identitaeten,
15K, Geldbewegungen, Einsatz, Auszahlung, Settlement-Marktbedeutung,
Modellwahrscheinlichkeiten, Quoten oder Consumer-Auswahl. Kein anderer
Sportadapter erhaelt eine Startzeit-Ausnahme. Cricket bleibt unangetastet.

## Tests und Wiederholung

Interpreter: bestehende `.codex_test_venv/quality/Scripts/python.exe`.
Alle Aufrufe verwenden `-B -m pytest -q -p no:cacheprovider` sowie eigene
Basetemp-Verzeichnisse innerhalb dieser Arbeitskopie.

- Erste Ausfuehrung erreichte wegen eines noch fehlenden `.pytest_tmp`-
  Elternverzeichnisses keine Tests. Das Verzeichnis wurde danach angelegt;
  diese Setup-Fehler sind kein TDD-Nachweis.
- `tennis-schedule-red-02`: 15 fehlgeschlagen, 6 bestanden auf Originalcode.
  Die fachlichen Positivfaelle scheitern mit `event_snapshot_ambiguous`.
- `tennis-schedule-green-01`: 96 bestanden, neuer Gegenfall plus unveraenderte
  RisikoBet-Store-/Settlementtests.
- `tennis-schedule-red-03`: beide neuen Duplikat-Quellzeilenfaelle rot,
  da der erste Readerstand willkuerlich eine Zeile uebernimmt.
- `tennis-schedule-green-02`: 152 bestanden, inklusive Pending-Refresh und
  Tennis-Prognoserevisionen; insgesamt 23 neue Regressionsfaelle.
- `tennis-schedule-full-01`: **2014 bestanden, 11 erwartete Windows-
  Symlink-Skips, 97 Untertests**, 61,76 Sekunden, Exit 0.
- `git -c core.autocrlf=false diff --check`: sauber.

Die Tests verwenden echte lokale SQLite-Reader und den unveraenderten Store.
Sie pruefen unterschiedliche Vertrage, exakte Zeitgrenzen, fehlende/falsche
native IDs, andere Teilnehmer, umgekehrte Orientierung, noch nicht vorhandene
Ergebnisse, mehrfache Ergebnisbeobachtungen sowie gleichzeitige mehrdeutige
Kandidatenrevisionen. Urspruengliche Run-, Snapshot-, Kandidaten-, Membership-
und Stage-Zeilen bleiben bytegleich; der Quell-DB-Hash bleibt unveraendert.
Ein zweiter Lauf fragt terminale Kandidaten nicht nochmals ab und legt keine
zweite Ergebniszuordnung an.

Eingefrorene SHA-256 nach der vollstaendigen Suite:

- `riskobet_settlement_automation.py`:
  `685378f90bba1e8b1ae9159dda95e936250542b9cc6bf48dab497c0b037dd2e1`
- `tests/test_tennis_settlement_schedule_revisions.py`:
  `b7b53199f1a078da27e17ef36da6274d41dd479c2e105f8404f0ec9e534f5954`
- Der unberuehrte gepinnte Backup-Helper hat weiter SHA-256
  `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

## Unabhaengiger Review-Auftrag und offene Grenzen

Reviewer sollen insbesondere native Bindung versus Legacy-Fallback, die
Zeitpruefung jedes einzelnen Kandidaten, Erhalt aller eingefrorenen Daten,
Idempotenz, widerspruechliche Quellen und die unveraendert geschlossenen
gleichzeitigen Kandidatenrevisionen angreifen. Kein bloesser gruener
Dienststatus gilt als Beleg fuer erfolgreiche Ergebniszuordnung.

Der separate produktive Tennis-Refreshfehler bleibt bestehen: die oeffentliche
WTA-Jahresquelle liefert aktuell HTTP 503, HTTPS scheitert beim TLS-Handshake.
Der gespeicherte Gesamtmodellhash bleibt der verifizierte Juli-Stand
`5b7377452256ff7064e8eba96c01b85e22a191008b74af4038025fd776675347`.
Dieser Patch aendert weder diese Quelle noch den getrennten ATP/WTA-Ausbau.
Keine weiteren Providerabrufe, Jobstarts, Produktionsschreibzugriffe oder
Deployments fanden fuer die Umsetzung statt.
