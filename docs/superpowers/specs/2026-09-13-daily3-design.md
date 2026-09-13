# 3 a day keeps the job away — Produktspezifikation v1

Stand: 13.09.2026. Interne Feature-ID: `daily3`.
Status: Die unten bezeichneten Nutzerregeln sind bestätigt. Die daraus
abgeleitete technische/UX-Fassung ist ein Entwurf zur Prüfung, kein bereits
implementiertes oder für Echtgeld freigegebenes Produkt.
Repository-Bezug: Reparaturbranch `codex/context-capacity-recovery-20260910`,
gelesener Code `9ccdf4262c7e69ee73160eb31540e0a4a2851ba7`.

## 1. Problem und Nutzer

Der Nutzer möchte höchstens drei verständlich begründete Einzelwetten pro Tag
mit echten, selbst bestätigten Einsätzen verfolgen. Die bisherige Oberfläche
zeigte unübersichtliche, teilweise gegensätzliche oder wenig aussagekräftige
Auswahlen; hohe Modellprozente allein liefern weder eine nützliche Entscheidung
noch ein verlässliches Einkommen. Der neue Bereich verbindet eine begrenzte
Tagesauswahl mit einer nachvollziehbaren Einsatz- und Ergebnisrechnung.

## 2. Bestätigte Produktregeln

| Regel | Bestätigter Inhalt |
| --- | --- |
| Öffentlicher Name | Exakt `3 a day keeps the job away` |
| Währung | CHF, intern ganze Rappen |
| Eigenes Tagesbudget | Maximal CHF 50,00 |
| Anzahl | Höchstens drei Einzelwetten auf unterschiedliche Spiele |
| Gewinne | Bereits abgerechnete Gewinne dürfen innerhalb des Tages weiterverwendet werden |
| Verlustgrenze | Maximal CHF 50,00 netto gegenüber dem Tagesstart; kein Limit vom Zwischenhöchststand |
| Nachzahlen | Kein zusätzlicher Eigenmittel-Nachschuss am selben Tag |
| Einsatzautomatik | Kein automatisches All-in; das Tagesbudget ist kein fester Einsatz pro Wette |
| Echtgeld | Kein verpflichtender virtueller/Paper-Modus für den Nutzer |
| Bedienung | Nutzer bestätigt und platziert selbst; keine automatische Buchmachertransaktion |
| Gewinnziel | CHF 150 netto als Wunschziel, weder Tagespflicht noch Einkommenszusage |

Vom Nutzer ausdrücklich bestätigtes Beispiel: CHF 50 -> CHF 120 -> CHF 0
ergibt CHF 50 Nettoverlust. Die zwischenzeitlichen CHF 70 Gewinn sind dann
ebenfalls verloren; das Produkt darf sie nicht als geschützten Gewinn darstellen.
Entwickler-, Regressions- und Abrechnungstests bleiben erforderlich und sind
kein dem Nutzer vorgeschriebener virtueller Wettmodus.

## 3. Ziele und Nicht-Ziele

Ziele:

1. Jede Hauptkarte erklärt Auswahl, Gegenargument, Datenstand und Preis ohne
   Aufklappen; keine gegensätzlichen Daily3-Auswahlen zum selben Event.
2. Jede zulässige neue Einsatzreservierung hält die Tagesrisikorechnung ein,
   auch bei zwei Tabs, Wiederholungen, offenen Spielen und späteren Gewinnen.
3. Jeder bestätigte Einsatz und jede Abrechnung bleibt revisionsgebunden
   nachvollziehbar; Reloads erzeugen weder Geld noch zusätzliche Wettslots.
4. Modelle werden nicht nochmals geladen oder berechnet. Quote, Zielbetrag
   und verfügbare CHF dürfen Modellwerte und Modellauswahl nicht verändern.
5. Tatsächliche Nettoergebnisse einschließlich Verlusttagen werden vollständig
   angezeigt; keine Erfolgsdarstellung anhand nur gewonnener Wetten.

Nicht-Ziele v1:

- Keine Garantie von Sicherheit, positiven Erwartungswerten oder CHF 150 täglich.
- Keine Dreier-Kombi, Verlustprogression, automatische Nachschüsse oder
  Rückwärtsrechnung einer Mindestquote aus dem gewünschten Tagesgewinn.
- Keine Kontoführung beim Buchmacher, Zahlung, Auszahlung, automatische
  Wettplatzierung oder Durchsetzung eines buchmacherübergreifenden Limits.
