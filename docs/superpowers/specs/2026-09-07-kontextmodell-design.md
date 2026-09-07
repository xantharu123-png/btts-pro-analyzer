# BetBoy – Verletzungen, Belastung und Kontext im Modell

Stand: 7. September 2026

Status: Architektur im Chat ausdrücklich freigegeben. Diese schriftliche
Spezifikation wird zur Prüfung vorgelegt; Implementierungsplan und
Produktivimplementierung dieses Ausbaus sind noch nicht freigegeben beziehungsweise vorhanden.

Ausgangscode: `b3afc478a07fa0d67509e2bef0a9c05766bdb077`.
Auftrag: Alle verbliebenen Arbeiten außer Cricket, mit Vorrang für Verletzungen,
Müdigkeit und Erholung. Kein vollständiger Neubau der Sportmodelle.

## 1. Ergebnis für den Nutzer

Eine Ausfallmeldung oder hohe Belastung soll, soweit die Daten und ein geprüftes
Modell das erlauben, die sportliche Prognose verändern. Es genügt nicht, nur
„Verletzungen geprüft“ neben einer unveränderten Zahl anzuzeigen.

- Fußball: Spielerwirkung, Ersatz, Rotation, Erholung und Wetter.
- Tennis: Sätze, Matchdauer, Erholung, verifizierte Verfügbarkeit, Belag und Hallenbedingungen.
- Basketball: erwartete Besetzung/Einsatzminuten, Ausfälle, Erholung und Reisebelastung.
- Eishockey: Besetzung, Torhüter, Einsatzbelastung und Erholung.
- E-Sport: bestätigte Kaderwechsel, Ersatzspieler und Serienbelastung.
- ATP und WTA erhalten unabhängig aktualisierbare Modellstände.

Die Karte zeigt die verwendete Prognose, eine kurze Erklärung des eingerechneten
Kontexts und wesentliche Datenlücken. Basisprognose und Veränderung sind
nachvollziehbar. Modellwahrscheinlichkeit und Wettpreis bleiben getrennt.

**Nicht versprochen:** Jede Meldung führt zu einem von null verschiedenen Effekt;
jede Sportart besitzt bereits vollständige historische Kontextdaten; bessere
Software beweist einen profitablen Wettvorteil. Diese drei Behauptungen müssen
jeweils durch Daten belegt werden und sind keine Abnahmekriterien, die man mit
erfundenen Zahlen erfüllen darf.

## 2. Bestätigter Ausgangspunkt

| Bereich | Vorhanden | Zu ergänzen |
| --- | --- | --- |
| Fußball | `challenge_15k.py` lädt Ausfälle, Aufstellungen und Wetter; `challenge_engine.py` berechnet gemeinsame Tor-/Zählverteilungen | Eigene aus Daten geschätzte Spieler-/Kontextwirkung; `material_impact` wird bisher vorausgesetzt, nicht aus der Ausfallliste berechnet |
| Tennis | `tennis/workload.py` sammelt beobachtete Belastung; `tennis/predict.py` berechnet Elo-/Aufschlagprognosen | Numerische Belastungs-/Verfügbarkeitsintegration; gegenwärtig ausdrücklich `probability_adjustment_applied=False` |
| Basketball/Eishockey | Historische Ergebnisadapter und `sports_prematch.py` | Kontextadapter und sportartspezifische Wirkungsmodelle; aktuelle Spielerausfälle gehen noch nicht in diese Zahl ein |
| E-Sport | Serienhistorie, Elo und persistierte Prognosen | Zeitkorrekte Kader-/Ersatzspieler-/Belastungsmerkmale |
| ATP/WTA | Gemeinsamer Modellbuild und geschützter letzter gültiger Stand | Getrennte Identitäten, Zustände, Kalibratoren und Frischeinformationen |
| Evidenz | Immutable Prognosen, Preisbeobachtungen und Ergebniszuordnung | Gepaarter Vergleich Basis gegen Kontext auf denselben Events und Stichtagen |

Beim vorangehenden lesenden VPS-Check lieferte die vorhandene WTA-Quelle sowohl
für XLSX als auch CSV HTTP 503; HTTPS scheiterte beim TLS-Handshake. Das ist ein
datierter Befund, keine Behauptung über die künftige Verfügbarkeit. Der Stand ist
vor der Implementierung/Abnahme erneut zu prüfen; TLS-Prüfungen bleiben aktiv.

