# Tennis-Spielerindex – kurzer Architekturentwurf

Stand: 15.10.2026. **Schriftliche Spezifikation vom Nutzer freigegeben.**
Freigabe: „Spezifikation freigegeben, weiter mit dem Umsetzungsplan.“
Umsetzungsplan, Migration und Veröffentlichung sind noch nicht freigegeben. Ausgangspunkt ist
Arbeitsbranch `codex/audit-repairs-20261013`, WIP `0ce0687`; der letzte geprüfte
Produktionsstand bleibt `4ece002`. Die fehlgeschlagenen Leistungsmessungen bleiben
in `docs/audits/2026-10-15-tennis-batch-45s.md` dokumentiert.

## 1. Ziel und gewählte Lösung

Historische Tennismerkmale sollen mit den ursprünglichen Zeitstichtagen und
allen zugehörigen Belegen schnell berechenbar werden. Der bisherige Batch
verarbeitet die vier festgelegten Fälle nicht innerhalb von 45 Sekunden: Seine
Spielersuche muss den globalen JSON-Bestand durchgehen. 2.602.717 Kontextbelege
insgesamt und 981.335 ATP-Belege wurden gemessen; die WTA-Zahl ist unbekannt.

**Gewählt: eine abgeleitete Spieler-Spiel-Zuordnung in derselben Datenbank.**
Sie speichert je Tour, Spieler und Spiel den frühesten tatsächlich gespeicherten
Empfangszeitpunkt samt Belegkennung – keine Statistik-BLOBs und keine neue Kopie
der Datenbank. Wiederholte Abfragen desselben Spiels erzeugen keine zusätzlichen
Zuordnungszeilen. Ein zwischenzeitlich beteiligter Spieler bleibt auffindbar.

Alternativen: Die reine Abfrageoptimierung wurde geprüft und reicht nicht aus.
Eine separate Indexdatei würde die bestehenden Schemakataloge zwar unberührt
lassen, benötigte aber eine zusätzliche Konsistenzgrenze zwischen zwei Dateien.
Die gemeinsame Datenbank ermöglicht stattdessen atomare Aktualisierungen.

## 2. Daten und Vollständigkeit

Es gibt zwei neue, intern versionierte Tabellen:

- `tennis_player_events`: Primärschlüssel `(tour, player_id, event_key)`, dazu
  `first_observed_at` und `first_receipt_digest`, als `WITHOUT ROWID`-Tabelle
  mit genau dieser Primärschlüsselstruktur. Gleichzeitige früheste Belege
  werden deterministisch nach Digest gebunden. Ein später eingefügter Beleg mit
  älterem Empfangszeitpunkt muss das Minimum korrigieren.
- `tennis_player_index_state`: eine Zustandszeile mit Version/Projektoridentität,
  Datenbank-Dateiidentität, Quell- und Indexänderungszählern, verarbeitetem
  Quell-Rowid sowie den zugehörigen geprüften Zählerständen; Zustand
  `building`, `ready` oder `invalid`. Kein Änderungszähler gilt allein als
  Vollständigkeitsnachweis: `ready` setzt den lückenlosen Aufbau voraus.

Feste SQL-Trigger invalidieren den geprüften Stand auch bei Schreibzugriffen,
die die neuen Python-Hooks umgehen: neue/geänderte/gelöschte Belege, Änderungen
oder Löschungen von Quellinhalten sowie direkte Änderungen der Zuordnung.
Die Trigger benötigen keine benutzerdefinierten SQL-Funktionen. Eigene
Indexschreibvorgänge dürfen nur nach bekannt vollständig verarbeitetem
Vorgängerzustand einen neuen geprüften Stand veröffentlichen.

Das ist eine Konsistenzprüfung für unterstützte Schreibwege, **kein** Beweis
gegen einen Angreifer, der Quelldaten, Trigger und Kontrollzustand zusammen
beliebig umschreiben kann. Ausgewählte Originalbelege werden weiterhin geprüft.

## 3. Aufbau und laufende Speicherung

Die Migration wird ausdrücklich aufgerufen, nicht beim Rendern einer Seite
und nicht automatisch durch einen lesenden Datenbankzugriff. Sie ergänzt nur
die freigegebenen Tabellen, Trigger und erforderlichen Schlüsselstrukturen.
Alte Belege, Schnappschüsse, Modelle, Tickets und Geldbuchungen bleiben erhalten.

