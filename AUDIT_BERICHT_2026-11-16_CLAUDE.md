# BetBoy – Gesamtaudit 16. November 2026 (Claude Fable 5.2)

Perspektiven: Modellwahrscheinlichkeit Fussball, Modelle der anderen Sportarten, Statistik, Mathematik und
Wahrscheinlichkeitsrechnung, Logik, Wettprofi und Buchmacher-Tricks, Entwicklung und Betrieb, UX. Dazu drei
Nachprüfungen für Lücken: RisikoBet, das erste volle Liga-Wochenende mit Doppel-Scan, Live und Platzverweis.

Geprüft: `origin/main` @ `c591afe`. Die Produktion läuft mit `fb38329`; danach kamen nur Doku-Merges, der Code ist
gleich. Vorheriges Audit: `AUDIT_BERICHT_2026-10-25_CLAUDE.md`.

Methode:

- **23 Prüfläufe:** acht Rollen lasen Code und Zahlen. Je Rolle schlug ein zweiter Prüfer jeden Befund im Code nach,
  mit dem Auftrag, ihn zu widerlegen. Ein Kritiker suchte danach Lücken; die drei wichtigsten wurden nachgeprüft und
  ebenfalls gegengeprüft.
- **Zahlen:** ein frischer Auszug vom Server vom 16.11.2026, nur gelesen und nur als Summen: 12 921 abgerechnete
  Wetten seit 06.09.2026, davon 6 695 mit gespeicherter Quote. Die Quote ist die früheste gespeicherte Quote eines
  Buchmachers, weder Bestpreis noch Mittelwert.
- **Eigene Nachprüfung:** Jede Code-Stelle der hohen Befunde habe ich selbst nachgelesen. Auf dem Server habe ich nur
  geprüft, welche Einstellungen gesetzt sind (Namen, keine Werte).
- **Grenzen:** Das Audit hat nichts geändert, keine API abgerufen und keine Tests in voller Breite laufen lassen. Der
  Fallenfilter und die Formstärke-Messung sind vorab festgelegt (Auswertung 30.11.2026) und wurden nicht angesehen.
  Layout-Aussagen stammen aus Code und CSS, nicht vom Gerät.

Ergebnis: 142 Befunde, 110 von den Prüfern und 32 von der Gegenprüfung ergänzt. Nach der Gegenprüfung sind 0
kritisch, 13 hoch, 77 mittel und 52 niedrig. Die Gegenprüfung hat keinen Befund widerlegt, 65 bestätigt und 45 nur
teilweise bestätigt; bei 56 hat sie die Schwere gesenkt, darunter bei 29 der 35 als kritisch oder hoch gemeldeten.
Den Befund LV-G1 habe ich nach dem Servercheck selbst auf hoch gesetzt (H8). Alle Befunde im Wortlaut, mit Beleg und
Gegenprüfung, liegen lokal unter `C:/Projekt/BetBoy/output/audit-20261116/` (`anhang_befunde.md`, `rohbefunde.json`,
Rechenskripte der Prüfer unter `scratch/`). Sie stehen nicht im Repo, weil einzelne Belege auf alte Schlüssel in der
Git-Historie zeigen.

---

## 0. Kurzurteil

**Die Kernfrage: Ist BetBoy schlauer als der Buchmacher?** Heute nicht. Das Modell trifft im Fussball so oft, wie es
sagt (61,6 % bei 61,7 %, 11 493 Wetten). Zur gespeicherten Quote verlieren die Wetten trotzdem 7,7 % vom Einsatz,
und zwar in jeder Quotenstufe und in jeder Stufe des Modell-Erwartungswerts. Wo das Modell mehr sieht als die Quote,
irrt das Modell: Dort trifft es 49,0 % statt der versprochenen 60,2 % (1 779 Wetten). Die App fällt auf keinen
Werbetrick herein, sie bezahlt aber überall die normale Marge.

**Modell Fussball:** Im Mittel stimmt die Chance, an den Rändern und nach der Auswahl nicht. Drei Ursachen stehen im
Code: ein zu klein gerechneter Heimvorteil (Heimsieg rund 2 Punkte zu tief), Kalibrierkarten mit flachen Enden und
die additive Paarung, die im Europapokal und in Länderspielen ohne Korrektur läuft. Dazu kommt ein Rauschen von
geschätzt 6 bis 7 Punkten je Prognose. Verlässlich als Niveau sind Teamtore, Doppelte Chance und Gesamttore. Vorsicht
gilt bei 1X2, Tor-Bereichen, Ecken und allem unter 25 % Modellchance.

**Andere Sportarten:** Unter 60 % Modellchance treffen Tennis, E-Sport, Eishockey und Basketball zusammen wie eine
Münze (283 von 568, versprochen waren 54,9 %). Nur Tennis hat dafür eine Grenze. Das E-Sport-Modell rechnet Bo1, Bo3
und Bo5 gleich. Der Montags-Wächter für die Tennis-Kalibrierung misst in Produktion nichts.

**Statistik:** Die Freigabestufe `RELEASED` beweist «besser als die Liga-Grundrate», nicht «besser als der Markt».
Neben der Quote erklärt das Modell das Ergebnis nicht (Gewicht des Modells −0,03, der Quote 0,96, Standardfehler je
0,07). Stark ist die Disziplin der Vorab-Prüfungen im November: Sie liefern ehrliche «nicht bestätigt» und haben den
Kleinstaaten-Fehler gefunden. Schwach sind die Messwege: fünf verschiedene «Einstiegsquoten», Skripte ausserhalb von
Git, keine Bündelung nach Spiel, und die Shadow-Prüfstufe von 1000 Tipps erkennt einen Vorteil von 2 % nur in einem
von fünf Fällen.

**Mathematik:** Die Formeln sind richtig. Tormatrix, Über/Unter, Doppelte Chance, Bereiche, Kombis, Kelly und No-Vig
stimmen in der Nachrechnung auf 16 Stellen. Das Problem liegt in den Versprechen: Das 15K-Ziel ist mit den eigenen
Einsatzregeln nicht erreichbar (die Seite nennt 70 Siege in Folge, nötig wären 200 bis 680), und das Doublebet-Ziel
«+CHF 150» verlangt zwei bis drei Siege in Folge mit vollem Wiedereinsatz.

**Logik:** Der Weg von der Modellzeile zum Tipp und zur Abrechnung ist sorgfältig gebaut. Ein falsch gebuchtes
Ergebnis wurde nicht gefunden. Schwachstellen: Doublebet füllt immer auf drei Wetten auf, die Kontextprüfung reicht
nur für rund 80 Spiele je Tag, und Spiele mit Verlängerung bleiben für immer offen.

**Wettprofi:** BetBoy sagt Ergebnisse ehrlich voraus, schützt den Geldbeutel aber nicht vor dem Preis. 78 % der
Fussball-Auswahlen liegen in Nebenmärkten. Doublebet und 15K wählen dort, wo das Modell am weitesten über dem Markt
liegt, und das ist die gemessene Verlustzone. 15K vervielfacht die Marge über Kombis. Von elf klassischen
Buchmacher-Tricks schützt die App vor einem, lenkt in zwei hinein und sagt zu acht nichts.

**Entwicklung und Betrieb:** Das System läuft stabil, solange jemand hinsieht. Es gibt einen einzigen Nachtlauf, der
erst im letzten Schritt veröffentlicht, und davor laufen die Suche für morgen und drei Nebenschritte. Alarme erreichen
keinen Menschen. Es gibt kein Backup und keinen reproduzierbaren Neuaufbau. Der Kundenzugang ist nicht erzwungen.

**UX:** Die App zeigt gross, was das Modell glaubt, und nirgends, was daraus geworden ist. Forschungsmodelle sehen auf
der Doublebet-Karte aus wie das Fussballmodell. Zwischen Mitternacht und dem Nachtlauf ist die App ohne Erklärung
leer. Gut sind die Sprache ohne Garantien, der Rechtsfooter mit echten Hilfestellen und das feste Tagesbudget.

**Gesamtnote:** Rechnung und Integrität sind sehr gut, die Ehrlichkeit der Prüfkultur ist überdurchschnittlich. Der
Betrieb hängt an einem Lauf und an einer Person. Ein Wettvorteil ist weiterhin nicht belegt, und zwei Flächen
(Doublebet, 15K) wählen systematisch dort aus, wo das Modell danebenliegt.

---