## 3. Unveränderte Grenzen

1. Keine Quote, Buchmacheridentität, Mindestquote oder Preisfreigabe als Modell-
   oder Rankingmerkmal. Preisänderungen dürfen weder Modellhash noch Prognose ändern.
2. Kein pauschales Wettartenverbot, insbesondere kein Verbot von Teamtor-Unter-
   oder Über-Märkten. Neue Kontextvalidierung sperrt nur die **numerische Nutzung
   des betreffenden neuen Modells**, nicht eine anderweitig berechenbare Basisprognose.
3. Cricket-Code, Konfiguration, Zugangsdaten und bestehendes Verhalten bleiben
   unverändert; gemeinsame Änderungen erhalten dafür explizite Regressionen.
4. Keine neue Echtgeldfunktion, kein automatisches Platzieren von Wetten, keine
   Lockerung der 15K-Konto-, Einsatz-, Ticket- oder Abrechnungsregeln.
5. Alte Prognosen, authentisierte Tickets und Abrechnungen werden nicht umgeschrieben.
6. Keine kostenpflichtige Quelle, neuer Vertrag oder Tarifwechsel ohne gesonderte
   Zustimmung. Vorhandene API-Budgets und Betriebsreserven bleiben verbindlich.
7. Nur der VPS schreibt produktive Daten. Lokale Forschung/Tests verwenden
   isolierte Dateien; Downloads schreiben weiterhin nicht in versionierte Seeds.

## 4. Gemeinsamer Daten- und Modellfluss

`Quellen → beobachtete Kontextrevision → Merkmale zum Stichtag → Sportmodell → Marktverteilung → Tabs → getrennte Preisprüfung`

### 4.1 Beobachtungen und Herkunft

Ein append-only Kontextspeicher unter dem konfigurierten Runtime-Root enthält:

- native Event-, Team- und Spieleridentitäten mit Sport, Wettbewerb und Format;
- Quelle, Quellenkennung und Schema, kanonischen Payloadhash;
- tatsächlichen Import-/Beobachtungszeitpunkt, gegebenenfalls belegte
  Veröffentlichungszeit und den Zeitraum, für den die Meldung gilt;
- ursprüngliche und korrigierte Meldungen als getrennte Revisionen;
- gemeldeten Status, Abdeckung und die Herkunft jedes abgeleiteten Merkmals.

Abrufzeit ist nicht gleich Matchende, Veröffentlichungszeit oder bestätigter
Spielerausfall. Ein heute geholter historischer Datensatz wird nicht als früher
beobachtet zurückdatiert. Ergebnisse, Aufstellungen und Verletzungen mit bloßem
Turnierdatum dürfen keine minutengenaue Erholung oder damalige Verfügbarkeit vortäuschen.

Historisches Training darf gesondert belegte Ereigniszeiten verwenden, muss aber
die rückblickende Herkunft und mögliche spätere Korrekturen ausweisen. Es ist
nicht gleichwertig mit prospektiv eingefrorenen Beobachtungen. Datensätze ohne
belegbare Verfügbarkeit vor der jeweiligen Prognose bestehen keine zeitstrenge
Abnahme. Native Zuordnung hat Vorrang; mehrdeutige Namensmatches bleiben ungenutzt.

### 4.2 Zustände pro Faktor

Es werden getrennte Dimensionen gespeichert, keine einzige vermischte Ampel:

- Daten: `available`, `missing`, `stale`, `conflicting`, `not_applicable`.
- Modellrolle: `not_applied`, `experimental`, `applied`.
- Beobachtungsreferenzen, Abdeckungsumfang, Frischefrist, Modell-/Merkmalsversion.

Eine frisch bestätigte Abwesenheit ist nicht dasselbe wie ein unklarer Einsatz.
Eine leere unvollständige Liste bedeutet nicht „alle gesund“. Eine abgeschlossene
historische Leistung veraltet nicht wie eine aktuelle Aufstellung; Revisionen
und eine unvollständige Historie bleiben trotzdem relevant.

Frischefristen sind je Quellen-/Faktortyp konfiguriert, versioniert und an den
Spielbeginn gebunden. Überschrittene Fristen oder ein verlegtes Event erzwingen
eine neue Kontextbewertung. Fehlende automatische Aktualisierung wird nicht als
unverändert bestätigte Nachricht interpretiert.

### 4.3 Eine Berechnung pro Eingaberevision

