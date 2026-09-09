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
- B4-Referenzbindung bleibt exakt
  `digest({base_hash: digest(validated_original_base), preprocessing: sorted(set(artifact.preprocessing_artifacts.values()))})`.
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

SHA-256 der unveraenderten Implementierungs-/Testbytes im vollen Lauf:

- `context_models/football_effect.py`:
  `571dbccde4d5c2e35997b38bfa1e7aeefe88ca0e4b227e8612cd2ae16f001c66`
- `tests/test_football_context_model.py`:
  `7769de0574e05d7ffbbc6111afd13a3a5942be1de83e29dba59c269b8ceb08a2`

## Explizit nicht erledigt

`build_football_training_rows`, tatsaechliches Training auf kausal belegten
Spieler-/Einsatzdaten, D1-Walk-forward-Auswahl, D2-Abnahme, B4-Quellenintegration,
D3/Worker/UI-Anbindung und Aktivierung bleiben offen. Es wurde kein echter
Verletzungseffekt behauptet oder aus diesen synthetischen Tests freigegeben.
Keine Providerabrufe, Produktionsdatenbank-, VPS-, Quoten-, Geldbewegungs- oder
15K-Vertragsaenderungen. Dieser Teilauftrag ist nicht die komplette B5-Abnahme.