## 1. Stand gegenüber dem Audit vom 25.10.2026

| Massnahme vom 25.10. | Stand 16.11. |
|---|---|
| 1 Lader je Zeile, 2 Shadow, 3 Betrieb, 4 Preisregel in der CI | erledigt (25.–28.10.) |
| 5 Owner-Entscheide | teils offen: 15K rechnet weiter in Euro, «Ziel +CHF 150» steht noch, Backup bleibt aus. Entschieden sind Doublebet-Pool, Quotenband und Kontextalter |
| 6 Evidenz ehrlich zeigen | offen: Die Evidenzstufe wird berechnet, aber nirgends gezeigt. Der Text «Alle … Gates bestanden» steht unverändert (UX-3, WE-10) |
| 7 UX-Politur | teils: Zahlen, Datum, Währung und Begriffe sind je Fläche noch anders (UX-9) |
| 8 Hybrid vor Aktivierung | offen, aber nicht live; Messung am 30.11. |
| 9 Persistenz | teils: Plattenwächter erledigt; Index, WAL und Aufbewahrung der Evidenz-Datenbank offen (DV-10) |
| 10 Strukturell | offen: Marktgate aus, Tennis-Kalibrierung, Modulgrösse und Zyklen |

Seit dem 25.10. neu und geprüft gut: Formstärke als Produktionsbasis, Ligastärke im Europapokal (1X2-Log-Loss 1,031
auf 0,939), Tennis-Grenze ab 60 %, Kleinstaaten-Sperre, Nachtspiel- und NHL-Fenster, Abrechnung im Quotenlauf.

---

## 2. Frische Zahlen vom Server (16.11.2026, nur gelesen)

Umfang: 94 713 Prognosezeilen, 12 921 abgerechnete Wetten (eine Wette je Spiel, Markt und Auswahl), 6 695 mit Quote,
Anstoss 06.09. bis 15.11.2026. Im Fussball liegen im Mittel 7,3 Wetten auf einem Spiel; die Spannen unten rechnen
ohne Bündelung nach Spiel und sind deshalb zu eng (realistisch etwa das 1,5- bis 2-Fache).

| Sportart (alle Wetten) | Wetten | gewonnen | Modell |
|---|---:|---:|---:|
| Fussball | 11 493 | 61,6 % | 61,7 % |
| E-Sport | 561 | 59,0 % | 62,8 % |
| Tennis | 403 | 61,0 % | 62,3 % |
| Eishockey, Basketball | 464 | nicht aussagekräftig: beide Seiten gespeichert, ergibt immer 50 % | |

| Quotenstufe (mit Quote) | Wetten | gewonnen | Modell | nötig (1/Quote) | Rendite |
|---|---:|---:|---:|---:|---:|
| unter 1,20 (von der App zurückgehalten) | 1 915 | 86,4 % | 81,4 % | 91,3 % | −5,4 % ±1,7 |
| 1,20–1,39 | 1 544 | 71,5 % | 70,6 % | 77,8 % | −8,1 % ±2,9 |
| 1,40–1,59 | 959 | 64,4 % | 63,2 % | 67,5 % | −4,5 % ±4,5 |
| 1,60–1,79 | 623 | 58,1 % | 57,3 % | 59,3 % | −2,0 % ±6,6 |
| 1,80–1,99 | 415 | 47,2 % | 53,6 % | 53,1 % | −11,0 % ±9,1 |
| 2,00–2,49 | 508 | 40,0 % | 48,1 % | 45,6 % | −12,3 % ±9,4 |
| 2,50–2,99 | 203 | 36,0 % | 40,4 % | 36,7 % | −1,3 % ±18,2 |
| 3,00–4,99 | 363 | 21,8 % | 30,6 % | 27,5 % | −20,1 % ±15,8 |
| ab 5,00 | 165 | 10,3 % | 20,3 % | 15,2 % | −31,2 % ±32,1 |
| **alle** | **6 695** | **64,3 %** | **64,3 %** | **69,0 %** | **−7,7 % ±2,0** |

| Modell-Erwartungswert (Modellchance × Quote − 1) | Wetten | gewonnen | Modell | Rendite |
|---|---:|---:|---:|---:|
| unter −20 % | 828 | 62,4 % | 49,4 % | −8,2 % |
| −20 bis −10 % | 1 781 | 72,5 % | 66,1 % | −6,4 % |
| −10 bis 0 % | 2 307 | 70,5 % | 71,4 % | −7,3 % |
| 0 bis +10 % | 876 | 57,3 % | 65,0 % | −9,6 % |
| +10 bis +20 % | 385 | 50,1 % | 61,1 % | −8,0 % |
| +20 bis +40 % | 316 | 40,5 % | 54,1 % | −5,8 % |
| über +40 % | 202 | 24,3 % | 47,1 % | −17,1 % |

Lesart: Je mehr «Wert» das Modell sieht, desto weiter liegt es über dem Ergebnis. Die Rendite hängt an der Quote,
nicht am Modell.

| Fussball je Marktart (mit Quote) | Wetten | Rendite |
|---|---:|---:|
| Teamtore | 3 638 | −8,1 % ±2,4 |
| Ecken | 1 036 | −11,5 % ±4,8 |
| Ergebnis 1X2 | 695 | +1,7 % ±10,1 |
| Doppelte Chance | 691 | −8,3 % ±5,2 |
| Gesamttore | 347 | −7,9 % ±7,3 |

Kombis aus Ergebnis und Toren (1 534 Wetten) und Tor-Bereiche (1 439) haben praktisch keine gespeicherte Quote. Das
sind 26 % aller Fussballwetten ohne jeden Geldbeleg (ST-3). Die Null bei 1X2 ist kein Vorsprung: erste Hälfte des
Zeitraums +15,6 %, zweite Hälfte −7,0 % (Bericht vom 12.11.).

| App-Fläche (Archiv der Pipeline) | Wetten | gewonnen | Modell | Rendite mit Quote |
|---|---:|---:|---:|---:|
| Wettfinder, Standardliste | 5 378 | 58,1 % | 60,1 % | −7,5 % ±2,8 (3 666 Wetten) |
| Tagesauswahl (bis 02.11. «3 a day», danach Doublebet) | 50 | 60,0 % | 74,5 % | zu wenige |

Die Tagesauswahl mischt zwei Regeln. Ohne die 20 Doublebet-Tipps (6 gewonnen) bleiben 24 von 30 bei 80,2 % Modell:
Die alte Regel ab 70 % war stimmig. Für 15K-Tickets und RisikoBet gibt es keine Zeile in der Evidenz (ST-G1, RB-1).

---

## 3. Befunde nach Schwere

### HOCH

**H1 – Die Auswahl nach höchster Modellchance wählt die Überschätzungen** (MF-4, ST-2, MT-G1, MT-1, WE-2, LO-G3)

- **Beleg:** `daily3_selection.py:264` wählt im festen Quotenband die höchste Summe der Modellchancen;
  `challenge_15k.py:5426` nimmt je Spiel den Markt mit der höchsten Modellchance. Im Band 1,80–2,20 trafen Zeilen
  mit 55 bis 65 % Modellchance 44,8 % (192 Zeilen), ab 65 % trafen 57,4 % bei 70,4 % Modell (54 Zeilen). Zusammen mit
  den 20 echten Doublebet-Tipps (6 gewonnen) sind es 37 von 74, also 50 %. Die Rangfolge-Prüfung vom 16.11. fand
  keine Trennung (−1,5 Punkte, 2 061 Wetten); die Form der letzten zehn Spiele ebenfalls nicht (−3,0 Punkte).
- **Ursache:** Bei gleicher Quote unterscheiden sich die Modellchancen vor allem durch Rauschen. In der Simulation mit
  den echten Schätzfenstern (12 Heim- oder Auswärtsspiele, 6 Formspiele) liegt jede Prognose 6 bis 7 Punkte neben der
  Wahrheit. Wer die höchste nimmt, nimmt die grösste Überschätzung: Modell 56 %, wahr 49 %. Eine Zufallswahl aus
  derselben Menge hat keinen Abstand.
- **Wirkung:** Die Zahl auf der Doublebet-Karte liegt im Band rund 14 Punkte über dem Ergebnis. Die Tipps treffen etwa
  so oft, wie die Quote sagt, und kosten die Marge.
