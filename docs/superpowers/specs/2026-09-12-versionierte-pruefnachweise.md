# Stufe B: vollständige Prüfung mit wiederverwendbaren Nachweisen

Stand:12.September2026. **Konkreter Architekturentwurf nach A1 STOP;
noch keine Freigabe für diesen neuen Betriebs-/Nachweisvertrag.**

Nutzerbedarf: Als Betreiber möchte ich einen korrekten neuen Stand zuverlässig
installieren können; als Nutzer möchte ich aktuelle Analysen erhalten, ohne
dass wiederholte historische Nachrechnung den Veröffentlichungsweg blockiert.
Ein Betreiber muss außerdem erkennen, ob eine Vorbereitung noch unvollständig
ist, statt einen gesunden HTTP-Endpunkt mit einer vollständigen Prüfung zu verwechseln.

Ausführungsauftrag ist der freigegebene
[Kapazitätsplan](../plans/2026-09-11-pruefarchitektur-kapazitaet.md).
Dieser verlangte bei fehlender Tragfähigkeit von A einen separaten B-Entwurf.
Die Freigabe von Commit/Push/Deployment liegt bereits vor; die unten genannte
Entscheidung betrifft erstmals gespeicherte Prüfberechtigungen, einen isolierten
Prüfbenutzer und einen längeren, explizit begrenzten Vorprüf-Lebenszyklus.

## 1. Ergebnis und Nutzen

Empfohlen wird ein prüfereigener Nachweisbestand außerhalb der laufenden App.
Er bestätigt, welche unveränderten Inhalte mit welchen exakten Implementierungen
bereits vollständig geprüft wurden. Für jeden neuen Stand wird trotzdem der
**gesamte physische und logische Bestand** erfasst und verglichen. Neue oder
betroffene Inhalte und Analysen werden vollständig durch ihre bisherigen
zuständigen Prüfer gerechnet. Ein alter Modellwert wird niemals anstelle einer
neuen Prognose erzeugt. Es ändern sich Prüfhäufigkeit und Ablauf, nicht Quoten,
Wettarten, Auswahlreihenfolge, Features, Modellmathematik oder gespeicherte Historie.

Die kleine A-Optimierung wird nicht gebaut. Die unabhängige Zeitrechnung und
12neue Messpaare belegen keinen ausreichenden Weg zum240Sekunden-Reserveziel.
Die reale31-Analyse-Datenbank umfasst inzwischen99776Belege/268824576Bytes.
Das ist eine neue Metadatenbeobachtung, kein bestandener D4-Lauf.
Details: [A1-Ergebnis](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-12-stage-a-result.md).

## 2. Ziele und klare Nicht-Ziele

### Verpflichtend

- Keine falsche Annahme unveränderter oder vollständiger Daten; keine erfolgreiche
  Freigabe bei fehlendem, gefälschtem, veraltetem oder nur teilweisem Nachweis.
- Vollständige neue Rechenarbeit für neue bzw. von Änderungen betroffene Analysen;
  Gleichheit der fachlichen Resultate mit den bisherigen zuständigen Prüfern.
- Explizites Modell der Erstprüfung, Codewechsel, Wiederanlauf, Backup und Restore.
- Wiederkehrender abschließender Deploymentcheck höchstens240CPU- und
 240Wandsekunden in drei getrennten nativen Läufen je Pflichtprofil, mit
  vorbereitetem vollständig abgeschlossenem passendem Nachweis.
- Jeder Teilaufwand und der **Gesamtaufwand** der Vorbereitung werden gemessen
  und begrenzt. Kein Umbenennen mehrerer300Sekunden-Läufe in einen alten Volltest.

### Nicht enthalten

