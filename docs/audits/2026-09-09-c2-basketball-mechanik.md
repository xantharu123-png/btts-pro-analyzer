# C2 Basketball: trainierte CPU-Vergleiche, keine reale Wirkungsfreigabe

Stand: 2026-09-09. Arbeitsbasis `0d000f6d8d85a4ada11521398ca1e4b82c88fd2d`,
isolierter Branch `codex/kontext-c2-basketball-20260909`.

## Ergebnis und harte Grenze

Implementiert ist die überprüfbare CPU-Kette aus ursprünglichem Ridge-Modell,
vollständig gebundenen nativen Besetzungsdaten, tatsächlich mit B2 trainierten
synthetischen Residuen und einer gemeinsamen Including-OT-Siegverteilung.
Ein kontextspezifischer Vergleich wird ohne D2-Freigabe von B3 ausschließlich
als `experimental` geführt; verwendet bleibt die vollständige Originalbasis.
Numerische Überläufe und unzureichende Merkmale erzeugen einen typisierten
unveränderten Basis-Fallback, keinen erfundenen Nulleffekt.

**Nicht geliefert:** ein realer ESPN-/Euroleague-Ausfall- oder Minutenadapter,
qualifizierte historische Basketball-Kontextfälle, eine empirische Verbesserung,
eine D1-Outcome-/Dataset-Anbindung, ein D2-Report, Laufzeit-/Scanneranbindung oder
eine produktive Aktivierung. Cricket, Hockey, Providerzugriffe, Geheimnisse,
Budgets, Server, 15K und privilegierte Deploymenthelfer blieben unverändert.

## Tatsächliche Quellenfähigkeit: null qualifizierte Spielerproben

Der einzige gespeicherte Basketball-HTTP-Befund im gelesenen Probe-Artefakt ist
der NBA-Scoreboard-Aufruf für **2026-01-01**, tatsächlich empfangen am
**2026-09-07T15:23:43.8010452Z**, mit **HTTP 403**. Darin sind **0 erfolgreiche
Basketballantworten, 0 native Spieler-/Minuten-/Ausfallkollektionen**. Die daneben
gespeicherten NHL-Antworten sind ausdrücklich keine Basketballnachweise. Dieser
Befund beweist keine dauerhafte globale Providerverweigerung; er belegt nur die
vorliegende Quelle und den dokumentierten Zeitpunkt. Keine neue Anfrage wurde
gestellt, kein anderer Endpunkt, Header, Tarif oder Schlüssel verwendet.

Quellprobe:
`.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/basketball-nhl-schedule-probe-20260907.json`
SHA-256 `2b5e7dc4edc73ddd985133faf4d7aef15f61649335545f91dd61e880f0d68df5`.

Der vorhandene RisikoBet-Pfad lädt anstehende Basketballspiele über den Scanner
und abgeschlossene Ergebnisse über `scanners/completed_history.py`. Aktuell
werden keine Spielerrotationen, individuellen Minuten, Ausfalllisten oder
Teilnahmewahrscheinlichkeiten in diesen Basketballpfad geladen; auch explizite
Saison-/Regelprovenienz fehlt dort. Eine vorhandene Endpunkt-/Score-Fixture ist
weder eine prospektive reale Spielerbeobachtung noch ein 200-Event-Testkorpus.
Der vorhandene Historienbudgetpfad (48/provider/day, Reservierung vor Abruf,
Fehler-Cooldown und Caches) wurde nur gelesen und nicht umgangen oder verändert.

Der begrenzte Preflight liegt unter `.pytest_tmp/c2-preflight-20260909/PREFLIGHT.md`,
SHA-256 `7f1f45a12b8adbb266d562cd95ad6068a01ea351242d70831befd51cc788cff3`.
Alle neuen Rohdaten in `test_basketball_context.py` sind ausdrücklich synthetisch.

## Produkt- und Modellvertrag

