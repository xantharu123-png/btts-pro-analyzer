# B7 – numerischer Tennis-Kontextvergleich

Stand: 9. September 2026. Basis `dd6fd38985e96e615450990c9a953d9af233580c`.
Isolierter Branch `codex/kontext-b7-tenniseffekt-20260909`.

**Anschlusskorrektur:** Nach dem ersten unten vollständig dokumentierten Freeze
hat der Controller eine strengere komplette Event-/Basisbindung beschlossen.
Der aktuelle Vertrag ist **Feature v2**, siehe den abschließenden Abschnitt
„Referenzkorrektur v2“. Die v1-Hashes/-Tests bleiben historische Nachweise.

## Status und verbleibende Aufgaben

Implementiert ist der **begrenzte numerische B7-Teil**, nicht die vollständige
Tennis-Kontextintegration. Echte B2-Optimierungen künstlicher Daten belegen hier
Rechenmechanik; sie belegen **keinen realen Müdigkeits-/Verletzungseffekt**.

- Neuer eigener Adapter: `context_models/tennis_effect.py`.
- Bestehende B6-Quell-/Featureberechnung unverändert bis auf die ausdrücklich
  genehmigte Erkennung zweier präziser Einzel-/Best-of-Eventformate.
- Kein Aufruf von Live-Quellen, kein lokaler produktiver Cache, keine aktuellen
  Spiele aus alten Quellenbeispielen konstruiert. B6-Quelle bleibt unverändert.
- Kein Produktivtraining, keine neue Modellaktivierung, kein UI-/Job-/15K- oder
  Cricket-Pfad geändert. Kein Push oder VPS-Schritt durch diesen Teilauftrag.
- Offen: reale zeitkorrekte Trainingszeilen und deren native Identität,
  tatsächliche Aufschlag-Erfolge/-Versuche samt Basisherkunft, train-only D1,
  unabhängige D2-Abnahme, Baseline-/Forecast-/Snapshot-Betriebsanbindung, öffentlicher
  Reexport und gerenderte Nutzerprojektion. Die gespeicherten künstlichen Fits
  ersetzen keinen dieser Nachweise.
- Insbesondere keine 200 realen unangetasteten Testevents, drei Zeitblöcke,
  2-%-Brierverbesserung, HAC/BH-FDR-Abnahme oder Verteilungs-Logloss-Abnahme erzielt.
  Quoten und vermeintliche Gewinne sind weder Trainingsinput noch Freigabegrund.

## Vorab abgestimmte Schnittstellenentscheidungen

Root las den vollständigen B7-Vertrag und den vorhandenen Simulator und gab
folgende enge Ergänzungen ausdrücklich frei:

1. `simulate_match(..., *, strict=True)` prüft echte endliche JSON-Zahlen im
   offenen Hold-Intervall und echtes Integer-Best-of 3/5. Dieser Opt-in-Pfad
   begrenzt und rundet Holds nicht. Ungültige Masse wird nicht normalisiert oder
   abgeschnitten. Legacydefault einschließlich bisheriger Resultate bleibt gleich.
2. Der tatsächliche alte Simulator verwendet **nicht** seine vorhandene Funktion
   `hold_to_point_prob`. Er nutzt einen Hold-basierten Punktproxy im Sieben-Punkte-
   Tiebreak und unabhängige Sätze mit gemittelter Erstaufschlagseite. Diese
   Näherungen bleiben ausdrücklich erhalten; B7 baut keine zweite Punktinversion
   und behauptet keine exakte Abbildung jeder tatsächlichen Tennisregel.
3. Serve benötigt `Event.format = singles_best_of_3` beziehungsweise
   `singles_best_of_5`, jeweils exakt passend zu `base.params.best_of`. Keine
   `best_of_3/5`-Aliase, Doppelmatches, Matchtiebreak-/No-Ad-Annahme oder geratenes
   Format. B6 akzeptiert diese beiden Codes zusätzlich zu `singles` allein zur
   bisherigen Lastberechnung. Historische Source-Beobachtungen bleiben `singles`.
4. Winner-only darf `singles` ausschließlich als exakt so deklarierte
   unbekannte-Formatpopulation vergleichen. Daraus entstehen keine Serve-/Satz-
   oder Game-Märkte. Auch bekannte Formate müssen in der Artefaktpopulation stehen.
