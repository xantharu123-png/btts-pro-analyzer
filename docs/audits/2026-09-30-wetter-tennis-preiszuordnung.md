# Wetterzeitpunkt und Tennis-Preiszuordnung – 30.09.2026

## Umfang und Ausgangsstand

Weiteres ausdrücklich begrenztes 60-Minuten-Fenster ab 18:27:49 CEST.
Ausgangspunkt lokal/GitHub/VPS `0e69ee7`. Änderungen nur an Wetterauswahl,
reiner Preiszuordnung und Regressionen. Keine neue Sicherung, Bereinigung,
Migration, Gebührenbuchung, API-Abfrage oder Sport-/Modellberechnung gestartet.
Die ohnehin eingerichteten Timer bleiben unverändert.

## Reparatur 1: Wettercache

Reproduktion: gleicher Ort, gleiche UTC-Stunde; Spiel um 10:20 wählt korrekt
09:00 mit 11 °C, Spiel um 10:40 müsste 12:00 mit 27 °C wählen. Zuvor wurde
der für 10:20 gewählte Punkt aus dem Stunden-Cache wiederverwendet.

`ChallengeDataProvider.weather` hält jetzt die bereits empfangenen Punkte
an der bestehenden stadt-/land-/stundenbezogenen Cachegrenze im RAM und
wählt je genauem Anpfiff erneut. Originale Empfangszeit, native Spielbindung
und bestehende Vier-Stunden-Grenze bleiben erhalten. Kein neuer Abruf.
Höchstens 64 Punkte / 64 KiB je Antwort; keine persistente Bild-/Wetterdatei.
Unrepräsentierbare Zeitstempel, übergroße Antworten und unvollständige Werte
werden nicht zu vollständigen Wetterbelegen umgedeutet. Rückgaben sind von
Mutation durch Aufrufer getrennt; fehlende Herkunftszeit wird nicht erfunden.

45 Wetter-Regressionsfälle umfassen Minute, Zeitzone, Datum/Stunde/Ort/Land,
Originalzeit, natives Spiel, Vier-Stunden-Grenze, Antwortgröße, extreme Zahlen,
negative Cachefälle, Mutation und unvollständige unterschiedliche Punkte.
Unabhängiger Wetter-/Integritätsreview: 335 Tests plus 53 Untertests bestanden;
eigener erweiterter Agentenlauf: 507 Tests plus 32 Untertests bestanden.
Diese Läufe überlappen und werden nicht als unabhängige Gesamtsumme addiert.

## Reparatur 2: vorhandene Tennis-Siegerquoten korrekt lesen

Der gemeinsame RisikoBet-Preisleser berücksichtigte Tennis-Siegerzeilen nicht.
Ein vorhandener exakt passender Preis unter 1,20 konnte deshalb als unbekannt
behandelt und im RisikoBet-Katalog sichtbar bleiben.

Neu: native Quelle/Ereignis-ID, exakter Anpfiff, ursprüngliche Teilnehmer-
reihenfolge, gewählter Spieler und Sieger-Abrechnungsvertrag müssen passen.
Originale Beobachtungszeit und bestehende Altersgrenzen bleiben erhalten.
Widersprüchliche doppelte Belege liefern keinen bequemen Preis. Satz-, Handicap-
und Totalmärkte bekommen keine Siegerquote. Modelle, Reihenfolge und Belege
werden nicht geändert. Die gemeinsame Funktion akzeptiert auch Generatoren.

35 neue Tests und unabhängiger Gegenreview bestanden. Zusammen mit Wetter,
Providern, Capture und Preis-/RisikoBet-Integration bestand ein 377-Test-Lauf.
Weitere Gegenläufe sind überlappende Evidenz, keine zusätzlich erfundene Summe.

### Noch nicht behoben: der Gegenpreis fehlt in den gespeicherten Daten

Nur-Lese-Produktionsprüfung: elf normale Tennis-Auswahlen, alle Favoriten,
drei gespeicherte Siegerquoten: Sakamoto 1,73, Gea 1,28, Djokovic 1,42.
Die 39 gespeicherten RisikoBet-Siegerkandidaten wählen bei denselben Spielen
Arnaldi, Zhang und Borges. Somit null exakte Auswahl-/Preispaare – auch bei
einem ausdrücklich historischen morgendlichen Replay. Der neue Leser kann
keine verworfenen Gegenpreise wiederherstellen. Kein aktueller Tennis-Preis-
Vollständigkeitsnachweis aus diesen Tests.

