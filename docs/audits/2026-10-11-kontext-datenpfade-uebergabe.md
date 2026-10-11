# Kontext-Datenpfade – tatsächliche Übergabe am 11.10.2026

Auf Nutzerwunsch wegen Tokenende pausiert. Dieser Bericht dokumentiert WIP,
keinen abgeschlossenen Modellnachweis und keine Veröffentlichung.
Die vollständige aktuelle Prioritätenliste steht oben in `TODO_AKTUELL.md`.

## Git und Eigentum

Kanonischer Checkout `C:/Projekt/BetBoy/betboy-app`, Branch main.
Verifizierte Basis: `e9eea811b85b124b797c0d995b6cdbbe8187c6b5`.
Neue Codeänderungen nicht committed/pushed/deployed. Git diff --check grün;
Windows LF/CRLF-Warnungen sind keine Testfreigabe. Inherited untracked Dateien
(.playwright-cli, alte Auditberichte, Landing-/Stripe-/Storage-/Browseroutputs)
unberührt lassen. Nicht `git add .`, nicht reset/clean.

### Taskdateien – bestehend geändert

- challenge_15k.py
- context_models/evaluator.py
- context_models/football_joint_context.py
- context_models/football_original_publication.py
- context_models/football_training.py
- context_models/training_contracts.py
- football_model_refresh.py
- scripts/tennis_daily.py
- tennis/live_context.py
- tennis/predict.py
- tests/test_football_context_provider.py
- tests/test_football_joint_training.py
- tests/test_football_joint_worker_integration.py
- wettfinder_automation.py

### Taskdateien – neu/untracked

- context_models/football_readiness.py
- context_models/football_roster_pool.py
- context_models/tennis_point_original.py
- context_sources/football_enrichment.py
- football_context_decisions.py
- scripts/prepare_football_context.py
- tests/test_football_context_decisions.py
- tests/test_football_context_readiness.py
- tests/test_football_deferred_decisions.py
- tests/test_football_enrichment.py
- tests/test_football_roster_pool.py
- tests/test_football_training_decision_binding.py
- tests/test_tennis_point_original.py

`football_joint_worker.py` / `context_transport.py` müssen für v2 noch angepasst
werden, sind beim Abbruch NICHT geändert. Deren Anschlussauftrag war an
day_timeout_repair vergeben; Agent vor Änderungen unterbrochen. Alle
Implementierungsagenten sind gestoppt/interrupted oder abgeschlossen.

## Tatsächliche Reparaturen

Historische Detailabfragen werden nur für aktuell konsumierte Torbasis-Spiele
reserviert, nativ gebunden und von demselben produktiven Observer aufgenommen.
Gemeinsame 4×20-ID-Grenze umfasst alle Batches, auch Fehler verbrauchen Budget.
Neueste Summary ohne Spieler kann keinen früheren Full-Detail-Clock erben;
dann echter neuer GET oder unknown. Quoten/Rendite/Resultate wählen keine Fälle.

Ein späterer Kontext-Cutoff ist nicht mehr frei wählbar: immutable nativer
Decision-Proof bindet Original, vollständige source revision und tatsächliche
Prematch-Uhr. Storage zuerst ALLEN Originalen, dann max32/32KiB decisions,
dann optionalen Vergleichen. Reuse des ersten echten Proofs erlaubt; unbekannter
Folgebatch darf ihn weder bei identischem Key noch voller Queue verdrängen.
Neuinsert-Uhr nach Vorbereitung und nochmals vor Commit geprüft.

Player-ID-Regressionsspalten waren für Mannschaften mit unterschiedlichen
Spielern nicht gemeinsam nutzbar. Neuer v2-Vertrag poolt Verlust/Zuwachs
getrennt als gewichtete 90-Minuten-Exposition. Das verhindert Wegheben durch
Ersatzspieler, liefert aber noch keine individuelle Spielerqualität. Daten
mit missing/stale/conflicting bleiben missing. Alte v1-Featurevektoren bleiben
exakt unverändert, Config-v1 kann keine neuen Poolspalten konsumieren.

