# Fußball: Torzeit-Profil und kumulative Zeitmärkte

Stand: 17.10.2026. Ausgangscode: `4f2af4e8e6e8a2eb4b92d94d12b7fc219611caf9`.
Status: Funktionsumfang vom Nutzer freigegeben; schriftlicher Entwurf zur Prüfung.
Noch kein Produktivcode, Modelllauf, historischer Backfill oder Deployment.

## Ziel und Umfang

BetBoy soll vor dem Spiel nachvollziehbare Auswahlen für Tore **ab Anpfiff bis
Minute 15, 30, 60 und 75** berechnen und mit passenden Anbieterquoten verbinden.
Unterstützt werden Gesamttore, Heim-/Auswärtsteam-Tore und beide Teams treffen.
Torzeiten beider Mannschaften werden kompakt als Spielstatistik sichtbar.
Eine gute Endstand-Prognose allein reicht nicht als Nachweis eines Zeitmarkts.

Der Nutzer hat historische Prüfung, Tests, Commit, main-Push und VPS-Deployment
beauftragt, ausdrücklich **ohne Backups**. Vorhandene/kostenlose Quellen verwenden;
keine neue kostenpflichtige Buchung. Keine neue Live-Wette oder automatische
Geldplatzierung. Keine neuen Timer. Die ersten zehn Minuten sind nicht Teil
dieser Freigabe; deren sekundengenaue Grenzen bleiben ein späterer Zusatz.

## Bestehende Verträge und geprüfte Quellenlage

- `api_football.py:get_fixture_events` kann Ereignisse abrufen. Fehler und echte
  leere Antworten müssen über den Fehlerstatus auseinandergehalten werden.
- `get_team_statistics` übernimmt bisher Durchschnittswerte, keine Torzeitkurven.
- Endstände/Formlisten enthalten keine vollständige Torchronologie. Der
  Platzverweis-Harvester verwirft die vollständigen Ereignislisten und speichert
  nur ausgewählte Folgen nach Platzverweisen. Diese Auswahl ist kein neutraler
  Trainingsbestand für Zeitmärkte. Ein genereller Rohantwort-Cache existiert
  im API-Budget-Wrapper nicht.
- Die bisherigen 96 Marktdefinitionen, v14, 40 Tor-Fit-Ziele, Originalnachweise
  und unveränderlichen Ticketverträge bleiben unverändert. Deren boolesche
  Ergebnislogik darf keine ganzzahlige Zeitlinie abrechnen.
- RisikoBet-/Prognosebelege unterscheiden derzeit WIN/LOSS/VOID, nicht PUSH.
  Eine Rückzahlung bei Gleichstand der Torlinie braucht einen eigenen Vertrag.

### Begrenzte echte Quotenprobe

Am 17.10.2026 wurden genau drei Diagnoseanfragen über den vorhandenen
API-Football-Schlüssel und Budget-Wrapper ausgeführt: Katalog, Bayern–Leipzig
(1575185), Roma–Genoa (1550148). Beide Spielantworten vollständig Seite 1/1,
keine Anbieterfehler. Keine neuen Prognosen, Scans oder Backups.

- Native 144: `Goal in 1-15 minutes`, William Hill, tatsächliche Auswahlen
  `Yes`/`No`. Bayern: 2,20/1,60, Anbieterstand 12:01:08 UTC. Roma: 3,00/1,35,
  Anbieterstand 13:27:15 UTC. Empfang etwa 15:38 UTC. Das sind historische
  Preisbelege mit diesen Anbieterzeiten, keine frisch bestätigten Angebote.
- 145/147/148 bezeichnen einzelne Abschnitte 16–30/46–60/61–75. Sie sind keine
  kumulativen Gesamtmärkte bis Minute 30/60/75.
- 136–139 bezeichnen Ergebniswetten zum Zeitpunkt 15/30/60/75, keine Torlinien.
- Exakte kumulative Gesamt-/Team-Torlinien und BTTS bis 30/60/75 sind durch diese
  Probe **nicht nachgewiesen**. Das ist kein Beweis weltweiter Nichtverfügbarkeit.
  Ihre Preisadapter werden erst nach tatsächlichem exaktem Angebotsbeleg aktiviert.

