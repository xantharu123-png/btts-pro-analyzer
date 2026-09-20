# Fortsetzung: Originalaufnahme und konkurrierende Datenläufe

## Geprüfter Ausgangsstand

Am 20.09.2026 standen Worktree, lokales main, GitHub und VPS auf
`2758619e8dced04152b305280728340a91af156b`. App/Caddy und öffentlicher
Healthcheck waren erreichbar; das Tagesbackup blieb deaktiviert.
Die alte Behauptung, der neue Aufnahmebeleg stehe noch vollständig aus,
ist durch den echten Nachtlauf überholt, nicht aber die fachliche Restliste.

## Tatsächliche Datenabdeckung

- 23 gespeicherte Fußball-Originale zu 19 verschiedenen Spielen, jeweils
  einschließlich gebundenem Manifest verlustfrei lesbar.
- **Alle 23 sind partiell; null vollständig quellgebundene Trainingsfälle.**
  Die 4.604 ungelösten Bezüge sind Referenzen über mehrere Originale, keine
  4.604 unabhängigen Spiele: 528 ohne native Referenz, 4.076 mit dem gespeicherten
  Sammelstatus `source-retention-budget-exhausted`.
- Aus den tatsächlichen Originalen: 714 dieser Bezüge stammen aus
  `football-data-results-only`; 3.890 aus nativen, noch nicht gebundenen Reihen.
  Der Budget-Sammelstatus allein erklärt deshalb nicht jede einzelne Lücke.
  CSV-Reihen besitzen keine nachgewiesene native Spieler-/Einsatzidentität.
- Aufnahmebudgets bleiben 4 MiB/Sitzung, 8 MiB/UTC-Tag und 128 MiB insgesamt
  zusätzliche JSON-Nutzlast. Keine Zähler zurückgesetzt, keine Zusatzkäufe,
  kein Training oder neuer numerischer Effekt freigeschaltet.

## Reproduzierter technischer Fehler

Tennis am 20.09.2026: Start 07:17 CEST, Ende 07:18:15, Exit 1.
ATP/WTA-State-Rebuild meldeten `OperationalError`; der Tages-Scan brach beim
Speichern mit `sqlite3.OperationalError: database is locked` ab.

Der Fußball-Ergebnisempfänger validierte in einer offenen SQLite-Lesetransaktion
den gesamten Beobachtungsbestand, auch Tennisdaten. Der VPS enthielt bei der
Messung 957.638 Beobachtungen. Der gleichzeitig laufende Wettfinder hielt eine
Lesesperre auf genau dieser Datenbank. Die Spielerhistorien-Inventur hielt
ebenfalls während ihrer CPU-Validierung den Leser offen. Der Fehler ist mit
echten zweiten SQLite-Verbindungen in beiden Pfaden reproduziert.

## Korrektur

1. Ergebnisempfang liest nur die nativen Event-IDs seiner bereits empfangenen
   Ergebnisantwort. Abfragen werden zu höchstens 128 IDs parametrisiert.
   Sämtliche Arten/Quellen dieser Events werden geprüft; eine manipulierte
   `source`-/`kind`-Spalte versteckt keine beschädigte Beobachtung.
2. Zusammengehörige Rohzeilen werden in einem konsistenten Lesebild übernommen.
   Die Verbindung ist vor Hash-, Inhalts-, Zeit- und Identitätsprüfung geschlossen.
   Nachträglich hinzugefügte Beobachtungen gelangen nicht in dieses Lesebild.
3. Auch die Spielerhistorien-Inventur gibt den Leser vor der Validierung frei.
   Abrufgrenzen, Wartefristen und tatsächliche Quellenzeiten bleiben unverändert.

Dies ist eine auf empfangene Events begrenzte Laufzeitprüfung, keine globale
Datenbankprüfung. Nicht angefragte Events erteilen keine Ergebnisfreigabe.
Die erste Korrektur änderte weder Prognosemathematik, Daily3-Auswahl, Quote,
Cricket, Echtgeld, Journalmodus, Timeouts, Datenbankschema noch bestehende Daten.

## Nachweise vor Veröffentlichung

- Vier neue Gegenproben zunächst fehlgeschlagen: beide Schreibkonflikte,
  unnötig fremder Event im Inventar und Schreiben während der Validierung.
- Danach 123 direkte Tests bestanden; zusätzlich Batch-/Leerscope-Regressionsfälle.
- Eingefrorener betroffener Lauf: **578 bestanden, 4 übersprungen, 53,60 s**.
  Kein vollständiger 10k-Testlauf und kein unabhängiger Agentenreview behauptet.
