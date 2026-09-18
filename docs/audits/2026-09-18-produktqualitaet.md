# Produkt-Audit: Auswahl, Widersprüche und Datenwirkung

Stand: 18.09.2026, Live-Prüfung 22:05–22:08 CEST. Geprüfter Code lokal und VPS:
`c64218bdf6bb81dfa1a107e2da13de2a35178935`.

## Urteil und Umfang

Die technische Auslieferung ist nicht das Hauptproblem dieser Beschwerden.
Es bestehen bestätigte fachliche Fehler und unerledigte Kernfunktionen.
Einzelne Modellprognosen sind berechenbar; daraus folgt weder eine belastbare
TOP-Rangfolge noch nachgewiesene bessere Wettqualität.

Geprüft: automatischer Wettfinder, Daily3, zugehörige Daten-/Auswahlpfade,
ausgewählte RisikoBet- und Fußball-/Tennis-Kontextpfade. Zwei unabhängige
lesende Gegenprüfungen ergänzten Live-Replay und lokale Speicher-Reproduktionen.
Kein neuer Suchlauf, kein Eingriff in Geldkonten, keine Code-/VPS-Änderung.
Nur dieser Bericht wurde angelegt; nicht committed oder veröffentlicht.

Grenzen: Browsersteuerung scheiterte bereits beim Start an einem lokalen
Sandbox-ACL-Fehler. Deshalb keine neue visuelle, responsive oder Tastatur-
Abnahme. UX-Aussagen beziehen sich auf Nutzerausgaben und geprüfte Renderer,
nicht auf behauptete neue Screenshots. Live/15K-Abrechnung und sämtliche
Sport-/Marktkombinationen wurden nicht vollständig erneut auditiert.
Cricket bleibt ausdrücklich ausgenommen. Kein neuer Volltestlauf.

## Eingefrorener Produktionsbeleg

Öffentlicher Prognosebestand `runtime_state/wettfinder_latest.json`:

- Veröffentlichung: `2026-09-18T19:42:03.466581+00:00` (21:42 CEST).
- SHA256: `46b205de490338636968cd274cbaea00058e430836fb6d9458c37fb9d7b75de6`.
- `run_status=completed`, `operational_error_count=0`.
- Fußball: 42 Spiele gefunden, 24 modelliert; Entdeckung 00:11 CEST,
  Kontextaktualisierung 21:42 CEST. Fünf verbleibende Fußballmärkte gehören
  sämtlich zu Spiel 1549783, Águilas Doradas gegen Deportivo Pereira, 23:00.
- Alle fünf haben denselben Modell-/Inputzeitpunkt
  `2026-09-18T19:37:38.598941+00:00`, denselben Scope und dieselbe Policy.
- E-Sport wurde zum Publikationszeitpunkt ebenfalls ausgespielt; bei der
  Gegenwartsprojektion um 22:05 war dessen Spiel bereits begonnen und wurde
  korrekt entfernt. Das historische Replay nutzt den echten gespeicherten
  Veröffentlichungszeitpunkt, keine erfundene Aktualisierung.

| Markt desselben Fußballspiels | Wahrscheinlichkeit | Verwendung |
| --- | ---: | --- |
| Auswärtssieg | 19,5253 % | TOP im normalen Wettfinder |
| Heimsieg | 55,1276 % | durch gewählte Gegenrichtung entfernt |
| X2 und unter 3,5 | 39,1263 % | weitere Auswahl |
| X2 | 45,4140 % | weitere Auswahl |
| 1X | 80,6871 % | Daily3-Auswahl |

## Bestätigte Befunde

### F1 — P1: Historische Modellgüte wird zur konkreten TOP-Empfehlung

`challenge_engine.py:522-555` bildet zuerst historische relative Verbesserung
mal Evidenzgewicht. Diese erste lexikografische Rangkomponente ist für
Auswärtssieg `0.039993768`, für Heimsieg `0.039494984`. Dieser kleine Unterschied
entscheidet vor allen weiteren Komponenten. Die Oberfläche übernimmt diese
Richtung und vergibt TOP anhand der Platzierung, nicht aufgrund eines belegten
spielbezogenen Vorteils (`wettfinder_surface.py:490-514,541-565,584-589`).

Live reproduziert: TOP Auswärtssieg, während die unmittelbar angezeigte
Begründung 0,9 erwartete Auswärtstore gegen 1,41 Heimtore und 80,5 % Gegenrisiko
nennt. Das macht einen Auswärtssieg nicht unmöglich. Es erklärt aber nicht,
weshalb gerade dieses Außenseiterszenario hervorgehoben wird.

