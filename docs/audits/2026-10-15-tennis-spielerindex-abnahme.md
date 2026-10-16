# Tennis-Spielerindex: lokale Abnahme grün, nativer Nachweis gescheitert

Stand 16.10.2026. **Task 6 nicht abgeschlossen. Kein freigegebener Index-Release.**
Der kompatible Vorbereitungsstand `c110d8e741e1e50fa63b69532aee40a3d4346748`
ist auf `main` und dem VPS. Der Index wurde vollständig aufgebaut, anschließend
nach dem fehlgeschlagenen unveränderten Vier-Fall-Test ausdrücklich deaktiviert.
Kein Rücksprung auf alte schemaunverträgliche Binaries.

## Lokale Softwareprüfung

- Quelle genau `c110d8e`, unabhängige Aufgaben-/Abschlussreviews abgeschlossen.
- Ganze QA03: **14.239 bestanden, 98 identische Skips, null Fehler,
  147 bestandene Untertests**. Alle 14.337 Haupt-IDs genau einmal, sämtliche
  älteren Bestände erhalten; 771 Quellhashes und Root-WIP unverändert.
- A Exit0: 7.074 bestanden/38 Skips/143 Untertests, 4030,46 s.
  B Exit0: 7.165 bestanden/60 Skips/4 Untertests, 3835,11 s.
- 29 zuvor festgehaltene Fehler-/Unterbrechungsbelege unverändert erhalten.
  QA01 bleibt INCOMPLETE, QA02 und die damalige Sandboxprüfung bleiben FAIL.
- Belege außerhalb Git: `output/tennis-player-index-20261015/qa-final-03/`;
  `final-summary.json` SHA256
  `5699afaae5969b8c7ac5ee9684c826c8fa29029483f7532e782d43c87a0b81b9`.

Diese Prüfung betrifft nicht die später hinzugekommene Sortieränderung
`0859468`. Deren separate QA01 endete mit14.250 PASS/2 FAIL/98 unveränderten
Skips/147 Untertests; alle14.350IDs und Quell-/Root-Freeze erhalten. Zwei reine
Prüfadapterlücken sind ohne Produktänderung mit7fea742 berichtigt,432betroffene
Tests bestanden und unabhängig ohne Befunde geprüft. Neue VollprüfungQA02 am
unveränderten8c36095 vollständig PASS:14.252bestanden/98identischeSkips/
147Untertests; alle14.350IDs genau einmal,771Quellhashes/RootWIP und118frühere
Receipts unverändert. BeideExits0, abschließende Prüfung07:56:17UTC. QA01 bleibt
als fehlgeschlagener Lauf erhalten. DieserSoftwarepass beseitigt den separaten
Index-Eingabebudget-FAIL nicht.

Die getrennte Sortierung ist anschließend als Produktivstand38f73ed auf main
und VPS veröffentlicht worden: Fast-Forward, nur App-Neustart1159516→1175628,
gespeicherte Modell-JSONs unverändert, Index weiterhin invalid/deaktiviert,
siebenTimeraktiv+aktiviert,Backup-Timerdeaktiviert, beideHealthchecksok.
Interner Browser bei1240×884: erste3Spielmaxima85,7/84,1/81,3%, darin22Märkte
jeweilsabsteigend; alterReihenfolgeumschalterfehlt, Spielblockzu/auf und
Daily3ausSeitenkarte→korrekterBereich→zurück bestanden, null neueKonsolenfehler/
-warnungen. Daily3zeigt1Karte; Mehrkarten-/Einsatzautorität nurdurchSoftwaretests
belegt. Kein Live-Mobilnachweis und nicht alle eingeklapptenSpiele geöffnet.
Artefakte: output/probability-order-20261016/browser-*. Keine Wett-/Budgetaktion.

