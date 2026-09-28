# Auswahlbegründungen: Audit und begrenzte Korrektur, 28.09.2026

## Reproduzierter Fehler

Die gespeicherte Produktionskarte zu Rublev/Jacquet zeigte nur 2/3 gegen 3/3
Hartplatzsiege, während sie Rublev mit 59,3 % auswählte. Das sind echte kleine
Bilanzwerte aus zuvor gespeicherten Prognosen, aber keine Erklärung der Auswahl.
Eine rein lesende Originalmodellprüfung bestätigte getrennt: langfristiger
Belag-/Gesamtvergleich und Aufschlagkomponente sprechen in diesem Fall für Rublev.
Das ist keine Behauptung, dass er gewinnen wird oder zuletzt stärkere Gegner hatte.

## Korrektur

- Tatsächliche verwendete Vergleichsmerkmale erklären; die bessere gegnerische
  jüngste Bilanz als Gegenargument anzeigen. Bei einer schwächeren Seite kein
  positiver Stärkevorteil erfinden. Andere Wettverträge erhalten nicht automatisch
  eine Siegerbegründung.
- Vorhandene Trainingsdateien ohne Download lesen. ATP-/WTA-Scope, Spielernamen,
  Belag und Prognosezeit binden. Ergebniszeilen höchstens ein Jahr alt und zehn
  pro Spieler. Cache nach der Prognose ist für diese Karte unzulässig.
- Abgeschlossene K.-o.-Runden einschließlich Qualifikation: echte Fünfer- und
  Zehnerbilanz samt optionalen Gegnern, Ergebnissen und tatsächlichen damaligen
  Rangplätzen. Kein Rang aus Setzung/Elo ableiten. Unbekannt geordnete RR-Runden
  nicht als geordnete jüngste Spiele ausgeben; Umfang im Statistikdetail benennen.
- ATP-Turnierdatum nicht als exakte Matchzeit/Erholung behandeln. Fortschritt der
  K.-o.-Runden ordnet Ergebnisse innerhalb desselben Turniers; keine erfundene
  Startzeit oder Dauer. Doppelte Eventidentitäten und widersprüchliche Metadaten
  ausschließen, Abbruch/Walkover nicht als regulären Sieg zählen.
- Anzeigeobjekte ändern weder Quellprognose noch Marktberechnung. Bei sehr
  kleinen rekonstruierten Aufschlagunterschieden eine Rundungstoleranz anwenden,
  statt eine möglicherweise umgekehrte Richtung zu behaupten.
- Fußball nutzt die exakt gebundenen gespeicherten Raten und marktbezogene
  Gegenereignisse. Formspielzahlen nicht als Siege darstellen. Vollständige
  Fußball-Ergebnis-/Gegnerlisten sind nicht im Kartenstand hinterlegt und werden
  in diesem Patch nicht durch neue Datenbeschaffung ersetzt.
- Teammodelle exportieren kleine reine Anzeigefakten nach derselben Berechnung.
  Original-Input-Hash und Wahrscheinlichkeit bleiben gleich. Basketball-/Hockey-
  Anzeigefaktoren im bestehenden Snapshotvertrag; keine zusätzliche Snapshot-DB.
  Hockey-Endstand inklusive OT/SO nicht aus normalisierten Regulation-Toren bauen.
- E-Sport speichert je neuer Erstprognose eine kleine optional gebundene
  Ergebnisfolge. Alte Beobachtungen bleiben unberührt. Kein zusätzlicher Scan.
  Keine Gegnerqualitätsbehauptung allein aus einer Ergebnisfolge oder Gegner-ID.
- Wettfinder/Daily3, Tennis und RisikoBet verwenden dieselben begrenzten Fakten.
  Interne Elo-Zahlen nicht in Kundentexte übertragen. Verletzungs-/Fitness-/Wetter-
  Wirkung bleibt eine getrennte fachliche Arbeit; dieser Patch aktiviert sie nicht.