Der gemeinsame Rechenschlüssel umfasst Eventidentität, angesetzten Beginn,
Basis-Modellhash, Kontextrevision, Merkmals-/Effektmodellversion und Stichtag.
Wettfinder und RisikoBet konsumieren denselben unveränderlichen Rechenstand.
Ein reiner Tabwechsel oder Preisabruf erzeugt keine zweite Sportberechnung.

Geänderte Meldungen erzeugen eine neue Revision. Erstprognose und frühere
Einflüsse bleiben erhalten. Fällt ein zuvor genutzter Faktor weg, wird aus der
Basis und den jetzt gültigen Merkmalen neu gerechnet, nicht ein alter Abschlag
auf einen bereits angepassten Wert addiert.

## 5. Numerischer Vertrag

### 5.1 Schätzverfahren und Referenz

Der neue Kontextteil wird als regularisierte Erweiterung mit der zeitkorrekt
rekonstruierten Basisprognose als Referenz geschätzt. Eingaben sind ausschließlich
Sportdaten. Parameter, Normalisierung und Interaktionen werden ausschließlich im
Trainingsfenster angepasst; Auswahl/Tuning und spätere Abnahme sind getrennt.

Spielerwirkung bezieht sich auf die Zusammensetzung, die bereits in der
Basishistorie steckt, nicht automatisch auf einen fiktiv immer vollständig
gesunden Kader. Ein seit Wochen abwesender Spieler darf nicht gleichzeitig die
beobachtete Teamleistung verschlechtern und erneut vollständig abgezogen werden.
Die Differenz zwischen erwarteter Besetzung und dieser historischen Referenz
ist als Modellmerkmal samt Referenzfenster nachvollziehbar.

Fehlen Spieler- oder Ersatzdaten, wird kein „Star“-Wert aus Namen, Marktquote
oder frei gewählten Prozenten eingesetzt. Team-/Rollenparameter werden bei
kleinen Stichproben regularisiert; nicht belegte Einzelwirkungen bleiben offen.
Geschätzte Vorhersageeffekte sind keine medizinisch oder kausal bewiesenen Effekte.

### 5.2 Verteilungen statt isolierter Prozentkorrekturen

- Positive Tor-/Zählraten: Kontext auf der Log-Skala der Rate modellieren.
- Aufschlag-/Punktwahrscheinlichkeiten: Kontext auf einer begrenzten
  Wahrscheinlichkeitsparametrisierung, anschließend Simulator ausführen.
- Punktedifferenzen: Kontext in die erwartete Differenz, gegebenenfalls gemeinsam
  geschätzte Streuung; beide Seiten müssen dieselbe Verteilung verwenden.
- Sieger-/Serienstärken: antisymmetrischer Stärkeunterschied; Teilnehmerwechsel
  muss die entsprechende Gegenwahrscheinlichkeit ergeben.

Diese Wahl definiert den mathematischen Raum, keine bereits bekannten
Koeffizienten. Es gibt keinen fest eingebauten „fünf Sätze = minus X Prozent“-Wert.

Zusammenhängende Märkte werden gemeinsam aus der angepassten Verteilung
abgeleitet. Summen, Gegenereignisse und verschachtelte Tor-/Satzlinien müssen
stimmen. Die neue Modellversion darf danach keine unabhängig angepassten alten
Marktkalibratoren anwenden, die diese Kohärenz wieder aufheben. Ihre gemeinsame
Verteilungs-/Parameterkalibrierung wird mitvalidiert; Legacy-Ausgaben behalten
ihre bisherige Version und erhalten nicht nachträglich ein neues Gütesiegel.

Marktfamilien bleiben getrennt: Ein für Tore belegter Effekt wird nicht ohne
Nachweis auf Ecken, Karten oder Halbzeitmärkte übertragen. Ein nur für den
Matchsieg identifizierbares Tennismodell erfindet keine Aufschlagparameter, um
Spiele-/Satzmärkte erzeugen zu können. Für nicht abgedeckte Familien bleibt eine
vorhandene Basisprognose mit ihrem tatsächlichen Status sichtbar.

### 5.3 Wirkungsnachweis pro Event

Gespeichert werden Basisparameter/-wahrscheinlichkeiten, final verwendete
Parameter/-wahrscheinlichkeiten, einbezogene Faktoren, ausgelassene Faktoren,
Modellversion und die tatsächliche Differenz. `applied` kann bei einem geschätzten
Nulleffekt eine Differenz von null haben; das ist von `not_applied` zu unterscheiden.

