# Doppelchance nach Liga – 26.11.2026

Ausgewertet: 07.–25.11.2026 (Spieltag Europe/Zurich) aus bereits vorhandenen Produktionsdaten.
Keine API-Abfrage, kein Modelllauf, kein Backup, keine Änderung an App oder Server.

## Befund

| Markt | Treffer | Modell erwartet | Deskriptives 95-%-Wilson-Intervall der Trefferquote |
|---|---:|---:|---|
| 1X | 42/60 | 42,27 | 57,5 % bis 80,1 % |
| X2 | 28/52 | 36,02 | 40,5 % bis 66,7 % |
| 12 | 15/16 | 12,10 | 71,7 % bis 98,9 % |

Bei X2 gab es 24 statt 15,98 erwartete Heimsiege. Das zeigt sich in beiden
Zeitabschnitten: 07.–19.11. 8 von 21 statt erwarteter 6,16 Heimsiege;
20.–25.11. 16 von 31 statt erwarteter 9,82. Ligue 2 und Allsvenskan je
3 statt rund 0,9 Heimsiege, Championship 2 statt 2,90.
Bei 1X liegt das Ergebnis im Gesamtbestand praktisch auf der Modellprognose;
bei den Haupttipps trafen nur 5/8 statt erwarteter 6,15. 12 traf 15/16, aber
acht der 16 stammen aus der türkischen 1. Lig.

Die Marktformel X2 = 1 − P(Heimsieg) und die 90-Minuten-Abrechnung stimmen.
`challenge_engine._fixture_model` mischt 75 % spielortbezogene Saisonraten
mit 25 % all-venue Formraten. In einem kontrollierten Beispiel mit zwei
gleich starken Teams und alternierendem Heimrecht (36 Spiele, jeweils 2:1
aus Heimsicht) reduziert die Mischung die Torgewichte von 2,00/1,00 auf
1,875/1,125. Die unkalibrierte X2-Chance steigt dadurch von 39,43 % auf
45,11 %. Das reproduziert einen möglichen Mechanismus, aber keine
kausale Erklärung für die tatsächlichen 52 Fälle.

Für die geprüfte Produktionsversion fehlen die Originale mit rohen und
kalibrierten Wahrscheinlichkeiten vor derselben Veröffentlichung:
257 B1-Bindungen im Bestand; die neueste ist vom 05.11. um
07:22 UTC, null ab 07.11. Der aktuelle Aufnahmestand meldet
`total_limit` (131.493.335 Bytes bereits verbucht). Ohne echte Paarung
lässt sich der Einfluss der Formmischung nicht vom Einfluss der
Kalibrierung oder der Vorauswahl trennen. Keine Schätzung fehlender
Originale; kein Öffnen des vorab festgelegten Heimvorteil-Tests.

**Entscheid:** Keine Änderung an Wahrscheinlichkeiten, Sortierung oder
Märkten, kein Commit, Push oder Deploy. Der nächste entscheidende
Nachweis ist der ligagleiche Vergleich von bisheriger und alternativer
Torverteilung auf denselben vor Anpfiff belegten Prognosen und getrennten
Spieltagen; nicht dieselbe Stichprobe zum Anpassen und Freigeben benutzen.

Technischer Gegencheck: Die drei geprüften Modell-/Abrechnungsdateien haben
dieselben Git-Inhaltskennungen wie die Produktion (`4ca4b6c`). 106 gezielte
Tests bestanden im bereinigten Windows-Temporärpfad; der verbliebene,
in der Sandbox blockierte Hardlink-Test bestand separat ausserhalb der
Sandbox. Diese Tests prüfen den Code, nicht die Prognosegüte.

## Methode und Ligatabellen

`consumer_tip_performance` verbindet die erste archivierte Wettfinder-Auswahl
je Partie, Markt und Seite mit einem zeitlich gültigen Endergebnis. Nur
entschiedene Zeilen der Version `challenge-engine:legacy-form-strength-joint-calibration-v1`
sind enthalten. Marktzeilen derselben Begegnung sind abhängig. Die Haupttipp-Kohorte
hat eigene, explizite Rollenbelege; sie kann Preisaktualisierungen enthalten und
ist keine nachträgliche Auswahl aus dem Katalog. In der Zeit 07.–19.11. fehlt
ein auswertbarer Haupttipp-Beleg für Doppelchance, nicht zwingend die Anzeige.
Die Intervalle beschreiben die beobachteten Quoten näherungsweise; Spieltags-
und Ligenabhängigkeit sowie die Auswahl der publizierten Märkte begrenzen
die Verallgemeinerung. Keine Wett-Rendite abgeleitet.

