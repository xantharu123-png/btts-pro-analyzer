# Produktionsbeleg: Live-Wettfinder „Spielfeldrand“ und Platzverweise

Owner-Auftrag: „live“. Am 22.11.2026 wurden [#159](https://github.com/xantharu123-png/btts-pro-analyzer/pull/159) und [#160](https://github.com/xantharu123-png/btts-pro-analyzer/pull/160) gemergt. Der geprüfte Entwurfsstand `2888a25` und der finale Merge haben denselben Git-Baum `702522aeb36025208f5ab48ec9ca504a6f23d629`.

| Produktionsprüfung | Ergebnis |
|---|---|
| Fast-forward auf dem VPS, Branch main | `5a67a63` → `9a3e5bdf7d8140db1269e5ffc15a4bd1f1f141bf`, wie GitHub-main; 24 geänderte Dateien abgeglichen, keine getrackten lokalen Änderungen |
| App-Prozess | Nur `betboy-app.service` neu gestartet; aktiv seit 16:35:17 CET, PID 1745430 → 1748520 |
| Erreichbarkeit | Interner und öffentlicher Streamlit-Healthcheck nach Start jeweils `ok`; unabhängig nachgeprüft. Caddy und sieben Kerntimer aktiv |
| Daten / API | Prüfsummen von Wettfinder- und RisikoBet-Tagesdatei sowie Ligaabdeckungs-DB vor und nach dem Neustart gleich. Kein Backup, kein neuer Anbieter-Scan, keine Änderung an Units oder Abhängigkeiten |

Auf dem VPS lief die App-Prüfung als Anwendungsbenutzer ohne Netzwerk und mit isoliertem Schreibverzeichnis. Zwei synthetische Spiele prüften den Wechsel mit/ohne Platzverweis; die Übernahme der Rotkartenminute, Bank-/VAR-Fälle, Automatik und Tipp-Frische wurden separat geprüft. Exit 0. Dies ist kein beobachteter realer Platzverweis, keine Messung der Zahl vorhandener Tipps und kein Nachweis einer Trefferquote.

Lokal 610 betroffene Tests, zusätzlich 235 unter `floor`. [CI des Merge-Commits](https://github.com/xantharu123-png/btts-pro-analyzer/actions/runs/45038696502) erfolgreich (drei automatische Jobs; die optionalen Vollsuite-Hälften waren nicht gestartet). Die lokale Vollsuite mit `-x` stoppte nach 99 bestandenen Tests am vorbestehenden Eishockeytest `test_native_conflicting_role_ids_fail_before_any_request`.

Separat: `betboy-wettfinder.service` war vor dem Release bereits beendet (Start 03:35:31, Ende 04:05:59 CET, Exit 1). Kein Neustart dieses Jobs und keine Zurücksetzung seines Status.