Receipt außerhalb Git: `C:/Projekt/BetBoy/output/time-markets-20261017/capability-01.json`
(ca. 183 KB, nur begrenzte Quoten-/Katalogfelder, keine Schlüssel).

## Gewählter Ansatz

Ein zeitlicher Zusatz zur vorhandenen gemeinsamen Torverteilung. Nicht bloß
Saison-Toranteile als Wettwahrscheinlichkeit ausgeben und nicht die 90-Minuten-
Prognose gleichmäßig mit 15/90 oder 60/90 kürzen. Ein vollständig neues
Parallelmodell für das gesamte Spiel würde widersprüchliche Endstandswerte
und unnötige zusätzliche Modellpflege erzeugen.

### 1. Vollständige, kleine Torverläufe

Native positive Fixture-ID, Wettbewerb, Saison, beide Team-IDs, tatsächlicher
Status, Anstoß, Halbzeit-/regulärer Endstand, Quellrevision, Empfangszeit und
semantische Version binden. Eine Timeline enthält ausschließlich gültige
reguläre Tore mit begünstigtem Team, Halbzeit, offizieller Minute und Nachspielzeit.
Spielerbiografien, Bilder, Aufstellungen und komplette Rohantworten nicht kopieren.

- Tore einschließlich gültiger Strafstoßtore; verschossene Elfmeter, aberkannte
  Tore und Elfmeterschießen nicht zählen. Eigentore dem begünstigten Team zuordnen.
- Nicht allein nach Minute deduplizieren: zwei Tore derselben Minute sind möglich.
  Transportduplikate dagegen erkennen. Korrigierte Quellrevisionen ersetzen nur
  den aktuellen abgeleiteten Verlauf; alte Prognosebelege nicht umschreiben.
- Nur vollständig abgeglichene Spiele verwenden: reguläre Torzahlen und
  Halbzeitwerte müssen zum Verlauf passen. Erste Version verarbeitet FT-Spiele;
  AET/PEN erst mit eigenem nachgewiesenem regulären Zeitvertrag.
- Ein validierter FT-Endstand 0:0 beweist eine leere Torfolge ohne Ereignisabruf:
  Herkunft `score_implied_empty`. Nicht als erfolgreich empfangene Ereignisliste
  ausgeben. Ein fehlender/fehlerhafter Abruf bei anderem Endstand ist niemals 0:0.
- Keine negativen CSV-Pseudo-IDs an den Ereignis-Endpunkt schicken. Ohne sichere
  native Zuordnung bleibt der betreffende historische Spielverlauf unverfügbar.

Persistenz: eine neue, versionierte kompakte Tabelle im vorhandenen
`xg_cache.db`, keine neue Datenbank. Höchstens 8 KiB kanonische Timeline pro
Spiel; übergroße/unplausible Fälle separat zählen, nicht abschneiden.
Aktuelle/vorherige Spielzeit, höchstens 730 Tage; höchstens 30.000 aktuelle
Verläufe und 64 MiB logische Nutzlast dieser Funktion, zusätzlich höchstens
128 MiB physischer Zuwachs dieser DB gegenüber dem dokumentierten Ausgangswert.
Bei Erreichen einer Grenze keine weiteren Einfügungen, bis ausreichend Platz
durch die eigene Retention frei ist. Nur älteste nicht referenzierte Verläufe
entfernen, keine Beleg-/Geldhistorie löschen.
Physische DB-Größe separat messen; keine automatische VACUUM-Kopie/Backups.
Aktuellen akzeptierten Verlauf und begrenzten Fehler-/Retry-Status getrennt halten:
ein fehlgeschlagener späterer Abruf darf einen gültigen Verlauf nicht überschreiben.

