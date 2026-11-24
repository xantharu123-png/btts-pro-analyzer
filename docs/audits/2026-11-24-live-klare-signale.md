# Live-Fußball: nur Empfehlungen mit neuem Signal

**Ausgangsbefund (24.11., tatsächliche Produktion vor der Änderung):** Die
17 ausgelesenen Erstbelege für diesen Spieltag waren alle „Noch ein Tor“;
11 davon in Minute 2 oder 3 beziehungsweise früher. Cardiff–Preston
(Fixture 1563276) wurde bei 0:0 in Minute 2 mit 94,7 % angezeigt. Aus den
veröffentlichten Vorabwerten 2,091 und 1,109 folgen zur selben Minute und beim
selben Spielstand ohne Live-Beobachtungen bereits 95,6 %. Native xG von 0:0
senken die Chance auf 94,7 %. Positive Live-Evidenz für „Noch ein Tor“ lag
damit nicht vor. Die alte Auswahl bevorzugte das breiteste Ereignis.

**Lösung:** Die 54 Auswahlen desselben Tor-/Ergebnismodells (Spielausgang,
doppelte Chance, Halbtor-Handicap, Gesamt-/Teamtore, Torbereiche, beide Teams
treffen und weitere Tore) werden bei genau diesem Stand in beiden Verteilungen
ausgewertet. Bereits entschiedene Märkte sind keine Kandidaten.
Veröffentlicht wird frühestens in Minute 15, ab 55 % Modellchance und ab
5 Prozentpunkten Zugewinn; dieselbe Regel bestimmt den automatischen Spielfokus.
Tipp und tatsächliche Anzeige binden Markt, Team, Zeit und Spielstand.
Bei Platzverweis wird die reguläre Minute der ersten Halbzeit in beiden
Anbieter-Schreibweisen gleich verwendet, ohne den angezeigten Uhrstand zu ändern.
Modellpreise, Ecken-/Kartenwetten, Pre-Match und manuelle Rotkarten-Suche sind
nicht Teil dieser Änderung. Der bestehende Ticker-Takt und seine Limits bleiben.

**Abnahme:** In der nachgestellten Cardiff-Situation erscheint keine Auswahl.
Zu testen sind außerdem das Zeitfenster, schwache und starke spätere Fälle,
Fokusreihenfolge, eine eindeutige Abrechnung pro Markt sowie die Abgrenzung
zum älteren Datensatz. Die neuen nicht kompatiblen negativen BTTS-Belege
verwenden einen eigenen Schlüssel; ein älterer Abrechner erkennt sie nicht als
positives BTTS. Das SQLite-Schema wird nicht geändert. Bei Rücknahme den
aktuellen Abrechner beibehalten, damit offene neue Märkte nicht liegen bleiben.

Lokale Regression: 675 Tests bestanden, 1 Skip unter `gate`; 673 Tests
bestanden, 1 Skip unter `floor`, nachdem zwei unveränderte `gate`-Erwartungen
im Vorabkarten-Audit separat abgegrenzt wurden. Die Vollsuite stoppt (99 grün)
am bereits bekannten `test_native_conflicting_role_ids_fail_before_any_request`
im Eishockey-Preispfad; dessen Code und Test sind in diesem Release unverändert.

**Grenzen:** Die Stichprobe (n=17) ist eine beschreibende Kontrolle der
Produktionsanzeige, kein geschätzter Trefferanteil. Es liegt kein vollständiges
zeitgenössisches Replaysample vor. Die 5-Prozentpunkte-Regel ist eine vorab
festgelegte Anzeigeregel, keine empirisch bestimmte Vorteilsschwelle. Das
interne Ledger speichert weiter Erstbelege je Spiel/Markt/Seite, nicht alle
verworfenen Beobachtungen, Vorab-Live-Paare oder jede wiederholte Anzeige.
Aus künftigen regulären Erstbelegen die Abrechnungen getrennt nach Policy und
Markt prüfen; keine Wett-Rendite aus Softwaretests ableiten.
