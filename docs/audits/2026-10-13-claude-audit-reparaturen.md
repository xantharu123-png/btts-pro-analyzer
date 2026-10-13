# BetBoy – Claude-Auditreparaturen vom 13. Oktober 2026

Stand: isolierter Arbeitsstand `C:/Projekt/BetBoy/betboy-app/.worktrees/audit-repairs-20261013`, Basis `c5a6264`. Die sechs freigegebenen Bereiche sind umgesetzt, qualifiziert und als **Codecommit `6636530267826fb37b3c834b8e94afa4ebc1b019` auf GitHub-main und VPS live** (13.10.2026,20:33CEST). Historische Fehlrunden darunter bleiben Fehlberichte und sind durch diesen neuesten Abschlussstatus ersetzt, nicht rückwirkend grün umgedeutet.

## Abschließende Qualifikation

- Vollsuite am eingefrorenen Index `b879d8d75ececc72848a3a2917bfab79959c8e95`:
  **13781 bestanden,97 bestehende Plattform-Skips,147 Untertests,0 Fehler**.
  A4:6648/58/36,2775,93s; B4:7133/39/111,946,85s.
  [Abdeckungsprüfung](C:/Projekt/BetBoy/output/audit-repairs-20261013/complete-qa-coverage.log)
  bestätigt jedes der13878 gesammelten Hauptitems exakt einmal ohne Fehler.
- Letzter statischer Anschlusscheck fand noch den fehlenden Merken-Button der
  manuellen Tennissuche. Neun neue Regressionen belegten den Fehler zunächst
  (6 RED/3 PASS). Der minimale21-Zeilen-Anschluss verwendet das vorhandene Modell,
  native Ereignis-ID und den bestehenden geschützten Bookmark-Speicherweg.
  Anschließend alle acht betroffenen UI-/Tennis-/Speichermodule **255/255 PASS**,
  10,16s, unabhängig statisch geprüft. [Abschlusslauf](C:/Projekt/BetBoy/output/audit-repairs-20261013/manual-tennis-bookmark-green.log).
  Keine neue Inferenz, Preisprüfung oder Einsatzfreigabe. Beide Favoritenseiten,
  mit/ohne Quote, ungebundene Daten, fehlender dauerhafter Scope und Schutz
  abgerechneter Einträge sind mit echter SQLite-Speicherung geprüft.
- Finale Code-/Testtree `0ca151db8eb99cbb058fd0891bfc09a492f13581`.
  Vollsuite und nachfolgende Delta-Prüfung getrennt ausweisen; keine Addition
  überlappender Prüfungen oder Behauptung einer erneuten finalen Vollsuite.
- Begrenzt veröffentlichter Code6636530: Offline-Linux-Imports inklusive
  Tennisrenderer PASS, aktive Kalibrierung legacy-v1. Beide Healthchecksok,
  App/Caddy aktiv, sieben Timer aktiv/enabled und letzte Dienste success/inactive.
  BackupTimer/-Dienst inactive,21GiBfrei. Kein neuer Backup-/API-/Sportscan.
- Beide gespeicherten ModelJSONs SHA-identisch vor/nach Release:
  Wettfinderf20422a802fd61461d8f8ab548f85228a1d083bdba92c51a0615bf9364a81bd4,
  RisikoBet6f0c5f3158fb2bbe08bc8b7692636a0f16847e90c32742a7f7497346b644e8f1.
  [Deploymentprotokoll](C:/Projekt/BetBoy/output/audit-repairs-20261013/deploy-code.log),
  [Produktionsnachweis](C:/Projekt/BetBoy/output/audit-repairs-20261013/production-code-final.log).
- Interner Browser nach frischem Reload:18 Merken-Buttons, erster sichtbar,
  keine Seitenexception und keine neuen Warnungen/Fehler seit18:33:12UTC.
  Während kurzem kontrolliertem Neustart gab es erwartete WebSocket-/502Logs;
  diese nicht löschen oder als permanente Appfehler ausgeben. Keine echten
  Produktions-Testmerker, Einsätze oder Geldbuchungen angelegt.
- Dieser Produktionsnachtrag wird dokumentations-only ohne Appneustart per
  Fast-forward veröffentlicht. Er ändert keinen Code oder geprüften Vertrag.

## Reparaturumfang

