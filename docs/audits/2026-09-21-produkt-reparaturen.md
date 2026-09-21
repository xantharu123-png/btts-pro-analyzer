# Produktreparaturen nach dem Audit vom 21.09.2026

Ausgangspunkt: `1e2c6f5c19b8ba32d8a970c622109e049f8c4060` auf Arbeitskopie,
GitHub main und VPS. Auftrag: sämtliche Auditbefunde beheben; Cricket bleibt
ausgenommen. Keine echten Wetten buchen, Finanzhistorien verändern, Marktarten
pauschal verbieten oder unqualifizierte Kontexteffekte aktivieren.

## Umsetzung

| Befund | Änderung | Abnahme / verbleibende Grenze |
|---|---|---|
| F01 | Gemeinsamer Kohärenzfilter jetzt auch vor allen 15K-Anzeige-/Preissplits; Ticketpool an sichtbare kohärente Menge gebunden | Gegensätze Ergebnis Heim/Gast, Über/Unter sowie Heimsieg/X2 reproduziert und abgesichert. Vollständiger interner Modellkatalog unverändert. |
| F04 | Gemeinsame typisierte Ausfallanzeige; unbekannt, nicht abgedeckt, veraltet und bestätigte Null getrennt | Auch alte Analyseumschläge verlieren die negative Abdeckungsinformation nicht mehr. Keine erfundenen 0/0 oder Spielernamen. |
| F03 | Nur bereits begonnene E-Sport-Spiele fällig; faire Wiederprüfung nach letzter Prüfung beziehungsweise Erfassung; zusätzlicher Ergebnislauf im bestehenden 30-Minuten-Worker | Maximal 15 Ergebnisabrufe pro regulärem Lauf, keine neue Discovery oder Quotenabfrage. HTTP-/Payloadfehler separat. Keine DB-Schreibsperre während des nächsten Netzaufrufs. Reale Rückstandsabnahme nach Deployment gesondert prüfen. |
| F06 | Offizielles FT-Ergebnis derselben Fixture-/Teilnehmeridentität kann Terminänderungen auflösen | Originalprognosen unverändert. Tatsächlicher Start im Ergebnisbeleg. Später entstandene Prognosen/Quoten werden nicht als Prematch-Nachweis gezählt. Teilnehmerkonflikte bleiben abgelehnt. |
| F05 | Defensive Auswahl priorisiert unter geeigneten Kandidaten die niedrigste Wahrscheinlichkeit der drei Modellvarianten vor Formabstand/Vielfalt | CHF50, drei Slots und Preisuntergrenze unverändert. Nur Fußball hat einen qualifizierten Vergleichsadapter; andere Sportarten nicht künstlich freischalten. |
| F08 | 15K nach Spiel auf-/zuklappbar, irreführende Gesamtfreigabe entfernt; RisikoBet-Kontext in Analyse-Details | Modellgrundlage statt behauptetem Pro-Vorteil; Torvergleich, Belag oder Elo statt bloßer Wiederholung derselben Chance. Tennis-Namensdopplung entfernt. Neue Policy-/Adapterrevision verhindert Kollisionen mit eingefrorenen Alttexten. |
| F07 | Qualitätsbericht zählt Ereignisse sportweit getrennt von Modellrevisionen; Ergebniszufuhr repariert | Kein Nachweis eines Wettvorteils allein durch grüne Tests oder mehr abgerechnete Zeilen. |
| F02 | Echter Daten-/Artefaktbestand erneut geprüft; keine fiktive Aktivierung | Noch nicht erledigt, siehe unten. |

## Tatsächliche Kontextlücke, 21.09. gegen 11:03 CEST

Rein lesende Abfrage der kanonischen VPS-Datenbank, keine Referenzlisten
expandiert und keine Sport-API aufgerufen:

- Null `context-effect-v1`, `context-approval-v1` und `context-training-case-v1`.
- 1.653 Tennis-Winner-Kontextsnapshots aus 207 verschiedenen Ereignissen;
  alle `not_applied`. Keine Fußball-Kontextsnapshots.
- 521.760 ESPN-Belastungsbeobachtungen betreffen nur 1.589 unterschiedliche
  Ereignisse. Die Zahl der Zeilen ist keine unabhängige Trainingsstichprobe.