- Rein lesender VPS-Probelauf des Korrekturcodes, ohne Austausch produktiver
  Dateien: vorsätzlich großer Scope von 1.096 Fußball-Events, 532 beobachtete
  Vorab-Events; 73,240 s Gesamtprüfung, davon **2,207 s SQL-Lesephase**.
  Spielerhistorie: 679 mögliche Nachabrufe, 54,291 s Gesamtprüfung, davon
  **0,650 s SQL-Lesephase**. Prozess-Spitzenspeicher 233.728 KiB.
  Die verbleibende CPU-Zeit blockiert diese Datenbank nicht mehr.

## Weiter offen

Ein erfolgreicher echter Tennis-Gesamtlauf nach Deployment ist separat
nachzuweisen. Ebenso bleiben vollständige native Fußballbezüge, versionsgleiche
Replay-/Trainingsanbindung, echte Spieler-/Ersatz-/Belastungsmerkmale und die
vorgegebene unbenutzte Modellabnahme offen. Gespeicherte Originale und bestandene
Softwaretests sind keine nachgewiesene Verletzungs-/Müdigkeits-/Wetterwirkung
oder bessere Wettqualität. Cricket bleibt ausgenommen.

## Veröffentlichung

Funktionscommit `bc6fef3d7775a301ae1808c380b42670b3413ffa` auf main/GitHub
und am 20.09.2026 um 09:31 CEST auf dem VPS bestätigt. Vor dem Push im
Hauptcheckout nochmals **125 direkte Tests in 9,77 s** bestanden.
Linux-Gegentest im automatisch entfernten, isolierten Testordner: beide
echten konkurrierenden Schreiber können während der Validierung committen.
Keine Produktionsdatenbank für diesen Gegentest verändert.

Code-only-Fast-forward: bestehende Jobs regulär beendet, App neu gestartet,
vorher aktive Rechentimer wiederhergestellt; öffentlicher/lokaler Healthcheck
`ok`. Keine Datenmigration, Installation, Sicherung oder Bereinigung.

Der echte Tennis-Neulauf startete 09:31:57 CEST. Modellaufbau erfolgreich nach
25 s: ATP behielt seinen gültigen Stand, WTA wurde erfolgreich veröffentlicht.
WTA-Datenstand bleibt ausdrücklich **12.09.2026**, nicht das neue Baudatum.
Der Tages-Scan scheiterte dennoch um 09:45:42 mit Exit 1 beim Veröffentlichen
einer Prognose (`put_artifact`, Commit in `_connect`, `database is locked`).
42 Prognosen waren vorbereitet, eine veröffentlicht; 26.567 Beobachtungen
waren zuvor gespeichert worden. Das ist kein erfolgreicher Gesamtlauf.
Ab 09:37 lief der normale Wettfinder parallel. Dessen 09:11-Lauf vor Deployment
blieb wegen zwölf fachlicher/operativer Teildatenprobleme degraded.

## Zweite gemessene Konfliktphase und Folgekorrektur

Nach Freigabe der langen CPU-Prüfungen verblieb das physische Kopieren des
konsistenten Tennis-Bestands: bei 1.008.095 Beobachtungen 1.423.547.529 Bytes
temporäre Nutzlast in **21,626 s SQL-Lesephase**. Rein lesender Probeprozess;
seine temporäre Datei wurde automatisch geschlossen/entfernt, keine produktiven
Zeilen verändert. Bisher gaben konkurrierende Schreiber bereits nach 5 s auf.

Die Folgekorrektur setzt für Kontextleser und Artefaktschreiber eine gemeinsame,
endliche Wartezeit von **60 s**. Die eigentliche Sperrzeit wird nicht verlängert:
nur ein blockierter Zugriff darf auf das Ende der gemessenen physischen Phase
warten. Kein Wiederholungskreislauf und kein Verschlucken von Fehlern; normale
Worker-Laufzeitgrenzen bleiben bestehen. Journalmodus DELETE, Schema,
Transaktionsgrenzen, Prüfinhalte, Prognosen und gespeicherte Daten unverändert.