1. **Kalibrierung und Versionsbindung.** Die stärkere Projektion mit Zielsumme statt Zielmittel ist als expliziter Offline-Kandidat `lawv2/prediction-v15` verfügbar. Engine und direkter Projektionsprimitive behalten standardmäßig `lawv1/prediction-v14`. Originalrezept, Vorhersageversion, Baseline, Effektvariante und Kontrast sind geschlossen gepaart. Alte v1-Originale und Fit-Ausgaben bleiben lesbar und reproduzierbar; gemischte Trainingsgesetze und alte Fits auf einer v2-Baseline werden abgewiesen.
2. **Tenniszeitgrenze.** Turnierstatistiken werden erst nach tatsächlich belegter Verfügbarkeit zugelassen, nicht nach geratenen 10/15 Tagen ab Turnierstart. Fehlende Verfügbarkeitsbelege bleiben ausgeschlossen. Die Regeln verwenden konservative Grenzen für ungezonte Kalenderdaten; Turniernamen entscheiden nicht über die Zulassung.
3. **Tennisabrechnung.** Backtest, automatische und manuelle Shadow-Abrechnung teilen die deklarierte Ein-Satz-Regel. Unbekannter Sieger oder unbelegte abgeschlossene Sätze werden nicht als erfundenes Void beziehungsweise normales Endergebnis behandelt. Aufgaben/Walkover trainieren nicht den gesunden Kalibrierungskohortenbestand. Historische Abrechnungen werden nicht neu bewertet; RisikoBets separat eingefrorener Vertrag bleibt unverändert.
4. **Auszahlungsplausibilität.** Neue Daily3- und 15K-Gutschriften oberhalb des aus tatsächlich gespeicherten Einsatz und Quote abgeleiteten Normalbetrags benötigen eine ausdrückliche Zweitbestätigung und einen konkreten Buchmachergrund. UI und Store sichern dieselbe Grenze; bestätigte Sondergutschriften erhalten eigene versionierte beziehungsweise signierte Provenienz. Historische v1-Gutschriften werden weiterhin unverändert nachgespielt.
5. **Exakte Quotenprodukte.** Die Korridorzulassung verwendet Decimal-Produkte der bestätigten Dezimalquoten. `1.50 × 1.60 × 1.25` ist exakt `3.00`, unabhängig von der Reihenfolge; tatsächlich höhere Angebote werden nicht hineintoleriert. Der monetäre Ticketvertrag `hac-fdr-executable-frechet-v11`, Wahrscheinlichkeitsrechnung und bestehende ROI-Regeln werden nicht neu definiert.
6. **Persönliche Tippmerkliste.** „Tipp merken“ ist an den tatsächlichen Wettfinder-/Modellrenderer angeschlossen. `BOOKMARK` ist eine persönliche Modellnotiz mit Einsatz null und ohne erfundene Quote, Preisfreigabe oder Wettzusage. Preisgeprüfte Tipps bleiben getrennt. Die atomare Migration erlaubt unbekannte Preisfelder, bewahrt vorhandene Werte, IDs und Sequenz; abgeschlossene Tipps werden weder durch Upsert noch durch erneutes Merken überschrieben.

## Empirische Kalibrierungsentscheidung

[compare_calibration.py](C:/Projekt/BetBoy/output/audit-repairs-20261013/compare_calibration.py) verglich dieselben Rohgesetze und ausschließlich vor dem jeweiligen Spieltag gefitteten Kurven aus vorhandenen vertrauensgeprüften lokalen Caches. Keine Providerabfragen, Cachekopien oder Cacheänderungen. Das Ergebnis betrifft retrospektiv die Torprojektion, nicht eine vollständige unabhängige Modellfreigabe.

| Bestehender Cache | Bewertete Spiele | Brier v1 / v2 | Gemeinsamer Logloss v1 / v2 |
| --- | ---: | ---: | ---: |
| `history_103_2026_2026-08-01.pkl` | 140 | 0.1853306051 / 0.1859464968 | 3.1569910111 / 3.9819283885 |
| `history_265_2026_2026-08-01.pkl` | 164 | 0.2036576386 / 0.2041978790 | 3.0157397883 / 3.7046417180 |

304 reale chronologisch bewertete Spiele, beide Rezepte ohne Solverfehler. Frische Wiederholung: 23,5 Sekunden. Kleinere Verluste sind besser; v2 verschlechterte beide Kennzahlen in beiden Stichproben. Deshalb **v2 nicht qualifiziert und nicht aktiviert**. Die frische Wiederholung ist vollständig im [Vergleichsprotokoll](C:/Projekt/BetBoy/output/audit-repairs-20261013/calibration-comparison.log) gespeichert; Cachehashes und exakter Vergleichspfad bleiben nachvollziehbar. Rechnerisch stärkere Zielwirkung ist kein Qualitäts- oder Profitabilitätsnachweis.

