# Tageslauf: physische Inventur statt nur Ergebnisindex

Stand: 11.10.2026, reine Leseprobe im vorhandenen VPS-Bestand.
Kein Sport-/API-Scan, Backup, Datenbankarchiv, Bereinigung oder Geld-Eingriff.

## Konkrete Betriebsbelege

- Der reguläre Wettfinder vom 11.10. lief 03:35:22–04:20:22 CEST und wurde
  nach 45 Minuten beendet; 40 Minuten 35 Sekunden CPU-Zeit. Der vorherige
  Lauf vom 10.10. brauchte bereits etwa 44 Minuten und 40 Minuten CPU.
- Der normale Tennisjob vom 11.10. verarbeitete 82 Karten in 1.566,586 s,
  verbrauchte 24 Minuten 37 Sekunden CPU und erreichte 3,4 GB Speicher plus
  1,2 GB Swap. Die letzten Karten benötigten nur etwa 0,16 s für Features;
  die gesamte Veröffentlichung benötigte anschließend etwa 31 s.
- Die bestehende Kontextdatenbank enthält 2.547.645 physische Receipts und
  ebenso viele unterschiedliche Content-Zeilen. Eine LRU-Deduplizierung
  gleicher Content-BLOBs wäre hier keine belegte Lösung.
- `LiveWorker.finish()` prüft die komplette physische Inventur vor der
  Tour-/Spielprojektion. Das bleibt fachlich erhalten: fremde und zukünftige
  beschädigte Zeilen dürfen nicht durch einen vorgezogenen Filter verschwinden.
- Ein begrenztes Profil von 512 nativen Receipts zeigte: die vollständige
  Normalisierung beanspruchte 0,084 von 0,173 s; drei JSON-Serialisierungen
  zusammen 0,043 s. Der reparierte Ergebnis-Lookupindex betrifft einen
  anderen Ablaufabschnitt und beweist allein keinen behobenen Tages-Timeout.

## Eng begrenzte Reparatur

Der physische Decoder hat bereits kanonisches, duplikatfreies JSON vorliegen.
Er prüft jetzt die unveränderte geschlossene Beobachtungsspezifikation direkt:
kanonische Quell-/Empfangszeiten, erlaubte Typen, endliche Zahlen,
preisfreie verschachtelte JSON-Strukturen und Publikationskausalität. Dadurch
entfallen eine zweite vollständige Baumkopie und deren JSON-Serialisierung.

Unverändert bleiben die Inhalts-/Receipt-Hashes sowie **alle** physischen
Indexbindungen. Die öffentliche Normalisierung liefert weiterhin abgetrennte
Kopien. Es gibt keinen Cache, keine caller-supplied Validierungsflagge, keine
Auslassung von History-Zeilen und keine Lockerung der Modellfreigaben.

## Nachweise und Grenzen

- Ein isolierter, rein lesender VPS-Vergleich von 512 vorhandenen Receipts,
  fünf Wiederholungen: gleiche Decodierergebnisse; alter Decoder 0,6114 s,
  neue Fassung 0,4931 s, etwa 19 % weniger Decodierzeit.
- Neue Oracle-Tests vergleichen kanonische Normalisierung und den festen
  physischen Validator einschließlich nichtkanonischer Zeiten, verschachtelter
  Preisfelder, bool/number-Kanten, Publikationszeiten, geschlossener Schemas
  und sämtlicher Hash-/SQL-Indexänderungen.
- Fokus: 156 Tests bestanden. Breitere Source-/Worker-/Replay-Abnahme:
  **498 Tests in 204,15 s bestanden**, zwölf Module, externes Netzwerk gesperrt.
  Kein Vollsuite-PASS; unabhängiger Abschlussreview bleibt vor Veröffentlichung.
- Die Stichprobe beweist keine exakt entsprechende Gesamtbeschleunigung.
  Der vollständige nächste reguläre Tageslauf bleibt ein eigener Nachweis.
- Das Wachstum durch wiederholte Source-Inhalte ist eine zusätzliche Ursache;
  bestehende Daten wurden nicht gelöscht oder rückwirkend umgeschrieben.

Lokale Diagnostik außerhalb des Git-Repositories:
`C:/Projekt/BetBoy/output/day-timeout-20261011/probe.py`,
`compare_decoder.py`, `focused.xml` und `broad2.xml`.
