# Club-Heimvorteil – vorab festgelegter Vergleich, 20. November 2026

**Entscheidung heute: kein Eingriff in die App.** Im Audit vom 16.11. lag die geschätzte
Heimsiegchance in 14 der 14 verglichenen Ligen niedriger als die margenbereinigte
Marktchance. Das ist kein Nachweis gegen tatsächliche Ergebnisse. Im Grundmodell
mischt sich die nach Spielort gebildete Saisonstärke mit jüngster Form aus allen
Spielorten. Wir prüfen genau eine Hypothese: Ein kleiner, aus früheren tatsächlichen
Heimspielen derselben Liga bestimmter Heimanteil verbessert die Verteilung.

## Was verglichen wird

- Nur reguläre Ligaspiele in England (39), Deutschland (78), Italien (135),
  Spanien (140) und Frankreich (61). Keine Nationalteams, Cups, Relegationsduelle,
  neutralen oder ungeklärten Spielorte. Keine Preise, Wettgewinne oder Fremdmodelle.
- Ausgangspunkt ist ein vor Anpfiff erfasstes, identitäts- und versionsgeprüftes
  ORIGINAL der aktiven Formstärke-Basis mit seiner kalibrierten gemeinsamen
  Torverteilung. Roh-Erwartungswerte, neu geladene Spielpläne und spätere Modelle
  sind kein Ersatz. Bei mehreren Belegen zählt der früheste geeignete vor Spielbeginn,
  nicht derjenige mit dem besten Ergebnis. Konflikte zum gleichen Zeitpunkt sind Lücken.
- Ein echter zeitgebundener Heimspielort-Beleg muss zum selben Spiel, Heimteam
  und Anpfiff passen. Für die Vorgeschichte zählen nur vorher bekannte reguläre
  Endstände dieser Liga aus der laufenden bzw. vorherigen Saison; weder Spiele
  desselben UTC-Tags noch erst nach Modellschluss bekannt gewordene Resultate.
  Mindestens 60 belegte unterschiedliche Partien, beide Torsummen positiv.
- Genau eine Änderung: `d = 0,125 × ln(Summe Heimtore / Summe Gasttore)`.
  Für ein Ergebnis (h,a) die **kalibrierte Originalzelle** mit
  `exp(d × (h−a))` multiplizieren und über alle Zellen neu normieren.
  Sämtliche Tormärkte aus derselben Verteilung ableiten. Eckbälle, Karten und
  die Veröffentlichung bleiben unverändert. Keine Suche nach einem besseren Faktor.

## Getrennte Zeitfenster

**Entwicklung, nur zur Fallzahlplanung:** Vorauswahl derselben fünf Ligen, vorhandene
Ergebnisdateien; Aufwärmphase 2023/24, Entwicklung 2024/25. Von 1.752 Spielen hatten
1.620 eine rekonstruierbare Rohmodell-Paarung (37 belegte Montag–Sonntag-Wochen).
Keines der CSV-Paare belegt zugleich veröffentlichtes kalibriertes ORIGINAL und
vorab bestätigten tatsächlichen Heimspielort. Es wurde kein Wirksamkeitswert
aus diesem Ersatzbestand übernommen.

Streuungsplanung mit Gewichten je Partie und Wochenclustern: äquivalente SD
0,02509. Für einen Unterschied von 0,002 im **unskalierten dreiteiligen**
Brier-Score, zweiseitiges Niveau 5 %, 80 % Zielstärke, ergibt die Normalnäherung
1.236 Paare. Puffer für echte Daten: **mindestens 1.600 zulässige Spielpaare und
40 belegte Wochen**. Das ist keine zugesicherte Teststärke. Reproduktion:
`python -B scripts/club_home_power_pilot.py --csv-dir PFAD_ZU_DEN_ERGEBNISDATEIEN`.
Das Skript öffnet nur die zehn festgelegten Dateien, benutzt keine Quoten und
gibt Streuung, Fallzahl sowie Quellen-Prüfsummen aus, keinen Wirksamkeitsbefund.

**Unberührter Testblock:** Anpfiff 01.01.2027 00:00 UTC bis ausschliesslich
01.01.2028 00:00 UTC. Keine Ergebnisse dieses Blocks wurden für diesen Plan gelesen.
Fixierter Auswertungsstichtag: 15.01.2028 00:00 UTC; nur bis dahin bekannte
offizielle Resultate. Bis dahin nur Fallzahlen und Datenlücken prüfen. Weder
vorzeitig öffnen noch die Frist verlängern, wenn die Fallzahl nicht reicht.
Ändert sich die Basis, getrennt zählen, keine stillschweigende Gleichsetzung.
Fehlt ein Herkunftsbeleg: als Ausschluss zählen, nicht rückwirkend ergänzen.

## Einmalige Entscheidung

1. Pro Spiel die Fehlerquadrate der drei Ergebniswahrscheinlichkeiten summieren,
   Differenz Kandidat minus ORIGINAL. Genau ein gleich gewichtetes Paar pro Spiel.
   Anzahl zulässig/ausgeschlossen und Gründe, je Liga und insgesamt, berichten.
2. Primär: mittlere gepaarte Differenz und 95-%-Intervall. Wochen über alle Ligen
   gemeinsam (Montag–Sonntag UTC); clusterrobuster Standardfehler
   `sqrt(G/(G−1) × sum_b(sum_i_in_b(d_i−mean(d)))²)/N`, t-Quantil mit G−1
   Freiheitsgraden. Bei null Streuung, fehlenden Belegen oder zu kleinem Bestand
   keine positive Entscheidung. Zeitliche Abhängigkeit über Wochen hinweg als
   Sensitivität mit vorab fixiertem Paaren aufeinanderfolgender Kalenderwochen
   berichten; widerspricht das der Überlegenheit, keine Aktivierung.
3. Zusätzlich Kalibrierung Heimsieg (mittlere Chance minus beobachtete Häufigkeit)
   für beide Modelle und Auswirkung auf **dieselben tatsächlich archivierten
   Hauptmärkte**: gepaarte binäre Brier-Differenz je Spiel mit unterstütztem Tormarkt
   samt Intervall; Anzahl, Abdeckung, Ligen und Marktmischung getrennt nennen.
   Keine Ersetzung fehlender Hauptkarten, keine neu erfundene Gewinnerauswahl.
4. Nur wenn Testmenge und -dauer erreicht und das primäre Intervall vollständig
   unter null liegt, gibt es einen positiven Modellbefund. Nur bei ebenfalls belegtem
   Nutzen für die Hauptmärkte (Intervall vollständig unter null) kommt ein separater
   Änderungsvorschlag infrage. Softwaretests, Einzelspiele, bessere Trefferquote
   bei anderer Abdeckung oder blosse Marktnähe sind keine Freigabe.