Frische getrennte Serverprüfung zeigt außerdem Shadow Exit1/partial wegen einer
fehlenden aktuellen Bet365-Providerzeitquote und zweier historisch unvollständig
belegter Abrechnungszeilen. Kein erfundener CLV-/Renditenachweis und keine
pauschale Behauptung fehlerfreier siebenJobs. Diese Datenfrage bleibt offen.

Unabhängiger rein lesender Receipt-/Raw-Git-Abgleich dokumentiert unter
`C:/Projekt/BetBoy/output/tennis-player-index-20261015/runtime-evidence-review.md`.
Kein erneuter nativer Versuch und keine nachträgliche Umdeutung eines FAIL.

## Kompatible Vorbereitung und Aufbau

Nur Fast-Forward `4ece002..c110d8e`, ruhende Jobs und mehr als sechs Minuten
bis zum nächsten Timer vor der Bereitstellung. Offline-Import und bestehende
numerische Quellenfamilie geprüft. Nur App-Neustart, PID1136736→1159516;
gespeicherte Wettfinder-/RisikoBet-Modell-JSONs dabei byte-identisch.
Keine neue Sicherung, Datenbankkopie, Sport-/API-Abfrage, Bereinigung oder
Änderung an Quoten, Wettformeln, Tickets oder Geldbewegungen.

Explizite Initialisierung ergänzte nur die optionalen Tabellen/Trigger.
Guard verweigert Originaltabellen-DML/Schemaänderungen und ATTACH/DETACH.
Initialisierung: ein Writer, 0,012160 s gemessene Transaktion, keine verbotenen
Versuche. Fortsetzbarer Aufbau in nummerierten Einzelaufrufen, feste Höchstzahl40;
tatsächlich bis28, davon Versuch6 nach Unterbrechung ohne vollständigen Receipt.
Dieser Versuch bleibt INTERRUPTED/Exit und Ressourcen unbekannt, kein PASS.

Während der Unterbrechung liefen reguläre Morgenjobs: Quellen stiegen um2.376
Belege, genau wie die Quellgeneration. Der gespeicherte Cursor520704 wurde ohne
Quellenlöschung oder künstliche Verkürzung fortgesetzt. Rewritegeneration blieb0.

Abschließender Aufruf28: **ready**, Cursor und Quell-Tail2.616.120,
18.232 weitere Zeilen, 5,966902 s Kern-/6,055428 s Wrapperzeit,
größte Transaktion dieses Aufrufs0,266630 s. Nicht abgeschlossene Deadlineaufrufe
melden überwiegend45,001 s Kern-/etwa45,1 s Wrapperzeit; dies wird nicht als
strikter ≤45,000-s-Rückkehrnachweis oder erfolgreicher Aufbauaufruf umgedeutet.
Die vorhandenen45-s-Arbeitsbudgets und55-s-Operatorwatchdogs wurden nicht erhöht.
Größte tatsächlich gemessene Writer-Spanne über die vollständigen Receipts:
0,463647 s einschließlich Lockgewinnung und Terminalabschluss. Versuch6 ist
darin ausdrücklich nicht gemessen; kein Nachweis über ausnahmslos alle Aufrufe.

Vollständiger Ready-Zustand vor dem nativen Test:

- logische Werte1.256.552 Bytes, Grenze64 MiB unverändert;
- `tennis_player_events`:348 Seiten/1.425.408 physische Seitenbytes;
- Kontrolltabelle:1 Seite/4.096 Bytes; zusammen1.429.504 Seitenbytes;
- tatsächliche Hauptdatei7.468.068.864 Bytes, kein WAL/SHM beim Messzeitpunkt;
- `user_version=0`, `application_id=0`, Pagegröße4096;
- Geräte-/Inodeidentität2049/809566 unverändert;
- Indexgeneration9748, Quellgeneration2376, beide geprüft, Rewrite0.

Tabellengrößen sind nicht die Gesamtgröße der bereits vorhandenen Datenbank.
Die zwischenzeitlichen regulären Quelldatenzuwächse sind kein Indexspeicher.
Keine Garantie über ungemessene Spitzen oder die unterbrochene Messung6.

