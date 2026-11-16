# Länderspiel-Modell reparieren: Kandidat und Regel vorab

Stand 16.11.2026. Geschrieben **vor** jeder Rechnung mit dem Kandidaten. Owner „Beides“: sperren und reparieren.
Die Sperre ist live (`docs/audits/2026-11-16-kleinstaaten-sperre.md`).

## Ausgangslage

Die Vorab-Prüfung hat bestätigt, dass das Länderspiel-Modell dem Favoriten gegen Kleinstaaten zu wenige Tore gibt
(`docs/audits/2026-11-16-laenderspiele-kleinstaaten-ergebnis.md`):

| Gruppe | Spiele | „Favorit höchstens 2 Tore“ eingetroffen | Modell | Lücke |
|---|---:|---:|---:|---:|
| Favorit gegen Kleinstaat | 197 | 58,4 % | 78,1 % | −19,7 Punkte |
| Kontrolle ohne Kleinstaat | 426 | 75,8 % | 78,6 % | −2,8 Punkte |

**Vermutete Ursache:** Die Produktionsbasis rechnet die Torraten additiv aus Angriff und Abwehr. Ein additiver
Mittelwert dämpft extreme Paarungen. Ein Favorit, der sonst 2 Tore schiesst, bekommt gegen eine Abwehr, die 4 Tore
kassiert, kaum mehr.

## Kandidat (einer, fest)

`dixon_coles_hl365`: Das ist die vorhandene, im Plan vom 20.10.2026 vorab registrierte Variante (Dixon-Coles,
multiplikative Stärken, Halbwertszeit 365 Tage, `GOAL_MODEL_OPTIONS`). Sie gilt nur für Länderspiele
(`senior_national_pooled`), Vereinsspiele bleiben bei der Produktionsbasis. Es wird kein Parameter neu eingestellt und
keine weitere Variante gewählt. Andere Varianten werden höchstens als Information gezeigt und nie gewählt.

## Daten und Rechnung

- **Daten:** derselbe Pool wie in der Vorab-Prüfung, 1243 A-Länderspiele nach dem Filter der Produktion, abgerufen am
  16.11.2026.
- **Rechnung:** wie `challenge_engine._walk_forward_market_records`, kausal Tag für Tag, mit Kalibrierung nur aus
  früheren Tagen. Kandidat und Produktionsbasis laufen auf denselben Spielen.
- **Zeitraum A:** 01.01.2024 bis 03.10.2026, der Zeitraum, in dem der Fehler bestätigt wurde. Der Kandidat wird
  daran nicht eingestellt.
- **Zeitraum B:** 04.10.2026 bis zum letzten abgeschlossenen Spiel im Pool. Die Spiele dieses Zeitraums haben die
  Hypothese erzeugt, nie aber den Kandidaten. Sie sind die zeitlich getrennte Kontrolle.

## Kriterien

Alle müssen erfüllt sein.

1. **Kleinstaaten (A):** Die Lücke für „Favorit höchstens 2 Tore“ liegt zwischen −5 und +5 Punkten, und ihr
   95-%-Intervall enthält null (Bootstrap über Spiele, 10 000 Ziehungen, Startwert 20261116).
2. **Kontrolle (A):** Für „Heimteam höchstens 2 Tore“ in Spielen ohne Kleinstaat ist der Brier-Wert des Kandidaten
   höchstens 0,002 schlechter als der der Produktionsbasis.
3. **Gesamt (A):** Der mittlere Brier-Wert über alle Tor-Märkte und alle Länderspiele ist beim Kandidaten nicht
   schlechter als bei der Produktionsbasis.
4. **Getrennt (B):** Der mittlere Brier-Wert über alle Tor-Märkte ist beim Kandidaten höchstens 0,005 schlechter als
   bei der Produktionsbasis. Zeitraum B hat nur rund 75 Spiele; das Kriterium soll einen klaren Rückschritt ausschliessen.

## Entscheidung

- **Alle Kriterien erfüllt:** Ich schlage vor, Länderspiele auf den Kandidaten umzustellen und die Sperre im selben
  Release aufzuheben. Das ist ein eigener Owner-Entscheid mit eigenem Release; die Umstellung braucht eigene
  Versionsangaben.
- **Ein Kriterium verfehlt:** Keine Umstellung. Die Sperre bleibt, bis der Owner entscheidet. Ein neuer Kandidat
  braucht eine neue Vorab-Regel.
- Diese Regeln werden nach dem Blick auf die Zahlen nicht geändert.
