# Auswahlgrundlagen und abgebrochener Nachtlauf – 11.10.2026

## Auftrag und verifizierter Ausgang

Nahtlose Fortsetzung nach Accountwechsel. Keine künstliche Regel zum Zählen
von zwei oder drei Argumenten: Strategie, Datengrundlage und gemeinsame
mathematische Berechnung müssen tragen. Torerwartung, Tordifferenz und daraus
abgeleitete Siegchance sind nicht drei unabhängige Bestätigungen.

Ausgang lokal, GitHub/main und VPS:
`02943e9cd69f5b421b68070bbc7343eed52cdc28`. Repository und Arbeitskopie
abgeglichen; geerbte ungetrackte Dateien erhalten. Keine weiteren Backups,
Bereinigungen oder zusätzlichen Sport-/API-Scans.

## Echter Produktionsstatus vor dieser Reparatur

- Wettfinder 11.10.03:35:22–04:20:22 CEST: `Result=timeout`, TERM/Status 15,
  45-Minuten-Limit; 40:35 CPU-Zeit. Die App war erreichbar, der Tageslauf
  aber nicht vollständig veröffentlicht. Kein behaupteter erfolgreicher Lauf.
- `wettfinder_latest.json` weiterhin aus dem 10.10.; RisikoBet wurde am
  11.10.04:16:44 CEST bereits gespeichert. Zeitpunktfolge allein beweist
  nicht, in welcher der späteren Phasen der Worker endgültig festhing.
- Echter Tennisjob 11.10.00:05:31–00:32:29 CEST: Exit 0, 82/82 verarbeitet,
  74 neue Prognosen. Zehn ungelöste Ergebnisereignisse bleiben separat offen.
- Nur-Lese-Roundtrip über beide RisikoBet-Lader: 129 Snapshots, 43
  Kontextreferenzen und zwei neue strukturierte Formanhänge; IDs, Inhalte
  und Eingabedaten unverändert. Die Formtransport-Korrektur ist somit auch
  auf neuen echten Produktionsdaten nachgewiesen, nicht nur auf UI-Fixtures.
- App/Caddy und sieben reguläre Timer aktiv; beide Healthchecks `ok`.
  Backup-Timer weiter abgeschaltet. Vor Veröffentlichung 21 GB verfügbar.

## Begrenzte Betriebsreparatur

Die echte SQL-Abfrage der Ergebniswarteschlange musste für jede Prognose die
Ergebnistabelle erneut durchsuchen. Ein nicht eindeutiger, idempotenter Index
auf `(event_key, market_key, selection, observed_at)` ersetzt diesen inneren
Vollscan. Keine neue Tabelle, kein Löschen, keine Änderung von Ergebnisdaten,
Auswahlkriterien, Abrechnung oder Zeitgrenzen. Alte Datenbanken erhalten
den Index durch den normalen Initialisierer; der Leser bleibt read-only.
Beim begrenzten Deployment wird dieser Initialisierer ausdrücklich auf der
vorhandenen Prognose-DB ausgeführt, während App und Worker inaktiv sind.
Alle vier Tabellen-Zeilenzahlen und acht unveränderlichen Trigger müssen
identisch bleiben; Indexspalten und Nicht-Eindeutigkeit werden geprüft.

Zudem beginnen/enden ausgewählte Workerphasen mit internen stderr-Zeitmarken:
Fußballscan/-kontext, Tennisrefresh, RisikoBet-Quellen/-Ergebnisse/-Modelle,
Teamsportpreise, E-Sport-Ergebnisse, Prognosespeicherung/-Ergebnisse,
Spielereinsatzhistorie, Veröffentlichung und Tippbelege. Keine Argumente,
Tokens, Anbietertexte oder Prognosepayloads im neuen Diagnoselog. Rückgabe,
Ausnahme und Veröffentlichung bleiben gleich, selbst wenn das Log fehlschlägt.
„completed“ bedeutet Rückkehr der Funktion, nicht automatisch fachlich OK.
Nicht jede denkbare Lade-/Preisphase ist separat instrumentiert.

