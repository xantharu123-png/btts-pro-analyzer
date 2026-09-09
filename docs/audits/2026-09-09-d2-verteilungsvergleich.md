# D2: vollständige Ergebnisverluste und gemeinsame Testkohorten

Stand: 9. September 2026. Controller-Arbeitsbasis
`1574044519b1c6c92a6b52c982af7562ffda9496`; vier neue reine CPU-/Testdateien.
Noch kein unabhängiges Abschlussreview dieses Pakets. Kein Push, Deployment,
Quellenabruf, echter Testdatensatz oder aktivierter Kontexteffekt durch dieses Paket.

## Enger Lieferumfang

`paired_distribution_losses` prüft die bestehenden B1-Event-/Base-Verträge und
den tatsächlichen nativen D1-Outcome-Record. Es berechnet selbst den Verlust
des beobachteten Ergebnisses unter Original- und Vergleichsparametern. Es
akzeptiert keine freien Ergebniswahrscheinlichkeiten, Logloss-Werte, Quoten
oder nachträglichen Epsilon-Regeln. Vollständige kausale Case-/Receipt-/Fit-
Auflösung und tatsächliche Wirkung gehören dem noch folgenden D1/D2-Evaluator.
Ein gültiger öffentlicher Inhaltshash allein beweist keine Quellenwahrheit.

| Familie | Tatsächlich bewertetes Ergebnis | Feste Policy |
| --- | --- | --- |
| Fußball | Exaktes gemeinsames Regulationstor-Ergebnis | `independent-poisson-exact-score-log-v1` |
| Tennis Winner | Native siegreiche Person | `native-winner-bernoulli-log-v1` |
| Tennis Serve | Finaler Match-Satzstand, nicht voller Punkt-/Spielpfad | `iidsets-holdproxy-tb7-match-set-score-log-v1` |

Fußball verwendet die vorhandenen unabhängigen Poisson-Raten und die bestehenden
zulässigen Ratengrenzen. Der bestehende Markt-Matrix-Tail in Zelle25 wird nicht
verändert; eine beobachtete26 wird für diesen ausdrücklich unbeschränkten
Log-PMF-Vertrag tatsächlich als26 bewertet. Tennis nutzt stabiles `log`/`log1p`.
Der Serve-Verlust summiert die Log-Satzwahrscheinlichkeiten mit dem gültigen
Kombinationsterm, bevor ein Produkt unterlaufen kann. Der bestehende strikte
IID-Set-/Hold-Proxy-/TB7-Simulator bleibt unverändert. Nullwahrscheinlichkeit des
tatsächlichen Ergebnisses ist ein typisierter Rechenfehler, kein Modell-Nulleffekt
und keine günstige Datenlücke. Es gibt keine geliehene Basketball-/Hockey-/
E-Sport-/Cricket-Verteilungsannahme.

`compare_registered_losses` ist ausschließlich die statistische Zusammenführung
eines strukturell validierten eingefrorenen Plans und bereits aufgelöster
Ergebniszeilen. Diese Funktion liest keine Quelle, kein Ergebnislabel aus einer
Datenbank, keine A1-Artefakte und veröffentlicht keine Freigabe. Ihre freien
Verlustinputs sind **kein** zulässiger Beweis am späteren CLI-/Approval-Eingang.

- Jede registrierte Hypothese benötigt genau einen expliziten Ergebniseintrag
  und Verteilungsverlusteintrag, auch bei leeren Tupeln. Fehlende/zusätzliche
  Hypothesen sind Fehler. Vorab fehlgeschlagene Varianten bleiben mit p=1 in BH.
- Vergleichbare Ready-Varianten haben dieselbe eingefrorene Sport-/Familien-/
  Population-/Coverage-/Basisversion-/Zielmarkt-/Outcome-Definition. Nur innerhalb
  dieser vorab bestimmten Gruppe wird die gemeinsame vollständige Eventmenge
  gebildet. Andere Populationen und vorab nicht berechenbare Varianten leeren
  die unterstützte Kohorte nicht.
- Jedes Ereignis benötigt sämtliche erklärten Zielmärkte und seinen einen
  Verteilungsverlust. Fehlende Ziele entfernen das ganze Ereignis aus allen
  vergleichbaren Ready-Varianten. Grund, erwartete, individuell vollständige
  und endgültige Eventanzahl bleiben nachvollziehbar.