## Gezielt belegte Softwareprüfung

Die Runden überschneiden sich und werden nicht zu einer Gesamtzahl addiert. Offline-Python nutzte den vorhandenen Launcher mit gesperrten externen Verbindungen und isolierten temporären Testdaten.

- Geldbereich: Ownerprüfung 300 bestanden plus 85 Untertests; unabhängige Prüfung 65/65.
- Merkliste: Ownerprüfung 78/78; unabhängige Prüfung 50 bestanden sowie tatsächlicher Streamlit-AppTest des Speicherwegs. Kein umfassender Browser-/Geräteabnahmestempel daraus.
- Tennis: 241 bestanden, drei dokumentierte Windows-Symlink-Skips; abschließende Reviewkorrektur 96 bestanden ohne Skips, unabhängige Gegenprüfung sechs bestanden. Einzelheiten und reale Cache-Nichtleckage im [Tennis-Handoff](C:/Projekt/BetBoy/output/audit-repairs-20261013/tennis-repairs-handoff.md) und [Kausalitätsprobe](C:/Projekt/BetBoy/output/audit-repairs-20261013/tennis_causality_evidence.py).
- Kalibrierungs-/Bindungsreview: 42/42 für geschlossene Variantenbindung, Gewichtung, Effekte und native D1-v1-Kompatibilität; danach der einzelne neue Default-Regressionsfall 1/1. Die aktive v1-Voreinstellung ist auch am direkten Primitive belegt. Scoped Whitespaceprüfungen sauber.
- **Vollständige konfigurierte Projektprüfung PENDING.** Erster Aufruf scheiterte bei fehlender Django-Portal-QA-Konfiguration. Zweiter Vorlauf mit bekanntem unverändertem Fixture/AST-Konflikt bei ca.10% gezielt beendet (kein PASS). Enger QA-Fix: exakt unveränderter Fixturehash mit LF-Attribut, Cricket-Pfad weiterhin eingefroren und Hockey-only-Zweige getrennt; sieben Mutations-/Replaytests bestanden. Der nächste vollständige fail-fast Lauf endete mit **3386 bestanden,25 Skips,117 Untertests,1 Fehler in1665,38s**: `test_schema2_point_live_original_replays_read_only_without_rebuild[ATP]` erkennt den neuen Loaderhash noch nicht als Point-Schema2-Codeidentität. Diese echte Integrationsbindung wird gezielt repariert, nicht die Integritätsprüfung umgangen. [Vollständiger Fehlbericht](C:/Projekt/BetBoy/output/audit-repairs-20261013/full-project-final.log). Kein Gesamt-PASS oder Release aus diesem Ergebnis ableiten.

## Zusätzlich geschlossene Integrations- und Windows-QA-Fälle

- Der vollständige Lauf deckte eine echte Tennis-Bindungslücke auf: Der neue
  Verfügbarkeitsloader war nicht in der eingefrorenen Point-Schema2-Identität
  enthalten. Die kompatiblen alten und neuen sechs Owner sind nun ausschließlich
  über vollständige statische LF/CRLF-Manifeste und gerichtete Replayübergänge
  zugelassen. Alte Originale bleiben read-only; unbekannte oder gemischte Owner
  und umgekehrte Übergänge bleiben abgelehnt. 162/162 betroffene Modultests und
  neun unabhängige Manifest-Gegentests bestanden.
- Der erste Dateishard B endete nach 2891 bestandenen Tests, acht Skips und
  85 Untertests mit einem Windows-Bash-Testaufbaufehler; A wurde bei circa 22%
  gezielt beendet. Beide Runden sind ausdrücklich kein Gesamt-PASS.
- Nur Bash-Testeingaben werden jetzt unverändert als UTF-8-Bytes übergeben,
  damit Windows keine zusätzlichen CR-Zeichen in Shellsyntax einschleust.
  Ausgabe und Fehler behalten die bisherige Textsemantik. Git Bash wird vor
  einem Windows-WSL-Alias bevorzugt. Nicht-Bash-Aufrufe sind unverändert.
  Zwei bisher lokal CRLF vorliegende, hartgepinnte Python-Skripte erhielten
  genaue LF-Attribute; Inhalte und erwartete kanonische Hashes ändern sich nicht.
  Keine Sicherung oder Produktänderung durch diese Testreparatur.