Der Vollscan der Fußball-Einsatzhistorie bleibt ein weiterer begründeter
Performanceverdacht. Er liest und prüft sämtliche passenden gespeicherten
Basisbelege, bevor maximal 20 IDs ausgewählt werden. Keine ungeprüfte
Umgehung der Quellenprüfung und keine Erhöhung des 45-Minuten-Limits.

### Betriebs-QA

- Zwei neue Indexregressionen zunächst rot, danach betroffene Module:
  84 Tests grün, auch ohne externes Netzwerk. Echte Queue-SQL per Trace/
  EXPLAIN geprüft; frische/alte Datenbank, unveränderte Payloadbytes und
  Identitäten, kausale Schnitte, Zukunftsbelege und erneute Initialisierung.
- Zeitdiagnostik: zunächst sechs echte rote Fälle, nach Review neun grün.
  Ein isolierter Produktionspfad beweist identische Dokumente, gespeichertes
  JSON und Aufrufreihenfolge mit/ohne Diagnostik. Alle Datenbanken privat,
  alle Anbieter-/Abrechnungsfunktionen ersetzt; keine Produktionsabfragen.
- Gesamte direkt betroffene Runde: 199 bestanden, 19,58 Sekunden.
- Breitere identische 526-Fälle-Runde: zunächst 57 Windows-Umgebungsfehler,
  463 bestanden, sechs Skips. 3 nicht ausführbare Windows-Bash-Aliasse und
  54 Temp-/Berechtigungsfehler, keine Modellbehauptung aus diesem Fehl-Lauf.
- Mit installiertem Git-Bash und privatem TEMP/TMP dieselben 526 Fälle:
  **519 bestanden, sieben bestehende Windows-Symlink-Skips, 24,48 Sekunden**.
  Keine Fälle entfernt und keine Checks gelockert. Zwei zuvor gescheiterte
  Fälle erreichen nun vorhandene Plattform-Skips; ein vorheriger Skip ist grün.
- Unabhängiger Review: keine verbleibenden blockierenden Befunde. Kein
  neuer einteiliger Vollsuite-PASS und kein Linux-Symlink-PASS behauptet.

Belege: `C:/Projekt/BetBoy/output/winner-audit-20261011/` und
`C:/Projekt/BetBoy/output/team-form-20261010/index-offline.xml`.

## Fachliche Ursache und mathematischer Arbeitsschritt

### Tatsächliche aktive Modelle

- Eishockey berücksichtigt bereits Angriff, gegnerische Defensive und
  Spielort in einem gemeinsamen Poisson-Fit. Der bisherige Kurztext zeigt
  diese Modellgrundlage unzureichend. Aktuelle Formkacheln sind bislang
  Darstellung tatsächlich verbrauchter Ergebnisse, kein weiterer numerisch
  qualifizierter Bonus. Viele geschossene Tore allein belegen keine Überlegenheit.
- Fußball verbindet Spielort- und Formdurchschnitte, berücksichtigt dabei
  aber nicht systematisch die Stärke der historischen Gegner. Der vorhandene
  „joint“-Kontextpfad ist keine versteckte Lösung dafür; er projiziert die
  bisherige Torverteilung beziehungsweise experimentelle Kontextfaktoren.
- Tabellenplatz darf weder erfunden noch als pauschaler Wahrscheinlichkeitssatz
  auf die Torberechnung aufgeschlagen werden. Gegnerqualität muss aus genau
  den verbundenen Spiel-/Quellendaten geschätzt werden.

### Neuer, ausdrücklich isolierter Vergleich

`football_opponent_strength.py` schätzt Angriff, gegnerische Defensive,
Ligabasis und Heimfaktor gemeinsam aus bereits geladenen regulär beendeten
API-Football-Spielen. Eine gemeinsame normalisierte 90-Minuten-Torverteilung
liefert Heimsieg, Remis, Auswärtssieg und abgeleitete Tormärkte konsistent.
Gleiche Rohresultate gegen unterschiedliche Gegner müssen unterschiedliche
Stärke ergeben. Kein Quotenbonus und keine Abstimmung dreier korrelierter Zahlen.

Optionaler Formvergleich nutzt ausschließlich Fits aus jeweils vorherigen,
rechtzeitig beobachteten Spielen; kein Training auf dem Spiel, das als
Formleistung bewertet wird. Das ist ein beschreibender Modellcheck, keine
zusätzliche unabhängige statistische Bestätigung.

