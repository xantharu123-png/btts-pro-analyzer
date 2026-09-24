# BetBoy – aktuelle To-dos und Account-Übergabe

## 24.09.2026 – Tippfindung ohne Buchmacherpreise

- Wettfinder (automatisch und eigene Suche), RisikoBet, Daily3 und aktive
  Sportansichten sollen Prognosen ausschließlich nach Modell- und Datenlage
  auswählen. Fehlende, veraltete oder niedrige Buchmacherquoten ändern weder
  Sichtbarkeit noch Reihenfolge; Preisbestätigung und Value-Grenze verschwinden
  aus diesen Tippkarten.
- Die feste Nutzer-Mindestquote 1,20 bleibt für eine tatsächlich erfasste
  Daily3-Wette bestehen. Historische Echtgeldquoten und Auszahlungen werden
  nicht verändert.
- Ausnahme bis zur gesonderten Produktentscheidung: Der automatische
  15K-Ticketpfad benötigt Ausführungsquoten für reale Einsätze und Abrechnung.
  Seine Quote wird nicht zur Sortierung des normalen Wettfinders verwendet.
- Alte E-Sport-/Teamsport-Preis-Caches werden vom normalen Prognoseleser nicht
  mehr geladen; deren automatischer Quotenrefresh ist deaktiviert. Historische
  Preisadapter bleiben für bestehende Daten und separate Prüffunktionen erhalten.
- Code-, GitHub- und VPS-Stand bei einer Übergabe getrennt anhand der Hashes
  prüfen; ein grüner Test allein belegt kein Deployment oder bessere Treffer.

## 24.09.2026 – Wettentscheidung liegt beim Nutzer

- Wettfinder, eigene Suche, Daily3 und Sportansichten bezeichnen Modell- und
  Quotenstatus als Informationen, nicht als Erlaubnis zum Wetten. Eine fehlende
  oder niedrige Quote verändert die Prognose nicht und blendet sie nicht aus.
- Interne Kriterien für optionale Einsatzvorschläge und die bestehende
  TipStore-Speicherung bleiben unverändert. Das ist eine Funktionsgrenze der
  App, keine Entscheidung über extern platzierte Wetten.
- Keine Modellwahrscheinlichkeiten, Preisgrenzen oder CHF-50-Budgetregeln
  geändert.

## 24.09.2026 – Wetter, Form, Ausfälle und Tennis-Belag

- Tennis: Das bestehende Elo nutzt bei mindestens acht Belagspielen **je Spieler**
  den Belaganteil (65 %) plus Gesamt-Elo (35 %). Der Tageslauf speichert jetzt
  beide tatsächlichen Belag-Elo-Werte, Stichproben und den Datenstand neben
  der unveränderten Prognose. Wettfinder/Daily3, Tennis und RisikoBet zeigen
  den Beleg kompakt; bei zu kleiner Stichprobe steht ausdrücklich
  „Gesamt-Elo verwendet“. Alte Prognosen erhalten keine nacherfundenen Werte.
  Historische Replay-Quellen tennis/predict.py und tennis/elo.py bleiben
  unverändert; 680 betroffene Integrations-/Replaytests bestanden, danach
  113 Speicher-/Anzeige-/Adaptertests nach der letzten Eingabegrenze.
- Fußball-Form wirkt schon als 25-%-Anteil der erwarteten Tore; Tennis
  verarbeitet jüngste Ergebnisse chronologisch im Elo, E-Sport jüngste
  Serien im Elo. Keine zusätzliche willkürliche Formkorrektur.
- Ausfälle/Wetter: Der Fußball-Kontext zeigt verifizierte Daten und kann
  extreme Gegenindikatoren prüfen, ändert aber die Modellchance **nicht**
  numerisch. Auch Tennis-Belastung/Verletzung ist kein freigegebener
  Wahrscheinlichkeitszu-/abschlag. Das ist in der UI als Grenze kenntlich.
- Produktionsinventur (rein lesend): 0 B1-Wetterbelege und 0 veröffentlichte
  Effektfreigaben. Vor numerischer Aktivierung fehlen echte, rechtzeitig
  erfasste Wetter-/Kaderbelege und eine unabhängige, zeitlich getrennte
  Qualitätsprüfung. Keine Wetterwirkung oder Gewinnverbesserung behaupten.
  Clay/Grass und WTA-Tipps bleiben von ihrer separaten Modellvalidierung
  abhängig; die Belag-Anzeige ist keine Freigabe.
- Keine neuen API-Läufe, Sicherungen, Datenbankmigrationen oder
  Quoten-/Wahrscheinlichkeitsänderungen für diesen Schritt.

## Form-Audit 23.09.2026

- Fußball, Tennis und E-Sport verwenden jüngste bekannte Ergebnisse bereits numerisch; keine zweite willkürliche Formkorrektur aufschlagen.
- Basketball: im produktiven Ergebnisspeicher aktuell keine verwertbaren Zeilen. Form erst mit kausaler Historie und unabhängigem Test.
- NHL: 1.535 gespeicherte Ergebnisse, davon nur 7 Spielstarts in den letzten 30 Tagen. Alte Saisonwerte nicht als aktuelle Form ausgeben; Forschungsversion erst bei ausreichender aktueller Stichprobe prüfen.
- Cricket: kein gespeicherter Ergebnisbestand; letzter Quellenversuch fehlgeschlagen. Keine Form erfinden.
- E-Sport: Die fünf zuletzt im Elo verwendeten Serien werden ab neuen Shadow-Einträgen zeitlich gebunden mitgespeichert und im RisikoBet offen angezeigt. Alte Einträge bleiben ohne nachträglich erfundene Form.
- Details: docs/audits/2026-09-23-sportarten-form.md. Betroffene Modell-/UI-Gruppen: 236 Tests bestanden; die lang laufende Vollsuite wurde nicht abgeschlossen. Kein Nachweis besserer Wettqualität.

## Fortsetzung 23.09.2026 – Code live, fachliche Abnahme offen

- GitHub `main` und VPS stehen auf `f5c0971c0bc3a09017b70b259f6b875efeeb149a`.
  Der VPS wurde ohne Datenmigration und ohne neues Backup-Archiv per
  Code-Fast-Forward aktualisiert. App/Caddy-Healthcheck `ok`, sieben
  Rechentimer aktiv, täglicher Backup-Timer weiter deaktiviert.
- Regression: vor einem fehlerhaften E-Sport-Test-Doppelgänger 6.999 Tests
  bestanden; nach Korrektur ausschließlich dieser Testdatei alle restlichen
  Module mit 4.061 bestandenen Tests abgeschlossen. Der echte E-Sport-
  Konstruktor war korrekt; zwei `__new__`-Tests brauchten `errors = {}`.
  Der reine Test-Fix gehört zu diesem Abschlussnachtrag.
- Automatischer Wettfinderlauf 01:37–01:44 CEST auf dem neuen Commit:
  `completed`, null technische Fehler. Die RisikoBet-ID-Wiederverwendung
  ist als Abdeckungsdiagnose sichtbar, 229 Kandidaten blieben offen und
  keine Wette wurde irrtümlich abgerechnet.
- Einmaliger regulärer Tennis-Tageslauf 01:44–02:01 CEST: Exit 0, Scan und
  Pipeline OK, 41 neue Prognosen. ESPN-WTA 183992 steht ausdrücklich als
  `partial`/nicht auswertbare alte Paarung, null technische Capture-Issues.
  Der Wettfinder-Timer wurde für den speicherintensiven Scan kurz angehalten,
  danach wieder aktiviert; die einmalige Rückfall-Sicherung ist entfernt.
  Der nächste automatische Wettfinderlauf um 02:07 CEST prüfte die inzwischen
  neu gespeicherten Tennis-Endergebnisse erfolgreich.
- Automatische Gegenprobe 02:07–02:13 CEST: `completed`, null technische
  Fehler, **29 andere RisikoBet-Kandidaten terminal abgerechnet**. Die neun
  Snapshots der wiederverwendeten Tennis-Event-ID haben weiterhin null
  terminale Abrechnungen. Der frühere Nullwert war vom Datenzeitpunkt
  abhängig, keine dauerhafte Blockade aller anderen Fälle.
- Rein lesende neue Tennis-Inventur nach dem Scan: 296 eindeutige rechtzeitige
  ORIGINAL-Events, davon 222 mit exakt passendem normalem Finale (+59 zum
  vorherigen Stand). Das sind 222 insgesamt, **nicht** 200 unangetastete
  Testspiele zusätzlich zu Training/Tuning. Effektfreigabe weiter offen.

- Maßgeblich: [Prüfbericht 22.09.](docs/audits/2026-09-22-kontext-daily3-status.md).
  Ausgangsstand lokal/GitHub/VPS `c784195`; App, Caddy und Timer aktiv,
  lokaler Healthcheck `ok`, rund 20 GB VPS-Speicher frei. Kein automatischer
  Code-Pull durch die Timer. Nutzerwunsch: keine neuen Tages- oder Updatearchive.
- Nach dem erfolgreichen Lauf vom 21.09. scheiterten am 22.09. der Tennis-
  Tagesdienst (74 verarbeitet, 13 neu gespeichert, Exit 1) und der Wettfinder
  (Fußball selbst fehlerfrei, Gesamt-Exit 1 wegen RisikoBet-Abrechnung).
- Tennis-Ursache: WTA 183992 wechselte nativ die Teilnehmer; eine neue
  Prognose erschien erst nach dem vorverlegten Beginn. Der veröffentlichte enge Fix
  klassifiziert nur eine exakt bestätigte Ersatzpaarung als sichtbare
  Nichtauswertbarkeit der alten Prognose. Kein fremdes Ergebnis, keine
  Geld- oder Settlementmutation. 300 gemeinsame Tennis-/Fußball-Regressionen
  bestanden; die produktive Nachprüfung läuft noch.
- RisikoBet: ESPN 183996 enthält alte und neue Spielerpaarung unter einer
  Event-ID. Der veröffentlichte Fix isoliert genau die nachweislich wiederverwendete
  Tennis-ID ereignisbezogen; beide Paarungen bleiben unabgerechnet, andere
  Spiele können weiterlaufen. Die Produktionsdaten bestätigen sieben alte
  und zwei neue Snapshots. 234 RisikoBet-Tests bestanden. Für eine sichere
  Abrechnung der neuen Paarung benötigen Ergebnisrouter **und Kandidaten-ID-/
  Terminal-Store-Vertrag** einen revisionsgebundenen
  Inkarnationsschlüssel und einen dauerhaft gebundenen Provider-Finalbeleg,
  bevor einzelne Szenarien dieser Event-ID gefahrlos abgerechnet werden.
  Im beobachteten alten Lauf: 227 fällige Kandidaten offen, null abgerechnet.
- Neuer reiner Fußball-ORIGINAL-v2-Settlementvergleich lokal getestet;
  weder Projektions-/Code-Replay noch empirische Wirkung freigegeben.
  Tennis vor dem neuen Scan: 163 eindeutig passende Finale bei 256
  rechtzeitigen Originalevents; aktueller Stand oben. WTA
  historisch negativ; Basketball/Eishockey/E-Sport ohne qualifizierte
  Same-Market-Variante für Daily3. Cricket bleibt ausgenommen.
- **Noch nicht behaupten:** erfolgreicher neuer Tennis-Gesamtlauf,
  abgeschlossene RisikoBet-Inkarnationsabrechnung oder belegte bessere
  Wettqualität. Diese Punkte erst nach gesondertem Nachweis abhaken.

## Kontext-/Daily3-Fortsetzung 21.09.2026 — 3201537 live, fachliche Abnahme offen

- Maßgeblich: [Kontext-/Daily3-Bericht](docs/audits/2026-09-21-kontext-daily3-fortsetzung.md).
- Der unten noch offene 11:37-Lauf ist erfolgreich beendet. Neue RisikoBet-
  Begründungen sind veröffentlicht, keine technische Störung dieses Laufs.
- ATP-Daily3-Vergleich aus dem tatsächlichen Modellstand implementiert;
  vollständiger Speicher-/Signalanschluss getestet, keine Preissteuerung.
- Tennis-v4: korrekt begrenzte Belastungsfenster, stabile Erholungs-Untergrenzen,
  kompakte vollständig revisionsgebundene Spielersnapshots. Kein Effekt
  automatisch aktiviert; alte v3-Snapshots bleiben unverändert reproduzierbar.
