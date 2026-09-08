# Unabhängiges Review: widerspruchsfreie Wettfinder-Auswahl

Datum: 08.09.2026, Europe/Zurich.

Ergebnis: **APPROVED – keine Findings im unten exakt gebundenen Source-Freeze.**

Review-Basis: `4f3ecd5db75cb6f4f466270a568ede742d4ed767` plus die acht unten aufgeführten, noch uncommitteten Quell- und Testdateien im Worktree `.worktrees/widerspruchsfreie-auswahl-20260908`. Die Freigabe bezieht sich ausschließlich auf diese geprüften Bytes, nicht auf ungeprüfte spätere Änderungen.

## Auftrag und Abgrenzung

Unabhängiges Read-only-Review der Auswahlkorrektur für die automatischen Wettfinder-Karten und die manuelle Fußball-Mehrmarktauswahl. Während der Prüfung wurden keine Quell-, Test-, Laufzeit-, Datenbank- oder Serverdateien verändert. Dieses Dokument wurde erst nach Abschluss des Reviews auf ausdrücklichen Auftrag des Controllers neu angelegt; der Reviewer hat nicht committed, gepusht oder deployed.

Geprüfte Anforderungen:

- Keine gegensätzliche sichtbare Auswahlmenge für dasselbe tatsächlich identifizierte Ereignis, über Topkarten, Zusatzkarten und Seiten hinweg.
- Prüfung der gemeinsamen Erfüllbarkeit aller behaltenen Marktbedingungen, nicht lediglich paarweiser Verträglichkeit.
- Alle 90 konfigurierten Fußballmarktdefinitionen bleiben einzeln zulässig; kein pauschales Wettartenverbot.
- Quote, Preisstatus und Wahrscheinlichkeit ändern nicht die logische Auswahlentscheidung. Keine Veränderung gespeicherter Modellkandidaten, Wahrscheinlichkeiten, Finanzregeln oder Abrechnungshistorien.
- Native Ereignis- und Teilnehmeridentitäten, kanonische vollständige UTC-Anstoßzeiten und eine korrekt gebundene Home-/Away-Achse.
- Manuelle Fußballauswahl löst Konflikte vor dem 25er-Anzeigelimit und vor jeder nachgelagerten Preisaufteilung.
- Die bestehenden Default-Helfer und die 15K-Aufrufer bleiben unverändert; der neue manuelle Auswahlpfad ist explizit opt-in.

Nicht Gegenstand dieser Freigabe sind die separate manuelle Tennis-Preisprüfung, RisikoBet, Live, 15K, sportliche Prognosegüte, empirische Modellvalidierung, zukünftige Verletzungs-/Müdigkeitsmodelle, Browserdarstellung oder Deployment. Diese Grenzen dürfen nicht zu einer Aussage „die gesamte App ist überall widerspruchsfrei“ erweitert werden. Der Controller prüft Browser und Release separat.

## Ursprünglicher Fehler und öffentliche API-Reproduktion

Im unveränderten Ausgangsstand wurden für Fixture `1635654` zwei `ModelSignal`-Objekte mit `RESULT_HOME = 0.464` und `RESULT_AWAY = 0.212` über `build_wettfinder_card` an `compose_wettfinder_catalog` übergeben. Ergebnis: Heimsieg als Topkarte und Auswärtssieg als Zusatzkarte. Drei vorgestellte, unabhängige brauchbare Karten verschoben beide Porto-Auswahlen gemeinsam in den Zusatzbereich. Dies reproduzierte den Screenshot ohne Änderungen an Dateien oder Produktionsdaten.

Ursache war der Unterschied zwischen zwei Verträgen: Ein vollständiger Rohkatalog darf Wahrscheinlichkeiten für alternative mögliche Ausgänge enthalten; eine nutzerseitige Empfehlungsliste darf diese nicht unkritisch als gleichzeitig passende eigenständige Tipps präsentieren. Der alte Code deduplizierte Fixtures nur innerhalb der Topkarten. Alle übrigen Marktzeilen gelangten anschließend in die Zusatzkarten und deren Pagination.

Auf dem geprüften Fix ergab die erneute öffentliche API-Reproduktion ausschließlich `RESULT_HOME` für Porto. Das galt sowohl für den automatischen Katalog als auch für `_merge_consumer_market_rows(..., coherent=True)` im manuellen Fußballpfad. Eine automatische Variante mit drei Zusatzseiten behielt ebenfalls nur die Heim-Auswahl. Alle behaltenen Karten waren dieselben ursprünglichen Objekte; die Wahrscheinlichkeit der verworfenen Gegenauswahl wurde nicht verändert.

## Tatsächlich ausgeführte unabhängige Prüfungen

### Fokus-Suite