## Echter unveränderter Vier-Fall-Test: FAIL

Code ausschließlich aus Git `c110d8e` unter
`/tmp/betboy-tennis-index.b09zLj`; keine Datenbankkopie.
Unverändertes Prüfskript SHA256
`58e031c070cda241575edd344505e4b08429fa3c873b0c9c288869a14fae0db1`.
Alle vier ursprünglichen ATP-/WTA-Ereignisse und ihre ursprünglichen Stichtage
blieben unverändert. Kein Austausch gegen kleinere oder erfolgreichere Fälle.

**Exit1, 0/4 abgeschlossene Fälle**, Fehler:
`native tennis batch selected byte/count budget exhausted`.
Ausgewählte Payload-Metadaten11.589.186 Bytes: mehr als2.097.152 je Fall und
8.388.608 insgesamt. Der protokollierte Wert `selected_count=512` ist die
konfigurierte Grenze, nicht die tatsächliche Zahl der ausgewählten Belege.
Diese Zahl ist im Fehlerreceipt nicht ausgewiesen. Keine erfundene Zählung.

Der Zulassungsschritt zählt/summiert Metadaten vor dem Öffnen dieser historischen
Belegkörper; er wurde korrekt abgebrochen. Ein schneller Fehler ist kein
erfolgreicher Merkmalslauf. Wrapper2,410309 s, CPU0,958659 s, RSS30.532 KiB;
CPU-Hardlimit50 s/Adressraum-Hardlimit2 GiB unverändert.
`labels_read=false`, `outcome_seen=false`, `provider_calls=0`,
`qualified=false`, `losses_evaluated=false`.

Der lokale Ergebnischecker verweigert Exit1 ebenfalls. Sein künftiger
Erfolgspfad ist durch diesen FAIL nicht nachgewiesen: Die generische spätere
Git-Schleife würde das absichtlich außerhalb Git liegende Prüfskript irrtümlich
als versionierten Quellowner behandeln. Diese Operatorgrenze wurde festgestellt,
nicht zur Erzeugung eines grünen Ergebnisses geändert. Unabhängig davon stimmen
alle28 versionierten Raw-Git-Quellhashes mit `c110d8e` überein; alle29 Importpfade
liegen im isolierten Codeverzeichnis, der externe Probe-Hash stimmt separat.
Der Checker selbst erreichte diese späteren Prüfungen bei Exit1 nicht.
Fehlerreceipt,
Exitreceipt, Gatefehler und isoliertes Codeverzeichnis bleiben erhalten;
kein neuer Sportlauf und kein wiederholter Versuch mit gelockerten Grenzen.

## Fehlersicherer Endzustand und Datenvergleich

Unmittelbar danach explizit `disable`: Exit0, ein Writer, 0,005177 s
Transaktion, keine Original-DML-/Attach-Versuche. Zustand jetzt `invalid`,
Rewrite1/verified0; Tabellen und Originalbelege bleiben erhalten.
Der schemafähige Code bleibt notwendig. Keine automatische Effektfreigabe.

Resume- und Nachhervergleich: unverändert6.114 Artefakte sowie jeweils2.616.120
Quellinhalte und Belege, gleicher Tail. Alle79 vorher erfassten Finanzdateien
mit5.791.744 Bytes unverändert. Nachher existiert zusätzlich eine77.824-Byte-
Sitzungsdatei; Gesamtinventar80 statt79, also **nicht** das ganze Inventar
byte-identisch. Keine bestehende Buchung wurde daraus als verändert abgeleitet.
Die genaue Ursache dieser zusätzlichen App-Sitzungsdatei wurde nicht gemessen.

