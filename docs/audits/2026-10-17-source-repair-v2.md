# Quellenverarbeitung und nativer Marktvergleich – Fortsetzung

Status 18.10.: technische Quellen-/Marktreparatur geprüft und seit 02:12:48 CEST
live, Quellrelease `c6fe02fdce07eae1e13368e98612c8b6bf569657`. Keine nachgewiesene
zusätzliche numerische Modellwirkung.

## Tatsächlicher Release-Nachweis

GitHub-main und VPS standen nach dem erlaubten Fast-forward von `2f62e5e` auf
dem genannten Quellcommit. Exakte 45-Pfad-Allowlist, sieben nativ geprüfte
Tennis-/Historien-/Indexbesitzer stimmen unter ausschließlich CRLF→LF-
Normalisierung. Beide Indexowner bleiben zusätzlich rohbytegleich vor/nach Pull
und Apprestart. Offline-Smoke bestätigt neue Verträge, Legacy/v3-Abgrenzung,
Evidenzpins, No-vig-Rechnung und fehlende-DB-No-create-Verhalten. Ausschließlich
App neugestartet, PID 1222039 → 1236110; App/Caddy aktiv, beide Healthchecks `ok`.
Acht Timer aktiv/aktiviert; Sicherungstimer weiterhin inaktiv/deaktiviert.
Prognose-Snapshots und alle neun Jobstartstempel während des Deploys identisch.
Kein Backup, Migration, Paketinstallation, Datenbankkopie oder neuer Sportscan.
`output/source-repair-20261017/deploy-source-repair-01.txt` bleibt außerhalb Git.
Nachfolgende Abschlussdokumentation wird separat ohne Apprestart gepullt.

Separater bereits bestehender Produktionsbefund: Shadow 02:02/02:12 unter altem
Code meldete `partial`/Exit 1, kein frischer Bet365-Providerbeleg für 1550998/1550999
und zwei ungültige historische CLV-Belege. `shadow_clv_automation.py` und
`clv_tracker.py` sind gegenüber 2f62 unverändert. Die Kennzahl bleibt bewusst
gesperrt; „malformed settlement“ kann fehlende Closingquote bedeuten und beweist
nicht allein falsche Geldabrechnung. Fehlende historische Provenienz nicht
nachträglich erfinden. Enge produktive Nachprüfung in gehaltenem read-only-
Snapshot: nur zwei Zeilen/400 Bytes skalare Nutzdaten; Zeile 2/Fixture 1528908
(Romania–Bosnia, Won) und Zeile 3/Fixture 1495965 (Strommen–Sandnes, Lost) fehlen
jeweils `closing_odds`, `closing_bookmaker`, `closing_source`, `closing_quoted_at`.
Öffnungs-, Ergebnis- und Profitfelder erfüllen alle übrigen bestehenden Kriterien.
Damit ist die Ursache geklärt, nicht die fehlende historische Evidenz repariert.
Ein regulärer vollständiger Tennislauf des neuen Codes und neue gespeicherte
native Markt-Gegenpaare bleiben zukünftiger Produktionsnachweis, kein Grund für
einen zusätzlichen Scan. Die fachlichen Vertrags-/Qualitätslücken unten bleiben.

## Abschließender Test- und Quellabgleich

Der unveränderte große 13-Modul-Fußballlauf ist mit Exit 0, **381 PASS**, null
Fehlern/Skips in 3.490,58 Sekunden beendet. Der exakte Abgleich aller bestehenden
Belege ergibt **15.459 PASS und 98 ursprüngliche unveränderte SKIP** für alle
15.557 aktuellen Haupt-IDs; sämtliche 15.495 IDs der ursprünglichen QA03 bleiben
erhalten. Alle fünf ursprünglichen Fehler haben vollständige Ownernachtests;
kein ursprünglicher FAIL-/INCOMPLETE-Beleg wurde gelöscht oder umgedeutet.
`output/source-repair-20261017/followup-receipt-merge-final.json` ist ausdrücklich
eine Zusammenführung ursprünglicher Vollsuite und späterer ganzer Ownernachtests,
**kein frisch wiederholter grüner Gesamtlauf oder damaliger WholeSource-Freeze**.
Der unveränderte Sourcepin-Wrapper bleibt am WholeSource-Assert FAIL/INCOMPLETE;
seine 103 eigenen Fälle werden nur im getrennt geprüften Umfang übernommen.