Ausgeführt im Fix-Worktree mit der vorhandenen Qualitätsumgebung:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp/independent-coherence-20260908 tests/test_selection_coherence.py tests/test_manual_selection_coherence.py tests/test_wettfinder_surface.py
```

Ergebnis: **221 passed in 3.16s**, Exit 0. Dies ist der eigene Reviewer-Lauf; die breitere Suite des Controllers ist davon getrennte Evidenz.

### Zusätzlicher In-memory-Gegenlauf

Der zusätzliche Prüflauf lief über öffentliche Python-APIs mit `python -B -c`, ohne ein Probeprogramm oder Modelldaten auf Platte zu schreiben. Er verwendete `challenge_engine.market_outcome` aus der unveränderten Ausgangssemantik und ein eigenes breiteres Raster aller Home-/Away-Zählwerte von 0 bis 40. Tor-, Eckball- und Gelbkartenräume wurden getrennt ausgewertet. Das behauptet keine statistische Unabhängigkeit dieser Sportgrößen.

Tatsächlich geprüft:

- **90 Einzelmärkte:** Jede konfigurierte Definition bleibt als alleinige Primärauswahl erhalten, mit identischem Originalobjekt.
- **8.100 geordnete Marktpaare:** Alle 90 × 90 Paare wurden gegen ein eigenständig aufgebautes, domänenspezifisches Ergebnisraster geprüft. Die vom Selector behaltenen Originalobjekte entsprachen der unabhängig berechneten möglichen Teilmenge.
- **400 vollständige 90er-Pools:** Deterministische unterschiedliche Reihenfolgen mit Seed `20260908`; alle ausgewählten Objekte stimmten mit dem unabhängigen fortlaufenden Schnittmengenverfahren überein. Eingabeobjekte und Eingabefelder blieben unverändert.
- **Drei zusätzliche Global-Konflikttripel:** `DC_1X / DC_X2 / DC_12`, `BTTS_NO / HOME_OVER_0_5 / AWAY_OVER_0_5` und `TOTAL_OVER_2_5 / HOME_UNDER_0_5 / AWAY_UNDER_2_5`. Jeweils wurden die ersten beiden verträglichen Bedingungen behalten und die dritte gemeinsam unmögliche Bedingung verworfen. Eine bloße paarweise Prüfung würde diese Fälle übersehen.
- **13 Identitäts-/Gewinner-Gegenfälle:** Unveränderte Teilnehmer-IDs bei umbenannten und lexikografisch umgedrehten Teamlabels; tatsächlich vertauschte IDs bei abweichenden Labels; vollständige, fehlende, teilweise und widersprüchliche Teilnehmerbindungen; schwache Ereignisidentität vor einer starken Identität einschließlich `preferred`; äquivalente Zeitzonen; getrennte starke Native-IDs; echte Folgetags-Rematches; gegensätzliche `H2H`-Seiten für Tennis, Basketball, Eishockey und E-Sport; sowie Fußball-`H2H` gegen die widersprechende `RESULT_AWAY`-Auswahl.
- **Automatischer Porto-Fall:** Nur `RESULT_HOME` bleibt sichtbar, einschließlich einer Variante über drei Zusatzseiten.
- **Preisneutralität:** Ersetzen von beobachteter Quote, Preiscode und Bestätigungsstatus änderte die gewählten Schlüssel nicht.
- **Identitätsweitergabe:** Die automatische Karte bewahrte die ursprünglichen numerischen Home-/Away-IDs.
- **Manueller Porto-Fall:** Eine preisgeprüfte Gegenseite verdrängte nicht die ausgewählte Modellrichtung.
- **Limit-Reihenfolge:** 30 zuvor liegende widersprüchliche Zeilen verhinderten nicht, dass ein späteres unabhängiges Spiel die auf zwei Einträge begrenzte Darstellung erreichte. Damit wird nicht zuerst auf 25 Rohzeilen gekürzt und erst danach bereinigt.
- **Legacy-Vertrag:** `_merge_consumer_market_rows` ohne Opt-in und `partition_consumer_featured_forecasts` behielten die bisherigen Rückgaben unverändert.

Der vollständig korrigierte zusätzliche Gegenlauf endete mit **Exit 0**. Seine Ergebniszusammenfassung lautete:

```json
{
  "single_markets": 90,
  "ordered_pairs": 8100,
  "random_complete_pools": 400,
  "triplets": {
    "DC_1X/DC_X2/DC_12": ["DC_1X", "DC_X2"],
    "BTTS_NO/HOME_OVER_0_5/AWAY_OVER_0_5": ["BTTS_NO", "HOME_OVER_0_5"],
    "TOTAL_OVER_2_5/HOME_UNDER_0_5/AWAY_UNDER_2_5": ["TOTAL_OVER_2_5", "HOME_UNDER_0_5"]
  },
  "identity_and_winner_checks": 13,
  "automatic_porto": ["RESULT_HOME"],
  "automatic_additional_pages": 3,
  "manual_porto": ["RESULT_HOME"],
  "manual_pre_25_cap": true,
  "legacy_defaults_unchanged": true,
  "input_mutation": false
}
```

Transparenz: Der erste zusätzliche In-memory-Lauf stoppte wegen eines Fehlers ausschließlich im eigenen Probehelper (`row() got multiple values for argument 'key'`). Der Helper-Parameter wurde im zweiten In-memory-Aufruf eindeutig benannt. Keine Produktivdatei wurde dafür verändert. Die oben berichteten Ergebnisse stammen aus dem danach vollständig erfolgreich wiederholten Lauf, nicht aus dem abgebrochenen Versuch. Beim Import außerhalb Streamlit erschienen die erwarteten Bare-Mode-/MemoryCache-Warnungen; kein Produktfehler wurde daraus abgeleitet.

## Befunde aus dem Source-Review

Die gemeinsame Auswahlprüfung läuft vor Abschnitts- und Seitentrennung. Sie erhält die ursprünglichen Objekte und deren Reihenfolge. Die Reihenfolge der bevorzugten Primärauswahlen kommt aus den vorhandenen preisneutralen Darstellungsregeln; der Kern interpretiert weder Quote noch Wahrscheinlichkeit als „beste Wette“.

Die während der Vorprüfung festgestellten Identitätslücken sind im Freeze behoben:

- Stabile Teilnehmer-IDs definieren die Ergebnisachse vorrangig vor veränderlichen Namen.
- Unvollständige oder widersprüchliche Teilnehmerbindungen werden nicht als Beleg für kompatible Extras verwendet.
- Eine nur schwach identifizierte Zeile kann durch fehlende Native-ID nicht als zweiter eigenständiger Tipp an einer exakt über Teilnehmer/Label und vollständigem UTC-Anstoß erkannten stärkeren Zeile vorbeigelangen.
- Unterschiedliche gleichrangige Native-IDs werden nicht aufgrund gleicher Namen oder Zeiten erfunden zusammengeführt. Es gibt keinen Fuzzy-Join und keinen neuen Provider-ID-Vertrag.

Die endlichen Zählraster dienen nur dem logischen Erfüllbarkeitsnachweis der bestehenden 90 Marktbedingungen. Es werden keine Modellwahrscheinlichkeiten abgeschnitten oder neue Wettmarktsperren eingeführt. Die aktuelle höchste individuelle beziehungsweise Gesamtgrenze wird überschritten; die zusätzlichen hohen Repräsentanten erhalten Größenordnung, Gleichheit und alle vorhandenen Grenzprädikate.

Ein Scope-Diff für `challenge_15k.py`, `challenge_engine.py`, `challenge_store.py`, `wettfinder_automation.py`, `ev_signal_sources.py`, `tennis_tab.py`, `riskobet_domain.py` und `riskobet_engine.py` war leer. Der unveränderte Stage-Helper hatte weiterhin SHA256 `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Zur Abdeckungsgrenze: Die manuelle Multi-Sport-Ansicht wählt aktuell ein Event per Selectbox und rendert dafür einen Kandidaten, keinen parallelen Mehrmarkt-Katalog. Die manuelle Tenniskarte zeigt eine Modell-Hauptauswahl; ihre separate bestehende Preisprüfung kann eine andere Gewinnerseite als passende Quote benennen. Dieser Tennis-Preisprüfpfad wurde nicht verändert und wird durch dieses Review ausdrücklich nicht freigegeben.

