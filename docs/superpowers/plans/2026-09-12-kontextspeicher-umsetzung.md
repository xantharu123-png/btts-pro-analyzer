# Umsetzung C und anschließender B-Prüfer

12. September 2026. Der Nutzer hat auf die konkrete Speicherfrage mit **„ja“**
geantwortet. Spezifikation08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba
ist damit freigegeben; kein weiteres Einholen derselben Freigabe.
Der unverändert archivierte Spezifikationstext dokumentiert den Entscheidungsstand
vor dieser Antwort. Neuer Modus: vollständiger Eingabesatz4GiB, kanonische
Tourhistorie1GiB, Blöcke16MiB, neuer QA/Aufbau/Ausgabebereich8GiB, mindestens4GiB
freie Reserve. CPU/RAM/gesamte Prüfvorbereitung wie B, kein Gratisbudget je Portion.

## Enger erster Integrationsabschnitt

Ausgangspunkt b2e811a, Produktbytes72421d3. Isolierter bestehender Worktree bleibt.
Neue Module unter context_storage_v2; alte Quell-/Modell-/Feature-/Runtimeowners
werden in diesem Abschnitt nicht geändert. Kein Aufruf aus Produktion und keine
Servermigration, bevor die vollständigen Freigabekriterien bestehen.

1. Root: gemeinsame Grenzen/Fehlerklassen; vollständiges typisiertes Zeilen-
   inventar als Grundlage der Kopie/Äquivalenz; Aufgabenbriefe, Integration/Index.
2. Referenzautor: refs.py und eigene Tests. Unveränderliche deduplizierte Blöcke,
   vollständiger Manifest-/Gesamtarraydigest, exakte sortierte Mitgliedschaft.
3. Historienautor: history.py und eigene Tests. Rein private plattengestützte,
   danach query-only gebundene Historie, vollständige Auswahlprüfung/1GiB je Tour,
   wiederholbare Reihenfolge/zeitliche Sichten; keine unbeschränkte RAMsammlung.
4. Tennisautor: tennis.py und eigene Tests. Expliziter neuer Streamingowner für
   bisherige v3-Semantik, vollständige alte Gegenreferenz; keine Änderung der
   Originaldateien, kein bloß vorgetäuschter Tuple-Vertrag, keine Gewichte/Quoten.
5. Root + unabhängiger Reviewer: vollständiger jeweiliger Diff, negative Fälle,
   Eigentümerschnittstellen und Ressourcen. Danach kopiebasierte Gesamtintegration.

Neue Schnittstellen sind noch keine HMAC-Prüfberechtigung. Öffentliche Digests
belegen Transportidentität; der bestehende B-Vertrag besitzt die spätere isolierte
Authentisierung, vollständige Coverage, Codeclosure und Veröffentlichung.

## Danach, ohne übersprungene Abnahme

- Verlustfreie komplette Kopie/typisierter Vergleich aller alten Tabellen und
  Bytewerte; Referenzdarstellung als neue Version, alte Bytes erhalten.
- Tatsächliche vollständig erzeugte Wachstumsbestände und Speicher-/RAM-/CPU-
  Messung, auf dem VPS nur versiegelte Eingaben und isolierter QA-Bereich.
- B-Inventar/Abhängigkeiten/Prüfportionen/geschützter Publisher und Kostenbuch.
- Vollständige neue read-only CLI, Bootstrap, Backup/Restore und verlustfreier
  Rückweg auch für während einer Umstellung neu eingegangene Belege.
- Drei native vollständige Schlussprüfungen pro Pflichtprofil <=240CPU/Wand,
  gesamte Vorbereitung<=1800CPU/3600Gesamt; einzelne WorkerCPU300/AS2GiB/RSS<1GiB.
- Exakte Produktvollsuite, unabhängiger Abschlussdiff, normaler main-Push und
  kontrollierter Updater-/App-Rollout; tatsächlich gelieferte Version und Health.

Keine empirische Kontextfreigabe, Cricketarbeit, A0/P4b3 oder Reparatur des
separaten Tennis-Tagesjobs aus diesem technischen Speicherabschnitt ableiten.
Offene Arbeit bleibt offen; der erste lokale Baustein ist kein Gesamtabschluss.