## Verifikation und Veröffentlichung

TDD-Reproduktionen: fehlende Tennisbegründung, ungewollter Gegner-Vorteil,
fehlende Fünfer-/Zehnerstatistik, Cache nach Prognose, Doppelzählung zwischen
Saisondateien, malformed Altstatistik, fehlendes Team-Gegenargument und
unerreichbare kompakte Gegenfakten. Bestehende Cricket-Bytes bleiben unverändert.

356 betroffene Tests plus 26 Untertests bestanden. Unabhängige Read-only-Reviews
nach Korrektur der Daten-/Anzeigegrenzen und des abschließenden Cache-Diffs ohne
offenen Codebefund. Zusätzlich rot/grün reproduziert: wiederholte Verarbeitung
derselben Historie und Doppelzählung eines Matchs bei normalisierten Namenskollisionen.
Die breite Suite wurde nach rund 32 Minuten unterbrochen, ohne beobachteten
Testfehler, aber ausdrücklich ohne vollständigen PASS-Nachweis.

Code-Commits `e7d220561c88f42a26ca23c7c202290e6bd15264` und
`00ef41968f7433238f95a1570169c032bf1660f1` auf GitHub `main` veröffentlicht und
auf dem VPS per Fast-forward gezogen. App aktiv, interner und öffentlicher
Healthcheck `ok`; alle sieben vorhandenen Timer weiterhin geplant. Keine neue
Sicherung, kein zusätzlich gestarteter Sport-/API-Scan und keine Paywall-Aktivierung.

Im internen Browser bestätigt: Rublev 3/5 und 4/10, Jacquet 4/5 und 6/10 echte
erfasste Hartplatzsiege. Längerfristiger Vergleich als Auswahlbegründung, bessere
gegnerische Fünferbilanz als Gegenargument, Gegner und Satzresultate aufklappbar.
Fußballgruppe Georgia/Ukraine mit Torprognosen, Gegenargument und ehrlicher
Formbasis geprüft; E-Sport zeigt längerfristigen Serienvergleich statt Elo-Zahlen.
Desktop und Mobil 390×844 geprüft: Dokument-/Bodybreite jeweils 390 px, kein
horizontaler Überlauf. Browserfehler waren auf die kurzen geplanten Neustarts
beschränkt (WebSocket-Unterbrechung/502), nach finalem Reload keine neuen Fehler.

Die zusätzliche Ladezeitkorrektur verarbeitet den nach Datum und Dateifingerprints
gebundenen Cache einmal pro Tour/Tag, nicht mehrfach je Kartenfeld. VPS-Messung
derselben Rublev-Statistik: vorher erster Aufruf 1,7835 s, Folgeaufruf 0,3527 s;
danach erster Aufruf 1,620751 s, Folgeaufrufe 0,000482/0,000279 s. Bilanzen und
Quell-Hash identisch. Das ist eine isolierte Statistikmessung, kein Nachweis der
gesamten Seitenladezeit. LRU höchstens vier Tagesindizes, keine neue DB-Kopie.

Abnahmegrenze: Bereits gespeicherte RisikoBet-Faktoren bleiben unverändert;
die neuen Ergebnisfakten werden beim nächsten regulären Lauf eingefroren.
Basketball/Hockey sind mit echten konsumierten Ergebniszeilen regressionsgeprüft,
aber mangels heutiger Karten nicht als reale aktuelle Produktionsfälle bestätigt.
Vollständige Fußball-5/10-Ergebnislisten und empirisch nachgewiesene zusätzliche
Verletzungs-/Wetter-/Müdigkeitswirkung bleiben getrennte Arbeiten.

Live-Screenshots (lokale Prüfartefakte, nicht in Git):
`output/playwright/customer-reasons-rublev-20260928.png` und
`output/playwright/customer-reasons-mobile-20260928.png`.
Bestehende ungetrackte Prüfdateien bleiben unberührt.
