# Beide Claude-Audits gegen den aktuellen Code

Stand 17.10.2026. Baseline `044a06fb6711b8e92c7f2d5051a5a4c3ab086405` im
aktiven Worktree `.worktrees/audit-repairs-20261013`, nicht im veralteten
Hauptcheckout. Beide Berichte vollständig gelesen: Nutzeranhang vom 13.10.
und `AUDIT_BERICHT_2026-10-16_CLAUDE.md` im Hauptcheckout. Insgesamt 79 IDs.

**Nicht alles in den Berichten ist ein noch vorhandener Fehler.** Insbesondere
widersprechen einige vorgeschlagene Preis-, Backup- und Navigationsregeln den
späteren ausdrücklichen Nutzerentscheidungen. Andere Punkte sind echte offene
Modell-/Datennachweise oder größere technische Schulden. Sie werden unten
nicht als erledigt umbenannt.

## In dieser Runde repariert

- Ursprünglicher statistischer Hauptmarkt bleibt unverändert in Metadaten.
  Wird dessen Angebot ausgefiltert, wird ein sichtbarer Hauptmarkt nur aus dem
  bereits kohärenten, bepreisten Pool derselben nativen Quelle, Teilnehmer und
  Modellrevision gewählt, nach bestehendem statistischem Rang. Nicht einfach
  der Markt mit der höchsten Prozentzahl. Ohne Rang bleibt die Darstellung neutral.
- Buchmacher/Quotenzeit sind auch ohne Hover erreichbar; sichtbare Zeiten in
  Zürich; alte interne Quelltexte in der Merkliste neutral. Live heißt
  „Berechnet“, nicht „Modell geprüft“. Fünf kleine Beschriftungen mindestens 12 px.
- Tennis-Kalibrierungswächter misst keinen Legacy-Bo3-Vertrag als Produktions-v2.
  Ohne gebundene Originalparameter ist er **nicht verfügbar**, nicht gesund.
  Unbekannte Formate werden gezählt; explizite Legacy-Diagnose bleibt abgegrenzt.
  Wochenbericht unterscheidet fehlende Messung, Legacy-Diagnose und echte Drift.
- „Awarded“ wird in beiden Ergebnisadaptern nicht als normales Tennisergebnis verwendet.
- Privater Fußball-Endstandleser lehnt explizite Nicht-FT-Status ab. Statuslose
  historische Replays bleiben kompatibel; öffentlicher Loader bleibt strenger.
- Separate `projection_target_diagnostics(...)` misst erreichte Marginalen und
  Residuen, ohne Originalschema, Optimierer, aktive Version oder Gates zu ändern.
- Daily3-Nachtrag per Kalender/Uhrzeit statt ISO-Zeichenkette. Schweizer doppelte
  oder fehlende Sommerzeitstunde wird nicht geraten; UTC ist explizit wählbar.
- Legacy-Modellcache nutzt die gemeinsame lokale Vertrauensprüfung beim Lesen
  und atomaren sicheren Schreibpfad. Das sind **keine signierten Pickles** und
  kein Schutz gegen einen bereits kompromittierten eigenen Dienstbenutzer.
- README/Architektur-Einstieg ergänzt, historische Übergaben nicht gelöscht.

## Schlüsselrotation

Nutzer meldete alle drei Ersatzwerte. Vergleich ohne Ausgabe mit den bekannten
Git-Expositionen: alle drei verschieden. Neue Werte in vorhandener lokaler
INI/Streamlit-Konfiguration und auf dem VPS in Environment/INI eingesetzt;
andere Konfiguration bleibt erhalten. Dateien/rechte geprüft, keine Sicherung.
Je Anbieter genau ein Authentifizierungsaufruf: API-Football, football-data.org
und OpenWeather jeweils HTTP 200/akzeptiert. Keine Sport-/Modellscans.

PandaScore separat gegen vier erreichbare historische Konfigurationsblobs
verglichen: aktueller Wert dort nicht gefunden. Das ist kein universeller
Beweis, dass ein Token niemals an anderer Stelle veröffentlicht wurde.
Der Widerruf alter Werte beim Anbieter ist nicht durch die neuen HTTP-200-
Antworten bewiesen. Aktivierung der neuen App-Umgebung braucht den Release-Neustart.

## Abgleich Audit 13.10.2026