Unabhängiger finaler Review: alle 834 Source-/Test-/Configdateien entsprechen
bytegenau der akzeptierten Abschluss-Collection. Exakte 45-Pfad-Allowlist,
unveränderte sechs Tennis-Prognosemodule und zwei Indexowner; kein neuer
bestätigter Releaseblocker. Native 72-Fälle-Quellenparität und Index-READY sind
separate Belege, kein bereits erfolgter regulärer Lauf des neuen Codes.
Numerische Verletzungs-/Wetter-/Müdigkeitswirkung bleibt offen, einschließlich
der unten konkret benannten Mehrfall-/PLAYER_LOAD-/POINT-Vertragslücken.

## Begrenzter Reparaturumfang

- Bereits vorhandene Quellen verarbeiten; kein neuer Sport-/API-Scan, kein neues
  Abo, keine Sicherung und keine Datenbankkopie. Isolierte VPS-Prüfungen verwenden
  ausschließlich Code und lesende Transaktionen der bestehenden Datenbank.
- Marktpreise sind ein getrennter Vergleich, kein Eingang der Modellberechnung
  und kein neuer EV-Auswahlfilter. Die bestehende bekannte Untergrenze 1,20 bleibt.
- Keine Verletzungsdiagnosen, Endzeiten, Erholung oder Wetterkoeffizienten erfinden.
  Cricket bleibt beim bisherigen Modell; eine fehlende native Quotenanbindung
  wird nicht durch synthetische Gegenpreise ersetzt.

## Fußball: ausdrücklich neue Speicherabrechnung v2

Die alte Datei `football-original-admission.json` und ihre Reservierungszählung
bleiben unverändert. Ihr ausgeschöpftes 128-MiB-Limit wird weder zurückgesetzt
noch rückwirkend als bestandener Nachweis dargestellt. Unbekannte alte Abstürze
lassen sich nicht nachträglich einzelnen tatsächlichen Schreibmengen zuordnen.

Die neue Datei `football-original-committed-admission-v2.json` verwendet deshalb
einen anderen, ausdrücklich benannten Umfang: bestehende `football-*`-Artefakte
plus künftig von diesem Owner tatsächlich neu gespeicherte Artefakt-/Quellbytes.
Sie ist **kein Limit für die gesamte SQLite-Datei** und zählt nicht rückwirkend
den allgemeinen alten Quellenbestand. Lesend gemessen waren vorhandene eigene
Artefakte 54.886.863 Bytes; allgemeine alte Basisquellen allein 188.428.344 Bytes.
Diese verschiedenen Mengen dürfen nicht als derselbe Nenner ausgegeben werden.

Weiter gelten 4 MiB pro Versuch, 8 MiB je UTC-Zulassungstag, 128 MiB insgesamt
innerhalb dieses neuen Umfangs und mindestens 512 MiB freier Plattenspeicher.
Die kanonischen Batches teilen eine einzige Reservierung. Nur ein nachweislich
abgeschlossener Aufruf darf seine ungenutzte Reservierung freigeben; fehlende
Abschlüsse bleiben mit vollen 4 MiB belastet. Erfolgreiche Schreibvorgänge werden
mit den bestehenden transaktionalen Bytezählern abgerechnet. Der alte Ledger ist
per Inhaltsdigest gebunden; eine rückwärts laufende Uhr darf die Zulassung auch
beim ersten v2-Aufruf nicht umgehen. Gemeinsame atomare Lock-/Schreibbesitzer
schützen konkurrierende Aufrufe. Keine historischen Belege werden gelöscht.

## Quellenleser: neue Verträge statt umbenannter alter Limits

- Fußball `football-native-source-stream-v2`: vollständige kausale physische
  Revisionen prüfen, gefrorene verbrauchte/inspektierte Belege behalten,
  Konflikte und Rücknahmen nicht wegfiltern. Featurezweige müssen dieselben
  Ergebnisse wie der vollständige ursprüngliche Leser liefern. Der alte
  4-MiB-Leser bleibt unverändert. Neue physische Obergrenze 128 MiB/100.000
  Belege; einzelne Featurezweige bleiben auf 4 MiB/4.096 Belege begrenzt.
  Ein expliziter neuer Trainingsfall wird aus der tatsächlichen lesenden
  DB-Transaktion rekonstruiert, nicht mit einem beliebig behaupteten Hash belegt.