- Kein Umbau der 15K-Konto-/Ticketregeln, kein neuer Modellkern und kein neuer
  Scanner/Timer; Cricket bleibt entsprechend der bisherigen Ausnahme außen vor.
- Kein neues Login-/Cross-Device-System und kein neuer Schlüssel-/Serviceaufbau
  als versteckte Voraussetzung dieses Entwurfs.

## 4. Nutzerabläufe

- Als Nutzer möchte ich das Tagesbudget einmal bestätigen und den verfügbaren
  Betrag erkennen, damit ein offener Einsatz nicht nochmals ausgegeben wird.
- Als Nutzer möchte ich nachvollziehen, warum eine Auswahl plausibel ist und
  was gegen sie spricht, bevor ich eine reale Quote und einen Einsatz bestätige.
- Als Nutzer möchte ich einen tatsächlich abgerechneten Gewinn weiterverwenden
  können, ohne dass mir eine neue Einzahlung oder ein vierter Tipp angeboten wird.
- Als Nutzer möchte ich bei fehlender Quote weiter die Prognose sehen; der
  Preis und eine mögliche Auszahlung bleiben offen, bis eine reale Quote vorliegt.
- Als Nutzer möchte ich verlorene, stornierte und korrigierte Wetten ebenso
  nachvollziehen wie Gewinne und meinen Tag jederzeit freiwillig beenden können.
- Als Betreiber möchte ich Abrechnungs- und Datenfehler untersuchen können,
  ohne technische Sperrlisten oder interne Prüfbegriffe in die Hauptkarten zu kippen.

## 5. Tagesrechnung — verbindliche mathematische Ableitung

Alle Geldwerte werden als ganze Rappen verarbeitet; kein binärer Float für
Kontostände oder Risikoprüfungen. Dezimalquoten werden separat exakt verarbeitet.
Eingaben, Zwischensummen und Speicherung müssen denselben geprüften
Ganzzahlbereich verwenden; Überlauf, stilles Abschneiden und boolesche Werte
als Geldbeträge sind unzulässig. Eine akzeptierte Dezimalquote muss endlich
und größer als 1 sein; das ist Formatprüfung, keine Qualitäts-Mindestquote.

Für genau einen Tageslauf:

- `D = 5000`: einmaliges Eigenmittelbudget.
- `G`: Summe realisierter Nettoergebnisse abgerechneter Wetten, jeweils
  tatsächliche bestätigte Gesamtrückzahlung minus ursprünglichem Einsatz.
- `O`: Summe aller noch offenen, als platziert bestätigten Einsätze.
- `R`: Summe noch nicht platzierter, aktiver Einsatzreservierungen.
- `A = D + G - O - R`: noch frei reservierbarer Betrag.
- `W = G - O - R`: Nettoergebnis, falls sämtliche offenen/reservierten
  Einsätze verloren gehen; keine erwarteten Gewinne werden gegengerechnet.

Eine neue Reservierung `s` ist nur zulässig, wenn `s` ganze positive Rappen
umfasst, `s <= A` und `G - O - R - s >= -5000`. Bereits platzierte Wetten und
aktive Reservierungen belegen zusammen höchstens drei Wettslots.
`A` ist eine Obergrenze, keine Empfehlung, diesen Betrag vollständig einzusetzen.

Beim Bestätigen einer Platzierung wandert der Betrag atomar von `R` nach `O`;
er wird nicht zweimal abgezogen. Bei Abrechnung verschwindet der Einsatz aus
`O`, und genau Rückzahlung minus Einsatz verändert `G`. Bei einem vollständigen
Void wird der Einsatz zurückgezahlt; er erzeugt keinen Gewinn.

### Rechenbeispiele, keine Einsatzempfehlungen

| Situation | G | O | R | A | W |
| --- | ---: | ---: | ---: | ---: | ---: |
| Tagesstart | 0 | 0 | 0 | 50 | 0 |
| CHF 20 reserviert | 0 | 0 | 20 | 30 | -20 |
| Diese CHF 20 platziert | 0 | 20 | 0 | 30 | -20 |
| CHF 20 verloren | -20 | 0 | 0 | 30 | -20 |
| Danach CHF 30 reserviert | -20 | 0 | 30 | 0 | -50 |
| CHF 50 wurden mit CHF 120 Gesamtrückzahlung abgerechnet | 70 | 0 | 0 | 120 | 70 |
| Diese CHF 120 ausdrücklich neu reserviert | 70 | 0 | 120 | 0 | -50 |
| Auch diese Wette später verloren | -50 | 0 | 0 | 0 | -50 |

