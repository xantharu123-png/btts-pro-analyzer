# Gemeinsame Spielblöcke – 19.09.2026

## Geliefert

Funktionscommit `1e918b970657dbf151baaa9df115accb7f579e43`, auf main gepusht
und auf dem VPS gegen 13:17 CEST unabhängig bestätigt.

- Ein auf-/zuklappbarer Block pro Spiel im automatischen Wettfinder.
  Spielname, Sport, Beginn und tatsächliche Auswahlanzahl stehen im Kopf.
- Hervorgehobene und weitere Märkte desselben Spiels werden zusammengeführt,
  ohne eine Auswahl hinzuzufügen, zu entfernen oder neu zu berechnen.
- Hervorgehobene Spiele anfangs geöffnet, weitere geschlossen. Eine einzige
  Spiel-Ebene; einzelne Märkte bleiben flach mit ihren bisherigen Fakten und
  exakt gebundenen Preisaktionen. Kein wiederholter Spieltitel je Markt.
- Benutzerentscheidung bleibt bei Filter-/Seitenwechseln in der laufenden
  Browsersitzung erhalten. Kein dauerhaftes Speichern über Browserneustarts.
- Weitere Spiele werden in ganzen Gruppen zu höchstens 20 Spielen pro Seite
  angezeigt. Ein Spiel wird niemals über mehrere Seiten verteilt.
- Gruppierung nach sport-/providergebundener Ereignisidentität, nicht nach
  ähnlich geschriebenen Namen; Rückspiele und andere Sportarten bleiben getrennt.

## Nachweise

- 907 betroffene Tests plus 26 Untertests im Reparaturworktree bestanden;
  derselbe Lauf nach Fast-forward im Hauptcheckout: 907 plus 26, Exit 0.
  Kein erneuter Gesamtmodelltest und kein unabhängiges Agentenreview behauptet.
- Regressionen: alle Karten genau einmal, bestehende Widerspruchsregeln
  unverändert, Preisneutralität, gleiche Namen bei verschiedenen Events,
  Markdown-Escaping, stabile UI-Zustände und unveränderte Preisbindung.
- Seitentest: 41 Spiele mit je drei Märkten werden in 20/20/1 ganze Spiele
  geteilt; alle 123 Märkte erscheinen genau einmal.
- Lokaler echter Streamlit-Browser bei 1440/761/320 Pixeln ohne horizontalen
  Überlauf. Auf-/Zuklappen, Enter, Sportfilterwechsel und Seitenwechsel geprüft.
  Lokale Fixture klar als Beispieldaten gekennzeichnet, keine Providerabfragen.
- Live-Browser: Brommapojkarna–Göteborg erscheint genau einmal mit zehn
  Auswahlen. Ein Klick schließt sämtliche Märkte. Nach Tennis und zurück zu
  Alle bleibt derselbe Block geschlossen. 1440/320 Pixel ohne Überlauf.
  0 Console-Fehler; neun bestehende Browser-/Iframe-Warnungen unverändert.
- Lokale/öffentliche Healthchecks ok; App/Caddy, sechs Rechentimer und
  Retention aktiv. Tagesbackup weiterhin disabled/inactive.
- Exakter Code-only-Fast-forward nach regulärem Abschluss des laufenden
  Wettfinderjobs; kein Abbruch einer Berechnung. Deployment Exit 0 und
  anschließender unabhängiger SHA-/Health-/Timer-Lesecheck erfolgreich.

Lokale QA-Belege unter `output/playwright/game-groups-*` bleiben uncommitted.
Es wurden keine Einsätze oder Wetten im Browser erfasst.

## Grenzen

Darstellungsänderung, keine Verbesserung der Prognosequalität behauptet.
Modelle, Auswahl-/Widerspruchslogik, Quotenprüfung, Daily3-Auswahlprofil,
Budget und Abrechnung unverändert. Daily3, Eigene Suche und RisikoBet wurden
in dieser Aufgabe nicht neu aufgebaut. Verletzungs-/Müdigkeitswirkung und
bekannte Datenjob-/Qualifikationsaufgaben bleiben separate offene Arbeiten.
Keine neue Sicherung, Bereinigung, Migration oder Paketinstallation auf VPS.