Einzige Familie: `basketball:margin:including_ot`. Parameter sind der **originale,
ungerundete** `expected_margin` und die positive Original-`residual_scale`.
Der einzige zusätzliche B2-Head ist `margin` mit Identity-Link. Es gibt genau
`home_win` und `away_win`, aus derselben Normalverteilung; keine Total-, Spread-
oder Regulation-only-Märkte und keine Änderung des bestehenden Settlements.
Die Normalverteilung ist eine Modellannahme, kein behauptetes exaktes Gesetz
diskreter Basketballergebnisse. Sie wird nicht auf Hockey oder Cricket übertragen.

Der B1-Trainingstransport akzeptiert ausschließlich für diese neue Familie einen
endlichen **signierten ganzzahligen** Punktabstand und `trials=None` (3.0 ist wie
bei bestehenden Count-Verträgen darstellbar, 3.5 nicht). B2 bleibt ein allgemeiner
numerischer Identity-Schätzer: seine künstlichen reellen Fit-Ziele sind keine
behaupteten Basketball-Endergebnisse. Ein tatsächlicher D1-Resultatresolver mit
Including-OT-Vertrag bleibt gesondert zu implementieren.

Explizite Formate: `nba_reg48_including_ot` und `euroleague_reg40_including_ot`.
Saison, vier Regulation-Perioden, gesamte Regulationdauer und tatsächliche
Verlängerungs-Periodendauer werden als Quellprovenienz verlangt. Die Dauer wird
nicht aus dem Anbieter- oder Turniernamen geschätzt. Der Effekt gilt exakt für
eine Competition, ein Format und einen Saison-/Regel-/Abdeckungsfall.

### Originalmodell und signierte Referenz

`sports_prematch.basketball_base_distribution(...)` ist ein ausschließlich
angehängter Export. Die alte Dataclass und der vollständige bisherige
Defaultcode bleiben bytegleich. Der Export verwendet den bestehenden Fit und
seine ursprünglichen Double-Parameter, nicht deren gerundete Anzeigetexte.

`basketball-margin-ridge-v1` bindet das vollständige Event, Saison/Regeln,
Heim-/Neutralorientierung, die komplette geordnete Team-/Spielmatrix, Ergebnisse,
Original-Ridge-Penalty (5 für Teamspalten, 1e-8 für Heimspalte), Fitkoeffizienten,
Residualskala und **signierte** Ziel-Einflüsse `q @ solve(X.T @ X + P, X.T)`.
Diese Gewichte sind kein konvexer Kaderdurchschnitt und werden nicht renormiert.
Der Validator spielt die ursprüngliche Rechnung samt Inventar erneut ab.
Vergleiche der Original-Replayparameter erfolgen exakt auf derselben CPU;
abweichende numerische Backends werden nicht durch aufgeweitete Toleranzen als
identischer Originalfit ausgegeben. Die B1-Markt-/Parameterkonsistenz benutzt
die bestehende absolute 1e-12-Transportgrenze; Null-Effekte bewahren selbst die
darin zulässigen Originalmarkt-Letztbits exakt.

Die numerische Originalquelle benutzt intern `casefold`. Der neue Export erhält
die tatsächlich gelieferten nativen IDs (z.B. `E2026_999` und `AAA`) und lässt die
interne Ridge-Zuordnung nur bei eindeutiger vollständiger Abbildung zu. Name-only,
fehlende IDs, unbekannte Saison/Regeln oder mehrdeutige Abbildungen erzeugen
keine behauptete native Kaderreferenz. Ist die ursprüngliche Prognose berechenbar,
bleiben ihre Parameter und Märkte mit `reference_weights.kind=unavailable` erhalten.

### Geschlossener interner Transport und Nullwertregel

`basketball-internal-context-v1` ist eine **interne CPU-Schnittstelle**, kein
verifizierter Provideradapter. Ein Record besitzt die vollständige gemeinsame
Event-/Teamrevision. Er enthält native Teilnehmer, Saison, Regeln, tatsächlichen
Empfang, Gültigkeit und die ganze `appearance`, `rotation` oder `availability`-
Kollektion. Keine partiellen Spielerprojektionen werden aus verschiedenen
Revisionen zusammengesteckt. Neuere leere, unvollständige oder widersprüchliche
Revisionen dürfen ältere Daten nicht wiederbeleben. B1-Inhalt und Receipt werden
zusätzlich zur vollständigen Quellprojektion geprüft; nur `usable_refs` tragen
numerische Merkmale. Identitätsdigests belegen Integrität, nicht Quellwahrheit.