Alle Tabellenbeträge sind CHF. Eine Folgewette mit CHF 31 nach CHF 20 Verlust
wäre unzulässig. Eine zusätzliche CHF 50 Gutschrift nach einem Reload ebenfalls.

## 6. P0 — Mindestanforderungen und Abnahme

### P0.1 — Sichtbare, begründete Auswahl

- Höchstens drei aktive Tagesauswahlen, maximal eine pro kanonischem Event,
  einschließlich bereits reservierter/platzierter Auswahlen. Vor der Kürzung
  wird der vollständige vorhandene Kandidatenpool auf Kohärenz geprüft.
- Keine pauschalen Verbote von Team-Unter 1,5 oder Über 0,5. Eine Hauptkarte
  benötigt jedoch eine konkrete datenbasierte Begründung; bloß ein hoher
  Prozentwert oder eine triviale Marktbezeichnung reicht nicht als Erklärung.
- Fehlende/zu niedrige/veraltete Vergleichsquoten löschen oder sortieren keine
  Prognose um. Es gibt keinen Quotenfilter, der CHF 150 erzwingen soll.
- Die Modellauswahl darf keine preisabhängigen `RELEASED`-Flags als Ersatz
  für preisunabhängige Modellqualität übernehmen. Preisbewertung bleibt getrennt.
- Gibt es weniger geeignete Auswahlen, werden weniger gezeigt. Keine
  Platzhalterspiele, erfundenen Prozentwerte oder künstlichen Nachfülltipps.
- Die fachliche Tagesrangfolge muss vor Codefreigabe versionsgebunden festgelegt
  werden. Kein angeblich sportübergreifender Sicherheitsscore aus unkalibrierten
  Prozenten und kein stilles Kopieren der bisherigen 15K- oder UI-Rangregeln.

Abnahme: Gleiches Modell bei geändertem Preis/Budget/Ziel ergibt identische
Prognosen und Modellauswahl. Heim-/Auswärtssieg desselben Events stehen nie
als zwei gleichzeitig aktive Daily3-Vorschläge. Alternative Märkte bleiben
im normalen Modellkatalog erhalten, auch wenn sie nicht zur Tagesauswahl gehören.

### P0.2 — Ehrliche Kontext- und Preisangaben

Kurzer sichtbarer Text mit konkretem Pro und Contra. Verletzungen, Müdigkeit,
Belag und Wetter werden nur als eingerechnet bezeichnet, wenn der verwendete
Modellstand ihren tatsächlichen numerischen Einfluss belegt. Eine geladene
Ausfallliste oder `Wetter geprüft` ist allein kein Vorteil und kein Recheneffekt.
Modellwerte bleiben als Schätzungen erkennbar; keine Bezeichnung als sichere Wette.

Für eine neue Echtgelderfassung werden die tatsächlich akzeptierte Quote,
exakter Markt/Linie/Zeitraum/Teilnehmer, Einsatz und Zeit erfasst. Ohne reale
Quote bleibt die Prognose sichtbar, aber keine bestätigte Auszahlung wird
erfunden. Eine niedrige Quote ist Preiswarnung, keine Modell- oder Importsperre.
Die Erfassung einer tatsächlich platzierten Wette ist kein Gütesiegel der App.

Abnahme: Quoten-/Marktänderung invalidiert nur eine noch offene Preis-/Einsatz-
Bestätigung, nie rückwirkend den gespeicherten Vertrag einer platzierten Wette.
Bei unklarer Eventidentität oder beschädigten Daten erfolgt keine neue
Budgetfreigabe; bestehende reale Aufzeichnungen bleiben sichtbar.

### P0.3 — Einsatz, Slots und offene Beträge

Entwurfsentscheidung v1: Betragseingabe mit ausdrücklicher Nutzerbestätigung,
kein automatisch vorbelegter All-in-Betrag und keine erfundene Kelly-/Prozent-
Formel. Eine spätere automatische Einsatzempfehlung ist ein eigener Vertrag.
Nur abgerechnete Rückzahlungen sind wieder verfügbar, nicht erwartete oder
nur als gewonnen vermutete Ergebnisse. Preisvorschau ist nicht Kontogutschrift.

