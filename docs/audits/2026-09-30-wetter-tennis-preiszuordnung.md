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

## Fortsetzung 01.10.2026

### Reparierter Code und verbleibende fachliche Grenze

Funktionaler Stand `1ae37d9ac0736bfeaf76e511c9602ab32b1c4d37`,
mit `3da96d4` und `ef8780c` als Vorfahren, auf main/VPS veröffentlicht.
Finaler vollständiger Softwaretest grün; empirische Effektfreigabe bleibt offen.

Der bestehende Tennis-Quotenabruf sammelt jetzt beide tatsächlich gelieferten
H2H-Seiten aus derselben eindeutig gebundenen Antwort. Der normale Rückgabewert,
die HTTP-Anzahl, Modellreihenfolge und Wahrscheinlichkeiten bleiben unverändert.
Preisbelege stehen separat als `tennis_price_observations` im vorhandenen
Wettfinder-JSON, nicht im Modellpool. Höchstens zehn Ereignisse / 20 Seiten /
256 KiB, Originalzeitstempel, maximal 24 Stunden und nur kommende Spiele.
Keine neue Datei, Datenbank oder Quote aus einer Gegenwahrscheinlichkeit.
Ungültige UTF-8-Identitäten dürfen die normale Quote nicht scheitern lassen.

RisikoBet übernimmt diese Belege nur für denselben nativen Anbieter/Spiel-ID,
Spielerreihenfolge, Anpfiff, die tatsächliche gewählte Seite und den gleichen
Sieger-Wettvertrag. Dedizierte eindeutige Beobachtungen haben Vorrang vor alten
Modellzeilen; explizite Konflikte blockieren deren Rückfall. Keine Siegerquote
für Satz-, Gesamt- oder Handicapmärkte. Fehlende Gegenpreise bleiben unbekannt.
Die bestehende 1,20-Untergrenze wird damit auch auf die echte Gegenquote angewandt.

Der Football-Joint-Worker ist nach dem Schließen und Persistieren des regulären
Captures an Scan und Modellrefresh angeschlossen. Er verwendet die tatsächliche
spätere UTC-Entscheidungszeit, nicht einen alten Scanzeitpunkt. Quellen,
nativer Spielvertrag, ORIGINAL-Bindung, Modellpopulation und physische
Modell-/Manifestveröffentlichung bleiben gebunden. Geänderte Wetterbelege werden
nicht an einen früheren Zeitpunkt zurückdatiert.

Ohne passenden bestehenden Fit keine großen ORIGINAL-/Featuredaten und keine
neuen Speicherzeilen. Auch mit Fit nur interner experimenteller Vergleich,
`approval=None`; die öffentliche Grundwahrscheinlichkeit bleibt identisch.
Maximal 32 Ereignisse, 4 MiB / 4.096 Eingangsbelege vor Body-Decoding geprüft,
512 KiB vollständiger Vergleich je Event / 1 MiB reservierter Speicher je Lauf.
Übergroße Eingaben werden ganz abgelehnt, nicht günstig zurechtgekürzt.
Identische revisionsgebundene Vergleiche werden schreibfrei wiederverwendet.
Wiederverwendung und Größen-Vorprüfungen ohne Schreibzugriff verbrauchen kein
fiktives Laufbudget; neue/teilweise Veröffentlichungen bleiben konservativ
reserviert. Die beiden unabhängig gefundenen Fairnessfälle sind getestet.

**Das schließt keine empirische Modelllücke.** Am 01.10. read-only bestätigter
Produktionsmanifest `0f70f44d2ada705a776fee9c081a729e05753a090b93190d053d9e1b1da6d0f1`
enthält nur `tennis:ATP` und `tennis:WTA`, null Kontext-Effekt-Slots. Die vorhandene
Aktivierung verlangt unter anderem 200 unabhängige unangetastete Testspiele in
drei Zeitblöcken, mindestens 2 % relative Brier-Verbesserung mit positivem
zeitabhängigem Test-Unterrand, Mehrfachtestkorrektur, nicht schlechtere Logloss
und bestandene Markt-Kalibrierung. Softwaretests beweisen das nicht.