Der Baustein ist **nur offline**, mit eigener Versionskennung und
`empirically_qualified=False`. Er ersetzt keine aktive Prognose und verändert
keine bestehende Siegerempfehlung. Bestehende Rezepte, alte Prognose-IDs,
Kalibrierungen, Kontextbelege, Tickets und Geldbuchungen bleiben unverändert.
Historie höchstens 730 Tage, maximal 1.200 Eingabezeilen/64 Teams; keine
vier Jahre alten Ergebnisdaten und keine stillen unbegrenzten Iteratoren.
Die Grenzen/Regularisierung stammen aus vorhandener numerischer Mechanik,
nicht aus einer angeblich optimalen Fußball-Abstimmung. Native positive
API-IDs und explizites FT; CSV-Pseudo-IDs werden nicht in native Belege umgedeutet.

Ein direktes Ersetzen der Torwerte unter dem alten `football-goals-v1`-Rezept
wäre eine falsche Herkunftsbehauptung: Dieses Rezept bindet tatsächlich die
75/25- und 50/50-Gewichte. Eine spätere aktive Integration benötigt einen
eigenen passenden Modellvertrag sowie konsistente Markt- und Replaypfade.

### Vorhandene echte Daten, keine neue Abfrage

Zwei unverändert geladene ORIGINAL-Belege: Liga 274 mit 340, Liga 333 mit
298 Spielen, ab August 2025. Nur Spielkennungen, Zeitpunkte, Ergebnisse,
gegebenenfalls vorhandene xG-Felder exportiert; zusammen 158 KB, keine
Datenbankkopie, keine Secrets. Tatsächlicher Empfang der Belege am
11.10.01:46–01:47 UTC; der alte `logical_history_cutoff` bezeichnet den
Anpfiff, nicht diesen Empfangszeitpunkt.

Der begrenzte Vergleich verwendet identische frühere Spiele je historischem
Ziel für beide rohen Torformeln. Brier und Logloss statt bloßer Trefferzählung.
Er ist eine retrospektive Ereigniszeit-Rekonstruktion: Historische individuelle
Empfangszeiten fehlen. Deshalb keine prospektive Validierung, keine neue
Produktfreigabe, kein Renditebeweis und kein Überschreiben gespeicherter Tipps.

49 Offline-Regressionen bestanden, darunter schwierige/leichte Gegner trotz
gleicher Rohresultate, echte kausale Formfits, fehlende Empfängerzeiten,
gemeinsame konsistente Tormärkte, Nichtkonvergenz/kein stilles Clipping,
fremde Ligen/alte Spiele, doppelte oder widersprüchliche Daten, strikte Typen,
unbegrenzte Iteratoren sowie spätere Ergebnis-/xG-Revisionen ohne Rückwirkung
auf die frühere Vergleichsreihe. Der unabhängige numerische Review fand noch
die gültige Nullwahrscheinlichkeitskante: Legacy 0:0-Erwartung, tatsächlicher
Heimsieg. Das Paar bleibt in der Auswertung; dessen Logloss ist korrekt
unendlich, nicht ein Absturz oder ein nach Ergebnis ausgewählter Ausschluss.
JSON-Berichte benennen unendliche Werte ausdrücklich, kein ungültiges Infinity.

Unveränderte Parameter, letzte 50 Zielspiele je Liga; ausgeschlossene Fälle
werden gezählt und nicht durch andere Spiele künstlich ersetzt:

| Liga | Paarvergleich / versucht | Brier alt → neu | Logloss alt → neu |
| --- | --- | --- | --- |
| 274 | 39 / 50 | 0,587679 → 0,552184 | 0,989995 → 0,935560 |
| 333 | 33 / 50 | 0,581298 → 0,514875 | 0,979909 → 0,887735 |

Kleinere Scores sind hier besser. Alle 28 Ausschlüsse: weniger als acht
verfügbare vorherige Spiele mindestens einer Zielmannschaft. 72 tatsächlich
gepaarte Spiele insgesamt, null individuell zeitgestempelte Ergebnisbelege.
Das ist ein günstiger erster Vergleich dieser zwei Rohformeln, **keine
abgenommene Verbesserung der produktiven Auswahl oder Wett-Rendite**.
Keine gespeicherte spätere Kalibrierung benutzt; kein Abstimmen auf diese
Zielresultate. Weitere Ligen, Wahrscheinlichkeitskalibrierung, Unabhängigkeit
des Testbestands und Betriebsbudget vor aktivem Wechsel weiterhin offen.
Ergebnis: `output/winner-audit-20261011/retrospective-opponent-strength-summary.json`
außerhalb des Repositories.

