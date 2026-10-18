# Fußball: speichersparender Trainingsdatensatz

Stand: 18.10.2026. Ausgangsstand `c242a4210daafe5366760820e8a3a1419ae2380f`.
Die Richtung „zuerst Fußball-Trainingspfad“ ist freigegeben. Diese schriftliche
Fassung steht noch zur Prüfung; sie autorisiert noch keinen Produktpatch.

## 1. Ziel und begrenzter Umfang

Mehrere zulässige Fußballfälle sollen gemeinsam trainierbar sein, ohne ihre
großen vollständigen Quellenbestände gleichzeitig zu behalten oder dieselben
Referenzlisten pro Fall erneut dauerhaft zu speichern. Jeder Fall bleibt aus
echten Originalbytes vollständig nachprüfbar. Modellformeln, Merkmale,
Regularisierung, Tuning und Qualitätsanforderungen ändern sich nicht.

Der heutige Quellenleser funktioniert für einzelne große Fälle. Der nächste
Besitzer sammelt aber wieder Vollfälle: `football_readiness.py`, `dataset.py`,
`training_cases.py` und `training.py`. Zwei große Fälle überschreiten bereits
128 MiB zurückbehaltene JSON-Nutzdaten. Zusätzlich wiederholt Dataset-Schema 1
die gesamte Beobachtungsliste je Fall. Ein Generator allein behebt beides nicht.

Dieser Umfang umfasst Dataset, physischen Projektionsbesitzer, unveränderte
numerische Fit-Anbindung, Readiness und bestehenden Offline-CLI-Einstieg.
Kein neuer Dienst, Zeitplan, Datensammler oder allgemeines Trainingsframework.

## 2. Versionierter Datensatz statt Änderung alter Belege

Das vorhandene Artefaktkind `context-dataset-v1` bleibt erhalten. Sein Payload
erhält einen ausdrücklich getrennten, geschlossenen Zweig `schema=2`:

- Felder oben: `schema`, `event_identity_hash`, `source_catalog`, `groups`.
- `source_catalog`: nichtleere lexikografisch sortierte eindeutige SHA-256-Receiptreferenzen
  sämtlicher Nicht-Ergebnis-Quellen aller enthaltenen Fälle, ohne unbenutzte Einträge.
- Gruppen behalten `family_config_hash`, `training_cases`, `final_cases`,
  `unavailable_final`, `fit_ref` und deren bisherige Bedeutung.
- Jedes Fallmitglied enthält ausschließlich `case_ref` und `source_membership`.
  Letzteres ist ein kanonischer Standard-Base64-String mit Padding, keine URL-Variante.
  Die decodierte Bitmap hat exakt `ceil(len(source_catalog)/8)` Bytes. Index k
  verwendet Bit `k % 8` im Byte `k // 8`, niederwertiges Bit zuerst.
  Nicht verwendete obere Bits des letzten Bytes müssen null sein.
  Decodieren mit strikter Alphabetprüfung und erneutes Encodieren müssen denselben
  String ergeben. Jede Fallmitgliedschaft ist nichtleer. Fehlende, zusätzliche
  oder abweichende Mitgliedschaft ist ungültig.
- Falllisten sind nach `case_ref` sortiert und duplikatfrei. Ein natives Event
  darf weiterhin nicht auf Training, Tuning und finale Prüfung verteilt werden.
- Der eigene `outcome_ref` stammt unverändert aus dem tatsächlichen Fallheader.
  Er steht nicht im gemeinsamen Nicht-Ergebnis-Katalog; seine Prüfung bleibt
  an Phase, Ergebnisvertrag und tatsächlich beobachteten Zeitpunkt gebunden.

Schema 2 ist ausschließlich für Fußball mit `football-native-source-stream-v2`,
bestehenden Schema-2-Joint-Fällen und den bereits unterstützten Varianten
`football-joint-log-tilt-v1` beziehungsweise `football-joint-log-tilt-v2` zulässig.
Kein automatisches Überführen alter Datasets, Experimente oder Freigaben.
Schema 1 bleibt byte- und verhaltenskompatibel.

## 3. Ein physischer Besitzer für Vorbereitung und Wiederprüfung

1. Der vorhandene `dataset._reader` hält einen echten read-only SQLite-Snapshot.
   Alle Gruppen-, Fall-, Identitäts-, Split- und Quellkopfprüfungen erfolgen
   weiterhin vor dem ersten Trainingslabel. Eine Bitmap ist kein Beweisersatz.