Der einmalige Aufbau läuft fortsetzbar in Quell-Rowid-Reihenfolge. Alle
Quellzeilen werden berücksichtigt; Inhalte werden nur für die bisherigen
ESPN-Kandidaten `event_status`/`workload` geöffnet, niemals Ergebnislabels.
Die bestehenden physischen und nativen Validatoren bleiben maßgeblich.
Physisch gültige, eindeutig anderen Sportarten zugehörige ESPN-Belege werden
ohne Tenniszuordnung als verarbeitet gezählt; widersprüchliche Tennis-/Tour-
Identitäten werden nicht dadurch übersprungen. Insbesondere darf gültiges
NBA-Material den Tennisaufbau nicht blockieren.
Gültige `unknown`-Status, Teilbesetzungen und Teilnehmerkorrekturen dürfen
nicht wegen ihres Status verschwinden. Unverständliche Kandidaten verhindern
`ready`; sie werden nicht als „keine Beteiligung“ behandelt.

Jeder Chunk verbindet gelesene/validierte Quellen, abgeleitete Änderungen und
Fortschrittsmarke atomar. Neue Belege zwischen Chunks bleiben als nachzuholende
Einfügungen erhalten. Ein höherer Rowid darf keine übersprungene Lücke als
verarbeitet markieren. Eine Einfügung unterhalb des bereits bearbeiteten
Rowids invalidiert den Stand ebenfalls. Änderungen/Löschungen bearbeiteter Quellen
erzwingen einen Neuaufbau der abgeleiteten Zuordnung. Erst ein abschließender
Abgleich in derselben Transaktion darf `ready` setzen. Ein Abbruch lässt einen
unvollständigen, nicht verwendbaren Stand zurück; Wiederaufnahme ist idempotent.

Beide tatsächlichen Schreibwege werden eingebunden:
`context_observations._append_observation_batch` vor dem Commit und
`context_storage_v2.receipt_append.append_observation_in_connection` vor dem
Release des vorhandenen Savepoints. Keine zweite Verbindung, kein eigener
Commit im zweiten Weg. Normalisierte Quellbytes, Digests und Empfangszeiten
ändern sich nicht. Fehler dürfen niemals vollständige Quellen mit fälschlich
vollständigem Index veröffentlichen. SQL-/Integritätsfehler rollen die jeweilige
Schreiboperation zurück; ein nicht unterstützter Projektionsfall kann atomar
als `invalid` gespeichert werden, ohne gültige Originaldaten zu verwerfen.

## 4. Lesen, Grenzen und Kompatibilität

Batch-Training und Readiness verwenden die Zuordnung nur in ihrem bestehenden
gehaltenen Leser und nur bei vollständig passendem `ready`-Stand. Zuvor werden
die exakte Schema-/Triggeridentität und Projektorversion im selben Lesesnapshot
geprüft. Die neue Version steht intern; die bisherigen
`user_version`-/`application_id`-Verträge werden nicht pauschal umgestellt.
Für jeden Fall gilt
weiterhin dessen eigener Stichtag. Das Zielspiel ist immer enthalten; für alle
zugelassenen Spielschlüssel werden **sämtliche** passenden Revisionen bis zu
diesem Stichtag geladen und unverändert nativ validiert. ATP/WTA bleiben getrennt.
Ausgewählte Zuordnungen werden gegen ihren physischen Ursprungsbeleg geprüft.

Fehlend, veraltet, teilweise aufgebaut, manipuliert oder unbekannt versioniert
bedeutet „Index nicht verfügbar“, niemals leere erfolgreiche Historie.
Der alte Einzelpfad bleibt Vergleichsreferenz; ein ausdrücklich angeforderter
Fallback behält sein bestehendes Zeitlimit. Kein stiller langsamer Fallback.

