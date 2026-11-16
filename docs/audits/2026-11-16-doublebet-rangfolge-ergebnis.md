# Doublebet: Ergebnis Rangfolge bei gleicher Quote

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in `docs/audits/2026-11-16-doublebet-rangfolge-vorab.md`
(Commit `59ac336`, gepusht vor der Auswertung).

## Ergebnis

**D2 nicht bestätigt.** Bei gleicher Quote gewinnen die Wetten, die das Modell höher einstuft, nicht öfter als die
tiefer eingestuften.

Quoten 1,40 bis 1,79 und 2,21 bis 3,00, früheste gespeicherte Quote, ohne Doublebet-Tipps. Je Quotenstufe von 0,10
geteilt am Median der Modellchance:

| | Wetten | gewonnen | Modell im Schnitt |
|---|---:|---:|---:|
| obere Hälfte | 1028 | 55,2 % | 63,8 % |
| untere Hälfte | 1033 | 56,6 % | 49,6 % |

- **Kennzahl:** Unterschied obere minus untere Hälfte −1,5 Punkte, 95-%-Intervall −6,3 bis +3,3 (Bootstrap über 1008
  Spiele). Die Regel verlangt eine untere Grenze über null bei mindestens 400 Wetten.
- **Was die Zahl heisst:** Das Modell trennt die beiden Hälften um 14 Punkte. Im Ergebnis gewinnen beide gleich oft.
- **Information je Quotenbereich:** 1,40 bis 1,79 −2,1 Punkte (1586 Wetten), 2,21 bis 3,00 +0,5 Punkte (475 Wetten).

## Einordnung

- **Erster Blick und Prüfung:** Im Doublebet-Band 1,80 bis 2,20 hatte die Gruppe ab 65 % mit 57 % gegenüber 43 %
  besser ausgesehen, allerdings bei nur 54 Wetten. Auf mehr als 2000 noch nicht angesehenen Wetten zeigt sich dieser
  Vorteil nicht.
- **Folge für Doublebet:** Das Modell erkennt in unseren Daten bei gleicher Quote die wahrscheinlichere Wette nicht
  besser als der Zufall. Die Quote enthält offenbar schon, was Form, Historie und Statistik im Modell beitragen.
  Doublebet wählt damit im Ergebnis wie eine zufällige Wahl unter Wetten um 2,0. Zu erwarten ist knapp 50 %, abzüglich
  der Buchmachermarge.
- **Was die Prüfung nicht sagt:** Das Modell ist nicht wertlos. Ausserhalb der Rangfolge bei gleicher Quote trifft es
  ungefähr so oft, wie es sagt. Bei Vereinsspielen sind es zum Beispiel 58,6 % bei 58,7 % Erwartung. Es fügt dem Preis
  aber keine trennende Information hinzu.

## Folgen

- **Am Doublebet ist nichts geändert.** Ob es so bleibt, umgebaut oder anders beschrieben wird, entscheidet der Owner.
- **Wie geplant** läuft dieselbe Regel in rund 5 Wochen erneut auf neuen Daten im Band 1,80 bis 2,20, mit Prognosen ab
  dem 16.11.2026.
