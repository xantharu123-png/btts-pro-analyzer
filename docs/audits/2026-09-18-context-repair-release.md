# Kontext-Reparaturen — Release-Abgrenzung vom 18.09.2026

## Umfang und Nachweis

Die fünf Funktionscommits nach `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9` beheben konkrete technische Hindernisse. Sie sind keine Freigabe einer neuen Verletzungs-/Müdigkeitswirkung und kein Nachweis besserer Wettqualität.

| Commit | Änderung | Verifikation |
| --- | --- | --- |
| `185812e` | Karten-Consumer friert zusammengehörige Rohdaten in einer Lesetransaktion ein und gibt diese vor CPU-Prüfung frei. | 472 betroffene Tests bestanden, 5 Skips; unabhängiger Review ohne Befund. Andere lange Leser sind nicht pauschal behoben. |
| `b342b02` | Tennis-Data-Saisonpfad auf den tatsächlich veröffentlichten HTTPS-Pfad korrigiert. | 159 betroffene Tests bestanden, 3 Skips; echter isolierter Download und WTA-Modellaufbau, keine Veröffentlichung. |
| `49ad632`, `0df6707` | Verlustfreie, inhaltsadressierte Fußball-Originalspeicherung mit atomarer, explizit begrenzter Publikation und korrekter inklusiver 4-MiB-Grenze. | Erstlauf: 356 bestanden / 4 Skips; Grenzfix: 93 bestanden / 4 Skips. Unabhängiger Nachreview ohne Befund. Noch kein aktiver Live-Collector. |
| `0b529cf` | Exakter vollständiger Sechsdatei-Versionsübergang erhält echte historische ATP-/WTA-Replays trotz geändertem Quellenpfad. | 733 betroffene Tests bestanden, 3 Skips; unbekannte/gemischte Versionen bleiben abgewiesen. Keine alten Originale umgeschrieben. |

Die Testzahlen verschiedener Läufe überschneiden sich und dürfen nicht addiert werden. Ein unabhängiger Gesamtreview der fünf Funktionscommits meldete keine Befunde; seine Freigabe ersetzt weder Gesamttests noch Deployment.

## Gesamtregression und historische native QA

Die Gesamtregression auf `0b529cf` stoppte nach fünf Fehlern: 7131 bestanden, 48 Skips, 97 Untertests bestanden. Der unverändert ausgeführte zuvor offene Rest umfasste 84 Dateien: 2913 bestanden, 48 Skips, zwei Fehler. Alle sieben Fehler wurden anschließend gegen den exakten LF-Export des vorherigen `f3c2b60` reproduziert. Keine durch diese fünf Funktionscommits entstandene Regression wurde daraus nachgewiesen.

Die alten nativen QA-Verträge erwarten historische, exakt gehashte Eigentümerdateien. Zwei frühere Änderungen hatten die normalen Arbeitskopien verändert: zwei ausdrücklich reservierte Sperrdateien erhöhen den aktuellen Task54-Speicherplan um 8192 Bytes; die Inventur kennt inzwischen zwei zusätzliche Snapshot-Referenztabellen. Die positiven Prüffälle vermischten aktuelle Dateien mit den historischen Zulassungsvoraussetzungen.

Die gezielte Testkorrektur `c44684d` trennt aktuelle portable Ausführung und historische native Zulassung. Native Pins, Reserven, Eigentümer, Quell- und wissenschaftliche Schutzregeln bleiben unverändert. Die heutige Ausführung bleibt am alten nativen Vertrag abgewiesen; historische positive Fälle sind ausdrücklich historische beziehungsweise synthetische Tests, kein neuer Linux-/Produktivnachweis. Unabhängiger Spec-/Qualitätsreview ohne Befund; betroffener Umfang: 337 bestanden, 54 Skips, zwei dokumentierte XML-Konfigurationshinweise. Sechs Task54-Fälle anschließend mit kompatiblem XML warnungsfrei bestanden.

**Finaler vollständiger Lauf:** `pytest tests -q --tb=short --durations=15 -W error::DeprecationWarning -p no:cacheprovider --basetemp=C:/Projekt/BetBoy/.qa-final-20260918-39b5c281` ergab **10.065 bestanden, 96 übersprungen, 97 Untertests bestanden**, Exit 0, 1608.90 s. Der identische Funktionsstand wurde danach auf lokalen `main` fast-forwardet und dort mit den acht betroffenen Testdateien nochmals geprüft: **346 bestanden, 12 Skips**, Exit 0. GitHub-main wurde frisch auf `c44684db0b4a2b00930194eca9404c554fddbbae` bestätigt. Kein Deployment- oder Modellwirksamkeitsnachweis aus diesen Zahlen ableiten.

## Tatsächliche Daten und Wirkung

