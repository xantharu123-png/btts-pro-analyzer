# Entscheidung C: vollständige Kontextdaten blockweise speichern und verarbeiten

Stand: 12. September 2026. **Entscheidungsvorlage, noch nicht freigegeben.**
Der B-Vertrag für den isolierten Prüfer ist bereits freigegeben. Diese Vorlage
behandelt ausschließlich die dort ausdrücklich ausgeklammerte Speicher- und
Eingabeänderung nach dem tatsächlich gemessenen B0-Größenfehler.
Noch keine Produktimplementierung, Migration oder Änderung der Grenzwerte.

## Problem und belegter Ausgangspunkt

Die Kontextprüfung kann mit der wachsenden Historie nicht dauerhaft dieselbe
Darstellung vollständig im Arbeitsspeicher aufbauen. Das blockiert die sichere
Auslieferung der begonnenen Reparatur; es erklärt für sich allein weder schlechte
Wettprognosen noch die separate Störung des Tennis-Tagesjobs.

B0 hat den heutigen versiegelten Bestand mit 100.553 Belegen und 31 Snapshots
gemessen: 270.233.600 Datenbankbytes, 58.390.805 ausgewählte ATP- und
75.669.070 WTA-Historienbytes. 61.392.466 der 66.373.102 Snapshot-Payloadbytes
sind ausgeschriebene Referenzlisten. Das sind 92,496 %, nicht eine gemessene
Kompressionsquote einer bereits gebauten neuen Speicherung.

Der ausdrücklich synthetische ATP-Grenztest überschritt nach 146.782 neuen
Belegen das unveränderte 256-MiB-Historienlimit: 268.435.847 statt höchstens
268.435.456 Bytes. Jede zusätzliche Zeile wurde tatsächlich normalisiert,
physisch dekodiert, ausgewählt und kanonisch gezählt. Es wurden keine künftigen
Echtspiele, kein Ausfalltag und kein vollständiger 199-Snapshot-Bestand behauptet.
Die 1-GiB-Dateigrenze wurde beim realen Bestand **nicht** überschritten; die
Dateigröße des vollständigen Wachstumsbestands ist weiterhin nicht gemessen.

Belege und unabhängige Nachrechnung:

- [B0-Ergebnis](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-14-sizing-result.md)
- [Instrumenten- und Ergebnisreview](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-14-size-review.md)
- [Bereits freigegebener B-Vertrag](2026-09-12-versionierte-pruefnachweise.md)

## Empfohlene Entscheidung

**Einen versionierten, verlustfreien Speicher-/Lesepfad bauen**, der vollständige
Daten auf Platte behält und nur begrenzte Portionen verarbeitet. Gleichartige
Referenzmengen werden gemeinsam gespeichert und vollständig rekonstruierbar
referenziert. Danach den bereits genehmigten B-Prüfer auf diese Darstellung
anwenden. Eine gesparte Referenzliste ist dabei kein Ersatz für eine geprüfte
vollständige Historie.

Dies ist eine echte Vertragsänderung: Die alten Grenzen von 1 GiB pro gesamter
Eingabedatei und 256 MiB pro vollständiger kanonischer Tourhistorie dürfen nicht
unbemerkt in Grenzen je Teilstück umgedeutet werden. Der alte Prüfmodus bleibt
unverändert. Nur ein neuer, explizit versionierter Modus erhält die unten
vorgeschlagenen Gesamt- und Arbeitsgrenzen.

## Ziele und Nutzerfälle

1. Alle bisherigen Belege, Originale, Ergebnisse, Zeitpunkte und Referenzen
   unverändert erhalten; alle alten zugelassenen Fälle exakt reproduzieren.
2. Für den vollständig erzeugten vereinbarten Sieben-Tage-Stresstest inklusive
   ATP-Konzentration, gemischter Touren und unterschiedlicher Stichtage die
   vollständige Verarbeitung unter festen RAM-/CPU-/Plattengrenzen nachweisen.
3. Einen unterbrochenen Aufbau ohne Teilfreigabe oder Verlust fortsetzen beziehungsweise
   verwerfen können; der letzte vollständige Zustand bleibt lesbar.
4. Danach den bereits freigegebenen kontrollierten Commit-/Push-/VPS-Rollout
   wieder ausführbar machen. Eine bessere Trefferquote ist kein Erfolgskriterium
   dieser Speicherreparatur und wird daraus nicht abgeleitet.

Als Nutzer möchte ich aktuelle Analysen sehen, ohne dass anwachsende interne
Historien die Aktualisierung verhindern. Als Betreiber möchte ich denselben
vollständigen Stand wiederherstellen und prüfen können, auch nach einem Abbruch.
Als Prüfer möchte ich fehlende, vertauschte oder alte Daten zuverlässig erkennen,
ohne die gesamte Historie gleichzeitig im RAM halten zu müssen.