- Sämtliche Satz-/Spiel-/Minutenwerte der 1-/3-/7-Tagesfenster sowie exakte
  Erholungszeiten fehlen in diesen Snapshots. Vorhandene Vollständigkeitsflags
  und Mindestpausen sind nicht dasselbe wie gemessene vollständige Belastung.
- 4.164 ESPN-Ergebnisbeobachtungen betreffen 125 unterschiedliche Ereignisse.
  Damit sind bereits vor Feature-/Identitäts-/Trainingsprüfung weniger als die
  unverändert geforderten 200 unabhängigen unangetasteten Testevents vorhanden.
- Fußball: 866 Ereignisse mit Einsatzbeobachtungen, 502 mit Ausfallbeobachtungen,
  496 mit Aufstellungen und 1.077 mit Ergebnisbeobachtungen. Diese Rohabdeckung
  ist noch kein kausal verbundenes Trainings-/Testpaket des echten Live-Modells.

Der ESPN-Normalisierer (`context_sources/tennis.py`) besitzt keine belegten
tatsächlichen Start-/Endzeiten. `context_models/tennis.py` verwendet korrekt
keine Abrufuhrzeit als erfundene Match-Endzeit. Die Fußball-Originalaufzeichnung
ist ein Ausführungsnachweis, keine automatisch qualifizierte Replay-Version.
Eine numerische Freischaltung würde diese Lücken verdecken, nicht beheben.

Für F02/F07 und weitere Daily3-Sportarten weiterhin erforderlich: ausreichend
zeitlich belegte Ausgangsdaten, echte kompatible Ergebniszuordnung, nachweisbare
Basis-/Kontext-Replays, getrenntes Training/Tuning sowie unangetastete Testblöcke.
Kein neu erfundener Abschlag, kein Absenken der vorab festgelegten Prüfkriterien,
keine synthetischen Testdaten als reale Sportdaten. Keine Gesamtfertigmeldung.

## Verifikation und Veröffentlichung

- Neue Regressionen zuerst gegen die Fehler ausgeführt: Gegenmärkte,
  unbekannte Ausfälle, falsche defensive Priorität, verhungernde Ergebnisqueue,
  echte HTTP-429-Antwort, Netzaufruf unter SQLite-Schreibsperre sowie Upgrade mit
  Alt-Szenarien aus dem tatsächlichen Vorgängercommit. Danach gezielt grün.
- Abschließende betroffene Regression: **1.621 bestanden, 32 Untertests**,
  Exit 0 in 160,63 s. Enthält Daily3, 15K, Quoten-/Marktfilter, Kohärenz,
  RisikoBet, E-Sport, Prognose-/Ergebnisbelege und Wettfinder-Worker.
  XML: `output/playwright/product-repairs-20260921-final-focused-v2.xml`.
  Der vorherige Lauf hatte genau eine veraltete Erwartung (Formvorteil vor
  defensiver Priorität); sie wurde der ausdrücklich freigegebenen Priorität
  entsprechend geändert, nicht durch Absenken der Aufnahmebedingungen.
  Gesamtsuite läuft seit vor den letzten Nachbesserungen; sie ist ergänzende
  Regression, kein Einzelbeleg für einen unverändert getesteten finalen Stand.
- Lokale Browserprüfung mit ausdrücklich künstlichen Beispielen: 15K behält
  kompatible Auswahlen, gesamter Spielblock schließbar; RisikoBet-Beobachtungen
  nur im Detailbereich. RisikoBet und 15K bei 320 Pixeln ohne horizontalen
  Überlauf, Screenshots tatsächlich angesehen, keine Console-Errors.
  Produktionsprüfung folgt nach Deployment.
- Keine Root-Werkzeuge, systemd-Units, Dependencies, Schemata, Einsätze oder
  vorhandenen Backups geändert. Tages-/Updatearchive bleiben aus. Der alte
  Root-Updater würde Backups neu erzeugen; deshalb nur der bereits genehmigte,
  exakt commit-/dateibegrenzte Code-only-Ablauf unter dem bestehenden Lock.
- Commit, Push, VPS-Hash und native Ergebnisabnahme werden nach Ausführung
  ergänzt. Vorhandene fremde Audit-/Browser-/QA-Dateien bleiben unberührt.
