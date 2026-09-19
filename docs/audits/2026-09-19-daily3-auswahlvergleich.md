# Daily3: Vergleich statt Rangfolge nach Rohwahrscheinlichkeit

## Anlass und Ursache

Der Nutzer beanstandete die Daily3-Auswahlen IMT unter 2,5 Teamtore,
Chapecoense unter 2,5 Teamtore und Molde über 0,5 Teamtore. Die mit `1985407`
eingeführte Regel sortierte tatsächlich die größte Modellwahrscheinlichkeit
zuerst. Ein Test verlangte sogar, dass drei einfache Über-0,5-Märkte andere
Märkte verdrängen. Das war ein Produktfehler, keine fehlende Quote.

## Geänderte Regel – Funktionscommit 0a54313

- Weiterhin höchstens drei verschiedene Spiele, keine Gegenwetten,
  keine Quote als Auswahl- oder Sortierkriterium und kein erzwungenes CHF150-Ziel.
- Zusätzlich zur bisherigen Frische/Identität/Erklärung mindestens 70 Prozent
  in jedem vorhandenen Spiel-, Saison- und Formmodell. Keine erfundene
  individuelle Wahrscheinlichkeitsuntergrenze.
- Bereits im normalen Modelllauf geladene Endstände derselben Liga liefern
  die historische Häufigkeit exakt desselben Marktes. Mindestens 200 eindeutige
  abgeschlossene Beobachtungen; keine zukünftigen Spiele, laufenden Spiele,
  Verlängerungsergebnisse, anderen Ligen oder widersprüchlichen Duplikate.
- Der konservativere der drei Modellwerte muss über dem oberen Wilson-Endpunkt
  der historischen Häufigkeit liegen. Nach dieser Differenz wird sortiert;
  Vielfalt ist Gleichstandsauflösung. Der Wilson-Endpunkt beschreibt allein
  die binomiale Vergleichshäufigkeit, nicht die Unsicherheit der Modellchance.
- Bestehende zeitgetrennte Marktvalidierung muss unterstützt und versionsgleich
  sein. Event, Teilnehmer, Markt, Zeitpunkt und aktive Wahrscheinlichkeit sind
  an dieselbe Analyse gebunden. Kein nachträgliches Aufwerten alter Analysen.
- Über 0,5 oder Unter 1,5/2,5 werden nicht pauschal verboten. Eine breite Torlinie
  gewinnt aber nicht mehr automatisch wegen ihrer größeren Rohwahrscheinlichkeit.
- Kompakte Vergleichszeile je Auswahl; Regeln optional. Echtgeldbuchungen,
  Einsatzgrenzen, alte Tickets, Modellwahrscheinlichkeiten und normale
  Prognosekataloge bleiben unverändert.
- Keine zusätzliche API-Abfrage im Vergleichsbaustein. Nur kleine aggregierte
  Zähler und drei Modellwerte, keine zweite gespeicherte Spielhistorie.

## Grenzen ausdrücklich offen

Diese Auswahlregel ist noch kein historisch nachgewiesener Wettvorteil und
keine empirisch bestätigte Verringerung des Verlustrisikos. Wiederholte Teams,
Abhängigkeiten zwischen Spielen und die nachträgliche Auswahl aus vielen
Märkten werden durch das Wilson-Intervall nicht gelöst. Die 70-Prozent- und
200-Spiele-Grenzen sind Auswahlregeln, keine Gewinnzusagen.

Der Vergleichsproduzent ist bislang nur für Fußball angebunden. Tennis und
E-Sport erhalten nicht ersatzweise eine erfundene 50-Prozent-Basis; ohne
passenden gespeicherten Vergleich gibt es dort derzeit keine Daily3-Auswahl.
Das ist eine engere Daily3-Auswahl als zuvor und wird in den optionalen Regeln
benannt. Der normale Wettfinder behält diese Sportarten und ihre Prognosen.
Andere Sportarten, UEFA-Transfermodelle und fehlende Vergleichsdaten werden
hiermit nicht als fertiggestellt behauptet. Cricket bleibt unverändert.