2. Der Besitzer löst genau einen vollständigen Fall über die bestehenden
   Original-, Bindungs-, Quellen-, Inventar- und Stichtagsvalidatoren auf.
   Alle kausalen Revisionen, Rücknahmen und Konflikte bleiben erhalten.
3. Die tatsächlich rekonstruierte Quellenmitgliedschaft muss exakt der Bitmap
   entsprechen. Der Besitzer darf weder nur verbrauchte Merkmale prüfen noch
   eine Quellenliste anhand des gewünschten Trainingsergebnisses verkürzen.
4. Erst nach vollständiger Prüfung entsteht intern eine kompakte Projektion:
   unveränderter Fallheader samt Digest, tatsächlich rekonstruierte Trainingszeilen
   und das validierte eigene Ergebnis für benötigte Marktziele und Joint-Zellen.
   Keine vollständigen historischen Payloads oder Originalartefakte behalten.
5. Vollfall, Validator-Rückgaben und sämtliche darauf zeigenden Aliase werden
   freigegeben, bevor der nächste Vollfall aufgebaut wird. Kurzzeitige interne
   Kopien desselben Falls sind separat zu messen, keine behauptete RSS-Garantie.
6. Der interne Zahlenkern erhält nur diese vom physischen Besitzer erzeugten
   Projektionen. Es gibt keinen öffentlichen Einstieg für frei gelieferte
   Zahlen, `verified=True`, Proofhashes oder caller-eigene Projektionen.
7. D2 erzeugt dieselben Projektionen erneut aus den realen Originalquellen.
   Sämtliche Alpha-Kandidaten, Tuningwerte, Auswahl, Zeilen- und Fitbytes müssen
   zum eingefrorenen Versuch passen. Finale Labels werden weiterhin erst nach
   dauerhaft protokollierter vollständiger Testöffnung benutzt.

Legacy-`fit_family` behält seinen bisherigen öffentlichen Vertrag. Wiederverwendete
interne numerische Kerne dürfen nur ihre Eingangsprojektion ändern: keine neue
Mathematik, Rundung, Skalierung, Verlustfunktion oder günstigere Fallauswahl.
Auf derselben kleinen Kohorte müssen alter und neuer Pfad identische Fitbytes liefern.

## 4. Ressourcen und tatsächlicher Einstieg

- Höchstens 1.024 explizit ausgewählte Events; kein günstiges Präfix bei Überlauf.
- Neuer gemeinsamer Quellenkatalog höchstens 100.000 Referenzen. Die bestehende
  Zulassung eindeutiger physischer Artefakt-/Quellbytes bleibt auf 128 MiB begrenzt.
- Je Fall weiterhin höchstens 100.000 Quellenreceipts, 128 MiB physische und
  128 MiB expandierte Quellnutzdaten; je Merkmalszweig 4 MiB/4.096 Receipts.
- Zurückbehaltenes kanonisches Dataset, Mitgliedschaften und numerische
  Projektionen zusammen höchstens 128 MiB. Das ersetzt nur im neuen Vertrag
  die Summierung sämtlicher vollständiger Fälle, nicht deren Einzelprüfung.
- Bestehende globale Offline-D2-Grenzen bleiben ebenfalls unverändert.
- Berichte trennen eindeutige physische Eingangsbytes, kumulierte Lesearbeit,
  größten transienten Fall, zurückbehaltene Nutzdaten, Wall-/CPU-Zeit und RSS.
  Lesearbeit ist keine gespeicherte Datenmenge; JSON-Nutzdaten sind kein Prozess-RAM.
  Kein Versprechen, 1.024 große Fälle würden in einer bestimmten Zeit passen.

`inspect_football_readiness` und `prepare_football_context` erhalten den expliziten
Parameter `dataset_schema=1`. Nur `dataset_schema=2` zusammen mit dem tatsächlichen
`source_transport='football-native-source-stream-v2'` wählt den neuen Pfad.
`scripts/prepare_football_context.py` reicht diese beiden optionalen Planschlüssel
wirklich weiter; fehlt einer, ist seine Kombination ungültig. Alte Pläne behalten
ihren bisherigen Default. Der neue Pfad darf kein unbenutzter Parallelhelper bleiben.

## 5. Zwei getrennte Abnahmen, keine verdeckte Produktionsfreigabe