5. Serve-Heads sind strukturell gespiegelt: gleiche geteilte Fitgröße und Alpha,
   gespiegelte Scales/Koeffizienten bei A/B-Merkmalen, negierte Koeffizienten bei
   Differenzen. D1 muss diese gemeinsame Parameterbindung einhalten; beliebige
   separat geschätzte Fits werden nicht durch nachträgliches Mitteln repariert.
6. Konsumierte Lastdimensionen benötigen die zugehörigen B6-Indikatoren
   `observed_<metric>_complete_<N>d_<side> = 1` mit vorhandener Provenienz. Dies
   bedeutet nur vollständige Messwerte innerhalb der **beobachteten Teilmenge**,
   niemals vollständige Spielerhistorie. Fehlende Minuten eines weiteren
   bekannten Matches werden nicht als null Minuten behandelt.

## Versionen, Rechen- und Identitätsvertrag

- Winner: `tennis-winner-performed-load-antisymmetric-v1`.
- Serve: `tennis-serve-performed-load-mirrored-iidsets-holdproxy-tb7-strict-v1`.
- Zugehörige ursprüngliche Serve-Basis:
  `tennis-serve-iidsets-holdproxy-tb7-strict-v1`.
- Comparisons: `tennis-context-comparison-v1`; diese sind als neue Basis
  ausdrücklich unzulässig. Ein B3-ContextResult ist ebenfalls keine Basis.
- Features: B6 `tennis-performed-load-v1`, geschlossener beobachteter
  Sätze-/Games-/Minuten-/Erholungswortschatz und passende Coverageversion/-fälle.
  Winner konsumiert ausschließlich belegte A-minus-B-Differenzen. Noch fehlende
  Verfügbarkeit, Reise, Rückkehr, reine Belag-/Hallenflags und eine aus Aufgabe
  vermutete Verletzung werden nicht als neue numerische Faktoren eingeschleust.
- ATP/WTA, Belag und Hallenabdeckung bleiben in dieser ersten Variante getrennt.
  Wettbewerbe und Formate müssen explizit zur eingefrorenen Population gehören.
  Feature-/Basiscutoff, nativer Eventschlüssel und historischer Referenzhash stimmen
  exakt überein. Später trainierte Artefakte verändern keine frühere Entscheidung.
- `apply_tennis_effect` benutzt ausschließlich originale Parameter und gespeicherte
  B2-Scales/Koeffizienten. Es gibt kein Live-Fitting, keinen Intercept oder
  pauschalen Fünfsatzabschlag. Gelerntes Nullmodell/Nullmerkmal erhält die originalen
  Sportparameter und Marktwerte exakt.
- Winner enthält exakt `winner_a/b`. Serve leitet Winner, Satzanzahl, Satz-Score,
  halbe Satz-/Game-Linien, deklarierte Gamehandicaps und Tiebreak aus einer gemeinsamen
  Simulatorverteilung ab. Vorhandene Basis-Marktteilmengen werden exakt beibehalten;
  keine zusätzlich erfundenen Karten oder Marktverbote. Unbekannte Kataloge,
  gerundete Basiswerte oder ein fremder Elo-/Platt-Winner in einer behaupteten
  kohärenten Serve-Basis sind für diesen Effekt nicht verwendbar.
- `effect_hash = SHA256(canonical({kind:'context-effect-v1', payload}))`, nicht nur
  der Payloadhash. `base_hash` bindet die vollständige normalisierte Basis. Die
  Vergleichsidentität bindet zusätzlich komplettes Event, Featurehash und ggf.
  expliziten Gegenrechnungsnamen. Manipulierte Identitäten werden nicht als
  harmlose Datenlücke ausgegeben.
- `tennis_context_result` nutzt B3. Ohne echte D2-Freigabe bleibt der Vergleich
  experimentell und `used_*` vollständig die Basis. Typisierte Modellfehler,
  fehlende/partielle Daten, falscher Scope und numerische Sättigung liefern keine
  erfundene Vergleichsverteilung. Synthetische Freigabe-Transporttests prüfen nur
  B3-Mechanik; ihre Testobjekte sind keine Produktionsfreigaben.
