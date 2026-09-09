# B5: begrenzte gemeinsame Torraten- und Kontrafakt-Mechanik

Stand: 9. September 2026. Basis `f876df0588aaed82db4a752e5f23977c6ceb5dc1`.
Arbeitskopie `.worktrees/kontext-b5-raten-20260909`, Branch
`codex/kontext-b5-raten-20260909`. Nur lokale synthetische Mechanik;
unabhaengiges Review, Integration, Push und Deployment noch offen.

## Bestaetigter Zusatzvertrag

Die B5-Sektion, A1-Transport, B1/B2/B3-Vertraege, Controller-Entscheidungen und
bestehenden MarketSpec-/Scorematrix-Vertraege wurden vor Umsetzung gelesen.
BaseDistribution und FeatureVector enthalten absichtlich keine vollstaendige
Eventpopulation. Der Controller hat deshalb vorab eng bestaetigt:

- `apply_football_effect(base, features, artifact, *, event)`.
- `football_factor_comparisons(base, features, artifact, *, event, groups)`.
- `groups`: stabile Gruppennamen mit nichtleeren, eindeutigen Featurelisten
  in exakter Artefaktreihenfolge; alle konsumierten Features sind abgedeckt.
  Ueberschneidungen sind fuer ausdruecklich geteilte Interaktionsspalten erlaubt.
- Jeder Gruppenvergleich setzt die benannten Referenzdifferenzen separat auf
  null, immer aus Originalfeatures und Originalbasis. Keine sequentielle
  Aufsummierung. Die Ausgabe ist `model_counterfactual`, `additive=False`, mit
  Originalbasis-/Feature-/A1-Effekt-/Gruppenhash, vollstaendigen Verteilungen und
  `delta_pp_vs_full` (Kontrafakt minus volle Rechnung, in Prozentpunkten).
- Das ist kein beobachteter kausaler Einzelspielereffekt. D1/D3 besitzen die
  spaetere versionierte Gruppierungsprovenienz; EffectArtifact wurde nicht um
  versteckte Gruppierungsfelder erweitert.

Die zwei Funktionen liegen bewusst in der neuen `context_models/football_effect.py`.
Der Controller integriert spaeter oeffentliche Reexports. Weder
`context_models/football.py` noch `challenge_engine.py` wurden hier veraendert.

## Numerische und Identitaetsgrenzen

- Zwei bestehende B2-`log_rate`-Heads auf den ORIGINAL-Lambdas. Featurelisten
  werden nicht alphabetisch umgeordnet, Skalen stammen ausschliesslich aus
  dem uebergebenen Fit. Keine zusaetzliche Heim-, Prozent- oder Spielerkonstante.
- Genau eine bestehende `score_matrix` pro vollstaendigem Vergleich; derzeit
  40 explizite 90-Minuten-Tor-MarketSpecs ueber `market_probability`.
- Die 50 bekannten Ecken-/Karten-MarketSpecs bleiben unveraendert. Unbekannte
  IDs werden insgesamt abgelehnt, nicht anhand ihres Namens geraten. Der
  bestehende Katalog hat keine Halbzeit-MarketSpecs; erfundene HT-IDs werden
  daher ebenfalls abgelehnt. Keine Fremdfamilie wird neu zertifiziert.
- Keine alten separaten Marktkalibrierkurven. Die einzige aktuell erlaubte
  gemeinsame Kalibrierungsvariante ist der geschlossene Identitaetsvertrag.
- Event, Spielstatus, Termin, Cutoff, Teamorientierung, Familie, Population,
  Featureversion, Coverage, Featureverfuegbarkeit und echte Referenzen werden
  geprueft. Training darf nicht nach dem Entscheidungszeitpunkt liegen.
- Die nach unabhaengigem Review ausdruecklich freigegebene B4/B5-Referenz-v2
  ist exakt `digest({version: 'football-context-reference-v2', base_hash:
  digest(validated_original_base), event_hash: digest(validate_event(event)),
  preprocessing: sorted(set(artifact.preprocessing_artifacts.values()))})`.
  Nur `football-roster-components-v2` gehoert zu diesem Anschlussvertrag.
  Termin-/Status-/Teilnehmer-/Wettbewerbsrevisionen brauchen neu gebildete
  Features. Alte unversionierte Referenzen und lediglich neu gehashte
  v1-Featurevektoren werden nicht als neue Berechnung angenommen.
  Doppelte benannte Bindungen desselben Preprocessing-Hashes werden nicht als
  zwei verschiedene Artefakte gerechnet.
- Effekthash: A1-`digest({kind: 'context-effect-v1', payload: artifact})`.
  Kanonische Artefaktbytes bleiben unveraendert. Der neue Modellhash bindet
  beide Heads, Originalbasis, komplette Features, konkretes Event und Katalog.