**Offline:** Der echte bestehende Prepare→Fit→Freeze→Evaluate→Verify-D2-Einstieg
wird an isolierten nativen Testfixtures vollständig geprüft. Die bisherigen
Produktionspfadsperren von CLI/Vorbereitung bleiben erhalten.

**Echte Produktionsoriginale:** Ausschließlich begrenzte lesende Prüfung von
Quellen, exakter Mitgliedschaft, Projektion, Parität und Ressourcen über den
vorhandenen Readiness-Bibliotheksbesitzer. Kein zusätzlicher Sportscan, DB-Export,
ATTACH, Datenbankkopie oder Produktionswriter zum Umgehen der Offline-Sperren.

Wichtige Grenze: Vorbereitung, Experiment-Freeze und D2-Testöffnung müssen heute
in dieselbe Datenbank schreiben. Ein neuer vollständiger Real-Kohorten-D2-Lauf
ist unter den jetzigen Offline-/Keine-Kopie-Vorgaben deshalb noch nicht ausführbar.
Dieser Speicherpatch allein behebt diese zusätzliche Ausführungs-/Persistenzgrenze
nicht. Eine spätere produktive Trainingsausführung braucht einen eigenen expliziten
Vertrag; weder ein Memory-Overlay noch ein direkter unterer Writer ersetzt ihn.
Die reine Produktions-Leseprobe darf nicht als solcher D2-Lauf ausgegeben werden.

## 6. Abnahmetests

1. Kleine echte SQLite-Fixture: Legacy und Schema 2 liefern identische kausale
   Fälle, Trainingszeilen, alle Alpha-Kandidaten, Tuningauswahl und finale Fitbytes.
2. Mindestens drei einzeln zulässige große Fälle mit zusammen mehr als 128 MiB
   expandierten Quellen: kein Übertrag vollständiger Fälle zwischen Iterationen;
   kleine Projektionen bleiben im unveränderten Batchlimit. RSS separat messen.
3. Überlappende, aber unterschiedliche Quellmengen: exakte Bitmap-Parität;
   fremde/fehlende Referenz, Duplikat, unbenutzter Katalogeintrag, falsche Länge,
   falsches Padding und gesetzte unbenutzte Endbits müssen scheitern.
4. Manipulierte physische Original-/Quellbytes, zurückgenommene oder geänderte
   Meldung, falsche Uhr und native Identität scheitern auch bei erneuter D2-Prüfung.
5. Spione für Labelzugriff belegen: erst alle Header, dann Training; finale
   Körper erst nach dauerhafter Testöffnung. Verspätete Ergebnisse und Event-
   Überschneidungen zwischen Phasen bleiben ausgeschlossen.
6. Tatsächlicher CLI-Opt-in erreicht Prepare/Fit/Freeze/Evaluate/Verify-D2;
   Legacy-Default und Produktionspfadsperre unverändert. Keine Aktivierung.
7. Bestehende Football-, Dataset-, Experiment-, Training- und D2-Nachbarn prüfen;
   alle bisherigen Test-IDs und ursprünglichen FAIL-/INCOMPLETE-Belege erhalten.

## 7. Unveränderte fachliche Grenzen und Release

Keine neuen APIs, kostenpflichtigen Quellen, Backups, DB-Kopien oder Dienstpläne.
Keine Änderung an Quoten-/1,20-Regeln, öffentlichen Prognosen, Tickets oder Geld.
Tennis, zusätzlicher PLAYER_LOAD-v3-Nationalteam-/Transferumfang und Cricket sind
nicht Teil dieses Pakets. Keine erfundenen Verletzungen, Endzeiten oder Effekte.

Empirisch unverändert: mindestens 200 unangetastete unabhängige finale Events
zusätzlich zu Training/Tuning, mindestens drei Zeitblöcke, mindestens 2 % relativer
gepaarter Brier-Vorteil, HAC/BH und Kalibrierung; kein Anstieg des mittleren
Verteilungs-Logloss.
Eine synthetische Kohorte oder bestandene Softwaretests erfüllt das nicht.

Nach Prüfung dieser schriftlichen Fassung folgt ein eigener kurzer Umsetzungsplan
mit dem bereits gewählten Unteragenten-/Review-Verfahren. Produktcode erst danach.
Commit/Push/VPS-Codeveröffentlichung nur nach tatsächlicher technischer Abnahme,
ohne Backup; neue Modellwirkung und reale empirische Freigabe bleiben getrennt.
