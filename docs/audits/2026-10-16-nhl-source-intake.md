# NHL: native Einsatzdaten und Tageslauf, 16.10.2026

## Auftrag und ehrliche Grenze

NHL zuerst: Gegnerstärke, Form, Torhüter, Ausfälle und Belastung; danach testen,
main pushen und auf dem VPS veröffentlichen. Keine neuen Backups, keine bezahlte
Quelle, keine zusätzliche automatische Sportsuche.

Dieser Bericht dokumentiert die native Datenerfassung. Sie ist **nicht** der
Abschluss des vollständigen Personalmodells. Die vorhandene Grundrechnung lernt
Angriff, gegnerische Defensive und Heimfaktor gemeinsam. Die letzten5/10 Spiele
in einer Karte sind noch kein zusätzlich trainierter kurzfristiger Formeffekt.
Es werden keine erfundenen Goalie-, Verletzungs- oder Müdigkeitsprozente aktiviert.

## Neue Quellenstrecke

- Kostenlose native NHL-Boxscores, nur exakte Spiel-/Team-/Spieler-IDs, unterstützte
  Saisons2025/26 und2026/27, reguläre Saison und Playoffs.
- Tatsächliche historische Torhüterstarts, Schüsse, Saves, Gegentore, Spieler-
  Eiszeiten und Schichten. Ganze Spielzeit bleibt ganze Spielzeit; keine erfundene
  Trennung in reguläre Spielzeit/Verlängerung und keine erfundenen Endzeitpunkte.
- Ein historischer Starter ist keine Vorab-Bestätigung. Eine fehlende Ausfallliste
  bedeutet nicht, dass alle Spieler gesund sind. Zukünftige Boxscores können
  noch keinerlei Spielerdaten enthalten.
- Anschluss ausschließlich an den fälligen regulären NHL-Tageslauf, dieselben
  bereits entdeckten Spiele und bereits geladenen Resultate. Kein zweiter Scan,
  keine Abfrage durch Kartenaufbau oder Import.
- Aktuelle NHL-Spiele plus höchstens die zwei jüngsten abgeschlossenen Spiele
  je beteiligtem Team innerhalb14Tagen. Native Identität statt Namensraten.
- Höchstens32 native Körperabrufe pro UTC-Tag, gemeinsame transaktionale
  Reservierung im vorhandenen Resultatspeicher, Fehlversuche mitgezählt.
- Nur die jeweils neuesten passenden revisionsgebundenen Belege,24h Wiederverwendung;
  echte Korrekturen bleiben mit ihrer tatsächlichen Empfangszeit erhalten.
- Bestehender B1-Inhaltsspeicher statt neuer Datenbank: maximal256KiB je Antwort,
  höchstens1MiB neuer Inhalt/Belege pro Aufruf, keine Körperkopien in Prognosen.
- Interner Adminbericht mit Zählern/Fehlercodes; keine neuen technischen Texte
  auf Kundenkarten. Basishistorie und Modellwerte werden nicht überschrieben.

## Echte Quellenprobe, nicht rückdatierter Modellnachweis

Zwei genau begrenzte kostenlose NHL-Anfragen:

- Abgeschlossenes Spiel2025020001, Antwort13.529Bytes, tatsächlich empfangen
  16.10.2026 20:03:11.738473UTC. REG und tatsächliche Spieler-/Goalie-Einsatzdaten.
- Zukünftiges Spiel2026020119, Antwort1.343Bytes, tatsächlich empfangen
  16.10.2026 20:03:23.875112UTC. FUT ohne gespielte Werte/Starterbestätigung.

Die eingecheckte Fixture enthält ausdrücklich nur ausgewählte echte Spieler und
keinen vollständigen Kader. OT/SO-/Playoff-Grenzen werden zusätzlich synthetisch
getestet; dafür wird keine echte Quellenabdeckung behauptet.

## NHL-Nachtfenster

Zusätzlich war der automatische Tageslauf fachlich unvollständig: ein Spiel der
folgenden US-Nacht lag außerhalb des Schweizer Kalendertages und war am nächsten
Morgen schon gestartet. Vier spätere Leser filterten solche Spiele ebenfalls aus.
Der native NHL-Zweig erhält jetzt ausdrücklich ein Fenster bis24 verstrichene
Stunden. Ein gemeinsamer Filter gilt vor der Historien-/Kontextsammlung sowie in
Projektion, Abdeckung, Katalog und gespeichertem Auswahlleser. Tatsächliches
Spieldatum bleibt erhalten; manuelle Tagesbereiche, andere Anbieter/Sportarten
und Daily3-Kalenderbudget bleiben unverändert. Inklusive24h-Grenze,24h+1Sekunde,
gestartete Spiele, historische Suchdaten, geänderte Uhren und beide Schweizer
Zeitumstellungen sind Bestandteil der23 neuen Offline-Fälle.

## Noch fehlender vollständiger Modelleffekt

1. Vor Spielbeginn gespeicherte Verfügbarkeits-/Starterbelege. Die offizielle
   NHL-Projektionsseite hat zeitgestempelte Ausfall-/Aufstellungsabschnitte, aber
   keine Spieler-IDs und keine historische Snapshot-Garantie; der Boxscore ersetzt
   diese Quelle nicht. Ein solcher Intake ist noch nicht verbunden.
