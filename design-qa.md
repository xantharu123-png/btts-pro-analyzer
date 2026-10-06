# Design QA – freigegebene BetBoy-Landingpage

Stand: 06.10.2026. Umfang: vorhandenes Django-Kundenportal, nicht der
Streamlit-Analyse-Workspace oder ein produktiver Verkaufsstart.

## Referenz und geprüfter Zustand

- Vom Nutzer ausdrücklich freigegebene Vorlage:
  `docs/design/landingpage-20261006/selected-remix.png` (1024 × 1536 px).
- Umsetzung: `portal/templates/landing.html`, `portal/static/portal/editorial.css`,
  DE/EN-Texte in `portal/members/copy.py`.
- Laufende lokale Vorschau: <http://127.0.0.1:8010/de/> und
  <http://127.0.0.1:8010/en/>; interner Browser, anonymer Besucher, Verkauf geschlossen.
- Freigegebene Reihenfolge: Hero → drei Schritte → Monatsbilanz September 2026
  → drei Abos → Stadion-CTA/Footer. Keine bedienbare Gratis-Produktdemo.

## Visuelle Nachweise

Alle folgenden Belege liegen lokal in `output/landing-20261006/`; generierte
Quell-PNGs und Browserbilder wurden nicht als Laufzeitassets eingebunden.

| Zustand | Tatsächlich gespeicherter Beleg |
| --- | --- |
| DE, 1024 × 850 CSS-Viewport, ganze Seite | `desktop-de-1024.jpg` |
| EN, 1024 × 850, lokalisierte Bildmotive | `desktop-en-1024.jpg` |
| DE, 1440 × 900 | `desktop-de-1440-final.jpg` |
| DE, 901 × 900, Desktop-Breakpoint | `tablet-de-901-final.jpg` |
| DE, 900 × 900, mobiles Layout | `tablet-de-900-final.jpg` |
| DE, 390 px breit | `mobile-de-390-final.jpg` |
| EN, 320 px breit | `english-320-final.jpg` |
| Tastaturbedienbares mobiles Menü | `mobile-menu-open.jpg` |
| Plus-Auswahl CHF 19.90, Registrierung geschlossen | `register-plus.jpg` |
| Vorhandener Login | `login-de.jpg` |

Zusätzlich die Grenzen 761/760 px geprüft. Abschließend bei 901 und 900 px
`scrollWidth == clientWidth`; ebenso bei 390/320 px. Beide WebP-Motive geladen.
Letzter Browser-Warn-/Fehlerlog leer. Temporäre Viewport-Overrides zurückgesetzt;
die interne Vorschau als Nutzer-Ergebnis offen gehalten.

### Vergleich mit derselben Vorlage

`qa_comparison.py` erzeugt die tatsächlich angesehenen Vergleichspaare:
`comparison-full.jpg`, `comparison-hero.jpg`, `comparison-plans.jpg`.
Grundlagen: `normalized-reference.jpg`, `normalized-implementation.jpg` und
`layout-de-1024.json`. Die Referenz wurde proportional auf 1009 × 1514 px
verkleinert. Der Implementierungs-Screenshot misst 1009 × 1723 px; für den
Vergleich wurde ausschließlich der zusätzliche 27-px-Pre-launch-Banner entfernt
(1009 × 1696). Keine vertikale Streckung und keine Browser-Chrome verglichen.
Die tatsächliche Capture-Auflösung wurde anhand der Bilddateien geprüft;
Scrollbarbreite kann von der angeforderten CSS-Viewportbreite abweichen.

Die Umsetzung ist keine behauptete pixelidentische Kopie. Der reale Katalog,
übersetzte Texte, Verkaufsstatus und zugängliche Bedienelemente benötigen etwas
mehr vertikalen Raum als der Bildentwurf. Visuelle Hierarchie, Reihenfolge,
Farbwelt, Bildkomposition und natürliches vollständiges Smartphone bleiben erhalten.

## Vergleichsrunden und korrigierte Befunde