Abnahme: Prognose und Hervorhebung getrennt qualifizieren. Historische
Marktgüte allein darf nicht als konkreter Spielvorteil erscheinen. Jede
Hervorhebung braucht nachvollziehbare, spielbezogene Gründe und Gegenargumente.
Nicht pauschal nach höchster Trefferchance sortieren: Das würde erneut triviale
Märkte bevorzugen. Keine Quote als Prognosefilter verwenden.

### F2 — P1: Widerspruchsschutz endet an der einzelnen Ansicht

`wettfinder_surface.py:561-565` übernimmt den ersten bevorzugten Kandidaten
als Richtung. `daily3_selection.py:143-164` verwendet dagegen eine eigene
Richtungsauswahl und danach Vielfalt, Aktualität, Beginn, Event und Schlüssel.
Beide konsumieren denselben Prognosebestand (`app.py:4729-4748`,
`daily3_ui.py:165-168,213`).

Live: normaler TOP Auswärtssieg und Daily3 1X schließen sich beim selben Spiel
gegenseitig aus. Der bestehende Test
`tests/test_wettfinder_surface.py:752-765` prüft die Entfernung einer späteren
Gegenrichtung innerhalb eines Katalogs, nicht diese bereichsübergreifende
Empfehlungssituation. Daily3 ist außerdem keine nachgewiesene Rangliste der
fachlich besten drei Auswahlen; bei gleichzeitigen unterschiedlichen Märkten
kann der Schlüssel den Ausschlag geben.

Abnahme: denselben eingefrorenen Bestand gleichzeitig durch alle Empfehlungs-
ansichten führen. Gegensätzliche Szenarien nicht unkommentiert als gemeinsame
Handlungsempfehlungen anbieten. RisikoBet darf bewusst Alternativszenarien
zeigen, muss deren abweichenden Zweck kenntlich machen. Gemeinsame Modelle
sind erwünscht; mehrfaches unabhängiges Berechnen ist keine Lösung.

### F3 — P1: Kalibrierte Marktchancen sind nicht gemeinsam konsistent

Die oben dokumentierten komplementären Ereignisse ergeben:

- Auswärtssieg + 1X = **100,2124 %**.
- Heimsieg + X2 = **100,5416 %**.

Beide Paare müssen bei identischem Spiel-/Zeitumfang 100 % ergeben. Das liegt
weit über der Rundung auf sechs Nachkommastellen. Die Karten erzeugen ihre
Gegenrisiken zusätzlich als `1-p`: daher passen die Gegenrisiken nicht zu den
separat veröffentlichten Gegenmärkten.

Ursache: `challenge_engine.py:1707-1713` kalibriert jeden Markt unabhängig und
stellt die gemeinsame Verteilung anschließend nicht wieder her. Unabhängige
Speicher-Reproduktion mit den vorhandenen Fit-Funktionen: Rohkomplemente
summieren sich zu 1, nach Kalibrierung zu `1.013175438596491`.

Abnahme: konsistente Wahrscheinlichkeiten aller betroffenen Märkte aus einer
gemeinsamen qualifizierten Verteilung; Komplement-, Summen- und Teilmengen-
invarianten nach Kalibrierung testen. Ein bloßes Überschreiben der Anzeige oder
nachträgliches Normieren einzelner Paare ersetzt keine Modellvalidierung.

### F4 — P1: Alte, unbegründete Prognosen können TOP sein

Echter Produktions-Replay 21:42 CEST: Shopify Rebellion gegen Sentinels,
Modellzeit 08:23 CEST, also über 13 Stunden alt, wird TOP mit 69,2 %.
Die eigene Analyse lautet zugleich: „konkrete Modellgrundlagen fehlen in
diesem Datenstand“. Es liegen gespeicherte Elo-Evidenzfelder vor; der normale
Erklärungsrenderer nutzt sie für diese Karte nicht.

`ev_signal_sources.py:537-552` prüft Spielbeginn und Modellversion, nicht das
Alter des E-Sport-Modells. Die Gesamtdatei hat eine Frischegrenze
(`:875-881`), die wiederverwendete Einzelprognose dadurch aber keine neue
Datenbasis. `_select_featured` prüft weder Modellalter noch ausreichende
Begründung. `WettfinderCard` transportiert keinen Modellzeitpunkt.

Zusätzliche synthetische Reproduktion: 14 Stunden altes E-Sport-Signal ohne
konkrete Begründung wird TOP; Daily3 nimmt es nicht an. Kein alter Modell-
zeitpunkt wird in dessen TOP-Karte ausgegeben.