- Erste native Messung: 205 rechtzeitige unabhängige erste Originalevents, 125
  passende Endresultate vor jeglicher Train-/Tune-/Testtrennung. Null
  qualifizierte Effektartefakte. Sechs zeitlich verteilte Fälle weiterhin
  ohne vollständige Belastungsfenster; Mindestpausen messbar, nicht exakt.
- Abschlussregression: 2.585 bestanden, 15 erwartete Skips, 26 Untertests;
  zusätzlich 115 Fußballtests grün. Keine finale Vollsuite daraus behaupten.
- Fußball-Speicherbudget: vollständige unveränderte historische FT-Bündel
  werden mit alten Uhren wiederverwendet. Korrekturen bleiben eigene Belege;
  Folgeläufe können fehlende Quellen ergänzen, ohne Limits zu erhöhen.
- `c9363109c44d3560717353c624130574fc592d43` wurde auf main/GitHub/VPS
  veröffentlicht und ist im späteren Stand enthalten. Keine neue Sicherung,
  Bereinigung oder Datenmigration.
- Echte Tennisprüfung 13:51–14:08 CEST: Scan 951 Sekunden statt altem
  2100-Sekunden-Timeout; 82 gespeicherte v4-Revisionen, 16 ATP-Vergleiche.
  Exit dennoch 1: ESPN ersetzte bei WTA 183996 Julia Avdeeva durch Ayla Aksu.
  Alte Prognose nicht überschrieben. Generische unveränderliche Nachfolgelinie
  mit exakter Ergebnisbindung lokal fertig: 1.461 Tests bestanden, drei Skips;
  danach 92 überlappende UI-/Fixturetests grün. Die spätere Live-Abnahme ist
  unten mit dem tatsächlich erfolgreichen 15:05-Lauf dokumentiert.
- Regulärer Lauf 14:07–14:26 CEST: Fußball abgeschlossen, insgesamt degraded.
  Drei Tennis-Refreshfehler; zwei nativ belegte offene Teilnehmerplätze
  (IDs 1588/1573), 1562 beim späteren lesenden Bindungstest wieder gültig.
  Kein erfolgreicher Gesamtlauf oder erfundener Teilnehmer behaupten.
- Nachtrag `30f31ed1944c6c7e879fc30224377b9548a527ab` auf main/GitHub/VPS.
  Echter Tennislauf 14:50:33–15:05:20 CEST: Exit 0, Scan OK, Gesamt OK;
  86 fertig verarbeitete Prognosen. Neue WTA-Linie 1637 korrekt mit 1585
  verknüpft; ausschließlich Ayla Aksu/Yuki Naito aktiv. Altdaten unverändert.
- Zusätzlicher Anzeigeschutz: bekannte Rücknahmen, offene Teilnehmerplätze,
  Starts und geänderte Termine werden in Wettfinder/RisikoBet/Tennis gemeinsam
  geprüft. Historie und manuelle Abrechnung bleiben getrennt zugänglich.
  Finale 55 betroffene Module: 1.897 bestanden, drei Skips, 26 Untertests.
  Dieser Anzeigeschutz ist als `ebfb69d85b2ff1aa1660c0e860a7a840d1617488`
  auf main/GitHub/VPS. Native Leserprobe 15:22 CEST: 1585/1588/1573 nicht
  aktuell sichtbar, korrekte neue WTA-Linie 1637 vorhanden. Historie erhalten.
- Statusnachtrag `3201537565a50f15daa96f5a4d049b8ca708d4d3` auf main/GitHub/VPS:
  bestätigte spätere Teilnehmer-/Statusänderungen sind getrennte Teildaten,
  kein pauschaler Programmfehler. Fehlende Originalbelege, beschädigte Quellen,
  fremde Wettbewerbe und gleichzeitige Widersprüche bleiben echte Fehler.
  **1.908 Tests, drei erwartete Skips, 26 Untertests** im betroffenen Abschlusslauf;
  keine gesamte App-Vollsuite und keine empirische Modellfreigabe behaupten.
  Rein lesende native Probe 15:36 CEST: 1588 `participants_changed`, 1573
  `participants_unconfirmed`; keine Neuberechnung oder Datenbankmutation.
  Regulärer Lauf **15:37:05–15:43:08 CEST, Exit 0**, `completed`, null technische
  Fehler. Fußball 25 Modellkarten, E-Sport sechs; Tennis null aktuelle Karten,
  zwei ausdrücklich gemeldete nicht berechenbare Paarungen, keine Refreshfehler.
  Keine zusätzliche Ausführung erzwungen. Vorheriger 15:07-Lauf war degraded.
- Lesende Zählung 15:13 CEST: 244 rechtzeitige unabhängige Originalevents,
  144 passende normale Endresultate insgesamt vor Train-/Tune-/Testteilung;
  weiterhin null Effekt- und Freigabeartefakte. Die frühere 125er-Zahl ist Historie.
- Weiter offen: echte empirische Wirkung, Fußball-Live-Jointmodell-Anbindung,
  WTA-/Basketball-/Eishockey-/E-Sport-Daily3-Vergleiche. Cricket ausgenommen.
  Fehlende Daten nicht durch erfundene Werte oder rückdatierte Belege ersetzen.

## Produkt-Auditreparatur 21.09.2026 — 8543fcc live

- F01/F04: 15K-Kohärenz und typisierte Ausfallanzeigen repariert; keine
  Gegensätze als gemeinsame Vorschläge, keine unbekannten Daten als 0/0.
- F03/F06: faire E-Sport-Ergebnisqueue, begrenzter Halb-Stunden-Ergebnislauf,
  echte Providerfehler getrennt, keine Schreibsperre beim Netzaufruf;
  verifizierte Fußball-Terminänderungen mit FT-Endergebnis auflösbar.
- Native Zusatzursache: 305 alte E-Sport-Zeilen ohne gespeicherte Team-IDs
  dürfen kein Abrufbudget blockieren. Sie bleiben unverändert erhalten;
  Queue-Nachtrag 8543fcc auf main/GitHub/VPS. Native zweite Probe:
  15 von 15 Endresultaten korrekt zugeordnet, null Providerfehler, alle
  ursprünglichen Prognosen und vollständigen Altzeilen unverändert.
- F05/F08: Defensive Daily3-Priorität korrigiert, 15K-Spielgruppen,
  kompaktere RisikoBet-Details und revisionssichere Modellgrundlagen.
- Abschließende betroffene Regression: 1.676 Tests und 32 Untertests grün;
  lokale Desktop-/320-Pixel-Browserprobe grün. Hauptreparatur d6fff68 plus
  Nachtrag 8543fcc auf main/GitHub/VPS. Gesamtsuite 10.811 bestanden/96 Skips/111 Untertests;
  sieben alte Text-/Reihenfolge-Erwartungen im Nachlauf exakt angepasst und
  grün. Keine einzelne komplett grüne finale Vollsuite behaupten.
  Maßgeblicher aktueller Reparaturbericht:
  [Produktreparaturen](docs/audits/2026-09-21-produkt-reparaturen.md).
- Zuerst den regulären Lauf ab 11:37:04 prüfen: um 11:49:41 aktiv rechnend,
  noch keine neue Veröffentlichung. Alte RisikoBet-Begründungen bis dahin
  noch aus dem 11:07-Datensatz. Kein neuer erfolgreicher Tennis-Tageslauf
  behauptet. Keine bereits erledigten Tests/Deploys/Bereinigungen wiederholen.
- Weiter offen: qualifizierte numerische Verletzungs-/Müdigkeitswirkung,
  echte empirische Verbesserung und Daily3-Vergleiche außerhalb Fußball.
  Keine Aktivierung ohne Datenbeleg. Cricket unverändert ausgenommen.

## Aktueller Stand – Fußball/Tennis, 21.09.2026

- **Nachtrag 08:24 CEST:** Die vier vom Nutzer freigegebenen historischen
  Tennisfälle sind aus aktiver Ergebnisaufnahme, Refresh und Abrechnung entfernt.
  Funktionscommit **`66b0a727ab0772e8137b0eb21063712c46c30192`** auf Worktree,
  lokalem main, GitHub main und VPS bestätigt. Vier Elternzeilen, 30 Originale
  und 22 Revisionen unverändert; keine Geldbuchungen geändert. Keine physische
  Löschung, Rücknahme des exakt begrenzten Katalogs stellt Verarbeitung wieder her.
  [Abnahmebericht](docs/audits/2026-09-21-tennis-altfaelle.md).
- Frische betroffene Regression: **1.988 bestanden, 3 Plattform-Skips,
  26 Untertests**. Danach ergänzter Fremdprognosen-Test in gezielter 16er-Runde
  grün (überlappende Zählung, nicht addieren). Native Vorher-/Nachherprobe mit
  540 Wettbewerben: bisherige Zuordnungsfehler beseitigt, 236 übrige Ergebnis-
  zuordnungen identisch. Nach Deployment Originalbelege erneut validiert,
  Eltern-Fingerabdruck unverändert, keine DB-Schreiboperation durch die Probe.
- Regulärer Wettfinder **08:07:29–08:15:29 CEST, Exit 0**: `completed`, keine
  technischen oder Fußball-Aktualisierungsfehler. Fußball-Kontingentengpass damit
  im Nachhollauf erledigt. Tennis 359 geprüft, **0 fällig**; dies bestätigt nicht
  die Behebung der separaten parallelen Abschlussausnahme. Kein zusätzlicher
  Tennis-Gesamtlauf nach Entfernung, alten Exit-1-Status nicht zurückgesetzt.
- App, Caddy und sieben Timer aktiv, beide Healthchecks `ok`; Tagesbackup bleibt
  aus. Keine Bereinigung, neuen Backups, Schema- oder Geldregeländerung.
  Verletzungs-/Müdigkeitsqualifikation und bessere Wettqualität bleiben offen.

### Historie vor der inzwischen freigegebenen Entfernung

Die unten angefragte Nutzerentscheidung liegt inzwischen vor; Umsetzung und
Abnahme siehe oben. Diese früheren Zwischenstände nicht als aktuell ausgeben.

- Funktionsstand **`7c805aeae0df6b85e68178adc7f40756cf99a06f`** auf Worktree,
  lokalem main, GitHub main und seit 00:17 CEST auf VPS. Vorige Reparaturen
  `e292b10`, `eea0703`, `f6b7c66` und der E-Sport-Anschluss sind enthalten.
  [Bericht und Reproduktionen](docs/audits/2026-09-20-football-tennis-refresh.md).
- Behoben: ursprüngliche 16 Fußball-Historienfehler, acht native Tennis-
  Terminänderungen, WTA-Import einer leeren Ergebnis-Platzhalterzeile,
  wiederholte Historienprüfungen und Wiederverwendung oberhalb 500.000 Verweisen.
  WTA-Ergebnisse reichen wieder bis 20.09. statt 12.09.
- Neue Korrektur: bekannte fremde Spielarten und explizite TBD-Turnierplätze
  verursachen keinen falschen Aufnahmefehler. Sie werden weiter unverändert
  als nicht modellierbar gespeichert. Native Gegenprobe mit 500 Wettbewerben:
  identische Beobachtungen/Abrechnungsquellen, alte Falschmeldung beseitigt.
- **Vollständige Testsuite: 10.773 bestanden, 96 plattformbedingte Skips,
  111 Untertests bestanden**, Exit 0, 33:33 min. Neun reine JUnit-Formatwarnungen.
  XML: `output/playwright/tennis-refresh-20260921-final-junit.xml`.
- Echter Tennis-Gesamtlauf 00:17:10–00:50:26: Modellaufbau, alle **74/74**
  Berechnungen, Montags-Kalibrierungsprüfung und Wochenreport abgeschlossen.
  Kein Timeout. 74 neue Prognose-Originale, **0 neue Shadow-Prediction-Zeilen**
  (die Spiele waren bereits vorhanden), nicht 74 neue Tipps.