| Runde | Befund | Umgesetzte Korrektur / erneute Prüfung |
| --- | --- | --- |
| 1 | P1: Headline vier statt zwei Zeilen, Hero zu hoch | Wirklich schmale League-Gothic-Schrift statt breiter Ersatzschrift; Desktop erneut aufgenommen |
| 2 | P2: Abokarten zu lang und textlastig | Kompakte sichtbare Funktionsnamen; vollständige Namen für assistive Technik erhalten; Preise/Umfang unverändert getestet |
| 3 | P2: schmale Tabletansicht gedrängt | Mobiles Layout bereits bis 900 px; Benefit-Breite auch am 901-px-Breakpoint begrenzt; beide Seiten der Grenze erneut aufgenommen |
| 4 | P2: EN-Seite mit deutschen Bildbeschriftungen | Eigene lokalisierte EN-Hero-/Stadionmotive, geladene Assets und Rendervertrag geprüft |
| 5 | P2: geerbte Konto-Navigation zeigte auf entferntes `#mobile` | Auf existierenden Monatsbilanzabschnitt geändert; Regression zuerst rot, danach grün |
| Abschluss | Mobile Menü-/Sprachziele und Icon/Text-Anordnung | Native Details-Navigation, sichtbarer Fokus, ausreichend hohe Ziele; finales DE/EN-Mobile geprüft |

## Fünf Fidelity-Flächen

- **Typografie:** extrem schmale zweizeilige Hero-Headline, Barlow für UI,
  Georgia für Wortmarke/sekundäre Überschriften; lokal eingebundene Fonts.
- **Abstände/Layout:** großzügiger Editorial-Hero, Dreischrittzeile, kompakte
  Monatsbilanz vor den drei Karten; Plus hervorgehoben, Karten auf Mobil gestapelt.
- **Farben:** Creme `#f8f7f1`, Dunkelgrün `#103f31`, Ink `#08181d`, Lime `#d5f35b`.
- **Bildmaterial:** richtige Sportcollage statt Platzhalterflächen, kompletter
  natürlich proportionierter Telefonkörper; responsive komprimierte WebPs.
- **Text/Hierarchie:** Auswahlgründe/Form statt technischem Jargon; echte
  CHF-Preise, keine erfundene Trefferquote, Testimonials, Kundenzahlen oder Store-Badges.

## Funktionsprüfung

Frischer vollständiger Portal-Lauf aus `portal/`:

```text
manage.py test --settings=siteconfig.qa_settings --noinput --verbosity 1
Ran 43 tests in 10.119s
OK
System check identified no issues (0 silenced)
```

15 neue Render-/Verhaltenstests; keine Addition überlappender Testläufe.
Prüft u. a. DE/EN, Reihenfolge, alle serverseitigen Tarifmerkmale, Preise,
authentifizierte/anonymous Links, statische Assets, geschlossenen Verkauf und
öffentliche Darstellung ohne Provideraufrufe/DB-Schreiboperationen.
Stripe/Mail bleiben in diesen Tests simuliert. Erwarteter negativer Billing-Test
loggt `BillingUnavailable`; kein unaufgeklärter Testfehler.

Browser: Hero-/Footer-CTA auf Abos, Plus-GET mit gewähltem Tarif, Login-GET,
Sprachwechsel und Menü per Tastatur tatsächlich geprüft. Keine Registrierung
abgesendet, kein echter Kauf und keine Änderung von Kundendaten.
Unabhängiges Abschlussreview: keine offenen P1/P2-Befunde innerhalb dieses Umfangs.

## Restgrenzen

- P3: generative Illustrationen und verfügbare lizenzierte Fonts sind nicht
  dieselben Quelldateien wie der ursprüngliche Entwurf. Bildscreen ist ausdrücklich
  fiktiv; seine kleinen Formzeichen sind keine nachgewiesenen Tennis-/Fußballresultate.
- Echte Monatsbilanz bleibt unveröffentlicht. Der Abschnitt zeigt keine erfundenen
  Zahlen; Datenwerbung muss separat anhand veröffentlichter Kundenauswahlen belegt werden.
- Reale Geräte/Touch, umfassender WCAG-/Zoom-Audit, echte Stripe-/SMTP-Transaktionen,
  Produktionsproxy und Apple-/Google-Store-Abnahme wurden nicht durchgeführt.
- Kein VPS-Deployment oder Verkaufsstart durch diese Designfreigabe.
  Aktuelle Modell-/Scanner-Restarbeiten sind dadurch nicht erledigt.

**final result: passed** – für die freigegebene lokale Landingpage-Umsetzung und
die hier dokumentierten Sicht-/Funktionsprüfungen; keine pauschale Releasefreigabe.
