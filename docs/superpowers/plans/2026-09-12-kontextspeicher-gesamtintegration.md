# Nächster C-Abschnitt: globale Bilanz und tatsächliche Größenprobe

Engineering-Fortsetzung innerhalb der bereits freigegebenen C-/B-Verträge;
keine neue Nutzerentscheidung, keine Erweiterung der Werte oder des Scopes.
Stand12.September2026: C1/C2/C3/Tennis/Quelladapter lokal differenziell geprüft.
Das ist noch keine vollständige Speicher-/Wachstums-/VPS-Abnahme.

1. Ein einziger Vorbereitungseigentümer reserviert **vor** jedem Writer dessen
   vollständiges mögliches Wachstum. Aktiver Eingabesatz inklusive aller eigenen
   Indizes/Blöcke/Manifeste insgesamt4GiB; alle neuen QA-/Aufbau-/Ausgabedateien,
   Archive, Spillbereiche und fehlgeschlagenen Versuche insgesamt8GiB. Feste
   Slotbudgets, exklusiver Job-Lock, keine Erneuerung des Budgets je Datei/Teil.
2. Diskwalks dienen dem Abgleich dieser Reservierung, nicht allein als Quota.
   SQLite-Journale, Statementjournale, TEMP-Sortierung, noch offene unbenannte
   Dateien und Konkurrenz müssen in einem tatsächlich kontrollierten Writer-
   Profil enthalten oder nachweisbar ausgeschlossen sein. max_page_count alleine
   genügt nicht. Kein Abschalten der Atomizität an Quell-/veröffentlichten Daten.
3. Mindestens4GiB tatsächlicher freier Platz zusätzlich; schon vorhandene Backups
   und Rückweg frisch einrechnen. Eine belegte Reservedatei ist kein freier Platz.
   Slots erst nach geschlossenem Writer und nachgewiesener Zuständigkeit lösen;
   keine Alt-/Laufzeitdaten oder Backups löschen, um einen Pass zu erreichen.
4. Die gesamte echte Vorbereitung vor dem Start an Eingabe-/Code-/Runtimeidentität
   und Kostenbuch binden:1800CPU/3600Gesamtsekunden über sämtliche Teile/Versuche.
   EinzelworkerCPU300/AS2GiB/RSS<1GiB/Ausgabe1MiB. Unbekannter Crashverbrauch
   konservativ verbuchen, keine Prozess-/Boot-/Uhr-/Retry-Budgetrücksetzung.
5. Vor großem Aufbau den gemessenen lokalen C2/C2b-Lesepfad bewerten. Gegebenenfalls
   eine **neue** begrenzte Chunk-Schnittstelle ergänzen; die existierende skalare
   Schnittstelle und ihre sofortige Lebensdauerprüfung nicht still abschwächen.
   Nur echte Messungen zählen, keine lineare Hochrechnung als Pflichtprofilpass.
6. Vollständige reale Baseline plus tatsächliches synthetisches Sieben-Tage-Profil:
   100553+490000=590553Belege,31+168=199Originale/Snapshots,16+98=114Stichtage.
   ATP-lastig, gemischt und Burst; jedes Original/Snapshot über echte zuständige
   Owner, nicht durch frei erfundene Hash-/Erfolgshüllen. Vollständige alte Bytes
   bleiben nachweisbar; C-Transport ist keine Modell- oder Quellenfreigabe.
7. Erst nach erfolgreicher C-Größen-/Ressourcenprobe B-Nachweise/Abhängigkeiten/
   transitive Ausführungsclosure und geschützten Publisher/Bootstrap anschließen.
   Drei echte finale Läufe je Pflichtprofil<=240CPU/Wand; Restore samt inzwischen
   neu eingegangenen Belegen, exakte Vollsuite und unabhängiges Release-Review.
   Danach normaler main-Push und kontrollierter Updater-/App-Rollout.

Die Datei erklärt nächste ausführbare Arbeit, keine bereits vorhandene globale
Budgetkontrolle. Kein neuer OS-Dienst/VM/externes Quota-/Datenbanksystem nötig
oder hier autorisiert. Alle abweichenden empirischen, Sport- und Tagesjob-Themen
bleiben außerhalb dieses technischen Abschnitts. Ausführliche Reviewbegründung:
`.superpowers/sdd/2026-09-10-context-capacity-recovery/task-18-copy-independent-review.md`.