- Alle Zeilen werden **vor** der Schnittmenge geprüft. Ein falscher Zeitpunkt,
  unbekanntes Event, falscher Block, doppelte Zeile oder manipulierte Policy
  verschwindet nicht als harmlose Abdeckungslücke. Überlappende Varianten dürfen
  weder Originalwahrscheinlichkeit/-Verlust noch den realisierten Marktausgang
  gegeneinander austauschen.
- Bestehende gepaarte Eventmittel, chronologische HAC-Reihenfolge, Blöcke,
  relative Verbesserung, Verteilungsdifferenz und alle Kalibrierungsprüfungen
  werden unverändert wiederverwendet. Einmal BH über **jede** registrierte
  Hypothese. Ein Basis-Kontrolllauf kann ausschließlich sich selbst vergleichen,
  bleibt deskriptiv und erhält niemals eine Kontextfreigabe.
- Ein nach Öffnung leerer Ready-Lauf wird nicht nachträglich `unsupported`.
  `empirical_approval_verified` ist in jedem Rückgabefall ausdrücklich `False`;
  auch gute künstliche Zahlen machen diese CPU-Funktion nicht zur Freigabestelle.

## Tatsächliche Tests

Die Testdaten sind ausdrücklich künstliche B1-Receipts bzw. freie synthetische
Verlustzeilen zur Prüfung der Rechenmechanik. Die 210 Zeilen der Statistikfixture
sind keine echten gehaltenen Tennis-Testspiele, und ihre freien Logloss-Werte
werden nicht als aus realen Modellparametern rekonstruiert bezeichnet.

- Distribution: erste29 Tests rot wegen fehlender API, dann29 grün; auf51
  permanente Tests erweitert. Gemeinsamer Lauf mit gepaarter Statistik,
  Validierung und nativen Outcomes:153 grün,2,82s.
- Registry-Kohorte:18 echte REDs wegen fehlendem `evaluation`-Modul, danach
  unverändert18 grün,1,49s. Weitere20 Fälle prüfen getrennte ATP/WTA-Kohorten,
  echte Basiskontrollen, fehlerhafte später ausgeschlossene Zeilen,
  Eingabereihenfolge und keine Speicher-/Approval-Schreibvorgänge.
- Gesamter Fokus:251 bestanden,6,71s;
  `.pytest_tmp/d2-score-registry-focus-20260909-01`.
- Vollsuite: **3954 bestanden,18 erwartete Windows-/POSIX-Skips,
  97 Untertests bestanden**,89,75s;
  `.pytest_tmp/context-d2-scoring-full-20260909-01`.

Die51+38 neuen Tests liefen vollständig. Unabhängiges Review folgt getrennt.

## Eingefrorene Implementierungsbytes

| Datei | SHA-256 |
| --- | --- |
| `context_models/distribution_losses.py` | `d70ccbf430bf553f77579010a7c76de8d2317c6b12ec32b36a4c93e9f885f950` |
| `context_models/evaluation.py` | `20e602e6256e7806928b83f8bc7292dccf72e8a829f8d462bf5ad57373f725a0` |
| `tests/test_context_distribution_losses.py` | `e9d2f288eada2cf43e8340a5631bef48dbef204cb3627214b2d245d08f99f44b` |
| `tests/test_context_registered_metrics.py` | `155496751f7e946287d79545974b64e8c07a84400b1fc8cda539f40ec89ed4cd` |

Der privilegierte unveränderte Backuphelfer behält
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.
Kein Geld-/Ticket-/15K-/Settlement-/Cricket- oder UI-Verhalten geändert.

## Weiterhin offen

Vollständiger owning `evaluate_experiment`-Eingang mit gebundener D1-Dataset-/
Case-/Fit-Provenienz und Verlustneuberechnung; persistierte vollständige Reports,
verifizierter `approved_effect`-Resolver und CLI; gelabelte reale Korpora mit
mindestens200 zulässigen Events, drei konsekutiven Blöcken und sämtlichen
unveränderten Qualitätsanforderungen; D3-Worker-/D4-Provenienz-Verbindung und
separate Produktionsprüfung. Tests oder eine lesbare Statistik schließen keine
dieser offenen Aufgaben stillschweigend.