Jede Reservierung, Platzierung und Abrechnung erhält eine eindeutige
Idempotenzkennung. Budget- und Slotprüfung plus Zustandsänderung erfolgen in
derselben Datenbanktransaktion. Dieselbe Anfrage darf weder doppelt abbuchen
noch zweimal gutschreiben. Negative/Null/NaN/Infinity-/Subrappen-Einsätze ablehnen.

Vor Platzierung wirklich verworfene Reservierungen geben ihren Betrag/Slot
wieder frei; eine Zeitüberschreitung oder fehlende Rückmeldung vom Nutzer
beweist kein Nichtplatzieren und gibt deshalb nichts automatisch frei.
Eine tatsächlich platzierte und später stornierte/void gewertete Wette zählt
weiter als eine der höchstens drei Wetten. Kein vierter Ersatz nach Verlust/Void.

Abnahme: Zwei Tabs können zusammen nicht CHF 60 aus denselben CHF 50 reservieren.
Nach CHF 20 Verlust bleiben höchstens CHF 30 frei. Nach drei Platzierungen gibt
es keine weitere Freigabe, auch nach Reload, Preisrefresh oder Ergebnisrevision.

### P0.4 — Tageswechsel und Nutzerscope

Zeitbasis als Entwurf: serverseitiger Kalendertag `Europe/Zurich`, Zeitstempel
zusätzlich in UTC. Pro dauerhafter Nutzer-ID und Zürcher Datum nur ein Tageslauf.
Kein automatisches Nachfüllen, kein Reset über Clientuhr, Sessionneustart oder Tab.

Konservative v1-Entwurfsentscheidung: Solange ein vorheriger Tageslauf noch
offene Platzierungen, ungeklärte Reservierungen oder Korrekturen hat, wird kein
neues Tagesbudget freigegeben. Die Modellansicht bleibt zugänglich. Nach Abschluss
beginnt ein neuer Tag nur durch ausdrückliche Bestätigung und wieder höchstens
mit CHF 50; alte Gewinne/Restbeträge werden nicht automatisch hinzuaddiert.
Diese Übernachtregel ist neu vorgeschlagen, nicht bereits vom Nutzer bestätigt.

Der vorhandene Browser-Nutzerscope ist kein verifiziertes personen- oder
buchmacherübergreifendes Konto. Das Limit gilt nur für diesen dokumentierten
Daily3-Bereich. Ein neuer Browser, fremde Konten oder Wetten außerhalb der App
können damit nicht zuverlässig begrenzt werden; keine anderslautende Zusage.

Abnahme: Sommer-/Winterzeit, Mitternacht, zwei Sitzungen und offene Spiele vom
Vortag werden geprüft. Keine anonyme Ersatz-ID bei fehlendem dauerhaftem Scope.

### P0.5 — Ergebnisse, Korrekturen und echte Einsatzdaten

Platzierungen speichern den unveränderlichen Modell-/Event-/Marktstand und die
tatsächlich bestätigte Quote/Stake. Neue Modellstände überschreiben alte
Entscheidungen nicht. Automatische Modellabrechnung und tatsächliche
Buchmacherabrechnung sind getrennt kenntlich; fehlender Beleg bleibt offen.

Marktspezifische Push-, Teilgewinn-/Teilverlust- und Void-Regeln dürfen nicht
in ein unzutreffendes binäres WON/LOST gepresst werden. Fehlt eine passende
Abrechnungsintegration, bleibt der Beleg offen beziehungsweise die tatsächliche
Nutzerabrechnung ausdrücklich unbestätigt; keine Fantasiegutschrift für Folgewetten.
Bestätigte reale Gesamtrückzahlungen sind die Geldquelle, nicht eine neuere
Vergleichsquote oder ein nachträglich veränderter Modellwert.
Berechnete Auszahlungen bleiben ausdrücklich Vorschauen. Tatsächliche
Rundungen und Gebühren dürfen nicht als zusätzliche Kaufkraft verschwinden;
ihre Erfassung gehört zum noch festzulegenden Abrechnungsvertrag.

Ergebnisrevisionen werden als verknüpfte Korrektur protokolliert, nicht durch
Löschen alter Buchungen. Ergibt eine nachträgliche Buchmacherkorrektur einen
negativen verfügbaren Betrag, wird dieser ehrlich ausgewiesen und jede neue
Reservierung gestoppt; keine Ausgleichsgutschrift. Die App kann solche externen
Revisionen oder falsch gemeldete reale Einsätze nicht als stets innerhalb CHF 50
garantieren. Außerhalb des Limits bereits getätigte Wetten dürfen zur ehrlichen
Historie als Abweichung erfasst, aber nicht rückwirkend als zulässig freigegeben werden.