## P0: verbindliche Anforderungen für die vorgeschlagene Umsetzung

### C1 — alte Daten und Identitäten bewahren

- Zuerst ausschließlich mit versiegelten Kopien arbeiten. Alte Datenbankzeilen,
  Original-/Snapshotbytes und historische Codeidentitäten werden nicht geändert.
- Neue Darstellung in einen gesonderten, versionierten Speicher aufbauen.
  Ein vollständiger Schlüssel-/Typ-/Bytevergleich muss jedes alte Objekt erneut
  nachweisen. Aktive, archivierte und spät eingegangene Belege bleiben enthalten.
- Physische Kompaktheit darf vorhandene kanonische Werte und semantische Digests
  nicht verändern. Neue Format-/Implementierungsidentitäten werden zusätzlich
  gebunden; alte Codehashes werden weder ersetzt noch künstlich nachgeahmt.
- Keine Löschung, Bereinigung oder automatische Entsorgung der alten Historie.

### C2 — vollständige Referenzen ohne Vollkopie je Snapshot

- Referenzmengen bestehen aus unveränderlichen, nach Inhalt adressierten Blöcken
  und einem vollständigen Verzeichnis: Version, Reihenfolge, Anzahl, Bytezahl,
  Blockidentitäten und Gesamtdigest. Ein einzelner Digest ohne nachgewiesene
  Vollständigkeit genügt nicht.
- Jeder bisherige sortierte Referenzsatz muss exakt und vollständig rekonstruierbar
  sein. Gleiche Teilmengen dürfen gemeinsam gespeichert werden; keine Auswahl
  nur der neuesten oder bequem erreichbaren Belege.
- Negative Tests: fehlender/zusätzlicher/duplizierter/ausgetauschter Block,
  gleiche Zeilenanzahl bei anderer Mitgliedschaft, ungültige Reihenfolge,
  falsche Versionsidentität, unvollständige und fremde Generation.

### C3 — vollständige Historie mit begrenztem Arbeitsspeicher

- Eine wiederholbar lesbare Sicht bindet den gesamten Datenstand, Tour, Stichtag,
  Quellversion, Auswahlregeln und totale Reihenfolge. Sie ist kein einmalig
  verbrauchbarer Generator und kein ungeprüfter SQL-Teilfilter.
- Vor fachlicher Einschränkung werden weiterhin alle vorgeschriebenen physischen,
  Schema-, Quellen- und Referenzprüfungen durchgeführt. D2-geschützte ungeöffnete
  Finals bleiben nach ihrem bestehenden Vertrag undurchsichtig.
- Auch Ereignisgruppen, Sortierung, vollständige Mitgliedschaft und Referenzlisten
  müssen auf Platte begrenzt bearbeitbar sein. Nur einen äußeren Iterator zu
  bauen und innen erneut alle Zeilen in dict/list/tuple zu sammeln reicht nicht.
- Tennis v3 benötigt derzeit eine vollständige Tuple und baut Ereignisgruppen
  im Speicher. Deshalb gehört eine ausdrücklich neue Leseschnittstelle mit
  überprüfter äquivalenter Gruppierung zum Umfang; sie darf die alte Schnittstelle
  nicht durch falsche Typ-/Vollständigkeitsbehauptungen umgehen.
- Rechenregeln, Summationsreihenfolge, Konfliktbehandlung, Zeitfenster, Statuswechsel,
  fehlende Werte, Featurewerte und Prognosen bleiben fachlich gleich. Alte
  Funktionen bleiben für zulässige Vergleichsbestände die unveränderte Referenz.
  Ein nicht identisches Ergebnis stoppt die Umsetzung, statt Toleranzen auszuweiten.

### C4 — vorgeschlagene explizite Grenzen des neuen Modus

Diese Werte sind eine zu genehmigende, noch nicht gemessene **Abnahmehülle**, keine
Behauptung, dass die aktuelle Implementation sie bereits unterstützt:

| Größe | Vorschlag für den neuen Modus |
| --- | ---: |
| Vollständiger aktiver Eingabesatz einschließlich eigener Indizes/Referenzblöcke | höchstens 4 GiB |
| Vollständige kanonische ausgewählte Historie je Tour | höchstens 1 GiB, vollständig auf Platte verarbeitbar |
| Einzelner Referenz-/Verarbeitungsblock | höchstens 16 MiB kodiert; RAM separat messen |
| Gesamter neu angelegter QA-/Aufbau-/Ausgabebereich | höchstens 8 GiB, nicht je Teilprozess |
| Zusätzlich frei zu haltender Platz | mindestens 4 GiB, vor und während des Aufbaus prüfen |
| Worker | unverändert CPU 300 s, AS 2 GiB, RSS unter 1 GiB, Ausgabe höchstens 1 MiB |
| Vorbereitung einschließlich aller Teile, Fehlversuche und Wiederholungen | unverändert höchstens 1.800 CPU- / 3.600 Gesamtsekunden |
| Wiederholte abschließende Freigabeprüfung | Abnahmegrenze unverändert höchstens 240 CPU- und Wandsekunden |

