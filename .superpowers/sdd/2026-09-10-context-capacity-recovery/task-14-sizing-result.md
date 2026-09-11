# Task14 / B0 — gemessene Groessen, kein Produktiv-PASS

12.September2026. B-Vertrag vom Nutzer mit "ja maxhrn" freigegeben;
spec498e63c5. B0 ist die vorgeschaltete Groessenentscheidung, nicht D4,
nicht die vollstaendige7Tage-Probe und nicht eine Modellqualitaetsabnahme.
Keine B-Produktimplementierung, keine geaenderten Grenzen oder alten Daten.
**Abgeschlossen: notwendiger StorageSTOP der konzentrierten ATP-Groessenprobe.**
Die getrennte Speicherentscheidung liegt als noch nicht genehmigter Vorschlag
in docs/superpowers/specs/2026-09-12-kontextspeicher-entscheidung.md vor.

## Identitaeten und bereits gepruefte Schritte

- Arbeitsbranch codex/context-capacity-recovery-20260910, AusgangsHEAD6a0ba81.
- Unveraenderte Produktbytes72421d3bdbec4ab15a3d2953cb153e867e7e340a.
- Frische versiegelte VPS-Kopie:
  /var/lib/betboy-live-backup-ssfvf5xs/context-current.db,
  270233600Bytes, SHA73ec16911c7d66e894a0f92c6600e3486e34b57c4176b30938638d3669146ffa.
- Vollbackup/Restore/bestehende Kontointegritaet:88Datenbanken bestanden;
  gesamte bestehende Backupkette40.78CPU/41.52Wandsekunden,
  632128KiBSpitzen-RSS. Privatarchiv und Schluessel bleiben auf dem VPS.
  Vollstaendige Metadaten: evidence/task14-fresh-backup-20260912.jsonl.
- Groessenhelper9b4d3a0f8501dda9d0ab0bb3714bcf4f59d5487d2ccdc5f23cefda56f07327f4,
  Eigenpruefungeneac0ef49826fdda95efe66414e414cd0022bae79c1dc8cd3f3e1cc1a963aa197.
  Root hat beide vollstaendig gelesen;8kleine Owner-Gegentests frisch bestanden
  in0.140s. Dies ersetzt weder Linuxmessung noch Produktvollsuite.
- Frischer rein lesender Servercheck: main/VPS2dd1116,
  alter Updater74b1c4b1 unveraendert; App/Caddy/7Timer aktiv+enabled,
  interner/oeffentlicher Health200ok. Separater betboy-tennis.service failed
  bleibt offen und unveraendert. evidence/task14-health-20260912.json.

## Ausfuehrungsjournal

Konservativer Gesamtbeginn23:19:00UTC am11.September2026; Grenze3600Sekunden
einschliesslich Vorbereitung/Wiederholungen. Ende23:46:11UTC,1631Sekunden
konservative Gesamtdauer. Gemessene nativeCPU einschliesslich Backup332.16
von1800; keine fehlgeschlagenen nativen Messversuche oder heimlichen Neustarts.
Schwere VPS-Laeufe seriell, je WorkerCPU300/AS2GiB/RSS<1GiB, Metadaten<=1MiB.
Baseline ist nativ vollstaendig abgeschlossen. Root verbucht auch erfolglose Anlaeufe;
ein fehlender Abschluss darf nicht als gueltiger Folgeteil verwendet werden.

Die vollstaendige Basishistorie wird pro Tour exakt kanonisch gezaehlt.
Neue synthetische ATP-Statusbelege durchlaufen unveraenderte Normalisierung,
physische Dekodierung und Quellenauswahl, hoechstens70000pro Tagesportion.
Eine exakte Ueberschreitung von256MiB beendet diesen notwendigen Stresstest.
Es werden weder kuenftige Echtspiele behauptet noch199Snapshots materialisiert.

## Frischer gemessener Ausgangsbestand

