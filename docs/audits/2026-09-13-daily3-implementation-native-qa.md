# Daily3-Implementierung und tatsächlicher Ausgang der nativen QA

Stand dieser Fortsetzung: 13.09.2026. Keine Behauptung „alles fertig/live“.

## Gesicherter Code

- Branch `codex/context-capacity-recovery-20260910`, Worktree
  `C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910`.
- Daily3: `aca7256d474a2f144fb08e53c13a71a09ff726d3`.
- Strukturelle Scanner-Fehlerdiagnose: `de6b12b`.
- Frühere native Harnesskorrekturen: `3cd3edb`, `150e3ee`, `9bd588a`.
- Getestete Dateien sind committed; der spätere Dokumentations-/Push-Commit
  ist anhand Git zu prüfen. GitHub main beim frischen Abgleich: `f84d9a6`.

Daily3 folgt dem bestätigten Namen und CHF-50-/Drei-Event-/Übernachtvertrag.
Es ist manuelle Buchführung echter, vom Nutzer bestätigter Einsätze, kein
simuliertes Guthaben und kein automatischer Wettauftrag. Quote 1,12 wird nicht
als Modellfehler oder pauschaler Ausschluss behandelt. CHF 150 ist kein Versprechen.
Die detaillierte tatsächliche Auswahl-/Abrechnungsregel steht in Abschnitt 12
der [Spezifikation](../superpowers/specs/2026-09-13-daily3-design.md).

## Nachweise auf dem lokalen Funktionsstand

Gemeinsame Schlussregression: **869 bestanden, 21 übersprungen,
97 Untertests bestanden**, äußerer pytest-Exit 0, Laufzeit 49,33 s.
Verwendet wurde `.codex_test_venv/quality/Scripts/python.exe` mit eigenem frischem
`--basetemp`, `-p no:cacheprovider`, `--tb=short`, `--maxfail=3`.
Explizite Testdateien, nicht die vollständige Repository-Suite:

```text
test_daily3_math.py test_daily3_store.py test_daily3_selection.py
test_daily3_ui.py test_daily3_backup.py test_ev_signal_sources.py
test_wettfinder_surface.py test_workflow_integrity.py test_challenge_15k.py
test_challenge_integrity.py test_account_identity.py test_ux_rendering.py
test_manual_price_reactivity.py test_native_context_qa_budget.py
test_native_context_qa_retained_v2.py test_native_context_qa_coordinator.py
test_backup_stage_archive.py test_server_jobs.py test_selection_coherence.py
```

Abgedeckt: centgenaue Rechnung, 50→120→0 = −50 netto, parallele Zugriffe,
Doppelbestätigung, maximal drei tatsächliche Wetten auch nach Void, keine zweite
Eventrichtung, ID-/Datenquellenwechsel, Uhr-/Tageswechsel, Vortagsnachtrag,
Abrechnung/Korrektur, negative echte Salden, falsche Schlüssel/manipulierte
Historie, wiederhergestellte offene Verbindlichkeiten, getrennte Konten,
fehlende Browser-ID, neue Formulare bei Analyseänderung und echte Modusverdrahtung.
Windows-Skips sind native Linux-/systemd-Grenzen, keine bestandenen Linux-Tests.

Backupprüfung zuerst korrekt an zwei veralteten Helfer-Pins gescheitert, danach
Pins auf die tatsächlich geänderte Helferquelle gebunden und erfolgreich erneut
geprüft: 96 bestanden/8 Skips. Neuer Helfer-SHA256:
`65f28869e773fcaa5bcc186648f440e1f764ffafa656b92211180eb857f09646`.
Die bestehende erwartete Produktions-Updater-SHA wurde nicht verändert.

Browser: eigene isolierte Streamlit-Testseite, ausschließlich erfundene Events
und Belege. CHF 20 bei 1,12 vorgemerkt, als platziert bestätigt, tatsächliche
Test-Rückzahlung CHF 22,40 erfasst → verfügbar CHF 52,40/netto CHF 2,40.
Keine echte Wette und kein echtes Geld bewegt. Desktop drei flache Karten,
Pro/Contra ohne Analyse-Aufklappen. DOM-Breiten 1440/1080/760/320 ohne horizontalen
Überlauf. Das 320-px-Bild war im Browserwerkzeug skaliert; keine pixelgenaue
Mobilabnahme behaupten. Checkboxen im Browser per Tastatur bestätigt, ein
Maus-/Automation-Verhalten blieb nicht abschließend geklärt. Keine Warnungen/
Fehler im gelesenen Browserlog. Eigener Port-8513-Prozess wurde nach überprüfter
Identität beendet; Testdaten/Logs blieben erhalten, Viewport zurückgesetzt.

