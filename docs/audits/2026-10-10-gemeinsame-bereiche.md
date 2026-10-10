# Gemeinsame Bereiche und eindeutige Gegenrisiken

## Freigegebener Umfang

Eine Bereichsauswahl unter dem gemeinsamen Wettfinder-Dach: Automatisch,
Eigene Suche, RisikoBet, 3 a day, 15K, Live, Meine Tipps. Kein zweites Desktop-,
Mobile- oder Modusmenü. Bestehende Abo- und Kontensperren bleiben erhalten;
die Navigation selbst startet keine Suche.

Mit übernommen: Gegenrisiko direkt mit dem betroffenen Ereignis kennzeichnen.
Bei Parma über 5,5 Ecken bedeutet 81,4 % **höchstens fünf Ecken für Parma**,
nicht eine 81,4-%-Chance auf ein Parma-Tor. Für Resultat/Tore-Kombimärkte wird
die exakte UND-/ODER-Negation mit der richtigen ganzzahligen Torgrenze gezeigt.

## Korrekturen der angrenzenden TOP-Prüfung

- Aktuelle, verfügbare H2H-, Wetter- und Ausfallprüfungen erforderlich;
  eine morgens noch offene Aufstellung allein verhindert TOP nicht.
- Fehlende/alte Kontextbelege ändern keine Modellrichtung oder
  Whole-Pool-Kohärenz. Ein stärkerer Heimsieg bleibt der modellseitige Anker,
  statt durch einen schwächeren Auswärtssieg mit besserem Kontext ersetzt zu werden.
- Tatsächlich abgeschlossener, exakt zugeordneter Quotenversuch ist getrennte
  TOP-Voraussetzung. Ein dokumentierter Versuch ohne lieferbare Quote ist kein
  falscher Modellausgang. Nie geprüfte Karten bleiben zusätzliche Auswahlen.
- Originale Prüfzeiten, Spiel-/Marktbindung und 24-Stunden-Frist werden verwendet,
  keine neue Frische durch Laden der Seite. Bekannte Quoten unter 1,20 werden
  weiterhin erst nach modellseitiger Kohärenz ausgefiltert.
- RisikoBet liest die ursprünglichen Kontextfristen auch zum Renderzeitpunkt.
  Eine eigene Anzeigequote darf einen tatsächlich vorhandenen Abrufnachweis
  nicht löschen oder erzeugen. Preiswerte bestimmen weder Modellchance noch
  Richtung oder Rangfolge.
- Neue Fußball-RisikoBet-Snapshots tragen einen kleinen typisierten Prüfbeleg
  im vorhandenen Faktorformat; keine Datenbankmigration. Die Schemafassung wird
  in die unveränderliche Eingabeidentität gebunden. Alte PARTIAL-Snapshots ohne
  passenden Nachweis werden nicht aus Freitext als vollständig interpretiert.
  Der interne Beleg wird nicht als Kunden-Analysesatz gezeigt.

## Nachweise und Stand

Die lokale Regression einschließlich Nachprüfung aller ursprünglichen
Fehlerfälle ist abgeschlossen. Veröffentlichung und Produktionsbrowserprüfung
stehen noch aus; dieser Bericht behauptet noch keinen abgeschlossenen Release.

Der unabhängige Abschlussreview ist inzwischen beendet: keine verbleibenden
konkreten P1/P2 im aktuellen Produktionsdiff. Letzte Originalrepros bestätigt:
fehlender Kontext eines ausgewählten Markts kann nicht durch einen anderen Markt
zertifiziert werden; negativer Beleg respektiert einen früheren Input-Cutoff;
explizit negative Aufstellung ohne Clock bleibt beim serialisierten Wettfinder
zusätzlich statt TOP. Ein pending-Status allein bleibt zulässig. Echte Gegenpreise
und Modellzahlen wurden durch diese Prüfungen nicht verändert.

- Test-first: Navigation 20 echte RED-Fälle vor der Umsetzung, anschließend
  20 grün. Richtung/Kontext: 24 echte RED-Fälle in Signal- und Kartenpfad;
  nach Trennung der Zulassung 141 betroffene Tests grün.