- Gruppen-Gegenrechnungen entfernen jeweils nur die numerischen Eingaben einer
  benannten Gruppe gegen dieselbe Basis. Die Ergebnisse sind als **nicht additiv**
  gekennzeichnete, umhüllte Gegenrechnungen, keine behaupteten kausalen Einzelbeiträge
  und keine als Beobachtung gespeicherten künstlichen Nullen.

## Testnachweise bis zum Review-Freeze

- Unveränderte Ausgangsbasis: **558 bestanden**, 3,97 s.
- Echtes RED: fehlendes `context_models.tennis_effect`, Importfehler in der neuen
  fokussierten Regression; kein Ausweichen auf einen bereits vorhandenen Stub.
- Erste Green-Stufe: vier Tests, anschließend 106 bestandene Tests; ein bewusst
  auf zukünftige Zeit gesetztes Testartefakt verwendete zunächst eine nicht
  kanonische Uhrschreibweise und wurde korrekt als Integritätsfehler abgelehnt.
  Die Fixture wurde kanonisch geschrieben, nicht der Transportvertrag gelockert.
- Letzter fokussierter Lauf: **840 bestanden**, 11,19 s, einschließlich B7,
  B6, B1/B2/B3, Tennis-Modell, Predictor, Sidebets, Prediction-Revisions und Workflow.
- Erster vollständiger Lauf vor dem separaten Harnessfix: **2.903 bestanden**,
  **15 erwartete Windows/POSIX-Skips**, **97 Untertests**, **ein bekannter fremder
  Testharnessfehler**, 61,15 s. `test_independent_processes_share_the_same_first_calculation`
  importierte unter Windows den von AppTest ersetzten `__main__`-Pfad und fand
  dort `__args` nicht. Root ließ dafür unabhängig `9ddb45f` prüfen und freigeben;
  die Korrektur wird separat übernommen, keine B7-Produktionsänderung dafür.
- Ein anfänglicher fokussierter Aufruf nannte eine nicht vorhandene Testdatei
  `test_tennis_shadow_revision.py`: **keine Tests ausgeführt**. Der tatsächliche
  Pfad `test_tennis_prediction_revisions.py` wurde ermittelt und im obigen
  840er-Gegenlauf verwendet. Das war kein Modellfehler oder Testpass.

Die Gegenprüfungen umfassen reale isolierte B1-Receipt-/B6-Pfade, doppelte
Beobachtungen, fehlendes Matchende, Rücktritt ohne Verletzungsdiagnose, beide
Seiten der unvollständigen Minuten-/Satzabdeckung, Seitenwechsel mit demselben Fit,
mehrdimensionales Head-Routing, 3/5-Satzformat, gemeinsame Summen und verschachtelte
Linien, unbekannte Familien/Kataloge, Modellüberlauf, unveränderte Basis,
Nullwirkung, Doppelanpassung und unangetastete Eingabeobjekte.

## Exakter Legacy-Gegenlauf

Die Testfixture `tests/fixtures/tennis_simulator_legacy_dd6fd38.py` ist der
**unveränderte Gitblob** der Ausgangsbasis. Sein SHA256 wird vor Ausführung
geprüft. Acht Parameterfälle einschließlich Clamping-/Rundungsgrenzen vergleichen
vollständige ursprüngliche und aktuelle Ergebnisdarstellungen **bytegenau auf
derselben CPU**; keine toleranzbasierte Aufweichung oder plattformfremde Goldenwerte.

Datierter Windows-Nachweis vom 9. September 2026, SHA256 der vollständigen
`repr(asdict(...))`-Ausgabe des ursprünglichen Gitblobs:

