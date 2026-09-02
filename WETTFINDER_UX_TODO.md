# Wettfinder UX-Neuaufbau - To-do

Stand: 02.09.2026
Prioritaet: P0
Status: **ABGESCHLOSSEN – WETTFINDER V2 IMPLEMENTIERT UND VERIFIZIERT**

Designreview:

- `docs/ux/wettfinder-v2/WETTFINDER_WIREFRAME_V1.md`
- `docs/ux/wettfinder-v2/wettfinder_wireframe_v1.html`

## Problem

Die aktuelle Wettfinder-Oberflaeche ist zu unuebersichtlich. Die Topvorschlaege
sind unnoetig verschachtelt und teilweise erst sichtbar, nachdem der Nutzer
Bereiche aufklappt. Der Wettfinder benoetigt deshalb einen vollstaendigen
UX-Neuaufbau und nicht nur weitere kleine Layoutkorrekturen.

## Verbindliche To-dos

- Informationsarchitektur des gesamten Wettfinders neu konzipieren.
- Topvorschlaege als sofort sichtbare, flache und schnell vergleichbare
  Hauptansicht darstellen. Zum Erkennen der Vorschlaege darf kein Aufklappen
  notwendig sein.
- Verschachtelte Expander, wiederholte Zwischenueberschriften und unnoetige
  Erklaerungstexte aus dem primaeren Ergebnisfluss entfernen.
- Pro Vorschlag Sport, Begegnung, Wettmarkt, Auswahl, Modellwahrscheinlichkeit,
  vorsichtige Prognose, Preisstatus und - falls vorhanden - aktuelle Quote oder
  Value-Grenze auf einen Blick zeigen.
- H2H, Ausfaelle, Wetter, Aufstellungen und ausfuehrliche Modellbegruendungen
  duerfen als optionale Zusatzdetails aufklappbar bleiben, aber niemals den
  eigentlichen Vorschlag verstecken.
- Topvorschlag, einfache Modellprognose, bestaetigten Tipp und Preishinweis
  optisch eindeutig unterscheiden, ohne diese Zustaende ineinander zu
  verschachteln.
- Wiederholte oder triviale Maerkte duerfen wichtige Vorschlaege weder
  verdraengen noch die Seite optisch dominieren.
- Desktop- und Mobile-Ansicht gemeinsam entwerfen und auf schnelle
  Erfassbarkeit, klare Priorisierung und kurze Scanwege pruefen.
- Vor jeder Implementierung zuerst einen konkreten Wireframe oder visuellen
  Entwurf zur Freigabe vorlegen.
- Erst nach ausdruecklicher Freigabe implementieren und danach gerendert auf
  Desktop und Mobile sowie mit der vollstaendigen Regression pruefen.

## Abnahmekriterium

Beim Oeffnen des Wettfinders erkennt der Nutzer alle Topvorschlaege und deren
wichtigste Entscheidungsdaten sofort. Nur echte Zusatzinformationen benoetigen
einen weiteren Klick.

## Abschluss

Der freigegebene Neuaufbau ist umgesetzt. Topvorschläge und Zusatzkarten sind
flach, die wichtigsten Entscheidungsdaten sofort sichtbar, Analyse und
Quotenprüfung getrennt und Desktop-/Tablet-/Mobilansichten geprüft.

Produktionsnachweis vom 02.09.2026:

- Implementiert mit `a086adf`, `5d5fe51` und `765008c`; Wiederholungsläufe mit
  `049d079a8f15031dccab0285000dd549db1f2388` revisionsfest gemacht und über
  `7d6f0e8060534b3f4d420b3c556321c7f7d022c9` HTTP/1.1-kompatibel deployed.
- 1.423 Tests bestanden, 8 erwartete Skips und 97 Untertests; 182 versionierte
  Python-Dateien kompiliert.
- Produktionsansicht bei 1440, 1080, 768, 430, 390, 360 und 320 Pixeln ohne
  horizontalen Überlauf sowie ohne Console-Fehler oder -Warnungen geprüft.
- Alle sechs Sportfilter zeigen die exakten Bestände; die fünfteilige
  Mobilnavigation bleibt bis 320 Pixel nutzbar.
- VPS-Healthchecks intern und öffentlich `ok`, sieben Timer aktiv und aktiviert,
  Deployment-Backup mit 86 Datenbanken verifiziert.
- Cricket bleibt mangels `RAPIDAPI_KEY` beziehungsweise `CRICKET_API_KEY` und
  gültigem Anbieterzugang extern ohne Quelle. Es wird deshalb keine
  Wahrscheinlichkeit erfunden; dies ist keine UI-, Modell- oder Quotensperre.
