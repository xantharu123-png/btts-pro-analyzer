# Länderspiel-Modell reparieren: Ergebnis Kandidat 3

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in
`docs/audits/2026-11-16-laenderspiele-reparatur-kandidat3-vorab.md` (Commit `a184af0`, gepusht vor der Rechnung).

## Ergebnis

**Nicht erfüllt, Kriterium K1.** Kandidat 3 rechnet die Torerwartung multiplikativ statt additiv. Er verkleinert die
Kleinstaaten-Lücke nur von −19,7 auf −16,3 Punkte, und das Intervall enthält null nicht. Nach der Vorab-Regel gibt es
keine Umstellung, die Sperre bleibt.

| Kriterium | Produktion | Kandidat 3 | erfüllt |
|---|---:|---:|---|
| K0 Abdeckung der Kleinstaaten-Spiele (A) | – | 197 von 197 (100 %) | ja |
| K1 Lücke „Favorit höchstens 2 Tore“ (A, n 197) | −19,7 (−26,7 bis −13,1) | −16,3 (−23,3 bis −9,6) | nein |
| K2 Kontrolle ohne Kleinstaat, Brier (A, n 426) | 0,1731 | 0,1701 | ja |
| K3 alle Tor-Märkte, Brier (A, 32 476 Paare) | 0,2002 | 0,1970 | ja |
| K4 alle Tor-Märkte, Brier (B, 2806 Paare, 61 Spiele) | 0,1901 | 0,1876 | ja |

Bei K1 kam „Favorit höchstens 2 Tore“ zu 58,4 % vor. Die Produktion rechnete mit 78,1 %, Kandidat 3 mit 74,7 %.

## Beobachtung

- **Insgesamt besser:** Kandidat 3 ist auf allen drei Brier-Kriterien besser als die Produktion, auch im getrennten
  Zeitraum B. Die multiplikative Regel beschreibt Länderspiele also insgesamt genauer.
- **Bei Kleinstaaten zu wenig:** Die mittlere Modellchance bewegt sich nur um 3,4 Punkte. Mögliche Gründe:
  - Die tägliche Kalibrierung ist auf allen Länderspielen gefittet und zieht extreme Werte zurück.
  - Die Abwehr der Kleinstaaten wird mit Gewicht 6 zum Gesamtschnitt geschrumpft.
  - Die Torquoten sind nicht nach Gegnerstärke bereinigt.
  Das ist nicht geprüft. Es sind Hinweise für einen späteren Kandidaten.

## Folgen

- **Keine Umstellung,** die Kleinstaaten-Sperre bleibt live (`fb38329`).
- **Owner-Entscheid möglich:** Kandidat 3 trotz verfehltem K1 als allgemeine Verbesserung des Länderspiel-Modells
  übernehmen. Das wäre eine bewusste Abweichung von der Vorab-Regel, wie am 07.11.2026 bei der Formstärke. Die Sperre
  bliebe dann trotzdem, weil die Kleinstaaten-Lücke offen ist.
- Das Länderspielfenster endet am 18.11.2026, das nächste beginnt im März 2027. Für einen gegnerbereinigten Kandidaten
  ist bis dahin Zeit. Er braucht eine eigene Vorab-Regel.