- Tennis `tennis-source-stream-v1`: expliziter Opt-in, alter 512-Belege-/2-MiB-
  Vertrag unverändert. Auswahlobergrenzen je Fall 32.768 Belege/32 MiB, vier Fälle
  insgesamt 131.072 Belege/128 MiB, ein physischer Verarbeitungsschritt höchstens
  512 Belege/2 MiB, gespeicherte Arbeits-/Ausgabemenge höchstens 256 MiB. Eine
  globale Mitgliedschaftssuche ist getrennt von diesen ausgewählten Fallmengen
  auszuweisen. Ein ungültiger abgeleiteter Index bleibt ungültig.
- Die sechs gefrorenen Tennis-Prognosemodule werden nicht verändert. Keine
  pauschale Prozentkorrektur und keine Lockerung der empirischen Abnahme.

## Marktvergleich

Native vollständige Gegenpreise für Fußball, Tennis, Basketball, Eishockey und
E-Sport werden im bestehenden Beleg mitgespeichert. Eine einzelne prognostizierte
Seite kann separat als binäres Ereignis gemessen werden. Diese `selection_groups`
dürfen nicht mit den bisherigen kategorialen vollständigen `groups` vermischt
werden. Beide mitteln innerhalb eines Ereignisses, dann über Ereignisse; Ein- und
Schlussbeobachtungen sowie Modell-/Policyversionen bleiben getrennt.

Doppelte Chance erhält die faire Vergleichswahrscheinlichkeit durch Summieren
passender Ergebnisse eines vollständigen echten 1X2-Markts. Überlappende DC-
Quoten selbst sind keine ausschließende Grundgesamtheit. Für Multigoal und
Kombinationen werden fehlende vollständige native Partitionen nicht erfunden.
Cricket meldet ausdrücklich `native_price_adapter=false`.

Basketball-/Hockey-Abrechnung verwendet vorhandene beobachtete Finals und die
kanonischen Regeln. Vor dem Laden eines Quellkörpers werden Datentyp, Bytegröße,
Identität und Mehrdeutigkeit geprüft. Eine Korrektur zwischen zwei Lesern darf
nicht mit den Bytes des vorherigen Ergebnisses verbunden werden.

## Noch zu beweisen

### Echte lesende Quellenproben

- Fußball, aktueller endgültiger Leser einschließlich alter Kaderrevisionen und
  Wetterquellenprüfung: Exit 0, 82,687 Sekunden. 36.111 kanonische Belege,
  97.110.896 physische und 108.341.418 expandierte Bytes; kompakt 1.555 Verweise,
  alle Featurezweige unter 4 MiB. 21 Merkmale, davon drei Terminmerkmale nutzbar.
  Keine vorhandene Verletzungs-/Wetterwirkung daraus behaupten. Rein lesender
  Beleg: `C:/Projekt/BetBoy/output/football-stream-20261017/native-proof-03.txt`.
- Tennis, vollständiger physischer Fallback ohne gültigen Index: **FAIL** nach
  600,038 Sekunden/518,562 CPU-Sekunden, 88,5 MiB maximaler RSS. Geprüft waren
  1.091.503 globale Belege/1.174.845.383 Bytes; bis dahin 35.062 ausgewählte
  Zeilen/37.613.741 Bytes, null fertig freigegebene von vier Featurefällen.
  Der globale Vollständigkeitsnachweis war nicht fertig. Das ist weder eine
  bestandene 128-MiB-Gesamtleseprüfung noch ein RAM-Problem. Der Beleg bindet
  seinen damaligen Quellstand vor der abschließenden Typ-/Vorleseprüfung und
  Docstring-Präzisierung, darf also auch nicht als Probe aller letzten Bytes
  ausgegeben werden. Keine identische Zeitlimit-Wiederholung gestartet.
  `C:/Projekt/BetBoy/output/tennis-stream-native-03.jsonl` bleibt als FAIL erhalten.