| ID | Ergebnis gegen aktuellen Code |
| --- | --- |
| M1 | Teilweise: v1-Zielkorrektur tatsächlich schwach; v2-Kandidat existiert, war in 304 chronologischen Prüffällen schlechter und bleibt aus. Residuen jetzt separat messbar; keine unbelegte Aktivierung. |
| M2 | Offen: PP-Abschläge sind Heuristik, keine individuellen Konfidenzgrenzen. Ersatz braucht unabhängige Prüfung, nicht einen willkürlichen relativen Abschlag. |
| M3 | Teilweise: vollständiger kausaler No-Vig-Marktvergleich fehlt. Markt-Mischung oder neues Preisgate widerspricht der Nutzerregel; Messung bleibt getrennte Aufgabe. |
| M4 | Policy/Modellrisiko offen: Fréchet-Rechnung korrekt; andere Stressannahme oder Kelly-Optimierung ist keine reine Fehlerkorrektur. |
| M5 | Offen: additives Basismodell ohne vollständige Gegnerbereinigung. Loglineares Gegnerstärkemodell existiert offline; noch kein belegter Produktionsersatz. |
| M6 | Nicht belegt als allgemeiner mathematischer Fehler: relative Brier-Verbesserung ist nicht automatisch ein universeller Marktart-Bias. Empirischer Vergleich bleibt nötig. |
| A1 | Bewusste spätere Nutzerregel: Daily3-Auswahl nicht nach EV/Mindest-Value sperren; bekannte exakte Quote mindestens 1,20 bleibt erforderlich. Kein altes Gate restauriert. |
| A2 | Bereits behoben: höhere Abrechnung/Quote braucht gebundene Zweitbestätigung und Begründung. Keine stille 24,0-statt-2,40-Gutschrift. |
| A3 | Bereits behoben: Rückzahlung über erwarteter Auszahlung braucht zusätzliche konkrete Bestätigung. |
| A4 | Teilweise bereits behoben: Decimal-Korridor und Schutz abgerechneter Merkliste. Historische ROUND_HALF_UP-Abrechnung nicht still auf Floor umgestellt. |
| T1 | Kern bereits vereinheitlicht inkl. echter beendeter Sätze und Walkover; verbleibender Awarded-Adapterfall jetzt ausgeschlossen. |
| T2 | Offen: 15-PP-Tennisabschlag nicht statistisch hergeleitet. Kein improvisierter Ersatz. |
| T3 | Bereits behoben: tatsächliche Verfügbarkeit/Turnierende statt 10-/15-Tage-Schätzung im zeitlichen Backtest. |
| T4 | Teilweise behoben: Wächter-/Formatvertrag und Berichtsfehler korrigiert; produktionsgleiche Kalibratorpopulation und tatsächlich funktionsfähiger v2-Wächter bleiben offen. |
| T5 | Offen: Elo-Decay, kontinuierliche Belaggewichtung und validierte zusätzliche Kontexteffekte brauchen einen neuen geprüften Modellvertrag. |
| T6 | Offen: zwei Elo-Durchläufe gewichten Ergebnisse mehrfach; tatsächliche Zukunftsleakage im heutigen Pfad nicht allein daraus bewiesen. Kausaler Alternativvergleich fehlt. |
| U1 | Durch spätere UX-Freigabe überholt: keine erneute Wand aus Haircut-/Value-/Research-Badges. |
| U2 | Bereits behoben: Tippmerken ist verdrahtet. Die alte Preisfreigabe-Aktion wurde bewusst nicht wiederhergestellt. |
| U3 | Heutiger echter Fehler mit verstecktem Lead jetzt behoben; Nutzer-Wahrscheinlichkeits-/Zeit-Sortierung bleibt. |
| U4 | Teilweise: falsches Live-Prüflabel jetzt neutral; einheitliche Forschungshinweise nicht gegen spätere Nutzer-UX restauriert. |
| U5 | Offen: gemeinsame echte Geldbilanz fehlt; CHF/EUR und reine Merkliste dürfen nicht unbesehen addiert werden. |
| U6 | Markenname ausdrücklicher Nutzerwunsch. Rechtliche/Alters-/Hilfefragen vor Kundenstart separat offen; keine erfundenen Rechtsangaben. |
| U7 | Behoben: historische interne Quellcaption neutral, gespeicherte Quelle unverändert. |
| U8 | Behoben: RisikoBet mit Zürcher Zeit und Spiel/Spielen. |
| U9 | Teilweise: Live-Prüfübertreibung korrigiert; Rohdatentabelle/technische Live-Begriffe noch gesonderte UX-Schuld. |
| U10 | Behoben: Angebotsquelle und Zeit sichtbar statt ausschließlich Hover. |
| U11 | Technische Schuld: unaufgerufene Diagnosefunktionen nicht ungeprüft gelöscht. |
| U12 | Offen: unvollständige manuelle Teamsport-Analysepfade; Cricket bleibt ausgenommen. |
| U13 | Teilweise: Hauptkarten bereits vereinfacht; historische/Legacy-Preisbegriffe noch nicht vollständig vereinheitlicht. |
| U14 | Entscheidung offen: echte historische EUR-Konten nicht bloß als CHF beschriften oder unbemerkt umrechnen. |
| U15 | Offen: punkt-/kommabasierte Formatierung noch nicht überall einheitlich. |
| U16 | Bewusste Produktregel: gewünschte obere Hauptnavigation und Daily3-Marke bleiben, keine erzwungene Fünfer-Bottomnav. |
| U17 | Offen: knapper unterscheidbarer Zustand „nie gelaufen/veraltet/Abdeckung/Fehler“ noch nicht überall vorhanden. |
| R1 | Drei bekannte öffentliche Schlüssel ersetzt/Authentifizierung geprüft; aktuelle Tokens nicht im Index. Alte Provider-Widerrufe nicht unabhängig bestätigt; kein privates Archiv pauschal gelöscht. |
| R2 | Teilweise behoben: gemeinsame sichtbare UI-Zeiten Zürich; weitere Saison-/Pipeline-Zeitlogik nicht pauschal geändert. |
| R3 | Technische Schuld: Legacy-Entrypoints und alte Hilfsskripte bleiben, kein destruktives Aufräumen fremder WIP. |
| R4 | Teilweise: kurzer Einstieg/Architektur ergänzt; historische Belege und Datendateien nicht blind entfernt. |
| R5 | Offen: kein vollständiges reproduzierbares Linux-Lockfile/CI. Psycopg2 hat tatsächliche Nutzer und ist nicht einfach ungenutzt. |
| R6 | Offen: Logging-/Persistenz-/Funktionsgrößen-Schulden. Keine großflächige Umschreibung eingefrorener Modelle in diesem Reparaturpatch. |

