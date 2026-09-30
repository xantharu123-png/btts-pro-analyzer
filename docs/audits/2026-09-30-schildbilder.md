# Originalbilder für die Sports-Editorial-Karten

Die erste Veröffentlichung ist nachfolgend historisch dokumentiert. Für den
aktuellen Bildweg gilt der letzte Abschnitt **Direktabruf ohne Server-Bildcache**.

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

## Direktabruf ohne Server-Bildcache, 30.09.2026

Auf Wunsch des Nutzers liegen die neuen Teilnehmerbilder jetzt vollständig
beim Anbieter. `sports_identity_media.py` liefert ausschließlich geprüfte
HTTPS-URLs und Quellenmetadaten. Keine HTTP-Anfrage, Bilddekodierung, Base64-
Übertragung, Binärdaten-RAM-Cache, Bilddatei- oder Datenbankkopie auf BetBoy.
Der kleine lokale Metadatenkatalog und die vorhandenen dekorativen Banner
bleiben bestehen. Normales HTTP-Caching im Kundenbrowser ist möglich.

- Codecommit `d4274a3981601ed724fd1d6651cf376b4ad1ce10` auf main gepusht,
  am 30.09.2026 um 11:50 CEST kontrolliert auf dem VPS gepullt und App neu
  gestartet. Kein neues Backup, keine Bereinigung oder zusätzlicher Sportscan.
- Nur native Fußball-PNG-Pfade und kleine, zum Originaldateinamen exakt passende
  Commons-Rasterthumbnails (maximal 400 px) erlaubt. Keine ursprünglichen
  Hochauflösungsdateien, fremden Hosts, Credentials, Querystrings oder SVGs.
  Direkte HTML-Bilder, keine externen Dokument-Einbettungen. Der Server prüft
  keinen HTTP-Status/MIME vorab; Verfügbarkeit behandelt der Kundenbrowser.
- Öffentliches Originalbild bleibt unverändert; CSS passt Vereinswappen ein
  und fokussiert Spielerbilder in der vorhandenen Schildkontur. `no-referrer`,
  Lazy Loading und Quellen-/Lizenzlink erhalten. Statischer UI-Fallback ohne
  Fetch, Speicherung, Konto-/Geldzugriff oder Modellcallbacks; Initialen beim
  Laden/Fehler. Neue DOM-Knoten und wiederverwendete Bilder mit geändertem `src`
  sind ebenfalls abgesichert.
- `pytest tests/test_wettfinder_identity.py tests/test_sports_identity_media.py
  tests/test_sports_identity_renderer.py tests/test_sports_editorial.py
  tests/test_wettfinder_surface.py tests/test_daily3_ui.py tests/test_daily3_store.py
  tests/test_workflow_integrity.py tests/test_riskobet_ui.py -q
  --basetemp .pytest_tmp/direct-image-20260930-final`: **464 bestanden**.
  Eigenständiger Review ohne Befund, eigener Gegenlauf 219 bestanden.
- Eigener lokaler Playwright-Browser: zwei 150×150-Vereinswappen und sechs
  330-px-Spielerbilder direkt vom Anbieter, alle acht Antworten HTTP 200;
  kein Netzwerk-/Page-/Console-Fehler im normalen Abruf. 1440/390/320 px ohne
  horizontalen Überlauf. Separater absichtlich simulierter 404 liefert Initialen
  und erwarteten Netzwerk-Konsoleneintrag; keine Page-Fehler. Bildwiederkehr und
  nachträglich eingefügte Match-Knoten funktionieren ohne Servercallback.
- Eigener echter Produktionsbrowser: Novak Djokovic vs Nuno Borges, beide
  Fotos direkt von `thumb.wikimedia.org`, HTTP 200, 330 px; weiterhin 75,9 %
  und letzte Quote 1,42. 1440/390/320 px ohne Überlauf oder Browserfehler,
  Moduswechsel zu Daily3 und zurück mit korrekt geladenen Bildern. Zu diesem
  Zeitpunkt keine Daily3-Auswahl vorhanden, daher kein neuer produktiver
  Daily3-Bildkarten-Nachweis; derselbe Präsentationspfad ist durch Tests gedeckt.
- App und Caddy aktiv, interner/öffentlicher Healthcheck `ok`, sieben Timer
  weiterhin geplant. Modell-/Preisdatei vor/nach Deployment bytegleich:
  `916beed520687a5304ef573fb2b8ac9a4fa624979cdebf0752816ff567bb8fdd`.
- Lokale Artefakte `output/playwright/direct-images-*20260930*` bleiben
  unversioniert. Vorhandene Audit-/Output-Dateien wurden nicht bereinigt.