- **Noch nicht grün:** Ergebnisaufnahme meldet zwei Konflikte und zwei nicht
  zuordenbare Altfälle wegen geänderter Teilnehmer: WTA 183831, 183854,
  183710, 183844. Der Gesamtlauf bleibt daher Exit 1. Read-only Gegenprobe
  mit 540 nativen Wettbewerben bestätigt exakt diese vier Fälle; 118 Events
  bekommen passende Ergebnisbeobachtungen. Keine alten Originale umschreiben,
  fremde Gewinner zuordnen oder einen Fehlerstatus nur zurücksetzen.
- Nutzerentscheidung angefragt: diese vier alten Prognosen unverändert als
  „nicht auswertbar – Teilnehmer geändert“ separat führen statt jeden neuen
  Tageslauf daran scheitern zu lassen. Noch keine entsprechende Vertrags- oder
  Statusänderung implementiert; keine Gewinne/Verluste automatisch ändern.
- Zusätzliche Nachprüfung: der parallele Wettfinderlauf 00:37–00:56:30 meldete
  beim Tennis-Refresh erneut `ContextIntegrityError`. Der bestehende Catch
  speicherte nur den Typ, keinen Fehlerort; damit noch keine genaue Ursache
  bewiesen. Diagnosecommit `e8f0faf` ergänzt begrenzte Codepositionen/Fehlerketten
  nur im Serverlog (keine Meldungstexte/Secrets in Log oder Nutzerartefakt),
  auf main/GitHub/VPS. 147 betroffene Regressionstests grün; Vollsuite oben
  gehört zu `7c805ae`. Read-only Gegenprobe mit vollständiger physischer
  Historie und 651.445 WTA-Verweisen: eine aktuelle Prognose in 487 s bis vor
  Veröffentlichung vollständig vorbereitet. Kein reproduzierter Integritäts-
  fehler; Ursache des parallelen Fehlversuchs noch offen. Diesen neuen Befund
  nicht mit den vier historischen Ergebnisfällen gleichsetzen.
- Folgelauf 01:07:04–01:16:07: Tennis ohne Fehler, aber **0 fällige Refreshes**,
  somit keine erneute Abschluss-/Race-Abnahme. Zwölf Fußball-API-Reservefehler.
- Separater Fußball-Engpass: 00:07–00:16 CEST 13 Abrufe an der API-Reserve
  gestoppt (Restschätzung 2.443, Background-Reserve 2.500). Keine Rückkehr der
  alten Identitätsfehler. Direktes Tageskontingent erneuert 02:00 CEST;
  Wiederholpfad/Timer vorhanden, regulär 02:07. Erfolgreichen Nachhollauf noch
  prüfen. Reserve und Tarif unverändert lassen.
- App/Healthchecks funktionieren, sieben Timer aktiv, tägliche Sicherung
  weiterhin deaktiviert. Keine Bereinigung, neuen Backups, Quoten-/Geldregel-
  oder UI-Änderungen. Verletzungs-/Müdigkeitswirkung und bessere Wettqualität
  sind dadurch weiterhin nicht empirisch nachgewiesen.
- Die älteren Statusblöcke darunter sind Historie, keine aktuelle Gesamtabnahme.

## E-Sport-Quoten – Anbindung 20.09.2026

- OddsPapi-Schlüssel geschützt übergeben; native Kontoprüfung: aktiver kostenloser
  Tarif, 250 Anfragen, keine automatische Verlängerung. Erste echte CS2-Preise
  von identifizierten Buchmachern bestätigt, keine Modellquote als Anbieterpreis.
- Gemeinsamer Serien-Sieg-Cache für CS2, Dota 2, LoL und Valorant implementiert:
  Wettfinder, Daily3 und RisikoBet benutzen dieselben Preise. Exakte Disziplin,
  Teams, Spielbeginn, PandaScore-Ursprung und Marktbindung; keine Map-Übernahme.
- Beste passende Quote unter 1,20 entfernt nur den Vorschlag, nicht das Modell.
  Fehlende Angebote bleiben unbekannt. Abrufbeobachtung ist keine Einsatzfreigabe.
- Freies Kontingent: höchstens sieben reservierte Anfragen täglich, 25 Monats-
  reserve; maximal fünf Turniere pro Anfrage, ein Buchmacher pro Anfrage.
  Kleinere vollständige Pakete alle zwölf Stunden, größere einmal täglich.
  Vor jedem Abruf aktive Free-Subscription prüfen; kein kostenpflichtiger Wechsel.
- Kein neuer Timer, kein Historienwachstum: ein begrenzter ersetzbarer Quotencache,
  Budget im vorhandenen Zähler. Keine neue Bereinigung oder Backupaktivierung.
- Funktionscommit `696635d` auf main/GitHub/VPS; Schlüssel root:betboy 0640,
  App neu gestartet, interner/öffentlicher Healthcheck `ok`. 1.358 Tests plus
  111 Untertests und 218 zusätzliche main-Anschlusstests bestanden.
- Vollständiger VPS-Quotenabruf: sieben kommende Spiele, fünf Anfragen,
  keine Fehler, Cache 8.987 Bytes. E-Sport-Worker um 18:46 CEST erfolgreich:
  30 Spiele geprüft, acht neue Modelle. Zwei exakte Modell-/Preiszuordnungen
  bestätigt. Veröffentlichung 20:16 CEST inzwischen tatsächlich sichtbar:
  Wettfinder Team Liquid 1,267; RisikoBet FlyQuest 3,80. Der Map-Markt bekommt
  keine Serienquote. Daily3 hat derzeit keine passende Auswahl.
- Nachprüfung: Disziplin ging beim Speichern der Quoten-Nachweise verloren.
  Korrektur `94fa36f` bewahrt sie für neue E-Sport-Daten; bestehende andere
  Sportarten und E-Sport-Altdaten ohne Disziplin bleiben unverändert.
  421 gezielte Tests bestanden; Quotenbeobachtung bleibt ohne Einsatzfreigabe.
  Code auf GitHub main und VPS (20:55 CEST); native read-only Gegenprobe mit
  echter LoL-Quote 1,267 bestanden, falsche Disziplin abgewiesen. Weitere
  142 Tests auf lokalem main grün. App und beide Healthchecks `ok`.
- Der gemeinsame Lauf ist weiterhin fachlich/technisch nur teilweise gelungen:
  16 Fußball-Fehlermeldungen und ein Tennis-Sammelfehler mit acht nicht
  aktualisierten Prognosen (`ContextIntegrityError`). Nicht durch den
  E-Sport-Anschluss als repariert melden; Verletzungs-/Müdigkeitswirkung offen.
- Release-/VPS-Nachweis in
  [E-Sport-Anschlussbericht](docs/audits/2026-09-20-esports-quoten.md).
  Ältere Angaben unterhalb dieses Blocks sind historische Zwischenstände.

## E-Sport-Quoten – frühere Zugangsvoraussetzung 20.09.2026

- FieldFunded erneut im getrennten Browser geprüft: Free-Anmeldung scheitert
  weiterhin am CORS-Preflight auf `/api/stripe/free-key`; kein Schlüssel erhalten.
- Bestehende The Odds API: echte kostenlose Katalogabfrage erfolgreich,
  179 Sport-/Turniereinträge einschließlich inaktiver, kein E-Sport-Eintrag;
  Kontingent unverändert 499. Kein Ersatz durch eine errechnete Modellquote.
- Alternative OddsPapi: tatsächliches Registrierungsformular bestätigt Free,
  alle Sportarten/Buchmacher und 250 Anfragen/Monat. Anmeldung erfordert eigenes
  Passwort und hCaptcha; dem Nutzer im internen Browser bereitgestellt.
  Schlüsselübergabe außerhalb von Git im geschützten Verzeichnis vorbereitet.
- Nächster Schritt nach Schlüsselübergabe: tatsächlichen Free-Tarif und
  E-Sport-Katalog prüfen, exakte Spiel-/Disziplin-/Serienmarktbindung testen,
  gemeinsame Preisversorgung für Wettfinder, Daily3 und RisikoBet anbinden.
  Auch Katalogabfragen zählen bei OddsPapi zum Kontingent; Abrufe bündeln,
  Monat-/Tagesbudget begrenzen, keine automatisch kostenpflichtige Erweiterung.
- Noch keine OddsPapi-Registrierung abgeschlossen, keine Produktivcode- oder
  VPS-Änderung und kein erfolgreicher E-Sport-Quotenabruf behaupten.
  Details: [Weitere Sportquoten](docs/audits/2026-09-20-weitere-sportquoten.md).

## Quotenanbindung 20.09.2026 – weitere Sportarten

- Tennis-Zugang inzwischen eingerichtet und auf dem VPS aktiviert.
  Funktionscommit `8e2581e` auf main/GitHub/VPS; 753 betroffene Tests und
  32 Untertests bestanden. Monatsbudget 500 Credits mit 25 Reserve,
  höchstens 16 reservierte Credits/Tag; mehrere Spiele eines Turniers gebündelt.
  Schlüssel ausschließlich in geschützter Konfiguration, nicht im Repository.
- Echte VPS-Probe: WTA Singapore Open, sechs kommende Events; Kasatkina gegen
  Sasnovich mit sieben Buchmachern pro Seite bepreist, keine Abruffehler.
  Ein Credit verbraucht, 499 verbleiben. Nur Quotenprüfung, kein Modell/Tipp erzeugt.
- Erster Quotenrelease `f4677e2`: damals main/GitHub/VPS abgeglichen, 1.122 Tests plus 58 Untertests
  grün. Nativer Abruf: vier NHL-Spiele zugeordnet, zwei Quoten ohne Fehler;
  Cache rund 3 KB. Das NHL-Modell liefert derzeit noch keine gewählte Seite.

- Fußballquoten und der übergreifende 1,20-Filter waren bereits mit `66161eb`
  live. Aktuell ergänzt: zentrale API-Sports-Quoten für NBA/Euroleague/NHL,
  Wiederverwendung in Wettfinder/Daily3/RisikoBet, inklusive RisikoBet-Spielen
  ohne vollständige Modellprognose. Zeitangabe ist ausdrücklich Abrufzeit,
  keine erfundene Buchmacherzeit und keine neue Einsatzfreigabe.
- Bestehender Worker/Budgetzähler, begrenzter Cache ohne Historienwachstum.
  Keine neue Bereinigung, Datenbank, Sicherung oder Timer.
- E-Sport bleibt offen: FieldFunded-Free-Anmeldung scheiterte im Anbieterformular
  an CORS/„Network error“; kein bestätigter Schlüssel. Details und Nachweise in
  [Weitere Sportquoten](docs/audits/2026-09-20-weitere-sportquoten.md).
- Bestehende Tennis-/Kontext-/Workerfehler sind dadurch nicht behoben.
- Die ältere Regel unten ist zeitlich enger formuliert: seit `d94c5bc`
  gilt der Filter auch für eindeutig als älter markierte letzte Angebote
  bis 24 Stunden. Fehlende oder fremde Quoten bleiben unbekannt.

## Neue Nutzerregel 20.09.2026 – bekannte Quoten unter 1,20 aussortieren

- Diese ausdrückliche Nutzerentscheidung ersetzt die bisherige ausnahmslos
  quotenunabhängige Sichtbarkeit: automatischer Wettfinder, eigene Fußballsuche
  und Daily3 entfernen Vorschläge, deren beste exakt passende aktuelle
  Anbieterquote unter 1,20 liegt. Genau 1,20 ist erlaubt. Fehlende/veraltete/
  fremde Quoten bleiben unbekannt; weder Modellchance noch Rechenpreis werden
  als angebotene Quote ausgegeben. Keine neuen kostenpflichtigen API-Abfragen.
- Reihenfolge: erst widerspruchsfreie Modellrichtung, danach Preisfilter,
  danach Platzvergabe. Der Filter darf nicht auf die Gegenseite umschalten.
  Alle gespeicherten Prognosen und Wahrscheinlichkeiten bleiben unverändert.
- Daily3 lehnt neue Vormerkungen mit manuell eingegebener Quote unter 1,20
  transaktional ab. Historische Buchungen, deren Wiederholungsbestätigung,
  Platzierung/Abrechnung und Nachträge tatsächlich externer Wetten bleiben
  lesbar und gültig. Keine Schemaänderung oder Umschreibung der Historie.
- 811 Tests plus 26 Untertests bestanden. Grenzwert ohne Aufrundungsloch,
  einzelne Anbieter, veraltete Hochquoten, falsche Zuordnungen, Tennis,
  echte UI-Eingabe und vorhandene Altverträge separat abgesichert.