- Echte isolierte WTA-Aktualisierung: 2075 Quelldatensätze bis 12.09.2026, 1110 Spielerinnen, 7025 vorhandene Kalibrierungsbeobachtungen, 5.95 Sekunden Aufbau. Vier openpyxl-Hinweise bleiben dokumentiert. Kein neuer produktiver Tennis-Gesamtlauf daraus ableiten.
- Die Ergebnisinventur enthält 101 unterschiedliche exakt gebundene Tennis-Spiele, nicht 850 unabhängige Spiele. Wiederholte Originalpublikationen dürfen die empirische Stichprobe nicht erhöhen.
- Fußball-Speicherbaustein gemessen an einem ausdrücklich synthetischen 380-Zeilen-Fall: 826589 Bytes expandiert, 230689 Bytes neue eindeutige Nutzlast, 237568 Bytes erstmaliges SQLite-Wachstum; unveränderte Wiederholung 271 Bytes neue Nutzlast. Das ist keine pauschale Festplattengarantie.
- Offen bleiben Fußball-Live-Anschluss mit kausalen B1-Quellbelegen, echte Spieler-/Ersatz-/Belastungsdaten, durchgängige Tennis-Spielinkarnationen bei wiederverwendeten Provider-IDs, tatsächliche Tenniszeitdaten, weitere Sportarten außer Cricket und die empirische Effektqualifikation.
- Mindestens 200 unabhängige unbenutzte Testevents in drei Zeitblöcken zusätzlich zu getrenntem Training/Tuning sowie die freigegebenen Verbesserungs-, Kalibrierungs- und Mehrfachtestregeln bleiben verbindlich. Keine neue numerische Wirkung und keine bessere Wettqualität freigegeben.

## Betriebs- und Freigabestand

VPS-Prüfung um 19:36 CEST: weiterhin `f3c2b60`, App und Caddy aktiv, interner Healthcheck `ok`. Der Wettfinderlauf 19:07:21–19:15:32 CEST war erfolgreich (Exit 0). Neuer Push und Deployment sind getrennt nachzuweisen. Frühere Tennis-Gesamtfehler wurden nicht zurückgesetzt oder als gelöst dargestellt.

Der geschützte Export und die Bereinigung der drei früher konkret freigegebenen Kopien sind abgeschlossen. Das geprüfte Wiederherstellungsarchiv bleibt lokal unter `C:/Projekt/BetBoy/.private-vps-backups/20260918-release-recovery`. Produktionsdatenbanken und reguläre Sicherungen wurden nicht dafür entfernt.

Die weiteren acht genau bezeichneten alten QA-/Recovery-Ziele wurden durch das erneute „alles“ nach konkreter Anfrage freigegeben. Der genaue Umfang wurde unmittelbar bestätigt und im Retirement-Plan festgehalten. Inaktivität und fehlende externe Bind-Mount-Aliase wurden frisch geprüft. Bounded Linux-Probe mit tatsächlichen ACLs, xattrs, Nanosekundenzeiten, Hardlinks und Symlinks bestand; anschließend wurde das echte vollständige Archiv wiederhergestellt und mit allen Originalbytes/Metadaten verglichen. Geschützter Binärexport, dauerhafte lokale Flushes, vollständige Archivdekompression nach Null, vollständiges Manifestlesen und Hash-/ACL-Kontrolle bestanden. Erst danach wurden ausschließlich die acht Ziele und die zusätzliche Server-Transportkopie entfernt. Der Installer, Wartungsrunner und Wartungszustand blieben hashgleich; Produktion und reguläre Backups waren keine Löschziele.

Eigenständige lokale Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`. Archiv: 1632517697 Bytes, SHA256 `44d6f5202513b96156b4b33e0724561b30186a71da0ce32039d89a549d5b9366`. Manifest: 5054045 Bytes, SHA256 `a025bce3460cfa83bb8148499d56907b77c1e76c9c32471adb13baeea987bc95`. Root-private Server-Quittung bleibt unter `/var/lib/betboy-qa-retirement-20260918-ujqea5nr/offload-verified.json`, SHA256 `2ba6b80ca829759d6d7bc79a9aa2aeb1f37f02e90c70233d525b065763ccddbc`. Rund 2.43 GB dauerhaft zurückgewonnen; der ausgewiesene Löschlaufgewinn von 4065267712 Bytes enthält zusätzlich das erst für diesen Vorgang erzeugte Transportarchiv und darf nicht als ausschließlich alte Datenmenge bezeichnet werden.

Reserve nach Bereinigung: 22581014528 Bytes frei, 22399551488 Bytes Grundreserve nötig. Codebereitstellung kommt hinzu; der verbleibende Abstand ist keine garantierte Deploymentfreigabe. Der nächste konkrete Releaseabschluss wird getrennt in `output/playwright/context-repair-deployment-20260918.md` protokolliert. Keine Absenkung der Schutzgrenze und keine weitere pauschale Löschfreigabe.

Ein vorübergehender zusätzlicher Verlust von rund 1.18 GB war eine bereits entlinkte offene Temporärdatei des laufenden Wettfinders. Nach dessen natürlichem Abschluss kam der Platz zurück. Dafür wurde nichts gelöscht oder beendet. Timer führen Berechnungen aus; sie pullen oder deployen keinen Code. Ausschließlich der installierte vertrauenswürdige Updater darf veröffentlichen.

## Lokale Detailbelege

Pläne und Taskreviews liegen in `docs/superpowers/plans/2026-09-18-*.md` und den jeweils gleichnamigen `.superpowers/sdd/`-Verzeichnissen. Große Laufprotokolle, Quelldownload und alte QA-Verzeichnisse bleiben lokal; sie wurden nicht pauschal in Git aufgenommen. Insbesondere: `output/playwright/full-suite-20260918-0545f0dd.log`, `full-suite-remainder-20260918.log`, `wta-isolated-build-20260918.md`, `tennis-replay-locator-compatibility-20260918.md`, `tennis-outcome-coverage-inventory-20260918.md` und `release-reserve-inventory-20260918.md`.