- Die vollständigen 354 Hooktests und 112 Updater-/Serverprüfungen bestanden;
  ein bestehender Linux-flock-Skip bleibt. Drei neue Adapterregressionen bestanden.
- Neue Vollcollection: 13878 Haupttests in 367 Modulen. Der finale A2/B2-Lauf
  prüft alle Module disjunkt; vor dem tatsächlichen Abschluss kein Gesamt-PASS.
  `check_complete_qa.py` bindet die beiden JUnit-Ergebnisse an jedes gesammelte
  Haupttest-Item und verhindert fehlende oder doppelt gezählte Prüfungen.

Auch A2/B2 endeten mit Fehlern, nicht mit einem Gesamt-PASS. A2:
2771 bestanden,19 Skips,32 Untertests,1 Fehler in1913,86s. Ein bisheriges
Sequenzfixture behauptete CHF120 Rückzahlung bei CHF50 Einsatz und Quote1,20;
der neue Auszahlungswächter verweigerte diese Gutschrift korrekt. Nur die
tatsächlich erfasste Erstquote im Test wurde auf2,40 korrigiert. Folgeeinsatz
CHF120 und maximales Nettorisiko CHF50 bleiben unverändert geprüft. 87 betroffene
Tests und anschließend alle251 Daily3-Tests bestanden, keine Produktlockerung.

B2:4835 bestanden,8 Skips,111 Untertests,1 Fehler in1479,91s. Weitere exakt
gepinnte native QA-Dateien waren lokal CRLF statt ihrer unveränderten Git-/Linux-
Bytes. Diese nachgewiesenen Pfade erhalten nur exakte LF-Attribute und bewachtes
Formatieren; weder Quelldatei-Gitblobs noch bestehende Pins werden ersetzt.
Native-Chain-Modul vollständig65/65 bestanden. Weitere Protokollprüfung und
bestehende Linux/root-Plattformskips sind separat auszuwerten.

Die vollständige siebenmodulige Protokollrunde ist danach abgeschlossen:
271 bestanden,54 bereits bestehende Linux-/Root-/openat-/FIFO-/DAC-/pidfd-
beziehungsweise native Coordinator-/Ordinary-UID-Voraussetzungsskips,0 Fehler,
148,56s. Die vorherige Runde270/54/1 bleibt ein Fehlbericht: ein zusätzliches
unverändertes Transporttemplate war ebenfalls CRLF. Nach seinem exaktpfadigen
LF-Schritt sind alle13 formatierten Quellen roh bytegleich zu HEAD und Index;
die historische inventory.py bleibt unangetastet. Keine Pinänderung oder neue
Auslassung. Vollständige Fallnamen/Gründe im
[Protokoll-JUnit](C:/Projekt/BetBoy/output/audit-repairs-20261013/native-pins-final-template.xml).

Finaler Source-/Testindex `c637efbfcd9ac91f244008cb326dc334a108ff17`;
gegen den Volltest-Startindex `cfd4e3c6b751010b8b09241bcb994b5254df3514`
ändert sich ausschließlich die abschließende LF-Gitmetadatenzeile. Alle
Produkt-/Test-Gitblobs bleiben während A3/B3 unverändert.

Die erneuerte Sammlung bleibt13878 Haupttests/367 Module. Finale A3/B3-Läufe
prüfen184/183 disjunkte Module vollständig, jetzt ohne Fail-fast, damit alle
verbleibenden Prüfungen tatsächlich ausgeführt werden. Noch kein Gesamt-PASS;
Abschlussbindung über die JUnit-Dateien und `check_complete_qa.py`.

B3 wurde anschließend vollständig ausgewertet:7124 bestanden,39 Skips,
111 Untertests,neun Fehler in1201,19s. Alle neun betreffen zwei weitere
unveränderte CRLF-Dateien: den gepinnten nativen Preparation-Worker und die
eingefrorene Tennis-Simulator-Fixture. Deren bewachte LF-Kanonisierung ändert
keinen Gitblob, bestehenden Hash oder Testinhalt. Beide vollständigen Module
danach226/226 bestanden,3,41s,0 Skips. Endgültiger Metadaten-/Code-/Testindex:
`b841b5ec0f14ec99f7ba068ae82f14ef014712f5`. A3 läuft unverändert weiter;
B4 wiederholt die gesamte zweite Modulhälfte. Nur A3/B4 und die exakte
Sammlungsbindung können den abschließenden vollständigen PASS belegen.

