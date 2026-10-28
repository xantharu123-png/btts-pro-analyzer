# 28.10.2026 – Massnahme 4: Suiten unter der Preisregel 1,20 in der CI, Lockfile mit Verbraucher

Massnahme 4 des Gesamtaudits `AUDIT_BERICHT_2026-10-25_CLAUDE.md` (Befunde D5 erster Teil, D7),
Owner-Auftrag vom 28.10.2026 („mach alles, was du von deiner Seite machen kannst“). Keine Änderung
an Modell, Auswahlregel oder Preisregel; fünf Korrekturen im Produktionspfad `floor`, die der neue
Testlauf aufgedeckt hat. Vier davon setzen Owner-Regeln vom 23. und 25.10. dort um, wo sie noch fehlten.

## Ausgangslage

`tests/conftest.py` setzte für alle Suiten ausser `tests/test_price_floor_policy.py` den alten
Vertrag `BETBOY_PRICE_POLICY=gate`. Die Produktion läuft seit dem 23.10.2026 unter `floor`; 20 von
6 629 Tests prüften diesen Pfad, und beide Ausfälle vom 25.10. waren Floor-Regressionen. Die CI
installierte `requirements.txt` (Mindestversionen); `requirements.lock` hatte keinen Verbraucher,
und `betboy-update` prüfte nur `requirements.txt`.

## Umgesetzt

| Teil | Datei | Vertrag |
|---|---|---|
| Testschalter | `tests/conftest.py` | `BETBOY_TEST_PRICE_POLICY=floor` lässt alle Suiten unter dem Produktionsvertrag laufen (Default bleibt `gate`); `@pytest.mark.price_policy("gate"|"floor")` pinnt einen Test, der nur einen Vertrag beschreibt; unbekannte Werte brechen ab |
| CI-Job `price-policy` | `.github/workflows/tests.yml` | Matrix `floor`/`gate` über 27 Suiten (Lader, Publikation, Karte, Bet-Finder, Daily3, 15K) bei jedem Push/PR; `test_price_floor_policy.py` und `test_requirements_lock.py` im Job `quick` |
| Lockfile in der CI | `.github/workflows/tests.yml` | alle Jobs installieren `requirements.lock`, Cache-Schlüssel ist das Lockfile |
| Lockfile-Prüfung | `tests/test_requirements_lock.py` | jede Zeile in `requirements.txt` ist im Lockfile genau einmal mit `==` gepinnt und liegt im erklärten Bereich |
| Lockfile im Updater | `deploy/update_server.sh` `prepare_dependencies` | ein geänderter Pin in `requirements.lock` stoppt `betboy-update` wie eine Änderung an `requirements.txt` (Runbook `deploy/VENV_MIGRATION.md`); Shell-Test mit fünf Fällen in `tests/test_server_jobs.py` |

Testkontexte an die Produktion angeglichen: Die Fixtures in `test_challenge_15k.py`,
`test_ev_signal_sources.py` und `test_wettfinder_automation.py` tragen jetzt
`release_eligible_without_lineups` (bzw. `passed`), das der Kontextbauer der Produktion seit dem
23.10. immer schreibt (`challenge_engine.py`, `context_release_eligible`). Ohne das Feld galten
unter `floor` alle Testkandidaten als nicht freigegeben; die Tests prüften dann nichts.

## Gefundene Fehler im Produktionspfad `floor` (behoben, je mit Regressionstest)

Die Fehler 1–4 treten nur auf, wenn Quoten unterschiedlichen Alters zusammenkommen oder gar keine Quote
ankam; das Live-Dokument vom 28.10. war nicht betroffen (Lader nimmt es an, 0 zurückgehaltene
Zeilen, 15K-Snapshot mit 10 Kandidaten, Freigabe- und Modellzeilen identisch).

1. **15K-Ticket brach ab oder liess sich nicht buchen.** Die Preisregel liest alle Quoten der
   letzten 24 Stunden (bester Punkt), das 15K-Hauptbuch speichert und prüft nur den frischen
   Konsens. Ein älterer höherer Punkt ergab `ValueError: ticket odds must lie inside the quoted
   market range` (die ganze 15K-Seite), sonst lehnte `place_ticket` das Ticket ab („Ticket odds are
   not the evidenced executable offer“). Jetzt bepreist `challenge_15k._automatic_challenge_ticket`
   ein Ticketbein unter `floor` mit dem ausführbaren Angebot des frischen Konsenses, und die
   angezeigte Preisprüfung nennt dasselbe Angebot.
   Test: `test_15k_ticket_prices_the_fresh_consensus_not_an_older_best_offer`.