Abnahme: Dateierstellung, Modellberechnung, Datenstand und Kontextfrische
getrennt prüfen/zeigen. Keine unbegründete oder ungeprüft alte TOP-Aufwertung.
Prognosen dürfen als entsprechend gekennzeichnete Informationen erhalten
bleiben; das ist keine Quoten-Sperre.

### F5 — P2: Neue Tennisberechnung verdeckt alten Trainingsstand

`tennis/predict.py:174-188` schützt vor Zukunftsdaten, nicht vor unbegrenzt
alten Daten. `stats_through` wird bei Zeile 229 übernommen. Der Refresh
verwendet vorhandene Modelle und setzt eine neue Berechnungszeit
(`scripts/tennis_daily.py:722-728,847-851`). Daily3 prüft das Berechnungsalter,
aber nicht die tatsächliche Trainingsabdeckung (`daily3_selection.py:62-82,119-123`).

Speicher-Reproduktion mit bestehenden Testfixtures: Modell-/Trainingsdaten
aus Januar 2000 bestehen die Prognoseprüfungen bei neuer Berechnungszeit im
September 2026; die entsprechend aufgebaute Daily3-Auswahl wird angenommen.
Das ist ein Grenzfallnachweis, keine Behauptung über eine reale 26 Jahre alte
Nutzerkarte.

Tatsächlicher Live-Status: verfügbares WTA-Modell gebaut 10.09., Ergebnisse
bis **26.07.2026**; am 18.09. keine Tennis-Kandidaten. Es wurde somit keine
aktuell ausgespielte veraltete Tennis-Karte nachgewiesen.

Abnahme: tatsächliche Datenabdeckung neben Berechnungszeit darstellen und
eine begründete sport-/modellbezogene Aktualitätsregel prüfen. „Neu gerechnet“
ist nicht gleich „mit neuen Ergebnissen trainiert“.

### F6 — P1: Zwei verlangte Sportarten sind automatisch nicht angebunden

`wettfinder_automation.py:3311-3319` setzt Basketball und Eishockey fest auf
`live_only_no_prematch_model`, null Kandidaten, null Betriebsfehler. Der
Produktionsbestand bestätigt genau diese Zustände. Das ist keine Aussage,
dass der Tag keine passenden Spiele hatte: Der Vorab-Modellpfad fehlt.
Daily3 besitzt dafür ebenfalls keinen Erklärungsadapter.

Die normale Leeranzeige sagt nur, dass keine Modellprognose vorliegt
(`app.py:4803-4808`), und unterscheidet damit nicht ausreichend zwischen
„geprüft, nichts gefunden“ und „Vorab-Analyse nicht angebunden“.

Abnahme: Sportabdeckung verständlich und zutreffend ausweisen; danach echte
Daten-/Modellanbindung samt Ergebnisnachweis. Ein zusätzlicher Filterknopf
oder null Fehler ersetzt keine funktionierende Sportanalyse. Cricket bleibt
ausgenommen.

### F7 — P2: Daily3 unterschlägt die vorhandene Preiswarnung

`daily3_ui.py:234-243` baut eine Karte mit Preisstatus, zeigt aber nur die
Vergleichsquote und den allgemeinen Hinweis, die eigene Quote zu prüfen.
`price_label` und der bereits berechnete Status `TOO_LOW` werden verworfen.
Die Spezifikation verlangt ausdrücklich eine Warnung statt einer Sperre
(`docs/superpowers/specs/2026-09-13-daily3-design.md:168-171`).

Unabhängige speicherinterne UI-Aufzeichnung: Prognose 65 %, passende Quote
1,12, Mindestquote 2,00; Kartenstatus `TOO_LOW`/„Unter Value“, Daily3 zeigt
keine entsprechende Preiswarnung. Dies ist kein Nachweis, dass Geld falsch
abgerechnet wurde, und rechtfertigt keine neue Quoten-Zulassungssperre.

Abnahme: vorhandenen Preisstatus beim konkreten Angebot sichtbar machen;
Auswahl und Reihenfolge bleiben unverändert. Optional berechnete Auszahlungs-
angaben strikt von bestätigten Buchmacherabrechnungen trennen.

### F8 — P1, unerledigte Kernfunktion: Kontextprüfung ist noch keine Wirkung

Der normale Fußballpfad dokumentiert selbst `applied=False`,
`adjustment_pp=0.0` und `veto_only_no_validated_effect_size`
(`challenge_engine.py:2983-2995`). Der vorbereitete `original_capture`-Anschluss
wird in den betrachteten normalen Aufrufen noch nicht durchgereicht
(`challenge_15k.py:2554-2571`, `shadow_clv_automation.py:855`).