Keine Datenlöschung, Archivierung, nachträgliche Neusignierung alter Daten,
Erhöhung bestehender Eingabe-/Historien-/RAM-Grenzen, neue Sportmodelle,
Cricket oder Änderungen am fehlgeschlagenen separaten Tennis-Tagesjob.
Keine empirische Freigabe von Verletzungs-/Müdigkeitseffekten durch ein technisches
Prüfzertifikat. Kein lokaler Automat, keine Änderungen an den sieben Sporttimern.
Ein größeres Speichermodell ist bei unzureichender Datenkapazität eine weitere
ausdrückliche Entscheidung, nicht eine verdeckte Nebenwirkung dieses Entwurfs.

## 3. Wiederverwendung: konkrete Identität und Vollständigkeit

Ein fertiggestellter Nachweis bindet mindestens:

- Vertrags-/Formatschema, Installationsidentität, fortlaufende Generation und
  Vorgängernachweis; exakte SHA256der vollständig versiegelten Eingabedatei.
- Vollständiges logisches Inventar **aller** zugelassenen Tabellen und Spalten:
  SQL-Speichertyp, unveränderte rohe TEXT/BLOB-Werte, Zahlen ohne stilles Kürzen,
  NULL, Schlüssel, Reihenfolge wo semantisch relevant, Zeilen-/Byteanzahlen.
  Hashfelder in der Appdatenbank werden nie als eigenständiger Beweis übernommen.
- Schema, Index-/Constraintidentitäten, vollständige Artefakt-/Content-/Belegmengen,
  Manifeste/aktiver Zeiger, Snapshots und Rollbacks; auch unreferenzierte, zukünftige
  und andere Touren betreffende Datensätze. Bestandsvergleich umfasst Löschungen.
- Vollständige Prüfaufgabenmenge mit Zuständigkeit, Eingabe-/Abhängigkeitswurzeln,
  abgeschlossenem Ergebnis und **unveränderten fachlichen Einschränkungen**.
- Exakte Implementierungs-/Laufzeitidentität sowie tatsächlicher Gesamtverbrauch.

Jeder Lauf behält das bisherige read-only/sealed-file-Eingabeverfahren sowie
physische SQLite-, Schema- und Referenzkontrollen. Zusätzlich scannt er alle
aktuellen Zeilen und erzeugt aus explizit typisierten, längenbegrenzten Werten
ein deterministisches Inventar. Seine vollständige Schlüsselmenge wird mit dem
authentisierten früheren Inventar verglichen. Mehrdeutige Kodierungen,
Schlüsselduplikate und unbekannte Schemata scheitern wie bisher.

Nur bei exakter Identität einer gespeicherten **Prüfeinheit und aller ihrer
Abhängigkeiten** entfällt deren erneute semantische Arbeit. Physische Inventur,
Abschluss-/Abhängigkeitsprüfung und die Datei-/Lebensdauergrenzen entfallen nie.
Alte `_validation_stamp`-/Cache-Besitzflags werden nicht aus Dateien gesetzt:
eine eigene Nachweis-Inventarschnittstelle besitzt den neuen Vertrag, die
bestehende kalte Schnittstelle bleibt Korrektheitsreferenz.

Geschützte ungeöffnete D2-Finaldaten bleiben opaque. Ihre Rohbyteidentität darf
gebunden werden, ihr Inhalt darf dadurch weder dekodiert noch als bekannte
Quelle oder empirisch bestätigter Wert verwendet werden.

## 4. Abhängigkeiten und Entwertung

Eine reine Liste der bisher verwendeten Beleg-IDs reicht nicht. Insbesondere
muss auch die **Vollständigkeit einer Auswahl** gebunden sein:

| Prüfeinheit | Zu bindende Abhängigkeiten / Entwertung |
| --- | --- |
| Physische/Quellbelege | Alle äußeren Spalten, zugehörige Contentbytes, zuständiges Quellschema und Decodervertrag; neue/geänderte Belege vollständig prüfen |
| Artefakt/Tourzustand | Gesamte gespeicherte Hülle, Erstellungszeit, alle typisierten/transitiven Referenzen und zuständiger Validator |
| Tennis-Original | Originalhülle, tatsächlicher Zustand vor Entscheidung, exakte Modellversion sowie vollständiges natives Ereignis-/Zeitpunkt-Auswahlergebnis einschließlich Gleichständen und leerem Ergebnis |
| Tennis-Snapshot | Original, vollständige geordnete kausale Tourhistorie zum Zeitpunkt, Feature-/Transportversion, Effekte/Freigaben/Preprocessing und sämtliche geprüften Werte |
| Sonstige Snapshots/D2 | Exakter bisheriger Zuständigkeitsvertrag und gesamte Eingabeclosure; ohne vollständig beschreibbare Closure keine Wiederverwendung |
| Manifest/aktiver Stand/Rollback | Vollständige Kette und aktuelle Zustände; diese globale Abschlussprüfung bleibt stets frisch |

Für zeitliche Auswahlen werden vollständige geordnete Gruppen-/Präfixwurzeln
mit Selektorversion, Tour und kanonischem Zeitpunkt neu aus dem aktuellen
Inventar ermittelt. Ein nachträglich eingefügter gültiger Beleg mit früherem
Beobachtungszeitpunkt verändert damit auch alte betroffene Analysen. Eine neue
gleichzeitige native Meldung kann ein vorher eindeutiges Original ungültig
machen. Keine Annahme, dass neue Daten immer einen späteren Zeitstempel haben.
ATP/WTA, Quellen, Statusrevisionen und Leermengen bleiben getrennt.

Für V1 gilt bewusst konservativ: Änderungen/Löschungen bestehender historischer
Zeilen beenden den schnellen append-only-Fortschreibepfad und verlangen einen
neuen vollständigen Prüfauftrag. Auch dann kann nur der bisherige zuständige
Prüfer entscheiden, ob der neue Bestand gültig ist. Kein automatisches Reparieren
oder Neuschreiben. Neue referenzierte/unreferenzierte Zeilen werden unabhängig
von ihrer eventuellen Wiederverwendung vollständig inventarisiert und geprüft.

## 5. Implementierungsversionen ohne Kompatibilitätstricks

V1 bindet einen konservativ großen, ausdrücklich versionierten Ausführungsumfang:
gesamte ausgelieferte Python-Produktquelle einschließlich Validatoren/Selektoren,
Modelle/Features/Transport/Verträge, Startargumente und erlaubte Konfiguration,
Interpreter/SQLite sowie eine **vorab deklarierte vollständige Abhängigkeits-/
Ressourcenclosure** mit ihren root-versiegelten Laufzeitbytes. Diese Closure
wird vor der ersten Wiederverwendungsentscheidung vollständig gehasht, auch
wenn die betreffenden Funktionen in diesem Lauf nicht aufgerufen werden.
Insbesondere Lazy-Imports, native Bibliotheken, Paketdaten, Modellressourcen,
Import-Suchpfade und transitive Abhängigkeiten dürfen nicht fehlen. Aus dem
gerade übersprungenen Aufruf kann keine vollständige Importliste abgeleitet
werden. Eine aufgezeichnete geladene-Modulliste ist nur ein zusätzlicher
Vollständigkeitsgegencheck; unbekannte Imports/Ressourcen beenden Wiederverwendung.
Ein Lockfile oder Git-SHA allein reicht nicht.
Dokumentation/Testausgaben sind keine Laufzeitabhängigkeiten.

Ein anderer Ausführungsumfang entwertet die bisherigen abgeschlossenen
semantischen Prüfbelege. Zunächst vollständiger Neuaufbau; späteres feineres
Versions-Mapping wäre ein eigener geprüfter Vertrag. Keine Hash-Whitelist,
Formatnormalisierung oder Umdeutung historischer `origin.code_hashes`.
Die bestehende explizite LF/CRLF-Replayunterstützung wird nicht erweitert.
Ein Modell-/Featureupdate wird durch B nicht automatisch als unterstützte
historische Rezeptversion behandelt.

## 6. Besitzer, Veröffentlichung und Rollbackgrenze