- Rein lesende VPS-Probe 11:15 CEST: 619 Eingangssignale, 336 kohärente
  Auswahlen unverändert; in diesem Bestand keine aktuelle exakt passende
  Quote unter 1,20. Daher nicht behaupten, jetzt seien dort massenhaft
  Auswahlen entfernt worden. Ohne Quote lässt sich dieser Filter nicht prüfen.
- Nur Produkt-/Preisfilter, kein Nachweis besserer Wettqualität. Unveränderte
  Restarbeiten an Tennis-Laufzeit sowie Verletzungs-/Müdigkeits-/Wetterwirkung.

## Hervorhebungen 20.09.2026 – spielbezogener Vergleich auch im Wettfinder

- Fehler am echten Bestand reproduziert: Corinthians–Fluminense, Auswärtsteam
  unter 2,5, wurde mit 89,8628 % hervorgehoben, obwohl die Saisonbasis schon
  91,655 % und die Formvariante nur 81,8378 % ergaben. Bisher prüfte nur Daily3
  den zusätzlichen spielbezogenen Formvergleich; im Wettfinder fehlte er.
- Fußball-Hervorhebungen nutzen jetzt denselben exakt gebundenen Vergleich
  und werden nach seinem Formkontrast geordnet. Die vorhandene Zwei-Prozent-
  punkte-Relevanzregel ist kein Sicherheits-/Valuebeweis. Keine Wettarten-
  verbote, keine Quotenfilter, keine Daily3-Wahrscheinlichkeitsschwelle im
  normalen Wettfinder. Eine kurze Formangabe erklärt die Hervorhebung.
- Richtungs-/Widerspruchsprüfung bleibt davor: Ein positiver Formkontrast
  eines Außenseiters darf die wahrscheinlichere Ergebnisrichtung nicht verdrängen.
- 706 Tests plus 26 Untertests bestanden; 19 neue Regressionen sichern den
  gemeldeten Fall, weiterhin erlaubte breite Märkte, Quotenunabhängigkeit,
  Belegbindung und Ergebnisrichtung. Streamlit: 23 Spielblöcke, keine Exception.
- Rein lesender Vorher-/Nachher-Lauf am VPS um 10:47 CEST: 621 Eingangssignale,
  dieselben 338 kohärenten Prognosen samt Wahrscheinlichkeiten; Fluminense
  unter 2,5 nicht mehr hervorgehoben. Keine Produktionsdatei dafür verändert.
- Nur Auswahlpräsentation korrigiert, keine neue Modellqualität nachgewiesen.
  Tennis-Laufzeit und vollständige Verletzungs-/Müdigkeits-/Wetterwirkung bleiben offen.

## Nutzeransicht 20.09.2026 – Diagnosebanner entfernt

- Automatischer Wettfinder: kein globaler Auswahlzähler und kein Banner
  „Suche unvollständig“ mehr, auch kein Ersatzabsatz oder leerer Rahmen.
- Datenstand, Sportfilter, Spielblöcke, sämtliche Auswahlen und wichtige
  Hinweise an einzelnen Karten bleiben erhalten. Interne Fehler-/Abdeckungs-
  daten werden nicht verändert oder als erfolgreich umgeschrieben.
- 243 betroffene Tests bestanden; zusätzlich echter Streamlit-Testlauf mit
  23 Spielblöcken, erhaltenem Datenstand und ohne Exception. Interner Browser
  wegen Sandbox-Startfehler nicht verfügbar; kein externer Browser verwendet.
- Reine UI-Korrektur. Die folgenden Tennis-/Kontext-Restarbeiten bleiben offen.

## Fortsetzung 20.09.2026 – Datenlauf-Konflikt

- Übergabe gegen echte Daten geprüft: `2758619` war lokal/GitHub/VPS identisch.
  Über Nacht sind 23 Fußball-Originale zu 19 Spielen gespeichert worden; alle
  sind partiell, also noch kein vollständig quellgebundener Trainingsfall.
- Tennis brach um 07:18:15 mit einer Datenbank-Lesesperre des Fußballlaufs ab.
  Ergebnisprüfung jetzt auf die empfangenen Events begrenzt; Ergebnis-/Spieler-
  historie gibt das konsistente SQL-Lesebild vor CPU-Validierung frei.
- 578 betroffene Tests bestanden, 4 Skips. Rein lesende VPS-Probe: selbst für
  1.096 Fußball-Events nur 2,207 s SQL-Lesephase; Spielerinventur 0,650 s.
  `bc6fef3` auf main/GitHub/VPS live; nochmals 125 Tests auf main und beide
  Linux-Schreibkonkurrenzproben bestanden. App/Healthchecks/Rechentimer aktiv.
  Echter Tennis-Neulauf 09:31:57: Modellaufbau erfolgreich, WTA publiziert;
  WTA-Ergebnisstand 12.09. Tages-Scan aber 09:45:42 erneut mit Schreibkonflikt
  abgebrochen. Nicht als erfolgreicher Gesamtlauf melden.
- Zweite Ursache gemessen: physisches Lesen der Tennis-Historie hält die
  Sperre 21,626 s, bisheriges Schreibbudget nur 5 s. Gemeinsame endliche
  Wartezeit jetzt 60 s, Journal/Schema/Prüfinhalte unverändert. 980 Tests,
  5 Skips grün. `9c579fe` auf main/GitHub/VPS live; 67 main-Tests/5 Skips
  und Linux-Probe mit echter 22-s-Lesesperre bestanden. Neuer Tennis-Lauf
  endete aber 10:19:32 mit 900-s-Timeout: Empfang gespeichert, History bereit,
  dann Vorbereitung von 48 Prognosen nicht abgeschlossen. Kein erfolgreicher
  Gesamtlauf und keine 48 veröffentlichten Tipps behaupten. Letzter Wettfinder
  vor Codewechsel ebenfalls degraded, nicht mit vollständiger Datenabdeckung.
- Nächste technische Aufgabe: CPU-Anteile von History, Spielerprojektion,
  Feature-Vorbereitung und Schlüsselbildung am selben Bestand messen und den
  tatsächlichen Engpass beheben. Synthetischer 500k-Grenzvergleich allein
  erklärt den Timeout nicht; keine blind erhöhten Laufzeit-/Speichergrenzen.
- Vollständige Verletzungs-/Müdigkeits-/Wetterwirkung bleibt unerledigt.
  Weder Aufnahmebudget noch Qualitätskriterien wurden gelockert. Keine neue
  Sicherung/Bereinigung, keine Finanz- oder Cricketänderung.
- [Prüfbericht und konkrete Restarbeiten](docs/audits/2026-09-20-fortsetzung-datenlauf.md).
  Ältere Abschnitte unten sind datierte Zwischenstände, keine aktuellen Freigaben.

## Kontextanschluss und Daily3-Spielvergleich – 19.09.2026, Code live

- Nachtrag `362a4a6` am 20.09. um 00:04 CEST auf VPS bestätigt; 1.526 Tests,
  nochmals 210 auf main und Linux-Smoke grün. Tatsächliche Originalaufnahme
  nach diesem Nachtrag bleibt offen; nächster normaler Worker 00:07 CEST.
- Nicht als vollständig fertig melden: numerische Verletzungs-/Müdigkeits-/
  Wetterwirkung ist weiterhin nicht trainiert und empirisch freigegeben.
  Die vorhandenen Prognosen sind echte Berechnungen, aber ohne diese Wirkung.
- Daily3 v4 vergleicht aktive/Form-Variante mit der Saison-/Heim-Auswärtsbasis
  derselben Begegnung. Favoritenstärke allein reicht nicht. Die zusätzlichen
  zwei Prozentpunkte sind eine Relevanzregel, kein Sicherheits-/Valuebeweis.
  Keine Marktverbote oder Quotenfilter; normale Prognosen bleiben erhalten.
- Kanonischer Fußballworker erhält die vorhandene Originalaufnahme mit
  dauerhaftem Aufnahmebudget: 4 MiB/Sitzung, 8 MiB/UTC-Tag, 128 MiB insgesamt
  an zusätzlicher JSON-Nutzlast. Keine neue Sicherung oder Bereinigung.
- Nicht gesendete Spielerhistorienabfragen wegen API-Budgetreserve lösen
  keine neue 24-Stunden-Wartefrist mehr aus; echte Fehlantworten weiterhin.
- Nachtrag abgesichert: Eine übergroße optionale Originalaufnahme darf die
  unveränderte normale Prognose nicht verwerfen; strenge Speicherung bleibt.
- Der erste Live-Lauf deckte den Mehrgruppenfehler auf: leere erste Gruppe,
  danach keine Aufnahme mehr. Nun teilen sämtliche Gruppen dasselbe endliche
  Kontingent; keine Vervielfachung, auch nicht bei parallelen Veröffentlichungen.
- Tatsächliche Lücken: keine Fußball-Originale oder trainierten Effekte im
  geprüften VPS-Bestand; Tennis nur 112 unterschiedliche Ergebnisereignisse.
  Neue Originalaufnahme ersetzt weder native Zuordnung noch Replayfreigabe.
- Funktionscommit `39bd0eb` gepusht und auf VPS deployed; 1.522 Tests grün,
  weitere 202 Anschlusstests auf main grün. Healthchecks und Rechentimer
  bestätigt. Erster Datenlauf 23:42:16 beendet, weiterhin degraded/16 Daten-
  probleme und noch keine Originale; API-Aufschub live korrekt. Aufnahme nach
  Mehrgruppen-Nachtrag weiterhin tatsächlich nachweisen, nicht als fertig melden.
- Prüf-/Releasebelege im [Reparaturbericht](docs/audits/2026-09-19-kontextanschluss-und-spielvergleich.md).
  Nachtrag mit Größen- und gemeinsamem Gruppenbudget ist separat live bestätigt;
  keine durchgehende Daten- oder Kontextqualifikation daraus ableiten.
  Cricket, Echtgeldregeln, alte Archive und deaktiviertes Tagesbackup erhalten.

## Daily3 19.09.2026 – Auswahlregel und Teil-Refresh repariert

- `0a54313`: keine Sortierung allein nach höchster Rohwahrscheinlichkeit mehr.
  Versions- und spielgebundener Vergleich zur historischen Markthäufigkeit,
  mindestens 70 Prozent in allen drei vorhandenen Modellvarianten. Keine
  pauschalen Wettartenverbote und kein Quotenfilter; normale Prognosen erhalten.
- `533a98f`: echter VPS-Befund behoben – ein nicht modellierbares Spiel verwirft
  nicht mehr die erfolgreichen Berechnungen seiner ganzen Gruppe. Alte Daten
  fehlgeschlagener Spiele werden weder gelöscht noch als frisch umetikettiert;
  ihr Fehler bleibt über weitere Gruppen hinweg sichtbar.
- Beide Commits auf main/GitHub und VPS; 1.090 Tests/111 Untertests jeweils im
  Worktree und main bestanden. App/Healthchecks bestätigt. Normaler Datenlauf
  um 15:26:36 CEST beendet: 51 Spiele neu modelliert, 9 weitere weiterhin
  unmodelliert (deshalb ehrlich Teildaten/Exit1). Gründe dieser neun offen.
  Echter Vorher-/Nachher-Vergleich bestätigt: alte Regel liefert exakt die
  beanstandeten drei Tipps; neue Regel Reykjavík-Gesamtüber2,5, Siriusüber0,5,
  Santosüber0,5. Zwei einfache Märkte bleiben erlaubt, kein Marktverbot.
  Kein zusätzlicher vollständiger 10k-Testlauf.
- Vergleichsproduzent bislang nur Fußball; ohne passenden Vergleich keine
  Daily3-Auswahl anderer Sportarten, deren normale Prognosen bleiben sichtbar.
  Kein empirischer Nachweis besserer Treffer-/Gewinnqualität. Verletzungs- und
  Müdigkeitswirkung bleibt separat offen; Cricket unverändert.
- Nur Streamlit-AppTests: interner Browser scheitert schon beim Start an
  Windows-ACLs. Keinen externen Browser übernehmen. Keine neue visuelle
  Desktop-/Mobile-Abnahme behaupten. Keine weitere Speicherbereinigung oder
  Sicherung; Tagesbackup bleibt aus.
