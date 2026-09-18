# Übernahme nach Account-Abbruch – 18.09.2026, 16:00 CEST

GitHub-main/lokale Checkouts bei Übernahme:
`afc8a100b6b0c659b06b85b891b8a2d4c09b5c29`.
VPS weiterhin `9659c49b2738d6a4c7b0fcc7442a9e8ecef3b665`.
App war seit dem abgebrochenen Release gestoppt/deaktiviert. Nach Kontrolle
von unverändertem produktivem Git-Arbeitsbaum und vollständigem Migrationsmarker
alter Stand wieder gestartet/aktiviert. Interner/öffentlicher Healthcheck `ok`,
sieben normale App-Timer gestartet/aktiviert. Kein `reset-failed`.

## Frische Tests

Auf unverändertem `afc8a10`: `test_tennis_outcome_schedule`,
`test_context_tennis_outcome_capture`, `test_football_appearance_backfill`,
`test_context_football_capture`, `test_context_tennis_capture`; pytest
`-W error::DeprecationWarning -p no:cacheprovider`, basetemp
`.pytest_tmp/context-resume-20260918-a`: **162 bestanden, Exit 0, 34.88 s**.
193er Windows-/Linux- und 519er Windows-Läufe vom 16.09. nicht addieren.

## Update noch blockiert

Erster entkoppelter Wrapper scheiterte an systemd-Expansion von Bash-Variablen
vor Updaterstart. Mit `--expand-environment=no` startete der vertrauenswürdige
Updater, brach aber vor App-Stopp ab:
`VerificationResourceError: insufficient combined snapshot/restore/seal disk capacity`.
Vom Wrapper pausierte Timer danach wieder gestartet. Fehlgeschlagene Units
`betboy-release-afc8a10-20260918.service` und
`betboy-release-afc8a10-20260918b.service` bleiben als Belege; kein Updater aktiv.

Installierter `/usr/local/sbin/betboy-update`, SHA256
`426145e2352e5ec2f3198b6ea2d0e743989f5b2acfeab60da75c50a6cf480524`.
Kein direkter produktiver Git-Pull oder Einsatz der Repo-Updaterversion.
Formel unverändert; Byte-Inventur: Produktiv-DBs/Begleitdateien 2.470.764.544;
Reserve erforderlich 21.263.988.736; frei 16.313.118.720;
Fehlbetrag 4.950.870.016. Reserve ist nicht App-Codegröße, sondern deckt
mehrere unabhängige Snapshot-/Restore-/Rollbackkopien ab.

### Eigene verwaiste Prüfkopien – noch nicht gelöscht

| Exakter Pfad | KiB | Inhalt |
| --- | ---: | --- |
| `/var/lib/betboy-context-update.05f6cayw` | 3.224.932 | Zwei Kontext-Prüfsnapshots und Berichte |
| `/var/tmp/betboy-update.8uHXm1gx` | 1.797.780 | Code, Rollback und kopierte Sicherungsarchive |
| `/tmp/betboy-outcome-qa.C9ax4T` | 232.220 | Isolierte Linux-Testkopie |

Freigabe für genau diese drei Ziele angefragt. Vor Bereinigung Inaktivität und
Pfade erneut prüfen, einzigartige Inhalte gesichert archivieren, Wiederherstellung
belegen; Backup-Duplikate nur nach Inhaltsvergleich entfernen. Keine produktive
DB oder reguläre Sicherung löschen. Archivgröße vor Freigabe der Reserve prüfen;
nicht behaupten, dass dieser Schritt zwingend den ganzen Fehlbetrag beseitigt.

Beide alten Kontext-Prüfberichte: strukturell `verified`, ausdrücklich
`empirical_approval_verified=false`, `historical_analysis_verified=false`.
Erhaltene Release-Sicherung:
`/var/backups/betboy-update/betboy-preupdate-20260916T082055Z-9659c49b2738-507268.zip`,
429.750.535 Bytes. Damaliger Backuphelfer bestätigte 89 Datenbanken.
Frische ZIP-CRC-Prüfung ohne defekten Eintrag, keine neue 89-DB-Restoreprüfung.
Kein Migrations-Receipt, neuer Produktivcode noch nicht installiert.

## Fachliche Restarbeiten

Unabhängiger Code-/Datengegencheck bestätigt: Fußball-Effektrechnung auf
gemeinsamen Torraten existiert, aber Live-Provenienz-/Snapshot-/Consumer-
Anbindung fehlt. Tennis-Live-Original-/Trainingspfad existiert, echte
Matchdauer/Endzeit fehlt in gespeicherten ESPN-Proben. Vollständige Details und
konkrete nächste Schritte stehen in `TODO_AKTUELL.md`.

Ein begrenzter Probeabruf der bereits in der ATP-CSV gespeicherten offiziellen
URL `https://www.atptour.com/en/scores/match-stats/archive/2026/9900/ms221`
war über das Browserwerkzeug nicht zugänglich. Keine Felder beobachtet; kein
Beleg für HTTP 403 oder grundsätzlich fehlende Daten, kein Endpunkt erfunden
oder Zugriffsschutz umgangen.

Keine produktive Kontextspeicherung bei dieser Übernahme. Keine neue
Effektfreigabe, erfundenen Originale oder Lockerung der 200-Event-Abnahme.
**Verletzungs-/Müdigkeitswirkung und bessere Wettqualität nicht fertig belegt.**
