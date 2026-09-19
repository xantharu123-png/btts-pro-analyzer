# Kontextanschluss und spielbezogener Daily3-Vergleich

## Auftrag und Status

Der Nutzer verlangt begründete, nicht lediglich offensichtliche Auswahlen.
Ein Tor eines Außenseiters kann sinnvoll sein, wenn die Berechnung dafür
spricht. Weder Teamname noch Wettart noch Quote dürfen eine Prognose ersetzen.
Cricket bleibt ausgenommen. **Die vollständige numerische Kontextintegration
und eine bessere Wettqualität sind mit diesem Reparaturpaket nicht erledigt.**

## Tatsächlicher Ausgangsbefund auf dem VPS

- Revision vor dieser Reparatur: `84292f6db3af30d4840ae1fa9f9ce7be6ccc34e7`.
- Veröffentlichter Fußballbestand: 296 Prognosen, sämtlich
  `probability_integration.applied=false`. Ausfall-/Wetterprüfung war keine
  numerische Wirkung. Molde: sechs/sieben gemeldete Ausfälle ohne Wirkung in p.
- Kontext-Artifakte: 1.100 Tennis-Originalpublikationen und vier Tourzustände;
  keine Fußball-Originalpublikation, kein trainiertes Kontext-Effektartefakt,
  kein D2-Auswertungsbericht oder Kontext-Approval.
- Vorhandene Beobachtungen sind nicht mit unabhängigen Trainingsfällen zu
  verwechseln: Fußball-Ergebnisse zu 320 Events, Spielereinsätze zu 220,
  Ausfallbeobachtungen zu 400; Tennis-Ergebnisbelege zu 112 unterschiedlichen
  Events. Mehrere Empfänge/Revisionen zählen nicht als mehrere Spiele.
- Das API-Tagesbudget stand am späten Abend auf 2.467 verbleibenden Abrufen.
  Der Hintergrundreservewert 2.500 blockierte unter anderem Einsatzhistorie
  und einige Liga-Historien **vor** dem HTTP-Aufruf. Kein Tarifwechsel, kein
  zusätzlicher API-Einkauf und keine Senkung dieser Reserve.

## Reparaturen

### 1. Tatsächliche Fußball-Originalaufnahme

Der kanonische automatische Worker reicht erstmals die bereits vorhandenen
expliziten Aufnahmebudgets an Discovery beziehungsweise Modellrefresh weiter.
Er speichert die wirklich ausgeführte unveränderte Berechnung einschließlich
der gebundenen Eingangsdaten; kein zusätzliches Modell, kein neuer API-Abruf.
Injizierte Scanner, lokale Testzustände und reine Kontext-/Preisrefreshes
erhalten keine Aufnahmefreigabe.

Ein separater atomarer Reservierungsstand begrenzt zusätzliche neue
JSON-Nutzlast: höchstens 4 MiB pro Worker-Sitzung (3 MiB Originale, 1 MiB
Quellbelege), zwei Reservierungen je UTC-Tag, insgesamt 128 MiB. Reservierungen
werden bei Absturz/Fehler nicht zurückerstattet. Das ist **keine Behauptung über
die Gesamtgröße der SQLite-Datei**, deren Seiten/Journal und andere vorhandene
Datensammler getrennt bleiben. Keine Löschung, keine neue Sicherung, keine
Finanzmigration. Speichergrenzen erzeugen nur einen Verwaltungsstatus und
keine künstliche Modellwahrscheinlichkeit.

Diese Aufnahme liefert weder rückwirkend alte Originale noch eine empirische
Freigabe. Ungeklärte native Quellzuordnungen bleiben ausdrücklich partiell.
Der gespeicherte Ausführungsfingerabdruck ist weiterhin kein C1-Replaypaket.

### 2. Keine 24-Stunden-Sperre für gar nicht gesendete Abfragen

Nur `APIBudgetExceeded` aus der Reservierung vor dem Netzwerk setzt den
neuen Aufschubstatus. Der Einsatzhistorienpfad entfernt dann ausschließlich
seine eigenen gleichzeitigen Reservierungen. Nach erneut verfügbarem Budget
können die Spiele wieder abgefragt werden. Leere Antworten, HTTP-Fehler und
unklare Buchungs-/Abschlussfehler behalten die bisherige Wartefrist. Die
globale API-Reserve und das Maximum von einer 20-Spiele-Abfrage bleiben erhalten.

### 3. Vergleich derselben Begegnung