- **Was hilft:** Das Modell muss genauer werden, sonst gibt es bei gleicher Quote nichts zu finden. Die Kandidaten
  stehen unter MITTEL: Heimvorteil (MF-2), Kalibrier-Enden (MF-1), additive Paarung (MF-3), längere zeitgewichtete
  Fenster und die Hybrid-Messung am 30.11. Jeder Kandidat braucht eine Vorab-Regel und eine getrennte Prüfung.

**H2 – Kein Vorsprung gegen den Markt; `RELEASED` beweist nur den Vorsprung vor der Liga-Grundrate** (ST-1, WE-1)

- **Beleg:** `challenge_engine.py:2631` vergleicht mit der Grundrate des Marktes in der Liga, Schwelle 2 % besserer
  Brier-Wert (`:2519`). Der Marktvergleich ist standardmässig aus (`market_release_gate.py:38`). Zahlen siehe
  Abschnitt 2. Veröffentlichte Wettfinder-Auswahlen: −7,5 % (3 666 Wetten, 1 028 Spiele).
- **Einordnung:** Nicht neu (S1 vom 25.10., Analyse vom 12.11.) und kein Defekt. «Modell vor Preis» und der Verzicht
  auf die Quotenanzeige sind Owner-Entscheide; das ist ihr Preis. Die App verspricht auch nirgends einen Vorsprung.
- **Wirkung:** Wer alle Tipps der Standardliste ab 70 % spielt, trifft rund 72 %, bräuchte bei Quote 1,28 aber 78 %
  (ST-11). Die hohe Trefferquote fühlt sich nach Erfolg an und kostet 6 bis 8 Rappen je Franken.

**H3 – 15K: Die Ticketregel landet in der Verlustzone, die Kombi vervielfacht die Marge, niemand misst das Ticket**
(LO-G1, ST-G1, MT-3, MT-2, MT-7, WE-4)

- **Beleg:** Ein Leg braucht positiven Modell-Erwartungswert (`challenge_engine.py:4554`, Grenze 3 %,
  `betting_math.py:15`), das Ticket ebenfalls (`:4644`). Genau diese Wetten verlieren gemessen 9,4 % (1 779 Wetten),
  weil das Modell dort 11 Punkte zu hoch liegt. Zwei Legs ergeben rechnerisch rund −18 %, drei rund −25 %.
- **Ziel:** Erlaubt sind Viertel-Kelly und höchstens 5 % Einsatz (`challenge_engine.py:4802`). Die Seite rechnet 70
  Siege in Folge vor; mit den wirklich erlaubten Einsätzen wären es 200 bis 680 (MT-2).
- **Messlücke:** Keine Auswertung kennt die 15K-Fläche. Ob Tickets schlechter laufen als Einzelwetten, kann heute
  niemand belegen.
- **Was hilft:** Zuerst zählen (Tickets seit 03.11.: Anzahl, Treffer, Rendite). Danach Owner-Entscheid zur
  Ticketregel; die vorhandene Kappung des Modell-Vorsprungs (8 Punkte, heute aus) wäre eine abschaltbare Option.

**H4 – Doublebet: Ziel und gezeigte Zahl stehen gegen die eigene Messung** (UX-1, MT-4, WE-5)

- **Beleg:** `daily3_ui.py:281` nennt «Ziel +CHF 150, nicht garantiert». Der Satz «Ein Vorsprung des Modells
  gegenüber dem Markt ist nicht belegt» steht im Popover (`:284`). Die Modellzahl ist das grösste Element der Karte.
- **Rechnung:** +CHF 150 aus CHF 50 verlangt drei Treffer zu Quote 2,00 (12,5 % bei 50 % Trefferchance) oder zwei
  Treffer mit vollem Wiedereinsatz (25 %). Gemessen: siehe H1.
- **Einordnung:** Der Punkt ist seit dem 25.10. als Owner-Frage offen (U6). Die Auswahlregel ist ein Owner-Entscheid;
  der Befund betrifft nur, was die Seite daneben verspricht.

**H5 – Der Nachtlauf macht «heute» nicht zuerst fertig** (DV-3, WO-1, WO-2)

- **Beleg:** Ein Timer um 03:35, Abbruch nach 60 Minuten, kein Neustart
  (`deploy/systemd/betboy-wettfinder.timer:5`, `.service:21`). Reihenfolge in `wettfinder_automation.py`: Suche für
  morgen (`:4279`), Tennis (`:4348`), RisikoBet-Ergebnisse (`:4968`), dann erst Evidenz von heute (`:5122`), ein
  reiner Hintergrundschritt (`:5153`) und als allerletztes die Veröffentlichung (`:5257`). Am 03.11. brauchten die
  Schritte vor der Veröffentlichung 24 von 33 Minuten.
- **Wirkung:** Ein langsamer Scan von morgen kostet den ganzen heutigen Tag: keine Liste, kein Doublebet, kein 15K,
  keine Evidenz. Für Samstag, 21.11. (erstes volles Liga-Wochenende mit Doppel-Scan) ergibt die Rechnung rund 45
  Minuten bei normalem Anbieter, also etwa 15 Minuten Reserve (Schätzung, keine Messung). Der Reihenfolge-Test kennt
  die Folgetag-Schritte nicht und ist seit längerem rot.
- **Was hilft:** Heute fertig rechnen und veröffentlichen, erst danach morgen suchen und ein zweites Mal
  veröffentlichen. Kleinster erster Schritt: den Hintergrundschritt hinter die Veröffentlichung legen und vor der
  Suche für morgen die verstrichene Zeit prüfen. Am Freitag, 20.11. die Stufenzeiten lesen: Dieser Lauf sucht den
  vollen Samstag schon als «morgen».

**H6 – Ein endgültig gescheiterter Abruf stuft den ganzen Fussballtag herab, teils ohne Alarm** (WO-G1)

- **Beleg:** Jede Anbietermeldung zählt als Betriebsfehler (`challenge_15k.py:1781-1789`); der Wetterabruf hat keine
  Wiederholung (`:1537`, `:1565`). Folge: `wettfinder_automation.py:1274` setzt `degraded`, damit entfallen
  Fussball-Top-Tipps, 15K-Pool, die Suche für morgen (`:4275`) und das Nachrücken (`:5421`). In einem Nachlauf ohne
  vollständigen Kontext bleibt der Status stehen, der Zähler steht aber auf 0 (`:1932-1940`): Der Lauf endet dann mit
  Exit 0 und ohne Alarm. Der Prüfer hat das mit der echten Funktion nachgestellt.
- **Was hilft:** Fehler je Spiel statt je Tag werten (fail-closed je Spiel bleibt), Status und Zähler koppeln, den
  Wetterabruf einmal wiederholen. Jede Änderung zuerst als roter Test.

**H7 – Alarme erreichen keinen Menschen** (DV-1, DV-G1, DV-2)

- **Beleg:** Ohne Token schreibt der Helfer nur ins Journal (`scripts/betboy_alert.py:124-127`). Am 16.11. auf dem
  Server geprüft: `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` sind nicht gesetzt. Seit dem 25.10. gab es mindestens 14
  Alarme, keiner kam als Nachricht an. Ein Ausfall der App selbst löst nie einen Alarm aus, und der Nachtlauf endet
  grün, auch wenn die App sein Dokument verwirft (`wettfinder_automation.py:5257-5261`, `:5894`).
- **Was hilft:** Token eintragen (Owner, Minuten). Ergebnis der Leseprobe auswerten und bei abgelehntem Dokument mit
  Exit 1 enden. Ein Lebenszeichen nach jedem gelungenen Nachtlauf an einen Wächter ausserhalb des Servers.

**H8 – Der Kundenzugang ist nicht erzwungen, und teure Suchläufe haben keine serverweite Grenze** (LV-G1, LV-5,
DV-G3, DV-7)

- **Beleg:** `customer_access.py:115-117` prüft nur, wenn der Portal-Token gesetzt ist. Am 16.11. auf dem Server
  geprüft: Er ist nicht gesetzt (unverändert seit H14 vom 25.10.). Die Sperre «ein Suchlauf» gilt je Sitzung, nicht
  für den Server. Live-Suchläufe zahlen aus dem gemeinsamen API-Budget.
- **Wirkung:** Ein fremder Besucher kann das Tagesbudget verbrauchen; dann stehen Quotenlauf und Shadow bis zum
  Zurücksetzen. Die Gegenprüfung stufte das als mittel ein; nach dem Servercheck halte ich hoch für richtig.
