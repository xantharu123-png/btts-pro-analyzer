# Task15 — enger Review der separaten Speicherentscheidung

Stand: 12. September 2026. Prüfer `/root/b0_size_review`.

Ursprüngliche Vorlage vollständig gelesen:
`docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md`, SHA256
`95fe3fbcc4b8964ba7c08f15cff9efa0fdcedc0f79ce43d94e3d69e2e3994b5d`.
Vergleich mit dem B-Vertrag, tatsächlichem B0-Ergebnis und den bestehenden
Grenzen in `context_runtime.py`/`context_runtime_history_cache.py`.
Keine Ausführung, SSH-, Produkt-, Index- oder Serveränderung durch den Reviewer.

## Enger Befund

Ein konkreter Bestandsfehler in C4 ist vor der endgültigen Vorlage zu korrigieren:
Die Formulierung „bisherigen 64-MiB-Einzelwert-/Legacy-Regeln“ nennt einen
Einzelwertvertrag, den die überprüfte Produktsource nicht besitzt. 64 MiB
begrenzt dort die **gesamte Legacy-In-memory-Eingabedatei**; zusätzlich gibt es
den getrennten 64-MiB-/32-Plätze-Historycache. Der 64-MiB-SQLite-Einzelwertcap
war eine eigene Grenze des B0-Messinstruments, kein Alt-Produktvertrag.
Diese drei Dinge müssen getrennt benannt werden, damit der neue Modus nicht
versehentlich eine zusätzliche bisher angeblich bestehende Grenze übernimmt.

Zwei eng begrenzte Formulierungspräzisierungen ebenfalls empfohlen:

- B verlangt den abschließenden Check einschließlich Zuwachs tatsächlich
  innerhalb von 240 CPU- und Wandsekunden. In C4 daher „Abnahmegrenze“ statt
  lediglich „Ziel“ verwenden; die vorgeschlagene größere Datenhülle lockert
  diese Pflicht nicht.
- „Die größere vollständige Datenhülle wird ... ermöglicht“ ist noch nicht
  durch einen Prototyp belegt. „Soll ... ermöglicht werden“ erhält die sonst
  klar formulierte Trennung zwischen vorgeschlagener Hülle und gemessenem Pass.

## Sonstige Grenzen im Entwurf

Keine weiteren konkreten Widersprüche oder versteckten Befugnisse gefunden:
4 GiB Gesamteingabe, 1 GiB vollständige Tourhistorie und 16 MiB je Block werden
ausdrücklich als **neuer zu genehmigender Modus** ausgewiesen, nicht als neue
Deutung des alten 1-GiB-/256-MiB-Vertrags. 8 GiB neuer Aufbau-/QA-/Ausgabebereich
und 4 GiB frei zu haltende Reserve werden nicht je Teilprozess vervielfacht.
RAM-/CPU-/gesamte Vorbereitungsbudgets bleiben bindend; vorhandener freier
VPS-Platz ist nur Momentaufnahme, kein behaupteter Kapazitätspass.

Alte Bytes, Digests und Original-Codeidentitäten sollen unverändert bleiben.
Die ausdrücklich neue Leseschnittstelle darf keine Tuple-Kompatibilität oder
vollständige Mitgliedschaft vortäuschen; fachliche Werte und Reihenfolge sind
gegen die alten zulässigen Owners exakt zu vergleichen. Quellen-/D2-Grenzen,
fehlende Werte und ursprüngliche Fehlerfälle bleiben erhalten. Neue Speicherung
ist weder eine empirische Modellfreigabe noch eine Garantie besserer Wetten.

Backup, konsistenter Generationswechsel und verlustfreier Rückweg sind
Voraussetzungen, keine still erteilte Lösch-/Migrationsfreigabe. Keine zusätzliche
Serveraufrüstung, externe Datenbank, Secretübertragung oder Cricketänderung.
Die bestehende B-Freigabe wird nicht erneut erfragt; C braucht genau die bislang
ausgenommene eigene Speicher-/Eingabeentscheidung. Die Vorlage ist noch keine
Produktimplementierungs- oder Deploymentabnahme.

## Korrektur und endgültiger Dokumentstatus

Die eng begrenzten C4-Korrekturen wurden anschließend an der festen Vorlage
SHA256 `08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba`
erneut gelesen und gegen die oben genannten Originalowners geprüft:

- Legacy-Gesamteingabe mit 64 MiB, Cache mit 64 MiB/32 Slots und B-Nachweisspeicher
  sind jetzt ausdrücklich getrennt. Der nur instrumentelle SQL-Einzelwertcap
  wird nicht länger als alter allgemeiner Produktvertrag ausgegeben.
- Neue Einzelwert- und Blockanzahlgrenzen müssen innerhalb der erst zu
  genehmigenden Hülle getestet festgelegt werden; keine automatische Umdeutung.
- Der abschließende Check bleibt eine verbindliche Abnahmegrenze von 240 CPU-
  und Wandsekunden. Die größere Datenhülle „soll“ ermöglicht werden, ihr Pass
  wird nicht vorweggenommen.

**APPROVED als Entscheidungsvorlage; keine offenen wesentlichen Findings.**
Das ist weder die ausstehende Nutzerfreigabe für C noch eine technische
Tragfähigkeits-, Implementierungs- oder Deploymentabnahme. Diese bleiben
Gegenstand des nach Freigabe zu bauenden Prototyps und vollständiger Messungen.
