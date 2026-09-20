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
Keine Änderung an Prognosemathematik, Daily3-Auswahl, Quote, Cricket, Echtgeld,
Journalmodus, Timeouts, Datenbankschema oder bestehenden Daten.

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