Die Ligabindung erfolgt über die native Fixture-ID mit übereinstimmenden
Heim-/Auswärtsrollen und Anstoßzeit (höchstens 60 Minuten Differenz zum
Shadow-Spielplan); zusätzlich wurden vorhandene native Basisbelege nach
exakter ID, Teamrollen und Zeit gesucht. Katalog: 127 von 128 Zeilen
in 36 Wettbewerben gebunden, Haupttipps: 19 von 20. Die eine fehlende
Liga-Zuordnung bleibt in den Gesamtsummen enthalten.

Lesart: Treffer/entschiedene Auswahlen (erwartete Treffer). „–“ = kein
auswertbarer Fall im jeweiligen Archiv, nicht null Treffer.

### Wettfinder-Katalog

| Wettbewerb | 1X | X2 | 12 |
|---|---:|---:|---:|
| Belgium / Challenger Pro League | 1/1 (0,75) | 1/2 (1,38) | – |
| Belgium / Jupiler Pro League | 1/1 (0,79) | – | – |
| Brazil / Serie A | 1/1 (0,72) | 1/2 (1,49) | – |
| Bulgaria / First League | 2/2 (1,41) | – | – |
| Chile / Primera Division | 0/2 (1,33) | 0/1 (0,63) | – |
| Colombia / Primera A | 1/2 (1,42) | 0/1 (0,65) | – |
| Cyprus / 1. Division | 1/1 (0,69) | – | – |
| Czech Republic / Czech Liga | 0/1 (0,65) | 2/3 (1,99) | – |
| Denmark / Superliga | – | 1/1 (0,64) | – |
| England / Championship | 3/3 (2,08) | 6/8 (5,10) | – |
| England / League Two | 3/3 (2,12) | 1/2 (1,33) | – |
| England / Premier League | 5/6 (4,36) | 0/1 (0,73) | – |
| Finland / Veikkausliiga | 1/1 (0,79) | 1/1 (0,65) | – |
| France / Ligue 1 | 0/1 (0,64) | – | – |
| France / Ligue 2 | 0/1 (0,67) | 0/3 (2,07) | – |
| Germany / 3. Liga | 3/3 (2,01) | – | – |
| Germany / Bundesliga | – | 1/2 (1,27) | – |
| Greece / Super League 1 | – | 1/1 (0,68) | – |
| Israel / Ligat Ha'al | 0/1 (0,61) | – | – |
| Italy / Serie A | 1/1 (0,70) | 3/4 (2,83) | – |
| Italy / Serie B | 2/4 (2,85) | 1/1 (0,67) | – |
| Mexico / Liga MX | 1/1 (0,64) | – | – |
| Netherlands / Eredivisie | – | 0/1 (0,74) | – |
| Norway / 1. Division | 2/2 (1,40) | 1/3 (2,20) | – |
| Norway / Eliteserien | 3/5 (3,36) | 3/5 (3,64) | – |
| Portugal / Primeira Liga | 0/1 (0,78) | – | – |
| Romania / Liga I | – | 1/1 (0,73) | 2/2 (1,50) |
| Scotland / Premiership | 1/3 (2,08) | – | 4/4 (3,05) |
| Serbia / Super Liga | 2/2 (1,50) | – | – |
| Spain / La Liga | 0/1 (0,63) | – | 2/2 (1,48) |
| Spain / Segunda División | 0/1 (0,74) | 1/1 (0,75) | – |
| Sweden / Allsvenskan | 3/3 (2,14) | 0/3 (2,14) | – |
| Switzerland / Super League | – | 1/2 (1,43) | – |
| Turkey / 1. Lig | 3/3 (2,18) | 1/1 (0,80) | 7/8 (6,08) |
| Ukraine / Premier League | 1/2 (1,60) | – | – |
| World / UEFA Champions League | 1/1 (0,64) | 0/1 (0,72) | – |
| Keine sichere Liga-Zuordnung | – | 1/1 (0,74) | – |

### Belegte erste Haupttipps

| Wettbewerb | 1X | X2 | 12 |
|---|---:|---:|---:|
| Belgium / Challenger Pro League | 1/1 (0,75) | – | – |
| Belgium / Jupiler Pro League | 1/1 (0,79) | – | – |
| Brazil / Serie A | – | 0/1 (0,78) | – |
| France / Ligue 2 | – | 0/1 (0,75) | – |
| Italy / Serie B | 0/2 (1,49) | – | – |
| Norway / Eliteserien | – | 1/2 (1,59) | – |
| Romania / Liga I | – | – | 1/1 (0,73) |
| Scotland / Premiership | – | – | 1/1 (0,79) |
| Spain / Segunda División | – | 1/1 (0,75) | – |
| Sweden / Allsvenskan | 1/1 (0,75) | 1/1 (0,74) | – |
| Turkey / 1. Lig | 1/1 (0,78) | 1/1 (0,80) | 1/1 (0,79) |
| Ukraine / Premier League | 1/2 (1,60) | – | – |
| World / UEFA Champions League | – | 0/1 (0,72) | – |
| Keine sichere Liga-Zuordnung | – | 1/1 (0,74) | – |