## Abgleich Audit 16.10.2026

| ID | Ergebnis gegen aktuellen Code |
| --- | --- |
| K1 | Drei bekannte historische Schlüssel ersetzt; siehe präzisen Rotationsnachweis und Widerrufsgrenze oben. |
| K2 | Offen: Ligabasisraten-Skill ist kein Markt-Skill. Kein positives Marktergebnis behauptet; neues hartes RELEASED-Marktgate widerspricht späterer Produktregel. |
| K3 | Teilweise/Modellaufgabe: Heuristikproblem real, behauptete universelle Fehlerauswahl nicht allein bewiesen; kein Markt-Logit-Blend ohne geprüfte Freigabe. |
| K4 | Bewusste Produktregel: Daily3 ohne EV-/Echtgeld-Preisfreigabe; konservative Auswahl, Tagesbudget und 1,20-Boden bleiben. Frischer Kontext ist weiter nicht immer verfügbar. |
| K5 | Modell und Preis sind bewusst getrennt; negativer Beispiel-EV ist keine behauptete profitable Wette. Keine Gewinn- oder Ruin-Sicherheitszusage. Neue Einsatzpolitik offen. |
| K6 | Ausdrücklich nicht umgesetzt: Nutzer verbietet neue Backups; Timer bleibt deaktiviert. Das verbleibende Wiederherstellungsrisiko ist real. |
| H1 | Offen: offline vorhandenes Gegnerstärkemodell noch kein validierter Produktionsersatz; kein Mehrjahres-Backfill entgegen Aufbewahrungswunsch. |
| H2 | Offen: aktuelle Heuristik ist kein Konfidenzintervall; belastbarer Ersatz fehlt. |
| H3 | Offen: Population/Belag-/Serve-Kalibrierung und Unsicherheitsmodell. Gegensätzliche Teilstatistik darf echtes Gegenargument sein; kurze Belagliste beweist allein keine vollständige Datenlücke. |
| H4 | Für Produktion bereits behoben: Tour-State baut explizit v2. Legacy-Default bleibt für alte Replays, nicht global umgestellt. |
| H5 | Offen: Rohpreis-CLV ist kein No-Vig-Marktvergleich. Vollständige passende Gegenpreise/zeitgerechtes Closing müssen vorhanden sein; kein bloßes Anbieter-Umetikettieren. |
| H6 | Offen: besserer Markt-/Renditenachweis nicht vorhanden. Softwaretests oder Basisraten-Brier beweisen ihn nicht. |
| H7 | Teilweise: aktiver Checkout eindeutig dokumentiert und mit main abgeglichen; alter Hauptcheckout/WIP und fremde Worktrees nicht gelöscht oder zurückgesetzt. |
| H8 | Offen: CI/Lock/Linter sowie vollständige Linux-Abnahme weiterhin eigenes technisches Arbeitspaket. Windows-Vollsuite ersetzt Linux-Nachweis nicht. |
| H9 | Offen: reale Zyklen und große Funktionen; keine riskante Komplettverschiebung mit Pin-/Replayänderung als Nebenfix. |
| H10 | Spätere Nutzer-UX überholt den alten Wireframe; keine erneute Preisfreigabe oder Badgewand. Quotenherkunft jetzt sichtbar. |
| H11 | Offen vor Kundenstart: korrekte Rechts-/Betreiberdaten, Datenschutz/Onboarding/Hilfe benötigen gesonderte Fertigstellung. Kein Kundenlaunch behauptet. |
| H12 | Teilweise: fehlende genaue Angebote werden öffentlich gefiltert; kohärenter Hauptmarkt/Fallback repariert. RisikoBet-Szenario und normaler Favorit sind nicht automatisch dieselbe Empfehlung; keine marktdefinierte Modellwahrscheinlichkeit eingeführt. |
| H13 | Teilweise: kleine Labels/Zeiten vereinheitlicht; obere Navigation ausdrückliche Nutzerwahl. Währungen, Portal-/App-Design und Scanstatus bleiben offen. |
| H14 | Entscheidung vor bezahltem Start nötig: derzeit bewusst persönliche Opt-in-Zugangskontrolle. Default ohne Migration umstellen würde den Nutzer aussperren; kein Public-Customer-Ready behauptet. |
| M1 | Wie 13-M4: mathematische Untergrenze korrekt, Änderung von Stress/Einsatz-/Zielpolitik ist eine gesonderte fachliche Entscheidung. |
| M2 | Teilweise widerlegt: ausführbare 15K-Tickets schließen gleiche Spiele/Teams bereits aus. Logische Mehrfachmärkte sind keine Portfolio-Einsatzrechnung. |
| M3 | Offen: Dispersion/Abhängigkeit von Ecken/Karten braucht validierten Alternativvergleich, nicht einen neuen ungemessenen Faktor. |
| M4 | Teilweise behoben: separate exakte Residuenmessung. Keine neue Gate-/Extrapolationsregel oder geänderte Originaldiagnostik. |
| M5 | Offen: FDR derzeit je Liga, kein globaler Fehlerkontrollnachweis. Fünf Jahre Historie nicht ungefragt beschafft. |
| M6 | Offen: E-Sport-Unsicherheit/Mehrfachgewichtung braucht alternative kausale Prüfung. |
| M7 | Offen: Platzverweis-Multiplikatoren nicht kausal validiert und nicht als actionable freigegeben. Deskriptive 11-v-10-Zahl identifiziert keinen kausalen Faktor. |
| M8 | Offen: Datenbank-/Logging-Schuld; Behauptung WAL nur dreimal bereits veraltet. Keine pauschalen DB-Löschungen. |
| M9 | Offen: manuelle Daemon-Scans können beim Neustart verloren gehen. Pauschale Behauptung eines Voll-Reruns alle zwei Sekunden ist so nicht korrekt. |
| M10 | Teilweise behoben: README/Architektur-Einstieg. Historische Nachweise bleiben erhalten statt unkontrolliert gekürzt. |
| M11 | Teilweise behoben: fünf winzige Labels, Quellcaption und Zeitangaben; weitere Live-Dichte/Sprach-/Fehlertextfragen bleiben. Markenname kein versehentliches Englisch. |
| M12 | Technische Schuld: kein ungeprüftes Löschen von Legacy, Daten oder Superpowers-Nachweisen. |
| N1 | Behoben für explizite Status: AET/PEN/Live etc. nicht als FT. Statuslose Legacy-Replays bleiben unverändert; öffentlicher Loader prüft sie strenger. |
| N2 | Nicht als mathematischer Defekt belegt: lineares Pooling korrelierter Prognosen ist nicht allein deshalb ungültig. Logit-Pooling braucht Vergleich. |
| N3 | Methodensensitivität offen: proportionale Marge nicht automatisch durch Shin/Power besser; passende Gegenpreise und unabhängiger Vergleich erforderlich. |
| N4 | Behoben am verbleibenden Legacy-Lade-/Schreibpfad durch vorhandene Dateivertrauensgrenze. Shadowpfade waren schon geschützt. Kein Signatur- oder vollständiger System-RCE-Schutz behauptet. |
| N5 | Erweiterungswunsch für spätere Skalierung, keine aktuelle Buchmacherintegration. Ohne echte Daten kein erfundenes Limitprotokoll. |
| N6 | Teilweise veraltet: aktive RisikoBet-Adapter liefern keine genannte Wald-Untergrenze mehr; heuristischer Charakter bleibt und ist kein validiertes Modell. |
| N7 | Behoben: Datum/Uhrzeit/Zeitzone statt ISO-Handeingabe; Geld-/Snapshotvertrag unverändert. |
| N8 | Bewusste UI-Entscheidung: interne Einstellungen nicht wieder in Kundennavigation gezwungen. |

