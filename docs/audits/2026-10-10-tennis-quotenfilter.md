# Tennis-Quotenuntergrenze – Produktionsnachweis 10.10.2026

## Konkrete Ursache

Der gespeicherte Tagesbestand enthält 16 Tennisprognosen. Der generische
Preisprüfpool begrenzte den Tennisabruf auf zehn Ereignisse, obwohl die Quelle
alle Ereignisse desselben Sportkeys in einer Sammelanfrage beantwortet.
Alcaraz/Cerundolo ist das 15. Ereignis: unveränderte Modellchance
92,35031193346213 %, aber keine zugeordnete Quote. Fehlende Preise dürfen laut
Produktregel offen bleiben; deshalb konnte der bestehende 1,20-Filter nicht greifen.

Zusätzlich konnte ein erfolgloser neuer Abruf eine zuvor exakt zugeordnete
Niedrigquote entfernen. Auch diese Stelle ist korrigiert: alte Beobachtung mit
Originalzeitstempeln behalten, aber daraus keine neue Ausführungsfreigabe erzeugen.
Fremde neue Belege werden abgelehnt, nicht zur Preisberechnung verwendet.

## Eng begrenzte Änderung

- Tennis verwendet den vorhandenen begrenzten Sportkatalog statt des
  Fußballlimits von zehn separat abgefragten Begegnungen.
- Teilnehmer-, Startzeit-, Ereignis-, Markt- und Seitenbindung unverändert.
- Vorhandener Abruf-Cooldown, Tages-/Monatskontingent und maximal acht
  Discovery-Sportkeys bleiben erhalten. Keine automatische Tarifänderung.
- Gespeicherte zusätzliche Tennis-Gegenpreise bleiben begrenzt auf zehn
  Ereignisse / zwanzig Seiten; keine Vergrößerung der Nachweishistorie.
- Keine Modellwahrscheinlichkeit, Auswahlrangfolge, Einsatzregel oder Geldbuchung
  geändert. Fehlende Preise nicht aus Modellchancen geschätzt oder als 1,02 erfunden.

Quellen im bestehenden Code: Tennis-Siegerquoten über The Odds API, Fußball über
API-Football. Die offiziellen [Quota- und Batchbedingungen](https://the-odds-api.com/liveapi/guides/v4/)
rechnen beim verwendeten Sport-Quotenendpunkt pro Markt und Region, nicht pro
Ereignis in derselben Antwort. Andere Sportkeys können weiterhin eigene Credits
benötigen; keine Behauptung, sämtliche Sportarten kosteten zusammen nur einen.

## Software- und Linuxprüfung

Test-first: die neue 16-Ereignis-Regressionsdatei ergab vor der Korrektur drei
Fehler / fünf erfolgreiche Fälle. Nach dem Fix letzte gemeinsame lokale Runde:
**352 Tests bestanden**, Exit 0, 9,18 Sekunden. Keine neue Vollsuite behauptet.
27 neue parametrische Fälle in den beiden Dateien; exakte 1,02, 1,20-Grenze,
Cooldown, andere Tage/Märkte/Spieler sowie fehlgeschlagene/fremde Antworten.
Unabhängiger Code- und Deploymentreview ohne blockierende Befunde.

VPS-Python hat kein pytest; keine Installation dafür vorgenommen. Stattdessen
den exakt gepushten Quelltext lesend im Arbeitsspeicher geladen und beide
Funktionsänderungen gegen 16 Offline-Ereignisse gegengeprüft: alter Pool zehn,
neuer Pool sechzehn, alle sechzehn exakten Preise, 1,02 ausgefiltert, nach
erfolglosem Refresh erhalten. Null Netzwerkaufrufe / null Datenbankänderungen.

## Veröffentlichung und echte Preise

Codecommit `097f4fae692ef0083af94b03c9af1f2e4b241c1a` auf GitHub main und
BetBoy-VPS per Fast-forward unter bestehender Deploylock veröffentlicht.
App/Caddy aktiv, interner und öffentlicher Healthcheck `ok`. Während des
Deployments beide Produktions-JSONs per SHA-256 unverändert.

Danach einmal bestehendes `refresh_prices_only(quote_sport="tennis")` unter
derselben erneut erworbenen Lock ausgeführt; kein Modell- oder Sportscan.
Konfiguration nur intern gelesen, keine Schlüssel ausgegeben. Zusatzlimit im
Prüfaufruf: höchstens ein kostenpflichtiger Credit.

Echter Abruf am **10.10.2026 um 08:43 Europe/Zurich**:

- Acht noch bevorstehende Tennisereignisse geprüft, acht exakte Preise,
  null Abruffehler / null operative Quotenfehler. Bereits gestartete Begegnungen
  werden nicht erneut als Pre-Match-Auswahl geprüft.
- Kostenfreie Sport-/Event-Discovery plus eine Shanghai-H2H-EU-Sammelanfrage;
  offizieller `x-requests-last=1`, Restkontingent 490 → 489.
- Alcaraz/Cerundolo, Sieg Carlos Alcaraz: tatsächlich beobachtete **Bestquote
  1,05**. Das ist nicht die manuell genannte 1,02, liegt aber ebenso unter 1,20.
  Exakte Ereignis-/Spieler-/Marktbindung geprüft, Publikationsfilter greift.
- Tatsächlicher Wettfinder-Katalog enthält diesen Kandidaten nicht mehr.
- Sämtliche Modellprojektionen und ursprüngliche Erzeugungszeit unverändert;
  RisikoBet-Snapshot ebenfalls unverändert. Keine Geldbuchung vorgenommen.

Interner Browser nach Reload: Alcaraz verschwindet sowohl aus dem Spielkatalog
als auch aus der Daily3-Kurzliste. Andere erlaubte Preise bleiben sichtbar,
beispielsweise Tsitsipas/Darderi mit 1,46. Keine externen Browser übernommen.
Lokale Offline-/VPS-Prüfskripte und Screenshotbelege liegen unter
`output/playwright/alcaraz-floor-20261010/`, nicht pauschal mitgecommitted.

## Grenzen des Abschlusses

Dieser Bericht bestätigt den konkreten Quotenabruf-/Filterfix, keine bessere
Wett-Rendite. Der vorhandene Wettfinder-Fehlstatus, Daily3-Zeitplanung,
fachliche Kontextmodelle, Domainumzug, Stripe und Store-Freigaben bleiben
getrennte Aufgaben. Keine neuen Backups, Bereinigungen oder Modellscans.