Raw evidence/task14-baseline-20260912.log,
SHAa6ebff9d0b08c617ed51948cc77d5ded2a62a948fc4b5177e36038f545877189.
Quelldatei-/Input-/Verzeichnisseals unveraendert, alle Abschlussflags gueltig,
Prozessexit0. GNUtime84.00CPU/84.06Wandsekunden,177556KiBSpitzen-RSS.
Gesamt einschliesslich Backup124.78CPU/125.58native Ausfuehrungssekunden.

| Exakte Ist-Messung | Wert |
| --- | ---: |
| Alle Belege / Contentzeilen | 100553 / 100553 |
| Vollstaendige ATP-Historie | 42099Zeilen / 58390805Bytes |
| Vollstaendige WTA-Historie | 54819Zeilen / 75669070Bytes |
| Sonstige physisch gepruefte Belege | 3635, darunter40match_outcome |
| Snapshots / Originale / Tourzustaende | 31 / 31 / 2 |
| Unterschiedliche Original-Cutoffs | 16, ATP |
| Snapshot-Payloadbytes | 66373102 |
| Darin kanonische observation_refs | 61392466Bytes / 916305Referenzen |
| Referenzanteil der Snapshot-Payloads | 92.496Prozent |
| Content-Payloadbytes | 107332761 |
| Datenbank / Freelist | 65975x4096=270233600Bytes / 0Seiten |

Die31gespeicherten Refarrays sind exakt67*n+1Bytes gross. dbstat-Seitenanteile
summieren exakt auf die versiegelte Dateigroesse. Alle31Snapshot-Refcounts passen
zur jeweils gemessenen vollstaendigen ATP-Praefixanzahl; das ist kein Ersatz fuer
Feature-/Originalreplay. Reale BaselineWTA ist nicht null. Die neue Baseline
ist spaeter als die alte99776/6Outcome-Metadatenaufnahme; keine Daten aus alten
Messungen als aktuelle Zahlen eingesetzt.

Unabhaengiger Reviewer hat rawSHA, die ganzen Phasen, Zeilen-/Byte-/Artensummen,
Runtime-/Seals-/Ressourcenabschluss und die exakten Tag1Argumente nachgeprueft.
Die folgenden neuen nativen Portionen grenzen den notwendigen Fehler exakt ein;
eine vollstaendige Wachstumsabnahme wird nicht behauptet.

## Gemessener erster Grenzfall und Stopp

| Teil | Neue ATP-Belege | Neue kanonische Bytes | Kumulative ATP-Historie |
| --- | ---: | ---: | ---: |
| Ausgangsbestand | — | — | 42099Zeilen / 58390805Bytes |
| Tag1 vollstaendig | 70000 | 100170000 | 112099 / 158560805 |
| Tag2 vollstaendig | 70000 | 100170000 | 182099 / 258730805 |
| Tag3 bis erste Ueberschreitung | 6782 | 9705042 | 188881 / 268435847 |

Jeder neue Beleg misst tatsaechlich1431kanonische Bytes. Nach146781neuen
Belegen liegt die Summe268434416 noch1040Bytes unter dem Cap. Der146782.Beleg
ergibt268435847Bytes, **391Bytes ueber268435456 (256MiB)**. Tag3meldet korrekt
storage_stop:true/day_completed:false bei measurement_completed:true. Die
notwendige Grenze ist vollstaendig gemessen; der dritte volle Tag und weitere
Tage werden nicht mehr erzeugt. Keine weitere native Groessenprobe gestartet.

Alle vier Messungen Exit0, vollstaendiger Abschluss, identische Source724/
Input73ec1691/Interpreter1643dacd/SQLite3.45.1, komplette Seals unveraendert.
Die Tagesargumente sind ausschliesslich aus vollstaendigen Vorgangerlogs
uebernommen; jeder Tageslog nennt den exakten SHA des gesamten Vorgangerlogs.
Keine alten Daten editiert, keine Wachstumskopie oder neuen Snapshots geschrieben.

