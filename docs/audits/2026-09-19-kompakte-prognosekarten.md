# Kompakte Prognosekarten – 19.09.2026

## Geliefert

Funktionscommit: `763c7415c7e5438e7437b6aa135750444e97ed0d`.
Auf main gepusht und auf dem VPS am 19.09.2026 gegen 12:47 CEST bestätigt.

- Wettfinder-Hauptkarten, Zusatzkarten und aktuelle Daily3-Auswahlen verwenden
  kurze Fakten statt mehrerer ständig sichtbarer Analyseabsätze.
- Torprognose, Gegenrisiko, Stichprobenbasis, Ausfallzahlen und Aufstellungsstatus.
  Einzelne Fakten öffnen per Klick, Antippen oder Tastatur ihre Details.
  Kein Aufklappen der gesamten Auswahl erforderlich.
- Spielernamen und Status getrennt für Heim-/Gastteam, soweit gespeichert.
  Neue Daten behalten getrennte Listen für Ausfälle und fragliche Spieler.
  Alte gemischte Listen werden ausdrücklich ohne eindeutige Statuszuordnung
  angezeigt, niemals als bestätigte Ausfallliste ausgegeben.
- Fehlende, veraltete oder unpassend zugeordnete Kaderdaten ergeben keine
  erfundenen Namen, null Ausfälle oder vermeintlich aktuelle Aufstellungen.
- Fehlende Ausfallwirkung, Modell-/Datenalter und sportartspezifische
  Einschränkungen bleiben unmittelbar sichtbar.
- Vollständige Herleitung und Datenstände unter „Berechnung & Daten“.
  Langfassung der heuristischen Preisschwelle unter „Preisberechnung“;
  kurze Einschränkung und konkreter Preisstatus bleiben sichtbar.
- Laufkopf ohne redundanten Modell-/Preisabsatz; „Suche unvollständig“ statt
  des unklaren „Teildaten“. Zählung und Unvollständigkeitsentscheidung unverändert.

## Keine fachliche oder finanzielle Neuberechnung

Wahrscheinlichkeiten, Rangfolge, Preise, Daily3-Auswahlprofil, Budgetregeln,
Speicherhistorien und bereits gespeicherte Echtgeldverträge unverändert.
Namensanreicherung ausschließlich aus derselben vorhandenen Zeile mit passendem
Zeitpunkt, Status und Mannschaftszahlen. Keine zusätzliche Providerabfrage,
Migration oder erneute Speicherung der Namenslisten im Analyse-Envelope.
RisikoBet-eigene Renderer wurden in dieser UI-Aufgabe nicht umgebaut.

## Nachweise

- Betroffene Regression: **713 Tests plus 26 Untertests bestanden**, zunächst
  im Reparaturworktree, danach im integrierten main-Checkout. Kein erneuter
  Gesamtmodell-/Langzeitqualitätstest und kein behauptetes unabhängiges Review.
- Neue Regressionen: Spielerstatus, Altdaten, Zeit-/Identitätsbindung,
  HTML-Escaping, fehlende Namen, sichtbare Einschränkungen, Preisneutralität.
- Lokaler Browser: echte Streamlit-Karten und Daily3 bei 1440 und 320 Pixeln,
  Namensdetails und Enter zum Öffnen/Schließen; kein horizontaler Überlauf.
- Produktionsbrowser: neuer Laufkopf und Faktenfelder bestätigt; Ausfallfeld
  Atletico-MG/Chapecoense geöffnet. Altdaten enthalten 3/7 Ausfälle plus je
  einen fraglichen Spieler und gemischte Namenslisten; diese Unterscheidung
  bleibt korrekt sichtbar. 0 Console-Fehler; 9 bestehende Browser-/Iframe-
  Warnungen nicht als behoben ausgeben.
- Lokal/öffentlich Healthcheck ok, App/Caddy sowie sechs Rechentimer und
  Retention aktiv. Tagesbackup weiterhin disabled/inactive.
- Deployment ließ den bereits laufenden Wettfinder regulär beenden, dann
  exakter Fast-forward und Appneustart. Keine neue Sicherung oder Bereinigung.
  SSH meldete nach COMPLETE einen abschließenden Windows-CR an „exit 0“.
  Der unabhängige anschließende Lesecheck bestätigte SHA, Health und Timer.
  Lokales Hilfsskript gegen diese Transport-Endzeile korrigiert; den bereits
  erfolgreichen Codewechsel nicht erneut ausgeführt.

Lokale Browserbelege liegen unveröffentlicht unter `output/playwright/compact-*`.
Empirische Prognosequalität, vollständige Verletzungs-/Müdigkeitswirkung und
andere bereits bekannte Datenjob-/Kontextaufgaben sind dadurch nicht erledigt.