POINT-Tennis hält tatsächliche Holds, Anchor und Marktdistribution gesondert
fest, rekonstruiert sie aus echtem immutable ATP/WTA-Modellstate. Der alte
Winner-v1-Vertrag bleibt unverändert. Finalscore benötigt genaue native
Paarung, Tour, gleichzeitig berichtete beidseitige Satzdaten und Winnerflag.
Es gibt keine zusätzlichen Resultatzeilen, Aufschlag-Trials, erfundenen
Matchzeiten oder natives Best-of. Die alte Winnerkorrektur bleibt am
POINT-Pfad zu Recht deaktiviert: Winnerlabel identifiziert keine zwei Holds.

## Offene fachliche und technische Arbeit

1. v2-Worker und numerische Transportreferenz fehlen (Details oben im TODO).
2. Readiness-Speicher-/Kohortenvertrag ist noch nicht für mindestens200 finale
   Spiele PLUS Train/Tune tragfähig belegt. Bestehende 64-MiB-Kumulierung zählt
   ca.1,16-MiB expandierte Originale und Quellen mehrfach je Event; gleichzeitig
   werden alle aufgelösten Cases gehalten. Headerbudget128MiB beim Evaluator
   ebenfalls prüfen. Kein Runtimebudget blind erhöhen oder Tests amputieren.
3. Öffentlicher Fußball-Effektpfad ist noch nicht fertig: interne Vergleiche
   verwenden ausdrücklich approval=None. Bei echter Freigabe muss komplette
   Jointverteilung samt ALLEN abhängigen Marktwerten, Kalibrierung,
   Unsicherheits-/Auswahlmetadaten konsistent neu erzeugt werden, kein p-Patch.
4. POINT-kompatibler Fit/Score-Outcome-/D2-Abnahmevertrag fehlt weiterhin;
   native Satzresultate sind dafür Vorbereitung, nicht fertiger Trainingsfit.
5. Echte Tenniszeiten und bestätigte native Verletzungsdaten fehlen in den
   vorhandenen Feeds. TA-Turnierdatum ist kein Matchstart; ESPN scheduledStart
   kein tatsächliches Ende. Nicht namensbasiert/mit geratenen90Minuten verbinden.
6. Fußball mindestens200 unabhängige Testspiele plus Training/Tuning und drei
   zeitliche Blöcke fehlen; Bestand in Produktion8 vollständige/80teilweise
   Originale. Null Trainingcases/Effekte/Approvals. Technische Tests ersetzen
   den gepaarten historischen Qualitätsnachweis nicht.

Quellenprüfung aus dieser Sitzung: historische Tennis-CSV-Minuten allein haben
keine tatsächlichen nativen Match-Start/Endzeitbindungen. WTA-Verletzungsnews
können einzelne verifizierte Meldungen belegen, keinen kompletten Kaderstatus.
MeteoSwiss-Freeforecast ist geografisch Schweiz; keine weltweite Ersatzquelle.
Open-Meteo-Free-Nichtkommerziell nicht still für die bezahlte App einsetzen.
Keine neue Subscription, bezahlte Quelle oder Autorität annehmen.

## QA und Wiederaufnahme

Exakte XMLs und Laufstatus im ersten TODO-Block. Alle Runden überlappen.
Der Session87305-Lauf ist beendet: 34 bestanden, 1 Fixturefehler, Exit1,
369,05s; mit alten Testbytes geladen, keine Freigabe. Neue Fixturekorrektur
darf nur durch eine neue gefrorene Runde bestätigt werden.
Letzte eigenständige v2-Poolrunde10/10 ist grün, aber deckt fehlenden Worker und
Speichervertrag nicht ab. Vollsuite NICHT erneut abgeschlossen.

Nach Reparatur sourcefreeze; whole-module QA einschließlich Original-,
Sourcecapture-, Deferred-, Jointtraining-, Readiness-, Dataset-, Experiment-,
Evaluator-, Activation-, Transport-, Wettfinder-/Challenge-/POINT-Nachbarn.
Launcher externes TCP geblockt; neue basetemp unter externem Projektoutput.
Keine Produktionsbytes während Hash-/Evaluator-QA editieren.

Danach expliziter scoped Commit/Push. VPS: SSH-Alias betboy-vps,
Repo/venv `/opt/betboy/app` / `/opt/betboy/venv`, Serviceuser betboy.
Natürliches freies Timerfenster, FF-only, offlineimports und beide Healthchecks,
forecastJSON-Hashes vorher/nachher. Kein Backup, Jobabbruch, Extrascan oder
Datenbereinigung. Alten Deployhelper nicht unverändert wiederverwenden.