2. **Wettfinder-Karte brach mit „provenance mismatch“ ab.** Dieselbe Ursache in
   `bet_finder_ui.evaluate_reference_price`: Die Entscheidung `BET` trug den besten Punkt der
   Preisregel (bis eine Minute voraus, 24 Stunden zurück), die Karte prüft gegen das Angebot des
   frischen Konsenses. Jetzt wird die Entscheidung unter `floor` mit diesem Angebot bewertet.
   Test: `test_wettfinder_bet_is_priced_at_the_fresh_consensus_offer`.
3. **Leere Website bei einem Lauf ganz ohne Buchmacherquote.** Der Lader verwarf jedes Dokument mit
   veröffentlichten Tipps, wenn `bookmaker_data_used` falsch war (Ausfall oder Budget des
   Quotenanbieters). Unter `floor` bleiben Tipps ohne Quote sichtbar (Owner 23.10.); die Regel gilt
   jetzt nur noch unter `gate`. Test: `test_run_without_any_bookmaker_quote_keeps_its_unpriced_tips`.
4. **15K-Snapshot fiel bis zum nächsten Quotenlauf aus.** `_floor_playable_rows` kopierte die
   Modellzeilen, bevor `_persist_quote_diagnostics` die Preisdiagnose an die Modellzeilen hing; die
   Freigabezeilen unterschieden sich danach in `reference_price_diagnostic`, und
   `build_scheduled_challenge_snapshot` verwarf den Snapshot. Die Diagnose wird jetzt vor der Kopie
   geschrieben. Belegt durch `test_scheduled_artifact_rebuilds_15k_forecast_and_exact_quote` und
   `test_scheduled_15k_uses_full_release_pool_not_normal_top_three` unter `floor`.
5. **Daily3, RisikoBet, Manuelle Suche und 15K-Seite prüften den besten Preis statt des Medians.**
   `quote_publication.publication_quote`, über das diese Verbraucher ein Angebot zulassen, verglich
   unter `floor` weiter das beste Angebot mit 1,20; die Karte prüft seit dem 25.10. den Median.
   Bei 1,10/1,12/1,20 hielt der Wettfinder den Tipp zurück, Daily3 schlug ihn vor (der Fall
   „Hammarby 1–4 Tore“ vom 25.10.). Jetzt entscheidet unter `floor` überall der Median; das
   zugelassene Angebot bleibt das beste reale. Test:
   `test_public_admission_checks_the_median_for_every_consumer`.

## Bewusst als `gate`-Vertrag markiert

41 Tests und 7 Parameterfälle beschreiben nur den alten Vertrag und tragen `@pytest.mark.price_policy("gate")`:
Statuscodes `TOO_LOW`/`UNAVAILABLE`/`THIN`/`STALE` statt `BELOW_FLOOR`/`UNPRICED`, Pflicht
bestätigter Aufstellungen, Konsens statt bester Punkt als angezeigter Preis, Buchmachernamen und
Mindestquote auf der Karte, Daily3-Mindestquote aus dem Risikomodell statt 1,20. Fünf Tests prüfen
statt eines Pins beide Verträge (`floor_only_pricing()` im Test): fremde und manipulierte Quoten
(unter `floor` wird die Zeile zurückgehalten, unter `gate` das Dokument), Tennis/E-Sport ohne Quote,
Lebensdauer des Tipps (24 h statt 150 min) und Median statt Bestpreis.

## Ergebnis

Lokal (Windows, 28.10.): `tests/test_price_floor_policy.py` 33 Tests grün (davon 5 neue
Regressionstests), Lader-Suite 59 Tests unter beiden Preisregeln grün, 15K-Suiten 178 Tests unter
`gate` grün; Ruff ohne Befund. Der vollständige Nachweis ist der CI-Job `price-policy` dieses PRs
(Ubuntu, beide Preisregeln, 27 Suiten).

## Nicht Teil dieser Massnahme

Die Vollsuite bleibt manuell (≈ 1,5 h). Der installierte Updater auf dem VPS wird nicht ersetzt;
die neue Lockfile-Prüfung greift, sobald `betboy-update` aus diesem Stand installiert wird. Der
No-Backup-Release-Helfer prüft `requirements.txt` bereits selbst und bekommt die Lockfile-Zeile im
nächsten Release.