Erklärungen einzelner Faktoren erfolgen durch Neuberechnung gegen denselben
Referenzstand. Bei Interaktionen werden solche Beiträge nicht als frei addierbare
Ursachen ausgegeben. Der gemeinsame Gesamteffekt ist die maßgebliche Veränderung.

## 6. Sportartspezifische Eingaben

### 6.1 Fußball – Verletzungen zuerst

- Verletzung/Sperre/fraglicher Einsatz mit Status, Gültigkeitszeit und Spieler-ID.
- Frühere Einsätze, Starts, Minuten, Rolle sowie vorhandene Leistungsmerkmale
  relativ zu Gegner und Wettbewerb; keine künftigen Saisongesamtsummen.
- Erwartete Besetzung und Ersatz aus vor dem Stichtag bekannten Kader-/Einsatzdaten;
  bestätigte Aufstellung ersetzt die vorherige unsichere Besetzungsannahme.
- Gesamtbelastung und Ruhe seit vorherigen Spielen, einschließlich nationaler
  und internationaler Spiele, soweit eindeutig bekannt; keine Doppelzählung.
- Wetter am verifizierten Spielort und relevanten Zeitraum; unbekannter Spielort
  oder Wetterzustand bleibt als Abdeckungslücke sichtbar.

Das eigene Modell berechnet die Spielerwirkung. Ein externes freies
`material_impact.verified`-Flag ersetzt weder Statistik noch Modellnachweis.
Fraglicher Einsatz wird nicht pauschal mit 50 % angenommen. Mit belegtem
Teilnahmemodell sind gewichtete Aufstellungsszenarien zulässig; ansonsten werden
die Szenarien separat erklärt und keine erfundene zentrale Mischung veröffentlicht.

### 6.2 Tennis – Belastung und Erholung zuerst

- Tatsächlich bekannte vorherige Sätze, Spiele und Dauer, getrennte Abdeckung
  für jeden Wert; Aufgaben und Walkovers sind keine normalen vollständigen Matches.
- Vorheriger Matchbeginn/-abschluss, angesetzter nächster Beginn und tatsächliche
  Ergebnisbeobachtung werden getrennt gespeichert. Bei unbekanntem Matchende gibt
  es eine belegte Erholungsgrenze, keine erfundene minutengenaue Pause.
- Kurzfristige und kumulierte Belastung; zukünftige angesetzte Spiele zählen
  nicht als bereits absolvierte Leistung.
- Belag/Halle sind bereits Basiseingaben und dürfen nicht nochmals pauschal
  aufgeschlagen werden. Belastungsinteraktionen mit Umgebung werden separat gelernt.
- Verifizierte Verfügbarkeitsmeldungen und Rückkehr nach Pause; eine Aufgabe
  allein beweist weder, welcher Spieler verletzt war, noch eine akute Diagnose.
- Reiseinformation nur bei belastbarer Quelle für den tatsächlichen Wechsel;
  Turnierstandorte allein belegen keinen konkreten Reisezeitpunkt oder Jetlag.

Der Simulator wird bei ausreichend identifizierter Aufschlag-/Returnwirkung neu
ausgeführt. Elo-only-Ausgaben erhalten nur die durch dieses Modell identifizierbaren
Märkte und werden nicht mit erfundenen Aufschlagdaten vervollständigt.

### 6.3 Basketball und Eishockey

Vorherige Einsatzminuten, erwartete Rotation/Besetzung, Ausfallstatus, Erholung
und belegte Ortswechsel bilden den Kern. Ein angesetztes Spiel am Folgetag ist
eine belegte Kalenderinformation, aber kein individuell gemessener Ermüdungswert.
Eishockey berücksichtigt den bestätigten beziehungsweise unsicheren Starttorhüter
gesondert. Reguläre Spielzeit und Verlängerung/Shootout behalten ihre eigenen
Verteilungs- und Settlementverträge; Basketball berücksichtigt Overtime nur dort,
wo der bestehende Marktvertrag sie einschließt.

### 6.4 E-Sport