Mathematische Referenzen: Angriff/Defensive-Modelle sind eine gemeinsame
Modellfamilie, nicht mehrere unabhängige Gründe. [Dixon/Coles, Originalarbeit](https://www.research.lancs.ac.uk/portal/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-football-betting-market%28d16276a2-d6e0-483b-a708-1d29663f1992%29.html).
Wahrscheinlichkeiten werden mit geeigneten Scores geprüft, nicht nur nach
dem Sieger des höchsten Prozentwerts. [Gneiting/Raftery](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).

## Offene echte Abnahmen

### Tatsächliche Veröffentlichung

Codecommit `be1ecb389c974435ce53f8eaf2fecf0add5fd4b1` auf main gepusht,
VPS per geschlossenem Whitelist-Fast-forward übernommen. App und Worker
während der expliziten Indexinitialisierung inaktiv; vorhandene forecast-only
Datenbank, exakt vier Tabellen und acht Immutabilitätstrigger vor/nach geprüft.
Unveränderte Zeilenzahlen: 816 Läufe, 86.300 Prognosen, 52.441 Quotenbelege,
4.628 Ergebnisse. Nicht eindeutiger, nicht partieller Index mit exakt den
vier geprüften Spalten vorhanden.

App/Caddy und sieben reguläre Timer aktiv, Backup weiter deaktiviert;
interner/öffentlicher Healthcheck `ok`. Veröffentlichte Prognosedateien bytegleich:

- Wettfinder `a51c9d865ab14db2d7d17971e469cbb029045a7107dd7417f2ff9da17af4298e`
- RisikoBet `acf24df6d14786a744b8fdf30a690bada1b34f84d54e32eb1e3915cdc3350ede`

Der Helfer meldete **nach** abgeschlossenen Änderungen/Healthprüfungen noch
Exit 127: PowerShell ergänzte hinter der abschließenden LF-Leerzeile ein CR,
das Bash als einzelnen Befehl behandelte. Kein Rollback oder wiederholter Scan.
Separater unverändernder Nachcheck bestätigte Commit, Index, alle Zeilenzahlen,
Triggerzahl, Artefakthashes und Gesundheit. Diesen Ablauf nicht als vollständig
fehlerfreien Helferlauf darstellen. Künftig den Transporttext vor stdin mit
`.TrimEnd([char[]]"`r`n")` abschließen. Beleg außerhalb Git:
`C:/Projekt/BetBoy/output/winner-audit-20261011/release-verification.txt`.

Finale kombinierte Offline-Runde: 248 bestanden, 9,50 Sekunden; mathematischer
und kausaler Zweitreview abgeschlossen. Keine offenen Blocker für den
ausdrücklich isolierten Vergleich, keine aktive Qualitätsabnahme.

### Noch offen

1. Nächsten **regulären** Wettfinderlauf am 12.10.03:35 CEST nach Index und
   Zeitmarken prüfen. Heute kein neuer API-/Sportscan; vollständige Reparatur
   des Timeout erst bei tatsächlichem Abschluss bestätigen.
2. Positiven ersten Offline-Gegnervergleich breiter und auf getrennt
   abgestimmten Daten prüfen. Kein Aktivieren allein wegen 72 guten Fällen.
3. Fußball-Gegnergewichtung als eigenständigen, nachvollziehbaren aktiven
   Modellvertrag integrieren und getrennt abgestimmte/historisch unbenutzte
   Spiele vergleichen; keine alte Provenienz nachträglich umetikettieren.
4. Verletzungs-/Müdigkeits-/Wetterwirkung, Tennis-Ergebnislücken, alte
   RisikoBet-Abrechnungsmehrdeutigkeit, Sortierung und weitere Eishockeyligen
   bleiben getrennte offene Arbeiten. Nicht als durch diese Reparatur erledigt melden.
