# Hockey Top 5: verifizierter Ausgangspunkt, nicht fertiggestellt

Auftrag: NHL, Schweizer National League, SHL, Liiga und DEL mit echter
Gegnerstärke, Form, Torhütern, Ausfällen und Belastung ausbauen; vorhandene oder
kostenlose aktuelle Daten, Tests und VPS-Deployment, keine Backups.

## Ausgangsprüfung vor dem späteren Quellenpatch

**Zu diesem Ausgangszeitpunkt kein vollständiger Fünf-Ligen-Ausbau und kein neuer Hockey-Deploy.**
Der damals geprüfte Produktstand war `084d8d3da441d014c9b7ff02077cd7daea6d0e26`.
In dieser Ausgangsprüfung wurden keine Produktivdateien, Modelle, Geldbuchungen oder Serverdienste
verändert; keine Datenbankkopie, Sicherung, Bereinigung oder kostenpflichtige
Bestellung. Nur diese Dokumentation und lokale lesende Prüfhelfer wurden erstellt.

### Tatsächlicher Modellstand

- `sports_prematch.py` schätzt Angriff, gegnerische Defensive und Heimvorteil
  gemeinsam. OT/Shootout werden separat und liga-/variantengebunden behandelt.
- Angezeigte letzte 5/10 Spiele sind keine zusätzliche numerische Kurzform.
  Der aktuelle Basisfit hat keine Recency-Gewichtung.
- Akute Ausfälle, bestätigte Starter und individuelle Belastung verändern
  die aktuelle öffentliche Hockey-Wahrscheinlichkeit nicht.
- `context_models/ice_hockey.py` enthält echte NHL-Lograten-/Expositionsmechanik,
  aber seine synthetischen Tests sind keine empirische Freigabe. Der vollständige
  Hockey-Trainings-, Outcome-, Replay- und Evaluatorpfad fehlt weiterhin.
- Keinen NHL-Effekt auf fremde Ligen übertragen. Gewinner-Goalie nach dem Spiel
  ist keine vor dem Spiel bestätigte Starterinformation. Kaderliste ist keine
  vollständige Ausfallliste; vergangene Startzeit ist keine tatsächliche Endzeit.

### Bereits vorhandene Produktionsdaten: ohne zusätzlichen API-Scan gelesen

`runtime_state/sports_completed_history.db`, ausschließlich SQLite `mode=ro` und
`query_only=ON`, kompakte Aggregation statt Payload-Export:

| Provider / Saison | Unterschiedliche Ereignisse | Revisionen |
| --- | ---: | ---: |
| NHL / 20252026 | 1.528 | 1.528 |
| NHL / 20262027 | 151 | 151 |

In diesem Cache gibt es keine API-Hockey-Ergebnisrevisionen. Die 151 NHL-Ereignisse
sind **nicht** automatisch 151 kausal zulässige Testfälle: Spieltyp, Ergebnisumfang,
Zeitgrenzen und echte vorherige Empfangszeit müssen weiterhin stimmen.
Alte Daten erstmals heute zu laden erzeugt keine damals bekannte Verletzungslage.

### Kontozugang und kostenlose Alternativen

Der begrenzte Kontotest meldete aktives API-Hockey **Free**, 100 Anfragen/Tag.
Der Katalog führt alle fünf Ligen für 2026. Der gezielte Schweizer
Saisonhistorienaufruf für 2026 wurde mit Anbieterfehler `plan` zurückgewiesen
(Antwort nennt 2022–2024); eine aktuelle Tagesabfrage lieferte dagegen 174 Spiele.
**Aktuelle Spielpläne sind also erreichbar; aktuelle Saisonhistorie ist damit
nicht bewiesen.** Keine Umgehung der Saisonberechtigung über andere Parameter.
Die anderen drei europäischen Saisonaufrufe wurden nicht zusätzlich wiederholt.

| Liga | Verifizierte öffentliche technische Daten | Noch fehlender Nachweis |
| --- | --- | --- |
| NHL | Eigener bestehender nativer Spielplan-/Ergebnisanschluss | Tatsächliche qualifizierte Starter-/Ausfall-/TOI-Aufnahme und owning Trainingspfad |
| SHL | Offizieller 2026/27-Spielplan, Periodenergebnisse, Boxscore/Goalies | Vollständige Ausfälle, Prematch-Startersemantik und Nutzungsfreigabe für Produktaufnahme nicht verifiziert |
| Liiga | Offizielle 2026/27-Spiele, Perioden, Spieler/Goalies | Vollständige Prematch-Abdeckung; §5 verlangt für öffentliche Informationsprodukte schriftliche Zustimmung |
| DEL | Offizielle Spiele/Perioden, Lineup, Boxscore und Goalie-Einsätze | Vollständige Prematch-Abdeckung; Website-Kopien nur privat/nichtkommerziell, weitergehende Verwertung zustimmungspflichtig |
| National League | Öffentliches SIHF-Game-Center-HTML mit Perioden und tatsächlicher Goalie-Spielzeit | Stabile Spieler-ID nicht verifiziert; vollständige Ausfälle/Starter und Bedingungen für öffentliche Produktaufnahme offen |

Nutzungsbedingungen sind keine Aussage darüber, welche einzelnen Fakten
urheberrechtlich geschützt sind. Es wurde aber keine pauschale kostenlose
Produktlizenz nachgewiesen. Persönliche Nutzung ist von öffentlicher
Weiterveröffentlichung zu trennen; kein kostenpflichtiger Zugang und keine
Kontaktaufnahme ohne zusätzliche Nutzerentscheidung.

Quellen:

- [API-Hockey](https://api-sports.io/documentation/hockey/v1)
- [SHL Bedingungen](https://www.shl.se/Villkor-och-integritetspolicy)
- [Liiga Bedingungen](https://www.liiga.fi/en/league/kayttoehdot)
- [DEL Bedingungen](https://www.penny-del.org/intern/impressum)
- [SIHF Bedingungen](https://www.sihf.ch/de/nutzungsbedingungen/)
- [SIHF öffentlicher Beispiel-Spielbericht](https://www.sihf.ch/de/game-center/game/spielerstatistik/20271105000072)

Der SIHF-Vertragszugang `data.sihf.ch` wird nicht umgangen; die
National-League-Website sperrt `/api` per robots. Keine dortigen Direktabrufe
als Ersatz für eine Freigabe anschließen.

## Konkrete nächste Schritte, nicht als erledigt markieren

1. Für die europäischen Ligen einen tatsächlich zugänglichen und für den
   gewählten privaten/öffentlichen Betrieb passenden kostenlosen Quellenumfang
   bestätigen; fehlende Zustimmung erfordert externe Koordination.
2. Native Provider-/Team-/Spieler-/Saison-/Regelidentitäten und Regulation/OT/SO
   erhalten, nie fremde Quellen als NHL/API-Hockey umetikettieren.
3. Quellengebundene aktuelle Ergebnisse und tatsächliche Auftritte mit echter
   Empfangszeit in vorhandene Beobachtungsspeicherung führen. Keine neue DB.
4. C3-Hockey-Trainings-/Outcome-/Replay-/Evaluationspfad vervollständigen.
   Form und beobachtete Spielplanbelastung mit geschätzten Koeffizienten testen;
   keinen frei erfundenen Goalie-/Verletzungs-/Müdigkeitsabschlag einsetzen.
5. Bestehende zeitgetrennte Abnahme anwenden. Fehlende Testfälle nicht durch
   rückdatierte heutige Quellen ersetzen. Erst dann numerische Kontexteffekte
   öffentlich aktivieren und die freigegebene Implementierung ohne Backup deployen.

## Frische technische Ausgangsprüfung

1.046 Tests bestanden, ein bestehender Skip, 71,56 Sekunden, Exit 0.
Das ist die Hockey-/Team-Sport-Ausgangsregression, **kein Nachweis einer neuen
Implementierung oder besseren Prognosequalität**. Keine erneute 14K-Vollsuite.

Lokale Belege außerhalb Git:
`C:/Projekt/BetBoy/output/hockey-top5-20261016/baseline-01.xml`,
`baseline-01.log`, `inspect_existing.py` und
`C:/Projekt/BetBoy/output/hockey-access-20261016/access-proof-01.log`.

## Spätere begrenzte Quellenkorrektur und Gesamttest

Die anschließende Implementierung beschränkt den regulären Hockeylauf auf
native NHL sowie API-Hockey National League, SHL, Liiga und DEL. Historien
werden nur für tatsächlich benötigte native Liga-/Saisonpaare geladen.
Explizit leere und fehlerhafte Identitäten führen nicht zu breiter Entdeckung.
Fehlende Katalogziele bleiben als Datenlücke sichtbar; Quellenfehler werden
auch über die serialisierte Wettfinder-Brücke sportgetrennt weitergegeben.
Codecommits433bb86 und1d3ca7a; das verändert keine Modellwahrscheinlichkeit.

Die vollständige Offline-QA02 erfasste14.499Tests, behielt alle14.462 alten
IDs und endete mit14.299PASS/98Skips/147bestandenen Untertests und102FAIL.
43 Fehler betrafen den bei der früheren Quotes-Erweiterung unvollständig
aktualisierten Updater-Inventar-/Pin-Vertrag;59 ältere Verbraucherfälle hatten
keine gültigen Preisfixtures oder erwarteten noch unbepreiste öffentliche Tipps.
Dieser rote Nachweis bleibt erhalten, keine fehlerhaften Fälle ausgefiltert.

Reparatur: exakte Acht-Dienste-Prüfung einschließlich Quotes, unveränderte
historische Algorithmus-Pins mit eng rekonstruierter geprüfter Erweiterung;
Preisfixtures und explizite Kartenargumente an den geltenden1,20-Vertrag
angepasst. Alte Richtungs-/Kontextassertionen bleiben erhalten. Neue Fälle
verhindern ein Umschwenken auf die bepreiste Gegenseite und prüfen echte
Tennis-Karten mit fehlender oder1,19-Quote bei erhaltener interner Prognose.

Gezielte Nachprüfungen:512PASS/6bestehende Plattform-Skips,221PASS,
137PASS sowie zwei abschließende Erhaltungsfälle. Unabhängiges statisches
Release-Review ohne Critical/Important-Befunde; Freigabe nur für frische QA.
QA03 auf eingefrorenen Quellen vollständig abgeschlossen:14.438PASS,
98unveränderte Plattform-Skips,147bestandene Untertests, beide Shards Exit0.
14.536gesammelt, keine der14.499QA02-IDs entfernt und alle14.462früheren IDs
erhalten.787 Quellhashes unverändert; keine nachträgliche Testauswahl oder
zusätzlicher Skip. Das ist ein Software- und kein Wett-Renditenachweis.
Commit/main-Push und Produktionsprüfung folgen erst anschließend.

Dieser Quellen-/Wartungsrelease vervollständigt **nicht** die oben beschriebenen
Torhüter-, Verletzungs- und Müdigkeitseffekte. API-Jahresabo noch nicht aktiviert;
neuer Primärquellenvergleich in
[Hockey-Quellen und Alternativen](2026-10-16-hockey-quellen-und-api-abo.md).