| Holds / Best-of | SHA256 |
| --- | --- |
| .78 / .74 / 3 | `d91ee2cb8d19306ba4c972782c58c54d158a385cd288f21e9fb88ddef7bdf674` |
| .78 / .74 / 5 | `eca3311d6769daecb4b547567dffcd2db2c93e1cbf050d30a567dedc29b4acbf` |
| .770001 oder .770009 / .74 / 3 | `cbb723eaccc1b0e511423ac59609acd37b61d14c25f7d09dccbcfe8b52e388fa` |
| .00001 / .7 / 3 | `6c4128d1b5a8a419970d93455ef704f16305a564605c40d07af86537b1bb58e9` |
| .999999 / .75 / 5 | `b05e0a92d740cbc0a89565a1085446fc98e7b760d4a87d9766ab76d4f585f098` |
| .9 / .6 / 3 | `3e540276565bd3aef08d02d82847122fcf9518df66d68bee0d097e163e9bd1a1` |
| .7 / .7 / 5 | `d4b564f9bebd7faf5fded0bd75acd54f70e1b95a17c85c1767e7ac00ca37305b` |

## Eingefrorene Code-/Testbytes des ersten B7-Stands vor Referenzkorrektur

| Datei | SHA256 |
| --- | --- |
| `context_models/tennis_effect.py` | `ebb8533ebf679f338157f3b0c61508290476cf25f0cf6ce7d1f320de918b5fde` |
| `context_models/tennis.py` | `ac3ec475fd64126fbc3e637a915bf0536b9d978e477ecb68841ac8b4fd0aae52` |
| `tennis/simulator.py` | `6f326fc84de6b705b762b9d9efaa2932daf0f4546c419d56f30e8c3f4644e29f` |
| `tests/test_tennis_context_model.py` | `1fccf25eeac7731ba077cadb7c2fbeb3f5e656298b7ba4eb97106b5ddead87b4` |
| ursprüngliche Simulatorfixture | `c0f6a751b09c59c3bb547d13703eb854094c0b6b5527f2bc27358086b3da3734` |

## Abschließender vollständiger Gegenlauf

- B7-Code-/Testcommit: `e9cc3900feb1e32f7e0711dc92795808074d56e6`.
- Ausschließlich der von Root unabhängig freigegebene Testharnessfix `9ddb45f`
  wurde danach als `5aca4cad7b19aafa039f07104ad21cabda85854e` übernommen. Keine
  weitere B7-Source-/Teständerung; die obigen SHA256 bleiben identisch.
- Vollständiger Lauf auf diesem Stand: **2.911 bestanden**, **15 erwartete
  Windows/POSIX-Skips**, **97 Untertests bestanden**, **0 Fehler**, 60,53 s.
- Aufruf: absoluter Quality-Python mit `-B -m pytest -q -rs -p no:cacheprovider
  --basetemp=.pytest_tmp/b7-full-fixed-20260909` im B7-Worktree.
- Der letzte fokussierte 840er-Lauf enthält **144 neue B7-Fälle**. Die beiden
  neuen expliziten Singlesformat-Codes und die strict-Seam haben zusätzlich die
  gesamte unveränderte Legacy-/Workflow-/Cricket-/15K-Suite durchlaufen.
- Nach dem Testlauf wurden ausschließlich diese Ergebniszeilen ergänzt.

Unabhängiges Review ist weiterhin Sache des Controllers. Der grüne Softwarelauf
ist ausdrücklich keine empirische oder produktive Freigabe; die am Anfang
benannten Daten-/Trainings-/Betriebsaufgaben bleiben offen.

## Referenzkorrektur v2 – vollständige Event-/Basisbindung

Nach dem unabhängigen Anschlussreview wurde konkret festgestellt: B6-Erholung
bezieht sich auf den angesetzten nächsten Beginn. Der erste history-only-
Referenzhash konnte deshalb denselben Merkmalsstand bei geändertem Beginn oder
anderer Event-/Basisrevision nicht selbst zurückweisen. Der frühere B3-Snapshot-
Eventhash allein ersetzt diese numerische Consumer-Prüfung nicht.

Der Controller gab als separate enge Korrektur folgenden Vertrag vor:

```text
FEATURE_VERSION = tennis-performed-load-v2
reference_hash = SHA256(canonical({
    version: tennis-context-reference-v2,
    base_hash: SHA256(canonical(validate_base_distribution(original_base))),
    event_hash: SHA256(canonical(validate_event(event)))
}))
```

- B6-Producer und B7-Consumer teilen `tennis_reference_hash`; keine zweite leicht
  abweichende Hashdefinition und keine Preprocessing-/Approvaldaten im B7-Hash.