B4 vollständig:7133 bestanden,39 bestehende Plattform-Skips,111 Untertests,
0 Fehler,946,85s. A3 vollständig:vier Fehler,6644 bestanden,58 Skips,
36 Untertests,2894,95s. Ein bereits unveränderter JSON-Originalbeleg hatte
CRLF-Zeilenenden statt seines bestehenden LF-Hashes. Zwei Testdoubles kannten
die neuen expliziten Parameter `law_version` beziehungsweise `save_source`
nicht. Es wurden nur die exakte JSON-LF-Zeile/Formatierung und diese beiden
Stubsignaturen korrigiert. Die aktive v1 und Herkunft „Fußball Prematch“ werden
zusätzlich geprüft; Familien-, Sortier-, Tabellen- und DataFrame-Assertions
bleiben erhalten. Keine Produkt- oder Pinänderung. Beide vollständigen UI-/
Wettermodule188/188 und beide Scanner-/Kalibrierungsmodule13/13 bestanden.

Finaler Produkt-/Test-/Metadatenindex `b879d8d75ececc72848a3a2917bfab79959c8e95`.
Gegen b841 sind ausschließlich diese zwei QA-Testdouble-Dateien und die
LF-Metadaten verschieden; B4-Tests und sämtliche Produkt-Gitblobs unverändert.
A4 prüft die gesamte erste Hälfte erneut. Erst A4/B4 plus Sammlungsbindung
berechtigen zum vollständigen Abschluss; keine gescheiterte Runde addieren.

## Separate Produktionsvorprüfung

Der lesende Serverabgleich vor diesem Release fand auf dem unveränderten
`c5a6264` eine bereits bestehende Fußball-Shadow-Datenlücke. Für Fixture1497716
fehlt eine akzeptierte aktuelle Bet365-Beobachtung mit Providerzeit. Der Runner
meldet deshalb korrekt `partial/exit1`, verschiebt den Fall und speichert keine
erfundene Prognose mit Quote. Der Log unterscheidet nicht zuverlässig zwischen
fehlender, veralteter oder nicht zuordenbarer Anbieterquote.

Zwei alte abgerechnete Shadow-Zeilen waren schon im früheren Lauf ungültig:
`invalid_quote_provenance/malformed_settlement`. Deshalb bleibt deren gesamte
CLV-/ROI-Evidenzauswertung gesperrt. Unabhängige lesende Quellenprüfung bestätigt
den vorgesehenen Fail-closed-Pfad im bisherigen Code, keine Regression dieses
Pakets. Kein zusätzlicher Scan, Löschen oder Umschreiben der Altbelege. Reguläre
Läufe und eine gesonderte Prüfung vorhandener Originalbelege bleiben Restarbeit.

## Datenverträglichkeit und Rollback

Die neuen Geld- und Bookmark-Verträge erweitern den lesbaren Bestand; sie ersetzen keine signierte Historie. Nach der ersten Daily3-v2-Sondergutschrift, neuen 15K-Adjustment-Provenienz oder einem nullable Bookmark ist ein ungeprüfter Rücksprung auf alten Code nicht sicher: alte Leser kennen diese Verträge nicht vollständig. Ein Rollback muss die neuen Leser-/Verifier-Verträge erhalten oder vorher separat qualifiziert werden. Keine Buchungen löschen, zurückübersetzen oder alte Datenbanksicherungen einspielen, um einen alten Leser scheinbar kompatibel zu machen.

Keine neuen Sport-/Provider-Scans, Backups, Produktionsdatenbankzugriffe oder historische Geldumschreibungen für dieses Paket. Commit, Push, VPS-Übernahme und Produktions-/Browserabnahme sind eigene noch zu belegende Gates. Inherited WIP außerhalb dieses isolierten Patches bleibt unberührt.

Die Reparaturen belegen weder tatsächlich aktive Verletzungs-, Wetter- oder Müdigkeitseffekte noch künftigen ROI, tägliche Gewinnziele oder universelle historische Tenniskausalität. Neue EV-/Preisgates, Währungswechsel und eine Umdeutung persönlicher Bookmarks zu Wettfreigaben gehören nicht zu diesem Paket.