- [Reparaturbericht und ehrliche Grenzen](docs/audits/2026-09-19-daily3-auswahlvergleich.md).

## Spielblöcke 19.09.2026 – gemeinsames Auf-/Zuklappen live

- Funktionscommit `1e918b9` auf main/VPS: automatischer Wettfinder zeigt jedes
  Spiel nur einmal, mit sämtlichen bisher sichtbaren Auswahlen im selben Block.
  Hervorgehobene Spiele zunächst offen, weitere zunächst geschlossen.
- Zustand bleibt innerhalb der Browsersitzung bei Sportfilter-/Seitenwechseln
  erhalten. Seiten enthalten ganze Spiele, keine zerschnittenen Marktgruppen.
- 907 betroffene Tests plus 26 Untertests jeweils in Worktree und main grün.
  Lokal Desktop/Tablet/Mobil und echter VPS-Browser geprüft; Beispiel
  Brommapojkarna–Göteborg mit allen zehn Auswahlen gemeinsam geschlossen.
- Keine Modell-, Quoten-, Geld-, Datenbank- oder Backupänderungen. Bekannte
  fachliche Restarbeiten bleiben offen. Keine erneute Speicherbereinigung.
- [Abschluss und Grenzen](docs/audits/2026-09-19-spielbloecke.md).

## Prognosekarten 19.09.2026 – kompakte Fakten und Ausfalldetails live

- Funktionscommit `763c741` auf main/VPS. Kurze Torprognose und Faktenfelder
  statt langer sichtbarer Absätze, Einzelheiten per Klick/Tastatur; Wettfinder
  und aktuelle Daily3-Karten. Keine Änderung von Wahrscheinlichkeit oder Geld.
- Spielerstatus ehrlich getrennt: alte gemischte Listen nicht als gesicherte
  Ausfälle bezeichnen. Neue Läufe speichern getrennte Namen; kein Zusatzabruf.
  Nicht eingerechnete Ausfallwirkung bleibt direkt sichtbar.
- 713 Tests und 26 Untertests jeweils im Worktree und main bestanden;
  Desktop/Mobil, Tastatur und echte Website geprüft. Health/Timer bestätigt.
- Keine Speicherbereinigung/Migration/Sicherung wiederholen. Tagesbackup aus.
  Vollständige Modellwirkung und empirische Qualität bleiben offen.
- [Abschluss und Grenzen](docs/audits/2026-09-19-kompakte-prognosekarten.md).

## Daily3 19.09.2026 — defensives Modellprofil und kompakte UI live

- Funktionscommit `1985407c176e4cf5ecc4a9d5b2a93636b8634673` auf main/VPS.
  Mindestens 70% Modellschätzung, höhere Modellchance vor Vielfalt, ein Spiel
  pro Slot. Kein Gewinnziel-/Quotenfilter, keine Änderung der normalen Rangfolge.
- 344 betroffene Tests im Worktree und nochmals in main bestanden. Desktop,
  Mobil, leer/gefüllt und die echte Website geprüft. Kein zusätzlicher Gesamttest.
- Hauptansicht gekürzt; allgemeine Regeln optional, konkrete Unsicherheiten
  weiterhin sichtbar. Echtgeld-/Budget-/Abrechnungslogik unverändert.
- VPS-Codewechsel und Healthchecks bestätigt. Keine neue Speicherbereinigung,
  Datenmigration oder Sicherung. Tagesbackup bleibt disabled, Retention unverändert.
- Offen bleiben empirische Qualität, vollständige Verletzungs-/Müdigkeitseffekte
  und die vorher bestehenden Teildaten-/Datenjobfehler. Höhere Roh-Modellchancen
  sind keine nachgewiesene Sicherheit und kein CHF150-Einkommensversprechen.
- Details und ehrliche Abgrenzung der SSH-Nachlaufkante:
  [Releasebericht](docs/audits/2026-09-19-daily3-defensiv.md).

## Speicherreparatur 19.09.2026 — live, ca. 11:29 CEST verifiziert

- **Erledigt:** Funktionscommit `8caf022b562c561c7d23b4b8363791bb0869d9d3`
  gepusht und auf VPS bereitgestellt; nachfolgende Abschlussdokumentation
  aendert keinen Produktcode. Vorherige Produktreparaturen damit ebenfalls
  ausgeliefert. Wartungsauftrag `betboy-storage-repair-20260919-b.service`
  erfolgreich (Exit 0). Keine bereits erledigte Speicherbereinigung wiederholen.
- Produktivdatenbank **3.326.431.232 -> 2.092.552.192 Bytes**, rund 1,23 GB
  weniger. 36 aufgeblähte Snapshots umgepackt; alle 1.041 Analyseidentitäten,
  926.502 Inhalts-/Empfangsbelege und übrige Tabellen-/Schemaidentitäten
  erhalten. SQLite/Fremdschlüssel ok, große Inline-Restfälle 0. Frischer
  normaler Lesetest mit 504.808 Verweisen und unverändertem Hash bestanden.
- App/Caddy aktiv, lokale und öffentliche Healthchecks ok; sechs Rechentimer
  wieder aktiv. Tagesbackup disabled/inactive; Aufbewahrungstimer unverändert.
  Kein neues Tages-/Updatearchiv; alte Archive und Root-Updater nachweislich
  unverändert. Nur eigene temporäre synthetische QA-Daten (~114 MB) entfernt.
- **Nicht daraus ableiten:** vorher fehlgeschlagene/degraded Tennis-/Wettfinder-
  Läufe, vollständige Verletzungs-/Müdigkeitswirkung oder empirische Qualität
  seien erledigt. Normale Beobachtungshistorien dürfen weiter wachsen; behoben
  ist die unbeabsichtigte Vollkopie jeder großen Nachweisliste pro Analyse.

- Konkreter Defekt behoben: ab 500.001 Nachweisverweisen wurden rund 34 MB
  pro Analyse erneut inline gespeichert. Gemeinsame Blockspeicherung und
  Leser funktionieren nun auch oberhalb dieser Grenze; Inhalte/Hashes und
  Prognosen bleiben unverändert. Keine Statistiken oder Wetthistorien löschen.
- 25 gezielte Tests jeweils Windows und VPS-Linux bestanden. Gesamtlauf:
  10.293 bestanden, 96 Skips, 111 Untertests, 16 Windows-Git-Setupfehler;
  die vollständige betroffene Testdatei anschließend mit exakt scoped
  safe.directory: 56 bestanden. Zusammen 10.309 unterschiedliche Tests
  erfolgreich, keine Quell-/Teständerung danach. Nicht als einzelnen grünen
  Gesamtlauf ausgeben. Details: [Speicherbericht](docs/audits/2026-09-19-snapshot-speicherfehler.md).
- Nutzer will keine neuen Tages-/Updatearchive. Tagesbackup auf VPS bereits
  disabled/inactive. Vorhandene Archive und Aufbewahrungspolitik unverändert.
  Alten Updater nicht unverändert starten: er erzwingt Archive und aktiviert
  Tagesbackups erneut. Dieser Release verwendet einen geprüften Code-only-
  Ablauf ohne Root-/Dependency-/Finanzmigration und danach die bestehende
  verlustfreie Inline-Snapshot-Kompaktierung bei stillstehenden Schreibern.
  Dies ist kein Auftrag, den alten Updater oder die Kompaktierung erneut
  auszuführen. Fachliche Modelllücken bleiben separat offen.

## Produktreparatur 19.09.2026 — committed und gepusht, VPS separat

**Veröffentlicht:** Reparaturpaket `2cd0a982a96331996955779a8dfff0466ecfb2fd` ist im Hauptcheckout auf main und auf GitHub-main, nach regulärem Push per `ls-remote` bestätigt. Nachfolgende Änderungen ergänzen nur diese Abschlussdokumentation. Funktions-/Teststand `d0759b1`. Alle unabhängigen Task-/Gesamtreviewbefunde geschlossen. Keine Produktions-/VPS-Änderung oder Speicherbereinigung in dieser Runde.

**Tests abgeschlossen:** Vollsuite auf `d0759b1`:10303 bestanden,96 Skips,111 Untertests,Exit0,1545.58s; neun reine JUnit-Berichtshinweise. Anschließend Hauptcheckout auf `2cd0a98`:625 bestanden,79 Untertests,Exit0,90.16s. Keine Quell-/Teständerung während oder nach diesen Läufen. Logs im Worktree `output/playwright/product-full-suite-20260919-d0759b1.{log,xml}` und im Hauptcheckout `output/playwright/product-main-checkout-20260919-2cd0a98.log`. Vorige Fixture-/Ownershipfehler im Reparaturbericht erklärt; keine Schutzregeln/Pins gelockert. Erledigte Tests nicht erneut als laufend übernehmen.

Dieser Abschnitt ersetzt die darunterstehenden historischen Statusmeldungen. Nutzerauftrag: bestätigte Produktfehler beheben, committen und pushen; Cricket unverändert. Keine weitere Speicherbereinigung und keine automatische Codeauslieferung durch Timer.

- Ausgangsstand des geprüften Produkt-Audits: lokal/GitHub/VPS `c64218b`. Audit [2026-09-18-produktqualitaet.md](docs/audits/2026-09-18-produktqualitaet.md); Reparaturfortschritt [2026-09-18-produktreparatur.md](docs/audits/2026-09-18-produktreparatur.md).
- Arbeit im bereits genehmigten Worktree `.worktrees/context-capacity-recovery-20260910`, Branch `codex/context-capacity-recovery-20260910`; Hauptcheckout per Fast-forward aktualisiert, VPS unverändert. Bestehender Worktree und fremde/ungetrackte Prüfdateien bleiben erhalten. Kein erneutes Worktree/Design/Push-Permission-Pingpong.
- Lokal erledigt und unabhängig geprüft: `f844f05` Preiswarnung/keine erfundene Erholung; `c953d46`+`9467148` gemeinsame widerspruchsfreie Auswahl, belegte Hervorhebung/Analyse, keine pauschalen Marktverbote; `f42e264` gemeinsame konsistente Fußballverteilungen mit eigener Validierungsversion und alter Ticket-/ORIGINAL-Kompatibilität. 709 betroffene Tests plus97 Untertests für den mathematischen Stand; **keine neue Gesamt-Suite** daraus ableiten.
- WTA-Dauererhaltung `534d27d` + `2d92eb9` ist unabhängig nachgeprüft: alle drei Reviewbefunde geschlossen, echte historische Laufzeit-/Trainingsreplays erhalten; 360 betroffene Tests und 92 numerische Tests bestanden, 3 Skips. Keine Müdigkeitswirkung daraus ableiten.
- Basketball-/Eishockey-Brücke `fdd04bf`+`423e888` unabhängig abgeschlossen: dieselbe vorhandene Berechnung wird im normalen Wettfinder konsumiert, Belege unveränderlich übernommen. Daily3 erklärt gemeinsamen Bestand und tatsächliche Anzahl. 468 Tests plus26 Untertests; Fixrunde275 plus26 Untertests. Finanz-Lesevorprüfung `5ff08a9` unabhängig geprüft:217 Tests plus85 Untertests; Geld-/Integritätsregeln unverändert. Browser-Rundungsfehler mit `a322430` behoben: kein gerundetes100% bei Wahrscheinlichkeit kleiner1;160 betroffene Tests bestanden.
- Kausale Fußball-Originalanbindung `f6f62a5` ist implementiert und unabhängig geprüft: 590 Tests, 4 Skips, 32 Untertests. Endliche ausdrückliche Opt-in-Budgets; standardmäßig keine Zusatzspeicherung. Ausführungsfingerabdruck ist **kein** replay-fähiges C1-Codepaket oder eine Effektqualifikation. Originalquelle, Codeidentität und empirischen Stand getrennt berichten. Echte Aktivierung/Tageszuwachs-/Kapazitätsprüfung bleibt offen.
- Desktop-/Mobilrenderer mit klar synthetischen Daten tatsächlich geprüft: konsistente Richtung, unveränderte Prognosen bei Quote1.12, Daily3 mit0/1/3 Events, neutrale Basketball-/Eishockeykarten, kein Überlauf bis320px und frische Konsole ohne Fehler. Bericht `docs/audits/2026-09-18-product-ui-check.md`. Keine Freigabe der vollständigen Produktionsseite oder Vorhersagequalität daraus ableiten.
- Git-Integration, Hauptcheckout-Prüfung und regulärer Push sind erledigt. VPS-Deployment und neue Linux-/Betriebsabnahme separat; Timer liefern keinen Code aus. Eine neue Produktionsfreigabe nicht allein aus Windows-Tests oder GitHub-Hash ableiten.
- **Fachlich weiterhin offen:** tatsächliche angewendete/empirisch belegte Verletzungs-/Müdigkeitseffekte; Aktivierung des kausalen Fußball-Live-/B1-Anschlusses und neuer versionsgleicher Wirkungs-/Trainingspfad; tatsächliche Tennis-Endzeiten/native Zuordnung; ausreichende unbenutzte echte Testevents. Neue Verteilungsregel braucht eigene Qualifikation. 101 gebundene Tennis-Spiele sind keine200 geeigneten Holdout-Events. Keine bessere Wettqualität behaupten.