Zuerst bereits vollständig gespeicherte native Fixture-Details prüfen. Danach
resumierbarer einmaliger Einrichtungs-Backfill, höchstens 1.000 reservierte
Anfragen pro Aufruf über BACKGROUND-Priorität und den bestehenden Kontingentschutz.
Pro Spiel einmal, mit Überlappungs-/Korrekturprüfung statt blindem Wiederholen.
Im Regelbetrieb vorhandene Ereignisantworten des täglichen Platzverweis-Laufs
um 05:41 Europe/Zurich zusätzlich in den kompakten Cache übernehmen. Neue
entdeckte Spiele über einen überlappenden Datumscursor ergänzen; bestehende
dauerhafte Saison-Importmarker beweisen keine aktuelle Spielabdeckung.
Alle Zusatzanfragen einschließlich Listen, Fehler und Wiederholungen bleiben
innerhalb dessen vorhandenen 350-Anfragen-Gesamtbudgets, nicht 350 zusätzlich.
Aktuelle konfigurierte Fußballwettbewerbe priorisieren, nicht blind nur die
alte feste Platzverweis-Ligaliste als vollständige Abdeckung ausgeben.
Der 03:35-Wettfinder liest den letzten abgeschlossenen Datenstand; kein neuer Timer.
Einmaliger historischer Backfill ist ausdrücklich Teil des Auftrags, kein
unbegrenzter Hintergrundlauf. Der spätere Implementierungsplan nennt vor Start
die tatsächlichen fehlenden Spiele und geschätzten API-Aufrufe.

### 2. Zeitvertrag und konsistente Berechnung

Reguläre Phasen: 1–15, 16–30, 31–Halbzeit einschließlich 45+, 46–60, 61–75,
76–Ende einschließlich 90+. Erste-Halbzeit-Nachspielzeit liegt vor jeder
zweiten-Halbzeit-Grenze; nicht naiv `elapsed+extra` gegen 60 vergleichen.
Minuten sind keine erfundenen Sekunden. Provider-Minutenkonvention, Buchmacher-
Grenzen und Nachspielzeit müssen nachgewiesen übereinstimmen, sonst keine Quote.

Für die bestehende gemeinsame Endstandverteilung `M(h,a)` werden zwei
zeitliche Toranteil-Kurven gelernt. Trainingsdaten berücksichtigen aktuelle
und vorangegangene Saison, stärkere Gewichtung jüngerer Spiele, Heim/Auswärts
sowie Torzeiten des Teams **und Gegentorzeiten des Gegners**. Kleine Stichproben
werden zur passenden Team-/Ligabasis geschrumpft, nicht ungeprüft übernommen.
Die bestehende Spielstärke steckt weiterhin in M; ein Torzeit-Profil ersetzt
keine Gegnerstärke und behebt keine separaten offenen Grundmodell-Lücken.

Aus geglätteten Angriffs-/Gegentoranteilen entsteht je Phase b:
`q_side,b ∝ q_attack(team,b) * q_concede(opponent,b) / league_share_b`.
Alle Anteile positiv glätten und gemeinsam auf Summe 1 normieren. Recency- und
Glättungsparameter ausschließlich im Trainings-/Abstimmungszeitraum bestimmen.

`F_H(c)`/`F_A(c)` sind die kumulierten Anteile bis zur Grenze c. Dann gilt:

`Q_c(k,l) = Σ M(h,a) * Bin(h,k,F_H(c)) * Bin(a,l,F_A(c))`.

Alle Zeitmärkte werden aus demselben Q berechnet. Dadurch bleiben die
Abhängigkeit der Endstandstore, normierte Wahrscheinlichkeiten und verschachtelte
Zeitfenster erhalten. Über-/BTTS-Ja-Chancen dürfen bei späterer Grenze nicht
fallen. Bei Endstandgrenze mit F=1 wird exakt das unveränderte M zurückgegeben.
BTTS nicht als Produkt unabhängiger Randchancen berechnen. Keine separate
skalare Nachkalibrierung einzelner Linien, die diese Konsistenz zerstört.

### 3. Neue Marktidentität und Rückzahlungen

