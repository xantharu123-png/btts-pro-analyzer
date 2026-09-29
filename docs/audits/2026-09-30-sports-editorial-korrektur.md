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

531 betroffene Tests bestanden in 13,34 Sekunden. Nach der letzten reinen
Tablet-CSS-Korrektur nochmals 35 enthaltene UI-Tests bestanden; keine Addition
überlappender Testzahlen, keine neue vollständige 11.000er-Suite behauptet.

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
Der Bildtest wartet auf abgeschlossene Medien-Downloads statt deren bloße
DOM-Präsenz; dauerhaft fehlende Bilder bleiben ein Fehler.

Lokale ungetrackte Nachweise: `output/playwright/editorial-v2-qa.js`,
`editorial-v2-1536.png`, `editorial-v2-390.png`, `editorial-v2-760.png`,
`editorial-v2-case-Daily3.png`, `editorial-v2-case-Keine-Auswahl.png` und
`editorial-v2-touch.png` / `editorial-v2-touch.js`.
Bekannte alte Audit-/Output-Dateien wurden nicht gelöscht oder ins Release aufgenommen.

## Veröffentlichung

Vor dem Commit noch nicht veröffentlicht. Ziel ist der reguläre Push auf main,
kontrollierter Fast-forward des VPS und Neustart ausschließlich der App, ohne
neues Backup, Bereinigung, Timeränderung oder zusätzlichen Sport-/API-Scan.
Der tatsächliche Live-Nachweis wird erst nach diesen Schritten ergänzt.

## Grenzen

Keine physische Geräte- oder native Store-Prüfung. Modellqualität sowie
numerisch nachgewiesene Verletzungs-, Wetter- und Müdigkeitseffekte bleiben
separate Arbeiten; dieses Designpaket belegt keine bessere Wett-Rendite.