Konkrete Wiederaufnahme aus den jeweiligen `.superpowers/sdd/2026-09-18-*/progress.md` und tatsächlichem Git; bereits vollständige Tasks nicht neu implementieren. Fremde/ungetrackte Prüfdateien erhalten. Der neue Fußball-Liveanschluss ist technisch unabhängig geprüft, aber nicht aktiviert; sein Code und Speicherbaustein sind kein fachlicher Effektbeleg.

## Historisches Releasepaket 18.09.2026 — neuerer Stand steht oben

- **Funktionsstand `c44684d` ist lokal auf `main` und auf GitHub-main.** Die folgenden Dokumentationsänderungen gehören zum selben Releasepaket. VPS zuletzt weiterhin `f3c2b60`; ein Push ist kein Deployment. Abschließende Serverbelege werden separat in `output/playwright/context-repair-deployment-20260918.md` festgehalten. Falls diese Datei fehlt, keinen erfolgreichen neuen Release annehmen; Git/Health/Jobstatus frisch lesen.
- Vollständige finale Suite: **10.065 bestanden, 96 Skips, 97 Untertests bestanden**, Exit 0, 1608.90 s. Danach im fast-forwardeten Hauptcheckout nochmals **346 bestanden, 12 Skips**, Exit 0. Alle Funktionsreviews, der Gesamtdiffreview und die QA-Korrektur sind ohne offene Befunde. Quellen-/Testdateien blieben während des finalen Gesamtlaufs eingefroren. Logs: `full-suite-final-20260918-39b5c281.log`, `main-checkout-20260918-031b438d.log` unter `output/playwright/`.
- Fertig: kürzere Consumer-Lesesperren, korrigierter Tennis-Saisonpfad, eng begrenzter historischer Tennis-Replay-Übergang, deduplizierte verlustfreie Fußball-Originalspeicherung. Sieben vorbestehende native QA-Fehler sind durch ehrliche Trennung historischer Prüffälle und aktueller Ausführung korrigiert; keine Pins, Ressourcen- oder Modellregeln gelockert. **Aktuelle native Neuqualifikation bleibt separat offen.**
- Die nach erneuter Freigabe zusätzlich übernommenen acht alten QA-/Recovery-Ziele sind nach vollständiger Linux-Wiederherstellung, geschütztem SSH-Export und kompletter lokaler Archivleseprüfung entfernt. Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`, Archiv 1.632.517.697 Bytes; SHA256 `44d6f5202513b96156b4b33e0724561b30186a71da0ce32039d89a549d5b9366`. Manifest SHA256 `a025bce3460cfa83bb8148499d56907b77c1e76c9c32471adb13baeea987bc95`. Rund 2.43 GB dauerhaft frei; zusätzliche Server-Transportkopie ebenfalls entfernt. Runner, Wartungszustand und installierter Updater sind hashgleich; Produktionsdatenbanken und reguläre Backups unangetastet. Alte Drei-Kopien-Bereinigung ebenfalls erledigt, keine Bereinigung erneut starten.
- Frischer Reservecheck nach Bereinigung: 22.581.014.528 Bytes frei, 22.399.551.488 Bytes unveränderte Grundreserve nötig. **Codebereitstellung muss zusätzlich passen**; 181 MB Abstand sind keine garantierte Releasefreigabe. Nur den vorhandenen vertrauenswürdigen Updater verwenden; nicht direkt in Produktion pullen, keine Grenze reduzieren. Acht gelöschte Ziele/Prüfbelege stehen im neuen Retirement-Plan und den SDD-Berichten. Keine weitere Datenkopie ist durch diesen konkreten Acht-Ziele-Schritt freigegeben.
- **Fachlich nicht fertig:** Fußballplan Tasks 2/3 (kausaler Live-/B1-Anschluss und Aktivierung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, echte Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket sowie empirische und Nutzerabnahme. 101 unterschiedliche exakt gebundene Tennis-Spiele sind keine 200 geeigneten unangetasteten Testevents. Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität freigegeben. Preise und Geldkonten unverändert.

Details: [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md). Die erneute allgemeine Design-/Worktree-/Pushfreigabe ist nicht erforderlich; erledigte Tasks nicht wieder beginnen. Timer berechnen, sie deployen keinen Code.

## Historischer Arbeitsstand 18.09.2026, 19:43 CEST

- **Nicht alles abgeschlossen.** Lokal `c44684d`, GitHub-main und VPS zuletzt `f3c2b60`. Sechs lokale Reparaturcommits noch nicht gepusht/deployed. Server um 19:36 CEST: App/Caddy aktiv, interner Healthcheck `ok`; letzter Wettfinderlauf 19:07–19:15 CEST erfolgreich. Kein neuer erfolgreicher Tennis-Gesamtlauf behauptet.
- Software fertig: Consumer-Lesetransaktion verkürzt (`185812e`), WTA/ATP-Quellenpfad repariert (`b342b02`), exakte historische Tennis-Replays erhalten (`0b529cf`), verlustfreie deduplizierte Fußball-Originalspeicherung samt inklusiver Grenze (`49ad632`, `0df6707`). Alle Funktionstasks und ihr Gesamtdiff unabhängig ohne Befund geprüft. Zahlen/Belege im [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md).
- Sieben Gesamtregressionsfehler waren bereits am exakten vorherigen Stand reproduzierbar: historische native Pins wurden mit inzwischen geänderten QA-Eigentümerdateien vermischt. `c44684d` trennt historische Prüffälle von der echten aktuellen Ausführung. 337 betroffene Tests bestanden, 54 Skips; native Pins, Eigentümer und Grenzen unverändert. **Aktuelle native Neuqualifikation bleibt offen**, kein anderer Name für einen zugelassenen aktuellen Lauf.
- Finaler Gesamttest läuft seit 19:40:14 CEST auf eingefrorenen Quellbytes, ohne `maxfail`: Sitzung `65907`, Log `output/playwright/full-suite-final-20260918-39b5c281.log`, isolierter Testpfad `C:/Projekt/BetBoy/.qa-final-20260918-39b5c281`. Gleichzeitig unabhängiger QA-Review unter `.superpowers/sdd/2026-09-18-native-qa-portability/task-1-review.md`. Noch keinen grünen Gesamtabschluss ableiten; keine Source-Änderung während des Laufs.
- Bereits genehmigter Drei-Kopien-Export und deren Bereinigung sind erledigt, nicht wiederholen. **Zusatzfreigabe durch „alles“ am 18.09., etwa 19:48 CEST:** die acht zuvor genau angefragten QA-/Recovery-Ziele geschützt archivieren, vollständig wiederherstellen/prüfen, lokal sichern und erst dann entfernen. Plan `2026-09-18-approved-qa-retirement.md`; privater lokaler Zielordner bereits angelegt, noch kein Transfer/Löschen. Letzter Reservefehlbetrag 2.239 GB vor Codebereitstellung; die acht Ziele garantieren noch keine ausreichende Reserve. Keine produktive Datenbank, reguläre Sicherung oder weitere Kopie entfernen.
- Nach grünem Gesamtlauf und abgeschlossenem Review: nur eigene Quell-/Test-/Plan-/Handoffdateien committen, unverändertes GitHub-main prüfen, `main` fast-forwarden und regulär pushen. Keine erneute allgemeine Push-/Worktree-/Designfreigabe nötig. Neues Deployment erst bei ausreichender echter Reserve über den installierten vertrauenswürdigen Updater. Timer deployen nicht.
- Fachlich offen: Fußballplan Tasks 2/3 (echter Live-/B1-Anschluss und Aktivierungsprüfung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket und empirische/nutzersichtbare Abnahme. Es gibt 101 verschiedene exakt gebundene Tennis-Ergebnisse, keine 200 geeigneten unbenutzten Testevents. **Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität nachgewiesen.**

## Historischer Zwischenstand 18.09.2026, 18:41 CEST

- **Nicht alles erledigt; neue Reparaturen noch nicht deployed.** Produktivstand und GitHub-main weiterhin `f3c2b60`; aktive Reparaturkopie `codex/context-capacity-recovery-20260910` ist weiter. App/Caddy und interner Healthcheck zuletzt 18:28 CEST erfolgreich gelesen. Keine Produktionsänderung durch die folgenden lokalen Tasks.
- `185812e`: tatsächlicher Karten-Leser-Konflikt repariert; unveränderliche Leseabbilder verlassen die SQLite-Transaktion vor CPU-Prüfung. 472 betroffene Tests bestanden/5 Skips; unabhängiger Taskreview ohne Befund. Andere lange Inventurleser bleiben separat offen.
- `b342b02`: WTA/ATP-Saisonquelle auf veröffentlichten HTTPS-Pfad korrigiert, 159 betroffene Tests bestanden/3 Skips. Ein echter isolierter WTA-Aufbau mit vorhandenen öffentlichen Daten funktioniert: 1110 Spielerinnen, Ergebnisstand12.09.2026,7025 bestehende Kalibrierungsbeobachtungen,5.95s. Keine Veröffentlichung, kein Wirkungstest; vier offene openpyxl-Hinweise dokumentiert.
- Wichtiger Nachfolgefehler vor Deployment entdeckt: `tennis/data_loader.py` gehört zur gespeicherten Original-Codeidentität. Alte Originale würden allein wegen der URL-Änderung scheitern. Exakte historische ATP/WTA-Fälle reproduziert; eng begrenzter vollständiger Sechsdatei-Versionsübergang gerade in Implementierung, Plan WTA Task2. Keine alte Prognose umschreiben und keine Hashprüfung pauschal lockern.
- `49ad632` plus `0df6707`: verlustfreie deduplizierte Fußball-Originalspeicherung fertig, inklusive korrigierter exakter4MiB-Grenze. Betroffener Erstlauf356passed/4skip, Fixlauf93passed/4skip; unabhängiges Nachreview SPEC/QUALITY PASS. Synthetischer380-Zeilen-Fall:826589Bytes expandiert,230689Bytes einmaliger Nutzinhalt, unveränderte Folgeberechnung271Bytes. Das ist ein Speicherbaustein, **noch keine Live-Scanneranbindung oder aktivierte Verletzungswirkung**. Fußballplan Task1 abgeschlossen,Tasks2/3 offen.
- Frische Tennis-Ergebnisinventur:995 Originalpublikationen,122 unterschiedliche native Paarungsidentitäten,101 verschiedene exakt outcome-gebundene Spiele(2ATP/99WTA). Keine weiteren abgeschlossenen Fälle aus vorhandenen normalisierten Statusdaten sicher nachbindbar. Fehlende Gewinnerbelege und wiederverwendete Provider-IDs bleiben explizit ungeklärt; kein künstliches Hochzählen wiederholter Originale. Weitere elf Identitäten zuletzt geplant/laufend.
- Die bereits genehmigte Drei-Kopien-Bereinigung und der geschützte Export sind abgeschlossen; nicht wiederholen. Acht **zusätzliche** alte QA-/Recovery-Ziele (2.432.557.056 Bytes) wurden zur geschützten Archivierung/Wiederherstellungsprüfung/Entfernung angefragt, noch keine Antwort. Reserve während laufendem Wettfinder: 22.314.248.192 Bytes nötig, 18.987.212.800 frei, 3.327.035.392 fehlend plus Codebereitstellung. Der zusätzliche Verlust ist read-only geklärt: PID560381 im Wettfinder hält fd3 einer bereits entlinkten temporären Datei, 1.182.539.776 Bytes. Kein neuer dauerhafter Bestand; kein Pfad zum Löschen, keinen Prozess für Speicher beenden. Nach natürlichem Abschluss Reserve erneut prüfen. Acht Ziele noch nicht verarbeitet, keine Schutzgrenze verändert.
- Nächster Softwareabschluss: historische Replay-Kompatibilität fertigstellen/reviewen, einmalige volle aktuelle Suite, Gesamtreview, dann gezielter Commit/Push. Serverrelease erst mit ausreichend echter Reserve und vollständiger Freigabe. Nochmalige ursprüngliche Spezifikations-, Worktree- oder allgemeine Push-Freigabe nicht erforderlich.
- Fachlich weiter offen: Fußball-Live-Original/B1-Anschluss, ursprüngliche Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeit-/Belastungsdaten, durchgängiger Fixture-Inkarnationsvertrag, weitere Sportarten außer Cricket, eigenständige Effektqualifikation und Nutzerabnahme. Mindestens200 unabhängige unangetastete Testevents in drei Zeitblöcken plus getrenntes Training/Tuning bleiben erforderlich;101 Spiele sind kein Qualitätsnachweis. Keine Gesamtfertigmeldung.

Belege lokal: jeweilige `.superpowers/sdd/2026-09-18-*/`-Ledger, `output/playwright/wta-isolated-build-20260918.md`, `tennis-replay-locator-compatibility-20260918.md`, `tennis-outcome-coverage-inventory-20260918.md`, `release-reserve-inventory-20260918.md`. Alte ungetrackte Ausgaben/QA-Verzeichnisse unverändert erhalten.

## Fortsetzung 18.09.2026, 17:50 CEST – hat Vorrang vor alten Angaben

- Release abgeschlossen: Lokal, GitHub-main und VPS auf `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9` (Funktionsstand `afc8a10`). App/Caddy aktiv, interner und öffentlicher Healthcheck geprüft; sieben reguläre App-Timer plus separater Retention-Timer geplant. Frische VPS-Leseprüfung um 17:44 CEST bestätigt Commit und internen Healthcheck. Alte fehlgeschlagene Dienste nicht zurückgesetzt.
- Die drei ausdrücklich freigegebenen verwaisten Prüfkopien wurden nach vollständiger Archiv-/Wiederherstellungsprüfung entfernt. Geschützte lokale Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-release-recovery`; Archiv und Manifest geprüft. Nur die zusätzliche Server-Transportkopie wurde anschließend entfernt. Produktionsdatenbanken und reguläre Backups blieben erhalten. Diese Bereinigung nicht wieder beginnen.
- Nach dem Release: 489 neue Belege, davon 151 Tennis-Ergebnisbelege für 101 verschiedene Spiele (2 ATP, 99 WTA); 338 Status-/Belastungsbelege separat. 850 frühere Originalpublikationen gebunden, **nicht** 850 unabhängige Testspiele. Probe bleibt fachlich teilweise vollständig; Bindungsprüfung ohne Fehler, kein kompletter Quellen-/Replay-/Qualitätsnachweis.
- Echter Wettfinderlauf 17:08 bis etwa 17:19 CEST erfolgreich, 81 Modellprognosen, 0 vollständig bestätigte Tipps. Keine neue Verletzungs-/Müdigkeitswirkung freigegeben.
- Konkurrierender Ergebnisschreibversuch scheiterte zuvor an `database is locked`; ruhender Wiederholungsversuch erfolgreich. Ursache im echten Karten-Leser reproduziert: CPU-Prüfung/Projektion hält eine Lesetransaktion. Bootstrap allein zu überspringen behebt es nicht. Reparatur läuft im vorhandenen Worktree; Plan `docs/superpowers/plans/2026-09-18-context-consumer-lock.md`. Weitere Langleser und physische Snapshot-Dauer bleiben separat zu prüfen.
- WTA-Ursache frisch geklärt: alter Downloadpfad 404; Upstream veröffentlicht einen neuen HTTPS-Prefix. Aktueller Payload: 2075 Zeilen bis 12.09., bestehende Inhalts-/Regressionsprüfungen bestanden. Noch kein Codefix/Produktivrefresh aus dieser reinen Quellenprüfung. Plan `docs/superpowers/plans/2026-09-18-wta-source-locator.md`.
- Fußball-Live-Original-/Provenienzanschluss wird konkretisiert; noch keine zusätzliche Wirkung aktiv. Tennis Abstract enthält tatsächliche Dauer für eine Teilmenge, der bestehende Loader verwirft sie. Keine tatsächliche Endzeit daraus ableiten. ATP-Turnierdatum bleibt kein Matchdatum.
- WTA `183854` ist als tatsächliche Provider-ID-Wiederverwendung geklärt: zuerst native Teilnehmer `2731/6769`, später `2731/2441`. Kein bloßer Terminwechsel. Die alte Prediction 1409 und ihre Revision blieben korrekt unverändert/offen; kein falsches Endergebnis zugeordnet. Eine durchgängige neue interne Spiel-Inkarnation für die Ersatzpaarung ist noch zu implementieren (Shadow, Refresh, Originale, Outcome, Settlement gemeinsam), nicht die Identitätsprüfung lockern. Diagnose `output/playwright/wta-183854-identity-20260918.md`.
- Consumer-Lock-Fix `185812e` lokal committed, unabhängig ohne Befund geprüft; 472 betroffene Tests bestanden, 5 bestehende Skips. Noch nicht gepusht/deployed. Gesamte aktuelle Testsammlung: 10062 Tests erfolgreich gesammelt; Sammlung ist kein bestandener Testlauf.
- WTA-Locator-Fix `b342b02` ebenfalls lokal committed und unabhängig ohne Befund geprüft; 159 betroffene Tests bestanden, 3 bestehende Skips. Echte isolierte HTTPS-Probe erfolgreich mit 2075 Zeilen bis 12.09.2026. Noch kein Produktivrefresh/Training und kein Deployment daraus ableiten.
- Der nächste sichere Release benötigt beim frischen Reservecheck rund 2,14 GB mehr freien Platz plus Codebereitstellung. Keine erneute alte Bereinigung oder pauschale Backup-Löschung; weitere alte Prüfkopien werden nur inventarisiert. Live-Kontextdatenbank: 1.939.492.864 Bytes. Neuer Fußball-Originalpfad muss feste Inhaltsblöcke wiederverwenden; vollständige Historienkopien pro Berechnung würden erhebliche vermeidbare Datenmengen erzeugen.
- Acht konkrete weitere Prüf-/Recovery-Bestände (2.432.557.056 Bytes) sind inventarisiert; geschützter Export, vollständige Wiederherstellungsprüfung und anschließende genaue Entfernung wurden angefragt, **noch nicht freigegeben oder ausgeführt**. Details `output/playwright/release-reserve-inventory-20260918.md`. Alte drei Ziele und altes Exportarchiv nicht verwechseln. Selbst nach Freigabe Reserve frisch prüfen, nicht trotz zu wenig Platz deployen.
- Fußball-Originalspeicherung wird als verlustfreier fester Inhaltsblock-Speicher implementiert; Plan `docs/superpowers/plans/2026-09-18-football-live-originals.md`, Task 1 im zugehörigen SDD-Ledger. Live-Scanneranbindung und Budget-/Aktivierungsprüfung folgen separat; noch keine neue Original-Publikation auf dem VPS aktiv.
- Weiter offen: vollständige Konkurrenz-/Tageslaufprüfung, WTA-Identitätsfall, Fußball-Live-Integration und verwendbare Spieler-Kohorten, echte Zeit-/Belastungsdaten, weitere Sportarten außer Cricket, empirische und Nutzerfluss-Abnahme. Basisprognosen bleiben unabhängig vom Preis sichtbar. Keine Gesamtfertigmeldung.