- **Was hilft:** Eine Tagesgrenze und Wartezeit für Live- und Platzverweis-Suchen, die für den ganzen Server gilt.
  Den Kundenzugang erzwingen, sobald die Migration für den Owner steht (AGENTS, Offen 2).

**H9 – Kein Backup und kein reproduzierbarer Neuaufbau** (DV-5)

- **Beleg:** Owner-Entscheid «keine Backups». Nur auf dem Server liegen die Evidenz (12 921 Wetten, alle Messreihen
  und Vorab-Auswertungen), die Konten von Doublebet und 15K und die Schlüssel. Der Neuaufbau installiert aus
  `requirements.txt` mit 12 von 13 offenen Versionen; `requirements.lock` stammt aus dem Windows-venv und wird nur in
  der CI benutzt.
- **Einordnung:** Kein Fehler, sondern der Preis eines Entscheids. Die Wahrscheinlichkeit ist klein, der Schaden
  vollständig und nicht umkehrbar.
- **Was hilft ohne neuen Job auf dem Server:** die Momentaufnahme des VPS-Anbieters, oder einmal pro Woche die
  Evidenz- und Konto-Datenbanken auf den PC ziehen. Unabhängig davon den Bootstrap auf ein Lock aus dem Server-venv
  umstellen. Der Entscheid bleibt beim Owner.

### MITTEL

Jede Zeile ist im Code oder in den Zahlen belegt; «teilweise» heisst, dass die Gegenprüfung Grösse oder Schwere
korrigiert hat. Wortlaut und Belege stehen im lokalen Anhang.

**Modell Fussball**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| MF-1 | Kalibrierkarten sind an den Enden flach: die klarsten Favoriten verlieren bis zu 9 Punkte | teilweise | mittel |
| MF-2 | Heimvorteil ist zu klein gerechnet: Heimsieg rund 2 Punkte zu tief, Auswärtsseite zu hoch | bestätigt | mittel |
| MF-3 | Additive Paarung läuft genau dort ohne Korrektur, wo die Stärkeunterschiede am grössten sind | teilweise | gross |
| MF-7 | Kleinstaaten-Sperre lässt die Tor-Bereiche des Favoriten durch | bestätigt | klein |
| MF-G1 | Europapokal im Heimatliga-Weg: Die Minimum-Kalibrierung nimmt dem Favoriten wieder weg, was die Ligastärke gibt | ergänzt | mittel |
| MF-G2 | Heimvorteil-Lücke ist auf echten Daten schon gemessen; die geschätzte Korrektur wirkt nur im Heimatliga-Weg (Ergänzung zu MF-2) | ergänzt | klein |

**Modelle der anderen Sportarten**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| SP-1 | Unter 60 % Modellchance sind alle vier Nicht-Fussball-Modelle zusammen ein Münzwurf; nur Tennis hat eine Grenze | teilweise | klein |
| SP-2 | Eishockey im Doublebet: Die Zulassung stützt sich auf alle Spiele, das Quotenband trifft aber die Spiele ohne belegten Vorsprung | teilweise | klein |
| SP-3 | Forschungs-Hinweis fehlt auf der Doublebet-Karte; E-Sport zeigt gar keinen Modellstatus (Vorbefund U1, Massnahme 6 weiter offen) | bestätigt | klein |
| SP-4 | E-Sport-Modell: gleiche Chance für Bo1, Bo3 und Bo5, doppelter Elo-Durchlauf, Rauschen von rund 10 Punkten | teilweise | mittel |
| SP-5 | Eishockey-Modell: Strafterm wirkt fast nicht, 365 Tage ohne Zeitgewicht, keine Torhüter und Ruhetage | bestätigt | mittel |
| SP-7 | Tennis mit Quote: Das Modell bewertet seine eigenen Tipps tiefer als der Markt; die -13,4 % sind Marge plus kleine Stichprobe | bestätigt | klein |
| SP-10 | Kein laufender Wächter für die Sieger-Kalibrierung je Sportart; Messplan mit realistischen Stichproben fehlt | bestätigt | mittel |
| SP-G1 | Ohne Quote blendet die 65-%-Regel bei Tennis, E-Sport und Basketball genau die besseren Zeilen aus; sichtbar bleibt das Münzwurf-Band | ergänzt | klein |
| SP-G2 | Der Montags-Wächter misst in Produktion nichts: Status immer «unavailable», n = 0 | ergänzt | mittel |

**Statistik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| ST-3 | Nur gut die Hälfte der Wetten hat eine Quote, und das Fehlen ist nicht zufällig | bestätigt | mittel |
| ST-4 | Die Shadow-Prüfstufe von 1000 Tipps kann einen kleinen Vorteil nicht nachweisen und beginnt bei jeder Version neu | bestätigt | mittel |
| ST-5 | Aussenseiter: das Modell verspricht 31 %, es treffen 22 %; die Rendite ist dort etwa dreimal so schlecht | teilweise | klein |
| ST-6 | «Trifft so oft, wie es sagt» stimmt nur im Mittel; in erkennbaren Gruppen liegt das Modell 8 bis 43 Punkte daneben | bestätigt | mittel |
| ST-7 | Fallenfilter-Test rechnet Tipps als unabhängig und misst die Trefferquote, nicht das Geld | bestätigt | klein |
| ST-9 | Fünf verschiedene «Einstiegsquoten», und die entscheidenden Skripte liegen ausserhalb von Git | bestätigt | mittel |
| ST-11 | Trefferquote als Zielgrösse täuscht: die Liste ab 70 % trifft 72 %, bräuchte aber 78 % | bestätigt | klein |
| ST-G2 | Die 1,20-Grenze lässt gerade die Tipps übrig, bei denen das Modell zu hoch liegt | ergänzt | klein |

**Mathematik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| MT-1 | Doublebet: höchste Modellchance im Band heisst grösste Abweichung vom Markt; gemessen 44,7 % Treffer bei nötigen 51,2 %, und die Summe füllt immer auf drei Wetten auf | teilweise | klein |
| MT-2 | 15K-Ziel ist mit den eigenen Einsatzregeln nicht erreichbar; die Seite nennt 70 Siege in Folge, nötig wären 200 bis 680 | teilweise | klein |
| MT-3 | 15K-Ticketregel lässt nur Legs zu, bei denen das Modell weit über der Quote liegt; dort irrt das Modell gemessen um 11 bis 15 Punkte | bestätigt | mittel |
| MT-4 | Doublebet-Ziel «+CHF 150» verlangt eine Vervierfachung: zwei bis drei Siege in Folge mit vollem Wiedereinsatz | bestätigt | klein |
| MT-5 | Aussenseiter: Wo die Quote ab 3,00 liegt, sagt das Modell 27,4 %, es treffen 18,2 % | teilweise | mittel |
| MT-7 | 15K-Liste und Ticketregel passen rechnerisch nicht zusammen: gelistet wird nach höchster Chance ab Quote 1,25, ein Ticket braucht zusätzlich +3 % Wert je Leg | bestätigt | mittel |
| MT-G2 | Die geplante Wiederholung der Rangfolge-Prüfung kann einen lohnenden Effekt rechnerisch kaum nachweisen | ergänzt | klein |
| MT-G3 | 15K lehnt ein regelkonformes Ticket ab, sobald ein Teil der gewählten Spiele allein schon ein gültiges Ticket ergibt | ergänzt | klein |

**Logik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| LO-1 | Doublebet wählt nach Summe statt Qualität: Füllwetten mit Modell-Minus, die beste Wette kann fehlen | teilweise | klein |
| LO-2 | Kontextprüfung reicht nur für rund 80 Spiele je Tag, die frühesten zuerst: späte Spiele fehlen still | bestätigt | mittel |
| LO-4 | Die drei «öffentlichen Tipps» zeigt keine App-Fläche; Shadow rechnet sie trotzdem als veröffentlicht ab | bestätigt | mittel |
| LO-6 | Filter-Zusammenspiel: Start bei 70 % plus 1,20-Grenze lenkt die Standardansicht ins Quotenband 1,20-1,39 | bestätigt | klein |
| LO-G2 | Die Lücke von 4 bis 5 Punkten auf der Liste ab 70 % ist ein Auswahl-Effekt der 1,20-Regel, kein Kalibrierfehler des Modells | ergänzt | klein |
| LO-G3 | Doublebet vergleicht Modellchancen aus verschiedenen Sportmodellen direkt: Das am stärksten überzogene Modell gewinnt die Plätze | ergänzt | klein |

