# Stufe B — konditioneller Umsetzungsplan

Stand:12.September2026. Entwurf, **noch keine B-Implementierungsfreigabe**.
Verbindlicher zu entscheidender Vertrag:
[Versionierte Prüfnachweise](../specs/2026-09-12-versionierte-pruefnachweise.md).
Die vorherige Planfreigabe erlaubte diese B-Ausarbeitung nach A1 STOP;
Commit/Push/Deployment bleiben bereits erlaubt, wenn technische Abnahmen tragen.

## Vorbedingungen, bevor Produktcode entsteht

1. Unabhängiges Architekturreview auf festem Dokumentstand abschließen und
   konkrete Findings lösen, ohne die neue Betriebsgrenze als genehmigt zu buchen.
2. Der Nutzer entscheidet einmal den konkret beschriebenen B-Nachweis-/Lebens-
   zyklusvertrag inklusive isoliertem Prüfer, separatem Proofschlüssel/-speicher,
   neuer Vorprüfgesamtgrenze1800CPU/3600Sekunden und enger Bootstrapintegration.
3. Zuerst die Größenprobe durchführen. Das vorläufige7Tage-Profil kann laut
   unabhängiger Rechnung Eingabe1GiB/Historie256MiB überschreiten. Falls bestätigt,
   **vor B-Produktcode die separate Speicherarchitektur vorlegen**. Kein
   verkleinertes Profil, höheres Limit oder Umschreiben historischer Daten.

## Ausführung nach den Entscheidungen

| Aufgabe | Liefergegenstand | Abnahme / Stopp |
| --- | --- | --- |
| B0: Ausgangs-/Größenprofil | Frischer versiegelter Bestand, proTour ausgewählte kanonische Bytes, echte Snapshotreferenzgrößen, page/freelist/Indexanteile, begrenzte7Tage-Größenprobe | Alle alten Zeilen bewahrt; neue ownergültige Ereignisse; jeweilige Grenze eingehalten oder expliziter StorageSTOP |
| B1: Vertrags-/Testfixtures | Exakte Aufgaben-/Runtimeidentitäten, typisierter Inventardigest; kleine/negative Vergleichsbestände | Neue Regressionen zeigen fehlende Semantik auf alter Implementierung; keine künstliche alte Freigabe |
| B2: Vollständiges Inventar | Streamender gesamter Schlüssel-/Wert-/Typvergleich, physische/Schema-/Referenzprüfung unverändert | Mutation/Löschung/gleicheCounts/ungültige Extras erkennen; boundedRAM/Disk, keine öffentlichen Hashflags als Beweis |
| B3: Abhängigkeitsplaner | Vollständige transitive Aufgabenclosure plus kausale Präfix-/Selektoridentität | Rückdatierte Einfügungen, Gleichstände/Leermengen, andereTour und Statuswechsel invalidieren exakt notwendige Aufgaben oder konservativ mehr |
| B4: Zuständige Prüfschritte | Bestehende kalte Original-/Source-/Feature-/Transportowners für jede fehlende Aufgabe | Gleiche kanonische Werte; keine neue Prognose aus Proofcache; geschützte Finals opaque; vollständige Coverage vor Abschluss |
| B5: Isolierung/Publisher | Dedizierter Prüfer, root-versiegelte Runtime, feste boundedIPC, HMAC-Proofgeneration und CAS-Publikation | App kann nichts fälschen; keine Rootproduktimporte; stale/concurrent/crash/rollback/foreignhost negativeTests |
| B6: Wiederanlauf-/Kostenbuch | Persistente reservierte/verbrauchte Gesamtbudgets, alle Nachkommen, Frist/Bootwechsel, unvollständiger Status | Retry/Timeout/OOM darf weder Teil-PASS noch neues Gratisbudget erzeugen; keine heimlichen Zusatzpools |
| B7: Neue reine Lese-CLI | Gesonderter expliziter Nachweismodus; alte kalte CLI unverändert | Identische fachliche Reportwerte/Limitations; missing/badproof führt zu Vorbereitung oder Abbruch, nicht Success |
| B8: Linux-/Differenzabnahme | Aktuell30/31/32/33, historische/größere und abgenommenes Wachstum, DAC-/Races-/Versions-/Restoretests | Drei echte≤240CPU/Wandläufe pro Pflichtprofil und tatsächliche Vorprüfgesamtkosten; keine Übernahme alter Testergebnisse |
| B9: Bootstrap-/Updater-V2 | Getrennter exakter Einführungsvertrag, neuer erwarteter Helperhash, Backup/Restore und rollbackfähiger einmaliger Updateraustausch | Alter Installer kann nicht unverändert den bekannten300Sekunden-Fail passieren; neuer vollständiger Proof muss auch Erstinstallation tragen |
| B10: Release | Vollsuite exakter finaler Produktbytes, frischer Bestand/Backup, normaler main-Push, überprüfter Updater-/App-Rollout | main/VPS/exakterUpdater stimmen, Dienste/Timer/Health geprüft; separate Tennis-/empirische Baustellen nicht als fertig melden |

Pro Aufgabe ein enger Brief mit zuständigen Dateien und unveränderten Owners;
ein Schreiber je Bereich, unabhängiges Review. Root besitzt Index/Integration.
Alte Modell-/Feature-/Quell- und Runtime-Transaktionsverträge bleiben eingefroren,
sofern der explizite B-Brief nicht eine benötigte neue **Prüfschnittstelle** nennt.
Neue Logik nicht in bestehende öffentliche Testflags verstecken.

Schwere VPS-Läufe seriell. Große Vollsuite erst nach tragfähigem Größen-/Native-
Kandidaten. Durchgefallene Profile, abgebrochene Jobs und fehlende frische Tests
bleiben als solche sichtbar. Nachweisumfang/CPU/Datei-SHA und Codeversion bei
jedem Übergang festhalten. Neue Speichermigration, höhere Limits oder geänderte
Sportberechnungen erfordern einen anderen expliziten Vertrag.

## Jetzt abgeschlossen / offen

- [x] A1 gemessen und unabhängig als nicht ausreichend bewertet.
- [x] Reale Aggregatdaten erhoben und getrennte Speichergefahr berechnet.
- [x] Konkreter B-Entwurf und konditionelle Ausführungsschritte dokumentiert.
- [x] Unabhängiges B-Architekturreview abgeschlossen / P2 durch vorab vollständige Runtimeclosure und Lazy-Import-Gegentest behoben; geprüftes SpecSHA498e63c5641adaccdd4d284fa9b57ad93c02ba834e9abd6bf4064636d6b12da1.
- [ ] Neuer B-Betriebs-/Nachweisvertrag entschieden.
- [ ] Größenprobe / ggf. gesonderter Speichervertrag abgeschlossen.
- [ ] B-Produktcode, Tests, Kapazitätsabnahme und Deployment abgeschlossen.
