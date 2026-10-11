# Eishockey: tatsächliche Saison statt festem 2025/26-Vertrag

Stand: 11. Oktober 2026. Quellenprüfung und Offline-Regressionsprüfung; keine
zusätzliche Sport- oder Provider-API-Abfrage, kein Backup, keine Änderung alter
Prognosen oder produktiver Daten.

## Reproduzierbare Ursache und Korrektur

`context_sources/team_sports_binding.py` erzeugte einen nativen NHL-Spielvertrag
nur für die ausdrücklich gemeldete Saison `20252026`. Ein korrekt gebundener
`20262027`-Datensatz blieb deshalb ohne nativen Eventvertrag. Zusätzlich akzeptierte
`context_models/ice_hockey.py:hockey_scope` ausschließlich die alte Kombination
aus Saison und Regelversion.

Beide Stellen verwenden jetzt einen kleinen, unveränderlichen Bestand aus genau
zwei ausdrücklich geprüften Saison-/Regelversionen: 2025/26 und 2026/27.
Unbekannte Jahre, Preseason, falsche Datentypen, eine alte Regelkennung mit neuer
Saison und eine neue Regelkennung mit alter Saison werden weiterhin abgelehnt.
Der tatsächliche native Saisonwert bleibt maßgeblich; kein Wert wird aus
Kalenderdatum oder Teamnamen konstruiert.

Der unveränderte Poisson-/Skellam-Modellpfad und die Trennung zwischen regulärer
Spielzeit und Sieg inklusive Verlängerung/Penaltyschießen bleiben erhalten.
Die Modellwahrscheinlichkeit wird durch diese Vertragskorrektur nicht geändert.

## Aktuelle Primärquelle

Die [offizielle NHL-Regelbuchseite](https://www.nhl.com/info/video-rulebook)
verweist auf die aktuelle Ausgabe. Das
[offizielle Regelbuch 2026/27](https://media.nhl.com/site/asset/public/ext/2026-27/2026-27Rules.pdf)
wurde ausschließlich im Arbeitsspeicher geprüft:

- 19.331.737 Bytes; 232 PDF-Seiten.
- SHA-256: `c6c1680c4aa26b53663882b21fd49fcf450e1f236fc6b09f0ea266ba34f1c69e`.
- Regel 77: reguläre Spielzeit aus drei 20-Minuten-Abschnitten.
- Regel 84: reguläre Saison mit begrenzter Verlängerung; Playoffs mit
  20-Minuten-Verlängerungsabschnitten bis zur Entscheidung.

Es wurde keine PDF-Datei dauerhaft gespeichert und keine NHL-Spieldatenabfrage
ausgeführt. Die PDF-Quelle ist ein Regelbeleg, keine Spieler-, Ausfall-,
Torhüter- oder Modellqualitätsfreigabe.

## Keine Übertragung alter Effektfreigaben

Der ursprüngliche 2025/26-Datensatz wird nicht umgeschrieben. Neue Aufzeichnungen
behalten die neue native Saison, eigene Eingabeidentität und eigene Belege.
Effektabdeckung bindet den vollständigen Scopehash und die saisongebundene
Spielervokabel. Die Regression weist nach, dass ein alter 2025/26-Effekt nicht
auf den neuen 2026/27-Merkmalsvektor angewendet werden kann. Fehlende native
Regel-/Besetzungs-/Torhüterinformationen bleiben weiterhin fehlend.

## Schweiz und weitere Ligen

Das bestehende Scanner-, History-, Identity- und Preisrouting ist NHL-spezifisch.
Die [offizielle API-Sports-Hockey-Dokumentation](https://api-sports.io/documentation/hockey/v1)
bestätigt einen eigenen Liga-ID-Namensraum und vierstellige Saisonfilter. Diese
IDs dürfen nicht aus dem offiziellen NHL-Namensraum übernommen werden. Die
Dokumentation enthält kein vollständig belegtes aktuelles Schweizer/Top-20-
Ligaangebot für unseren Zugang. Deshalb wurden keine Liga-IDs geraten und keine
zusätzlichen Ligen als funktionsfähige Abdeckung ausgegeben.

Für zusätzliche Ligen fehlen tatsächliche Katalogbelege sowie überprüfte
Schedule-/Historien-/Regulation-OT-SO-/Ergebnis- und Marktzuordnungen. Das ist
weiterhin eine konkrete Daten-/Adapterabhängigkeit, nicht mit dem Saisonfix
erledigt.

## Softwareprüfung

- Gezielter Offline-Lauf: 294 Tests bestanden.
- Breiter Hockey-/Native-/Capture-/Preis-/Historienlauf: 896 Tests bestanden,
  ein erwarteter Skip; 72,42 Sekunden; Exit 0.
- Neuer aktueller Event-ID-Fall danach separat: ein Test bestanden.
- `git diff --check` für die geänderten Vertrags-/Testdateien: bestanden.

Die ursprüngliche Modellrechnung, alte Scopebytes, abweichende Regelpaare und
die Verhinderung eines alten Effekts auf neuem Saisonvokabular sind abgedeckt.
Diese Softwareprüfungen sind keine neue empirische NHL-/Kontextqualifikation und
keine Behauptung besserer Rendite. JUnit-Belege stehen außerhalb von Git unter
`C:/Projekt/BetBoy/output/hockey-seasons-20261011/`.
