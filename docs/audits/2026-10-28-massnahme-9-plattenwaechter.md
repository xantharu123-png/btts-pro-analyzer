# 28.10.2026 – Massnahme 9: Platzwächter für die Laufzeitdaten, Befund zu SQLite

Massnahme 9 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md` (Befund D6), Owner-Auftrag vom
28.10.2026. Umgesetzt ist der Teil ohne Datenverlust und ohne Formatänderung: ein Wächter, der
den freien Platz misst und alarmiert. Aufbewahrung, Journalmodus und Schema-Versionen bleiben
Owner-Entscheide; der Befund dazu steht unten.

## Messung auf dem VPS (28.10.2026 09:00 CET, nur lesend)

| Grösse | Wert |
|---|---|
| Volume `/` | 38 GB, 18 GB belegt, 20 GB frei (48 % belegt), Inodes 4 % |
| `runtime_state/` | 8,7 GB |
| `context_models.db` | 7 848,8 MiB (8,23 GB), Journal `delete`, `user_version` 0 |
| `forecast_evidence.db` | 445,1 MiB, `delete`, 0 |
| `riskobet.db` | 383,8 MiB, `wal`, 3 |
| `challenge_model_cache.db`, `api_budget.db` | 19,5 / 11,9 MiB, `wal`, 0 |
| übrige 13 Datenbanken | je unter 20 MiB, `delete`; `consumer_tips.db` `user_version` 1 |
| `database is locked` im Journal der sechs Kerneinheiten seit 14.10. | 0 |

Wachstum: Das Audit vom 25.10. nannte `context_models.db` 8,0 GB und `forecast_evidence.db`
462 MB; heute 8,23 GB und 467 MB. Bei gerundeten Ausgangswerten sind das grob 60–90 MB pro Tag
für die Kontextdatenbank und 1–2 MB für die Prognose-Evidenz. Bei 75 MB/Tag reichen die 15 GB
über der Alarmgrenze rund 200 Tage. Der Wächter misst das Wachstum ab jetzt selbst.

## Umgesetzt

- `runtime_disk_guard.py`: misst nach jedem Quotenlauf (Timer alle drei Stunden) das Volume von
  `runtime_state/` und die Grösse aller `*.db` darin, schreibt `runtime_state/disk_status.json`
  (letzter Stand, fünf grösste Datenbanken, eine Stichprobe je UTC-Tag, höchstens 120 Tage,
  mittleres Wachstum pro Tag, Tage bis zur Grenze) und meldet `low` unter 5 GiB frei oder unter
  10 % des Volumes. Er löscht nichts.
- `wettfinder_automation.main --quotes-only`: Bei `low` gibt der Lauf eine Zeile „Speicherplatz
  knapp: … GB frei (… %); Laufzeitdatenbanken … GB. Nichts wird gelöscht; Aufbewahrung
  entscheidet der Owner.“ aus und endet mit Exit 1. `OnFailure=betboy-alert@%n` (Massnahme 3)
  trägt diese Zeile im Journal-Auszug in den Alarm. Eine fehlgeschlagene Messung lässt den Lauf
  nie scheitern.
- Tests: `tests/test_runtime_disk_guard.py` (9 Fälle: gesunder Stand, Grenze nach Bytes und nach
  Anteil, eine Stichprobe pro Tag mit Wachstum, Begrenzung und kaputte Statusdatei,
  Messfehler, Exit-Code des Quotenlaufs).

Keine Änderung an Einheiten, Pins oder Datenbanken.

## Befund, nicht umgesetzt (Owner-Entscheide)

1. **Aufbewahrung der Kontextquittungen.** `context_observations.py` speichert Rohquittungen
   append-only als BLOB (`context_contents`); das ist Absicht (Nachvollziehbarkeit der
   Kontextmodelle) und Codex-Bereich. Eine Aufbewahrungsregel löscht Evidenz und braucht einen
   Owner-Entscheid mit Frist (z. B. Rohinhalte älter als 180 Tage, Hashes behalten).
2. **WAL für die Ledger.** `challenge_store`, `clv_tracker` und `forecast_evidence` laufen im
   Journal `delete` mit dem Python-Standard von 5 s Wartezeit. Seit dem 14.10. gab es keinen
   Sperrfehler; WAL verändert zudem, wie Dateikopien und Sicherungen die Datenbanken lesen
   müssen. Erst mit der Backup-Entscheidung (Audit D1) umstellen.
3. **Schema-Versionen.** `PRAGMA user_version` ist nur in `consumer_tips.db` und `riskobet.db`
   gesetzt; die übrigen Stores migrieren mit `ALTER TABLE … IF missing`. Ein Versionszähler je
   Datenbank lohnt sich mit der nächsten Schemaänderung, nicht als eigene Migration.
