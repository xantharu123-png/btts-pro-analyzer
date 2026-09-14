# 14.09.2026: konkrete Laufzeitkorrektur, Deployment weiterhin offen

Ausgangspunkt: Reparaturbranch `078ca7379ab56b7799f0e6ef8f0e79ce7336cc92`.
Der Nutzer verlangt die tatsächliche Fehlerbehebung. Keine Löschung,
Quoten-/Modellfreigabe oder Wiederverwendung verbrauchter QA-Aufträge.

## Frische Produktionsdiagnose

SSH-Abgleich ab 06:46 UTC: App-HEAD weiterhin
`2dd1116b68f3d94e9c24338c6c9dff9b01799221`; installierter Updater weiterhin
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
App aktiv; Tennis und Wettfinder haben Exit 1.

- Tennis: WTA-Rebuild HTTPError; anschließender Tages-Scan Timeout nach 900 s.
  Pipeline verwirft bisher bei Timeout die komplette bisherige Kind-Ausgabe.
- Öffentliche WTA-Datei `2026w/2026.xlsx`: HTTP mit/ohne www ergibt auf dem
  VPS 503; HTTPS mit/ohne www TLSV1_ALERT_INTERNAL_ERROR. Kein TLS-Bypass,
  keine erfundene Ersatzquelle und kein alter Stand als frisch ausgegeben.
- Wettfinder 06:37 UTC: 73 Modellprognosen, Fußball abgeschlossen. Der eine
  operative Fehler kommt aus `forecast_evidence.settlement`:
  `football:result_identity_mismatch`. Tennis-Modellrefresh dort unverändert
  ohne eigenen Fehler. Nicht als fehlende Fußballberechnung oder Quotenfehler deuten.
- Kontextdatenbank 600219648 Byte (rund 572 MiB), 265298 Contents:
  ESPN 133271 event_status + 108176 workload; API-Football 13818 availability,
  3042 base_fixture, 6586 confirmed_lineup, 405 match_outcome.
  31 Kontext-Snapshots belegen 66373102 Payload-Byte, maximal 3019231 je Snapshot.
  Das beweist Wachstum, nicht beschädigte Daten oder exakt doppelte Receipts.
- Begrenzte offene Ergebnisprobe fand Fixture 1505529 mit Anstoß
  13.09.15:30 UTC und Teams 2324/2328. Seine letzte gespeicherte Basisbeobachtung
  stimmt damit überein. Der konkrete aktuelle Resultat-Unterschied ist damit
  NICHT geklärt; keine gelockerte Ergebniszuordnung oder falsche Abrechnung.

## Implementierte Korrektur

`PreparedTennisHistory` validiert die ganze bereits ausgewählte Tour-Historie
einmal beim Aufbau und hält eigene unveränderliche JSON-Bytes. Für eine Karte
werden alle Revisionen jedes jemals mit einem Beteiligten verknüpften Events
sowie das Ziel-Event ausgewählt. Damit bleiben spätere Teilnehmerwechsel,
Rücknahmen, Terminänderungen und Konflikte erhalten. Unbeteiligte beschädigte
Receipts werden vor jeder Projektion weiterhin abgewiesen.

`LiveWorker.finish` baut diesen Index einmal pro Tour/Entscheidungszeitpunkt.
Es speichert weiterhin die VOLLSTÄNDIGE frühere `observation_refs`-Liste im
Snapshot. Keine Datenbankzeile, Wahrscheinlichkeit, Mindestquote, empirische
Freigabe oder historische v3-Bedeutung wird geändert. Es ist noch keine
Optimierung sämtlicher `bind_pending`-Lesezugriffe oder der ersten Volllektüre.

Die reine Feldnamenklassifikation wird mit maximal 512 Namen von höchstens
128 Zeichen memoisiert; keine Datenwerte oder Gültigkeitsentscheidungen.
Andere/längere Namen gehen unverändert durch die ursprüngliche Funktion.

Die Tennis-Pipeline erzwingt ungepufferte Kind-Ausgabe und protokolliert bei
Timeout maximal die letzten 2500 Zeichen einschließlich Byte-Ausgabe. Timeout
bleibt ein Fehler. Das erhöht keine Laufzeitgrenze und macht keinen Lauf grün.

## Nachweise

- Neue Regressionen zunächst rot; eigene Fixture-Sortierannahme korrigiert.
  Ein früher Testaufruf ohne eigenes `--basetemp` scheiterte außerdem an der
  Windows-Temp-Verzeichnisberechtigung. Keine Rechteänderung/Aufräumaktion.
- Enge Integration: 152, danach mit erweiterten Gegenfällen 205 bestanden.
- Abschließende gezielte Kombination: **917 bestanden, 1 Plattform-Skip**,
  77,17 s, Exit 0. XML `.pytest_tmp/tennis-release-20260914-04.xml`.
  Enthält Live-/Status-/Kontext-/Transport-/History-/Updater-/Wettfinder-/
  Forecast-Settlement-/Daily3-Auswahltests. Keine vollständige Repository-Suite.
- Eigener Diff geprüft, `git diff --check` sauber. Kein unabhängiges Agentenreview.

Begrenzter echter Linux-Vergleich als betboy, nur In-Memory-Code und SQLite
mode=ro, keine Datei-/Dienst-/Produktionsdatenänderung; maximal 40 CPU-/50
Wandsekunden. Vollständige alte und projizierte Feature-Bytes verglichen:

| Messumfang | Ergebnis |
| --- | --- |
| Physisch gelesene Beispielreceipts | 1000, ausdrücklich keine Vollhistorie |
| Am ursprünglichen Entscheidungszeitpunkt ausgewählt | 725 |
| Zugehörige Event-Historie | 6 |
| Berechnungen | 10 |
| Vollständiger Featurepfad | 2,563810719 CPU-s |
| Indexaufbau + projizierter Featurepfad | 0,348907847 CPU-s |
| Feature-Bytes / vollständige Snapshot-Referenzen | jeweils exakt gleich |

Quell-SHA256: contracts `0faef3956846aaa5386b25517a66da9c60d5e1cf325bb7cf65eddda0fb2f3ee5`,
projection `61b04f4ce61b184706ff2dcae003eced24a9e43f53834633372f5dab9279818f`.
Der erste kleine Messaufruf wurde korrekt wegen nicht passendem historischem
Basis-/Entscheidungszeitpunkt abgewiesen; danach tatsächlichen Ursprungscutoff
verwendet. Kein Eingriff in historische Daten oder Modellzeitstempel.

## Noch nicht erledigt

Kein dritter großer QA-Auftrag, keine C/B-Gesamtabnahme, kein Updateraustausch,
kein main-Merge und kein VPS-Pull. Die gemessene Beschleunigung eines Teilpfads
ist kein Beleg, dass der gesamte Tageslauf jetzt unter 900 s liegt.

Der bisherige Updatevertrag verlangt weiterhin vier vollständige historische
QA-Beobachtungen plus C/B-Wachstum und Restore. Eine gezielte Änderung dieses
festgefahrenen Verfahrens bedarf einer ausdrücklichen Entscheidung: betriebliche
Code-/Schema-/Backup-/Restore-/Startprüfung von umfangreichen historischen
Analyseprüfungen trennen, ohne Geldkonten-, Migrations- oder Rollbackprüfungen
zu entfernen. Diese Alternative wurde hier noch nicht implementiert.

WTA-Quelle und tatsächlicher Fußball-Resultatkonflikt sind ebenfalls offen.