Die letzte vollständige Merkmalsinventur stammt weiterhin vom 28.09.: vier
vollständige Fußballpakete, keine gemessenen Tennis-Matchminuten oder verwertbaren
akuten Verletzungsmerkmale. Die damaligen WTA-Gesamtzahlen belegen keine 200
unabhängigen Testfälle zusätzlich zu Training und Abstimmung. Keine neue
Inventur, Zusatzabfrage oder erfundenen Gewichte. Kleinster fachlicher Folgeschritt:
ein enges WTA-Erholungsuntergrenzen-Experiment mit vorher eingefrorener zeitlicher
Aufteilung prüfen; bei Fehlbestand vorhandenen planmäßigen Datenzulauf nutzen.
Für Fußball zuerst rechtzeitig quellgebundene Kader-/Ersatzspieler-/Wetterdaten.

### Vollsuite: konkrete Diagnose statt alter Hypothesen

Die neue Diagnose passierte die früher verdächtigen 40–44-/76-%-Bereiche und
fand bei 97 % einen veralteten UI-Testvertrag. Resultat: **11.615 bestanden,
97 Skips, 111 Untertests bestanden, ein Fehler**, 2.761,16 Sekunden.
Er verlangte den vom Nutzer ausdrücklich entfernten öffentlichen Hinweis
`keine gesicherte Mindestchance`. Der zweite isolierte Fehler beobachtete
den früheren Compact-Renderer statt des aktuellen Sports-Editorial-Renderers.
Beide Tests sind eng auf die freigegebene Kundenansicht aktualisiert;
unveränderte interne Fakten, Modellwert, Markt, Schlüssel, genaue Preisbindung,
ARIA-Identität und Spielgruppierung bleiben abgesichert. Keine neuen Skips,
Produktänderungen oder gelockerten Modellvalidierungen daraus.

113 Kunden-/Gruppierungsregressionen und der gesamte letzte Testabschnitt
mit 241 Fällen bestanden. 95 Root-Integrationsprüfungen und abschließend
54 Football-Helper-/Integrationstests bestanden. Zahlen überlappen und werden
nicht addiert. Die frühere Originalursache bei 40–44/76 % bleibt ohne deren
Trace unbewiesen; weder Windows-Pfadlänge noch Berechtigungen als Ursache behauptet.

Zwischenläufe auf `3da96d4` (17 %) und `ef8780c` (7 %) ausdrücklich gestoppt,
nicht bestanden: erst wegen der nachgewiesenen veralteten UI-Tests, dann vor
der engen Fairnesskorrektur. Final eingefrorener Lauf auf `1ae37d9`:
**12.026 gesammelt, 11.929 bestanden, 97 Skips, 111 Untertests bestanden**,
Exit 0, 2.246,03 Sekunden (37:26). Neun Pytest-JUnit-Metadatenwarnungen.
JUnit: 12.137 Fälle inklusive der 111 Untertests, null Fehler / Failures.
Quellcode-/Test-SHA nach dem Lauf weiterhin `1ae37d9`, keine Python-/Testdiffs.
JUnit-SHA256: `088b6e42ac330ffbc61eb3c8918f3e1b5c36143e65991b38cce188597576715b`.

```powershell
.\.codex_test_venv\quality\Scripts\python.exe -m pytest tests -q -x --tb=short -p no:cacheprovider --basetemp=.pytest_tmp/final101c --junitxml=output/playwright/full-frozen-1ae37d9-20261001.xml
```

Eigener Offline-Browser verwendet die tatsächliche Anbieter-Namensreihenfolge
`Zhizhen Zhang`: Gegenquote 1,12 ohne Karte, 1,20 / 2,70 mit Karte und
unverändert 36 %. 1440/390/320 Pixel ohne Überlauf; keine Console-Fehler,
bekannte Streamlit-Iframe-Warnungen. Browserartefakte bleiben unversioniert.

### Produktionsstand vor der Veröffentlichung