Diese Änderung betrifft nur Darstellung und Speicher-/Übertragungsweg der
Teilnehmerbilder; sie belegt keine höhere Wettqualität. Nachweiscommit und
abschließender Pull ändern ausschließlich diese Dokumentation und Übergabe.

## Teamlogos weiterer Sportarten, 30.09.2026

Umfang: gemeinsame Schildkarten von Wettfinder/Daily3 für E-Sport, Basketball,
Eishockey und Cricket. Fußballwappen und Tennisfotos bleiben erhalten. Keine
Modell-, Preis-, Finanz- oder Kontoänderung; keine neuen Sport-/Quoten-Scans,
Sicherungen oder Bereinigungen. Bilder werden direkt extern im Browser geladen.

- 47 geprüfte Manifest-Bindungen: 32 aktive NHL-Teams, zwei EuroLeague-Teams,
  neun E-Sport-Teams sowie Indien/Australien bei zwei Cricket-Providern.
  NBA nutzt ESPN-Teamkennung ausdrücklich zusammen mit Wettbewerb NBA;
  WNBA/NCAA/fehlender Wettbewerb können keine NBA-Logos erhalten.
- Spieler-/Team-/Provider-Namensräume getrennt, vollständige Namen statt fuzzy
  Suche. Utah Mammoth ID 68; die inaktive Utah-Hockey-Club-ID 59 wird nicht
  wiederverwendet. Cricket zeigt die vom Anbieter verwendeten Nationalflaggen,
  nicht erfundene Clubwappen; andere nicht geprüfte Teams behalten Initialen.
- Konkreter visueller Quellenfehler gefunden: NAVIs `1w`-Bild zeigte ein rotes
  Dota-Spielicon. Aus Manifest und Allowlist entfernt, Ablehnungstest ergänzt;
  kein anderes Markenbild geraten. 1win bleibt bis zu einer echten geprüften
  Teamgrafik bei Initialen. Reine HTTP-200-Prüfung war dafür nicht ausreichend.
- E-Sport sammelt ausschließlich bereits empfangene native ID/Name/Logo-URLs
  erfolgreicher Spiele im bestehenden Suchfenster. Optionaler Seiteneffekt,
  kein weiteres HTTP und keine Änderung zurückgegebener Modellfelder/Hashes.
  Atomar und dedupliziert, maximal 256 Einträge / 128 KiB; keine Bildbytes/DB.
  Exakte PandaScore-CDN-ID plus dokumentierter 200px-`thumb_`-Rasterpfad.
- NHL-SVG ausschließlich offizieller externer `img`-Pfad, nie inline SVG oder
  Dokument-Embedding. Alle übrigen Logos Rasterbilder. Bestehende Schildform,
  Contain-Einpassung, no-referrer, Lazy Loading und Quellen-/Lizenzlinks erhalten.
- Betroffene Regression: **674 bestanden, ein erwarteter Windows-Symlink-Skip**.
  Einschließlich Scanner-Rückgaben, Provider-ID-Kollisionen, tatsächlichem
  Manifest, Quellen-/Autorenangaben, Grenzen, unveränderlichen Geld-/Modellfeldern
  sowie Wettfinder/Daily3/RisikoBet. Keine vollständige 11k-Vollsuite behauptet.
- Unabhängiger Gegencheck: beide Befunde (1w-Grafik und ESPN-Namensraum) behoben,
  47/47 Manifest-Einträge offline auflösbar, keine weiteren konkreten Findings.
- Eigener lokaler Browser: 18 geladene Bilder in neun Beispielpaarungen plus
  unbekanntes Paar mit Initialen; 1440/390/320 ohne horizontalen Überlauf.
  Antworten 200 beziehungsweise normale 304-Cachebestätigung; keine Page- oder
  normalen Console-/Requestfehler. Sichtbare Bilder kontrolliert, nicht nur DOM.
  Absichtlicher Bildausfall je neuer Sportart: Initialen bleiben sichtbar,
  Wiederherstellung sowie dynamisch eingefügte Knoten funktionieren. Dabei vier
  erwartete 404-Konsolenmeldungen, keine JS-Pagefehler. Streamlit-Iframe-
  Feature-Policy-Warnungen sind vorhandene Plattformwarnungen, keine Bildfehler.
- Metadatenquellen/Autoren und erlaubte Grenzen:
  [Identity README](../../assets/identity/README.md),
  [Teammanifest](../../assets/identity/team-logos.json).
  Die externen Betreiber erhalten normale Browserabrufe; eine freie Quelle
  bedeutet keine pauschale kommerzielle Markenfreigabe oder Teambefürwortung.

Produktionscommit, echte Live-Karten und unveränderter Modell-/Preishash werden
nach kontrolliertem Pull separat nachgetragen. Lokale Browserartefakte verbleiben
unversioniert unter `output/playwright/team-logos-*20260930*`.