Daily3 v4 vergleicht die bestehende aktive/Form-Variante mit der
Heim-/Auswärtsbasis derselben Begegnung (Saisonvariante), nicht mehr mit einem
ungefilterten Ligadurchschnitt. Eine hohe Favoritenchance allein genügt nicht.
Alle drei Varianten müssen weiterhin mindestens 70 Prozent erreichen.

Der zusätzliche Unterschied muss mindestens zwei Prozentpunkte betragen.
Dies ist eine ausdrücklich benannte **Darstellungs-/Relevanzregel**, kein
gelernter Verletzungseffekt, Konfidenzintervall oder Sicherheitsnachweis.
Es gibt weder eine Markt-Namenssperre noch eine Wahrscheinlichkeitsobergrenze.
Der normale vollständige Prognosekatalog bleibt erhalten; Quoten, Einsätze und
das CHF-150-Ziel sind keine Eingaben dieser Reihenfolge.

Die Varianten sind keine unabhängigen Modelle. Auch die Saisonvariante enthält
jüngere Spiele; korrekt ist deshalb zusätzliche Formgewichtung, nicht eine
Berechnung vollständig ohne jüngste Form. Die kurze Kartenzeile benennt den
Vergleich, behauptet aber keine angewendete Verletzungs-/Wetterwirkung.

## Zusatzabsicherung und fachliche Restarbeiten

### Zusatzschutz vor der Freigabe des Aufnahmepfads

Die unveränderte Transportgrenze von 4 MiB pro expandiertem Original ist kein
Ablehnungsgrund für das bereits berechnete Spielmodell. Übergrößen werden nun
vor Parsing und Speicherung als `original-size-limit` gemeldet; keine neue
Originaldatei oder Datenbankzeile entsteht. Die tatsächliche Modellverteilung
bleibt unverändert. Andere Integritätsfehler werden nicht verschluckt.
Gegenprobe zuerst fehlgeschlagen, danach zusammen mit den Aufnahme-/Speicher-
und Automationstests grün: 202 Tests in 20,81 s. Der abschließende eingefrorene
Stand einschließlich gemeinsamem Gruppenbudget besteht **1.526 Tests in
328,99 s**. Danach keine Quell- oder Teständerung mehr.

Der erste echte Lauf zeigte außerdem, dass eine leere erste Spielgruppe die
Aufnahme späterer Gruppen verhinderte. Das reservierte Kontingent gehört nun
dem gesamten Worker: getrennte Gruppen teilen dasselbe sperrengeschützte
Bytebudget, ohne die persistente Reservierung zurückzuerstatten oder pro
Gruppe neu anzulegen. Bereits gespeicherte Quellbytes werden auch bei späterem
Gruppenfehler belastet. Ein zusätzlicher Laufbericht zeigt die gemeinsamen
tatsächlich gespeicherten Bytes. Leere Gruppen, parallele Veröffentlichungen,
Teilfehler und der echte Automationseintritt sind regressionsgeprüft.

### Fachliche Restarbeiten

1. Aufnahme im echten Worker einschließlich Größenmessung und gebundener
   Quellabdeckung prüfen. Partielle Aufzeichnungen nicht als trainierbar zählen.
2. Aktuelle gemeinsame Fußballverteilung/Original-v2 über den owning
   Trainings-/Replaypfad führen. Ältere Roh-Poisson-Qualifikation darf die neue
   Verteilungsregel nicht still zertifizieren.
3. Spieler-/Ersatz-/Erholungsmerkmale mit echter Abdeckung rekonstruieren;
   historisch unvollständige Listen nicht als gesund oder null Minuten deuten.
4. Geeignete getrennte Trainings-, Abstimmungs- und unbenutzte Testfenster
   aufbauen. Die freigegebenen 200 Testevents, drei Zeitblöcke, Verlust- und
   Mehrfachtestregeln bleiben bestehen. 112 Tennis-Ergebnisereignisse sind
   dafür selbst ohne weitere Ausschlüsse nicht ausreichend.
5. Erst dann passende Effekte trainieren, gegen dieselbe Basis auswerten und
   versions-/populationsgebunden anwenden. Wetter, Tennisbelastung und die
   übrigen Sportarten außer Cricket bleiben gesondert zu qualifizieren.

Softwaretests und ein erfolgreicher Pull schließen diese Punkte nicht ab.

## Prüfstand

- 114 gezielte Auswahl-/UI-/Abruf-/Reservierungstests bestanden.
- Der wirkliche Automationseintritt ist zusätzlich mit kanonischem, lokalem
  und injiziertem Scanner geprüft; 11 Reservierungs-/Integrationstests grün.