Abnahme: Doppelte/verspätete Resultate, widersprüchliche Abrechnungen, offene
Wetten, Teilrückzahlungen und Korrekturen erzeugen keine doppelte Kaufkraft.

### P0.6 — Flache Oberfläche und freiwilliges Beenden

Entwurf: eigener Bereich innerhalb des Wettfinders; kompakter Zugang `3 a day`,
volle bestätigte Überschrift auf der Seite. Die bestehende fünfteilige
Hauptnavigation wird nicht ungeprüft um eine sechste schmale Mobile-Schaltfläche ergänzt.

Sofort sichtbar: Tagesdatum, eigenes Budget, verfügbarer Betrag, offene Einsätze,
realisierter Nettostand und genutzte Slots. CHF 150 ist eine zurückhaltende
Zielangabe, keine Aufforderung zu höheren Einsätzen oder zum Nachholen von Verlusten.
Darunter höchstens drei flache Karten mit Warum/Gegenargument, Datenstand,
getrennter Quote sowie Einsatz-/Gewinn-/Verlustvorschau. Nur Belegdetails optional.
`Für heute beenden` bleibt jederzeit verfügbar; offene Wetten werden dabei
nicht gelöscht, freigegeben oder vorzeitig abgerechnet. Kein automatischer Neustart.

Abnahme: 320/760/1080/1440px ohne horizontalen Überlauf; Kerninformationen und
Aktionen ohne verschachtelte Expander. Technische Betriebsdiagnose ausschließlich
in der Adminansicht. Sprachhinweis zum Risiko kurz, nicht als langer Sperrbericht.

### P0.7 — Betrieb und Nachweis vor Freigabe

Eigene Tagesrechnung, getrennt von `ChallengeLedger`/15K und ohne Migration
existierender Geldkonten. Dauerhafte Transaktionen, Zugriffsbegrenzung nach
Scope, vollständige Backups inklusive Belegen und tatsächlich geprüfter Restore.
Vor Echtgeld-Freigabe: definierte Modellauswahl, passender Abrechnungsvertrag,
Budget-/Nebenläufigkeitstests, Browserabnahme und kontrollierter Release.
Der momentan offene Kontext-/Speicher-Reparaturstand wird nicht durch ein
neues Feature als abgeschlossen erklärt. Keine neuen Timer oder VPS-Änderungen
im Rahmen dieser Spezifikation.

## 7. P1 und P2

P1: freiwilliges Monatslimit, freiwilliges Sichern eines Teils der Gewinne,
CSV-/Belegexport und übersichtliche Monatsbilanz. Monatslimit ist noch nicht
bestimmt; weder CHF 1500 noch ein unbegrenztes Budget als Nutzerfreigabe erfinden.
Die Anzeige aller täglichen Verluste bleibt bereits in v1 erforderlich.

P2: empirisch begründete automatische Einsatzempfehlung, verifizierte
geräteübergreifende Konten und geprüfte Buchmacher-Belegimporte. Keine
automatische Wettplatzierung als stillschweigender nächster Schritt.

## 8. Technische Anknüpfungspunkte — Code tatsächlich gelesen

| Vorhanden bei 9ccdf42 | Konsequenz für Daily3 |
| --- | --- |
| `app.py:PAGE_INFO/MAIN_PAGES` | Neue Rubrik integrieren, kein ungeprüfter Navigationsneubau |
| `selection_coherence.py` | Preisunabhängige Event-/Widerspruchsprüfung auf vollständigem Pool wiederverwenden und Daily3-spezifisch testen |
| `bet_finder_ui.py` | Flache Kartenbausteine prüfen; `partition_consumer_forecasts` verschiebt extreme Kurzquoten, deshalb nicht unverändert als Daily3-Ranking übernehmen |
| `partition_consumer_featured_forecasts` | Nutzt Marktgruppen und teilweise `RELEASED`; ist kein nachgewiesener sportübergreifender Sicherheitsrang |
| `challenge_engine.py` | 15K hat eigenes Ziel 15000, Ticketquoten 2–3 und Einsatzregeln 5–25 %; ausdrücklich nicht auf Daily3 übertragen |
| `challenge_store.py:ChallengeLedger` | Transaktions-/Integritätserfahrungen nutzbar, aber kein Tagesbudgetmodell; keine Änderung alter Regeln oder Schlüssel |
| `tip_store.py:TipStore` | Akzeptiert BET/RELEASED und nur WON/LOST/VOID, speichert Geld als REAL; daher kein Daily3-Geldledger und kein uneingeschränkt passender Importpfad |
| `account_identity.py:storage_scope` | Dauerhaften Browser-Scope nutzen; nicht mit sicherem globalem Personenlimit verwechseln |