Zeitkorrekte Kader- und Ersatzspieleridentitäten, Spiel-/Patchversion soweit
vorhanden, best-of-Format und vorherige Serien-/Mapbelastung. Serienmodelle dürfen
keine neue Unabhängigkeitsannahme für Maps unbemerkt einführen. Körperliche
Verletzungen oder Müdigkeit werden ohne belastbare Meldung nicht diagnostiziert;
beobachtete Serienbelastung wird ausdrücklich als sportartspezifisches Merkmal geführt.

## 7. Datenverfügbarkeit und Beschaffung

Priorität haben die bereits verwendeten Quellen und vorhandenen Budgets.
Vor jedem neuen Adapter wird mit echten, begrenzten Antworten geprüft, welche
Felder, native Identitäten, Zeitangaben und historischen Abdeckungen vorhanden sind.
Ein API-Schlüssel oder eine dokumentierte Funktion beweist keine Liga-/Spielabdeckung.

API-Football-Ausfälle und Aufstellungen werden um wirklich abrufbare historische
Spieler-/Einsatzdaten ergänzt. Die derzeitigen Ergebnisadapter für die übrigen
Sportarten ersetzen noch keinen Verletzungs- oder Kaderfeed. Für jeden Adapter
wird ein Abdeckungsbericht gespeichert. Fehlt die erlaubte Quelle, bleibt das
betroffene Arbeitspaket als Datenabhängigkeit offen, nicht „implementiert“.

Für Wettertraining werden damals verfügbare Vorhersagen bevorzugt. Nachträgliches
tatsächliches Wetter/Reanalyse ist ein anderer Datentyp und besteht nicht allein
die prospektive Abnahme. Archivquellen werden vor Nutzung auf Nutzungsbedingungen,
Kosten und passende Prognosehorizonte geprüft; keine stillschweigende Bestellung.

## 8. ATP und WTA unabhängig aktualisieren

- Eigene Tour-Namensräume, Rating-/Aufschlagzustände und Kalibratoren; keine
  gegenseitige Verwendung von Spielernamen, Frische oder Stichprobenzahlen.
- Pro Tour: Modellhash, Bauzeit, Trainingsstichtag und präzise bezeichnete
  Abdeckung. Ein Turnierstart-Proxy heißt weiterhin ausdrücklich so.
- Nur ein vollständig geprüftes Tour-Artefakt wird atomar veröffentlicht. Bei
  Fehler bleibt für diese Tour der letzte gültige Stand mit altem Zeitstempel.
- Das gemeinsame Manifest referenziert beide konkreten Artefakte; ein neuer
  ATP-Stand macht den behaltenen WTA-Stand nicht scheinbar frisch.
- Ohne vertrauenswürdiges Tour-Artefakt bleibt die betreffende Berechnung offen.
  Der andere Tour-Refresh darf erfolgreich veröffentlicht werden, während der
  Gesamtlauf die fehlgeschlagene Tour explizit als Teilergebnis/Betriebsfehler meldet.
- Der alte kombinierte Zustand wird nicht durch mutmaßliches Sortieren von
  Spielernamen zerlegt. Neue Tour-Artefakte werden getrennt aufgebaut; Legacy-
  Leser bleiben bis zur Migration verfügbar und erkennen den alten Status korrekt.
- Jahresbereiche werden aus dem aktuellen UTC-Jahr und dem unveränderten
  historischen Startjahr gebildet; Jahreswechsel und noch nicht vorhandene neue
  Saisondateien besitzen Tests, statt ab 2027 scheinbar erfolgreich zu veralten.

## 9. Empirische Abnahme und Aktivierung

Die Umsetzung umfasst Datenbeschaffung, Merkmalsrekonstruktion, tatsächliches
Training, Auswertung und Anwendung. Ein leeres Gerüst mit `applied=False` ist
keine fertige Verletzungs-/Belastungsintegration.

Für jede Sport-/Wettbewerbs-/Modellfamilie werden Basis und Kontext auf denselben
Events, Stichtagen und Auswahlregeln verglichen. Zeitlich geordnete Trainings-,
Abstimmungs- und unangetastete Testfenster verhindern Zukunftsinformationen.
Skalierung, Spielerwerte, Teilnahmeannahmen und Kalibratoren werden innerhalb
jedes Fensters neu aus dessen Vergangenheit erzeugt.