Vollständig angewendete und empirisch belegte Verletzungs-/Müdigkeitseffekte
sind durch diesen Patch nicht hergestellt. Deren Einschränkungen bleiben
direkt am Spiel sichtbar. Ein einfacher Markt kann weiterhin sachlich gewinnen;
eine pauschale Garantie, bestimmte Markttexte nie mehr anzuzeigen, wäre falsch.

## Prüfnachweise

- Erster Auswahlpatch: Worktree 1.010 Tests/111 Untertests, main mit Marktumfang
  1.035 Tests/111 Untertests. Nach dem unten beschriebenen realen Refresh-Befund:
  **1.090 Tests/111 Untertests** im Worktree (32,54 Sekunden) und unverändert auf
  main (33,09 Sekunden). Kein neuer vollständiger 10k-Gesamtlauf.
- Regressionsfälle: bisheriges Fluten mit breiten Linien, echte Alternative,
  erlaubter einfacher Markt mit passendem Vergleich, keine erzwungenen drei,
  fehlende/fremde/zu alte/versionsfremde Nachweise, Modellwiderspruch,
  Duplikate, historische negative CSV-IDs, unveränderte Prognose-/Preisdaten,
  begrenzte Metadaten, Kontextrefresh sowie Geld-/Identitäts-/Abrechnungsschutz.
- Vergleich aktiviert/deaktiviert: genau ein bestehender Modellaufruf pro
  Kandidatenerzeugung; sämtliche bisherigen Kandidatenfelder identisch.
- Streamlit-AppTests für gefüllt/leer, Anzeige, Preise und Buchungsschutz grün.
- Interner Browser zweimal an `apply deny-read ACLs` vor Tab-Erzeugung
  gescheitert, auch nach Reset. Kein externer Browser geöffnet. Deshalb keine
  neue visuelle Desktop-/Mobile-Abnahme behaupten. Lokale Vorschau mit klar
  synthetischen Daten: `tests/fixtures/daily3_comparison_preview.py`.

## Zusätzlicher echter Refresh-Fehler – Funktionscommit 533a98f

Der alte VPS-Lauf meldete `Context RuntimeError: model refresh could not
recompute every requested fixture`. Dadurch wurden auch erfolgreiche Modelle
derselben Gruppe verworfen. Im Artefakt von 14:31 CEST standen alle 404
Fußballprognosen weiterhin auf dem Modellstand von 11:42 CEST; sämtliche
107 Prognosen mit mindestens 70 Prozent waren deshalb für Daily3 veraltet.
Das trat vor dem neuen Auswahlpatch auf und ist keine Quotenentscheidung.

- Der Refresh liefert jetzt berechnete, bestätigte ungültige und nicht
  berechenbare Spiele getrennt. Nur tatsächlich berechnete Spiele erhalten
  neue Prognosen und Modellzeitstempel. Bestätigte Absagen werden entfernt.
- Fehlgeschlagene Spiele behalten ihre bisherigen Daten in sämtlichen Pools;
  ihr Prüfversuch ist kein neuer Modellstand. Keine rückwirkend erfundenen Werte.
- Fehlende Modelle bleiben als Fehler je Spiel erfasst, auch wenn die nächste
  Gruppe erfolgreich ist. Erst eine erfolgreiche Neuberechnung oder bestätigte
  Ungültigkeit beseitigt den betreffenden offenen Fehler.
- Unvollständige Provider-Eingaben oder falsche Teilnehmeridentitäten brechen
  weiterhin ab; der Patch lockert diese Eingangsverträge nicht.
- 14 gezielte Regressionen, inklusive zuerst reproduziertem Gruppenabbruch,
  fremden/überlappenden IDs, leeren Gruppen, späteren Reparaturen und Absagen.

## Betriebsnachweis und echter Ausgabevergleich

GitHub main bestätigt auf `533a98f635c2f386d4e2a4c40193d1b56734d3b8`.
Beide Funktionscommits sind erfolgreich auf den VPS übernommen, zuletzt exakt
`533a98f`. App und interne/öffentliche Healthchecks bestätigt. Der alte Job wurde
für den zweiten Codewechsel über systemd geordnet beendet (SIGTERM/15, kein
erfolgreicher Lauf behauptet); der normale Wettfinder-Service läuft seit
15:01:07 CEST mit dem Folgepatch. Keine zweite parallele Datenpipeline.
Keine Archive, Bereinigungen, Dependencies oder Datenbankschemata verändert.
Tagesbackup bleibt deaktiviert. Die bestehende morgendliche Tennis-Service-
Fehlermeldung wurde nicht als durch diesen Auswahlpatch repariert ausgegeben.