Beim frühen Snapshot unmittelbar nach der Index-Abschaltung waren App/Caddy
aktiv, die sieben Jobs zuletzt Exit0 und Timer geplant, Backups inaktiv sowie
beide Healthchecks `ok`. Das ist ausdrücklich kein aktueller Gesamtlaufstatus:
Der später oben dokumentierte Shadow-Fehler bleibt offen. Kein manueller Zusatzscan.

## Offen / nächster fachlicher Schritt

Der Index beseitigt die globale Suchschleife, aber nicht den zu großen
vollständigen historischen Eingabesatz. Vor einer neuen Freigabe ist genau
dieser Belegumfang gegen den unveränderten Vollständigkeits-/Ressourcenvertrag
zu lösen. Nicht alte Revisionen wegwerfen, aktuelle Daten als historische
ausgeben oder die vier Fälle/Grenzen still ändern. Kein neuer Produktpatch
während der unabhängig laufenden Sortier-Vollprüfung.

Verletzungs-, Wetter- und Müdigkeitswirkung sowie bessere Wettqualität sind
dadurch weiterhin nicht nachgewiesen. Der neue Spielerindex ist dafür keine
Abkürzung und wird nicht als fertig/freigegeben gemeldet.

## Getroffene begrenzte Ausführungsentscheidungen und jeweilige Kosten

1. RED/GREEN und Nachbarprüfung je Aufgabe, eine vollständige Gesamtabnahme am
   Schluss statt einer 14.000er-Suite pro Kleinänderung. Kosten: Integrationsfehler
   werden unter Umständen erst am Schluss sichtbar; Teilprüfungen sind kein Vollpass.
2. Ungültige abgeleitete Zuordnung nur in begrenzten 512er-Chunks zurücksetzen;
   bis vollständigem Neuaufbau invalid. Kosten: zusätzliche Aufbauaufrufe und
   vorübergehend nicht verfügbarer Cache; Originaldaten bleiben erhalten.
3. Zusatzindex-Budget im Live-Append gilt für dessen eigene begin/observe/finish-
   Arbeit, nicht rückwirkend für die ursprüngliche Quellspeicherung. Kosten:
   bei Überschreitung Index invalid und später expliziter Neuaufbau; Quelle erhalten.
4. Physisch gültige, noch unbekannte ESPN-Tennisformate als Original erhalten,
   Index nicht freigeben; bekannte native Quellkorruption weiterhin zurückrollen.
   Kosten: Index bleibt bis zur Formatunterstützung unverfügbar, nicht falsch ready.
5. Minimale bestehende Reader-Identität vor Übergabe an den unveränderten
   Authorizer prüfen, der spätere PRAGMAs verweigert. Kosten: zusätzliche gemeinsame
   Reader-Regressionsprüfung vor Release; keine Lockerung von query-only/Vertrauen.
6. Quellenkörper der Mitgliedschaftsbelege erst nach der tatsächlichen Fall-
   Budgetzulassung lesen; vorher nur begrenzte Metadaten im selben Snapshot.
   Kosten: zusätzliche Abfrage und Tests, aber keine verkürzte Historie/weitere Grenze.
7. Eigene ignorierte SDD-/Fehlerbelege entgegen routinemäßiger Skill-Aufräumregel
   erhalten. Kosten: kleine zusätzliche Dokumentablage; spätere bewusste Archivierung.
8. QA02 auf nachgewiesene Prüfadapterfehler begrenzen: historische DATA/LF-Bytes,
   Factory-Adapter und echte negative Fälle, keine zweite Produktpatch-Welle.
   Kosten: zusätzliche begrenzte Prüfung und frische Vollsuite; historische FAILs bleiben.
9. Operator maximal40 einzeln protokollierte Aufbauversuche mit unveränderten
   45-s-Arbeitsbudgets/55-s-Watchdogs, Stopp bei Fehler/fehlendem Fortschritt.
   Kosten: bei zu wenig Durchsatz Index und Task6 offen statt verkürzter Quellen
   oder still angehobener Grenzen; tatsächlich28 Versuche, Versuch6 unvollständig.