Vorgeschlagene neue, ausschließlich serverseitige Komponenten:

- Ein eigener unprivilegierter Systembenutzer `betboy-verify`, ohne Login,
  Netzzugriff, App-Secrets oder Schreibrecht an App/Live-DB/Schlüsseln.
- Root-versiegelte Quell-/Laufzeit- und Eingabesnapshots. Keine Importe aus der
  veränderbaren Live-App oder einem durch den Appbenutzer änderbaren venv.
- Ein kleiner root-eigener Koordinator/Publisher ohne Produktimporte. Er startet
  nur den exakt gepinnten Prüfer unter obigem Benutzer, nimmt Ergebnisse über
  eigene Prozess-/Dateideskriptoren entgegen, kontrolliert Exit, Ressourcen,
  vollständige Aufgabenabdeckung und Identitäten. Kein vom Appbenutzer
  abgelegtes `success.json` wird als fertiges Ergebnis übernommen.
- Neuer proof-only256Bit-Schlüssel, ausschließlich root lesbar; **keine**
  Wiederverwendung oder Offenlegung des vorhandenen Kontointegritätsschlüssels.
- Root-eigener Prüfzustand, vorgeschlagen `/var/lib/betboy-context-proof/`.
  App und Prüfarbeitsprozess können weder Nachweise noch den aktuellen
  Generationszeiger ändern. Prüfer erhält nur explizite read-only Ansichten.

Veröffentlichung: fester Auftrag bindet Eingabehash/Code/Parentgeneration;
Teilresultate sind lediglich `pending`. Erst komplette Aufgabenabdeckung,
erneute Identitäts-/Hashkontrolle, vollständiger Report und eingehaltene Budgets
erlauben HMAC-authentisierte Veröffentlichung. Temporäre Dateien, fsync und
atomarer Generationswechsel; compare-and-swap gegen den ursprünglichen Parent.
Parallele/veraltete Publisher dürfen keinen aktuelleren Zustand überschreiben.
Absturz darf nur alten vollständigen oder neuen vollständigen Stand hinterlassen.

Ein abgeschnittener oder alter Datenbankstand wird gegen die **aktuell getrennt
gespeicherte** Generation geprüft und nicht durch eine ältere gültige Signatur
freigegeben. Ein App-/SQL-Zugriff kann diese Autorität nicht zurückdrehen.
Das ist **kein** Schutzversprechen gegen root-/Kernel-Kompromittierung oder das
Zurücksetzen der gesamten VM samt Schlüssel und Generationsstand. Ohne externen
unabhängigen Anker lässt sich ein solcher Gesamtrollback hier nicht beweisen.
Ein solcher externer Dienst ist nicht Teil von B. Dokumentierter Gesamt-Restore
setzt eine neue Installationsepoche und vollständige Neuprüfung voraus.

## 7. Neuer Ablauf und ausdrücklich neue Gesamtbudgets

`Live-Bestand → versiegelte Kopie → Inventar/Abhängigkeitsvergleich → vollständig
fehlende Prüfaufgaben → atomarer Nachweis → frischer Abschlusscheck → Deployment`

Die Vorbereitung läuft bedarfsgesteuert vor dem Umschalten, nicht als neuer
Sporttimer und nicht als dauerhaft laufender Dienst. Die App läuft dabei weiter.
Ändert sich der Datenstand, bleibt der vorbereitete Nachweis an seine alte Kopie
gebunden. Ein neuer vollständiger Inventarvergleich entscheidet über den Zuwachs.
Während des abschließenden bisherigen kontrollierten Deploymentfensters wird
der tatsächlich umzuschaltende Bestand erneut versiegelt/geprüft. Ist der
Nachweis veraltet oder der Zuwachs zu groß, **kein Umschalten**: Vorbereitung
fortsetzen und später erneut versuchen, ohne Endlosschleife im Updatefenster.

### Zur Entscheidung vorgeschlagene Betriebsgrenzen

