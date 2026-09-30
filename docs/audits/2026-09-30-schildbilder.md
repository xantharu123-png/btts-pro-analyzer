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

## Produktionsnachweis, 30.09.2026

- Codecommit `4e87ca23696cadf19e68f602fa6df019e57476e5` auf GitHub main und
  kontrolliert per Fast-forward auf den VPS gezogen; App neu gestartet.
  Kein Backup, keine Bereinigung, kein zusätzlicher Sportscan.
- App/Caddy aktiv; interner und öffentlicher Healthcheck `ok`.
  Alle sieben bestehenden Timer weiterhin geplant. Historische fehlgeschlagene
  einmalige Prüf-/Release-Dienste wurden nicht verändert oder bereinigt.
- Originalwappen FC Porto (native ID 212) und Manchester City (50) auch über
  den veröffentlichten VPS-Bildweg geladen und validiert.
- Echte Gea-/Zhang-Karte im Produktionsbrowser: beide Spielerbilder geladen,
  Gea-Gesichtsausschnitt sichtbar, Modell weiterhin **79,4 %**, Quote **1,28**.
  Desktop 1440 und Mobil 390/320 ohne horizontalen Überlauf oder Browserfehler.
  Auch die echte Daily3-Karte lädt beide Originalfotos; keine Wette erfasst.
- Die gespeicherte Modell-/Preisdatei blieb vor und nach Deployment sowie
  Browserprüfung bytegleich: SHA-256
  `916beed520687a5304ef573fb2b8ac9a4fa624979cdebf0752816ff567bb8fdd`.
- Screenshots/CLI-Nachweise unter `output/playwright/identity-*20260930*`.
  Sie sind lokale Prüfartefakte, keine zusätzlich versionierten Datenkopien.

Der anschließende Nachweiscommit ändert ausschließlich diese Dokumentation
und die Übergabe, nicht den geprüften Produktivcode.