Die größere vollständige Datenhülle soll durch blockweise Verarbeitung ermöglicht
werden, nicht durch mehr zugelassenen Worker-RAM. Die bisherigen 64 MiB für die
gesamte Legacy-In-memory-Eingabe, der getrennte 64-MiB-/32-Slot-Historiencache und
der B-Nachweisspeicher werden nicht still vergrößert; ihre Kapazität ist in der
Gesamtbilanz auszuweisen. Einen bestehenden produktweiten 64-MiB-Einzelwertvertrag
gibt es hier nicht: Dieses SQL-Limit gehörte ausschließlich zum B0-Instrument.
Eine einzelne große Altstruktur muss unter ihrem bisherigen Lesevertrag bleiben
oder erhält einen eigens geprüften Adapter; 16-MiB-Blöcke sind keine Behauptung
über Alt-Payloadgrößen. Der neue Modus braucht unabhängig davon feste, getestete
Einzelwert- und Blockanzahlgrenzen innerhalb seiner freigegebenen Gesamthülle.

Read-only VPS-Aufnahme am 12. September: etwa 4,01 GB Gesamt-RAM, 15,06 GB freier
Plattenplatz. Das ist nur ein momentaner Ausgangswert. Die nächste Ausführung
muss freien Platz, komplette Backup-/Rollbackreserve und bereits vorhandene
QA-Daten frisch einrechnen. Keine automatischen Löschungen oder Server-Upgrades.
Reicht die reservierte Hülle nicht, ist das ein expliziter Testfehler, kein
Anlass zum heimlichen Verkleinern des Profilumfangs oder erneuten Gratisbudget.

### C5 — konsistente Veröffentlichung, Backup und Rückweg

- Der Aufbau liest eine stabile Generation. Ein vollständiges Verzeichnis bindet
  alle Teile desselben Standes; ein Dateisystempfad oder eine Dateiliste allein
  ist keine konsistente Momentaufnahme mehrerer Datenbanken.
- Die bestehende B-Isolierung und der geschützte Publisher bleiben zuständig.
  Veröffentlichung erst nach vollständig geprüfter Coverage und atomarem Wechsel
  des aktiven Generationsverweises. Paralleländerungen, Absturz und alte Verweise
  dürfen keinen Teilstand freigeben.
- Backup und Restore enthalten sämtliche erreichbaren Blöcke, Verzeichnisse,
  Nachweise und nötigen Schlüssel innerhalb des bestehenden geschützten Pfads.
  Keine Schlüssel oder Laufzeitdatenbanken in Git oder auf den lokalen PC kopieren.
- Ein Rückwechsel darf keine seit der Umstellung neu eingegangenen Daten verlieren.
  Deshalb vor einer Schreibumstellung einen getesteten Kompatibilitäts-/Exportpfad
  beziehungsweise eine verlustfreie Vorwärtsreparatur nachweisen. Kein Zurücksetzen
  auf eine alte Datenbankkopie, die neue Belege nicht enthält.
- Öffentliche Hashes belegen Gleichheit, nicht Vertrauenswürdigkeit. B bindet
  weiterhin vollständige Eingabe-/Ausführungsidentität und den aktuellen Kopf;
  vollständiges Root-/VM-Rollback ohne externen Anker bleibt außerhalb des Claims.

### C6 — messbare Abnahme statt Annahme

- Auf kleinen und allen alten zulässigen Beständen vollständiger Vergleich:
  ausgewählte Belege, Reihenfolge, Referenzen, Features, Originale, fachliche
  Ergebnisse, Ablehnungen und Fehlerfälle. Kein lediglich gleicher Count.
- Rückdatierte neue Zeilen, Gleichstände, Teilnehmerkorrekturen, Absagen,
  neue/entfernte Ergebnisse, andere Tour, leere Historie und fehlende Quellen
  müssen dieselben fachlichen Folgen haben wie im unveränderten Vergleichspfad.
- Vollständige reale Ausgangsbestände sowie owner-erzeugte Originale/Snapshots
  des Sieben-Tage-Profils aufbauen. Die heutige Größenprobe ersetzt das nicht.
  Der aktuelle Baselinezähler beträgt 100.553, nicht der frühere 99.776.