## Prüfung und Veröffentlichung

Gezielte RED→GREEN-Belege liegen unter
`C:/Projekt/BetBoy/output/claude-recheck-20261017/` (UX, Tennis, Mathematik,
Daily3, Cache/Rotation). Sandbox-Hardlink-/Temp-Berechtigungsfehler sind getrennt
erhalten; unveränderte betroffene Module nativ wiederholt. Ein erster Gesamt-
Zwischenlauf wurde wegen eines tatsächlichen Reviewfundes als **INCOMPLETE**
beendet; nicht als vollständiger Pass verwenden.

`full-qa-02` ist vollständig beendet: ursprünglich15.219PASS/1FAIL/98SKIP und147
bestandeneUntertests. Einziger Fehler: alter Test verlangte einzeiligen Bild-
nachweis; die12px-Lesbarkeitskorrektur erlaubt bewusst Umbruch. Nur diese
Erwartung aktualisiert; vollständiger106erOwner-Recheck bestanden. **Expliziter
kombinierter Endstand15.220PASS/98identischeSkips/147Untertests**, keine offenen
Testfehler; ursprünglicherFAIL und B-Exit1 nicht überschrieben. Alle816Quell-
undFixturehashes außer dem Erwartungstest und einer zusätzlichen leeren EOF-
Zeile im neuen Watch-Test gleich; letztere AST-identisch, vollständiger11er-
Owner ebenfalls erneut grün. Produktionscode unverändert. Abschließender
Supplementbeleg `final-summary-02.json` erhält den ersten Abschlussbeleg unverändert.
Alle15.318IDs genau einmal,15.233 maßgebliche Vorläufer-IDs vollständig+85neue.
Die alte Multigoal-Parameterumordnung ist anhand exakter Quellhashes und AST-
Multimengen erklärt, kein verloren gegangener Fall. Unabhängiger Gegenabgleich.