| Phase | Vertrag |
| --- | --- |
| Kalte Referenz-CLI | Unverändert; bestehende300Sekunden-/RAM-/Eingabegrenzen. Kein stiller Moduswechsel |
| Eine isolierte Vorprüfportion | Weiterhin CPU300 hart, AS2GiB, RSS<1GiB, kontrollierte Prozessgruppe, Ausgabe≤1MiB; Ziel≤240CPU/Wandsekunden |
| Gesamter Vorprüfauftrag je exakt gebundener Eingabe/Version | **Neu vorgeschlagen:** maximal1800CPU-Sekunden und3600Sekunden Gesamtzeit, über alle Portionen/Neustarts zusammen; noch nicht gemessen oder genehmigt |
| Abschließende Prüfung inklusive Zuwachs | ≤240CPU und240Wandsekunden, nachweislich vollständiger Report; keine versteckte historische Nachrechnung außerhalb der Kostenbilanz |
| Daten-/Arbeitsgrenzen | Eingabe≤1GiB, vollständige kanonische Historie≤256MiB, vorhandener In-run-Cache64MiB/32Plätze unverändert |
| Neuer persistenter Prüfindex | Vorschlag≤256MiB pro Generation; höchstens zwei Abschlussgenerationen plus ein begrenzter Arbeitsauftrag, keine unbegrenzten Zwischenstände |

1800/3600 sind eine **neue lifecycle-weite Grenze**, keine Erhöhung des alten
Einzelprüferlimits und keine Behauptung, das alte Gesamtbudget werde eingehalten.
CPU aller Nachkommen wird auf Auftragsniveau erfasst; fehlende Messbarkeit
ist ein Stoppgrund. Vor Start wird Restbudget reserviert; Crash/unklarer Exit
darf keinen Verbrauch vergessen oder Wiederholungsbudget zurücksetzen.
Root-journalisierter Verbrauch und Teilnachweise bleiben an Eingabe/Version
gebunden. Boot-/Uhrsprung und abgelaufene Deadline werden konservativ abgebrochen.
Ein fehlgeschlagener Auftrag verlängert sich nicht automatisch durch Neustart.

Erstaufbau und jeder relevante Codewechsel benötigen alle Prüfeinheiten. Das
kann mehr als300CPU-Sekunden insgesamt benötigen und wird genau so angezeigt.
Keine Veröffentlichung eines Teilauftrags. Wenn eine einzelne unveränderte
zuständige Modell-/Featureprüfung oder die Eingabe ihre Grenze überschreitet,
kann B sie nicht durch ein positives Zwischenzertifikat retten.

Ein binärer Prüfinventarindex speichert Identitäten/Prüfresultate, keine zweite
Modellhistorie und keine ausgegebenen Wettprognosen. Temporärer/plattenbasierter
Arbeitsbedarf gehört zu einer vorab inventarisierten Platzreserve; auch neue
Indexbudgets dürfen nicht als freier zusätzlicher RAM-Cache verwendet werden.
Retentionsregeln betreffen ausschließlich neue Prüftemporärdaten, nicht historische
Appdaten oder vorhandene Backups; Löschung erfolgt nur nach klarer Zuständigkeit
und erfolgreicher Veröffentlichung des Nachfolgers, niemals für einen Pass.

## 8. Sieben Tage: messbarer Testbereich, keine erfundene Garantie

Echte Beobachtung umfasst bisher nur zwei angebrochene Tage, ausschließlich ATP
bei Originalen.51.220Belege/17Originale/9Zeitpunkte am11.September sind keine
vollständige Tagesrate. WTA-Wiederanlauf/Burst kann zusätzliche Last bringen.

Vorläufiger, bewusst größerer **Planungsprobe**-Umfang aus dieser Beobachtung:
pro zusätzlichem Tag70.000Belege,24neueOriginale/Snapshots und14neueZeitpunkte;
nach7Schritten589.776Belege,199Originale/Snapshots und114Zeitpunkte. Varianten:
ATP-lastig ohne entlastende Tourteilung, gemischte ATP/WTA sowie schiefe Bursts.
Das ersetzt nicht die noch fehlende repräsentative Wachstumsreihe und ist kein
bereits zugesagter unterstützter Produktionsbereich.60/120unterschiedliche
Verbraucher bleiben separate Stresstests, nicht automatisch verpflichtende Pässe.

