# Spielerbelastung aus Verein und Nationalteam – 12.10.2026

## Behobene Ursache

Die native Spieler-ID war vorhanden, der Fußball-Kontextpfad las aber nur die
im Vereins-/Grundmodell enthaltenen Ereignisse. Länderspielminuten außerhalb
dieses Pools fehlten. Mehr Tore oder jüngste Mannschaftsergebnisse ersetzen
keine Prüfung individueller Belastung.

`football_player_history` erweitert ausschließlich den Kontext derselben
Spieler um bereits gespeicherte Ereignisse. Ganze Revisionspools werden gelesen,
keine Namenszuordnung, Gegnerexpansion oder neue historische Modellpopulation.
Maximal4096 Receipts/4MiB Quellen und512KiB Veröffentlichung bleiben erhalten.
Aktuelle Einsätze werden innerhalb des bestehenden20-ID-/Ein-GET-Budgets
bevorzugt. Nicht gespeicherte Nationalteamspiele werden nicht erfunden.

`football_player_load` trennt beobachtete7-/14-Tage-Minuten von Vereinsrolle
und tatsächlicher Erholung. Zeitfenster beziehen sich ausdrücklich auf geplante
Termine. Unbekannte Minuten sind nicht null. Ein Ergebnisempfang ist lediglich
eine Erholungsuntergrenze; spätere Wiederholungsabrufe setzen sie nicht zurück.
Ein früher angesetztes, tatsächlich später beendetes Spiel kann maßgeblich sein.

Die separate v3-Merkmalsversion nutzt den bestehenden gemeinsamen Torvertrag.
Neue Eingänge werden gelernt, nicht pauschal mit Prozentabschlägen belegt.
Training und Live-Reader verwenden dieselbe Auswahl. Ungeprüfte interne
Vergleiche verändern weder öffentliche Modellmärkte noch Geldbuchungen.

## Tatsächlicher Produktionsbefund

Lesende Prüfung12.10.2026,12:40UTC:0 aktive Effekte und0 Freigaben; aktive Slots
sind ausschließlich ATP/WTA. Begrenzte Probe aus11 bereits referenzierten
Fußballereignissen:654 Receipts,1,24MB;470 neueste Spielereinträge/433IDs,
381 bekannte Minuten,89 unbekannt,0 tatsächliche Spielendzeiten.
Nur Vereinswettbewerbe283/106/244 in dieser Probe. Keine belegte Nationalteam-
Überschneidung in der Probe, aber auch kein Nachweis global fehlender Daten.
Kein globaler Payloadscan, nur read-only/query-only mit Abbruchgrenzen.

Zusätzliche kleine Binding-Prüfung12:50UTC:95 insgesamt,81 unter128KiB gelesen
(5,61MiB),14 größere nicht expandiert. Darin33 native Ereignisse, davon7
`captured` und26 nur`partial`,43 Bindings ohne native Eventidentität. Alle81
`not-evaluated`. Selbst die obere Schranke95 unabhängige Bindings genügt nicht
für200 unberührte Testspiele neben Training und Abstimmung. Revisionen sind keine
neuen unabhängigen Spiele.

## Prüfung und klare Restgrenze

Unabhängiges Diffreview ohne kritischen/wichtigen Funktionsbefund. Die ursprüng-
liche77/78-Testrunde ist kein PASS:26 vollständige synthetische Fixtures liefen
in die bestehende512KiB-Transportgrenze. Vollständige24 Fixtures/22Spieler,
also keine herabgesetzte Liga-Mindeststichprobe, bestanden5/5 Integrationen.
Große reale Captures können weiterhin vor Speicherung abgelehnt werden.
Der finale exakte isolierte Release-/Nachbarlauf bestand273/273,0 Skips,229,94s.
Erste Runde272/273: Sandbox blockierte atomare HMAC-Testdateiverknüpfung, kein
Modellfehler. Kompletter unveränderter Lauf mit normalen Dateirechten danach
bestanden; keine Tests entfernt, externes Netzwerk blockiert. XML:
`C:/Projekt/BetBoy/output/player-load-20261012/release-final.xml`.
Deploymentbeleg folgt im aktuellen TODO. Keine Testzahl bedeutet nachgewiesene
bessere Wettqualität; dies ist kein erneuter Vollsuite-PASS.

Nicht erledigt: ausreichende echte Personal-/Belastungsdeckung, zeitgetrennter
qualifizierter Fit und owning Freigabe. Zusätzlich große Readiness-/Transport-
grenzen sowie fehlender Spieler-/Zeitindex vor Aktivierung prüfen.
Altes v2-/Entscheidungs-/Tennis-WIP bleibt unveröffentlicht.
Kein neuer Backup, zusätzlicher Sport-/API-Scan oder historische Umschreibung.
