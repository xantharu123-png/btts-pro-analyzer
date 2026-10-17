# BetBoy – kurzer Wegweiser

Stand: 17.10.2026. Die historischen Handbücher bleiben als Nachweis erhalten;
dieser Einstieg ersetzt weder Modellverträge noch Buchhaltungshistorie.

## Datenfluss

1. Sportquellen liefern Spielplan, abgeschlossene Ergebnisse und verfügbare
   Statistiken. Schlüssel kommen über `config_loader.py`, niemals aus Git.
2. Sportmodelle berechnen ihre Wahrscheinlichkeiten. Fußball:
   `challenge_engine.py`; Tennis: `tennis/`; E-Sport: `esports_elo.py`;
   weitere Teamsportpfade: `multi_sport_recommendations.py`.
3. `wettfinder_automation.py` veröffentlicht persistierte Prognosesnapshots.
   Quotenabruf und Diagnose sind ein eigener Pfad; eine Quote verändert nicht
   nachträglich die Modellwahrscheinlichkeit.
4. `forecast_selection.py` und `selection_coherence.py` wählen aus dem gesamten
   kanonischen Pool. `wettfinder_surface.py` baut Karten. Ein sichtbarer Ersatz
   für einen ausgefilterten Hauptmarkt braucht dieselbe Quelle und Modellrevision.
5. Streamlit `app.py` zeigt gespeicherte Ergebnisse. Daily3 und 15K verwenden
   eigene Auswahl-/Buchhaltungsregeln, keine unabhängigen Zweitprognosen.

## Persistenz und Verträge

| Bereich | Verantwortlicher Code | Bedeutung |
| --- | --- | --- |
| Laufzeitpfade und sichere Artefakte | `runtime_paths.py`, `db_paths.py` | Gemeinsame Pfade/Dateigrenzen; kein Freibrief zum Löschen |
| Prognoseoriginale und Entscheidungen | `forecast_evidence.py`, `football_original_storage.py` | Zeit-/Quellbindung, Replay, getrennte Nachweise |
| Wettfinder/RisikoBet-Snapshots | `runtime_state/` | Lesbare Veröffentlichungsstände, keine Echtgeldbuchungen |
| Gemerkte/gespielte Tipps | `tip_store.py` | Lesezeichen und manuelle Erfassung; nicht mit Echtgeld-Ledgern summieren |
| Daily3-Konto | `daily3_store.py` | CHF-Centbeträge, bestätigte Buchungen, signierte Ereignisse |
| 15K-Konto | `challenge_store.py` | Eigenständige Ticket-/Abrechnungshistorie; historische Währung erhalten |
| Kontextbeobachtungen und Effekte | `context_sources/`, `context_runtime*` | Beobachtete Daten sind noch kein validierter Wahrscheinlichkeitseffekt |

Es gibt noch mehrere Datenbankfamilien. Keine pauschale Konsolidierung oder
`VACUUM`/Löschung ausführen: Abhängigkeiten und freier Speicher müssen separat
geprüft werden. Ein SHA/HMAC schützt nicht automatisch vor dem gemeinsamen
Zurückspielen einer kompletten Datenbank und ihres alten Zustandsankers.

## Lokal starten und testen

- Python-Abhängigkeiten: `requirements.txt`; zusätzlich braucht die QA unter
  anderem pytest. Ein plattformübergreifendes Lockfile/CI bleibt offen.
- Lokaler Start aus dem gewünschten Checkout: `python -m streamlit run app.py`.
  Aktive Produktionsjobs **nicht** zusätzlich lokal einrichten.
- Tests: `python -m pytest tests`. Für die aktuelle vollständige Offline-QA
  gelten die im Auditbericht verlinkten Launcher, Quellenhashes, Gruppen und
  JUnit-Belege. Teilmengen und übersprungene Linuxfälle sind keine Vollabnahme.
- `tests/customer_label_font_probe.cjs` prüft die echten CSS-Schriftgrößen mit
  Chromium. Das ist kein Nachweis für eine gesamte Produktions-Browsersitzung.

## Produktion

Git-Remote: `xantharu123-png/btts-pro-analyzer`, Branch `main`.
VPS-Checkout `/opt/betboy/app`, Python `/opt/betboy/venv/bin/python`,
App `betboy-app.service`, Reverse Proxy `caddy.service`.
Secrets: `/etc/betboy/betboy.env`; die ignorierte INI bleibt für direkte
Legacy-Leser vorhanden. Streamlit-Secrets hätten Vorrang und müssen bei
Schlüsseländerungen mitgeprüft werden.

Timer berechnen Daten; sie deployen keinen Code. Releases brauchen einen
geprüften Fast-Forward, gezielte Smokeprüfung, App-Neustart und Healthchecks.
Der Nutzer verlangt **keine neuen Backups**; der normale Updatehelfer mit
eingebauter Sicherung ist dafür nicht ungeprüft aufzurufen. Der konkrete
No-Backup-Releaseweg und seine Einschränkungen stehen im jeweiligen Audit.

## Bewusst nicht automatisch geändert

Alte Modelloriginale/Pins, aktive Kalibrierungsrezepte, Haircuts, Kontowährungen,
Kundenzugang und persönliche WIP werden nicht durch einen kosmetischen Patch
neu definiert. Verletzungs-/Wetter-/Müdigkeitswirkungen und Marktvorteile
brauchen passende Daten und zeitlich unabhängige Prüfung, keine neuen Texte.