- Kombimärkte: sechs echte RED-Fälle vor der Ergänzung; danach 187 fokussierte
  Tests grün und mathematischer Gegencheck der Negationen.
- Ursprünglicher Vollsuite-Aufruf scheiterte an fehlendem Django im lokalen
  Test-Venv. Testabhängigkeiten aus dem vorhandenen Portalmanifest ergänzt;
  Collection mit isolierten Portal-QA-Settings danach erfolgreich.
- Windows-Sandbox versperrte temporäre Backup-Testordner (WinError 5). Derselbe
  unveränderte Testbereich außerhalb der Sandbox: 49 bestanden, sechs
  plattformbedingt übersprungen. Kein Lockern des produktiven Pfadvalidators.
- Die gestartete Vollsuite wählte für Bash-Harnesses den WindowsApps-/WSL-Alias,
  der bereits an `set -euo pipefail` vor dem eigentlichen Testablauf scheiterte.
  Identischer Einzeltest nur mit Git-Bash-Prozess-PATH: grün; das vollständige
  unveränderte Update-Hook-Modul danach 351 bestanden. Keine produktiven
  Pfad-, Backup- oder Updatevalidatoren geändert und keine Tests ausgeblendet.
- Zwei Prognoseleser-Grenztests brauchten eine explizite Behauptung für das neu
  getrennte `model_eligible`-Feld: akzeptierter Originalbeleg wahr, fehlender
  Beleg falsch. Sonstige Gleichheits- und Zeitgrenzen unverändert. Ganze Datei
  danach 57 Tests und 26 Untertests bestanden; Navigation plus letzter
  serialisierter Kontext-Gegentest nochmals frisch: 66 bestanden.
- Vollsuite bis zum Ende: **12.683 bestanden, 50 fehlgeschlagen, 97 Skips,
  143 bestandene Untertests** (53:16 Minuten). 46 Fehlschläge waren der
  WindowsApps-Bash; vier betrafen alte Testanbindungen an die geänderte
  Schnittstelle. Neben den beiden Feldprüfungen wurde der RisikoBet-Mock um
  den explizit geprüften gemeinsamen Zeitpunkt ergänzt (ganze Datei: 64 grün).
  Der Daily3-Test verwendet jetzt einen injizierten späteren Kontext-only-
  Refresh und einen tatsächlich ausgeführten leeren Preisversuch, bei hart
  unveränderten Mitternachts-Modellzeiten (ganze Datei: 106 grün).
- **Alle 50 Originalfehlerfälle gemeinsam erneut ausgeführt: 50 bestanden,
  Exit 0 (26,75 Sekunden).** Kein produktiver Fix, Skip oder gelockerter
  Validator für diese Fehlermeldungen. Der ursprüngliche Vollsuite-Aufruf
  wird nicht nachträglich als ein einzelner fehlerfreier Lauf bezeichnet.
- Weitere frische Diffregression: 281 bestanden. Produktivcode war während
  Vollsuite und Nachprüfung unverändert; nur präzisierte positive Testbelege
  und Test-Schnittstellen wurden ergänzt.
- Lokaler interner Browser: alle sieben Bereiche hin/zurück und Tastatur;
  Desktop 1440, Mobil 390/320 Pixel ohne horizontalen Überlauf. Ein Selector,
  keine alten Doppelmenüs, keine Console-Warnungen/Fehler. Synthetische Karte
  ausdrücklich als lokale Darstellung markiert, kein echter Tipp.

Lokale Belege außerhalb Git:
`C:/Projekt/BetBoy/output/unified-navigation-20261010/`.

## Grenzen

Keine neue Verletzungs-/Wetter-/Müdigkeitswirkung berechnet oder empirisch
nachgewiesen. Keine Renditeverbesserung aus Softwaretests ableiten. Daily3-
Zeitfolge, bestehender Wettfinder-Datenfehlstatus, Domainumzug, Stripe und
Store-Release sind separate Aufgaben. Kein zusätzlicher Sport-/Modellscan,
keine Produktionssicherung oder Bereinigung für diesen Patch.