Regulationrotationen benötigen echte individuelle Regulation-Minuten und einen
vollständigen konsistenten Mannschaftsumfang (Summe 5 × Regulationdauer).
Inklusive Minuten sind ein separates Feld mit tatsächlicher OT-Zahl und
Regeldauer zur Konsistenzprüfung. Fehlende Regulation-Minuten werden niemals
aus Totalminuten minus geratenen OT-Minuten abgeleitet. Ein Aktivkader oder
fünf Starter ersetzen keine vollständige Minutenrotation. `questionable` oder
unbekannte Teilnahme bekommt weder 0,5 noch einen pauschalen Prozentabschlag.

Die vom Controller präzisierte Regel bleibt entscheidend: In einer belegten
vollständigen **gemessenen** historischen Rotation bedeutet ein nicht enthaltener
Spieler gemessene Exposition 0 in genau diesem Team/Event. In einer vollständigen
**erwarteten** Rotation bedeutet die gleiche rechnerische 0 nur erwartete
Exposition innerhalb genau dieses Szenarios. Sie beweist keine tatsächliche
Nichtteilnahme, Gesundheit oder Verletzung. Erwartete und bestätigte Projektionen
haben unterschiedliche Abdeckungsidentitäten. Fehlende Zellen/unvollständige
Kollektionen bleiben unbekannt. Eine langfristig ausdrücklich gemessene und
aktuell erwartete Null-Exposition erzeugt keinen zweiten Ausfallabzug.

### Merkmale, Last und Zeit

Featureversion `basketball-rotation-observed-load-v1`, Modellvariante
`basketball-signed-ridge-rotation-margin-v1`. Native Spielerspalten stellen den
aktuellen signierten Regulationanteil dem signierten ursprünglichen
Ridge-Referenzanteil gegenüber. Jede benötigte Referenzkollektion muss vorhanden
und vollständig sein. V1 konsumiert keine noch nicht implementierten gelernten
Teilnahme-/Preprocessingartefakte und keine unvollständige zentrale Projektion.

Beobachtete inklusive Mannschaftsminuten in 1/3/7-Tagesfenstern sind ausdrücklich
**nur die beobachtete Teilmenge**, keine vollständig gesammelte Karriere oder
Spielplanung. Fenster sind `[cutoff - N*24h, cutoff)` UTC anhand tatsächlichen
Spielendes. Spielplanzeit ist keine Actual-End-Zeit. Ein unbekanntes Ende darf
nur bei `result_observed_at < window_start` ausgeschlossen werden, nicht bei
Gleichheit. Exakte beobachtete Erholung ist nur zulässig, wenn das neueste
bekannte Ende sämtliche unbekannten End-Obergrenzen dominiert; sonst bleibt
nur eine klar getrennte Empfangs-Untergrenze. Ausschlussbelege sind in den
tatsächlich verwendeten Referenzen enthalten. Vollständigkeit der beobachteten
Minuten wird separat geprüft; `history_complete` behauptet niemals Vollabdeckung.
`medical_fatigue` und `travel_hours` bleiben unbekannt. Keine medizinische
Müdigkeitsdiagnose, Reiseinferenz oder fixe Back-to-back-Strafe wird erfunden.

Referenzidentität `basketball-context-reference-v1`: vollständige validierte
Originalbasis + vollständiges validiertes Event + sortierte exakte
Preprocessingreferenzen (V1: leer). Terminänderung, neue Revision, Teilnehmer,
Format, Saison/Regeln oder Basisparameter benötigen neu gebaute Merkmale.
Quoten und UI-Tab beeinflussen weder Originalmodell noch Merkmale.

## Eng genehmigte B3-Erweiterung

