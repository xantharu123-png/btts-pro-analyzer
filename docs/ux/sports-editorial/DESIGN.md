# BetBoy – Sports Editorial

Stand: 30.09.2026. Freigegebene responsive Weboberfläche umgesetzt und geprüft.
Veröffentlichungsbeleg: [Abnahmebericht](../../audits/2026-09-30-sports-editorial.md).

## Verbindliche Auswahl

Nutzerentscheidung: „2 für Webbrowser und ein Mix aus 5 und 2 für Mobile/App“.

- **Desktop:** Design 2, Sports Editorial.
- **Mobil:** Farben, Typografie und Sportmagazin-Charakter aus 2; Spielkarten,
  Touch-Bedienung und untere Navigation aus 5.
- Die neue kombinierte Mobilvorschau konkretisiert diese Auswahl. Sie ist keine
  fertige App und kein Nachweis einer nativen iOS-/Android-Implementierung.

## Referenzen

- [Desktop – gewähltes Design 2](desktop-design-02.png)
- [Mobil – Kombination 2 + 5](mobile-design-02-05.png)

Die Bilder sind mit der eingebauten Bildgenerierung erstellte Designstudien.
Teams, Wappen, Spiele, Werte und Quoten sind Beispieldaten. Nicht als Datenquelle
verwenden. Der Desktop-Satz über ein „Redaktionsteam“, Werbeformulierungen,
scheinbare Wettbewerbszuordnungen und dekorative Formkurven werden NICHT
unbesehen übernommen. Marken/Wappen nur aus zulässigen vorhandenen Quellen,
sonst neutrale Initialen. Keine erfundenen Daten, Erklärungen oder Menschen.

## Problem und Ziele

Die bisherige Oberfläche wirkt wie ein Verwaltungsformular und zwingt Nutzer,
Form und Ergebnisse aus langen Textzeilen herauszulesen. Ein Spiel soll schnell
erkennbar, seine Auswahl verständlich und der Mannschaftsvergleich direkt
erfassbar sein – auf Desktop und kleinen Touchscreens.

1. Begegnung, Auswahl und Startzeit ohne Öffnen technischer Details erkennen.
2. Letzte Spiele anhand von Ergebnisfeldern statt verdichteter Textformeln lesen.
3. Alle Auswahlen zu einem Spiel gemeinsam schließen und wieder öffnen können.
4. Fachliche Aussagen und vorhandene Bedienfunktionen beim Umbau erhalten.

## Gestaltung und P0-Anforderungen

- Warmweiß, nahezu schwarzer Text, dunkles Waldgrün; Gelb sparsam als Akzent.
  Kräftige Sportüberschriften, ruhige gut lesbare Textschrift, tabellarische Ziffern.
  Keine Bank-KPI-Wand, Geldstapel-Icons, Neonflächen oder dauernden Animationen.
- Desktop: horizontale Navigation, Hauptbereich für Spielgruppen und eine
  ergänzende Daily3-/Sportspalte, sofern die Breite und echte Inhalte reichen.
  Bei leeren Zusatzinhalten keine künstlichen drei Tipps oder Platzhalter-Tipps.
- Mobil: eine Spalte, kompakte Karten, klare Touchflächen und feste untere
  Navigation mit sicherem Abstand zum Inhalt. Bestehende Ziele Wettfinder,
  RisikoBet, Live, 15K und Meine Tipps bleiben erreichbar. Daily3 bleibt prominent
  im Wettfinder; die illustrative Mockup-Navigation entfernt nicht die 15K-Seite.
- Pro Spiel ein gemeinsamer Block. Wichtigste Auswahl offen sichtbar; weitere
  Märkte gehören zum selben Spiel. Schließen versteckt nicht den Spielkopf.
- Form: 5/10-Umschalter, S/U/N bzw. sportgerechte Ergebnisse, Buchstaben UND
  Farbe. Klick/Tipp zeigt Gegner, Ergebnis, Zeitpunkt und Wettbewerb, soweit
  vorhanden. Keine ausschließlich hover-basierten Informationen.
- Chronologie und Ergebnis-Perspektive eindeutig machen; jüngstes Spiel
  konsistent an derselben Stelle. Keine Siegbilanz durch dekorative Kurven ersetzen.
- Fußball: Teamvergleich, Heim/Auswärts und echte Ergebniszeilen.
  Tennis: gewählter Belag, Sätze/Ergebnisse und reale Gegner; keine Fußball-Remis.
  Weitere Sportarten verwenden ihre vorhandenen passenden Ergebnisdaten.
- Ein knapper datengestützter Grund sichtbar; relevante Gegenargumente bleiben
  erreichbar. Keine unbelegte Erklärung aus bloßem Designtext übernehmen.