**Wettprofi**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| WE-2 | Doublebet und 15K wählen dort, wo das Modell am weitesten über dem Markt liegt: das ist die gemessene Verliererzone | teilweise | mittel |
| WE-3 | 78 % der Fussball-Auswahlen liegen in Nebenmärkten mit hoher Marge; nur 1X2 liegt nahe null | teilweise | mittel |
| WE-4 | 15K: Kombis vervielfachen die Marge, und das Ziel mal 150 ist auch bei fairem Spiel in weniger als 1 von 100 Fällen erreichbar | bestätigt | klein |
| WE-5 | Doublebet: im Band um 2,00 misst die Evidenz −11,7 %; das Ziel +CHF 150 gelingt nur an 9 bis 20 % der Tage, und das Band gilt nicht für den echten Preis | teilweise | klein |
| WE-6 | Der Massstab der Profis fehlt: Schlussquoten werden kaum erfasst, und die 1000-Tipp-Prüfstufe erkennt einen echten Vorteil von 3 % nur in einem von fünf Fällen | bestätigt | mittel |
| WE-7 | RisikoBet lenkt in Aussenseiter: die Zone mit der höchsten Marge und dem grössten Modellfehler | teilweise | mittel |
| WE-12 | Ehrlicher Weg zu einem Vorsprung: den Preis schlagen, nicht das Ergebnis erraten; die Bausteine liegen im Code | bestätigt | gross |
| WE-G1 | Doublebet kennt kein «heute keine Wette»: Es füllt bis zu drei Plätze, auch mit Auswahlen, die das eigene Modell unter dem Preis sieht | ergänzt | klein |
| WE-G2 | Die einzige Zahl auf der Karte ist bei veröffentlichten Tipps ab 70 % rund 4 bis 5 Punkte zu hoch: Wer daraus eine faire Quote rechnet, hält zu tiefe Quoten für gut | ergänzt | klein |

**Entwicklung und Betrieb**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| DV-2 | Nachtlauf endet grün, auch wenn die App das Tagesdokument verwirft | bestätigt | klein |
| DV-4 | Release-Weg liegt ausserhalb von Git und hat keinen Rückweg | teilweise | mittel |
| DV-6 | Alte API-Schlüssel stehen in der öffentlichen Git-Historie, Sperrung nicht belegt | teilweise | klein |
| DV-7 | API-Hockey läuft konstruktionsbedingt an die Tagesgrenze; eine offene App kann Budgets mitverbrauchen | teilweise | mittel |
| DV-8 | Eine einzige unpassende Zeile leert die ganze Website (38 Abbruchstellen im Lader) | bestätigt | mittel |
| DV-9 | CI prüft 35 von 460 Testdateien; auf main schlagen bekannte Tests fehl | bestätigt | mittel |
| DV-G1 | Ein Ausfall der App selbst löst nie einen Alarm aus, auch nicht mit Telegram-Token | ergänzt | klein |
| DV-G2 | Dateiwächter von Streamlit ist in Produktion aktiv: der Fast-forward tauscht den Code der laufenden App sofort, vor Prüfung und Neustart | ergänzt | klein |
| DV-G3 | App ohne Grenzen je Besucher: Speicher je Sitzung wird nie freigegeben, Suchläufe haben keine Obergrenze | ergänzt | mittel |

**UX**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| UX-2 | Die App zeigt nirgends ihre eigene Bilanz, obwohl 12 921 abgerechnete Wetten vorliegen | bestätigt | mittel |
| UX-3 | Forschungsmodell und geprüftes Modell sehen gleich aus; die Evidenzstufe wird berechnet, aber nie gezeigt | bestätigt | klein |
| UX-6 | Zwischen 00:00 und etwa 03:50 ist die App leer und sagt nicht warum | bestätigt | klein |
| UX-7 | RisikoBet zeigt Aussenseiter-Chancen ohne Hinweis, dass das Modell dort bisher klar zu hoch lag | teilweise | klein |
| UX-8 | 15K-Seite: ein Dutzend Bedienelemente vor der ersten Auswahl, der Hauptknopf startet eine Suche, die Zielrechnung zeigt nur den besten Fall | bestätigt | mittel |
| UX-11 | Recht und Spielerschutz: Rechtstexte fehlen weiter, der Hinweis fehlt auf Sperrseiten und steht nur ganz unten | teilweise | klein |
| UX-G1 | Doublebet: Die Vormerkung nimmt jede Quote ab 1,20 an; die App kennt den Marktmedian und sagt nichts, wenn die eigene Quote weit darunter liegt | ergänzt | klein |
| UX-G2 | Auswahlen ohne je gesehenen Preis sehen aus wie preisgeprüfte; ein Viertel der Fussball-Wetten liegt in Marktarten praktisch ohne gespeicherte Quote | ergänzt | klein |
| UX-G3 | 15K-Guthaben, Doublebet-Buchungen und gemerkte Tipps hängen an einer Zufalls-ID im Browser-Speicher; es gibt keinen Weg auf ein zweites Gerät und keine Wiederherstellung | ergänzt | mittel |

**RisikoBet**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| RB-1 | RisikoBet hat keine gemessene Bilanz; die nächsten Messwerte sind klar negativ | teilweise | klein |
| RB-2 | Abrechnung Fussball: Verlängerung, Elfmeterschiessen, Verschiebung und grüner Tisch bleiben für immer offen | bestätigt | mittel |
| RB-4 | Die Seite zeigt nur Szenarien mit gespeicherter Quote; vier Szenario-Arten können nie erscheinen | bestätigt | klein |
| RB-6 | Das Log5-Modell läuft nicht; das echte Forschungsmodell zeigt Aussenseiter zu tief | bestätigt | klein |
| RB-G1 | Fällt die RisikoBet-Runde aus, fehlen Eishockey und Basketball im Wettfinder und im Doublebet | ergänzt | mittel |

**Volles Liga-Wochenende**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| WO-2 | Rechnung Sa 21.11.: rund 45 Minuten bei normalem Anbieter, Reserve rund 15 Minuten; die einzige Bremse ist der Abbruch nach 60 Minuten, danach bleibt der Tag leer | bestätigt | mittel |
| WO-5 | Am vollen Wochenende bekommt «morgen» nur 20 von rund 110 bis 140 Spielen einen Kontext, heute fehlen die späten Spiele; die Liste sagt nichts dazu, obwohl die volle Prüfung nur rund 2 Minuten und 150 bis 380 Abrufe kostet | bestätigt | klein |
| WO-G2 | Für die Liste zählt nur der Versuch: «geprüft» gilt auch, wenn H2H, Ausfälle und Wetter alle fehlen; verborgen wird ein Spiel allein wegen des fehlenden Kontextplatzes | ergänzt | klein |
| WO-G3 | Arbeitsspeicher und Dokumentgrösse fehlen in der Rechnung; beide sind seit dem 25.10. nicht mehr gemessen | ergänzt | klein |

**Live und Platzverweis**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| LV-1 | Kein Live- oder Platzverweis-Kandidat kann je freigegeben werden – die Seite zeigt die gesperrten Werte trotzdem als «Wettkandidat», ohne Forschungs-Hinweis | teilweise | klein |
| LV-5 | Live-Klicks zahlen aus dem gemeinsamen API-Budget, ohne globale Bremse; der alte Analyzer startet für jede Sitzung, obwohl nur Live ihn braucht | bestätigt | mittel |
| LV-G2 | Drei verschiedene Uhren: Verlauf, Modell und Abrechnung zählen Tore der Nachspielzeit je anders – die geplante Shadow-Messung misst nicht die Wette | ergänzt | mittel |

### NIEDRIG

**Modell Fussball**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| MF-5 | Formstärke ist nur auf 31 ersten Ligen geprüft, läuft aber in 32 weiteren Katalog-Ligen | teilweise | klein |
| MF-6 | Ecken: Über-Konfidenz ist nicht gesichert, aber grösstes Rauschen und schlechteste Rendite | teilweise | mittel |
| MF-8 | Unabhängige Poisson-Tore: Remis zu tief, «12» zu hoch, Torbereiche leicht zu sicher | teilweise | mittel |
| MF-9 | Saisonstart: Fenster und Formstärke greifen ohne Abschlag in die Vorsaison | bestätigt | klein |
| MF-10 | Neutraler Spielort wird bei Vereinsspielen nie gesetzt | bestätigt | klein |
| MF-11 | Evidenz-Auswertung trennt nicht nach Modellversion, Seite und Spiel | bestätigt | klein |