Der standardmäßige indizierte Tennis-Pfad akzeptiert keinen ungültigen Index.
Der neue explizite Fallback ist korrektheitstestbar, aber auf diesem großen
Produktionsbestand noch nicht innerhalb seiner Laufzeitgrenze abgenommen.
Die sechs Tennis-Prognosemodule bleiben unverändert. Der unten beschriebene
optionale v4-Livequellenpfad ist ein eigener Vertrag; seine Produktionscaller
werden erst nach dessen tatsächlichem Gesamtbatchnachweis umgestellt. Auch
der neue Fußball-Headeranschluss ist keine Live-Effektfreigabe.

Softwaretests und lesbare Quellen sind kein Nachweis besserer Wettqualität.
Unverändert erforderlich: mindestens 200 unabhängige unberührte finale Testspiele
zusätzlich zu Training/Abstimmung, drei zeitlich getrennte Blöcke, mindestens 2 %
relativer gepaarter Brier-Vorteil, HAC/BH-Prüfung und keine Verschlechterung des
Verteilungs-Log-Loss. Ein Modell darf erst dann als empirisch verbessert gelten.
Die bisherigen acht vollständigen Fußball-Originale oder 1.000 Tennis-Finals
gemischter alter Modellgenerationen erfüllen das nicht automatisch.

### Konkrete Fußball-Restarbeit, nicht als bloßes Warten beschreiben

Der ursprüngliche Berechnungsstichtag liegt vor späteren Kader-/Wetterabfragen.
Mehr unveränderte historische Zeilen beheben das nicht. Der aktuelle Beleg
beweist deshalb nur drei Terminmerkmale, nicht spätere Verletzungs-/Wettereffekte.
Zudem überschreiten zwei vergleichbar große vollständig expandierte Trainingsfälle
bereits den neuen 128-MiB-Aufbewahrungsrahmen. Ein beliebig großer Trainingslauf
ist mit diesem einzelnen Quellenleser noch nicht fertig repariert.

Der spätere Entscheidungsbeleg wird jetzt separat integriert (nächster Abschnitt).
Vorbereitung/Fitter/D2 nacheinander je physischem Fall und nur die tatsächlich
rekonstruierten numerischen Projektionen zu behalten bleibt eine eigene offene
Arbeit. Fittermathematik und feste Trainings-/Abstimmungs-/Testinventare müssen
erhalten bleiben. Der neue Headeranschluss löst diesen Mehrfall-Speicherpfad
nicht; die Effekte deshalb nicht als fertig oder nur noch auf 200 wartend melden.

## 18.10.: tatsächlich abgeschlossene Basisprüfung und weitere Integration

Basis lokal committed als `bc6e7f2`, noch kein Push oder Deployment. Der
ursprüngliche vollständige Offline-Lauf QA03 enthält 15.392 PASS, 98 identische
SKIP und fünf FAIL. Drei Fehler waren ein echter JSON-Containerunterschied:
der neue native Quotenanhang war im Speicher ein Tupel, nach Speicherung eine
Liste. `MarketConsensus.to_dict()` gibt diesen nichtleeren Anhang nun explizit
JSON-nativ aus. Ein fehlender/leerer Anhang bleibt aus alten Daten unverändert
weg. Zwei bisherige Ganzobjekt-Hashfixtures prüfen nun weiterhin den festen
alten Kernhash und dessen anhangfreien Roundtrip, statt legitime additive
Metadaten als altes Ganzobjekt zu behandeln. Fünf neue Roundtripfälle ergänzt.

Alle 13 betroffenen vollständigen Quoten-/Markt-/Evidence-Module separat:
439 PASS. Exakte zusammengeführte Abdeckung 15.402 PASS/98 gleiche SKIP, alle
15.495 ursprünglichen IDs plus fünf neue; keine Originalfehlerbelege gelöscht.
Andere ursprüngliche Produktquellen waren für diese Zusammenführung identisch.
Das ist kein komplett wiederholter grüner Gesamtlauf nach dem JSON-Fix und
deckt die nachfolgenden neuen Live-/Headeränderungen nicht automatisch ab.
Belege: `output/source-repair-20261017/full-qa-03/` und
`output/source-repair-20261017/market-json-recheck-01/` außerhalb von Git.

### Reiner Produktions-Marktvergleich

