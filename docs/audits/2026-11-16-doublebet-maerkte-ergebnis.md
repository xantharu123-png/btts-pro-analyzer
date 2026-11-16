# Doublebet: Ergebnis Stufe 1 (Märkte mit Trennung)

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in `docs/audits/2026-11-16-doublebet-maerkte-vorab.md`
(Commit `820db78`, gepusht vor der Auswertung).

## Ergebnis

**Kein Kandidat.** In keiner geprüften Gruppe gewinnt bei gleicher Quote die obere Hälfte der Modellchance
nachweislich öfter als die untere. Nach der Vorab-Regel gibt es damit keine Gruppe mit nachgewiesener Trennung, und
Stufe 2 entfällt.

| Gruppe | Wetten | Spiele | obere Hälfte gewonnen / Modell | untere Hälfte gewonnen / Modell | Unterschied | p | q |
|---|---:|---:|---|---|---:|---:|---:|
| Fussball / Teamtore | 1222 | 799 | 55,3 % / 65,7 % | 54,1 % / 50,9 % | +1,2 | 0,339 | 0,753 |
| Fussball / Ergebnis | 439 | 433 | 51,9 % / 48,4 % | 52,0 % / 39,2 % | −0,1 | 0,516 | 0,753 |
| Fussball / Ecken | 497 | 242 | 52,0 % / 62,5 % | 55,4 % / 53,2 % | −3,3 | 0,753 | 0,753 |

- **Nicht geprüft,** weil unter 200 Wetten mit gespeicherter Quote: Fussball / Doppelte Chance (197), Fussball /
  Gesamttore (61), Eishockey / Sieger (58), Tennis / Sieger (26), Fussball / Torbereich (13). E-Sport / Sieger und
  Fussball / Beide treffen hatten keine Wetten im Quotenbereich.

## Einordnung

- **Der Befund passt zum Gesamtergebnis:** Die Modellchance trennt in allen drei Gruppen deutlich, um 10 bis 15
  Punkte. Die Trefferquoten der beiden Hälften liegen aber fast gleich.
- **Nur Fussball ist prüfbar:** Für andere Sportarten fehlen gespeicherte Quoten in ausreichender Zahl. Dort ist
  keine Aussage möglich, weder dafür noch dagegen.
- **Doublebet ist unverändert.** Wie es weitergeht, entscheidet der Owner.