Eine zusätzliche rein funktionale Linux-pytest-Prüfung war nicht möglich:
Die Produktionsvenv enthält kein pytest. Keine Pakete nachinstalliert.
Das eigens erzeugte leere QA-Verzeichnis wurde nichtrekursiv entfernt;
keine Produktions- oder Sicherungsdaten gelöscht. Windows-Tests und echter
Produktionslauf sind unterschiedliche Nachweise.

Der neue normale Lauf endete um **15:26:36 CEST**. Ergebniszeitpunkt im
veröffentlichten Artefakt: 15:17:04 CEST. **51 Spiele wirklich neu modelliert**;
9 weitere konnten nicht neu modelliert werden. Genau diese neun bleiben als
offene Modellfehler erhalten. Der Dienst endet deshalb ehrlich mit Exit 1 /
Teildaten, nicht mit einer erfundenen vollständigen Freigabe. Die Fehler der
neun Spiele wurden durch diesen Patch nicht fachlich behoben; ihre erfolgreiche
Nachmodellierung beziehungsweise konkrete Eingangsdatenursache bleibt offen.

Read-only-Vergleich um **15:27 CEST**, dieselben unveränderten frischen
Prognosen unter beiden Auswahlregeln:

| Alte Regel (Rohwahrscheinlichkeit zuerst) | Neue Regel (historischer Vergleich) |
| --- | --- |
| Vojvodina–IMT: IMT unter 2,5; 95,34 % | KR Reykjavík–Víkingur: Gesamt über 2,5; 81,57 % |
| Atlético-MG–Chapecoense: Chapecoense unter 2,5; 90,84 % | Örgryte–Sirius: Sirius über 0,5; 82,38 % |
| Molde–Aalesund: Molde über 0,5; 90,75 % | Remo–Santos: Santos über 0,5; 76,42 % |

Damit reproduziert die alte Regel auf dem neuen Bestand exakt die drei
beanstandeten Markt-/Spielpaare. Die neue Regel wählt tatsächlich anders,
nicht nur in erfundenen Testdaten. **Zwei Team-Über-0,5-Auswahlen bleiben**:
Es wurde ausdrücklich kein Marktverbot eingeführt und keine vollständige
Eliminierung einfacher Märkte behauptet. Die Torerwartungen liegen bei
Örgryte/Sirius 1,372/1,765 und Remo/Santos 1,396/1,473; insbesondere Santos
wird nicht als haushoher Favorit konstruiert.

Der neue Vergleich zeigt mindestens 80,9 % gegenüber 64,7 % historischer
Markthäufigkeit (300 Spiele) für das Reykjavík-Total; 81,7 % gegenüber 71,0 %
(410) für Sirius; 74,8 % gegenüber 65,8 % (647) für Santos. Diese Unterschiede
sind Modell-/Häufigkeitsvergleiche, kein belegter Buchmacher- oder Gewinnvorteil.

298 sichtbare Prognosen, darunter 296 Fußballprognosen mit gespeichertem
Vergleich. Datei rund 12,02 MB, zuvor 11,80 MB; darin sind auch die übrigen
normalen Datenaktualisierungen enthalten. Keine großen Historienlisten
für den Vergleich kopiert. Prüfskript lokal unter
`output/playwright/daily3-comparison-live-audit-20260919.py`; es führt die
vorherige Auswahlregel aus Git-Commit 5be83cf nur lesend im Speicher aus.

App und Caddy aktiv; sechs Rechentimer und Retention aktiv, Tagesbackup
disabled/inactive. Interner und öffentlicher Healthcheck `ok`.
Die echte Browserdarstellung bleibt wegen des genannten internen Browser-
Startfehlers ungeprüft. Die vorhandenen Warnungen zu nicht angewendeten
Ausfallwirkungen bleiben unverändert; bessere reale Treffer-/Gewinnqualität
ist weiterhin nicht bewiesen.