Separater Namensraum `TIMEWIN_…`, etwa `TIMEWIN_1_30_AWAY_UNDER_0_5`.
Nicht mit `TOTAL_…`/`HOME_…`/`AWAY_…` anfangen: der alte Resolver könnte daraus
sonst eine 90-Minuten-Quote machen. Zeitfenster, kumulativ/Abschnitt, Teamrolle,
Linie, Richtung und Abrechnungs-/Zeitregelversion sind Teil der Identität.
Endpunkte ausschließlich 15/30/60/75. Unterstützte Linien 0,5/1/1,5/2/2,5/3;
keine Viertellinien im ersten Umfang. Anbieterangebot und Statistik entscheiden,
welche dieser Kombinationen tatsächlich als Tipp erscheinen.

Halbe Linien: Gewinn/Verlust. Ganze Linie k: Über gewinnt bei N>k, Rückzahlung
bei N=k, Verlust bei N<k; Unter entsprechend umgekehrt. Eigene Ergebniszustände
WIN/PUSH/LOSS/VOID/UNRESOLVED. PUSH ist kein Verlust und keine Absage.
`p_win+p_push+p_loss=1`; Erwartungswert bei Quote d:
`p_win*(d-1)-p_loss`, faire Quote `(1-p_push)/p_win`.
Nicht `1/p_win` und keine umdeklarierte bedingte Gewinnchance anzeigen.

Alte Ticket-/HMAC-/Geldverträge bleiben byte-identisch. Neue Zeitmarkt-Ergebnisse
und Prognosemetriken separat versioniert in zusätzlichen Tabellen derselben
Prognose-Beleg-DB, nicht in alte boolesche Ergebniszeilen schreiben. Keine
automatische Echtgeld-Abrechnung über einen alten Vertrag. Eine spätere
manuelle Erfassung muss den tatsächlichen Rückzahlungsbetrag korrekt buchen;
gesonderte zeitmarktgebundene Beleg-/Buchungsadapter sind vor Freigabe zu testen.
M, Zeitanteile und der gemeinsame Trainingsmanifest-Verweis werden je Spiel/
Modellrevision einmal gespeichert und von den Zeitmärkten referenziert. Keine
komplette Historie oder wachsende Referenzliste je Linie erneut serialisieren.
Erhaltene historische Belege müssen ihre damals verwendeten Eingaben behalten,
auch wenn sich der aktuelle veränderbare Timeline-Cache später korrigiert.

### 4. Historischer Nachweis

Chronologischer Walk-forward: M, dessen Kalibrierung und sämtliche Torzeit-
Kurven jeweils nur aus Informationen vor dem damaligen Spiel gewinnen. Ein
heutiger Modellcache darf nicht rückwirkend für alle historischen Spiele gelten.
Nachträglich beschaffte historische Ereignisse sind eine retrospektive Prüfung,
kein vorgetäuschter damals beobachteter Live-/Shadow-Beleg.

Gleiche Spiele nicht durch vier Zeitfenster zu vier unabhängigen Spielen zählen.
Training gewichten, Holdout nicht stillschweigend nachträglich umgewichten.
Je Markt/Zeitraum eigene Kalibrierungs- und Vergleichswerte gegen eine ausschließlich
historische expandierende Ligabasis; Mehrfachtests und Spielcluster berücksichtigen.
PUSH in Stichprobe und mehrklassigem Brier-Score berücksichtigen; VOID/offene Fälle
getrennt. Mindestens 200 unabhängige Testspiele zusätzlich zu Training/Abstimmung
für einen freizugebenden Zeitmarkt; fehlende Teilklassen offen ausweisen.
Eine fehlende Wirksamkeit nicht mit zusätzlichen Softwaretests überspielen.
Rendite nur aus tatsächlich historischen exakten Zeitmarkt-Quoten behaupten;
heute geholte Preise sind keine damaligen Abschlussquoten.

### 5. Exakte Preise und Darstellung