Aktuelle Arbeitsbasis: `output/playwright/context-outcome-release-20260916.md`, `output/playwright/context-lock-rootcause-20260918.md`, `output/playwright/tennis-data-coverage-20260918.md`. Ungetrackte Diagnosen erhalten; verbindliche Restliste unten bleibt offen, soweit hier nicht ausdrücklich als erledigt belegt.

## Historische Übernahme 18.09.2026, 16:00 CEST

- **Nicht alles erledigt.** Funktionscommit `afc8a10` lokal und GitHub-main,
  **VPS weiterhin `9659c49`**. Spätere Dokumentationscommits sind kein Deployment.
- Das Update vom 16.09. wurde unterbrochen; App war gestoppt/deaktiviert.
  Nach Prüfung des unveränderten Git-Arbeitsbaums und vollständigen
  Migrationsmarkers wurde der alte Stand wieder gestartet/aktiviert.
  Beide Healthchecks `ok`, sieben reguläre App-Timer gestartet/aktiviert.
  Tennisfehler nicht zurückgesetzt, kein erfolgreicher Gesamtjob behauptet.
- Erneutes entkoppeltes Update brach vor App-Stopp an der unveränderten
  Kapazitätsprüfung ab: 21.264 GB Reserve nötig, 16.313 GB frei;
  rund **4.61 GiB fehlen**. Drei eigene verwaiste Prüfkopien inventarisiert,
  noch nicht gelöscht; genaue Freigabe angefragt. Keine produktive DB oder
  reguläre Sicherung löschen, keine Schutzgrenze lockern.
- `afc8a10`: Tennis-Ergebnisse auch bei belegten Terminrevisionen; ungültige
  Fußball-Spielerprojektion verwirft nicht mehr andere gültige Spiele im Batch.
  **Frisch 162 Tests bestanden**, Exit 0, 34.88 s, DeprecationWarnings als Fehler.
  Ältere 519/193-Läufe nicht addieren; keine neue Vollsuite behaupten.
- Inventur 18.09., 13:50:35 UTC: 986 Tennis-Originalartefakte, fünf Ergebnisbelege
  für nur ein eindeutiges Spiel. Fußball: 272 Spieler-Einsatzbelege / zehn Spiele;
  4.633 Ergebnisbelege / 235 Spiele. Belegzeilen sind keine unabhängigen Testfälle.

### Nächste konkrete Schritte

1. Reserve sicher herstellen, dann nur den installierten vertrauenswürdigen
   Updater nutzen, keinen produktiven Git-Pull. Funktionsziel `afc8a10`;
   bei weiterem Docs-Commit origin/main-Anforderung des Updaters prüfen.
2. Erst danach echte Tennis-Ergebnisprobe speichern und Original-/Event-/
   Terminbindung nachweisen. Entwurf `output/playwright/capture-context-outcomes-20260916.py`
   ist noch nicht ausführungsbereit: `inventory()` fragt fälschlich
   `context_observations.source_schema` ab; Schema liegt im Inhalts-Payload.
   Vor Ausführung korrigieren. Diese Übernahme schrieb keine Kontextdaten.
   Fußball-Probe muss API-Budget und 24h-Backoff respektieren.
3. Fußball-Live-Lücke schließen: `fixture_market_probabilities()` reicht
   `native_provenance` nicht weiter; Originale haben noch
   `unresolved-receipts-not-in-this-capture`. Replay ist bereits verbunden.
   Dieselbe Live-Berechnung mit echten B1-Belegen zum Stichtag verbinden,
   Referenzraten/Kalibrierung/Originale erhalten; danach kompatibler Snapshot-
   Anschluss. Separat kalibrierte Legacy-Marginalen nicht als kohärentes neues
   Torverteilungsmodell umetikettieren. Teilnahme-/Aufstellungsmischung offen.
4. Tennis-Zeitdaten: ESPN-Proben ohne tatsächliche Matchdauer/Endzeit. ATP-CSV
   enthält 8.980 Dauerwerte in 9.736 Zeilen, aber kein Matchdatum. Turnierbeginn
   oder Zeilenfolge sind kein Ersatz. Einzelne offizielle ATP-Seitenprobe war
   mit dem Browserwerkzeug nicht zugänglich; kein Beleg für fehlende Felder
   oder HTTP 403. Quellen-/Zeitsemantik vor versionierter Erweiterung prüfen.
5. Unverändert mindestens 200 eindeutige unangetastete Testevents in drei
   Zeitblöcken zusätzlich zu Training/Tuning. **Keine freigegebene neue Wirkung
   und keine belegte bessere Wettqualität.** WTA, weitere Sportarten und
   Produktabnahme bleiben offen. Cricket bleibt ausgenommen.

