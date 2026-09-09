# B4: Native Fußballbelege und kaderbezogene Merkmale

Stand: 9. September 2026. Dies ist ein begrenzter Software-/Quellennachweis,
keine empirische Freigabe und keine produktive Wirkung von Verletzungen.

## Tatsächlich verfügbare Quelle

Genau zwei zusätzlich genehmigte BACKGROUND-Anfragen über den bestehenden
API-Football-Governor: gebündelte Fixtures und Ausfälle, jeweils HTTP 200,
vollständige Einzelseite, ohne Wiederholung oder Redirect.

- Fixtureempfang: `2026-09-09T07:20:32.783563+00:00`.
- Ausfallempfang: `2026-09-09T07:20:32.902895+00:00`.
- Abgeschlossenes Fixture 1570343: 46 Spielerzeilen, 32 bekannte Minutenwerte,
  14 unbekannte Bank-Minuten. Unbekannt wird nicht zu null oder 90 Minuten.
- Künftiges Fixture 1575469: keine bestätigte Aufstellung/Spielminuten.
- Die zehn gemeldeten Ausfälle gehören zum historischen Fixture. Der leere
  künftige Ausfallabruf beweist nicht, dass beide Teams vollständig gesund sind.
- Septemberempfang eines Augustspiels ist kein nachgewiesener August-Prematch-
  Kenntnisstand. Keine historischen Veröffentlichungszeiten wurden erfunden.

Sanitierte Fixture: `tests/fixtures/context/football/api-football-20260909.json`,
SHA256 `0b429c4b8f8aa840261a1557fabf22a4b3dab811d688948a8a800f1475a113fa`.
Keine Schlüssel/Headers, Modell-/Konto-/Ticketänderung; nur die vorhandene
Kontingentreservierung wurde durch die zwei Anfragen geschrieben.

## Implementierte Software

- `context_sources/football.py`: geschlossene native 90-Minuten-Projektionen,
  tatsächliche Receipts, getrennte Aufstellung/Verfügbarkeit/Appearance,
  unbekannte Quellenabdeckung ausdrücklich unvollständig.
- Ganze Team-Kollektionen sind in jedem Mitglied an ihren **vollständigen
  Inhalt** gebunden. Gleiche Spielerliste bei geänderten Minuten/Startrollen
  ist eine andere Revision. Teilprojektionen dürfen keine Mitglieder aus alten
  oder gleichzeitigen widersprüchlichen Revisionen übernehmen.
- Explizite leere Team-Kollektionen ziehen vorherige Aufstellungen/Appearances
  zurück. Sie sind keine Spieler und behaupten weder Gesundheit noch Minuten.
  Frühere Entscheidungszeitpunkte behalten ihre damals empfangenen Daten.
- `context_models/football.py`: erwartete Rollen aus tatsächlich bekannten
  historischen Minuten; bestätigte Aufstellung und gemeldete Abwesenheit sind
  getrennt. Zweifel ohne kausal gelerntes Teilnahmemodell bleiben Szenarien,
  nicht ein erfundener 50-Prozent-Mittelwert.
- Rosterkomponenten verwenden exakt die vorhandenen Venue-/Form-/Prior-/xG-
  Gewichte der unveränderten Basis. Langfristig fehlende Spieler werden nicht
  automatisch ein zweites Mal als zusätzliche Schwächung abgezogen.
- `football_native_provenance` verknüpft ausschließlich exakt passende native
  Fixture-/Team-/Ergebnis-/Receipt-Belege mit dem vollständigen Basisdatensatz.
  Neueste Revision wird **vor** dem Abgleich gewählt; alte passende Ergebnisse
  können keine neuere Korrektur verdrängen. CSV-Pseudojoin bleibt unaufgelöst.
- Begrenzte Provider-Schnittstelle: maximal 20 eindeutige Fixtures und zwei
  kontingentgeprüfte Anfragen pro explizitem Batch. Nur exaktes HTTP 200 und
  vollständige valide Seiten; fehlgeschlagene Endpunkte erzeugen keine frischen
  Beobachtungen. Dieser neue Pfad ist noch kein automatisch aktivierter D3-Job.
- Die Merkmalsversion `football-roster-components-v2` bindet vollständige Basis,
  vollständiges Event einschließlich Termin/Teilnehmer und Preprocessing-Hashes.

## Gegenprüfungen und aktueller Testnachweis

Die unabhängigen Reproduktionen fanden zunächst echte Fehler: Fortleben alter
Spieler/Startrollen, vorgezogene Gültigkeit, Mischkollektionen mit zwölf Startern,
fehlende Rücknahme leerer Kollektionen, HTTP 206/3xx und direkter 45-Minuten-Scope.
Diese Fälle wurden jeweils reproduziert und durch eng begrenzte Regressionen
korrigiert; keine Quote, Wettart oder empirische Qualitätsregel wurde geändert.

Nach der letzten Quellenkorrektur: **101 bestanden**, einschließlich der
**unveränderten zehn** externen Source-/Provider-Repros. Die vollständige
Root-Runde auf `3e9ce2c` plus diesen B4-Arbeitsbytes bestand **3.281 Tests,
15 erwartete Windows-Skips und 97 Untertests** in 70,60 Sekunden, isoliertes
`--basetemp=.pytest_tmp/root-b4-b7-full-01`.

Die abschließende unabhängige Native-/Kollektionsprüfung ist freigegeben:
118 Fokusfälle, 39 zusätzliche Gegenproben und 459 Integrationsfälle bestanden
(überlappende Läufe, nicht addieren). Root las den vollständigen Bericht und
wiederholte 94 Quellen-/Provider-/Native-Fälle einschließlich der 39 neuen
Gegenproben. Alle zehn eingefrorenen B4-Quell-/Testhashes blieben gleich.
Der vollständige Bericht einschließlich SHA-Tabelle ist unter
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-8-final-review-20260909.md`
dauerhaft gesichert. Das ist die begrenzte technische Reviewfreigabe, keine
empirische Freigabe oder bereits aktive Verletzungswirkung.

## Weiter offen

Kausale reale Trainingszeilen, geschätzte Spieler-/Teilnahmeeffekte, echte
200-Event-/Drei-Block-Abnahme, D3-Aufnahme/Snapshot-/Oberflächenanbindung und
Aktivierung. Ein gültiger Inhaltshash beweist interne Konsistenz, keine
Quellenwahrheit oder Prognosequalität. Die unveränderte Basis bleibt nutzbar.