Zwei neue Regressionen zunächst rot: echter Schreiber hinter einer sieben
Sekunden gehaltenen Lesetransaktion und gemeinsames endliches Wartebudget.
Mit Korrektur: **980 Tests bestanden, 5 übersprungen, 274,77 s**. Noch keine
Bestätigung eines erfolgreichen vollständigen Tennislaufs nach diesem Nachtrag.
Die CPU-Kosten des großen Bestands und die oben dokumentierten fachlichen
Daten-/Modelllücken werden hiermit nicht als gelöst ausgegeben.

Folgekorrektur `9c579fe517ae3fb6331a6f975c69c38ea387d213` auf main/GitHub
und VPS am 20.09.2026 um 10:04 CEST bestätigt. Hauptcheckout zusätzlich
**67 Tests bestanden, 5 Skips, 11,06 s**. Echte Linux-Probe: Leser hält
22 Sekunden, konkurrierendes vollständiges `put_artifact` einschließlich
Verbindungs-/Schemaöffnung wartet 22,066 s und committed danach erfolgreich.
Beide Artefakte verlustfrei zurückgelesen, Produktionsdatenbanken unberührt.
Temporärer Testordner automatisch entfernt.

App/Caddy und öffentlicher/lokaler Healthcheck gesund. Sechs Rechentimer plus
Retention-Timer aktiv geplant; Tagesbackup weiterhin deaktiviert. Bestehender
Wettfinderlauf endete vor Codewechsel um 10:04:03 erneut degraded, Exit 1;
dieser fachliche/operative Zustand wird nicht durch den Healthcheck aufgehoben.
Neuer vollständiger Tennis-Neulauf seit 10:04:13; Modellaufbau nach 19 s
erfolgreich, WTA-Ergebnisstand weiterhin 12.09.2026.

## Verifiziertes Ende des neuen Live-Laufs

**20.09.2026, 10:19:32 CEST: Exit 1, Tages-Scan TIMEOUT nach 900 s.**
Es gab in diesem Lauf keinen gemeldeten `database is locked`-Abbruch:
26.567 Beobachtungen wurden gespeichert und der Modellaufbau abgeschlossen.
Der Scan für 21.09. hatte 183 Fixtures und 48 vorbereitete Prognosen.
Letzte abgeschlossene Phase: `history_ready`, WTA mit 563.386 Referenzen;
letzte begonnene Phase: `prepare`, 48 native Einträge. Weder `prepared` noch
`complete` wurde erreicht. Diese 48 Prognosen sind deshalb **nicht** als
erfolgreich veröffentlichte Tagesauswahl auszugeben. CPU 14 min 47,364 s,
Spitzenspeicher 2,6 GiB laut systemd; keine Laufzeitgrenze erhöht.

Zusätzlicher lokaler CPU-Gegentest, ohne Produktionsdaten: jeweils drei
`context_payload_key`-Aufrufe mit synthetischen gültigen Gewinner-Eingaben.
Unterhalb der Referenzcache-Grenze (499.999 Bezüge): 3,281 s unter cProfile;
mit 563.387 Bezügen: 3,313 s. Die noch vorhandene 500k-Cachegrenze allein
ist dadurch **nicht** als Ursache des 900-s-Abbruchs belegt. Sie wurde nicht
blind erhöht. Es fehlen genaue Zeitanteile der vollständigen History- und
spielerspezifischen Feature-Vorbereitung im echten Abschlusslauf.

### Nächster konkreter Einstieg

1. Die CPU-Anteile von History-Aufbau, `for_event`, `_original`/
   `tennis_features_v3`, Zustandsprüfung und Schlüsselbildung an demselben
   eingefrorenen Bestand getrennt messen. Keine neue Sammlung, keine
   vergrößerte Warte-/Speichergrenze und keine verkürzte Herkunftsprüfung.
2. Den nachgewiesenen wiederholten Arbeitsschritt mit unveränderten Bytes,
   Zeitgrenzen und Gegenproben beheben; anschließend kompletter normaler
   Tennis-Lauf. Der Lock-Gegentest allein schließt dieses Ziel nicht ab.
3. Native Fußballbezüge und versionsgleichen Trainingspfad vervollständigen;
   erst danach die ausdrücklich noch offene empirische Kontextqualifikation.

Frühere Änderungen aus der Account-Übergabe (`1592afa`, `5be83cf`, `84292f6`
und `2758619`) sind nach frischem Git-Ancestry-Abgleich vollständig enthalten.
UI-Vereinfachung, Spielgruppierung und Daily3-Regel wurden hier nicht erneut
umgebaut; keine neue Browser-/Gewinnqualitätsfreigabe behauptet.
