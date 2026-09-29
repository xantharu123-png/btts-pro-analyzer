# Sports Editorial – Korrektur nach Vorlagenvergleich

## Anlass und Umfang

Der Nutzer hatte Design 2 für den Webbrowser und den Mix 2+5 für Mobil gewählt.
Die erste Umsetzung war technisch funktionsfähig, aber strukturell zu weit von
den Referenzen entfernt. Die vorige Meldung „abgenommen“ war deshalb zu weitgehend.

Ausgangspunkt: `f5b17214d6ff315f2fcdad422378495e83c4f23f` auf lokalem main,
GitHub und VPS. Korrigiert wird die bestehende responsive Streamlit-Oberfläche;
keine native Store-App, kein Modellneubau und keine Kundenzahlungsaktivierung.

## Konkrete Änderungen

- Kompakter horizontaler Kopf, schwarzer BetBoy-Schriftzug und grüne Editionzeile.
- Desktop-Spielkarte: Begegnung links, Auswahl/Modell/Quote und knapper Grund
  rechts; Formvergleich darunter. Keine zusätzliche losgelöste Matchüberschrift.
- Farbige S/U/N-Ergebnisse mit echten Gegnernamen und Resultaten. Drei
  Gegnerzeilen direkt sichtbar; weitere Einzelspiele und deren Datum, Wettbewerb,
  Spielort oder Rangdetails bleiben anklickbar. 5/10-Schalter bleibt bedienbar.
- Weitere Märkte sichtbar innerhalb derselben Spielgruppe; deren wiederholte
  Analyse ist optional. Identische Formlisten nicht mehrfach wiederholen.
- Daily3- und Tennisspalte mit zwei generischen lokalen Sportbildern. Kein
  erfundenes Redaktionsteam oder künstliches Auffüllen von drei Tageswetten.
  Leerer Spieltag behält den Magazinaufbau und einen kurzen ehrlichen Leerzustand.
- Einspaltiger Mobil-/Tablet-Umbruch; fünf bestehende untere Navigationsziele.
  Daily3-Karten unterhalb 1024 px gestapelt, nicht in engen parallelen Spalten.
- Keine Änderungen an Auswahlreihenfolge, Wahrscheinlichkeiten, gebundenem
  1,20-Filter, Daily3-Budget, Geldbuchungen oder bestehenden Abo-Rechten.
  Die Tennisvorschau verwendet denselben gefilterten Katalog, keinen Preis-Bypass.

Bilddateien insgesamt etwa 4,8 MB, unverändert lokal versioniert; Streamlit
liefert die Anzeige als JPEG aus. Keine externen Bildabrufe oder riesigen
eingebetteten Bild-Strings. Provenienz: `assets/editorial/README.md`.

## Tests und Browserprüfung vor Veröffentlichung

Finaler Stand: 531 betroffene Tests bestanden in 13,94 Sekunden, einschließlich
der Produktions-Wrapper-Korrektur. Der vorherige 35er-Zwischenlauf ist darin
enthalten; keine Addition überlappender Zahlen und keine neue vollständige
11.000er-Suite behauptet.

```powershell
.\.codex_test_venv\Scripts\python.exe -m pytest tests/test_sports_editorial.py tests/test_forecast_compact.py tests/test_daily3_selection.py tests/test_daily3_comparison.py tests/test_daily3_store.py tests/test_daily3_ui.py tests/test_wettfinder_surface.py tests/test_workflow_integrity.py tests/test_publication_odds_floor.py tests/test_riskobet_ui.py tests/test_riskobet_surface.py tests/test_riskobet_football_recent_results.py tests/test_football_recent_results.py tests/test_tennis_customer_facts.py tests/test_team_customer_facts.py tests/test_tennis_tab.py tests/test_forecast_analysis.py tests/test_customer_access.py -q --disable-warnings --maxfail=2
```

Isolierte Vorschau mit ausdrücklich markierten Beispieldaten; keine produktive
Datenbank und kein Sport-/API-Scan. 31 Kombinationen: normale Seite bei
1536/1440/1024/761/760/390/320 px; lange Namen, kurze Historie, leere Auswahl,
Daily3, RisikoBet und Abo-Hinweis jeweils bei 1440/760/390/320 px.

- Kein horizontaler Seitenüberlauf oder Fehleroverlay; keine Page-/Console-Fehler.
- Bilder vollständig geladen, kein abgeschnittener Covertext. Spaltenbreiten
  und tatsächlicher Stapelwechsel zusätzlich zur Seitenbreite gemessen.
- Spielblock, Ergebnis- und Gegnerdetails per Maus und Enter bedient.
  5/10-Wechsel per Klick und Pfeiltaste; drei Desktop-/Mobilrückwege bestanden.
- Separater Touch-Browser bei 390 px: Zehnerauswahl, Ergebnisdetails und
  RisikoBet/Finder-Rückweg per Tap bestanden, ohne Page-/Console-Fehler.