- Abschließende betroffene Regression: **1.522 bestanden in 330,47 s**,
  darunter Daily3, Fußballaufnahme, echter Automationseintritt, UI-AppTests,
  Kontexttraining/-Freigabeverträge, Auswahlkonsistenz und bestehende Markt-
  und Refreshregeln. Kein zusätzlicher vollständiger 10k-Gesamtlauf.
- Die Vergleichszeile wurde zusätzlich dagegen geprüft, den kleineren
  Ranglisten-Kontrast fälschlich als tatsächliche Wahrscheinlichkeitsänderung
  zu bezeichnen. Angezeigt wird aktive minus Saisonwahrscheinlichkeit.
- Nach Fast-forward auf main nochmals **202 unmittelbar betroffene Tests in
  13,54 s bestanden**. Keine Quelländerung zwischen Regression und Commit.
- Keine neue Browser-Sichtprüfung: ausschließlich interner Browser versucht;
  dessen Start scheitert an Windows-Sandbox-ACLs. Keinen externen Browser geöffnet.

## Veröffentlichung und echte Betriebsprüfung

- Funktionscommit `39bd0ebfb282e89a44a97d818fbeb397c402748b` auf main/GitHub
  gepusht und auf dem VPS explizit per geprüftem Fast-forward deployed.
- Nur die 15 geprüften Code-/Test-/Übergabedateien übernommen. Bestehende Jobs
  vor dem kurzen App-Neustart nicht abgebrochen. Keine neuen Archive,
  Datenmigration, Bereinigung, Paketinstallation oder Backupaktivierung.
- Interner und öffentlicher Healthcheck: `ok`; App/Caddy aktiv, sechs
  Rechentimer wiederhergestellt und aktiviert. Tagesbackup disabled/inactive.
- Produktionsimport bestätigt `daily3-match-form-comparison-v4`.
  Im zum Prüfzeitpunkt noch sichtbaren Abendbestand: 20 lesbare Prognosen,
  null Daily3-Auswahlen. Nicht als Verbesserung der Wettqualität darstellen.
- Echter Worker von 23:20:58 bis 23:42:16 CEST gelaufen; Exit 1/degraded mit
  16 operativen Datenproblemen, kein erfolgreicher Gesamtdatenlauf. Der neue
  Historienpfad meldet für eine vor dem Netzwerk blockierte Abfrage korrekt
  `budget_deferred` statt einer neuen 24-Stunden-Sperre.
- Trotz 4-MiB-Reservierung noch keine Fußball-Originale geschrieben. Dieser
  reale Test deckte den oben reparierten Mehrgruppenfehler auf. Nicht behaupten,
  dass Originalaufnahme oder numerische Kontextwirkung bereits live belegt sei.
- Frühere Voll-Refreshes benötigten auf diesem VPS bis 27 Minuten CPU-Zeit;
  der hier geprüfte Lauf benötigte rund 21 Minuten. Kein neuer Timeout und kein
  durchgängiger erfolgreicher Datenbestand daraus ableiten.

### Nachtrag ausgeliefert – 20.09.2026, 00:04 CEST

`362a4a69ae328243a91d67c4d1fed2b5ac1958fe` mit gemeinsamem Gruppenbudget und
Größenschutz ist auf main/GitHub und VPS bestätigt. Zusätzlich 210 betroffene
Tests auf main in 21,59 s bestanden. Linux-Smoke am echten VPS: konkurrierende
Dateireservierungen, gemeinsam verwendeter Budgetzustand und Verwerfen einer
über 4 MiB großen Aufnahme ohne Veröffentlichung bestätigt. Nur winzige eigene
temporäre Testdateien verwendet und entfernt; keine Produktionsdaten kopiert
oder verändert, keine zusätzlichen API-Abfragen. App/Caddy aktiv, öffentlicher
Healthcheck `ok`, Tagesbackup weiterhin disabled. Nächster regulärer
Wettfinderlauf um 00:07 CEST geplant, nicht vorzeitig als abgeschlossen zählen.

**Offen:** Neue Fußballoriginale nach diesem Nachtrag im realen Lauf nachweisen;
die vollständige Trainings-/Replayanbindung und empirisch freigegebene
Verletzungs-, Müdigkeits- und Wetterwirkung bleiben unvollständig. Dies ist
kein erfolgreicher Gesamtdatenlauf und kein Nachweis besserer Wettqualität.