- Grenzen, drei unabhängige vollständige Wiederholungen der finalen Prüfung,
  Vorbereitungskosten, Abbruch/Resume, Konkurrenz, Wiederherstellung und
  rückwärtskompatibles Lesen messen. Jede Quelle muss tatsächlich abgearbeitet
  oder über den genehmigten vollständigen B-Nachweis abgedeckt sein.
- Erst danach neue Produktvollsuite, unabhängiges Abschlussreview, frisches
  Backup und bereits genehmigter kontrollierter Commit-/Push-/VPS-Rollout.

## P1 / später und ausdrückliche Nicht-Ziele

P1: Administrationsanzeige für belegten Speicher, Alter des letzten vollständigen
Standes und verbleibende Abnahmehülle. Interne Prüfdaten nicht in Tippkarten ausgeben.

P2: Langfristige Archiv-/Aufbewahrungsstrategie auf Basis realer vollständiger
Betriebstage. Diese Vorlage behauptet keine unbegrenzte Skalierbarkeit.

Nicht enthalten: Datenlöschung/Verkürzung; Quotenfilter oder Wettartenverbote;
neue Verletzungs-/Müdigkeitsgewichte oder eine empirische Modellfreigabe;
Cricket; A0/P4b3; die separate Fehlerbehebung des Tennis-Tagesjobs; ein externer
Datenbankdienst, neue Zugangsdaten oder ein kostenpflichtiges Server-Upgrade.

## Ablauf, Erfolgsmessung und offene Entscheidungen

Es gibt keinen belastbaren Liefertermin vor dem Prototyp. Reihenfolge nach
Freigabe: (1) enger Vertrags-/Differenztest, (2) kopiebasierter Speicher-/Leseprototyp,
(3) vollständige Größen-/RAM-/CPU-Probe, (4) B-Inventar/Nachweise/Bootstrap,
(5) Regression/Restore/Review, (6) kontrollierter Rollout. Pro Bereich ein
Schreiber und unabhängiges Review; Root behält Index und Serverintegration.

Früher Erfolg: null veränderte alte Objekte, null semantische Differenzen,
vollständig bestandenes Profil innerhalb aller genannten Grenzen. Späterer
Betriebserfolg: reale vollständige Tage ohne kapazitätsbedingten Ausfall innerhalb
der gemessenen Abnahmehülle; Telemetrie und längere Beobachtung separat ausweisen.
Kein steigender Testzähler gilt als Nachweis besserer Wetten.

**Einzige jetzt blockierende Nutzerentscheidung:** Soll die verlustfreie
versionierte Speicherung und blockweise vollständige Verarbeitung einschließlich
der neuen begrenzten Datenhülle umgesetzt werden? Die schon erteilte B-,
Commit-/Push- und kontrollierte Deploymentfreigabe muss nicht erneut erfragt
werden. Ohne diese zusätzliche Speicherentscheidung bleibt der Produktstand
unverändert. Die vorgeschlagenen Grenzen gehören ausdrücklich zu dieser Frage.

Technische Detailverantwortung nach Freigabe: Engineering bestimmt das konkrete
Blockformat und die reproduzierbaren Lese-/Gruppierungsalgorithmen innerhalb
dieses Vertrags. Ein nicht passender Zeit-/Speicherbedarf, abweichende Semantik
oder nicht verlustfrei möglicher Rückweg wird offen gemeldet, nicht kaschiert.

## Technische Referenzen, am 12. September 2026 geprüft

SQLite beschreibt die abgeschlossene Online-Sicherung als konsistente Kopie;
konkurrierende Schreibvorgänge können die Sicherung neu starten. Daher bleibt
der Aufbau zeitlich begrenzt und braucht einen vollständigen Abschlussnachweis.
[SQLite Online Backup API](https://www.sqlite.org/backup.html)

Getrennte Verbindungen und eine gehaltene Lesetransaktion ermöglichen einen
konsistenten Lesestand; Änderungen über dieselbe Verbindung während einer
laufenden Abfrage sind dafür keine sichere Grundlage.
[SQLite Isolation](https://www.sqlite.org/isolation.html)

`immutable=1` setzt eine wirklich unveränderliche Datei voraus und ist nicht
für die parallel beschriebene Live-Datenbank vorgesehen. Ein neuer Mehrdatei-
Speicher muss diese Eigenschaft pro veröffentlichter Generation selbst garantieren.
[SQLite URI-Parameter](https://www.sqlite.org/uri.html)

Die konkreten 1-GiB-/256-MiB-Grenzen stammen aus BetBoys bisherigem Vertrag;
SQLite besitzt eigene, getrennte Implementierungs- und Laufzeitgrenzen. Die
neue Gesamthülle ist daher eine Produktentscheidung, kein automatischer SQLite-Fix.
[SQLite Limits](https://www.sqlite.org/limits.html)