- Ungueltige/nicht darstellbare Raten, ungueltige Matrixmasse, NaN/Bool, fehlende
  Features und vorzeitige Integer-Rundung sind typisierte Fehler. Kein Clipping
  und keine teilweise veraenderte Marktausgabe. Die Engine-Obergrenze 8 bleibt
  unveraendert; ein bereits erzeugter Vergleich darf nicht neue Basis werden.

## Eigene RED/GREEN-Nachweise

Interpreter `.codex_test_venv/quality/Scripts/python.exe`; `-B -m pytest -q
-p no:cacheprovider`, eindeutige lokale Basetemp-Verzeichnisse.

- `b5-function-red-01`: **1 fehlgeschlagen, 1 bestanden**. Die echte neue
  Function fehlt; der bereits existierende B2-Fit allein ist kein B5-Nachweis.
- `b5-guards-red-01`: **59 fehlgeschlagen, 1 bestanden** vor Implementierung.
- `b5-green-01`: **60 bestanden**.
- `b5-green-02`: **520 bestanden**, einschliesslich A1/B2/B3-Vertraegen.
- Eigene zusaetzliche Integer-Gegenprobe `b5-integer-red-01`: **1 rot**.
  Die Float-Konvertierung vor B2 konnte `2**53+1` unbemerkt runden; nun wird
  vor Konvertierung die exakte Darstellbarkeit von Integer-Eingaben geprueft.
- `b5-green-03`: **674 bestanden, 32 Untertests**, einschliesslich 15K-Kern.
  Insgesamt **85 neue B5-Testfaelle**, darunter acht deterministische
  synthetische Feature-/Ratengitter und sechs Grenzratenpaare.
- Vollsuite `b5-full-01`: **1 fehlgeschlagen, 2786 bestanden, 15 erwartete
  Skips, 97 Untertests**, 60,19 Sekunden. Keine gruene Gesamtfreigabe.
- Der bestehende B3-Test
  `test_independent_processes_share_the_same_first_calculation` startet nach
  einem Streamlit-AppTest dessen temporaeres `__main__`-Skript und scheitert
  mit `NameError: __args`, daraus `BrokenProcessPool`. Der Fehler tritt in der
  Gesamtsuite vor Ausfuehrung der neuen B5-Testfaelle auf.
- Isolierte Wiederholung nur der UNVERAENDERTEN Dateien `test_bet_finder_ui.py`
  plus dieses einen Prozesspooltests: `b5-existing-process-repro-01`, **1 rot,
  12 gruen**, gleicher Fehler ohne Import/Ausfuehrung des B5-Moduls.
- Derselbe Prozesspooltest allein: `b5-process-alone-01`, **1 bestanden**.
  Diese Bestands-Testisolation wurde an den Controller uebergeben und nicht
  durch Skip, Aenderung der Testreihenfolge oder abgeschwaechte Assertions als
  behoben ausgegeben. Die drei neuen B5-Dateien bleiben der gesamte Patch.

Geprueft sind Summen, Komplemente, geschachtelte Torlinien, gemeinsame
Resultat/Tor-Kombinationen, Seitenwechsel, Matrix-Einmaligkeit, Abwehr-/Angriffs-
Headreihenfolge, Parametergrenzen, Quellenreferenzen, Preprocessing-Deduplikation,
A1-put/load-Rundreise und B3: ohne D2-Freigabe bleibt `used` exakt die Basis,
der Vergleich ist nur `experimental`, und `certified_markets` bleibt leer.
Originaleingaben bleiben unveraendert; rueckgegebene Historien sind entkoppelt.

SHA-256 der damaligen Implementierungs-/Testbytes im ersten vollen Lauf:

- `context_models/football_effect.py`:
  `571dbccde4d5c2e35997b38bfa1e7aeefe88ca0e4b227e8612cd2ae16f001c66`
- `tests/test_football_context_model.py`:
  `7769de0574e05d7ffbbc6111afd13a3a5942be1de83e29dba59c269b8ceb08a2`

## Unabhaengiges Review und eng autorisierte Korrekturen

Die unveraenderten externen Repros des B3/B4-Reviewers wurden auf Commit
`49e6faefd7a8f73be766ef2c8b53301f547f3192` selbst ausgefuehrt:
`b5-review-fixes-red-01`, **5 fehlgeschlagen, 1 bestanden**. Repro-SHA256
`07ab92411606a12fd28a2ff9eefdc71c4afc561c366ca72e34899edf82974772`.

