# Wettfinder V2 - Wireframe v1

Stand: 27.08.2026

Status: **ZUR DESIGNFREIGABE - KEINE IMPLEMENTIERUNGSFREIGABE**

## Ziel

Der Nutzer soll die besten Modell-Auswahlen und ihren Preisstatus sofort
verstehen. Kein Topvorschlag darf durch einen Expander, einen Sport-Container
oder einen zweiten Ergebnisbereich verborgen werden.

Der Entwurf ist ein isolierter Designprototyp. Er ändert weder die
Wettfinder-Logik noch die produktive Streamlit-Oberfläche.

## Gewählte Richtung: Entscheidungs-Karten

Die Hauptansicht kombiniert:

- große Entscheidungs-Karten für maximal drei Top-Auswahlen;
- eine kompakte, flache Liste für weitere Modellprognosen;
- eine einzige optionale Detail-Ebene pro Auswahl;
- einen klaren Umschalter zwischen `Automatisch` und `Eigene Suche`.

Diese Richtung wurde einer reinen Vergleichstabelle und einer vollständigen
Gruppierung nach Spielen vorgezogen. Eine Tabelle ist mobil zu dicht. Eine
Spiel-zuerst-Gruppierung verwischt die Priorisierung der Auswahl. Mehrere Märkte
desselben Spiels werden in der weiteren Liste trotzdem sichtbar
zusammengehalten.

## Neue Informationsarchitektur

```text
Wettfinder                              Stand / Aktualität
[Automatisch] [Eigene Suche]

Kompakter Datenstatus und einmalige Erklärung

TOP-AUSWAHLEN NACH MODELL
[Top-Karte] [Top-Karte] [Top-Karte]

WEITERE MODELLPROGNOSEN
[flache Zeile]
[flache Zeile]

Hinweis zum Spielrisiko
```

Es gibt keine getrennten, aufklappbaren Ergebniswelten mehr für Fußball,
Tennis und E-Sport. Sportart und Startzeit stehen als Metadaten direkt an jeder
Auswahl. Filter verändern nur die Ansicht, nicht die zugrunde liegenden
Modellergebnisse.

## Kartenhierarchie

Jede Topkarte zeigt ohne Interaktion:

1. Einordnung als Top-Auswahl
2. Evidenzstatus (`Modellprognose` oder `Bestätigter Tipp`)
3. Preisstatus (`Spielbar`, `Quote offen`, `Unter Value` oder `Veraltet`)
4. Sportart und Startzeit
5. Begegnung
6. Markt und konkrete Auswahl
7. vorsichtige Trefferchance als Hauptwert
8. Modellwahrscheinlichkeit als Nebenwert
9. `Value ab ...`
10. aktuelle Quote oder einen eindeutigen Fehlstatus
11. kompakte Kontextabdeckung
12. Aktionen `Analyse anzeigen` und `Eigene Quote prüfen`

Nur `Analyse anzeigen` darf eine Zusatzebene öffnen. Die Auswahl selbst bleibt
dabei vollständig sichtbar. In der Analyse liegen H2H, Ausfälle, Wetter,
Aufstellungen und Modellbegründung.

## Getrennte Statusachsen

Die Oberfläche darf fachlich verschiedene Aussagen nicht in ein einziges
Label pressen:

| Achse | Beispiele | Bedeutung |
|---|---|---|
| Platzierung | `Top-Auswahl` | Teil des vom jeweiligen Modell gelieferten Top-Sets |
| Evidenz | `Modellprognose`, `Bestätigter Tipp` | Freigabestand der Auswahl |
| Preis | `Spielbar`, `Quote offen`, `Unter Value`, `Veraltet` | Bewertung des Wettpreises |
| Marktart | `Einfacher Markt` | optionale Einordnung, keine Sperre |

Eine fehlende oder zu niedrige Quote ändert die Prognose nicht und sortiert die
sichtbaren Karten nicht um. Ein gemeinsames numerisches Ranking von Fußball,
Tennis und E-Sport wird nicht dargestellt, solange kein fachlicher Vertrag zur
sportübergreifenden Vergleichbarkeit existiert. `Bestätigter Tipp` darf
ausschließlich für tatsächlich freigegebene `RELEASED`-Auswahlen erscheinen.

## Vorhandener Datenvertrag

Ohne Backendumbau sind bereits zuverlässig verfügbar:

- Sport, Startzeit, Begegnung, Markt und Auswahl;
- Modellwahrscheinlichkeit, Haircut und vorsichtige Wahrscheinlichkeit;
- Value-Grenze;
- Evidenz- und statistischer Freigabestatus;
- Preisstatus und optional gebundene Vergleichsquote;
- optionaler Kontext-Kurztext und Kontext-Vollständigkeit;
- Modellherkunft als technische Detailinformation.

Ein kanonischer sportübergreifender Modellrang ist derzeit nicht vorhanden.
Die spätere UI darf aus der Listenposition keinen solchen Rang ableiten.

Die spätere Implementierung benötigt eine kleine Adapter-Erweiterung, wenn
H2H-Bilanz, einzelne Ausfälle, Temperatur, Aufstellungen oder Prüfzeitpunkte
separat statt nur als Kontext-Kurztext dargestellt werden sollen. Der
Wireframe erfindet diese Detailwerte nicht.

## Desktop

- Top-Auswahlen stehen als maximal drei gleich ausgerichtete Karten in einer
  Reihe und sind gemeinsam sichtbar.
- Die vorsichtige Trefferchance ist der größte Wert.
- Modellwert, Value-Grenze und aktuelle Quote sind gleich ausgerichtete
  Sekundärwerte.
- Weitere Prognosen verwenden flache Vergleichszeilen und behalten Startzeit,
  Modellwert, vorsichtige Prognose, Value-Grenze, aktuelle Quote sowie getrennte
  Evidenz- und Preiskennzeichnungen sichtbar.
- Die bestehende Hauptnavigation kann als schmale Seitenleiste erhalten
  bleiben.

## Mobile

- Einspaltige Karten ohne horizontales Scrollen.
- Die erste vollständige Auswahl passt bei `390 x 844 px` in den ersten
  Bildschirm.
- Die Top-3 sind mit rein vertikalem Scrollen erreichbar; kein Tabwechsel und
  kein Öffnen eines Containers ist nötig.
- Die Hauptnavigation wechselt wie bisher in eine untere Navigation.
- Aktionen besitzen mindestens 44 Pixel Höhe.

## Zustände

Der spätere Umbau muss zusätzlich zu normalen Auswahlen folgende Zustände
explizit entwerfen und testen:

- Laden/Aktualisieren ohne Layoutsprung
- keine Auswahl gefunden
- Teildaten oder unvollständiger Lauf
- veraltete Modell- oder Quotendaten
- Quote fehlt oder ist zu dünn
- Quote unter Value-Grenze
- Preis passend, Modell aber noch nicht freigegeben
- vollständig bestätigter spielbarer Tipp
- mehrere korrelierte Märkte desselben Spiels

Große Warn- und Erklärboxen dürfen die Top-Auswahlen nicht aus dem ersten
Bildschirm verdrängen. Eine Erklärung erscheint einmal auf Seitenebene oder
als Tooltip, nicht als wiederholter Absatz in jeder Karte.

## Abnahmekriterien für die spätere Implementierung

- Top-3 vollständig ohne äußeren Expander, Tabwechsel oder weiteren Klick.
- Pro Karte höchstens eine Detail-Ebene und niemals verschachtelte Expander.
- Erste komplette Karte bei `390 x 844 px` im ersten Viewport.
- Kein horizontaler Seiten-Scroll bei 320, 360, 390 und 430 Pixel Breite.
- Status nie ausschließlich über Farbe; immer mit eindeutigem Text.
- WCAG-AA-Kontrast und mindestens 44 x 44 Pixel große Bedienflächen.
- Lange Team- und Marktnamen umbrechen, ohne abgeschnitten zu werden.
- Tastatur-/Screenreader-Reihenfolge: Top-/Evidenzstatus, Spiel, Auswahl,
  Prognose, Preis, Aktionen.
- Automatische Aktualisierung verschiebt keinen Fokus und schließt keine
  geöffnete Analyse.
- Die sichtbare Auswahlreihenfolge wird nicht nach Preisstatus umsortiert.
- Vier von fünf Testpersonen können innerhalb von zehn Sekunden Auswahl,
  Evidenzstatus und Preisstatus der besten Karte korrekt benennen.

## Review-Artefakt

Der responsive Klickprototyp liegt in
`docs/ux/wettfinder-v2/wettfinder_wireframe_v1.html`.

Gerenderte Reviewansichten:

- `docs/ux/wettfinder-v2/renders/wettfinder_wireframe_v1_desktop.png`
- `docs/ux/wettfinder-v2/renders/wettfinder_wireframe_v1_mobile.png`

Die Beispieldaten dienen nur zur Layoutprüfung und sind ausdrücklich keine
Tipps oder aktuellen Wettangebote.
