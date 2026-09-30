# Originalbilder für die Sports-Editorial-Karten

## Umfang

Die bisherige Schildform in Wettfinder und Daily3 bleibt erhalten. Originale
Fußballwappen werden über die vorhandene native API-Football-Teamkennung
zugeordnet und vollständig eingepasst. Tennisfotos stammen aus dem explizit
geprüften Commons-Manifest; nur vollständige Namen/registrierte Aliase sind
zulässig. Gesichtsausschnitte werden ausschließlich per CSS dargestellt;
die Originaldatei wird nicht verändert. `© Foto` verlinkt die Quelldatei,
Fotograf und Lizenz, mit Hinweis auf den angezeigten Bildausschnitt.

Keine Änderung an Modellen, Ranglisten, Quoten, Geld oder Ergebnisverarbeitung.
Keine neue Datenbank, Sicherung, persistente Bildkopie oder Sport-API-Scans.
Öffentliche Bilddateien werden begrenzt geladen und im Arbeitsspeicher gecacht.
Nicht verfügbare oder unbekannte Bilder führen zurück zu den Initialen.

## Prüfungen vor Veröffentlichung

- `pytest tests/test_sports_identity_renderer.py tests/test_sports_identity_media.py tests/test_wettfinder_identity.py tests/test_sports_editorial.py tests/test_wettfinder_surface.py tests/test_daily3_ui.py tests/test_daily3_store.py tests/test_workflow_integrity.py tests/test_riskobet_ui.py -q --basetemp .pytest_tmp/identity-final-20260930-b`
  mit `.codex_test_venv/quality/Scripts/python.exe`: **442 bestanden**.
- Vollständige Namen, mehrdeutige/unbekannte Identitäten, fremde Team-ID-Namensräume,
  ungültige Quellen, fehlgeschlagene Downloads, MIME-/Rastervalidierung, sichere
  Bildausschnitte und unveränderte Modell-/Finanzfelder geprüft.
- Separater Playwright-Browser, keine Bedienung des Kundenbrowsers: FC Porto,
  Manchester City, Arthur Gea, Zhang Zhizhen, Novak Djokovic, Nuno Borges,
  Rei Sakamoto und Matteo Arnaldi: **8/8 Originalbilder geladen**.
- Vereinswappen `contain`, Spielerbilder `cover`, Gesichtsausschnitte sichtbar;
  Desktop 1440 sowie Mobil 390/320 px: kein horizontaler Überlauf,
  keine Page-/Console-Fehler. Bestehende Streamlit-Warnungen separat erhalten.
- Die isolierte Designvorschau enthält ausdrücklich Beispieldaten, keine echten
  Wettprognosen. Erst der Produktionsbrowser bestätigt die echte Veröffentlichung.

## Grenzen

Das Manifest enthält 13 geprüfte Spieler, nicht jeden zukünftigen Teilnehmer.
Weitere Spieler behalten Initialen bis zur Prüfung eines authentischen Fotos.
Die Bilddarstellung belegt keine Verbesserung der Prognose- oder Wettqualität.

Der finale Commit, Fast-forward-Deployment und echte Browser-/Healthnachweise
werden nach erfolgreicher Veröffentlichung ergänzt.