Die unabhängige [Größenrechnung](../../../.superpowers/sdd/2026-09-10-context-capacity-recovery/task-13-growth-sizing.md)
meldet schon unter konstanten mittleren Payloadgrößen ungefähr1.153GB
Dateiumfang und unter einem gleichbleibenden ATP-Anteil ungefähr345MB
kanonische Historie. Beides liegt über den aktuellen1GiB-/256MiB-Grenzen.
Das sind **bedingte Szenarien, keine gemessenen Zukunftsgrößen oder exakten
Untergrenzen**: freie Seiten, Datenmix, Tourzuordnung und tatsächlich wachsende
Referenzlisten fehlen in dieser Näherung. Sie machen die Speicherprüfung zu
einem vorgeschalteten P0-Entscheidungspunkt, nicht zu einer späteren Optimierung.
Das Profil darf nicht heimlich verkleinert werden, nur damit eine Abnahme gelingt.

**Vor jeder B-Implementierung zuerst Dimensionierung:** Die aktuelle Datei
enthält bereits66,37MB Snapshot-Payloads. Neue Snapshots referenzieren jeweils
eine wachsende vollständige Historie. Deshalb müssen reale kanonische Historiemaße
und gespeicherte Snapshot-/Indexbytes bei jedem geplanten Wachstumsschritt
bestimmt werden. Die Zahl der Belege allein reicht nicht; keine lineare
Dateigrößenhochrechnung als Nachweis. Ein generatorgestützter Größencheck darf
abbrechen, bevor Eingabe1GiB/Historie256MiB/Plattenbudget überschritten werden.

Erreicht die definierte Probe vorher eine dieser Grenzen, ist eine unveränderte
Sieben-Tage-Garantie nicht möglich. Dann benötigt es einen separaten Entwurf für
z.B. verlustfreie, versionierte Speicherung wiederholter Referenzmengen **neuer**
Snapshots; keine alten Umschreibungen/Archivierung/Grenzerhöhungen durch B.
Dabei sind zwei Grenzen getrennt zu behandeln: Kompakte Referenzspeicherung
kann die Dateigröße verringern, **nicht** die256MiB-Zulassungsgrenze der weiterhin
vollständigen kanonischen Historie. Für deren Überschreitung wäre ein eigener
belegbar äquivalenter Eingabe-/Verarbeitungsvertrag erforderlich; Kompression
ist dafür keine Freigabe und Datenpruning keine erlaubte Lösung.
Diese Speicher-/Vertragsänderung ist noch nicht ausgearbeitet/freigegeben. Ein schneller
Check für31Analysen darf diese offene Betriebskapazität nicht verdecken.

## 9. Tests und Abnahme

1. Kalte vs. wiederverwendende Prüfung auf denselben kleinen/mittleren/großen
   zulässigen Eingaben: gleiche fachliche Ergebnisse, kanonische Werte und
   Einschränkungen. Laufzeit-/Nachweisfelder separat; kein `transport_only`→
   `structural`, kein `empirical_approval_verified=True` durch Wiederverwendung.
2. Vollständige Bestandsdiffs: Zusatz/Löschung/Mutation einer beliebigen Zeile,
   gleicher Count/Max-ID, vertauschte Typen, gleiche sichtbare Zahlen nach
   Kürzung, unbekannte Tabelle, verwaiste/andereTour/zukünftige/unreferenzierte
   Belege, Contentaustausch und absichtlich kollidierende interne Schlüssel.