Der Aufbau liest höchstens 512 Quellzeilen und 2 MiB Tennisinhalte je Chunk,
mit Längenprüfung vor dem Laden. Kein vollständiges Python-Quelleninventar;
die bestehende 256-MiB-Retentionsgrenze bleibt erhalten. Ein einzelner zu großer
Kandidat bricht ab.
Die Schreibtransaktion eines Chunks hat zusätzlich ein 2-Sekunden-Budget;
bei Überschreitung wird dieser Chunk zurückgerollt und nicht als Fortschritt
gezählt. Die Uhr startet vor dem Lock-Erwerb, einschließlich SQLite-Arbeit;
das Busy-Timeout darf das verbleibende Budget nicht überschreiten. Ein Aufruf hat
höchstens 45 Sekunden und einen fortsetzbaren Fortschritt;
keine unbeschränkte Gesamtschleife. Die zusätzliche abgeleitete Datenmenge ist
auf 64 MiB logische Werte begrenzt. Das ist keine Zusage zur SQLite-Dateigröße
oder zum Prozess-RAM: tatsächliche Tabellen-/Index-/WAL-Größe und RSS werden
separat gemessen und berichtet. Ein Überschreiten verhindert die Freigabe,
nicht die Speicherung einer verkürzten Zuordnung. Keine automatische Löschung
von Originaldaten, kein VACUUM und kein weiterer Sicherungs-/Sportlauf.
Erreicht ein bereits aktiver Index sein Größen-/Zusatzzeitbudget, muss er
atomar `invalid` werden können, ohne gültige neue Originalbelege oder andere
Sportarten dauerhaft am Speichern zu hindern. Echte Quell-/SQL-Integritätsfehler
behalten ihre Rollback-Semantik.

Wichtig: `context_runtime._verify_schema` und der getrennte v2-Inventarkatalog
lehnen neue Schemaobjekte bisher ab. Beide müssen die **exakte**, vollständig
vorhandene neue Schemafamilie zusätzlich zur unveränderten alten erkennen.
Keine allgemeine Erlaubnis unbekannter Tabellen/Trigger. Typisierte Inventur,
Kopier-/Importpfade, Ressourcenabrechnung und tatsächliche Quellenhashes sind
entsprechend einzubinden. Der v2-Corpus muss genau die abgeleiteten Inserts,
Updates und Invalidierungen separat abrechnen/prüfen; seine Prüfung, dass alle
vorhandenen Originalzeilen unverändert bleiben, darf nicht entfallen.
Dateikopien gelten nicht durch ihren Namen als geprüft.
Bestehende C-Eingangsgrenzen bleiben unverändert; die große Produktionsdatei
wird damit nicht automatisch für den separaten C-Pfad zugelassen.

Migration erst nach kompatiblem Code und mit ruhenden Schreibern. Ein bloßer
Rollback auf alte, schemaunverträgliche Binaries ist nach Migration unzulässig;
Rücknahme deaktiviert den Index mit weiterhin schemafähigem Code. Keine neuen
Backups oder Datenbankkopien. Kein neuer Dienst, Anbieter oder Zeitplan.

## 5. Abnahme und Nicht-Ziele

Vor Veröffentlichung erforderlich:

1. Echte SQLite-Tests beider Schreibwege: Duplikate, ältere Empfangszeit,
   Teilnehmerwechsel/-entfernung, Verlegung, gleiche Zeit, Tour-/ID-Kollision,
   Teilstatus, fehlender/defekter Beleg, Rollback, konkurrierende Leser,
   unterbrochener Aufbau, Legacy-Schreiber, Änderungen/Löschungen und Import.
2. Bei gültigen Daten exakt dieselben Belegmengen, Reihenfolge, Merkmale und
   Case-Digests wie der bisherige Einzelpfad; expliziter Zwei-Stichtag-Gegentest.
3. Derselbe echte Vier-Fall-Test: **4/4 innerhalb insgesamt 45 Sekunden inklusive
   Vorbereitung**, unveränderte Auswahl und Stichtage; weiterhin 512 Belege/
   2 MiB je Fall, 8 MiB insgesamt, CPU-Hardlimit 50 s, AS-Hardlimit 2 GiB und
   gemessener RSS unter 1 GiB. Aufbaukosten separat, nicht als schneller Leser
   ausgeben. Bei Scheitern kein Release und keine stille Grenzanhebung.
4. Anschließend vollständige Regression, unabhängiger Review und koordinierte
   Migration/Veröffentlichung; Originalbelege und Geldbewegungen unverändert.

Nicht enthalten: Datenbereinigung, neue APIs, Cricket, UI-Umbau, neue
Modellkoeffizienten oder eine automatische Effektfreigabe. Der Index ermöglicht
erst die weitere Auswertung vorhandener Verletzungs-/Wetter-/Belastungsdaten;
er beweist weder deren numerische Wirkung noch bessere Wettqualität.