## Echter VPS-Diagnoseauftrag: fehlgeschlagen, nicht wiederholt

Geprüfte Quelle: `9bd588af9798974d42e8868e4c0a38dcf01aae0f`.
Archiv-SHA256 `f76e3f5aa9c79758661c908d5b9b57b2709029e2e6bfea80139b2f59f528853a`.
Exakte Git-Bytes ohne CRLF-Konvertierung: 458 Python-Dateien und die eingefrorenen
Owner-Pins lokal gleich. Das frühere CRLF-Exportproblem ist hier nicht die Erklärung.

96 historische Wurzeln gebunden. Der einmalige Auftrag reservierte 900 CPU-s /
900 s Gesamtwandzeit, mit A/B/C je 300 CPU-s. Keine Rückerstattung der Reservierung:

| Phase | Beobachtung |
| --- | --- |
| A1 | abgeschlossen, 107,575990 CPU-s |
| A2 | Kind-Exit 125, 108,389114 CPU-s, RSS 91.742.208 Byte, 125,454116338 s Phase |
| Gesamter Prozess | Exit 1, 259,11 s Wandzeit, user 171,27 s/system 48,13 s |
| A3 / B / C | nicht erfolgreich erreicht; Daten-Worker B nicht gestartet |

Exit 125 kommt vom alten Catch-all im Kind. Das ist **kein nachgewiesener
CPU-Timeout**: A2 hatte rund 192 CPU-s zugelassen. Die originale Exception wurde
damals nicht übertragen; genaue Ursache unbekannt. Neuer Diagnosecode bindet
Schritt, Exceptiontyp und begrenzte Dateiname/Funktion/Zeilennummern ohne
Exceptionwerte oder lokale Variablen. Er wurde portabel getestet; noch kein
neuer großer nativer Lauf dieses Diagnosepatches.

Neue reservierte/fehlgeschlagene Daten bleiben unter:

```text
/var/lib/betboy-context-qa-v2-inputs-01
/var/lib/betboy-context-qa-v2-registry-01
/var/lib/betboy-context-qa-v2-job-01
```

`coordination-failure.json`, Request, Codearchiv, Retained-Inventur und Journal
sind erhalten. Lokal `.pytest_tmp/qav2-unit-9bd588a-qualification/` mit stdout,
stderr und Quellenarchiv. Kein neuer Rootname als kostenloser Wiederholungsweg,
keine Entfernung des historischen FIFO, keine Rücksetzung alter Kosten.
Vorherige kleine native Harness-/CPU-Übergabetests waren erfolgreich; sie
ersetzen diesen fehlgeschlagenen Gesamtlauf nicht.

Nach zwei A-Scans sind rund 216 CPU-s verbraucht; rund 84 verbleiben. Ein dritter
gleich teurer Scan würde die 300-s-A-Reserve voraussichtlich überschreiten.
Das ist eine Hochrechnung, kein schon ausgeführter A3-Fehler. Ein weiterer großer
Versuch braucht eine ausdrücklich bestimmte zusätzliche Mess-/Budgetentscheidung,
auch falls die Gesamtaufteilung geändert werden soll. Erst klein die Ursache
eingrenzen; keine unveränderte Endlosschleife und keine Prüfumfangsverkürzung.

## Produktionsstand und offene Arbeit

Letzter frischer SSH-Abgleich dieser Fortsetzung: Produktions-HEAD
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`, `betboy-app.service` und Caddy aktiv,
lokaler Healthcheck `ok`. Tennis: Result=exit-code/Status 1; Wettfinder:
Result=success beim letzten Abgleich. `betboy.service` ist der falsche Unitname
und darf nicht als App-Ausfall berichtet werden.

Kein Produktivcode geändert, kein Updater gestartet, kein direkter Git-Pull,
kein Timer geändert. Installierter Updater weiterhin erwartete alte SHA
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`;
bekannte 64-MiB-Grenze versus zuletzt 499.855.360-Byte-Kontextdatenbank. Niemals
die erreichbare App für einen schon absehbar scheiternden Größencheck abschalten.

Offen: A2-Ursache und tragfähiger begrenzter QA-Ablauf; vollständige C/B-
Wachstums-/Verbraucher-/Feature-/Runtime-Nachweise, reale Restore-/Installer-
Integration und kontrollierter Main-/VPS-Release. Daily3 ist kein Ersatz dafür.
Auch noch offen: Basketball-/Hockey-Begründungsadapter, empirische Validierung
der tatsächlichen Verletzungs-/Müdigkeitseffekte und Prognosequalität. Bestehende
Tennis-/Kontextprobleme werden durch einen neuen Geldledger nicht für gelöst erklärt.