- Mindestens 44 px Mobilziele, alle fünf unteren Navigationseinträge erreichbar,
  auch auf unverändert gesperrten Abo-Seiten. Kein neues Zugriffsrecht vergeben.
- Originalreferenzen unverändert erhalten und tatsächlich visuell verglichen.
  Neutrale Initialen ersetzen fiktive Wappen; echte Inhalte können von den
  Beispieldaten der Designstudien abweichen. Keine Nutzerabnahme vorwegnehmen.

Die Prüfung fand und korrigierte echte Fehler: nicht greifende CSS-Selektoren
für verschachtelte Streamlit-Spalten (760-px- und Daily3-Ansicht) sowie einen
um 2 px abgeschnittenen Mobil-Covertext. Kein Prüftoleranzwert wurde gelockert.
Beim frischen Produktionsvergleich außerdem den zusätzlichen Leerabstand
eines verschachtelten, unsichtbaren Kontobrücken-Iframes korrigiert. Die lokale
Vorschau bildet jetzt diesen nativen Null-Höhen-Wrapper ohne echtes Konto nach.
Sein Browser-/Speicher-Code wird nicht geändert oder deaktiviert. Der Covertext
erhält explizite Zeilenhöhe ohne native Überschriften-Zusatzabstände.
Der Bildtest wartet auf abgeschlossene Medien-Downloads statt deren bloße
DOM-Präsenz; dauerhaft fehlende Bilder bleiben ein Fehler.

Lokale ungetrackte Nachweise: `output/playwright/editorial-v2-qa.js`,
`editorial-v2-1536.png`, `editorial-v2-390.png`, `editorial-v2-760.png`,
`editorial-v2-case-Daily3.png`, `editorial-v2-case-Keine-Auswahl.png` und
`editorial-v2-touch.png` / `editorial-v2-touch.js`.
Bekannte alte Audit-/Output-Dateien wurden nicht gelöscht oder ins Release aufgenommen.

## Veröffentlichung

Erster UI-Commit `ab5cd900352b5f3f16ee840c8764d058f304ca35` um 01:46 CEST
auf main gepusht und per kontrolliertem Fast-forward auf den VPS gezogen.
Nur die App neu gestartet; beide Healthchecks `ok`. App/Caddy und die sieben
bestehenden Timer aktiv, Tagesbackup weiter deaktiviert, keine neue Sicherung
oder Sport-/API-Abfrage. Der Transportcontroller hatte nach erledigtem Pull,
App-Neustart und Healthcheck einen abschließenden Windows-CR-Zeilenfehler;
eine unabhängige SSH-Prüfung bestätigte den tatsächlich erfolgreichen Deploy.

Frischer isolierter Produktionsbrowser: sieben Breiten ohne Überlauf oder
Fehleroverlay, beide Coverbilder geladen; 22 gespeicherte RisikoBet-Karten und
erster Desktop-/Mobilrückweg geprüft. Keine Page-/Console-/Request-Fehler;
neun schon vorher vorhandene iframe-/Permissions-Policy-Warnungen. Für den
neuen Tag noch kein automatisches Ergebnis vor dem regulären 03:35-Termin;
keine Live-Tipps fingiert und kein Zusatzscan gestartet.

Finaler UI-Commit **`c6b66c341479d7423935b5a25222b5dd7150833f`** um
01:56 CEST auf main gepusht und per Fast-forward auf den VPS gezogen;
Controller Exit 0. Nur die App neu gestartet. Interner und öffentlicher
Healthcheck `ok`, App `active/running`, Caddy und die sieben Timer aktiv.

Endgültige frische Produktionsprüfung: 1536/1440/1024/761/760/390/320 px
ohne Überlauf oder Fehleroverlay, korrekt gestapelte Mobilspalten, beide Bilder
geladen, kein Cover-Text abgeschnitten. Kopf beginnt bei 46,6 px am Desktop
und 15,2 px auf Mobil statt des vorherigen unsichtbaren Iframe-Leerabstands.
23 tatsächlich gespeicherte RisikoBet-Karten gerendert; erster direkter
Desktop-/Mobilrückweg bestanden. Keine Page-/Console-/Request-Fehler; die
neun vorhandenen Chromium-/iframe-Warnungen bleiben. Screenshots erst im
fertigen `notRunning`-Zustand erstellt, nicht während eines ausgegrauten Rerenders.
Live-Nachweise: `editorial-v2-live-qa.js`, `editorial-v2-live-1536.png`,
`editorial-v2-live-390.png` im bewahrten lokalen Output-Verzeichnis.

Der folgende Nachweiscommit ändert ausschließlich diese Dokumentation und die
beiden Übergaben. Der getestete UI-Code bleibt identisch; sein reiner VPS-Pull
benötigt keinen weiteren App-Neustart oder Sportscan.

## Grenzen

Keine physische Geräte- oder native Store-Prüfung. Modellqualität sowie
numerisch nachgewiesene Verletzungs-, Wetter- und Müdigkeitseffekte bleiben
separate Arbeiten; dieses Designpaket belegt keine bessere Wett-Rendite.