**Modelle der anderen Sportarten**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| SP-6 | Die 50,0/50,0-Zeilen für Eishockey und Basketball messen nichts; auch der eigene Qualitätsbericht zählt beide Seiten | bestätigt | klein |
| SP-8 | Tennis-Suche zeigt 50-60 % weiter als «Modellfavorit» mit Merken-Knopf; Datenstand bis 14 Tage gilt als aktuell | bestätigt | klein |
| SP-9 | Basketball: 29 bis 39 Spiele tragen keine Aussage; Modell bisher deutlich zu hoch, zu Recht nicht im Doublebet | teilweise | klein |
| SP-G3 | Doublebet-Zulassung gilt für jedes Eishockey-Modell; belegt ist nur das NHL-Modell | ergänzt | klein |

**Statistik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| ST-8 | Unsicherheiten ohne Spielbündelung; die versionierten Berichte haben gar kein Intervall | teilweise | klein |
| ST-10 | Der Marktvergleich misst das alte Modell; für die Produktionsbasis fehlt er | bestätigt | klein |
| ST-12 | Spiele mit Verlängerung werden nie abgerechnet; Zwei-Weg-Sportarten zählen jedes Spiel doppelt | bestätigt | klein |
| ST-G3 | Ein versionierter, spielgebündelter Marktvergleich liegt im Repo und wird nicht benutzt | ergänzt | klein |

**Mathematik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| MT-6 | Die 1,20-Grenze ist keine Wertregel: bei 1,20 sind 83,3 % Treffer nötig; im Band 1,20–1,39 treffen 71,5 % bei nötigen 77,8 % | bestätigt | klein |
| MT-8 | Unter der 1,20-Regel sind EV und Kelly ausserhalb von 15K wirkungslos; der Text meldet trotzdem «alle Gates bestanden» (M5 vom 25.10., unverändert) | teilweise | klein |
| MT-9 | Stufe 2 und 3 der 1,20-Prüfung: 6 % Marge und 65 % Modellschutz liegen neben den Messwerten | teilweise | klein |
| MT-10 | Kalibrierkurven kommen in der gemeinsamen Projektion nur zu 6 bis 12 % an (M2 vom 25.10., Gesetz v1 weiter aktiv) | bestätigt | mittel |

**Logik**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| LO-3 | Evidenz-Abrechnung ohne Endzustand: Verlängerung, Absage, Abbruch und verlegte Tennis-Starts bleiben stumm offen | bestätigt | mittel |
| LO-5 | Je Spiel zeigt die Liste ein einziges Endstand-Szenario: viele fast gleiche Zeilen, gemeinsam unwahrscheinlich | teilweise | mittel |
| LO-7 | NBA-Nachtspiele bekommen nie eine Prognose mit Ergebnis (dieselbe Lücke wie bei der NHL vor dem 15.11.) | bestätigt | mittel |
| LO-8 | Doublebet-Archiv hält nur den Plan von etwa 04:10 fest; spätere Pläne nur, wenn jemand die Seite öffnet | bestätigt | klein |
| LO-9 | Doublebet-Vorschau «Morgen» zeigt NHL-Nachtspiele, die sich nie vormerken lassen | bestätigt | klein |
| LO-10 | Liste jede Nacht von 00:00 bis etwa 04:10 leer, obwohl das Dokument die Spiele des neuen Tages schon enthält | bestätigt | klein |
| LO-11 | Kleinstaaten-Sperre lässt Tor-Bereiche mit Obergrenze durch («Favorit 1-3 Tore») | teilweise | klein |

**Wettprofi**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| WE-8 | Kombi- und Oder-Märkte aus einem Spiel erscheinen ohne jeden Preisbeleg: der Markttyp, an dem Buchmacher am meisten verdienen | teilweise | klein |
| WE-9 | Kein Einsatzhinweis und kein Hinweis auf abhängige Wetten: im Mittel 7,3 Auswahlen je Spiel | teilweise | klein |
| WE-10 | Preisprüfung meldet «Alle … Risiko-EV- und Einsatz-Gates bestanden» bei −18,8 % Risiko-EV (seit 25.10. bekannt, weiter offen) | teilweise | klein |
| WE-11 | Elf Buchmacher-Tricks im Abgleich: Schutz bei einem, Lenkung hinein bei zwei, zu acht sagt die App nichts | bestätigt | klein |
| WE-G3 | Der Preis-Check für die eigene Quote ist seit 24.09.2026 nicht angeschlossen; wer ihn wieder einhängt, bekommt unter der Produktionsregel bei jeder Quote ab 1,20 «QUOTE IM VALUE-BEREICH» | ergänzt | klein |

**Entwicklung und Betrieb**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| DV-10 | Evidenz-Datenbank ohne Index, WAL und Aufbewahrung (Rest von Massnahme 9) | teilweise | klein |
| DV-11 | Jede Änderung ist teuer: fünf Module mit 5000 bis 5900 Zeilen, Altcode im App-Start, 22-MB-Dokument bei jedem Klick neu gelesen | teilweise | gross |
| DV-12 | Alte Massnahmen 5, 6, 8, 9, 10: Stand im heutigen Code | bestätigt | klein |

**UX**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| UX-4 | Wettfinder-Zeile: Auswahl und Modellchance sind die kleinste Schrift; Spielname und «Contra» wiederholen sich | teilweise | klein |
| UX-5 | Handy: Doublebet-Kachel, Tennisbox und 18+-Hinweis liegen unter bis zu 20 offenen Spielkarten; die Navigation ist abgeschnitten | teilweise | klein |
| UX-9 | Zahlen, Datum, Währung und Begriffe sind je Fläche anders (Massnahme 7, weiter offen) | bestätigt | mittel |
| UX-10 | Betreibersprache in Kundentexten | bestätigt | klein |
| UX-12 | Jede Bedienung baut die ganze Wettfinder-Seite neu: alle Karten, bis zu 20 Formblöcke, Archivschreiben im Renderpfad | teilweise | mittel |

**RisikoBet**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| RB-3 | Was die Seite wirklich zeigte, wird nur beim Seitenbesuch archiviert | teilweise | mittel |
| RB-5 | Fussball-Auswahl vor allen Gates; «Aussenseiter» ohne Mindestabstand; Chance strukturell zu hoch | teilweise | klein |
| RB-7 | Karte: Evidenzstufe und vorsichtige Chance werden gerechnet, aber nicht gezeigt | teilweise | klein |
| RB-8 | Betrieb: eine Runde pro Nacht, tote Spiele bleiben ewig in der Warteschlange, eine Zeile kann eine ganze Quelle kippen | bestätigt | mittel |
| RB-G2 | Fussball-Szenarien tragen immer dieselbe Modellversion; eine Bilanz lässt sich nicht nach Modellstand trennen | ergänzt | klein |
| RB-G3 | Tennis: Zwischen 40 und 50 % Modellchance ist der gezeigte «Aussenseiter» gemessen kein Aussenseiter | ergänzt | klein |

**Volles Liga-Wochenende**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| WO-3 | Nachtspiel-Evidenz hängt am Kontextplatz von morgen: am vollen Wochenende 20 Plätze nach Modellrang, und die Grenze 04:30 stützt sich auf kurze Läufe | bestätigt | klein |
| WO-4 | API-Budget reicht am 21.11. (geschätzt 2900 bis 3500 von 7500); zuerst gesperrt werden die Eishockey-Quoten; eine Budget-Sperre im Fussball-Scan zählt als Betriebsfehler, und ein zweiter voller Lauf am selben Tag stösst an die Hintergrund-Reserve | teilweise | klein |
| WO-6 | Kontext-Gate ohne Nutzenbeleg: Das Ausfall-Veto kann im Betrieb nie auslösen, das Wetter-Veto beruht auf der widerlegten Annahme, das H2H-Veto ist nie geprüft, und gesperrte Kandidaten werden nicht gespeichert | teilweise | mittel |

**Live und Platzverweis**

