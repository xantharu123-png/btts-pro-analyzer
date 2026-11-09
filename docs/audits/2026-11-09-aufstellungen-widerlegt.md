# Startelf in der Torerwartung: vorab festgelegter Test widerlegt

Stand 09.11.2026. Owner-Auftrag „ja“ zur Vorbereitung und „Ja, abrufen“ für den Abruf, beides am 09.11.2026.

Am Code der App ändert sich nichts. Skripte, Hypothese und Protokoll liegen unter `output/aufstellungen-20261109/`.
Die Daten liegen auf dem Server unter `/var/tmp/bb_lineups/lineups.db`.

## Anlass

Bei 566 App-Tipps sah das Modell mindestens 5 Punkte mehr als die Einstiegsquote. Getroffen haben 47 %, das Modell
hatte 61 % versprochen, die Quote 50 % (`2026-11-09-fallenfilter-vorab.md`). Der Owner vermutet: Der Buchmacher
weiss in solchen Fällen etwas, das die App nicht weiss. Der wichtigste Kandidat dafür war, wer wirklich spielt.

## Vorab festgelegt

`output/aufstellungen-20261109/HYPOTHESE.md` wurde geschrieben, bevor eine Aufstellung abgerufen war.

- **Stammspieler:** die 11 Spieler, die in den letzten 10 Ligaspielen des Teams am häufigsten in der Startelf standen.
  Nötig sind mindestens 5 solche Spiele mit Aufstellung.
- **Merkmal m:** wie viele Stammspieler in der Startelf fehlen.
- **Variante:**
  - λ_Heim · exp(β · (m_Gast − m_Heim)) und λ_Gast · exp(β · (m_Heim − m_Gast)).
  - Grundlage ist die Produktionsbasis Formstärke.
  - β wird einmal per Poisson-Regression geschätzt, mit der Rate der Produktionsbasis als Offset.
- **Abbruchregel:** Auf den Lerndaten (Anstoss vor dem 01.07.2026) muss β − 1,96 · SE > 0 gelten.
- **Danach:** Stufe 1 hätte die vier Bedingungen des Formstärke-Tests geprüft, Stufe 2 den Vergleich gegen die
  Einstiegsquote.

## Daten

- **Abruf:** 486 Abrufe beim bestehenden Pro-Tarif von API-Football.
  - 2 Abrufe Probe.
  - 28 Saisonlisten, um Spiele aus football-data einer API-Nummer zuzuordnen.
  - 456 Abrufe `fixtures?ids=` mit je 20 Spielen.
- **Spiele:** 9107 Ligaspiele gespeichert, 9019 davon mit vollständiger Startelf beider Teams.
- **Zuordnung:** 4306 von 6626 football-data-Spielen liessen sich einer API-Nummer zuordnen. Unter 50 % lagen Liga 79
  (2. Bundesliga), 144 (Belgien), 197 (Griechenland) und 203 (Türkei).
- **Merkmal:** vorhanden für 7703 Spiele, davon 4527 Lernspiele.

## Ergebnis

| | Wert |
|---|---:|
| β je fehlendem Stammspieler | +0,0063 |
| Standardfehler | 0,0043 |
| Grenze β − 1,96 · SE | −0,0021 |

- **Die Abbruchregel greift, die Hypothese ist widerlegt.** Stufe 1 und 2 wurden wie festgelegt nicht gerechnet.
- Die Richtung stimmt, der Effekt ist aber winzig: etwa 0,6 % Torerwartung je fehlendem Stammspieler. Pro Spiel
  fehlen im Schnitt etwa 3 Stammspieler.
- Was die Startelf aussagt, steckt schon in den Toren und im xG der letzten Spiele. Sie erklärt nicht, warum der
  Buchmacher bei „zu guten“ Quoten recht behält.
- Varianten wie Minuten statt Startelf oder Gewichte je Position werden nicht nachgeschoben.

## Grenzen

- In 4 Ligen fehlt ein grosser Teil der Spiele, weil die Zuordnung nicht gelang.
- Das Merkmal zählt nur Köpfe und gewichtet nicht nach der Qualität der Spieler.