3. Kausale Vollständigkeit: spätere Einfügung mit altem Zeitpunkt, Gleichstand,
   leere→nichtleere Auswahl, andere Tour, neue native Statusrevision; wirklich
   betroffene Originale/Features/Transporte erneut ausführen. Prognosefunktionen
   für neue Ereignisse niemals aus gespeicherten Prüfresultaten bedienen.
4. Versionsänderung: jede relevante Quell-/Prüf-/Modell-/Abhängigkeitsdatei;
   falsches venv, ungebundener Import, geändert erlaubte Konfiguration;
   kein stilles Weitersiegeln bereits gespeicherter Historie. Insbesondere eine
   lazy importierte Bibliothek verändern und sämtliche Aufrufe, die sie laden
   würden, als Reusekandidaten planen: der vorgezogene Closurevergleich muss
   die Änderung trotzdem erkennen. Entsprechende Fälle für native Bibliothek,
   Paketressource und Import-Suchpfad; unbekannte Abhängigkeit ist kein Cachehit.
5. Zuständigkeit: gefälschte Appflags/Arbeitsdateien, falsche Signatur/Generation,
   alte gültige Signatur plus DB-Rollback, fremde Installation, fehlender Kopf,
   zwei Publisher, Quelle/FD/Dateiaustausch, Crash an jedem Publikationsschritt.
6. Teilauftrag/Neustart: keine halbe Freigabe, vollständige Aufgabenabdeckung,
   unverlierbare Verbrauchsbilanz, Timeout/OOM/abgeschnittener Output, ausgeschöpftes
   Restbudget, kumulative CPU statt nur schnellster Portion. Keine neuen Rootimports.
7. Bestehende reale Transaction-/Callback-/Factory-/Schema-/Dateitauschregressionen
   bleiben für die unveränderten Interfaces grün; keine aus Cachedateien
   rekonstruierte transaktionsgebundene Objektberechtigung.
8. Backup/Restore der dann real vorhandenen Datenbanken und vorhandenen
   Kontointegrität; neue Proofdaten/Schlüssel separat geschützt sichern.
   Alter/fremder/fehlender Proofstand erzwingt Neuprüfung, keinen Integritätsreset.
9. Größen-/Budgettests vor nativen Lasttests, danach drei getrennte Läufe je
   aktuellem und tatsächlich vereinbartem Wachstumsprofil. Alle Einzelwerte,
   Quelle/Daten/Runtime-SHAs, Input-Unverändertheit, Reports und Vorprüfgesamtkosten
   festhalten. Kalter Erstaufbau/Codewechsel/Restore gehören zur Abnahme.

Ein vollständiger kalter Lauf auf einem großen Bestand, der anCPU300 scheitert,
bleibt gescheitert. Äquivalenzbelege auf solchen Beständen müssen zusätzlich
alle unveränderten zuständigen Prüfaufrufe anhand begrenzter Referenzportionen
abdecken; sie werden nicht als ein bestandener alter monolithischer Lauf etikettiert.
Die vollständige native kalte Referenz wird dort verglichen, wo sie innerhalb
ihrer unveränderten Grenze tatsächlich abschließt.

## 10. Geplante Codegrenzen und Einführungsweg

Neue klar getrennte Module für Inventar-/Abhängigkeitsidentität, Nachweisformat,
Planer/Prüfportionen und read-only Wiederverwendungs-CLI. Exakte Aufgabenbriefe
vor jedem Patch, ein Implementierer pro Bereich plus unabhängiges Review.
Bestehende `context_runtime.py`/Inventar-/Tennis-Orchestrierung können eng
abgegrenzte neue Schnittstellen benötigen; keine Nebenkorrekturen an Mathematik,
Quelladaptern, Trainern oder Featurewerten. Die bisherigen kalten Owners dürfen
nicht stillschweigend umdefiniert werden.