| Nr. | Befund | Gegenprüfung | Aufwand |
|---|---|---|---|
| LV-2 | Wer aus der Live-Tabelle wettet: zuerst kommen Spiele mit fairer Quote unter 1,20, der Datenstand hat keine Altersgrenze, die Nachspielzeit fehlt | teilweise | mittel |
| LV-3 | Die Messung kann das Platzverweis-Modell nicht bestätigen: Signale entstehen nur per Klick in der App | bestätigt | mittel |
| LV-4 | Der 05:41-Lauf holt Spiellisten nur einmal je Liga und Saison: der Verlauf wächst nicht, der Lauf läuft leer; beide Datenbanken liegen im Code-Ordner | bestätigt | mittel |
| LV-6 | Zwei verschiedene Rechenmodelle für denselben Spielzustand; alle Faktoren sind gesetzte Annahmen; das Niveau liegt rund 25 % unter den im Code genannten Verlaufswerten | bestätigt | gross |
| LV-G3 | Der Satz «Live-Analyse · keine passende Live-Quote» nennt einen Grund, den die App nie prüft | ergänzt | klein |

---

## 4. Die Sicht des Wettprofis: Buchmacher-Tricks und was Buchmacher wirklich stört

Der Owner will eine App, die schlauer ist als der Buchmacher und auf keinen Quotentrick hereinfällt. Der Abgleich mit
elf klassischen Tricks (WE-11):

| Trick des Buchmachers | Was BetBoy heute tut |
|---|---|
| Ungültig- und Streichregeln (verschoben, abgesagt) | schützt teilweise: Shadow und 15K kennen die Regeln; der Hinweis zu Ecken und Karten steht nur auf der 15K-Seite |
| Kombis aus einem Spiel («Bet Builder») | lenkt hinein: sechs Kombi-Märkte aus Ergebnis und Toren im Katalog, ohne jeden Preisbeleg (WE-8) |
| Kombiwetten über mehrere Spiele | lenkt hinein: 15K-Ticket mit bis zu drei Spielen; jede Kombi vervielfacht die Marge (H3) |
| Quoten-Boosts | sagt nichts |
| Cash-out | sagt nichts |
| Freiwetten mit Umsatzbedingung | sagt nichts |
| Kombi-Versicherung | sagt nichts |
| Frühe Preise mit breiter Marge | sagt nichts; die Tipps entstehen im Nachtlauf, also früh |
| Limitieren von Gewinnern | sagt nichts; Nebenmärkte führen am schnellsten zu Limits |
| Irrtumsquoten, die gestrichen werden | sagt nichts |
| Verzögerte Annahme | sagt nichts |

Eigener Schutz ausserhalb der Liste: die 1,20-Grenze gegen den mittleren Preis, widerspruchsfreie Auswahlen je Spiel,
das feste Tagesbudget im Doublebet, Einsatzdeckel im 15K und Texte ohne Garantie.

**Was Buchmacher wirklich stört,** hat mit Trefferquoten wenig zu tun:

- Kunden, die nur zum besten Preis über der fairen Marktquote wetten und regelmässig die Schlussquote schlagen;
- Hauptmärkte mit kleiner Marge statt Nebenmärkte (78 % der Fussball-Auswahlen von BetBoy liegen in Nebenmärkten,
  WE-3);
- Einzelwetten mit flachen Einsätzen statt Kombis;
- Aktionen nüchtern nachrechnen.

**Was die eigenen Zahlen dazu sagen:** 0 von 112 Liga-mal-Markt-Zellen schlagen den Schlussmarkt. Von sechs geprüften
Ideen zeigte am 12.11. nur die Preisjagd ohne Modell ein Plus: +3,5 % [+1,2; +5,9] auf 18 686 Wetten, aber nur mit
dem Bestpreis sehr vieler Buchmacher. Mit zwölf namentlichen Buchmachern enthält der Bereich die Null (+2,9 %
[−1,7; +7,5]), und die Saison 2025/26 war negativ (−15,4 %). Der Owner hat am 12.11. entschieden: nicht messen, nicht
bauen, nicht erneut vorschlagen. Dieses Audit ändert daran nichts. Es hält nur fest, dass die Bausteine im Code
liegen (No-Vig nach Shin und Power, Quoten je Buchmacher mit Zeitstempel, CLV-Ledger, Kappung des Modell-Vorsprungs)
und dass das Modell allein den Buchmacher nach allen bisherigen Messungen nicht schlägt (WE-12).

---

## 5. Einordnung scheinbar widersprüchlicher Zahlen

- **«Gut kalibriert» und «liegt daneben» stimmen beide.** Über alle Prognosen trifft das Modell so oft, wie es sagt.
  In erkennbaren Gruppen liegt es 8 bis 43 Punkte daneben (ST-6): zu tief, wo der Markt mehr sieht, zu hoch, wo er
  weniger sieht. Die Fehler heben sich im Mittel auf. «Gut kalibriert» gilt deshalb nie für eine ausgewählte Liste.
- **Die Liste ab 70 % verspricht 4 bis 5 Punkte zu viel, obwohl das Modell bei klaren Favoriten zu tief liegt.** Die
  1,20-Grenze blendet die Tipps aus, bei denen der Markt sicherer ist als das Modell und recht behält. Übrig bleiben
  die, bei denen der Markt skeptischer ist (ST-G2, LO-G2). Wer die Enden der Kalibrierkarten anhebt (MF-1), macht die
  sichtbare Liste zuerst noch optimistischer. Beide Punkte gehören in dieselbe Vorab-Prüfung.
- **6 bis 8 Punkte oder 14 Punkte zu hoch im Band um 2,00?** 6 bis 8 Punkte gelten für alle Wetten im Band, 14 Punkte
  für die Gruppe mit 55 bis 65 % Modellchance (192 Zeilen). Für die Doublebet-Karte zählt die zweite Zahl.
- **Aussenseiter:** Bei Quote 3,00 bis 4,99 sagt das Modell 30,6 % und es treffen 21,8 % (363 Wetten); ab 3,00
  zusammen 27,4 % gegen 18,2 % (528 Wetten). «Dreimal so schlechte Rendite» ist nicht gesichert (−23,6 % ±14,8).
- **Die Null bei 1X2** kommt von der kleinen Marge in diesem Markt, nicht vom Modell. Dort ist der Rückstand des
  Modells auf den Markt am grössten (Bericht vom 12.11.).
- **«Öffentliche Tipps» hat zwei Bedeutungen.** Die Archivzeilen des Wettfinders sind die Standardliste. Die höchstens
  drei «öffentlichen Tipps» der Pipeline zeigt keine App-Fläche; Shadow rechnet sie trotzdem als veröffentlicht ab
  (LO-4).

---

## 6. Was gut ist

- **Rechnung:** Tormatrix, Marktchancen, Abrechnungsregeln, Kelly und No-Vig sind exakt. Alle Marktchancen kommen aus
  derselben Matrix; nirgends wird eine Summe benutzt, wo ein Produkt nötig wäre.
- **Kein Blick in die Zukunft:** Walk-forward und Kalibrierung lernen nur aus früheren Tagen. Die Formstärke nutzt nur
  Spiele vor dem Anstoss.
- **Evidenz:** Die Datenbank ist unveränderlich, nimmt Prognosen nur vor Anstoss an, weist widersprüchliche Ergebnisse
  ab und speichert jeden Buchmacherpunkt mit Zeitstempel. Deshalb liess sich alles nachrechnen.
- **Prüfkultur:** Hypothese vor den Daten, Commit als Beleg, getrennte Prüfdaten, Bootstrap über ganze Spiele,
  Korrektur für viele Tests. Durchgefallene Kandidaten bleiben draussen (Kalibriergesetz v2, Startelf, Wetter,
  Kandidaten 1 bis 3, Rangfolge, Form).
- **Fail-closed:** Fehlende Stichprobe, Aufsteiger ohne fünf Spiele, veränderte Annotation oder gescheiterte
  Projektion ergeben keine Prognose statt einer geschätzten. Verlängerung zählt nie als 90-Minuten-Ergebnis.
- **Betrieb:** Der API-Budgetwächter reserviert atomar mit Prioritäten. Das Tagesdokument wird atomar ersetzt. Die
  Einheiten sind gehärtet, Streamlit hängt nur an 127.0.0.1 hinter dem Proxy, verpasste Timer werden nachgeholt.
- **Sprache und Schutz:** Keine Garantiesprache gefunden. Doublebet hat ein festes Tagesbudget ohne Nachschuss. Der
  Rechtsfooter nennt 18+ und echte Schweizer Hilfestellen. Tippflächen sind 44 bis 48 Pixel gross, alle geprüften
  Textfarben erreichen 4,5:1.
