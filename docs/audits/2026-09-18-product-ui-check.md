# Lokale Produktprüfung der reparierten Auswahl

## Umfang und Grenzen

Prüfung am 18.09.2026 mit den echten Renderern aus `wettfinder_surface.py` und `daily3_ui.py`, den App-Styles und deutlich gekennzeichneten synthetischen Prüfdaten. Lokale Streamlit-Vorschau auf Port 8519; isolierter Testkontospeicher außerhalb des Repositorys. Keine echte Wette, kein produktiver Kontozugriff und keine VPS-Änderung. Dies ist eine Renderer-/Interaktionsprüfung, keine Freigabe der gesamten Produktionsseite oder der Vorhersagequalität.

Die erste Runde lief nach den Auswahlcommits c953d46/9467148; nach weiteren Quelländerungen ist eine Abschlussrunde erforderlich. Die Screenshotdateien sind lokale QA-Artefakte, kein Produktinhalt.

## Beobachtungen

- Seite lädt mit Titel `BetBoy · Produktprüfung`; tatsächliche Modellkarten sichtbar, kein leerer Ladebildschirm und keine Fehlermeldung.
- Umkehren derselben vollständigen Eingabeliste ändert die sichtbaren Schlüssel nicht: HOME, Tennis-H2H, BTTS-YES und kompatibles DC-1X. AWAY/X2 erscheinen nicht als Gegenempfehlung desselben Modellstands.
- Beobachtete Quote 1.12 bleibt sichtbar und ändert weder Modellwerte noch Reihenfolge. Daily3 zeigt ausdrücklich: Die beobachtete Quote liegt unter der berechneten Preisschwelle; die Modell-Auswahl bleibt unverändert.
- Daily3 nimmt maximal drei verschiedene Events aus demselben Modellbestand. Die Testausgabe enthält drei, aber der Renderer erzeugt keine fehlenden Kandidaten. Kein Budget bestätigt und keine Kontobuchung ausgeführt.
- Kalender-/Modell- und Datenzeiten sind lesbar getrennt. Tennis benennt hier ausdrücklich, dass Verletzungen/Müdigkeit kein nachgewiesener numerischer Vorteil sind.
- Breitenmessung: Desktop 1440/1440 px, Daily3 390/390 und 320/320 px, normale Karten 320/320 px (Dokument/Viewport), kein horizontaler Überlauf.
- Browserkonsole: 0 Fehler, 0 Warnungen in dieser lokalen Prüfrunde.

## Belege

Temporärer Prüfordner: `C:/Users/miros/AppData/Local/Temp/betboy-product-qa-20260918`.

- Desktop-Screenshot: `.playwright-cli/page-2026-09-18T20-57-38-683Z.png`, visuell geprüft.
- Daily3-Mobil: `.playwright-cli/page-2026-09-18T21-04-29-792Z.png`, visuell geprüft.
- Normale Karten 320 px: `.playwright-cli/page-2026-09-18T21-12-00-899Z.png`.
- Zustände und Interaktionen als zugehörige Playwright-Snapshots im selben Ordner.

Native Checkbox-Eingabefläche war durch ihr Streamlit-Label überlagert; der sichtbare Label-Klick funktioniert. Keine Produktreparatur daraus abgeleitet. Ein vollständiger Reload setzt die Wegwerf-Prüfbedienelemente wie erwartet zurück.

## Zweite Runde 19.09.2026, ca.00:26–00:34 CEST

- Echte Daily3-Rendererzustände mit null/einer/drei verfügbaren Testpaarungen zeigen0/3,1/3,3/3 und denselben Prognosepool; leere Plätze werden nicht gefüllt. Kein Tagesbudget bestätigt, keine Echtgeldbuchung ausgeführt.
- Team-Sport-Pfad benutzt den echten Adapter, das normale Artefakt und den echten Verbraucher mit kontrollierter historischer Testuhr. Beide Siegerkomponenten werden einmal berechnet; die Oberfläche zeigt die konsistente Richtung, Originalzeit, Stichprobe und ausdrückliche fehlende unabhängige Bestätigung. Keine TOP-Hervorhebung, kein erfundener Sicherheitswert/Mindestpreis.
- Gefunden und behoben: Rundung einer Wahrscheinlichkeit knapp unter1 auf100.0 %. Fix a322430, fünf beobachtete RED-Fälle,160 betroffene Tests grün. Nach Neustart nur des eigenen QA-Servers zeigt der Browser >99.9 % in Karte und >99,9 % in Erklärung. Vorheriger reiner Browser-Reload hatte alte Python-Imports behalten und war deshalb noch kein Fixbeleg.
- Teamkarten Desktop1440/1440 und Mobil320/320, kein horizontaler Überlauf. Beide Screenshots visuell gelesen. Frische Browserkonsole0Fehler/0Warnungen; temporäre Verbindungsversuche während des absichtlichen lokalen Serverneustarts sind keine Produktivfehler.
- Belege im selben temporären Ordner: Leerzustand `page-2026-09-18T22-26-52-450Z.png`; korrigierter Team-Desktop `page-2026-09-18T22-33-53-719Z.png`; Team-Mobil `page-2026-09-18T22-33-59-332Z.png`.
- Frische Daily3-Mobilprüfung320px um00:36: unveränderte drei Auswahlen, aktuelleQuote1.12 und ausdrückliche Preiswarnung sichtbar,320/320px ohne Überlauf. Screenshot `page-2026-09-18T22-36-24-680Z.png`; kein Geld-Button betätigt.

Browser plugin not available; vorhandener Playwright-CLI-Wrapper verwendet, keine neuen Browser-Abhängigkeiten installiert. Keine gesamte Produktionsseite, echten aktuellen Sportdaten, Konto-/Platzierungsabläufe oder VPS aus dieser Rendererprüfung als abgenommen behaupten.