- Ausfälle/Wetter als kompakte anklickbare Fakten. Fehlende Daten weder als
  „0 Ausfälle“ noch als geprüft darstellen. Technische Hinweise in Details.
- Modell und Quote bleiben getrennte Werte. Keine Form-, Quoten-, Budget- oder
  Modelländerung durch Styling; bekannte exakt gebundene Quote unter 1,20 weiter
  ausblenden, keine gegenüberliegende Auswahl nachschieben.

## Nicht Teil dieses Designpakets

- Neue Modelle, Gewichtungen, Verletzungswirkung, Sportscans oder API-Anbieter.
- Neue Wettartenverbote, garantierte Gewinne oder geänderte Geldbuchungen.
- Aktivierung von Abos, Anmeldung, Stripe oder Store-Veröffentlichungen.
- Native App-Neuentwicklung; zunächst die vorhandene responsive Weboberfläche.

## Umsetzung im vorhandenen Projekt

1. Gemeinsame Farben, Typografie und responsive Navigation in `app.py` isolieren.
2. Spielkarten in `wettfinder_surface.py`, gemeinsame Fakten in
   `forecast_compact.py` und die bestehende Spielgruppierung umgestalten.
3. Dieselben Bausteine in Daily3, manueller Suche und RisikoBet nutzen;
   `daily3_ui.py` und `riskobet_surface.py` dürfen fachliche Unterschiede behalten.
4. Reale vorhandene Fakten in Formfelder überführen; keine neuen Abrufe beim
   Öffnen/Schließen oder Wechseln von 5 auf 10 Spiele auslösen.
5. Render- und Interaktionstests, danach kontrollierte Veröffentlichung des
   geprüften UI-Patches. Keine neue Sicherung oder Speicherbereinigung.

## Abnahme

- [x] Bei 320, 390, 760, 1024 und 1440 px kein horizontaler Seitenüberlauf.
- [x] Formfelder, Gegnerlisten, 5/10-Auswahl und Spielgruppen per Maus und
      Tastatur geprüft; Touch-Emulation, sichtbarer Fokus, mindestens 44 px Ziele.
- [x] Lange Teamnamen, 0/1/3 Auswahlen, fehlende Quote und kurze Historie geprüft.
- [x] Modellwerte, Marktauswahl, 1,20-Filter und Geldbuchungen unverändert.
- [x] Keine produktiven Beispieldaten, erfundenes Redaktionsteam oder Fake-Wappen.
- [x] Tatsächliche Browserbilder mit beiden Referenzen verglichen; keine
      Store-/Geräteprüfung aus einem Desktop-Screenshot ableiten.

Erste messbare Abnahme sind diese Rendering-/Funktionsprüfungen, nicht eine
unbelegte Verbesserung der Trefferquote. Keine offene Nutzerentscheidung
verhindert den Beginn des beschriebenen UI-Umbaus.

## Umsetzungsnachweis

- Gemeinsames lokales Theme und Schrift, native Desktop-/Mobilnavigation.
- Spielgruppen mit neutralen Initialen, Auswahl und Modellchance im Blick.
- Echte Ergebnisfelder und Gegnerdetails in Wettfinder, Daily3 und eigener Suche;
  RisikoBet erhält dieselben Gestaltungsregeln. Bestehende reine Zusammenfassungen
  werden nicht in erfundene Einzelspiele umgewandelt.
- 526 betroffene Tests bestanden; 29 Browser-/Randfallkombinationen geprüft,
  zusätzlich native Klick-/Tastatursteuerung und mobile Touch-Emulation.
- Ein beim Browsercheck reproduzierter Rücksetzfehler des 5/10-Schalters behoben.
- Mobilnavigation bleibt auf Abo-Hinweisseiten erreichbar, ohne den Zugriff auf
  die gesperrten Funktionen zu öffnen. RisikoBet-Statuskontrast ebenfalls geprüft.
- Gemeinsamer Routenzustand statt konkurrierender versteckter Sidebar-Radio;
  dreifacher Desktop-/Mobilrückweg jeweils beim ersten Klick geprüft.
- Kein neuer Sportscan, Modellumbau, Backup oder Finanzvorgang. Reale Geräte,
  native Store-Apps und numerisch nachgewiesene Kontexteffekte bleiben separat.

## Generierungsnachweis

Mobilbild: eingebaute Bildgenerierung, kein CLI-/separater API-Aufruf.
Vollständiger Prompt: [mobile-prompt.txt](mobile-prompt.txt).
Referenzen: das gewählte Desktopbild 2 und die zuvor gezeigte Mobilkarte 5.