- **Forschung ist im Code sauber getrennt:** Forschungszeilen können nie Tipp oder 15K werden; Live- und
  Platzverweis-Werte lassen sich nicht merken und bekommen keinen Einsatz.

---

## 7. Massnahmenplan in Reihenfolge

| # | Massnahme | Aufwand | Löst |
|---|---|---|---|
| 1 | **Vor dem Wochenende 21./22.11.:** Nachtlauf so ordnen, dass heute zuerst veröffentlicht wird; Hintergrundschritt nach hinten; Zeitprüfung vor der Suche für morgen; am Fr 20.11. die Stufenzeiten lesen | 1 Tag | H5 |
| 2 | Telegram-Token eintragen (Owner, Minuten). Leseprobe auswerten: Exit 1, wenn die App das Dokument verwirft. Lebenszeichen nach jedem gelungenen Lauf | Minuten bis 1 Tag | H7 |
| 3 | Fehler je Spiel statt je Tag werten, Status und Zähler koppeln, Wetterabruf einmal wiederholen | 1–2 Tage | H6 |
| 4 | Serverweite Tagesgrenze und Wartezeit für Live- und Platzverweis-Suchen; Streamlit-Dateiwächter abschalten (`fileWatcherType = "none"`) | 1 Tag | H8, DV-G2 |
| 5 | **Messen, was die App wirklich zeigt:** eine Preisreferenz in einem Modul, Messskripte in Git, Bündelung nach Spiel, Abdeckung je Marktart; eigene Bilanz für 15K-Tickets, RisikoBet und die Standardliste ab 70 % | 2–3 Tage | H2, H3, ST-3, ST-9, RB-1 |
| 6 | **Modell genauer machen, je Kandidat mit Vorab-Regel und getrennter Prüfung:** Heimvorteil (MF-2, auf echten Daten schon gemessen: Heimsieg in 14 von 14 Ligen unter dem fairen Markt), Enden der Kalibrierkarten (MF-1, MF-G1), additive Paarung mit Kandidat 4 (MF-3), Hybrid-Messung am 30.11. | je 2–4 Tage | H1, MF-1 bis MF-3 |
| 7 | Andere Sportarten: die 60-%-Regel als Vorab-Hypothese für E-Sport und Eishockey prüfen; E-Sport-Serienformat; Montags-Wächter auf die eigenen Prognosen umstellen | 3–5 Tage | SP-1, SP-2, SP-4, SP-10, SP-G2 |
| 8 | Abrechnung schliessen: Verlängerung und Elfmeterschiessen mit dem 90-Minuten-Stand, Endzustand für verschoben und abgesagt in Evidenz und RisikoBet | 1–2 Tage | RB-2, LO-3, ST-12 |
| 9 | Owner-Entscheide zu 15K: Ticketregel und Kombi, Zielrechnung, Währung | Entscheid | H3, MT-2, UX-8 |
| 10 | Owner-Entscheide zu Doublebet: immer auffüllen oder «heute keine Wette», Eishockey unter 60 %, Forschungs-Hinweis auf der Karte, «Ziel +CHF 150» (offen seit 25.10.) | Entscheid | H4, LO-1, WE-G1, SP-2, SP-3 |
| 11 | Massnahme 6 vom 25.10. abschliessen: Evidenzstufe als Textzeile, Text «Alle … Gates bestanden» berichtigen; Owner-Entscheid, ob die App ihre Bilanz zeigt | 1–2 Tage | UX-2, UX-3, WE-10 |
| 12 | Kleinstaaten-Sperre um nach oben begrenzte Tor-Bereiche der vier kleinsten erweitern (Owner-Entscheid, gilt bis Kandidat 4) | klein | MF-7 |
| 13 | Schutz vor Datenverlust ohne neuen Job auf dem Server; Bootstrap auf ein Lock aus dem Server-venv | Entscheid, klein | H9 |
| 14 | Lader: Ein Fehler in einer Zeile verbirgt die Zeile, nicht die Website; Release-Weg in Git mit Rückweg; CI auf mehr als 35 von 460 Testdateien | 1 Woche | DV-4, DV-8, DV-9 |
| 15 | Leere Liste zwischen Mitternacht und Nachtlauf erklären oder überbrücken; Rechtstexte | Entscheid, klein | UX-6, LO-10, UX-11 |

Punkt 1 ist dringend, weil das erste volle Liga-Wochenende mit Doppel-Scan in fünf Tagen liegt und die Rechnung nur
rund 15 Minuten Reserve zeigt. Punkt 6 ist der einzige Weg, auf dem «bei gleicher Quote die wahrscheinlichere Wette»
stimmen kann: Solange das Rauschen grösser ist als die Unterschiede zwischen den Kandidaten, wählt jede Regel nach
Modellchance die Überschätzungen.

---

## 8. Methodik und Kennzahlen

| Kennzahl | Wert |
|---|---|
| Prüfläufe | 23 (8 Rollen, 8 Gegenprüfungen, 1 Kritiker, 3 Nachprüfungen mit je einer Gegenprüfung) |
| Befunde | 142: 110 von den Prüfern, 32 von der Gegenprüfung ergänzt |
| Urteil der Gegenprüfung | 65 bestätigt, 45 teilweise, 0 widerlegt; Schwere bei 56 gesenkt |
| Schwere nach Gegenprüfung | 0 kritisch, 13 hoch (mit H8: 14), 77 mittel, 52 niedrig |
| Python-Zeilen im Root | 94 552; grösste Module `challenge_15k` 5 925, `wettfinder_automation` 5 898, `challenge_store` 5 201, `app` 5 182, `challenge_engine` 4 980 |
| Tests | 460 Testdateien; die CI prüft 35 davon; bekannte rote Tests auf `main` |
| Zahlenbasis | 94 713 Prognosezeilen, 12 921 abgerechnete Wetten, 6 695 mit Quote, 06.09.–15.11.2026 |
| Rechenprüfungen | reine Funktionen und Simulationen der Prüfer, lokal unter `output/audit-20261116/scratch/` |

Nicht geprüft oder nicht prüfbar:

- echte Kalibrierkarten und Walk-forward-Datensätze der Produktion (MF-1 und MF-2 sind deshalb in der Grösse nur
  simuliert; die Richtung von MF-2 ist auf echten Daten belegt);
- echte 15K-Tickets, Doublebet-Buchungen und RisikoBet-Ergebnisse;
- Fallenfilter und Formstärke-Messung (vorab festgelegt, 30.11.2026);
- die laufende Seite auf Handy und Desktop, Screenreader und Geschwindigkeit;
- die Laufzeit des Nachtlaufs an einem vollen Samstag mit Doppel-Scan (den gibt es erst am 21.11.);
- ob die alten Schlüssel beim Anbieter gesperrt sind.

---

## 9. Offene Fragen an den Owner

1. **15K:** Soll die Ticketregel weiter positiven Modell-Erwartungswert je Leg verlangen, obwohl genau diese Wetten
   gemessen verlieren? Soll das Ziel bleiben, obwohl es mit den erlaubten Einsätzen 200 bis 680 Siege in Folge
   braucht?
2. **Doublebet:** Soll es weiter immer bis zu drei Wetten füllen, auch wenn das eigene Modell eine Auswahl unter dem
   Preis sieht? Soll Eishockey unter 60 % Modellchance im Doublebet bleiben?
3. **Bilanz:** Soll die App je Fläche zeigen, was aus ihren Auswahlen geworden ist (Wettfinder 58 % bei 60 % Modell)?
4. **Nacht:** Soll die Liste zwischen Mitternacht und dem Nachtlauf die schon gerechneten Zeilen des Vortags zeigen,
   oder reicht ein erklärender Satz?
5. **Schutz der Daten:** Reicht die Momentaufnahme des Anbieters oder ein wöchentliches Ziehen der zwei kleinen
   Datenbanken auf den PC, oder bleibt es ganz bei «kein Backup»?
6. **Live und Platzverweis:** als Forschung kennzeichnen, ausblenden oder richtig messen? Die Seite zeigt gesperrte
   Werte heute als «Wettkandidat» (LV-1).
7. **RisikoBet:** Soll die Ungültig-Regel des Shadow (verschoben, abgesagt, grüner Tisch, Verlegung über zwölf
   Stunden) auch dort gelten?
8. **Kundenzugang:** Wann wird er erzwungen (H8)?
