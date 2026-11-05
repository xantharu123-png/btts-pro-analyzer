# Ligastärke für Europapokal-Spiele (Plan „bessere Prognosen“, Schritt 1)

Stand 05.11.2026. Owner-Auftrag: „Ja, starten“ (Schritt 1 aus
`docs/superpowers/plans/2026-11-05-bessere-prognosen.md`, PR #92). Owner-OK für einmalig rund 90
API-Football-Abrufe: „Ja, ~90 Abrufe“. Sicherungspunkt vor der Änderung: Tag `modell-sicherung-2026-11-05`.

## Befund

Hat ein Team in Champions League, Europa League oder Conference League zu wenig Spiele im Wettbewerb,
nimmt das Modell die Tore beider Teams aus ihren Heimatligen (`_continental_team_history`) und rechnet sie
1:1 gegeneinander. Eine Mannschaft, die in Kasachstan viele Tore schiesst, sieht dann aus wie eine, die das
in England tut. In den nachgerechneten Spielen gibt die Live-Rechnung dem Team aus der stärkeren Liga
sogar etwas *weniger* Tore:

| Ligastärke-Abstand des Teams | Spiele (Teamseiten) | tatsächliche Tore | live | neu |
|---|---:|---:|---:|---:|
| −0,75 bis −0,50 | 52 | 0,90 | 1,60 | 0,83 |
| −0,50 bis −0,25 | 183 | 1,08 | 1,56 | 1,10 |
| −0,25 bis 0 | 309 | 1,42 | 1,51 | 1,31 |
| 0 bis +0,25 | 323 | 1,66 | 1,47 | 1,63 |
| +0,25 bis +0,50 | 183 | 1,83 | 1,40 | 1,91 |
| +0,50 bis +0,75 | 52 | 2,83 | 1,33 | 2,46 |

## Daten

- 1091 gespeicherte Europapokal-Ergebnisse (90 Minuten) aus `context_models.db` (`base_fixture`, API-Football),
  07/2025 bis 04.11.2026, nur gelesen.
- Heimatliga-Ergebnisse: einmaliger Abruf am 05.11.2026, **88 API-Football-Abrufe** (Hintergrund-Budget,
  App-eigene Budgetkontrolle, keine Fehler): 26 Ligen von August bis Mai mit den Saisons 2024–2026 und
  5 Ligen mit Kalenderjahr-Saison 2025–2026. Ausgewählt wurden die Heimatligen der Europapokal-Teilnehmer im
  Bestand plus Zypern, Israel, Bulgarien, Aserbaidschan und Kasachstan.
- Nachrechenbar mit der unveränderten Live-Rechnung (`challenge_engine._fixture_model`, UEFA-Wettbewerb für
  den Ligaschnitt, Heimatliga für die Teamstärke): **751 Spiele**. 318 Spiele haben ein Team aus einer nicht
  abgerufenen Liga, 22 haben zu wenig Spiele.

## Modell

Poisson-Regression mit der Live-Torerwartung als Offset und einem Faktor je Heimatliga:

    Tore Heim ~ Poisson(λ_Heim · exp(c_Heim + s[Liga Heim] − s[Liga Gast]))
    Tore Gast ~ Poisson(λ_Gast · exp(c_Gast + s[Liga Gast] − s[Liga Heim]))

Ridge-Prior τ = 0,3 auf s und eine Halbwertszeit von 365 Tagen. Skript: `scripts/uefa_league_strength_fit.py`.
Getrennte Angriffs- und Abwehrfaktoren je Liga waren nicht besser (1X2 0,9400 gegen 0,9387) und bleiben draussen.

## Prüfung (Walk-forward)

Vor jedem Spieltag wird nur mit früheren Spielen geschätzt; die ersten 200 Spiele dienen nur zum Lernen.
Geprüft sind **551 Spiele an 72 Spieltagen** (ab 06.11.2025). Die Standardfehler sind nach Spieltagen gebündelt.

| Mass | live | mit Ligastärke | Differenz (SE) |
|---|---:|---:|---:|
| Tor-Log-Likelihood je Spiel (negativ) | 3,2308 | 3,0948 | −0,136 (0,033) |
| 1X2 Log-Loss | 1,0310 | 0,9387 | −0,092 (0,023) |
| Über 2,5 Log-Loss | 0,6714 | 0,6657 | −0,006 (0,004) |
| Beide treffen Log-Loss | 0,7024 | 0,6970 | −0,006 (0,004) |
| Heim über 1,5 Log-Loss | 0,6863 | 0,6343 | −0,052 (0,018) |
| Gast über 1,5 Log-Loss | 0,6586 | 0,6201 | −0,039 (0,013) |

Kalibrierung über alle Ja/Nein-Märkte (versprochen → eingetroffen):

| Band | live | neu |
|---|---|---|
| 30–40 % | 35,3 → 37,8 | 35,1 → 36,8 |
| 60–70 % | 64,7 → 62,2 | 64,9 → 63,2 |
| 70–80 % | 75,2 → 70,7 | 75,0 → 73,3 |
| 80–90 % | 83,3 → 82,5 | 84,0 → 83,7 |

Kein Band wird schlechter. Die Regel aus dem Plan ist damit erfüllt: Log-Loss und Brier sind besser, und
kein Band verschlechtert sich um mehr als 2 Punkte.

Robustheit (`output/ligastaerke-20261105/robust.log`):
- Nur Spiele 2026/27 (307, geschätzt fast nur mit 2025/26): 1X2 −0,098 (SE 0,027).
- Champions League (219 Spiele): 1X2 −0,068 (SE 0,031).
- Conference League (102 Spiele): 1X2 −0,075 (SE 0,058).
- Lernphase 100 statt 200 Spiele: 1X2 −0,082. Lernphase 300: 1X2 −0,084.
- Halbwertszeit 180 Tage: 1X2 −0,089. Ohne Halbwertszeit: 1X2 −0,095.

Gesamttore (Über 1,5) ändern sich kaum. Das ist erwartet, denn der Faktor verschiebt vor allem die
Torverteilung zwischen den Teams.

## Tabelle (geschätzt bis 04.11.2026)

c_Heim = +0,066, c_Gast = −0,085. Faktor = exp(s); der Abstand zweier Ligen wirkt auf beide Seiten.

England 1,85 · Spanien 1,48 · Deutschland 1,43 · Frankreich 1,38 · Portugal 1,36 · Italien 1,34 ·
Belgien 1,28 · Dänemark 1,20 · Türkei 1,14 · Griechenland 1,12 · Norwegen 1,10 · Ungarn 1,05 ·
Österreich 1,05 · Niederlande 1,04 · Aserbaidschan 1,00 · Zypern 0,95 · Ukraine 0,94 · Polen 0,93 ·
Tschechien 0,93 · Schweiz 0,90 · Israel 0,88 · Bulgarien 0,85 · Serbien 0,84 · Kroatien 0,83 ·
Schottland 0,82 · Rumänien 0,81 · Finnland 0,78 · Schweden 0,75 · Island 0,69 · Slowakei 0,66 ·
Kasachstan 0,65.

Die Niederlande liegen tief, weil dort viele Tore fallen; der Faktor fasst Spielstärke und Torniveau der Liga
zusammen.

## Umsetzung

- `football_league_strength.py`: feste Tabelle, Version `uefa-league-strength-v1-20261104`, reine Rechnung.
- `challenge_15k.scan_daily_challenge`: Jedes Europapokal-Spiel im Heimatliga-Weg bekommt am Spiel die
  Annotation `challenge_league_strength`. Fehlt der Wert für eine der beiden Ligen, bleibt das Spiel ohne
  geprüftes Transfermodell (`cross_competition_unvalidated`, gesperrt), und dafür wird keine
  Heimatliga-Validierung abgerufen. Zähler im Lauf: `continental_league_strength_missing`.
- `challenge_engine._fixture_model`: Saison-, Form- und aktive Torerwartung werden mit den geprüften Faktoren
  multipliziert. Eine fremde oder veränderte Annotation sowie eine Torerwartung über 8 sperren das Spiel
  (fail-closed). Die Referenz-Herkunft wird für angepasste Raten als `unavailable` markiert.
- ORIGINAL-Erfassung (`football_original._FIXTURE`) übernimmt die Annotation.
- Begründung am Kandidaten: „Ligastärke aus Europapokal-Duellen eingerechnet: Torerwartung Heim ×…, Gast ×…“.
- Unverändert: Ligaspiele, gleiche Wettbewerbe mit genug Europapokal-Spielen, Länderspiele, der Shadow-Hybrid
  (er nimmt die angepassten Legacy-Raten für die Torsumme), Kalibrierung, Sperren und Freigaberegeln. Die
  Europapokal-Prognose bleibt „in Prüfphase“ und wird nie Tipp.

## Messung im Betrieb und Rückweg

- Nach dem Release: Abstand Modell–Markt der Europapokal-Spiele im Tagesdokument messen
  (`output/check-20261104/scope_gap.py`, vorher 14,7 Punkte). Danach Trefferquote und Brier der abgerechneten
  Europapokal-Prognosen gegen die Basiswerte.
- Wird es schlechter: Release auf den Tag `modell-sicherung-2026-11-05`.
- Neu schätzen, wenn weitere Europapokal-Spieltage vorliegen: Daten exportieren und das Skript laufen lassen.
  Dafür braucht es keine neuen Abrufe, solange die Heimatliga-Daten reichen; für die laufende Saison ist ein
  Abruf nur mit Owner-OK möglich.
- Offen: Teams aus Ligen ohne Wert, zum Beispiel Slowenien, Armenien, Georgien, Bosnien, Lettland, Litauen,
  Gibraltar, Andorra, Albanien und Liga Portugal 2. Sie bekommen keine Europapokal-Prognose mehr.
