# Auswahlqualität: prospektive Historie und Kohärenz

## Auftrag und Grenzen

Zweistündiger Arbeitsblock am 03./04.10.2026. Keine zusätzlichen Sport- oder
API-Scans, keine neuen Backups, keine Änderungen historischer Geldbuchungen.
Der Metrics-Review-Workflow trennt Datenbasis, Sport/Markt-Segmente und
Qualitätsnachweis. Softwaretests sind kein Beleg für profitable Wetten.

## Konkrete Reparaturen

1. RisikoBet konnte aus einer Fußballverteilung Heimsieg und Remis als getrennte
   Vorschläge für dasselbe Spiel übernehmen. Die vollständige ausgewählte Gruppe
   muss jetzt gemeinsam erfüllbar sein. Dies passiert vor Quotenfilter, Kartenlimit
   und Paginierung. Verschiedene eingefrorene Modellstände werden nicht vermischt.
2. Eine fehlende Best-of-1-Formatbindung im E-Sport ließ Seriensieg und eine Map
   des Gegners fälschlich als vereinbar gelten. Ohne exakten Formatnachweis wird
   keine Vereinbarkeit mehr angenommen; die Wettart bleibt als Einzelvorschlag
   erlaubt. Eine Quote darf keine gegensätzliche Ersatzposition nachrücken lassen.
3. Ein interner Modellpool ist kein Nachweis veröffentlichter Tipps. Die neue
   `runtime_state/consumer_tips.db` protokolliert kleine, tatsächlich angebotene
   Auswahlinventare. Automatischer Wettfinder und standardmäßiger Daily3-Plan werden
   beim normalen Veröffentlichungsablauf erfasst; gerenderte Wettfinder-, Daily3-
   und RisikoBet-Ansichten separat. Keine zusätzliche API-Anfrage. Ein Inventar
   beweist weder einen Kundenbesuch noch eine platzierte Wette.
4. Gleiche Inventare werden nicht bei jedem Browser-Neuladen erneut gespeichert.
   Keine vollständigen Kontexte, Nachweislisten, Konten oder Einsätze. Je Tipp
   höchstens 8 KiB; konkrete Testbelege liegen unter 2 KiB. Dies ist keine Zusage
   unbegrenzter Gesamtspeichergröße: echte neue Auswahlen/Quoten erzeugen neue
   kleine Datensätze. Keine historische Veröffentlichung wird nachträglich erfunden.
5. Ergebnisberichte prüfen tatsächliche Modell-/Teilnehmer-/Zeitbindungen und
   unterscheiden Gewinne, Verluste, offene Ergebnisse, Stornos und Datenfehler.
   Teilnehmerwechsel dürfen nicht das Ergebnis einer alten Paarung übernehmen.
   Veröffentlichten Tipps werden die bei ihrer Erfassung beobachteten Preise
   zugeordnet, nicht ältere Modellpreise oder nachträglich ausgesuchte Bestquoten.

## Aktuelle Produktionsprobe: 30.09.–02.10.2026

Nur interne, prospektiv gespeicherte Modellkandidaten; keine Rekonstruktion einer
damaligen Kunden-Tippliste. Drei abgeschlossene Schweizer Kalendertage, 91 Spiele,
181 deduplizierte Markt-/Seitenprognosen: 107 gewonnen, 71 verloren, 3 offen.
Alle 181 Modellbelege haben vollständige Modell-/Input-Zeiten und Teilnehmerrollen.
Keine Integritätsabweichung in dieser Probe. Mehrere Märkte eines Spiels sind
abhängig und keine unabhängigen Testspiele.
Die optimierte reine Leseabfrage benötigte auf dem VPS 0,561 Sekunden; dieselben
181/107/71/3 Ergebnisse wie vorher. Ein SQL-Laufzeitlimit verhindert endlose Abfragen.

- Fußball: 109 Marktprognosen aus 19 Spielen; 67 gewonnen, 42 verloren.
- Tennis: 39 Spiele; 18 gewonnen, 18 verloren, 3 offen.
- E-Sport: 33 Spiele; 22 gewonnen, 11 verloren.
- Brier-Score gesamt: 0,2128; Log-Loss: 0,6106. Kein geeigneter Vergleichsbaseline
  wurde in diesem Arbeitsblock nachträglich erfunden.
- 113 Preise fehlen, 56 sind veraltet, 12 frisch. Nur elf frische Tennispreise
  sind bereits abgerechnet: hypothetisch −2,00 Einheiten bei gleichen Einsätzen.
  Die vorab definierte Auswahl verwendet den jüngsten gebundenen Quotenpunkt mit
  stabiler Anbieter-Reihenfolge. Die frühere Schätzung mit der jeweils besten
  gespeicherten Quote ergab −2,17; beide sind keine echten Kunden-Geldbuchungen.