Frischer tatsächlicher Renderer mit synthetischen Daten bei1440/390/320px:
Bildnachweise max78/60px, Labels12px, Wappenpolygon/-rand/-maße unverändert,
keine Überläufe, sichtbare Angebotsquelle/Zeit, Haupt-/Nebenmarkt sowie Maus- und
Tastaturbedienung der5-/10-Spieleansicht. Keine externen Bildabrufe freigegeben,
kein Benutzerbrowser übernommen. Das ist keine ganze produktive Streamlit-
oder physische Geräteabnahme. Belege: `ui-closeout-01/summary.json`, Screenshots.

VPS vor Release noch4f2af4e, App/Caddy und Healthchecks gesund; regulärer
Shadowlauf19:42Exit0. OptionalerLegacycache fehlt wie zuvor; vorhandene
Startlogik prüft lokaleSQL-Daten und verwirft das ML am bisherigen Gate. Keine
separate Trainingsausführung ergänzt, kein erzwungener Cache erzeugt.
Der neueReleaseweg ist source-only mit expliziter31-Pfadliste und neun
Jobzuständen; keine Sicherung, Migration oder zusätzlich gestarteter Sportscan.
Release-SHA und tatsächliche Aktivierungs-/Healthbelege werden nach Deployment ergänzt.