Ein frei gesetztes Comparison-Label darf die Originalparameterprüfung nicht
umgehen. Deshalb besitzt `basketball-context-comparison-v1` einen geschlossenen
`basketball-margin-comparison-reference-v1`-Beleg mit kompletter Originalbasis,
Event, Featurevektor und Effekt. Der owning Validator rechnet daraus Parameter,
Märkte und Modelldigest erneut. Ein anderes Label, eine veränderte Skala, ein
verschachtelter Vergleich oder manipulierte Original-/Feature-/Effektbytes werden
abgewiesen; die Original-Ridge-Referenz bleibt vollständig im Envelope erhalten.

Der Controller gab daraufhin genau den notwendigen zusätzlichen B3-Zweig frei:
`select_context_result` verlangt für diese Familie die verschachtelte Originalbasis,
Event und Features **bytegleich** zur tatsächlichen Übergabe; der Effekt muss
bytegleich zum tatsächlich A1/B3-verifizierten Effekt samt Digest sein. Eine intern
gültige fremde Comparison reicht nicht. Alle bisherigen Football-/Tennis-
Referenzgleichheiten, Rollen, Approvalregeln, Snapshots und Geldregeln bleiben
unverändert. Ohne Approval: `experimental`, `used=base`. Kein Laufzeitloader wurde
angeschlossen; Quellen-/Training-/D2-Vertrauen entsteht nicht durch dieses Envelope.

## TDD und Regression

- Vor Produktänderung: 5 eingefrorene echte Legacy-CPU-Cricketläufe, darunter T20,
  ODI, frisch importierte Historie, leere Historie und ununterstütztes Testformat.
  Der permanente Vergleich führt die unveränderte Altdatei und Neuimplementation
  auf derselben CPU aus und vergleicht kanonische Ergebnisbytes exakt.
- Erste Basisschnittstelle: `c2-initial-red-01`, **14 rot / 1 grün**; danach
  `c2-base-green-02`, **132 grün** inklusive B1-Verträgen.
- Interner Transport: `c2-source-red-01`, **31 rot / 15 grün**; danach
  `c2-source-green-01`, **46 grün**.
- Merkmale: `c2-features-red-01`, **19 rot / 46 grün**; nach numerischem Pfad
  `c2-effects-green-02`, **182 grün** inklusive B1.
- Gemeinsames B3-Resultat: `c2-b3-red-01`, **2 rot / 6 grün**; positiver
  Vergleich und Nullvergleich wurden am alten Referenzvertrag korrekt abgewiesen.
  Nach der genehmigten Erweiterung: `c2-b3-green-01`, **445 grün** inklusive
  unveränderter B1/B3-Tests.
- Euroleague/native Großschreibung und echter Overflow-Fallback: zunächst
  **2 rot**, danach `c2-euro-fallback-green-02`, **2 grün**.
- Weitere Typ-/Spiegelproben: zunächst **3 rot / 15 grün**, danach
  `c2-shapes-mirror-green-01`, **18 grün**. Ein Test wurde präzisiert: fehlen nur
  historischen Teams die IDs, kennt die Originalbasis die Zielteams nicht;
  name-only Referenz-Unavailability wird bei tatsächlich berechenbarer
  name-only Originalbasis geprüft, nicht durch Erfinden einer Basis.
- Fokus `c2-final-focus-01`: **1.307 bestanden**, 35,55 s. Enthält alle **166 C2-
  Fälle**, unveränderte Prematch-/Completed-History-, B1/B2/B3-, Football-,
  Tennis- und C1-Wettertests.
- Vollsuite `c2-final-full-01`: **3.739 bestanden, 15 übersprungen, 97 Untertests
  bestanden**, 96,23 s. Windows-Plattformgrenzen sind kein Linux-/VPS-Nachweis.
- Separater Skip-Nachweis `c2-skip-audit-01`: **132 bestanden / 15 Skips**, 9,90 s.
  Genau ein POSIX-Umasktest, drei POSIX-Rechtetests und elf ohne Windows-Symlink-
  Privileg nicht ausführbare Fälle; kein C2-Test wurde übersprungen.