## Exakte Freeze-Bindung

Die folgenden SHA256 wurden vor und nach der unabhängigen Prüfung vollständig gelesen und unverändert bestätigt:

| Datei | SHA256 |
| --- | --- |
| `selection_coherence.py` | `0051932d129fb5c7c21cafe48faa9615bc65a8d4b25189a2d13b3b4caa0768f2` |
| `wettfinder_surface.py` | `2996c91b70ac32dee5700070481ab83405e9b342f426acadf8efb9820a31e6a4` |
| `app.py` | `9aa24d7738913f623dcbed0e6bd22771ad08f0d644b86cb12700d297730374f6` |
| `bet_finder_ui.py` | `c522e23d90f57a651bfecd4ca4c4285438ebd7eb62f461e68f6c50bb560c7336` |
| `alternative_markets_tab_extended.py` | `c8db01ce7be5a81b9b1ab07eac81e643e54abb7c0eed90fe928fd2a7f4a35a67` |
| `tests/test_selection_coherence.py` | `7c41d7279b62579b7ff130672933252ca6c8f4adec813ca1820150e3452926b8` |
| `tests/test_manual_selection_coherence.py` | `188d05ffc733d91b7543acf67b5ea8963ecd805a17e971de65bff1af14fa7ef9` |
| `tests/test_wettfinder_surface.py` | `a91921847e4ce439c9ccd16f947bdfa1f4eea12c4a0b02191f33c82e168e7d97` |

**Abschluss:** Keine offenen Findings gegen diesen eingefrorenen, begrenzten Auswahlfix. Keine Freigabe für ungetestete Quellen, empirische Prognosegüte, Gewinne, separate Produktoberflächen oder ein noch nicht vom Controller verifiziertes Deployment.