Lesend, ohne API, 17.10. 22:53:21 UTC: 6.671 erste kausale Auswahlen
(Fußball 5.985, Tennis 261, E-Sport 383, Hockey 42). Im alten kategorialen
Vergleich 48 Marktsätze aus 20 Fußballereignissen. Aktuelle v14-Kohorte nur
acht unabhängige Ereignisse: Modell-Brier 0,12913 gegenüber Markt 0,13859;
explorative einseitige Untergrenze des Vorteils −0,01162, p=0,2302. Das ist
kein belastbarer Überlegenheits- oder Renditenachweis. Es existierten 72
Closing-Beobachtungen, jedoch noch kein passendes neues binäres Gegenpaar:
die alten Preisbelege enthalten die neue native Partition nicht. Keine
Gegenpreise oder alten Entry-Zeitpunkte rückwirkend erfunden. Basketball ohne
Auswahlen im Bestand; Hockey ohne passend gebundenen Finalbeleg; Cricket ohne
nativen Preisadapter. Beleg `output/source-repair-20261017/native-market-proof-01.json`.

### Tatsächlicher Tennisindex und regulärer Lauf

Der bestehende Indexbesitzer wurde unverändert weitergeführt. Aufruf 13 bleibt
als FAIL mit 2,0030598319 Sekunden von BEGIN bis Transaktionsende erhalten.
Nach dem regulären Tennisjob und einem stabilen lesenden Fußballfenster wurden
Aufrufe 14–32 unter denselben Grenzen ausgeführt. Erst Aufruf **32** erreichte
READY: Tail und Abdeckung 2.639.584, logische Indexbytes 1.303.491; letzter
Aufruf 34,768 Sekunden, maximale Writerphase 0,371 Sekunden. Originaltabellen-
Writes/ATTACH wurden ausdrücklich verboten. Keine DDL-/Flags-/Quellcodekorrektur
zum bloßen Freischalten des Index. Belege `output/tennis-stream-index-rebuild-20261017/`.

Separat war der alte reguläre Produktionslauf erfolgreich: 18.10. 00:05:02 bis
00:36:48 CEST, Exit 0. 72 verarbeitet, 64 neue Prognosen, tatsächlich 72 neue
Winner-Originale; `unresolved_outcome_events=0`. Kontext weiterhin teilweise:
14 Teilnehmerkonflikte, ein nativ nicht verfügbarer Fall, drei Matchaufgaben;
Kategorien sind nicht zwangsläufig disjunkt. Dieser Lauf nutzte den alten
Produktionscode `2f62e5e` und beweist nicht die neue Quellenreparatur.

### Expliziter optionaler Tennis-Livequellenpfad

`tennis-live-indexed-source-v1` nur für v4, Legacy/v3-Default unverändert. Eine
gehaltene physische Transaktion für alle tatsächlichen Entscheidungsuhren;
alle Fallmetadaten und kumulierte Roharbeit vor dem ersten Körper zugelassen.
Nur ein physischer Historienbesitzer gleichzeitig, danach sowohl Besitzer als
auch dekodierte Zeilen vor Konstruktion des nächsten Falls freigeben. Die
unveränderten Original-/Feature-/Publikationsbesitzer bleiben maßgeblich.

Neuer ausdrücklich benannter Rahmen pro `LiveWorker.finish` (kein Tages-/API-
Kontingent): maximal 400 qualifizierte Auswahlen, zwei Millionen kumulierte
Zeilen/2 GiB Lesearbeit, 1.200 Sekunden Wall/CPU, Ausgabe samt Planheap 128 MiB.
Je Fall 32.768 Zeilen/32 MiB Rohkörper, 256 MiB Besitzerrahmen; Chunks 512/2 MiB.
Kein ungültiger Indexfallback, keine Teilprefixpublikation. 191 vollständige
Owner-/Nachbartests bestanden; unabhängiger Review ohne bestätigten Blocker.

Die Metadatenprobe aller 72 tatsächlich gespeicherten neuen Winner-Originale
bestand: 870.479 Zeilen/930.892.969 Bytes, größter Fall 23.121/24.665.284 Bytes,
keine ungültigen physischen Typen. Sie ist kein vollständiger Feature-/Heap-
Nachweis. Vier native unveränderte Trainings- und Livefälle bestanden danach
jeweils mit 78.548 Zeilen/83.966.904 Bytes, exakter Original-/Feature-/Ref-
Parität und sämtlichen nativen Tailprüfungen: 111,24 Sekunden, maximaler RSS
364.016 KiB, vorbereitete Ausgabe 10.415.605 Bytes. Frühere reine Codeoverlay-
Hash-/Diagnosecaller-Fehler bleiben getrennte FAIL-Belege.