- Die komplette ursprüngliche Verteilung umfasst auch Modellversion, Parameter,
  Märkte, historischen Referenzstand und Stichtag. Das komplette Event umfasst
  Termin, Terminrevision, Status, Teilnehmerorientierung, Format, Tour, Belag,
  Hallen- und Wettbewerbsangaben. UTC-äquivalente Schreibweisen bleiben gleich.
- Feature-/Effect-Version v1 wird nicht still migriert. Der alte history-only-
  Hash wird auch mit umbenanntem Featurestand nicht akzeptiert.
- Gleicher nativer Eventschlüssel und gleicher Stichtag genügen bei veränderten
  gebundenen Inhalten nicht. Der Consumer meldet einen Integritätsfehler;
  die künftige D3-Anbindung muss vor Wiederverwendung neue Merkmale erzeugen.
- Echte Neuberechnung nach vier Stunden Terminverschiebung aktualisiert beide
  absoluten Erholungswerte um vier Stunden und erzeugt eine neue Referenz- und
  Vergleichsidentität. Die alte Event-/Featurekombination bleibt unverändert
  reproduzierbar. Änderungen der Basis verändern keine beobachteten Sportwerte,
  wohl aber ihre vollständige Berechnungsbindung.
- Reine externe Preis-/Tabänderungen sind weiterhin keine Eingaben. Keine
  Fensterarithmetik, Quellenhistorie, numerischen Fits, Simulator-/Legacybytes,
  Cricket-/UI-/Job-/15K-Pfade oder produktiven Daten geändert.

### Korrekturevidenz

- Neues echtes RED gegen `1acd2fa`: **14 Fehlfälle**, 144 andere B7-Fälle
  bewusst deselektiert. Beginn, Revision, Teilnehmer und Basisänderungen konnten
  zuvor ohne den verlangten Referenzfehler durchlaufen; weitere Scopeänderungen
  wurden zu spät nur als unpassende Modellpopulation erkannt. Der B6-Producer
  lieferte erwartbar noch v1. Dieser Befund wurde nicht verschwiegen.
- Nach der Korrektur: **223 B6/B7-Fälle bestanden**, 3,20 s. Danach zusätzliche
  v1-Transportablehnung, wirklicher B6-Neubau nach Terminänderung sowie getrennte
  Serve-Basisparameter-/Marktänderungen abgesichert.
- Finaler fokussierter Lauf: **860 bestanden**, 9,29 s. Er enthält alle
  unveränderten vorherigen Mathematik-/Legacy-/Workflow-Prüfungen und insgesamt
  **164 B7-Fälle**. Bestehende Tests wurden lediglich an den ausdrücklich
  geänderten Referenzvertrag gebunden, keine erwartete Sportwirkung gelockert.

| Aktuelle v2-Datei | SHA256 |
| --- | --- |
| `context_models/tennis.py` | `e0ea6e53852cbcf671c0fc69af51c43ecaac05ae8562f0a2cda79c1aab209349` |
| `context_models/tennis_effect.py` | `95ee2b5fb9b57c3605388c1920a9a893dc7711e81fb6c6bf09690fc1e43a0a54` |
| `tests/test_tennis_context_features.py` | `c9f2af758ac28142cb44a817b83eedbbc3a9e8a2d604755410ee2b35a51c9bf9` |
| `tests/test_tennis_context_model.py` | `f45dfc34bcbba97dbace508cc1cbf53489767b3f13dc6d4e44734942c4c1a025` |

Simulator und ursprüngliche Simulatorfixture haben weiterhin die oben
dokumentierten identischen SHA256. Der vollständige v2-Gegenlauf auf genau
diesen Codebytes ist grün: **2.931 bestanden**, **15 erwartete Windows/POSIX-Skips**,
**97 Untertests bestanden**, **0 Fehler**, 69,45 s. Verwendet wurde derselbe
vollständige Quality-Python-Aufruf mit neuem isoliertem
`--basetemp=.pytest_tmp/b7-v2-full-20260909`. Danach wurden nur diese
Ergebniszeilen ergänzt. Unabhängige Wiederprüfung sowie sämtliche fachlichen
Daten-/Trainings-/D1-/D2-/Betriebsabhängigkeiten bleiben offen.