- Aktuelle reine Verknüpfungsprobe auf dem VPS: sechs noch bevorstehende
  Fußballprognosen, sechs exakte bestehende Modellbelege. Nur gelesen, keine
  Veröffentlichung zurückdatiert.

## Bedienung der internen Auswertung

`scripts/selection_performance_report.py --db runtime_state/forecast_evidence.db
--from-day YYYY-MM-DD --through-day YYYY-MM-DD` wertet den internen Modellpool aus.
Mit `--history-db runtime_state/consumer_tips.db` werden ausschließlich echte
prospektive Auswahlinventare ausgewertet; `--surface` grenzt die Oberfläche ein.
Leere Historie bleibt leer. Frische, exakt passende Quoten unter 1,20 zählen nicht
zur hypothetischen Einsatzrechnung. Offene/ungültige Belege werden nicht geraten.
RisikoBet-Snapshot-Abrechnungen sind noch nicht an diese neue veröffentlichungs-
gebundene Bilanz angeschlossen; sie erscheinen ausdrücklich als Verknüpfungslücke.

## Noch nicht daraus ableitbar

Keine bewiesene höhere Rendite. Verletzungs-, Wetter- und Müdigkeitswirkungen samt
unabhängigem Qualitätsnachweis bleiben getrennte Arbeiten. Alte Ansichten ohne
Veröffentlichungsbeleg können nicht rückwirkend als Kunden-Tipps ausgewertet werden.
Manuelle Sport-Suchen haben noch keine eigene Inventar-Protokollierung.
Der echte automatische Produktionsnachweis entsteht mit dem nächsten regulären
Wettfinderlauf; die vorhandenen Scanner-Endstatus werden nicht künstlich zurückgesetzt.

## Release-Nachweis

Auswahl-/Historien-Code `25e79a5c71bcd763fd0d5b66e7bb937c98aef427` ist seit
03.10. 21:53 UTC live. 510 betroffene Tests am finalen Commit bestanden. Linux-
Offline-QA blockierte Provideraufrufe; App/Caddy, beide Healthchecks und sieben
Timer geprüft. Kein Backup, keine Bereinigung, keine zusätzliche Modellabfrage.
Wettfinder-Artefakt `17f8d60e04caeda9e8d09e4879e742c42dbf292f765a91f9ab1c22160d33c0cf`
und Risiko-Artefakt `c669c09792f08185c3080c75039659c408fa2bf308840376405cc07d1ba3ac19`
blieben unverändert. Die ersten echten UI-Inventare liegen in 20.480 Bytes,
derzeit drei leere Oberflächeninventare; keine historischen Kundentipps erfunden.
Browser nach Reload ohne neue Fehler; die Neustart-WebSocket-Unterbrechung ist
kein verschwiegenes dauerhaftes Browserproblem.

Die während der Änderungen gestartete breite Suite endete mit 12.256 bestanden,
97 Skips, 111 Untertests und zwei Fehlern in früher importierten Testfixtures.
Aktuelle Dateien dieser beiden Fälle frisch geprüft: 70 bestanden. Nicht als
komplett neu durchgelaufene grüne Vollsuite des späteren Standes darstellen.

## Zusätzlich gefundener Tennis-Vertragsfehler

Beide produktiven ATP-/WTA-Artefakte verwenden intern Schema 2 und zusätzlich
`market_model_version=serve-points-joint-v2`. Der Consumer verlangte bislang
exakt die Schema-1-Felder und Schema 1. Daraus stammen die zwei Tennis-bedingten
operativen Fehlmeldungen im letzten Wettfinder; Fußball selbst hatte null.
Der enge Headerfix unterstützt beide kanonischen Formate, keine unbekannten
Keys/Versionen. Keine Modellrekonstruktion oder numerische Änderung. 229 Tests
und unabhängig 54 Tests grün; beim Eintrag wegen aktivem regulären Tennisjob noch
nicht deployed. Das ist getrennt vom bereits veröffentlichten Auswahlrelease.

Im gekürzten alten Tennislog sind außerdem 24 verschiedene WTA-Prognosen vom
04.–11.09. fälschlich als Best-of-5 gespeichert. Ihr strenger Settlement-Validator
lehnt normale Best-of-3-Endstände korrekt ab. Die volle Anzahl ist aus dem
gespeicherten 2.500-Zeichen-Tail nicht belegbar. Originalprognosen/Geldbuchungen
wurden nicht geändert. Neue Tippqualität oder ein fehlerfreier neuer Tageslauf
wird daraus nicht behauptet.
