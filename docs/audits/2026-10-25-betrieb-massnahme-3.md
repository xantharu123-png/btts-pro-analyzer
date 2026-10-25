# Betriebsänderung 25.10.2026: Massnahme 3 des Gesamtaudits (Budget, Tennis-Fallausschluss, Timer, Alarm)

Owner-Entscheidung vom 25.10.2026 abends („alles machen“) zu den offenen Teilen von Massnahme 3 des
Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md` (Befunde D2, D3, D5). Die Fälligkeitstoleranz des
Quotenlaufs (D2, erster Teil) war bereits am selben Abend live (`docs/audits/2026-10-25-quotenlauf-toleranz.md`).
Kein Modell, keine Preisregel und keine Veröffentlichung ändern sich.

## 1. Budget und Identitätslücken sind keine Betriebsfehler (D2)

Vorher: Der Quotenlauf (`--quotes-only --quote-sport all`) endete mit Exit 1, sobald ein Nebenzweig
einen Fehler meldete. Am 25.10. war das jede fällige Ausführung: Eishockey-Identitätslücken
(`ice_hockey:ValueError`, kein Buchmacherspiel zu einem nativen Spiel) und an anderen Tagen das
OddsPapi-Tagesbudget (`APIBudgetExceeded`, zehn Aufrufe je Tag). Die Fussballquoten waren dabei
fehlerfrei.

Nachher:
- `team_sport_prices.classify_refresh_error`: `ambiguous_origin_events`, `conflicting_origin_identity`,
  `native_identity_unavailable`, `native_identity_unbound` sind `identity_gaps` (Datenstatus),
  `APIBudgetError` ist `budget_deferred`; nur alles andere bleibt `errors` und macht den Zweig `partial`.
  Ein Lauf ohne geprüftes Spiel wegen Budget heisst `budget_deferred`.
- `esports_prices.refresh_esports_prices`: ein erschöpftes Budget liefert `status: budget_deferred`
  mit leerer Fehlerliste; je Buchmacher landen Budgetfehler in `budget_deferred`, nicht in `errors`.
- `wettfinder_automation._refresh_scheduled_prices`: `budget_deferred` zählt nicht als Betriebsfehler;
  das Ergebnis trägt `operational_errors` nur noch für Fussball und Tennis (sie entscheiden den
  Exit-Code und damit den Alarm), daneben `side_operational_errors` für Team- und E-Sport sowie
  `budget_deferred` als Summe. Manuelle Läufe sind unverändert.

## 2. Tennis-Tagesscan verliert nicht mehr den ganzen Tag (D3)

Vorher: Ein einziger Fall über dem Fall-Limit der Live-Quelle (32 768 Rohzeilen, 32 MB, 2 MB je
Chunk oder fehlende Payloads) warf `ValueError('live tennis per-case raw admission exceeded')` in
`batch.finish()`; der Scan brach ab (Fehlschläge 22., 24., 25.10.), ohne Partie oder Zahlen zu nennen.

Nachher:
- `context_models.tennis_live_source.LiveCaseAdmissionExceeded` (eine `ValueError` mit derselben
  Meldung) trägt Zeilen, Bytes, grössten Chunk und fehlende Payloads.
- `_LiveSources` schliesst genau diesen Fall vor jeder Zulassung aus (`excluded` mit Diagnose,
  `admitted` mit den Indizes der zugelassenen Fälle); am gemeinsamen Tagesbudget war nichts
  verbucht. Die kumulierten Grenzen, die Chunk-Grenzen und die Frist bleiben fail-closed für den
  ganzen Lauf.
- `prepare_live_v4` ordnet Quellen und Fälle über `admitted` zu, meldet jeden Ausschluss als
  `prepare_excluded` (im Journal als `Tennis-Abschluss`-Zeile) und trägt ihn in das Ergebnis der
  Partie ein (`reason: live_case_raw_admission_exceeded`, Status `partial`); die Prognose wird ohne
  Kontextbeleg gespeichert wie jede Partie ohne Bindung.

## 3. Timer holen nach, Kernjobs alarmieren (D5)

- `Persistent=true` für `betboy-wettfinder.timer`, `betboy-tennis.timer`, `betboy-esports.timer`,
  `betboy-quotes.timer`: Ein verpasster Lauf (Downtime, Neustart) wird nachgeholt, statt dass die
  Website einen Tag ohne Dokument bleibt. Shadow-, Red-Card- und Backup-Timer bleiben wie sie sind.
  Damit nachgeholte Tagesläufe beim Start nicht gleichzeitig laufen, ordnen `After=` den Tennis-Scan
  hinter den Wettfinder-Scan und den E-Sport-Scan hinter beide (wirkt nur, wenn sie gemeinsam
  anstehen).
- `OnFailure=betboy-alert@%n.service` auf `betboy-wettfinder`, `betboy-tennis`, `betboy-esports`,
  `betboy-quotes`, `betboy-football-shadow` und `betboy-app`. Die Vorlage
  `deploy/systemd/templates/betboy-alert@.service` startet `/usr/local/libexec/betboy-alert.py`
  (aus `scripts/betboy_alert.py`) als Benutzer `betboy` mit Journal-Leserecht
  (`SupplementaryGroups=systemd-journal`), gehärtet wie die übrigen Einheiten. Der Helfer schreibt je
  Fehlschlag eine JSON-Zeile nach `runtime_state/ops_alerts.jsonl`, hält die letzten 50 Alarme in
  `runtime_state/ops_alerts.json` und sendet eine kurze Telegram-Nachricht, sobald
  `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` in `/etc/betboy/betboy.env` stehen (heute nicht
  gesetzt; der Owner trägt sie nach, danach braucht es keinen Code). Journalauszüge werden gekürzt
  und Werte hinter `key=`, `token=` usw. geschwärzt; die Telegram-URL wird nie protokolliert. Der
  Helfer wirft nie und endet immer mit 0.

## Supply-Chain und Ausrollen

- Alle 17 Einheiten unter `deploy/systemd/` bleiben in beiden Root-Werkzeugen byte-genau gepinnt
  (`expected_unit_sha256`, zehn Pins erneuert); die Vorlage liegt bewusst unter
  `deploy/systemd/templates/` und hat ihren eigenen Pin (`expected_alert_unit_sha256`,
  `validate_trusted_alert_unit`), damit das Laufzeit-Inventar des Kontext-Hooks (acht Dienste)
  unverändert bleibt. Bootstrap und Updater installieren Helfer und Vorlage mit.
- `tests/test_context_updater_repair.py` rekonstruiert den Updater weiter byte-genau: die
  Änderungen vom 25.10. sind als umkehrbare Pin-Wechsel und Zusätze eingetragen; alle älteren
  Prüfalgorithmen bleiben eingefroren.
- Abweichung vom Zwei-Schritte-Verfahren in `deploy/README.md`: Die Einheiten wurden am 25.10. in
  einem Schritt über einen geprüften Root-Helfer eingespielt (byte-geprüfte Kopie aus dem
  Fast-forward-Stand, `daemon-reload`, Neustart nur der vier Timer und der App), während die Pins in
  beiden Root-Werkzeugen gleichzeitig nachgeführt wurden. Updater und Bootstrap sind danach mit den
  installierten Bytes konsistent; ein Bridge-Updater war nicht nötig, weil kein Lauf des Updaters
  zwischen Merge und Einspielen lag.

## Nachtrag zum Release am 25.10.2026, 23:22–23:25 CET

- **Instanzname des Alarms:** `%n` enthält bereits `.service`, die Instanz heisst darum
  `betboy-alert@betboy-tennis.service.service`; der Helfer erhält `%i = betboy-tennis.service` und
  liest damit Zustand und Journal der richtigen Einheit. Die Namensprüfung im Release-Helfer
  erwartete den kürzeren Namen und brach nach der Installation ab (Exit 23); `finish.sh` im
  Release-Ordner führte Neustart und Prüfungen aus. Probelauf
  `systemctl start betboy-alert@probe.service.service`: Eintrag in `runtime_state/ops_alerts.jsonl`,
  Telegram `skipped`, Benutzer `betboy`.
- **Timer-Neustart feuert ohne Stempel:** `systemctl restart` der drei Tagestimer, die neu
  `Persistent=true` trugen und noch keinen Stempel unter `/var/lib/systemd/timers` hatten, startete
  Wettfinder-, Tennis- und E-Sport-Scan sofort (23:24:56). Die `After=`-Ordnung griff: der
  Wettfinder-Scan lief, Tennis und E-Sport warteten in der Job-Warteschlange. Künftig vor einem
  solchen Neustart die Stempel anlegen oder den Timer nicht neu starten; der Stempel existiert jetzt,
  ein weiterer Neustart holt nur echte Ausfälle nach.
- **Exit-Code des Shadow-Runners:** `scripts/run_football_shadow_due.py` endete mit 1, sobald das
  Artefakt einen Fehlertext trug, auch für „keine aktuelle Bet365-Quote mit Providerzeit; Retry“.
  Mit dem Alarm wäre das alle zehn Minuten ein Fehlalarm. Seit demselben Abend klassifiziert
  `shadow_clv_automation.operational_errors` (Marker `; Retry`, `-Quote/Zeitstempel`,
  `: Details fehlen` sind Datenstatus), das Artefakt führt `operational_errors`, und der Runner
  endet nur dafür mit 1; `partial` bleibt sichtbar. Tests: `tests/test_shadow_runner_exit.py`.

## Offen

- Der Alarm meldet erst nach Telegram, wenn der Owner Token und Chat-ID hinterlegt; bis dahin
  stehen die Alarme nur im Journal (`journalctl -u 'betboy-alert@*'`) und in `runtime_state`.
- Die App zeigt `ops_alerts.json` noch nicht an.
- `get_clv_statistics` ohne Intervalle und der No-Vig-CLV (S5) bleiben offen.

## Tests

`tests/test_betboy_alert.py` (Schwärzung, Protokoll ohne Telegram, Telegram ohne Token-Leck,
nie werfen, Vorlage und Pins, OnFailure an allen sechs Kerneinheiten), `tests/test_tennis_live_source.py`
(Ausschluss genau eines Falls mit Zahlen, Rest läuft, Meldung unverändert),
`tests/test_team_sport_prices.py` (Klassifikation, Identitätslücke ist `complete`),
`tests/test_esports_prices.py` (`budget_deferred`), `tests/test_price_refresh_schedule.py` (Nebenzweige
entscheiden den Exit-Code nicht, Budget ist Aufschub, CLI-Exit nur vom Kern), `tests/test_server_jobs.py`
(Nachholen der drei Tagesscans, kein Nachholen für Shadow und Red Card, Pins), Supply-Chain-Gates
`tests/test_context_update_hook.py` und `tests/test_context_updater_repair.py` grün.