Neuer expliziter Quotenvertrag mit nativer Markt-ID **und** Namen/Wert, Fixture,
Anstoß, Teamrolle, Zeit-/Nachspielzeitregel, Linie, Buchmacher-ID, Anbieter- und
Empfangszeit. Native 144 Yes/No darf erst nach bestätigter Abrechnungskonvention
als bis-15 Über/Unter 0,5 dienen. Keine Preise aus anderen Intervallen,
Halbzeiten, 1X2 oder getrennten Märkten kombinieren/umetikettieren.
Bestehende Pagination, Zeitgrenzen, Diagnosen und Budgetschutz wiederverwenden.
Kein nachgewiesener Preis: Statistik im Spielblock, kein bepreister Haupttipp.
Öffentliche Zeit-Tipps nur mit exakt passendem Anbieterpreis ab 1,20.

Ein gemeinsamer kleiner Block „Torzeiten“ in den vorhandenen Spielkarten:
Tore/Gegentore je Phase, tatsächliche 5-/10-Spiele-Häufigkeiten, Basisstichprobe
und ein kurzer passender Grund. Keine Modellnamen, Forschungsprosa oder
erfundenen Prozentwerte. Größerer Trainingsbestand bleibt in internen Details.
Zeitmarkt-Auswahlen dürfen keine gesonderte widersprüchliche Rangliste erzeugen.
Wettfinder/manuelle Suche nutzen den neuen Adapter; gemeinsame Statistiken auch
in Daily3/RisikoBet/15K. Aufnahme in deren Auswahl-/Erfassungsverträge erst mit
derselben Zeitidentität und korrekter PUSH-Abrechnung, nie durch alte Markt-IDs.
Die bekannte Lücke „verdeckter Hauptmarkt, höchste sichtbare Alternative wirkt
wie Haupttipp“ bleibt separat offen und darf durch diese Funktion nicht als
erledigt ausgegeben oder im neuen Adapter übernommen werden.

## Abnahme und Veröffentlichung

- Reale vollständige Torverläufe plus belegte 0:0-Spiele; kein fehlender Abruf als Null.
- Grenzfälle 15/30/45+/60/75/90+, gleiche Minute, VAR, Eigentor, verschossener
  Elfmeter, Abbruch, falsches Team, Anstoßänderung und spätere Revision getestet.
- Normierung, monotone Grenzen, exakte Endstandidentität, abhängiges BTTS und
  jede Gewinn/Rückzahlung/Verlust-Grenze unabhängig gegen Handbeispiele geprüft.
- Zeitlich getrennte historische Prüfreports mit tatsächlichen Fixture-Zahlen,
  Fehlern, Ausschlüssen und unverändertem Testbestand; keine Ergebnis-Auswahl.
- Falsche Intervalle/Teamrollen/Markt-IDs/Quotenzeiten werden nachweislich abgelehnt.
- Alle alten 96 Wahrscheinlichkeiten, v14/40-Fit-Ziele und Ticket-/Geldhashes unverändert.
- UI in Desktop/Mobil mit echter Interaktion; verständliche, kompakte Statistiken.
- Speicher-/API-Budget, Wiederanlauf, Parallelität und Quellen-Deduplizierung geprüft.
- Danach vollständige Offline-Suite und unabhängiges Review, gezieltes Commit,
  main-Push, geprüftes VPS-Fast-Forward ohne Backup; keine ungeprüfte Alt-Updateroutine.
- Echte reguläre Veröffentlichung, Dienststatus, Healthchecks und Commitgleichstand
  nachweisen. Nicht verfügbare Zeitquoten bleiben konkrete offene Abdeckung,
  niemals durch einen allgemeinen „alles fertig“-Status verdecken.

## Quellen

- API-Football: https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide
- Buchmacher-Zeitgrenzen: https://tn.1xbet.com/web-api/rulespdf, Fußballregeln 20–23.
- Lokale Eigentümer: api_football.py, challenge_engine.py, market_consensus.py,
  forecast_evidence.py, redcard_history_harvester.py, xg_backfill.py und
  context_sources/outcomes.py. Diese Pfade sind Integrationsstellen, keine Behauptung
  einer bereits vorhandenen produktiven Zeitmarkt-Funktion.
