# Fußball: Wie die Live-Bilanz zählt

**Ausgangslage, 21.11.2026, 22:04 Uhr Zürich:** Auf dem VPS (`afd5d1c`) gab es kein Archiv der tatsächlich im Live-Tab angezeigten Auswahlen. Im separaten Rotkarten-Signalprotokoll standen null Zeilen. Die Trefferquote der früheren Live-Anzeigen ist unbekannt; weder historische Spiele mit Platzverweis noch die Haupttipp-Bilanz vor Anpfiff beantworten diese Frage.

| Auswahl im Live-Tab | Was als Treffer zählt |
| --- | --- |
| Noch ein Tor | Nach dem angezeigten Spielstand fällt mindestens ein weiteres gültiges Tor. |
| Team trifft noch | Das ausgewählte Team erzielt nach der Anzeige mindestens ein weiteres gültiges Tor. |
| Beide Teams treffen – Ja | Am Ende der regulären Spielzeit haben beide Teams getroffen. Frühere Tore zählen mit. |
| Nächstes Tor nach Platzverweis | Das ausgewählte Team erzielt das nächste Tor ab dem analysierten Spielstand bzw. es fällt keines, falls „kein Tor“ gewählt war. |

Die erste frische Detailanzeige je Spiel, Markt und Seite wird mit Modellchance, Zeitstempel, Spielphase, Minute und Spielstand gespeichert. Neuladen ersetzt sie nicht. Nicht angezeigte Alternativen und historische Modellläufe erzeugen keine Belege. Gespeichert wird die Modellauswahl, kein Wetteinsatz und keine platzierte Wette.

Das getrennte Rotkarten-Forschungsprotokoll erfasst weiterhin beim frischen Scan auch nicht angezeigte Modellfälle nach seinen bisherigen Datenregeln. Kein solcher Shadow-Eintrag zählt in der öffentlichen Bilanz. Bei nicht eindeutig einzelnem Platzverweis, einem Platzverweis nach dem eingefrorenen Spielstand oder laufender Nachspielzeit ab Minute 90 gibt es keine neue 11-gegen-10-Prognose. Eine früher angezeigte, gültige Auswahl wird weiterhin bis zum tatsächlichen Ende der regulären Spielzeit abgerechnet.

Der bestehende Ergebnislauf teilt sein Spielbudget zwischen der öffentlichen Bilanz und dem separaten Rotkartenprotokoll. Nachspielzeit gehört zur regulären Spielzeit; Verlängerung und Elfmeterschießen nicht. Für auf den Anzeigezeitpunkt bezogene Märkte muss der Ereignisverlauf zum Anzeige- und Endstand passen. Bei einer unklaren Reihenfolge, einem widersprüchlichen Spielstand oder fehlenden Pflichtdaten darf daraus kein erfundener Treffer oder Verlust werden.

Je Markt: Trefferquote = gewonnen / (gewonnen + verloren). Offene und ungültige Auswahlen werden separat gezählt, mehrere Auswahlen desselben Spiels sind nicht unabhängig. Bei null entschiedenen Auswahlen gibt es keine Trefferquote. Ohne aufgezeichnete Einsatzquote lässt sich aus dieser Bilanz kein Gewinn berechnen. Keine rückwirkende Erfassung, kein neuer Scanner, kein zusätzliches Abrufbudget und keine zusätzliche Sicherung.

**Abgrenzung:** Die separate Rotkarten-Forschung betrachtet alle gültigen frischen Kandidaten mit ihren drei Ausgangswahrscheinlichkeiten, nicht nur die in der Oberfläche gewählte Seite. Ihr bisheriger Modellhorizont von 93 Minuten ist keine Abpfiffregel. Für historische Muster bleiben alte Datensätze erhalten; der neue Musterbericht verwendet nur nach dem neuen Verfahren geprüfte Fälle. Die öffentliche Bilanz verwendet keine dieser Forschungszahlen.

**Regression:** Die isolierte Freigabeprobe spielt alle vier Märkte, zwei identische Anzeigen je Markt, einen verschossenen Elfmeter und den echten Torzeitpunkt 90+4 mit synthetischen Daten durch. Es ergeben sich vier Belege und vier korrekt entschiedene Ergebnisse, ohne Anbieterzugriff. Der vollständige Windows-Testlauf mit Stopp beim ersten Fehler scheitert weiterhin am zuvor bekannten Eishockeytest `test_native_conflicting_role_ids_fail_before_any_request` (unverändert, nach 83 bestandenen Tests). Die Live-Regression ist davon getrennt.
