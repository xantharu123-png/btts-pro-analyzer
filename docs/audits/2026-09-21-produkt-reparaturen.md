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
| F03 | Nur bereits begonnene, anhand eingefrorener Team-IDs zuordenbare E-Sport-Spiele fällig; faire Wiederprüfung nach letzter Prüfung beziehungsweise Erfassung; zusätzlicher Ergebnislauf im bestehenden 30-Minuten-Worker | Maximal 15 Ergebnisabrufe pro regulärem Lauf, keine neue Discovery oder Quotenabfrage. HTTP-/Payloadfehler separat. Keine DB-Schreibsperre während des nächsten Netzaufrufs. Alte fehlende Identitäten unverändert erhalten, nicht nachträglich erfinden. |
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
- Zwischenabnahme der betroffenen Regression: **1.621 bestanden, 32 Untertests**,
  Exit 0 in 160,63 s. Enthält Daily3, 15K, Quoten-/Marktfilter, Kohärenz,
  RisikoBet, E-Sport, Prognose-/Ergebnisbelege und Wettfinder-Worker.
  XML: `output/playwright/product-repairs-20260921-final-focused-v2.xml`.
  Der vorherige Lauf hatte genau eine veraltete Erwartung (Formvorteil vor
  defensiver Priorität); sie wurde der ausdrücklich freigegebenen Priorität
  entsprechend geändert, nicht durch Absenken der Aufnahmebedingungen.
  Gesamtsuite: **10.811 bestanden, 96 Skips, 111 Untertests, sieben Fehler**,
  2.328,47 s. Der Lauf startete vor den letzten Nachbesserungen. Die sieben
  Fehler waren die alte Daily3-Reihenfolge und sechs historische Tennis-
  Erklärungserwartungen. Der eingefrorene Tennis-Oracle bleibt unverändert;
  ausschließlich neue Adapterrevision, neuer Grundlagentext und entfernte
  doppelte Spielernamen werden exakt erwartet. Alle Modellwerte, Märkte,
  übrigen Felder und unveränderte Quelldaten werden weiter voll verglichen.
  Beide betroffenen Dateien plus neue Queuefälle: **74 Tests bestanden**.
  Queue-/Worker-/Upgrade-Gegenprüfung: **189 Tests bestanden**. Runden
  überlappen, nicht addieren. Abschließende verbreiterte Regression des finalen
  Codestands: **1.676 Tests und 32 Untertests bestanden**, Exit 0, 128,25 s;
  `output/playwright/product-repairs-20260921-final-focused-v3.xml`.
  Zusätzlich nach dem Queue-Nachtrag: zwölf E-Sport-Kontexttransporttests grün.
- Lokale Browserprüfung mit ausdrücklich künstlichen Beispielen: 15K behält
  kompatible Auswahlen, gesamter Spielblock schließbar; RisikoBet-Beobachtungen
  nur im Detailbereich. RisikoBet und 15K bei 320 Pixeln ohne horizontalen
  Überlauf, Screenshots tatsächlich angesehen, keine Console-Errors.
  Auf der echten Website nach Deployment: 15K-Spielblock schließbar,
  "nicht abgedeckt" statt 0/0, 320 Pixel Seitenbreite ohne Überlauf;
  kein Browserfehler. Neun Framework-/Iframe-Warnungen bleiben getrennt
  dokumentiert, nicht als "keine Warnungen" melden.
- Keine Root-Werkzeuge, systemd-Units, Dependencies, Schemata, Einsätze oder
  vorhandenen Backups geändert. Tages-/Updatearchive bleiben aus. Der alte
  Root-Updater würde Backups neu erzeugen; deshalb nur der bereits genehmigte,
  exakt commit-/dateibegrenzte Code-only-Ablauf unter dem bestehenden Lock.
- Hauptreparatur `d6fff683a57f6f5e510f8119eabf714888e445a1` auf lokalem main,
  GitHub und VPS ausgeliefert. App nach Code-only-Update gesund, sechs
  Rechentimer wieder aktiv; Retention unverändert, Tagesbackup disabled.
- Die erste native Ergebnisprobe überprüfte 15 Zeilen, alle blieben offen.
  Drei zusätzliche reine Diagnoseabrufe bestätigten echte Endresultate,
  aber fehlende eingefrorene Team-IDs. Bestandsprüfung: **305 solcher Altzeilen,
  208 offene Zeilen mit beiden IDs**. Kein Löschen, keine nachträgliche
  Identitätserfindung, kein Umschreiben alter Wahrscheinlichkeiten. Der
  Nachtrag nimmt diese unmöglich zuordenbaren Fälle aus dem Abrufbudget und
  zählt sie separat. Nachtrag **8543fcce91374ed15547380e36b587bd77d98cab**
  auf lokalem main, GitHub main und VPS bestätigt. Zweite native Probe:
  **15 geprüft, 15 echte Endresultate übernommen, null API-/Abruffehler**.
  Offen 513 -> 498, abgeschlossen 138 -> 153. Vollständige ursprüngliche
  Prognosefelder aller Zeilen per SHA-256 unverändert; zusätzlich sämtliche
  Felder der 305 Altzeilen unverändert. Keine Konten/Tickets abgerechnet.
  Beleg: `output/playwright/product-repairs-20260921-native-esports-v2.log`.
- Regulärer Wettfinder-Folgelauf ab **11:37:04 CEST** unter dem neuen Code:
  um **11:49:41** noch aktiv rechnend, 745,66 CPU-Sekunden. Kein Abbruch,
  kein manueller Zweitlauf, kein als Erfolg umgedeuteter Zwischenstatus.
  Die letzte abgeschlossene Veröffentlichung bleibt vorläufig 11:07; darin
  stehen noch die alten RisikoBet-Begründungen. Darstellungscode ist live,
  neue gespeicherte Erklärungsversion erst nach echter Veröffentlichung
  abnehmen. Diesen laufenden Datenjob beim nächsten Einstieg zuerst prüfen.
  Ein kompletter erfolgreicher Tennis-Tageslauf nach dem früheren Retirement-
  Fix ist ebenfalls weiterhin nicht nachgewiesen; alten Exit 1 nicht löschen.
- Vorhandene fremde Audit-/Browser-/QA-Dateien bleiben unberührt.