Erst separat neu geprüfte Deployment-/Bootstrapintegration darf den neuen
Nachweismodus benutzen. Die bisherigen eingefrorenen Installer-/Updaterpins
gelten weiterhin, bis exakt diese neue Version freigegeben und geprüft ist.
Der bisherige Reparaturinstaller ruft den zu langsamen Vollprüfer auf; B kann
deshalb **nicht** einfach über diesen unverändert erfolgreich eingeführt werden.
Ein versionierter Bootstrap muss frisches Backup/Restore, Altzustand, exakte
neue Code-/Proofpins und rollbackfähigen einmaligen Updateraustausch prüfen.
Kein temporäres Abschalten des Kontextchecks und kein Installer-Successmarker
ohne vollständigen neuen Nachweis. Appdeployment bleibt ein eigener Schritt.

Nach positivem Größencheck: lokale Schnittstellen/Differenztests → unabhängiges
Review → isolierte Linux-Abnahme → finale Vollsuite auf exakten Produktbytes →
frisches Backup/Restore und neuer Bootstraptest → normaler main-Push →
kontrollierter Updateraustausch → normales Deployment desselben Commits →
Revisionen/Services/Timer/interner und öffentlicher Healthcheck.

## 11. Entscheidung, Risiken und aktuelle Liefergrenze

Zur Entscheidung steht der neue B-Vertrag: abgeschlossene Prüfungen dürfen nur
bei vollständiger Daten-/Abhängigkeits-/Versionsidentität wiederverwendet werden;
eigener isolierter Prüfbenutzer, root-geschützter Nachweisbestand/Schlüssel sowie
maximal1800CPU-/3600Gesamtsekunden für die dokumentierte Vorbereitung, bei
unverändert begrenztem abschließendem Deploymentcheck. Das ist keine zusätzliche
Commit-/Push-Freigabe und keine Freigabe einer Speichermigration.

Vor tatsächlichem B-Code bleiben bindend: unabhängiges Architekturreview,
Größenprobe für den realen7Tage-Bereich und ausdrückliche Entscheidung zu diesem
neuen Vertrag. Scheitert die Größenprobe, zunächst die Speicherfrage lösen.
Es gibt noch keine B-Implementierung, neue Serveridentität, Schlüssel oder
Dienstinstallation. Der aktuelle technische Kapazitätsfehler ist nicht behoben.

Priorisierung: P0 sind sämtliche Vollständigkeits-/Invalidierungs-, Budget-,
Größen-, Restore- und Releasekriterien. P1 ist eine knappe ausschließlich interne
Fortschrittsanzeige mit Restaufgaben/Verbrauch; kein neuer Technikblock für Nutzer.
P2 sind feineres geprüfteres Versions-Reuse und zusätzliche Automatisierung,
nicht ein Ausweichen vor der vorgeschalteten Speicherentscheidung.
Früher Erfolgsindikator: drei bestandene native Pflichtläufe samt Kosten der
Vorbereitung; nach Einführung: sieben tatsächliche Betriebstage innerhalb des
**vorher tatsächlich abgenommenen** Bereichs ohne verlorenen Nachweis oder
unvollständiges Umschalten. Diese Beobachtung ist hier weder begonnen noch
automatisch eingerichtet. Kein belastbarer Fertigstellungstermin vor Größen-
und Vertragsentscheidung. Engineering besitzt Dimensionierung/Schnittstellen,
unabhängiges Review die Gegenprüfung; der Nutzer entscheidet die neue
Betriebsgrenze und gegebenenfalls einen danach nötigen Speichermodellwechsel.

Technische Primärgrundlagen: Konsistente Kopien müssen die tatsächliche
SQLite-Backup-/Snapshotmechanik verwenden, nicht rohes Kopieren einer laufenden
Datei. [SQLite Backup API](https://www.sqlite.org/backup.html).
Normales Lesen einer WAL-Datenbank ist nicht mit einer unveränderbaren
versiegelten Datei gleichzusetzen. [SQLite WAL](https://www.sqlite.org/wal.html).
Prozesslimits und gemessener Ressourcenverbrauch sind getrennte Größen; die
neue Gesamtbilanz ist ein eigener Architekturvertrag.
[Python resource](https://docs.python.org/3/library/resource.html).