Details: [Übernahmebericht](docs/audits/2026-09-18-kontext-fortsetzung.md).

## Historischer Stand 16.09.2026

Stand: **16.09.2026, 01:10 CEST**. Für die Fortsetzung zuerst dieses Dokument
lesen. Es aktualisiert den Arbeitsstatus, ersetzt aber weder die freigegebene
Spezifikation noch ältere Prüfbelege. Bei späterer Übernahme Git/VPS und letzten
Jobabschluss frisch prüfen; die Zahlen unten sind datierte Beobachtungen.

## Auftrag und feste Regeln

- An der App und ihrer fachlichen Qualität weiterarbeiten; die abgeschlossene
  Speicherbereinigung nicht wieder zum Hauptprojekt machen.
- Fußball und Tennis zuerst, danach Basketball, Eishockey und E-Sport.
  **Cricket bleibt ausdrücklich ausgenommen.**
- Verletzungen, Besetzung und Belastung sollen die Modellrechnung nachweisbar
  beeinflussen. Fehlende Daten sind nicht null; keine erfundenen Abschläge.
- Quoten verändern weder Prognose noch Modellreihenfolge und blenden keine
  berechenbare Prognose aus. Keine pauschalen Wettartenverbote; Preis separat.
- Keine gegensätzlichen Haupttipps für dasselbe Spiel. Kurze, belegte Begründung
  sichtbar statt interner Prüfbegriffe; keine erfundenen Vorteile.
- Spezifikation, Umsetzung und isolierter Worktree sind bereits freigegeben.
  Keine erneute Design-/Namens-/Arbeitskopie-Freigabeschleife. Geprüfte Änderungen
  wie beauftragt committen, pushen und kontrolliert deployen.
- Kein Echtgeld automatisch setzen, keine Kontohistorie ändern, keine neue
  kostenpflichtige Quelle ohne gesonderte Zustimmung.

## Erledigt / nicht erneut beginnen

- [x] Speicher-/Backupbereinigung und zugehörige Wartung: Funktionsstand `5069e75`.
  Keine Produktionsdatenbank und kein echtes Backup für weitere Reserve löschen.
- [x] Tennis-Live-Originale an Fallaufbau, Training, Evaluation, Transportprüfung
  und Live-Effektauswahl angebunden: `9d271c1` und `9659c49`.
  Typ: `tennis-live-winner-status-load-antisymmetric-v1`.
- [x] Dieser App-Code committed, auf GitHub-main gepusht und explizit deployed.
  Geprüfter App-Commit: `9659c49b2738d6a4c7b0fcc7442a9e8ecef3b665`.
- [x] Softwareprüfung: 545 Tests im breiteren Zwischenstand; nach zwei letzten
  Korrekturen 144 betroffene Tests unter Windows und dieselben 144 unter Linux,
  jeweils mit DeprecationWarnings als Fehler. **Keine finale Vollsuite behaupten.**
- [x] Nur die eigene temporäre Tennis-QA-Kopie und Transportarchive entfernt;
  Code/Testquellen sind über Git wiederherstellbar. Ältere QA-Bestände erhalten.

## Tatsächlicher Betrieb – nicht mit Modellqualität verwechseln

- VPS-Commit um 01:09 CEST erneut `9659c49…`, App und Caddy aktiv.
  Interner/öffentlicher Healthcheck und acht geplante Timer nach dem Release
  geprüft. Timer berechnen und warten, **sie pullen/deployen keinen Code**.
- Tennis 16.09., 00:35:59–00:50:22 CEST: Gesamtjob **Exit 1 / failed**.
  WTA-Refresh `HTTPError`, letzter Ergebnisstand 26.07.; ATP `retained_fresh`,
  Datenstand 14.09. Die Touren bleiben getrennt.
- Spielscan 850 Sekunden, also diesmal unter 900 Sekunden: 73 gefundene
  noch nicht gestartete Einzelspiele, 40 vorbereitete Abschlussfälle,
  26.283 gespeicherte Spielbeobachtungen, 23 neue Predictions.
  Ein WTA-Event `183854` blieb mit `FixtureIdentityConflict` teilweise offen.
  Kein `reset-failed` und kein weiterer manueller Lauf zur Verschleierung.
- Kontextspeicher nach dem Lauf: **450 Tennis-Originalartefakte, 0 native
  Tennis-Endergebnisbelege**. Artefakte sind nicht gleich unabhängige Testspiele.
  Die separat abgerechneten 39 ESPN-Finals im bisherigen Shadow-Store beweisen
  keine Ergebnisanbindung des neuen Kontexttrainings.
- Peak des Tennisdienstes 2,7 GB RAM; CPU-Zeit 13 min 51,6 s. Kein allgemeiner
  Performance-Erfolg aus einem Lauf knapp unter dem Zeitlimit ableiten.
- Wettfinder 00:07–00:17: 59 Modellprognosen, Gesamtstatus `degraded` wegen
  Cricket. Fußball erfolgreich, Tennis-Refresh ohne operativen Fehler in diesem
  Wettfinderlauf. Cricket bleibt unverändert; kein Alle-Sportarten-Erfolg.

## Offene To-dos – in dieser Reihenfolge

- [ ] **P0 – echte Tennis-Ergebnisbelege nutzbar machen.** Zuerst nachvollziehen,
  warum trotz gespeicherter Originale und Shadow-Finals null passende
  `match_outcome`-Belege vorliegen. Der Erfassungscode existiert bereits; nicht
  blind neu bauen. Nachweisen, dass genau passende, normal beendete native
  Spiele mit tatsächlich vor Spielbeginn gespeicherten Originalen verbunden
  werden. Keine nachträglichen Originale, keine erfundenen Zuordnungen und
  keine Retirement-/Walkover-Labels als normale Siegergebnisse.
- [ ] **P0 – WTA-Datenabruf reparieren.** HTTP-/Inhaltsfehler reproduzieren,
  gültige aktuelle Quelldaten beziehen und Tour-Frische beweisen. ATP darf
  unabhängig weiterlaufen; alten WTA-Stand nicht als frisch ausgeben.
- [ ] **P0 – Spielzuordnung WTA `183854` klären.** Native Revisionen/Teilnehmer
  gegen das unveränderliche Original vergleichen. Nur belegte Korrekturpfade
  zulassen; keine Historie überschreiben und Identitätsprüfung nicht abschalten.
  Danach echten Gesamtjob mit klar ausgewiesenem Ergebnis prüfen.
- [ ] **P1 – Laufzeitreserve belegen.** Die 850/900 Sekunden sind zu knapp.
  Teure Abschluss-/Historienabschnitte messen und gezielt verbessern, ohne
  Datenbelege wegzulassen. Parallelität mit Wettfinder auf SQLite-Locks/OOM
  prüfen; keine bloße Zeitlimit-Erhöhung als Reparatur verkaufen.
- [ ] **P1 – Fußball-Verletzungswirkung fertigstellen.** Vorhandene Erfassung
  für Spieler, Minuten, Rolle, Ersatz, Rotation und Erholung auf echte nutzbare
  Kohorten prüfen; Wirkung auf Tor-/Stärkeverteilung schätzen und alle betroffenen
  Märkte konsistent neu ableiten. Ausfallliste allein ist keine Modellwirkung.
- [ ] **P1 – Tennisbelastung vervollständigen.** Sätze, tatsächliche Dauer und
  Endzeit, Erholung sowie belegte Ausfälle und Umgebungsdaten anbinden, soweit
  die Quelle sie tatsächlich liefert. Der aktuelle ESPN-Kontext belegt keine
  echten Matchminuten/Endzeiten. Beobachtete Erholungs-Untergrenzen nicht als
  gemessene Fünfsatz-Müdigkeit ausgeben. Native historische Namens-/ID-Zuordnung
  bleibt ungeklärt; der neue Live-Pfad ersetzt diesen Nachweis nicht.
- [ ] **P1 – empirische Wirkung nachweisen und erst dann aktivieren.** ATP/WTA
  und Modellfamilien getrennt; mindestens 200 eindeutige Testevents in drei
  Zeitblöcken, unverändert vereinbarte Brier-/HAC-/BH-, Verteilungs- und
  Kalibrierungsprüfungen. Kleine synthetische Tests oder hohe Trefferquoten
  reichen nicht. Bis zum Nachweis bleibt die Basisprognose unverändert.
- [ ] **P1 – Auswahlqualität im echten Nutzerfluss abnehmen.** Wettfinder,
  RisikoBet und Daily3 auf aktualisierte Modelle, Marktvielfalt, keine
  widersprüchlichen Hauptkarten sowie kurze sachliche Pro-/Contra-Begründung
  prüfen. Fehlende/kleine Quoten dürfen den Modellpool nicht verändern.
  Keine Mindestzahl an Tipps erzwingen und keine Profitabilität behaupten.
- [ ] **P2 – Basketball/Eishockey/E-Sport vervollständigen.** Vorhandene Adapter
  und die früheren Teilreviews zuerst inventarisieren; fehlende Aufstellungs-,
  Spieler-/Torhüter-, Belastungs- und Kaderbelege gezielt schließen. Implementierte
  Hüllen nicht als empirisch aktive Sportmodelle abhaken. Cricket nicht anfassen.
- [ ] **P2 – abschließende Regression/Produktabnahme.** Historische Native-/QA-
  Pins und offene Teilplanbefunde gegen den heutigen Code prüfen; keine Pins
  pauschal umschreiben. Für jedes Teilrelease getrennt Software, verwendbare
  Daten, empirischen Status, tatsächliche Aktivierung und Browser/VPS belegen.

Daily3 ist technisch live; Name **„3 a day keeps the job away“**, höchstens
CHF 50 eigenes Geld pro Tag, Gewinne können weiterverwendet werden,
kein Nachschuss über dieses Tagesbudget hinaus.
Die Qualität/Verfügbarkeit der Auswahlen bleibt Teil der offenen Abnahme. Keine
Gewinngarantie oder Behauptung täglich sicherer CHF 150.

## Einstieg für den nächsten Account

1. Git-Root `C:/Projekt/BetBoy/betboy-app`; aktiver Arbeitsstand in
   `.worktrees/context-capacity-recovery-20260910`, Branch
   `codex/context-capacity-recovery-20260910`. Main enthält denselben App-Code.
   Dokumentationsfolgecommits sind kein neuer produktiver Funktionsstand.
2. [Übergabe](PC_WECHSEL_UEBERGABE.md), [freigegebene Spezifikation](docs/superpowers/specs/2026-09-07-kontextmodell-design.md),
   [20-Aufgaben-Plan](docs/superpowers/plans/2026-09-07-kontextmodell-umsetzung.md),
   [Tennis-Vertrag](docs/audits/2026-09-15-tennis-live-training.md) und
   [Datenpfad](docs/audits/2026-09-15-kontext-datenpfad.md) lesen.
3. Konkrete Startdateien: `context_models/tennis_training.py`,
   `tennis/live_context.py`, `context_models/tennis_live.py`,
   `scripts/tennis_daily.py`, `scripts/run_daily_pipeline.py` und zugehörige Tests.
4. Ausführlicher lokaler Abschlussbeleg:
   `output/playwright/tennis-live-training-release-20260916.md` im Worktree.
   Bewusst ungetrackt; die entscheidenden Zahlen stehen deshalb auch hier.
5. Nur VPS `betboy-vps` schreibt/schedult produktiv; App `/opt/betboy/app`.
   Deployment ausschließlich über den vorhandenen vertrauenswürdigen Updater,
   nicht durch direkten produktiven Git-Pull. Bei einem späteren Deployment
   auch `activating`-Worker beachten, nicht nur `is-active`.
6. Vorhandene ungetrackte Audits, `.playwright-cli/`, `output/playwright/` und
   `qa19-*` erhalten. Kein `git add .`, Reset/Clean oder pauschales Löschen.
   Python lokal: `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`.
   Tests isoliert, kein pytest in die produktive VPS-venv installieren.

**Nächster konkreter Arbeitsschritt:** read-only den fehlenden Tennis-
Endergebnisübergang vom bestehenden Quellenempfang zum Kontextspeicher
reproduzieren; danach gezielter Regressionstest und kleinster belegter Fix.