| Rohlog | SHA256 |
| --- | --- |
| evidence/task14-day1-20260912.log | da22a2fc6da40c360691312915f1d136842e8a4532c39d2ddfd833885ab96007 |
| evidence/task14-day2-20260912.log | 59c226e2c3a45cee89af496667de8ae03347af7dd2958b7d7c8b3b84f3db342d |
| evidence/task14-day3-20260912.log | d4cccc6a20926893ad34847aee67f8f808ab672eb4466f30648011cb2ffc194a |

Die exakten Instrument-/Eigenpruefungsbytes wurden zusaetzlich unter
evidence/task14-instrument archiviert; beide SHAs entsprechen den ausgefuehrten
lokalen Dateien. Wiederherstellungspfad und Diagnosegrenzen stehen im README.
Keine geheimen oder privaten Daten sind in diesem Archiv enthalten.

## Ressourcen und unabhaengiger Abschluss

| Native Phase | GNU/aeussere CPU s | Wandzeit s | RSS KiB |
| --- | ---: | ---: | ---: |
| Backup/Restore/Kontointegritaet | 40.78 | 41.52 | 632128 |
| Baseline | 84.00 | 84.06 | 177556 |
| Tag1 | 98.44 | 98.63 | 44908 |
| Tag2 | 97.20 | 97.24 | 45040 |
| Tag3 bis Grenze | 11.74 | 11.76 | 44904 |
| Summe | 332.16 | 333.21 | nicht additiv |

1631chronologische Sekunden enthalten die Zwischenzeiten und Vorbereitung;
333.21ist nur die Summe der nativen Ausfuehrung. Beides bleibt getrennt.
Keine Kapazitaetszulassung fuer einen vollstaendigen Replay aus dem niedrigen
RAMverbrauch eines streaming Bytezaehlers ableiten. Die acht kleinen lokalen
Tests sind ebenfalls keine grosse Produktvollsuite.

Unabhaengiges Ergebnisreview task-14-size-review.md,
SHA5776a9f72111c24b046aa8c997c9d06f944ae54f856c5e2c88458652c686dfd2,
hat alle vier Rohlogs, Summen, Lineage, Grenzen und Abschlussbedingungen
vollstaendig gegengeprueft. Resultat: notwendiger B0StorageSTOP bestaetigt.

## Bedeutung fuer den naechsten Schritt

Der aktuell gemessene echte Bestand passt unter die Groessencaps. Das konkrete
synthetische ATP-Profil passt nicht. Daraus folgt weder ein heutiger Live-Ausfall
noch ein vorhergesagtes Datum. Die1GiB-Eingabedateigrenze fuer einen vollstaendigen
zukuenftigen199Snapshot-Bestand wurde nicht gemessen und nicht als bestanden
oder gescheitert gebucht.

Der B-Vertrag verlangt fuer diesen Fall eine **getrennte Speicher-/Eingabeentscheidung
vor B-Produktcode**. Diese Vorlage trennt deshalb explizit groessere Gesamtmengen
auf Platte von unveraenderten CPU-/RAM-Arbeitsgrenzen, Datenhaltung von
Sportberechnung und eine neue Version vom unveraenderten alten Pruefmodus.
Noch keine Umsetzung oder Deploymentfreigabe aus dem Vorschlag ableiten.
Feste C-EntscheidungsvorlageSHA08f296bfd0b7c43e4934367ec2533f29464b28f9dc7d2ada218ea194ae4645ba,
unabhaengiger Dokumentreview185d45dc272d611c636f64bd34fcbec00965a84fe11cc7f3aec75ca9192f0f0f;
als Vorlage ohne offene wesentliche Findings, weiterhin ohne Nutzerfreigabe.
main/VPS bleiben2dd1116 und der Updater74b1c4b1; separate Tennis- und empirische
Baustellen bleiben offen. Nur Diagnostik, Nachweise, Uebergabe und Plan wurden
in diesem Schritt bearbeitet.
