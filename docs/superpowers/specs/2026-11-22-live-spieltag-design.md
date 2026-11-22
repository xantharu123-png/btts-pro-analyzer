# Spieltag und Fußball-Liveansicht

Stand 22.11.2026. Bestätigt: Liga-Abdeckung wiederverwenden; alle fünf Minuten neue
Live-Spiele suchen, laufende jede Minute aktualisieren. Ziel: kommende Tipps oben,
Live-Spielstände und zugehörige Tipps nebeneinander ohne „Scannen“. Die 2.293
zusätzlichen Abrufe vom Samstag sind eine Schätzung aus Anstoßzeiten (105 Minuten
pro Spiel), keine gemessene Last des neuen Feeds oder zugesicherte Reserve.

## Vor Anstoß

- In der automatischen Liste, Tennisbox und im Doublebet gelten dieselben Rechte,
  Filter und Auswahlregeln wie bisher. Nur zukünftige Spiele mit gültigem
  Anstoßzeitpunkt sind neue Tipps. Bei 11:30 Anstoß ist das Spiel ab 11:30
  nicht mehr neu, auch in einem offen gebliebenen Tab (höchstens ein UI-Takt).
  Keine Sportabfrage, um die Uhr zu prüfen. Bestätigte neue Anstoßzeiten
  gelten bei der nächsten Veröffentlichung, kein Raten über Spielverlegungen.
- Ein unveränderlicher 3er bis 6er ist nach Beginn seines ersten Spiels als
  ganzer Schein nicht neu spielbar. Vollständig bevorstehende Scheine oben,
  bereits begonnene darunter eingeklappt. Keine Legs löschen oder austauschen;
  gebuchte Wetten, Belege, Abrechnung und morgige Vorschau nicht umschreiben.

## Wiederverwendbare Liga-Angaben

Nur die nachgewiesenen Anbieterangaben „Aufstellungen abgedeckt“ und „Ausfälle
abgedeckt“ je identischer Fußball-Liga und Saison bis zu 24 Stunden wiederverwenden,
auch zwischen Wettfinder und Shadow. Eine ausdrücklich negative Angabe ist
gültig, eine fehlende nicht. Kein Cachetreffer bei ungültigen Feldern, falscher
Identität, abgelaufenem oder künftigem Zeitstempel. Fehlversuche nicht als „nicht
abgedeckt“ speichern. Keine aktuellen Aufstellungen, Ausfälle oder Quoten auf diese
Weise zwischenspeichern. Bei Cacheproblemen den bestehenden Anbieter-/Fehlerpfad
und seine Kontingentgrenzen beibehalten.

## Liveansicht: gewählte Variante und Alternative

Der bisherige manuelle Vollscan holt unter anderem Spielstatistiken einzeln.
Ein Vollscan pro Minute und Benutzer würde unnötig Abrufe vervielfachen. Auch
alles minütlich als Gruppen abzuholen, inklusive der Suche nach neuen Spielen,
wäre am untersuchten Samstag zu teuer gewesen. Gewählt: ein gemeinsamer Stand
für alle berechtigten Zuschauer, mit zwei Takten. Kein Zusatzabo, kein Quotenabruf.

- Neue unterstützte Spiele per gemeinsamer Liste höchstens alle 300 Sekunden
  entdecken. Bekannte laufende Spiel-IDs in Gruppen von höchstens 20 alle 60
  Sekunden auffrischen. Die Antwort auf den Detailabruf enthält auch den Stand:
  Tore nicht erst beim nächsten Fünfminutentakt anzeigen. Keine doppelte Abfrage
  durch Tabs, Filter, Seitenneuladen oder parallel eintreffende Anfragen.
- Einmal geladene Vorabgrundlagen derselben Modellversion je Partie wiederverwenden.
  Modellwahl, Datenqualitätsregeln und vier bestehende Live-Märkte nicht lockern.
  Soweit nicht belegt ist, dass die Gruppenantwort für einen Markt vollständige,
  richtig zugeordnete Ereignisse/Statistiken liefert, allenfalls den Spielstand
  zeigen, keinen Tipp ableiten. Keine Serie von Einzelabfragen als Ersatz. Beim
  Platzverweis nur die konfigurierten Ligen automatisieren. Die gesonderte,
  bewusst manuell gestartete weltweite Suche behalten; nicht heimlich auf einen
  weltweiten Minutentakt umstellen.
- Teilfehler je Spiel trennen. Bei Tor, VAR-Korrektur, Platzverweis, Spielende
  oder unklarer Zuordnung den alten Tipp sofort mit Eingang der Information
  zurückziehen; neuen Tipp nur auf konsistentem Stand. Ein Abruffehler ist keine
  leere Spielliste. Letzten Spielstand mit Standzeit behalten, veraltete Tipps
  nicht anbieten (bestehende 120-Sekunden-Grenze, Zeit je Spiel).
- Links Spiele, Minute und Ergebnis, rechts das zum gewählten Spiel gehörende
  aktuelle Signal; ohne gezielte Spielauswahl nur die nach bisherigen Regeln
  zugelassenen Vorschläge. Auf Mobil direkt beim Spiel. Auswahl über Spiel-ID,
  nicht Listenindex. Kein Seitenneustart, kein neuer Wettschein, keine neue
  Kundenbilanz. Für die interne Auswertung weiterhin ausschließlich tatsächlich
  sichtbare, frische Tipps erfassen; nicht alle Hintergrundberechnungen.
- Bei knapper Restreserve, Ratenlimit oder Fehlern langsamer werden bzw.
  Abrufe aussetzen; ausgefallene Takte nicht nachholen. Bestehende automatische
  Fußball-Aufgaben schützen: neue automatische Feed-Anbieteraufrufe laufen mit
  der bestehenden Hintergrundpriorität und deren konfigurierter Restreserve
  (Standard 2.500). Weil auch Shadow diese Priorität verwendet, zusätzlich
  Vorrang für bestehende Jobs und eine an gemessenem Restbudget begrenzte
  Live-Obergrenze vor Aktivierung prüfen; 2.293 ist kein zugesichertes
  Tagesbudget. Auch die erstmaligen Vorabgrundlagen und alle Zusatzdaten zählen.
  Keine Erhöhung der bestehenden Tarifgrenze.
- Betriebsdauer (Owner, 22.11.): **nur bei offenem berechtigtem Live-Tab**.
  Erster Zuschauer startet die gemeinsame Aktualisierung, weitere Zuschauer lesen
  denselben Stand. Ohne aktive Zuschauer keine neuen Anbieterabrufe; kein
  dauernder Server-Timer. Eine ausstehende Anfrage darf zu Ende gehen.
  Dauerbetrieb ohne Zuschauer ist ausdrücklich nicht gewählt.

## Abnahme

Offline mit fester Uhr: 11:29/11:30/11:45 bei offenem Wettfinder, vollständig
begonnene und gemischte Scheine, gültige Rechte, fehlende Zeiten, Mitternacht.
Live: 0/1/20/21/80 Spiele und zwei gleichzeitige Nutzer; bei 80 Spielen fünf
Minuten lang vier Detailgruppen pro Minute und nur eine planmäßige Spielsuche.
Ende, Tore/Rot und veraltete oder teilweise fehlende Gruppen ohne überholte Tipps.
Vor Aktivierung aus vorhandenen Belegen oder im autorisierten regulären Betrieb
prüfen, welche Felder der echte Gruppenabruf liefert. Zusätzlich auf Desktop
und Mobil prüfen, dass Auswahl und Leseposition erhalten bleiben. Einsparungen
erst aus späteren vergleichbaren Betriebszahlen angeben.