Zusätzlich permanent geprüft: echte B1-SQLite-Schreib-/Lese-/Cutoff-Replays;
native Teilnehmer-/Kaderkorrekturen, gleichzeitige Konflikte und Deduplikation;
späte Importe, fehlende Minuten/Regeln/Saison; explizite langfristige Abwesenheit;
strenge Fenstergrenzen beider Seiten; manipulierter Ridge-Fit/Zeileninventar;
Modell-/Feature-/Effekt-/Markt-/Skalen-Manipulation; Intern-valid-aber-fremde B3-
Vergleiche; neutrale Seitenäquivarianz; kein Quoteninput oder Cricket-Drift.

## Eingefrorene Originalbytes und Source-Hashes

Unveränderte Legacy-Fixture `tests/fixtures/context/basketball/sports_prematch_legacy_0d000f6.py`:
Git-Blob `be3d56fc574e62f78d52eeabedd6fba59143bd00`, SHA-256
`b4e44d03d09a6c8f22ce52568ea36f9af1c7e563d094af98c135703a0a204677`.
Die vor Bearbeitung erfassten fünf Cricket-Eingabe-/Ergebnisobjekte hatten SHA-256
`1446a372d561f2f9926620a6d90e1a9fb721a5159d52465253f2d2968ba28709`.
Der Beweis ist der permanente exakte Alt-/Neu-Lauf, nicht allein diese alte Hashzahl.

Unverändert:

- `scanners/basketball_scanner.py`: `05371eff84e0d0f91824ca08a5134e4a0b241c6f6e2d30f037f4335eb6de3064`
- `scanners/completed_history.py`: `9f318672c0a18054d8fb9cae95ecbd6402a49ca0f17699eef8bb6a93beb1e264`
- `context_models/offset.py`: `027939cc5f7c05648177bfc94605bdc5f0fabac10e215d346a6e9ba1b37ec7a7`

Finale Source-SHAs des vollständigen Gegenlaufs:

- `context_models/contracts.py`: `763b105a712418c8963b6f620ecea75eb8b42fec54b3775f9587c6e235737b9d`
- `context_models/team_sports.py`: `410fddf37b42f61e1d1cf6044df1e0636a912701be8193c4666a2ea075870605`
- `context_sources/basketball.py`: `da6dd98b15a8cbb55f508b6c7980c22acc4cd2055ec0a3e06b76028822b6b12b`
- `context_snapshots.py`: `6caa81aa7ac7f188cfef689b688cc0deb452515b8ba8f7fad2f8e5b2f27d6dac`
- `sports_prematch.py`: `fc1253fbeb0888870715c21238d4da78de2c0cbe19fee910da67ebfd35b756d7`
- `tests/test_basketball_context.py`: `0e52913cd9b3e57a080a646b34a2d5f1ba20855fb307bb76ad038440ff3a43e4`

Alle Test- und Implementierungsdateien waren beim obigen Vollgegenlauf bereits
auf diesen Bytes. Danach wurde nur dieser Auditbericht vervollständigt.

## Offen, nicht durch grüne Tests erledigt

1. Vertrauenswürdig tatsächlich angebundene native Basketball-Minuten-,
   Saison-/Regel-, Verfügbarkeits- und Besetzungsquelle. Das gespeicherte 403
   wird nicht umgangen; eine neue Quellen-/Tarifentscheidung bleibt gesondert.
2. Reale prospektive Zeitabdeckung, gelernten Teilnahme-/Minutenmix für unsichere
   Spieler und ausreichend complete gemessene Referenzrotationen sammeln.
3. C2-D1-Outcome- und Dataset-/Trainingrow-Assembler, zeitlich saubere tatsächliche
   Trainingskohorten und frei von Quote/Echtgeld gespeicherte Artefakte.
4. D2: mindestens 200 eindeutige Events, mindestens drei aufeinanderfolgende
   Blöcke, Brier/Logloss/Kalibrierung plus gemeinsame FDR-Prüfung. Die 84 künstlichen
   Referenzspiele und 60 künstlichen B2-Fitzeilen erfüllen davon **keinen** Nachweis.
5. D3-Provider-/Worker-/Snapshot-Laufzeitanbindung nach unabhängiger Prüfung, dann
   separate Aktivierungs-/VPS-/Betriebsnachweise. Kein Push oder Deployment durch
   diesen C2-Auftrag; Root organisiert unabhängiges Review und Integration.