Tennis dokumentiert ebenfalls keine numerisch qualifizierte Belastungswirkung
(`tennis/workload.py:65-72`, `daily3_selection.py:81`). Die TennisAbstract-
Projektion übernimmt Matchdauer weiterhin nicht (`tennis/data_loader.py:775-792`).

Wichtig: Die geprüften aktuellen Texte erfinden daraus nicht pauschal einen
positiven Einfluss. Die offene Produktanforderung ist trotzdem erheblich:
Verletzungen/Müdigkeit sind noch nicht durchgehend mit echten Daten verbunden
und als wirksame Verbesserung qualifiziert. Fehlende Daten bleiben fehlend;
keine frei erfundenen Abschläge zur bloßen Erfüllung der Anzeige.

Abnahme: reale Quellen bis zur gleichen Modellrevision verfolgen; numerische
Wirkung auf die gemeinsame Verteilung und alle betroffenen Märkte belegen;
zeitlich getrennte empirische Abnahme bestehen. Softwaretests allein reichen
dafür nicht.

### F9 — P2, Legacy-Pfad: Tatsächliche Mindesterholung wird überbehauptet

`tennis/workload.py:68-72` kennt nur beobachtete Matches. Trotzdem nennt
`:131` die Zeit seit einem Ergebnisempfang eine tatsächliche Mindest-
erholung. `:110-113` wählt das vorherige Match nach geplantem Start.

Speicher-Reproduktion mit zwei gültigen Ergebniszeilen: ein früher angesetztes
Spiel mit Ergebnisempfang vor einer Stunde, ein später angesetztes mit Empfang
vor 48 Stunden; Ausgabe `minimum_recovery_hours=48.0`. Diese Daten belegen
weder vollständige dazwischenliegende Spielhistorie noch tatsächliche 48
Stunden Ruhe. Es wurde keine aktuelle Live-Karte mit diesem Satz nachgewiesen;
der Pfad verändert keine Wahrscheinlichkeit.

Abnahme: Zeit seit konkret beobachtetem Ergebnis nicht als bestätigte
tatsächliche Erholung ausgeben. Unvollständige Abdeckung und fehlende Endzeit
explizit erhalten; Fälle mit verschobenen Spielen/verspäteten Ergebnissen testen.

## Nicht als Fehler behauptet

- Eine einzige Daily3-Auswahl spät am Abend beweist allein keinen Suchfehler.
  Begonnene Spiele dürfen nicht nachträglich als spielbare Vorab-Auswahlen
  aufgefüllt werden. Keine drei künstlich erzeugten Tipps.
- Ein Außenseiter mit niedriger Chance kann ein legitimes Risiko-Szenario sein.
  Der Fehler ist die unbegründete TOP-Aufwertung, nicht jede Außenseiterchance.
- Fehlende/niedrige Quoten dürfen Prognosen nicht löschen oder umsortieren.
- „Sicherheitswert“ ist aktuell ausdrücklich als heuristischer Abschlag
  erklärt. Der Name bleibt missverständlich; eine statistische Untergrenze
  wurde in diesem Audit nicht nachgewiesen.
- Keine Aussage über realisierte Verluste, Profitabilität oder garantierte
  Gewinne: Dafür wurde hier keine unabhängige Ergebniskohorte ausgewertet.

## Reparaturfolge und notwendige Abnahme

1. F1–F4 gemeinsam absichern: fachliche Hervorhebung, widerspruchsfreie
   Handlungsrichtung, probabilistische Konsistenz und Einzelprognosenfrische.
2. F5/F7/F9: tatsächlichen Datenstand, Preiswarnung und Erholungsbelege ehrlich
   und unmittelbar verständlich darstellen.
3. F8 und F6: reale Kontextwirkung und fehlende Sportpfade fertig anbinden,
   anschließend empirisch qualifizieren — nicht durch Abschalten von Prüfungen.
4. End-to-End-Abnahme mit dem eingefrorenen Águilas/Pereira-Bestand plus
   Gegenbeispielen: umgedrehte Reihenfolge, anderer Preis, veraltetes Modell,
   fehlende Begründung, widersprüchliche Märkte, anderer Tab und Seitenwechsel.
5. Erst danach Render-/Desktop-/Mobilprüfung nachholen und Wirkung anhand
   bislang ungenutzter Ergebnisse messen. Commit/Push/Deployment sind eigene
   Schritte, keine Beweise für bessere Wettqualität.

Die vorhandenen Tests decken zahlreiche technische Regeln ab. Dieser Audit
belegt ausdrücklich Lücken zwischen diesen Regeln und der fachlichen
Nutzerentscheidung; er ist keine Vollabnahme der gesamten App.