Der Prüfbericht enthält Datenabdeckung und Herkunft, Event-/Zeitraumzahlen,
Merkmalsanzahl, Verteilungs-Logloss, marktbezogenen Brier-Score und Kalibrierung,
gepaarte Unterschiede mit zeit-/eventgruppierter Unsicherheit sowie getrennte
Ausfall-, hohe-Belastungs- und Datenlücken-Kohorten. Ablationen zeigen den Beitrag
von Verletzungen, Belastung und Wetter einzeln und gemeinsam. Preise/ROI sind
eine zusätzliche Auswertung, weder Trainingsziel noch Aktivierungsargument.

Für die erste Aktivierung gilt eine vor der abschließenden Auswertung
eingefrorene, versionierte Policy:

- Mindestens 200 eindeutige Testevents über mindestens drei aufeinanderfolgende
  Zeitblöcke; viele Märkte eines Events zählen nicht als unabhängige Matches.
- Der primäre gepaarte Brier-Verlust wird zuerst innerhalb eines Events über
  die vorab festgelegten Zielmärkte gemittelt und anschließend über Events.
  Gegen die unveränderte Basis sind mindestens 2 % relative Verbesserung nötig.
- Die Verbesserung muss zusätzlich den bestehenden zeitabhängigen gepaarten
  Verlusttest mit Mehrfachtestkorrektur bestehen (Newey-West/HAC und
  Benjamini-Hochberg, FDR 5 %); alle untersuchten Modellfamilien gehören in die
  Testfamilie, nicht nur die erfolgreichen.
- Der mittlere Verteilungs-Logloss darf gegenüber der Basis nicht steigen;
  die bestehenden marktspezifischen Kalibrierungsprüfungen bleiben erforderlich.
  Eine Gewinnquote oder ein positiver historischer ROI ersetzt diese Prüfung nicht.
- Der numerische Einsatz gilt ausschließlich für die geprüfte Population und
  Merkmalsabdeckung. Nicht repräsentierte Wettbewerbe, seltene Ausfallarten oder
  andere Formate erben keine Freigabe. Jeder Testblock und die genannten
  Kontextkohorten werden separat berichtet, einschließlich negativer Ergebnisse.

Die 200-Event-/2-%-Grenzen und der Verlusttest lehnen sich an die vorhandenen
Modellabnahmeregeln an; sie sind bewusste Aktivierungskriterien, keine behaupteten
Naturkonstanten oder Effektgrößen. Das finale Testfenster wird nicht nachträglich
zum Tuning verwendet. Jede nachträgliche Modell-/Policyauswahl benötigt eine neue
unangetastete Abnahme; nur ein reproduzierbares Ergebnis reicht zur Umstellung.

Bis dahin dürfen experimentelle Vergleichsrechnungen intern laufen. Die bereits
berechenbare Nutzerprognose bleibt sichtbar; es werden keine fehlenden Quoten
oder mangelhaften Vergleichsdaten durch eine scheinbare Bestätigung übergangen.

Für ein späteres Echtgeld-/15K-Release gelten zusätzlich dessen bestehende
Freigabekriterien. Eine neue Prognoseversion erbt nicht die historische Validierung
einer alten Version. Alte authentisierte Tickets bleiben vollständig prüfbar.

## 10. Oberfläche und Betrieb

Die flachen Karten bleiben erhalten. Sofort sichtbar sind Prognose, wesentliche
eingerechnete Faktoren und relevante Datenlücken; Preis separat. Kurze Aussagen
wie „Ausfälle eingerechnet“ erscheinen nur, wenn das belegbar stimmt. Ist nur die
Liste bekannt, lautet die Aussage entsprechend „Ausfälle bekannt; Wirkung offen“.
Technische Modellkennungen, Trainingsdiagnosen und Providerfehler gehören in die
Administrationsansicht beziehungsweise den Bericht, nicht in alle Nutzerkarten.

Hintergrundläufe nutzen die vorhandenen Scheduler und pro Quelle gemeinsame
begrenzte Abrufe/Caches. Verletzungen und Besetzungen werden vor Spielbeginn erneut
geprüft; veröffentlichte Änderungen erzeugen neue Snapshotrevisionen. Updates und
UI-Refreshes dürfen weder doppelte Rechnungen noch API-Abrufstürme verursachen.

Neue Datenbanken und Modellartefakte werden vor Aktivierung in Backup/Restore
aufgenommen. Rollback stellt einen konsistenten Manifest-/Modellstand wieder her,
ohne bereits aufgezeichnete Prognosen oder Echtgeldhistorien zurückzuschreiben.
Git-Checkout bleibt nach regulären Datenläufen sauber. Code wird explizit
committed, gepusht und revisionsgebunden deployed; Timer deployen keinen Code.