Regulärer Tennislauf 01.10. 00:05:12–00:28:52 CEST: Erfolg / Exit 0,
65 Berechnungen verarbeitet, 23 neue Prognosen, Scan/Gesamt OK.
`unresolved_outcome_events`: ATP183397, ATP186254, WTA184266, WTA186216.
WTA183992 natives Ergebnis nicht verfügbar; WTA183831/183844/183854 aufgegeben,
keine erfundenen Ergebnisse. Wettfinder 03:35:06–03:58:51: Erfolg / Exit 0.
Sieben Timer unverändert geplant, App/Caddy aktiv. Datenbankgröße etwa 5 GiB,
18 GiB frei; keine Bereinigung oder Speicheroperation erforderlich.

Read-only-Probe um 07:29 CEST, vor Veröffentlichung: 41 Fußball-/22 Tennis-Modellzeilen, keine dedizierten
Gegenpreis-Belege; 71 kommende RisikoBet-Szenarien, darunter 30 Tennis und null
passende Tennispreis-Overlays. Die Reparatur ergänzt keine alte fehlende Quote.
Erst die nächste ohnehin geplante Anbieterantwort kann echte Gegenpreise liefern.
Nächster regulärer Wettfinder 02.10., 03:35 CEST; kein zusätzlicher Scan gestartet.

### Kontrollierte Veröffentlichung und tatsächliche Grenzen

Um 08:45 CEST `7acc2da` → `1ae37d9` per Git-Fast-forward auf dem VPS.
Remote-URL, exakter GitHub-main-Zielcommit, Abstammung, tracked-clean und
Acht-Dateien-Allowlist kontrolliert. Bestehender Deployment-Lock; alle sechs
Sportwriter inaktiv, >120 Sekunden bis ihren nächsten Terminen. Nur App neu
gestartet, keine Timeränderung, Sicherung, Bereinigung oder Migration.

Vier Python-Module auf dem VPS kompiliert; reiner Offline-Collector bestätigt
die beiden tatsächlich in einer Dummyantwort enthaltenen Preise 1,52 / 2,70.
Aktiver Fußball-Effektbestand weiterhin null. Kein Provideraufruf,
Fit, Datenbankschreiben oder historischer Prognoseumbau. Beide Healthchecks
`ok`; zwei anfänglich erwartete lokale Verbindungsversuche während des
App-Neustarts abgelehnt, danach gesund. App/Caddy aktiv, sieben Timer geplant.

Wettfinder-JSON vor/nach Deployment bytegleich:
`b402263cf4e0557a715151b0c5f7a7f9d81989c0da7820cf527ac690052152a7`.
RisikoBet-JSON bytegleich:
`c999bdfdaa5df6a06405d14c6c00fd56f0066cf6f85b1276b50500bb55298cb7`.
Der neue Code kann die vorher verworfene Gegenquote nicht aus dem vorhandenen
einseitigen Beleg rekonstruieren. Neue echte Preise werden beim nächsten
regulären Abruf gesammelt; deren Produktionsabdeckung ist noch nicht bewiesen.
Numerische Verletzungs-/Müdigkeits-/Wetterwirkung und bessere Wettqualität
bleiben ausdrücklich unvollständig. Technischer Anschluss ist keine Freigabe.

Eigener frischer Produktionsbrowser nach App-Neustart: RisikoBet fertig
gerendert, Navigation tatsächlich ausgewählt; 63 kommende Szenarien / 38 Events.
Sichtbare Karten bei 1440/390/320 Pixeln angesehen, ohne horizontalen Überlauf.
Null Console-Fehler, zehn bekannte Framework-/Iframe-Warnungen. Ein früher
`check()`-Versuch auf dem asynchronen Segmented-Button prüfte den Zustand zu
früh; die ersten schnellen Screenshots zeigten nur den Kopf. Die Prüfung wurde
am sichtbaren Kartentitel und ausgewählten Navigationszustand wiederholt;
die korrigierten kleinen Viewport-Screenshots enthalten die echten Karten.
Keine daraus erfundene Navigation-Reparatur oder Behauptung echter Gegenpreise.
Artefakte `output/playwright/live-counter-*-20261001.png` unversioniert.