Der ganze tatsächliche 72-Fälle-Quellen-/Feature-Replay ist nun vollständig PASS:
72 exakt rekonstruierte unveränderte Originale, 870.479 tatsächlich gelesene und
einmalig nativ validierte Zeilen/930.892.969 Bytes, exakt vorab zugelassenes
Inventar. Endheap 120.207.043 Bytes, Planheap null, unveränderte 128-MiB-Grenze;
621,740 Sekunden Wall/610,244 CPU, RSS 370.968 KiB. Beleg
`output/tennis-live-source-draft-20261018/native-actual-batch-01-PASS.json`.
Die sieben tatsächlichen Tennis-/History-/Indexbesitzer sind bytegleich mit
dem Checkout. Die damals ausgeführten dataset/evaluator-Ganzdateihashes bleiben
historisch richtig; der spätere abweichende Diff darin besteht ausschließlich
aus nicht ausgeführten Football-Seams bzw. additiven Pins. Kein Austausch der
Overlayquellen während des Prozesses. Dieser Replay berechnet keine neue
Sportprognose, liest keine neuen Outcomes und ersetzt keinen vollständigen
A1-ModelState-/Publikationsnachweis. Beide canonical Tages-/Refreshcaller sind
nach diesem Beleg explizit angeschlossen; ihre eigene Testsuite ist abgeschlossen.

Canonical-Folgetest richtig mit bestehender `.codex_test_venv` und unverändertem
Offline-Launcher: **338 PASS**, 96,39 Sekunden, null Fehler/Skips; sämtliche
338 vorherigen IDs unverändert erhalten. In fünf vorhandenen Testdateien wurden
ausschließlich echte lokale READY-Voraussetzungen für zehn betroffene Caller-
Tests aufgebaut; ein Zähler prüft jetzt den tatsächlichen physischen Fallbesitzer
statt des absichtlich nicht mehr aufgerufenen WholeTour-Lesers. Neue zwei Tests
prüfen die tatsächlichen Daily-/Refresh-Opt-ins. Negative Invalidindex-/Legacy-
und v3-Tests bleiben erhalten. Die vorherige abweichende Interpreterrunde
328 PASS/10 fehlende Testvoraussetzungen bleibt als FAIL dokumentiert. Weitere
Importcallermodule sind ebenfalls fertig: 327 ursprüngliche IDs, nach reiner
Umgebungsnachprüfung 324 eindeutige PASS/3 gleiche Windows-Symlink-Skips. Die
initialen 13 Temp-/Hardlink-Permissionfehler traten vor Produktlogik auf und
bleiben erhalten. Beide vollständigen betroffenen Module wurden unverändert
mit regulären QA-Rechten und Projekt-TEMP wiederholt: 60 PASS/3 SKIP, dieselben
63 IDs; kein Produktguard oder Hardlinkprimitiv verändert. Kein einzelner
grüner 327er Lauf behauptet. Unabhängiger Finalreview bestätigt diese
Abgrenzung und unveränderte sechs Tennis-Kern-/zwei Index-Quelldateien.

Die drei gemeinsamen Aktivierungs-/Consumer-/Runtime-Ownermodule haben separat
103 PASS/0 SKIP in 509,32 Sekunden. Der ursprüngliche unveränderte Wrapper
beendet trotzdem korrekt mit EXIT 1 am WholeSource-Assert: während seiner
Laufzeit wurden genau Daily und die neue Caller-Testdatei geändert. Alle drei
Ownermodule und tatsächlich von ihnen ausgeführten Produkte blieben bytegleich;
Import-/Subprozess-/runpy-Prüfung fand keinen Aufruf der zwei veränderten Dateien.
Die fünf Fixtureänderungen folgten erst nach Laufende. `scoped-owner-summary.json`
und `caller-exclusion-review.md` grenzen die Ergebnisse ab; ursprünglicher
Wrapper-FAIL bleibt erhalten, kein Waiver oder erfundener Vollquellen-PASS.

