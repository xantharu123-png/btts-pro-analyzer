# Daily3: defensive Modellauswahl und kürzere Oberfläche

Stand: 19.09.2026, 12:09 CEST. Funktionscommit:
`1985407c176e4cf5ecc4a9d5b2a93636b8634673`, auf main und VPS verifiziert.

## Bestätigter Umfang

Der Nutzer priorisiert geringeres Verlustrisiko, nicht das Erzwingen von CHF150.
Policy `daily3-defensive-model-v2` verlangt mindestens 70% Modellschätzung
zusätzlich zu den bestehenden Beleg-/Aktualitätsregeln. Höhere Modellchance
zuerst, Vielfalt bei Gleichstand. Eine Auswahl pro Spiel, keine schwächere
Auffüllung. Quoten, Geldziel, Kontostand, Releaseflag und heuristischer Abschlag
verändern die Reihenfolge nicht. Normale Wettfinder-Auswahl unverändert.

Das ist eine defensive Modellpräferenz, kein empirischer Sicherheitsnachweis.
Insbesondere werden fehlende Verletzungs-/Müdigkeitseffekte damit nicht repariert
oder als berücksichtigt ausgegeben. Die aktuelle Hauptansicht zeigt diese
konkreten Unsicherheiten weiterhin unmittelbar am Spiel.

Daily3: eine Budget-/Zielzeile, ein Leerhinweis oder tatsächliche Auswahlanzahl.
Allgemeine Regeln im optionalen Popover. Keine verschachtelten Hauptkarten.
Doppelte Preisabsätze entfernt, konkrete Preiswarnungen bleiben. Auch die fünf
Bereichsbeschreibungen und redundanten Wettfinder-Überschrifttexte gekürzt.
Echtgeldrechnung, Ledger, bestehende Wetten und Benutzerbestätigungen unverändert.

## Prüfung

- 344 Tests bestanden im Reparaturworktree, danach dieselben 344 in main.
  Daily3-Auswahl/UI/Geldrechnung/Store/Backup, gemeinsamer Selektor,
  Analyse, Wettfinder-Oberfläche und Workflow-Integrität. Keine neue Vollsuite.
- Regressionen: 69,9999/70%-Grenze, aktuelle schwächere versus ältere höhere
  Prognose, hohe unbegründete Werte, Quote/Haircut/Releaseflag, getrennte
  Ereignisse, keine alten Gegenrichtungen, Preiswarnungen und Echtgeldablauf.
- Lokaler Browser: leer/gefüllt, Popover, 1440px Desktop und 390px Mobil.
  Screenshots in `output/playwright/daily3-v2-*20260919.png`.
- Frisch geladene Produktion zeigt die neue Fassung und drei heutige
  Modell-Auswahlen; keine Preisfreigabe oder echte Platzierung daraus ableiten.
  Mobil scrollWidth=390 bei innerWidth=390. Null Console-Fehler; neun
  Framework-/iframe-Browserwarnungen separat protokolliert, nicht als behoben
  ausgegeben. Keine echten Budgets, Einsätze oder Abrechnungen bedient.

## VPS

Code-only Fast-forward unter bestehendem Deploy-Lock, explizite Acht-Dateien-
Allowlist. Sechs Rechentimer kurz pausiert, vorhandene Jobs normal auslaufen
lassen, App neu gestartet, vorherige Timer wiederhergestellt. Interner und
öffentlicher Healthcheck `ok`, App/Caddy aktiv. Keine Datenbankmigration,
Kompaktierung, zusätzliche Backups oder Bereinigung.

Tagesbackup weiterhin disabled/inactive; Retention unverändert. Installierter
Root-Updater unverändert und nicht ausgeführt. Der einmalige SSH-Auftrag gab
nach vollständig bestätigtem COMPLETE wegen einer nachfolgenden Windows-CR-
Leerzeile Exit1 zurück. Frische separate Prüfung bestätigt exakt den Zielcommit,
sauberen tracked Checkout, App, Timer und Healthchecks. Lokales Wartungsskript
mit explizitem `exit 0` gegen diese Transportkante korrigiert, nicht erneut
ausgeführt. Kein falscher Exit0-Nachweis für den ursprünglichen Auftrag.

Der vor dem Release gestartete Wettfinderjob endete mit ExecMainStatus1 und
veröffentlichte Teildaten. Das ist nicht durch dieses UI-/Auswahlrelease behoben.
Höhere tatsächliche Trefferquoten und vollständige Kontextwirkung bleiben offen.