2. Owning Hockey-Training, Eingabefallbau, Replay, Ergebnis-/Verteilungsverlust und
   Abnahme für diese echten Daten. Der vorhandene synthetische C3-Intervallkern
   kann Ganzspiel-Eiszeiten nicht als vollständige Manpower-Intervalle übernehmen.
3. Zeitgetrennter Qualitätsnachweis gemäß freigegebenem D1/D2-Vertrag. Mindestens
   200 unberührte verschiedene Zielspiele und die übrigen vorab festgelegten
   Prüfungen dürfen nicht durch hundert Softwarefixtures ersetzt werden.

Neu abgerufene alte Boxscores sind brauchbare historische Daten, aber keine
damals vor Anpfiff gespeicherten Verletzungsinformationen. Die separate
62/100-Grundmodell-Stichprobe ist kein Personal-, Rendite- oder Freigabenachweis.

## Prüf- und Veröffentlichungsstand

Produktcode sowie NHL3-Spezifikation/Qualität unabhängig geprüft: PASS. Der
No-Backup-Helfer wurde nach reproduziertem Fail-open bei leeren Git-Fehlerausgaben
auf geprüfte Zuweisungen korrigiert: RED6→GREEN10; unabhängiges Re-Review PASS.
Der reine spätere Dokumenten-Pull hat ebenfalls eine geschlossene Pfadliste,
geprüfte Inventarabfragen und drei bestandene Offline-Gegentests.

Die vollständige Prüfung ist **zweistufig**, kein grüner erster Durchlauf:

- `full-qa-01`:14.680 gesammelt, sämtliche14.536 früheren IDs erhalten.
  A:10PASS; B/C/D zunächst Exit1 durch Windows-Sandbox-Beschränkungen bei
  Hardlinks, atomaren Dateiumbenennungen und Bash. Originale Fehler-XMLs/Logs
  und der ursprüngliche FAIL-Bericht bleiben unverändert erhalten.
- Unveränderter Code: alle betroffenen ganzen Module einschließlich dreier
  zusätzlicher Sandbox-Skips außerhalb der Sandbox, weiterhin ohne externes
  Netzwerk, nachgeprüft. **1.465PASS/21 bestehende Skips/85 bestandene Untertests**,
  Exit0. Kein Assertion-, Produktcode- oder Skip-Umbau für diese Fehler.
- `native-recheck-01/aggregate-result.json`:PASS, alle12 Prüfungen wahr.
  Exakt gleiche Fallinventare; jeder ursprüngliche Fehler und jeder zusätzliche
  Skip jetzt tatsächlich PASS; gesamte Abdeckung **14.582PASS/98 unveränderte
  Skips**, kein Fall verloren,797 Quell-/Fixture-Hashes unverändert.

## Tatsächliche Veröffentlichung

Code **bd035b71cf02368b21b72bd4ef2e765329769e8e** auf GitHub main und VPS.
Erster Versuch `deploy-nhl-01.log` stoppte nach erfolgreichem Fast-Forward vor
dem Neustart: Der externe Smoke validierte normalisierten Inhalt ohne den
erforderlichen `observed_at`-Empfangsbeleg. Der Produktcode wies das korrekt ab.
Regression aus dem echten Smoke-Block RED→GREEN; Fix verwendet ausschließlich
die vorhandenen echten Fixture-Zeitstempel. Die eng begrenzte Resume-Funktion
fordert den bereits gepullten exakten Zielcommit und erhält Baseline-Ancestry,
Diff-Allowlist, Job-/Timer-/Statusprüfungen. Unabhängiges Re-Review PASS.
18 unveränderte Helfertests außerhalb der Windows-Sandbox PASS; ihr zusätzlicher
Sandbox-Versuch scheiterte beim Bash-Start an Windows-Named-Object-Berechtigungen.
Keine Produktänderung oder Testlockerung dafür.

`deploy-nhl-02.log`: Exit0, Offline-Smoke `ok`, AppPID1198478→1200874,
App/Caddy aktiv und lokaler/öffentlicher Healthcheck `ok`. Wettfinder- und
RisikoBet-Snapshotfingerprints vor/nach Neustart identisch. Kein Backup,
Sportscan, Datenbankkopie/-migration, Cleanup oder Paketinstallation.
Backup-Timer disabled/inactive; acht bestehende andere Timer geplant. Acht alte
fehlgeschlagene September-Prüfdienste bleiben unberührt als historische Belege.

**Ausstehender Betriebsnachweis:** Erster regulärer NHL-Erfassungslauf nach dem
Deploy ist17.10.2026 03:35 Europe/Zurich. Seine Quellenzähler sind noch nicht
bekannt. Kein manueller zusätzlicher Lauf gestartet; keine Vollmodellfreigabe.
Die abschließende Übergabe ist ein separater reiner Docs-Commit ohne App-Neustart.
Alle Zwischenstände/Fehlversuche unter
`C:/Projekt/BetBoy/output/nhl-context-20261016/` bleiben erhalten.