### Fußball: späteres eingefrorenes, noch nicht körpergeprüftes Inventar

Neuer separater Kind `football-native-context-inventory-v2`, Status
`frozen-unresolved`: vor Anpfiff tatsächlichen späteren Kader-/Wetterstichtag
und komplette kausale Skalarkopf-Mitgliedschaft LP8-gebunden einfrieren.
Höchstens 1 KiB pro Artefakt. Keine teure Körperprüfung unter Worker-Mutex oder
Schreibtransaktion. Spätere Readiness/Case/D2-Nutzung muss sämtliche realen
Quellkörper und das genaue Inventar physisch rekonstruieren. Ein bloßer Hash
oder dieser neue Status ist keine Daten-/Effektfreigabe.

Expliziter neuer Headerrahmen je Inventar: 100.000 Zeilen/32 MiB Metadaten,
Vorbereitung und Writer jeweils zwei Sekunden; gemeinsamer Worker maximal 32
Entscheidungen/128 Sekunden kumulierte Phasenarbeit, einschließlich dreier
vollständiger Traversierungen pro Inventar. Das sind Lesearbeitsgrenzen, keine
GB-große gespeicherte Datei. Bestehender DB-Writer ohne Anlage/DDL, timeout 0
innerhalb des Phasenbudgets, realer created_at-Readback. Nach COMMIT kann ein
Überlauf nicht rückgängig behauptet werden: tatsächliche Bytes belasten und
Status ausdrücklich `captured-unresolved-time-overrun`, niemals PASS.

Externer unabhängiger Review fand zwei Writerfehler und bestätigte ihre
Korrektur; 23 externe Ownertests bestanden. Jetzt canonical integriert,
einschließlich explizitem Workeropt-in und additiven Codepins; bestehende
Owner-/Fit-/D2-/Legacytests laufen separat: neuer Owner inklusive echtem
Fit→Freeze→Evaluate→Verify-D2 und realem Bodytamper 24 PASS; vier weitere ganze
Deferred-/Opponent-/Readiness-/LOAD-v3-Owner 91 PASS. Große 13er-Runde 381 PASS,
Exit 0, keine Skips/Fehler; keine Quellen-/Teständerung während dieses Laufs.
Native reine Headerprobe 36.111
Zeilen/11.834.736 LP8-Bytes: kalt 1,449892 Sekunden, warm 0,488861 Sekunden,
Originalbesitzer zusätzlich 0,292784 Sekunden. Das beweist **nicht** den
vollständigen nativen Writer. PLAYER_LOAD-v3 bleibt originalstichtagsgebunden;
zusätzliche Nationalteam-/Transferbelastung und Mehrfall-Fitter offen.

Der Mehrfall-Rest ist ein konkreter Vertragsgap: `football_readiness` und
`dataset._prepare` halten volle aufgelöste Fälle, `training.fit_family` verlangt
erneut deren unveränderte Rekonstruktion. Ein Generator allein spart nicht die
im bestehenden Dataset pro Fall wiederholte vollständige Quellenliste; bei
36.111 Referenzen und 200 Fällen etwa 484 MB. Kleinster sauberer Folgeumfang:
bestehende Schema2-Fälle behalten, einen ausdrücklich versionierten Dataset-
Vertrag für einmalige vollständige Quelleninventare und exakte Fallmitgliedschaft
ergänzen. Nur der bestehende physische Besitzer darf daraus numerische
Projektionen ableiten; D2 muss alle Originalquellen/Revisionen/Finalgrenzen erneut
vollständig prüfen. Keine Erhöhung der bestehenden Grenzen und kein freier
Proofhash-Ersatz. Dieser Folgeumfang ist hier nicht implementiert.

Auch aktuelles POINT-Tennis hat noch keinen eigenen qualifizierten Effektvertrag.
Der neue Quellenpfad behält die bestehende Sperre gegen das Anwenden alter
Serve-Koeffizienten auf diese andere Gewinner-/Joint-Verteilung unverändert.
Quellenverarbeitung, numerischer Effektvertrag und empirische Freigabe sind
drei verschiedene Nachweise; nur den ersten davon als erledigt ausweisen.