Geplante neue Verantwortung, noch kein Code: Daily3-Kandidatenauswahl,
centgenaue Tagesrechnung/Persistenz und eigener UI-Adapter. Vorhandene Modelle,
Quotenbeobachtungen und Ergebnisquellen bleiben gemeinsam verwendet.

## 9. Erfolgsmessung

Vor Freigabe: null Budget-/Slot-/Doppelbuchungs-/Widerspruchsverstöße in den
definierten Regressionen; alle Geldbewegungen centgenau rekonstruierbar;
alle Hauptkarten enthalten belegbares Pro, Contra und Datenstand; kein
zusätzlicher Modell-/Providerabruf durch bloßes Öffnen der Rubrik.

Nach Freigabe: alle bestätigten Platzierungen einschließlich Verluste/Void
werden nachverfolgt; offene und unbestätigte Ergebnisse separat. Nettoergebnis,
Trefferquote, Abdeckung, Kalibrierung und gegebenenfalls Wettpreisgüte werden
versionsgebunden ausgewertet. Positive Gewinne, eine bestimmte Nutzungsfrequenz
oder CHF 150 pro Tag sind kein vorab zugesichertes Akzeptanzkriterium.

## 10. Offene Entscheidungen und Phasen

| Thema | Zuständig | Zeitpunkt |
| --- | --- | --- |
| Entwurfsregel Tageswechsel bei offenen Wetten | Nutzer/Produkt | Vor Umsetzung der Budgetfreigabe ausdrücklich prüfen |
| Preisunabhängige fachliche Tagesrangfolge und belegbare Vergleichbarkeit | Modell/Entwicklung | Vor Empfehlungscode quantifizieren und mit eingefrorenen Beispielen abnehmen |
| Reale Ergebnisbestätigung und Umgang mit nicht unterstützten Abrechnungstypen | Produkt/Entwicklung | Vor Wiederverwendung realer Gewinne festlegen |
| Kurzer Zugang `3 a day` innerhalb Wettfinder | Nutzer/UX | Mit erstem Wireframe prüfen; voller Name unverändert |
| Monatslimit | Nutzer | Offen, kein erfundener Betrag; für v1-Tagesmathematik nicht erforderlich |
| Öffentliche Bewerbung des bestätigten Slogans | Betreiber/rechtliche Prüfung | Vor öffentlicher Vermarktung; keine rechtliche Freigabe durch diesen Entwurf |

Phasen: (1) diese schriftliche Fassung prüfen; (2) offene P0-Regeln und flache
Desktop-/Mobile-Skizze konkretisieren; (3) begrenzter Implementierungsplan mit
Budget-/Slot-/Preisneutralitäts- und Abrechnungstests; (4) Umsetzung/Review;
(5) reale Daten-/Restore-/Browserabnahme; (6) Commit/Push und kontrolliertes
VPS-Deployment erst nach Freigabe. Kein Termin und kein aktueller Testerfolg
für ein noch nicht implementiertes Feature werden erfunden.

## 11. Quellen und Reichweite

Produktregeln stammen aus den ausdrücklichen Nutzerantworten dieses Chats.
Wiederverwendung nur nach aktuellem Codeabgleich; alte Übergabegrenzen sind
keine neuen Daily3-Einsatzregeln.

Für die Gestaltungsentscheidung zugunsten vorab festgelegter Ausgabengrenzen
siehe [Gambling Commission: Put a limit on your spending](https://www.gamblingcommission.gov.uk/public-and-players/guide/page/limit-how-much-you-can-spend).
Für die Abgrenzung vom Einkommensversprechen siehe
[Gambling Commission: Think about why you are gambling](https://www.gamblingcommission.gov.uk/public-and-players/guide/page/think-about-why-you-are-gambling).
Am 13.09.2026 gelesen; dies sind allgemeine Verbraucherhinweise, keine Schweizer
Rechtsberatung und keine empirische Bestätigung der BetBoy-Prognosen.