- Eine bekannte native Zielteam-ID bleibt bindend, wenn nur die historischen
  Joins `unresolved` sind. Jetzt werden ALLE vorhandenen nichtleeren
  Komponenten-IDs gegen die konkrete Home-/Away-Angriff-/Abwehrorientierung
  geprueft. Unbekannte Historie radiert keine bekannte Zielidentitaet aus.
- Der gemeinsame B2-Fitvalidator prueft Integer-Koeffizienten und -Skalen
  VOR Float64-Konvertierung auf exakte Darstellbarkeit. Der Gegenfall
  `(2**53+1)-2**53` darf nicht durch Konvertierung zu null werden. Es gibt
  keine pauschale 2**53-Grenze: exakt darstellbare grosse Zahlen, einschliesslich
  `2**1023`, bleiben gueltig. Artifact-JSON und Hashes werden nicht veraendert.
  Der numerische Fehlerwrapper bewahrt den konkreten typisierten Fehlergrund.

Eigene 27 permanente Zusatzfaelle vor Fix: `b5-review-permanent-red-01`,
**13 fehlgeschlagen, 14 bestanden**. Nach Korrektur: unveraenderte externe
Repros plus Fokus `b5-review-fixes-green-01`, **380 bestanden**.

Zusaetzlich bestaetigte der Controller nach dem Event-Replaybefund den oben
beschriebenen v2-Vertrag. `b5-event-reference-red-01` reproduzierte
**7 fehlgeschlagen, 4 bestanden**: Termin frueher/spaeter, Schedule-Revision,
beide Teilnehmer trotz fehlender Historien-ID, Competition innerhalb derselben
erlaubten Population und Legacy-Hash waren nicht ausreichend gebunden.
`b5-feature-version-red-01`: **3 fehlgeschlagen** fuer v1/v3/fremde beidseitig
passende Feature-/Artifactversionen. Der Controller hat explizit nur v2 fuer
diesen Pfad freigegeben; kuenftige Varianten benoetigen einen eigenen Vertrag.

Nach v2-Umstellung: `b5-reference-v2-green-01`, **388 bestanden**.
Mit positiven Neu-Referenz-/Zeitzonenfaellen und A1/B1/B2/B3/15K-Fokus:
`b5-reference-v2-green-02`, **830 bestanden, 4 erwartete Skips, 32 Untertests**.
Die permanente Orientierungsgegenprobe bindet absichtlich den umgedrehten
Event korrekt an den v2-Referenzhash. Sie erreicht deshalb wirklich die
Teampruefung, nicht zufaellig den vorgelagerten Referenzvergleich. Der
urspruengliche Replayfall bleibt als eigener negativer Referenztest erhalten.
Die historische externe Reprodatei wurde nicht angepasst oder ueberschrieben.

Vollsuite der korrigierten Bytes: `b5-review-full-02`, **1 fehlgeschlagen,
2829 bestanden, 15 erwartete Skips, 97 Untertests**, 67,83 Sekunden. Derselbe
unveraenderte UI-zu-Spawn-Harnessfehler aus dem ersten vollen Lauf bleibt der
einzige Fehler. Der Controller integriert dafuer separat den unabhaengig
geprueften B3-Harnessfix; dieser ist absichtlich kein Teil dieses B5/B2-Commits.
Keine Vollsuitefreigabe fuer diese isolierte Arbeitskopie behauptet.

Finale SHA256 der korrigierten Quell-/Testbytes:

- `context_models/contracts.py`: `fafa94df182f3cf5e37eb2ec2cf800e06e2821bcc954670092ac16195cb2ab32`
- `context_models/offset.py`: `027939cc5f7c05648177bfc94605bdc5f0fabac10e215d346a6e9ba1b37ec7a7`
- `context_models/football_effect.py`: `76f6db32ccbde0d582bb988a431e384cb1f71eb814c255e3ef311e33047e7789`
- `tests/test_context_offset.py`: `74f0f30878ec6fc1c7f30f3a7ab7eca901c89057c5fb1154f651855c07a416b7`
- `tests/test_football_context_model.py`: `f7f5d77e79c2e1c63648a6ef9715d745281b944637c04f1979ef24a768c9b413`

## Explizit nicht erledigt

`build_football_training_rows`, tatsaechliches Training auf kausal belegten
Spieler-/Einsatzdaten, D1-Walk-forward-Auswahl, D2-Abnahme, B4-Quellenintegration,
D3/Worker/UI-Anbindung und Aktivierung bleiben offen. Es wurde kein echter
Verletzungseffekt behauptet oder aus diesen synthetischen Tests freigegeben.
Keine Providerabrufe, Produktionsdatenbank-, VPS-, Quoten-, Geldbewegungs- oder
15K-Vertragsaenderungen. Dieser Teilauftrag ist nicht die komplette B5-Abnahme.