## 11. Prüfbare Abnahmekriterien

1. Ein kontrollierter verifizierter Spieler-/Belastungswechsel verändert mit
   einem passend trainierten Modell dessen Parameter und betroffene Märkte.
2. Dieselbe Beobachtung zweimal oder eine reine Quote-/Tabänderung verändert
   weder Sportparameter noch Reihenfolge und löst keine zweite Eventrechnung aus.
3. Dauerhaft abwesende Spieler, Ersatz, fraglicher Einsatz und Rückkehr sind
   getrennte, gegen Doppelabzug geprüfte Fälle.
4. Unbekannter Ausfall ist nicht „gesund“, unbekannte Dauer nicht null Minuten;
   ein vollständig beobachteter Nulleffekt ist nicht „ungeprüft“.
5. Trainings-/Testtrennung, nachträgliche Korrekturen, Veröffentlichungszeiten,
   Turnierdatum, verlegte/abgesagte Spiele und Namenskollisionen sind regressionsgeprüft.
6. Kohärente Verteilungen, Gegenwahrscheinlichkeiten, verschachtelte Linien und
   zulässige Parameterbereiche bestehen numerische Eigenschaftstests.
7. Alte Modellrevisionen/Tickets bleiben unverändert auswertbar; falsche oder
   beschädigte Identitäten werden nicht durch den neuen Kontextpfad akzeptiert.
8. WTA-Fehler verhindert keinen vollständig gültigen ATP-Publish und umgekehrt;
   alte Frischeangaben bleiben erhalten. Erstinstallation, Parallelzugriff,
   atomarer Publish, Jahreswechsel und Wiederherstellung sind geprüft.
9. Alle drei Zustände – intern experimentell, produktiv angewendet, Daten fehlen –
   sind fachlich korrekt dargestellt. Keine neuen Markt-/Quoten-Sichtbarkeitssperren.
10. Cricket bleibt im Vorher-/Nachher-Vergleich unverändert.
11. Volle Regression, empirischer Ergebnisbericht und gerenderte Desktop-/Mobile-
    Prüfung bestehen vor Produktivaktivierung; Push, VPS-Hash und echter Lauf sind getrennte Nachweise.

## 12. Reihenfolge und Fertigmeldung

Die Umsetzung wird in prüfbare Pakete zerlegt: (A) gemeinsame Beobachtungs-/Modell-
verträge plus unabhängiger ATP/WTA-Refresh; (B) Fußball-Spielerwirkung; (C) Tennis-
Belastung; (D) Wetter und verbleibende Fußballkontexte; (E) Basketball/Eishockey;
(F) E-Sport; (G) vergleichende Abnahme, Oberfläche und Release. B und C haben
fachlichen Vorrang; Datenprüfungen anderer Pakete dürfen früh stattfinden.

Jedes Paket endet mit konkret benannten verwendbaren Daten, implementierter
Berechnung, Tests, empirischem Status und verbleibender Abdeckung. Eine externe
Datenhürde verhindert nicht unabhängige Arbeiten, wird aber weder verschwiegen
noch mit einem ungetesteten Koeffizienten überbrückt. „Alles erledigt“ ist erst
zulässig, wenn alle Pakete einschließlich der angegebenen fachlichen Abnahme
erfüllt sind; andernfalls wird genau der unerledigte Teil benannt.

## 13. Bezug und Freigabe

- Bestehendes Produktdesign: `2026-09-01-riskobet-design.md`.
- Ausgangsaudit/Umsetzung: `../../audits/2026-09-05-auswahlqualitaet.md` und
  `../../audits/2026-09-05-umsetzung.md`.
- Release-/Datenbefunde: `../../audits/2026-09-07-release.md`.
- Dokumentierte Ausfallquelle: [API-Football Injuries](https://www.api-football.com/news/post/new-endpoint-injuries).
- Mögliche Archivart, keine Anbindungs-/Kostenfreigabe:
  [Open-Meteo Previous Runs](https://open-meteo.com/en/docs/previous-runs-api).

Die Chatfreigabe bestätigt den beschriebenen Architekturansatz. Diese
schriftliche Fassung wird vor Erstellung des Implementierungsplans zur Prüfung
vorgelegt. Durch das Speichern dieses Dokuments wird kein Modell aktiviert und
keine neue Effektvalidierung behauptet.
