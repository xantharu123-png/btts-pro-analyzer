# Sports Editorial – umgesetzte Landingpage

Der Nutzer hat `selected-remix.png` mit „ja genau so bitte umsetzten diese
landigpage passt“ freigegeben. Am 06.10.2026 im bestehenden Django-Portal umgesetzt,
ohne Frameworkwechsel, neue Sportberechnung oder Änderung der Zahlungslogik.

## Einstieg

- Templates: `portal/templates/landing.html`, erweiterbare Blöcke in `base.html`.
- Scoped Styles: `portal/static/portal/editorial.css` (`editorial`/`e-*`).
- DE/EN: `portal/members/copy.py`; kumulativer Tarifkatalog unverändert in `plans.py`.
- 15 neue Verträge: `portal/members/test_landing_editorial.py`.
- Vollständiger Prüfbericht: [design-qa.md](../../../design-qa.md).
- Vorschau: <http://127.0.0.1:8010/de/> / <http://127.0.0.1:8010/en/>.

## Bild- und Fontbudget

Alle Laufzeitassets unter `portal/static/portal/editorial/`: **23 Dateien,
1.128.615 Bytes insgesamt** einschließlich beider Sprachen, Fonts und Lizenzen.
Die acht WebPs zusammen belegen 988.634 Bytes. Ein Besucher lädt die ausgewählten
Bildkandidaten einer Sprache, nicht alle acht Dateien.

| Datei | Pixel | Bytes |
| --- | --- | ---: |
| hero.webp | 1120 × 1120 | 225486 |
| hero-small.webp | 640 × 640 | 117118 |
| hero-en.webp | 1120 × 1120 | 234764 |
| hero-en-small.webp | 640 × 640 | 111896 |
| stadium.webp | 1600 × 582 | 107730 |
| stadium-small.webp | 800 × 291 | 43176 |
| stadium-en.webp | 1600 × 582 | 104962 |
| stadium-en-small.webp | 800 × 291 | 43502 |

Beispielbudget pro Sprache bei beiden großen Bildern: DE 333.216 Bytes,
EN 339.726 Bytes. Mit beiden kleinen Kandidaten DE 160.294 / EN 155.398 Bytes.
Der Browser entscheidet über `srcset`/`sizes` und Pixeldichte; diese Summen sind
keine Garantie für den Download bei jedem Gerät. Hero priorisiert, Footer lazy;
intrinsische Bildmaße gesetzt. Keine High-quality-PNGs im Laufzeitverzeichnis,
keine externen Fonts/Tracking- oder Bildprovideraufrufe beim Rendern.

### Herkunft und Bildinhalt

Hero/Stadionmotive wurden mit dem integrierten Bildgenerator nach der freigegebenen
Sportkomposition erstellt, jeweils mit DE-/EN-Beschriftungen. Telefon-Screens sind
**fiktive statische Illustrationen**, keine aktuellen Tipps oder verifizierten
Spieler-/Clubdaten. Keine echten Kundenfotos, Testimonials oder Leistungszahlen.
Die Bildänderungen erfolgten mit dem Bildgenerator; WebP-Kodierung/Skalierung
liefert die responsiven Laufzeitkandidaten.

Lokale, absichtlich nicht mitcommittete Quell-/Promptbelege:
`output/landing-20261006/hero-source.png`, `hero-prompt.json`,
`hero-en-source.png`, `hero-en-prompt.json`, `stadium-source.png`,
`stadium-en-source.png`, `stadium-en-edit-metadata.md`.
Der Stadionauftrag: großflächiges abendliches Fußballstadion mit Fanpublikum,
dunkelgrüne Sportkampagne und genügend freier zentraler Fläche für echten HTML-CTA.
Englische Fassung übersetzt die eingebrannte Kampagnenbeschriftung.
Dateien/Prompts enthalten keine Zugangsschlüssel oder Kunden-/Geldhistorie.

### Schrift-/Icon-Lizenzen

- **League Gothic:** Google Fonts, SIL Open Font License 1.1.
  [Fontquelle](https://fonts.gstatic.com/s/leaguegothic/v13/qFdR35CBi4tvBz81xy7WG7ep-BQAY7Krj7feObpH_-am.ttf),
  [Lizenzquelle](https://raw.githubusercontent.com/google/fonts/main/ofl/leaguegothic/OFL.txt);
  lokal `league-gothic.ttf` / `League-Gothic-OFL.txt`.
- **Barlow**, Latin Regular/Medium/Semibold/Bold: Google Fonts, SIL OFL 1.1.
  [Projekt/Lizenz](https://github.com/google/fonts/tree/main/ofl/barlow);
  lokal vier `.woff2` / `Barlow-OFL.txt`.
- **Bootstrap Icons 1.13.1:** offizielle unveränderte SVGs, MIT.
  [Projekt](https://github.com/twbs/icons/tree/v1.13.1),
  lokal `Bootstrap-Icons-LICENSE.txt` und sieben SVGs.
- Georgia ist der vorhandene Systemfont-Fallback, keine kopierte Fontdatei.

## Reproduzierbare lokale Prüfung

Die geerbten venv-Launcher verweisen auf einen nicht vorhandenen alten
Python-Installationspfad. Nicht blind löschen/reinstallieren. Für den tatsächlichen
43er-Testlauf wurden die vorhandenen reinen Portalabhängigkeiten mit dem
bereitgestellten Python verwendet:

```powershell
Set-Location C:\Projekt\BetBoy\betboy-app\portal
$env:PYTHONPATH = 'C:\Projekt\BetBoy\betboy-app\.portal-venv\Lib\site-packages'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\miros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' manage.py test --settings=siteconfig.qa_settings --noinput --verbosity 1
```

Nicht aus dem Repo-Root ohne explizites Testlabel starten: das entdeckt hier
keine Portaltests. QA-Settings nutzen In-memory-DB/simulierte externe Dienste.
Lokale Vorschau, ebenfalls ohne Migration oder Kundenkontoerzeugung:

```powershell
$env:BETBOY_PORTAL_DEV = '1'
& 'C:\Users\miros\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' manage.py runserver 127.0.0.1:8010 --noreload
```

Vorlage-/Copyänderungen erfordern bei `--noreload` einen Serverneustart;
CSS wird beim Reload neu geladen. Server ausschließlich auf Loopback.

## Absichtliche Releasegrenze

Keine echte September-Ergebniszahl belegt: Status „Noch keine veröffentlichte
Monatsbilanz.“ statt erfundener 74 %. Preise CHF 9.90 / 19.90 / 29.90 monatlich,
kein Gratis-Testabo, gleiche Modellqualität. Bestehende Login-/Registrierungs-
und Kontopfade bleiben, Registrierung im Pre-launch geschlossen.
Kein Portalservice/Stripe-/SMTP-Setup auf dem VPS durch diesen Auftrag erstellt.
Sales-Readiness, Recht/Länder, Mail/Billing-E2E, Reconciliation und Stores bleiben
separate Aufgaben in `TODO_AKTUELL.md`; die Designfreigabe öffnet sie nicht.