Der normale H2H-Abruf empfängt beide Seiten, behält aber nur den Konsens der
angefragten normalen Auswahl. Die übrigen Preise bleiben nicht abrufbar;
`odds_api_client.py` speichert Budgetmetadaten, keine wiederlesbare Rohantwort.

Nächste kleine Integration, ohne zusätzliches HTTP:

1. `market_consensus.py::fetch_tennis_h2h_consensus`: optionaler Sammlungskanal;
   dieselbe eindeutig zugeordnete Antwort für beide echten Seiten auswerten.
   Rückgabevertrag der normalen Auswahlen unverändert lassen.
2. Bestehender Writer in `wettfinder_automation.py`: Preisbelege getrennt als
   `tennis_price_observations` im selben Schnappschuss, nicht als Modellkarten.
   Bestehender expliziter Preisrefresh kompatibel anschließen, nicht starten.
3. `riskobet_prices.py`: exakte native Preisbelege bevorzugen, normale alte
   Zeilen als Rückfall. Nicht blind doppelte Konsensen mit verschiedenen IDs
   zusammenfügen. Maximal zehn Events / 20 Seiten / 256 KiB, keine Historien-
   anhäufung oder künstlich erneuerten Zeitstempel.
4. Tests: identische HTTP-Anzahl, beide tatsächlichen Preise, keine errechnete
   Gegenquote, fehlende zweite Seite, Konflikte, Quelle/ID/Spieler/Zeit/Markt,
   alte Schnappschüsse, Originalzeit, Begrenzungen und unveränderte Modelle.

## Software- und sichtbare Prüfung

Vollsuite auf eingefrorenem Code `707e2f8`: 11.940 gesammelt. Bei etwa 40–44 %
Fehler gemeldet, weitere um 76 %. Beim Stop noch gepufferte Ausgaben bis 90 %
nachgeliefert; bei 90 % wegen des ausdrücklich begrenzten Arbeitsfensters
angehalten; kein abschließender Gesamtsummary und ausdrücklich kein Vollsuite-PASS.
Sofortige Einzelprüfung der benachbarten Gruppen: 479 Tests bestanden;
Updater 111 bestanden / ein Windows-Skip. Unabhängig Update-Hook 351 bestanden.
Diese Läufe überlappen; die ursprünglichen Fehler sind damit nicht widerlegt.
Keine blinde Teständerung oder Skip. Nächster Diagnosebefehl: Vollsuite `-x
--tb=short` mit kurzem neuen Basetemp, konkreten ersten Trace sichern. Denkbare
Windows-Pfadlänge oder Reihenfolgeeffekte sind Hypothesen, keine belegte Ursache.

Eigene lokale Streamlit-/Playwright-Prüfung mit gekennzeichneten Beispieldaten:
1,12 erzeugt keine Vorschlagskarte; 1,20 und 1,52 bleiben bei unverändert 36 %
sichtbar. Bestehender RisikoBet-CSS-Scope verwendet. Bei 1440/390/320 Pixeln
kein horizontaler Überlauf, keine Console-Fehler. Keine echte Sport-/Geldquelle.

Vermutete Navigation-Störung unabhängig untersucht: sechs frische Desktop-/
Mobilaufrufe mit um 1,8 Sekunden verzögerter Identitätsantwort und zehn weitere
Wechsel bei Statusupdates/Rerenders bestanden. Nur ein zu früher Klick vor
vollständig gemounteter Testseite ging verloren. Kein reproduzierter Fehler
der fertigen Produktnavigation; deshalb keine spekulative Navigationsänderung.

## Produktionsnachweis

Code `707e2f802f9d14a849bd1d3ad74fb5e23e722f3f` auf main und VPS. Nach Fetch
exakter Zielcommit, Fast-forward-Abstammung und Vier-Dateien-Allowlist geprüft;
VPS tracked-clean, alle sechs Writer inaktiv, mindestens zwei Minuten Abstand
zum nächsten Termin. Bestehender Deployment-Lock verwendet. Sportwriter
verwenden diesen Lock nicht; deshalb zusätzlicher unmittelbarer Zeitabstand.
Keine Timer gestoppt/geändert. Nur App neu gestartet.

