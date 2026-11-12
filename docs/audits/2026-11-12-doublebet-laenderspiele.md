# Doublebet: Länderspiele ohne Verletzungsdaten (12.11.2026)

Owner-Entscheid am 12.11.2026: „Ja, zulassen“. Policy `doublebet-odds-around-2-most-probable-v16`.

## Anlass

Am 11. und am 12.11.2026 (Länderspielpause) war das Doublebet leer. Am 12.11. um 07:46 lagen drei
Fussballzeilen im Quotenband 1,80–2,20:

| Spiel | Auswahl | Median | Modell |
|---|---|---|---|
| England – Kroatien | England unter 2,5 Tore | 1,85 | 53 % |
| San Marino – Belarus | Belarus unter 2,5 Tore | 1,83 | 66 % |
| Tschechien – Spanien | Spanien unter 2,5 Tore | 1,90 | 71 % |

Alle drei sind A-Länderspiele (`model_scope = senior_national_pooled`). `football_context_highlight_reason`
schloss sie mit „Spielinformationen nicht aktuell belegt“ aus. H2H und Wetter waren geprüft und frisch.
Gesperrt hat allein die Verletzungsprüfung: `status=unavailable`, `availability=not_covered`. API-Football
deckt Verletzungen für Nationalteams nicht ab („Verletzungsdaten werden für diese Liga nicht abgedeckt“,
`challenge_engine._injury_summary`). Ein Länderspiel konnte deshalb nie ins Doublebet.

## Änderung

- `forecast_analysis.football_context_highlight_reason(..., uncovered_injuries_ok=False)`: Mit dem Schalter
  übergeht die Prüfung nur die Verletzungsachse. Das gilt nur, wenn die Quelle ausdrücklich „nicht abgedeckt“
  meldet (`availability='not_covered'` und `coverage_available=False`). Ohne Schalter ist alles wie vorher.
- `daily3_selection._explanation` setzt den Schalter nur für A-Länderspiele (`model_scope ==
  daily3_comparison.NATIONAL_SCOPE`). `model_scope` gehört zur Identität der Evidenz; eine umetikettierte
  Vereinszeile bleibt draussen (Test).
- Unverändert:
  - Vereinsspiele ohne Verletzungsdaten bleiben draussen.
  - Ein fehlgeschlagener oder fehlender Verletzungsabruf sperrt weiter.
  - H2H, Wetter, das Aufstellungs-Veto, ein Widerspruch und die Tageslebensdauer sperren weiter.
  - Die Regeln für Quotenband, Spielende vor Mitternacht und höchstens drei Wetten gelten weiter.
  - Wettfinder-Hervorhebung, Tipps, 15K und RisikoBet behalten die volle Kontextprüfung.
- Die Karte zeigt im Hinweis den bestehenden Satz „Verletzungsdaten für dieses Spiel nicht abgedeckt“.

## Risiko, ehrlich

Bei diesen Wetten ist nicht geprüft, ob wichtige Spieler fehlen. Ein Ausfall bleibt unbemerkt. Ob das
Länderspielmodell trifft, was es verspricht, ist hier nicht neu geprüft. Die Änderung wirkt nur an Tagen mit
A-Länderspielen.

## Trockenlauf mit Live-Daten (12.11.2026, 08:03)

Der Branch-Code lief nur lesend gegen den Live-Snapshot:

- **Zugelassen:** Die drei Länderspiele von heute und Serbien – Deutschland vom 13.11. (Deutschland unter
  2,5 Tore, 1,88, 70 %).
- **Weiter draussen:** Das Vereinsspiel Llaneros – Chico (Kolumbien, 1,87) im Band.
- **Doublebet heute:** Tschechien – Spanien, Spanien unter 2,5 Tore, 1,90, 71 %. Alle drei Spiele beginnen um
  20:45, deshalb gibt es nur eine Wette. Der Hinweis nennt die fehlenden Verletzungsdaten.
- **Vorschau 13.11.:** Columbus – Tampa Bay (Sieg Tampa, 1,82, 57 %) und Serbien – Deutschland (1,88, 70 %).

## Tests

`tests/test_doublebet_laenderspiele.py` prüft diese Fälle:

- Länderspiel mit „nicht abgedeckt“ kommt ins Doublebet, mit Hinweis und Policy v16.
- Vereinsspiel bleibt draussen, auch umetikettiert.
- Fehlgeschlagener oder fehlender Verletzungsabruf bleibt draussen.
- Gesperrtes Wetter, gesperrte H2H, Aufstellungs-Veto, veraltetes Wetter, fehlende H2H und Widerspruch bleiben
  draussen.
- Die anderen Flächen behalten den Ausschluss.
- Länderspiel mit geprüften Ausfällen bleibt wie bisher.

Der Zulassungstest ist auf `main` rot und auf dem Branch grün.

Lokal grün:

- Doublebet-, Daily3-, Hervorhebungs-, Analyse-, RisikoBet- und Morgen-Suiten (1058 Tests).
- Doublebet- und Hervorhebungs-Suiten unter `BETBOY_TEST_PRICE_POLICY=floor` (411).
- Ausgenommen: `test_forecast_consumer_reuses_exact_cached_price_without_network`, scheitert schon auf `main`
  (bekannt seit 10.11.).

## Rückweg

In `daily3_selection._explanation` `uncovered_injuries_ok=False` setzen. Das stellt v15 wieder her.