VPS-Smoke mit Dummy-Schlüsseln und vollständig gemocktem HTTP: genau zwei
Mockaufrufe, 10:20 → 11 °C und 10:40 → 27 °C. Reiner RisikoBet-Leser:
70 gespeicherte Kandidaten, zwei kommende, null vorhandene passende Preise.
App/Caddy aktiv, sieben Timer geplant, beide Healthchecks `ok`. Zwei erwartete
lokale Verbindungsversuche während des App-Neustarts scheiterten, danach Erfolg.

Wettfinder SHA-256 unverändert:
`916beed520687a5304ef573fb2b8ac9a4fa624979cdebf0752816ff567bb8fdd`.
RisikoBet SHA-256 unverändert:
`bfba0310d9a1199abbac089f762830f97c97d1574cde9f252de51e3c0b347e18`.

Eigener frischer Produktionsbrowser: zwei kommende Basketball-Szenarien,
keine bereits gestarteten Gea/Tsitsipas/Djokovic/Spirit/Vitality-Einträge,
1440/390/320 ohne Überlauf, null Console-Fehler; bekannte Iframe-Warnungen.
Ein QA-Script wartete zunächst auf eine bei nur zwei Karten nicht vorhandene
„Weitere Szenarien“-Überschrift; an tatsächlich vorhandener Sektion wiederholt
und bestanden. Kein Appfehler aus diesem falschen Testwait abgeleitet.

## Unveränderte und neu bestätigte offene Grenzen

- Die zwei Basketball-Szenarien haben mangels Historie keine berechenbare
  Wahrscheinlichkeit. Redundante technische Datenlückentexte sind weiterhin
  wenig nutzbar; nicht als fertige Top-Tipps oder gelöste Sportmodelle darstellen.
- Daily3-Seitenleiste verwendet den Modellpool ohne Konto-Slots, besetzte
  Events oder Guard-Status. Die eigentliche Daily3-Seite berücksichtigt diese.
  Kein Geld-/Ledgerfehler nachgewiesen. Keine Finanzstore-Konstruktion nur zum
  Rendering hinzufügen: diese könnte Schlüssel/Schema/Dateien erstellen.
  Kurzfristig klar als Modellvorschau kennzeichnen; Konto-Parität benötigt einen
  bewusst schreibfreien, authentisierten Zustandleser.
- Tatsächlicher Tennislauf 30.09. 00:05:24–00:24:27 CEST: Exit 0,
  Scan/Gesamt OK, 33 neue Prognosen. `unresolved_outcome_events` ATP183397,
  ATP186254, WTA186216; `native_unavailable_outcome_events` WTA183992.
  Keine Coverage-Gaps, keine daraus erfundenen Ergebnisdaten. Frühere Nachprüfung
  bereits PAUSED, unverändert belassen.
- Qualifizierte numerische Verletzungs-/Wetter-/Müdigkeitseffekte sowie bessere
  Wettqualität weiterhin nicht belegt. Quellenkorrektur ist keine Effektfreigabe.
  Aktuelles Aktivierungsmanifest publiziert nur ATP/WTA, keine Kontexteffekte.
  Vollständige Merkmalsinventur zuletzt 28.09.: ATP72/WTA289 passende Ergebnisse,
  keine gemessenen Dauern/nutzbaren akuten Verletzungen, vollständige beobachtete
  Dreitages-Satzhistorie ATP0/WTA2. Das sind datierte, nicht heutige Gesamtzahlen.
  Vorhandenen Football-Jointvergleich nach persistiertem regulärem Capture am
  echten späteren Vor-Anpfiff-Stichtag anschließen, ohne Daten nachzudatieren,
  zusätzliche Abrufe, frei erfundene Gewichte oder empirische Aktivierung.

Browserbilder und Hilfsscripte unter `output/playwright/continue60-*` bleiben
unversioniert. Inherited untracked Audit-/Output-Dateien bleiben unberührt.
