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

## Verifikation vor Veröffentlichung

TDD-Reproduktionen: fehlende Tennisbegründung, ungewollter Gegner-Vorteil,
fehlende Fünfer-/Zehnerstatistik, Cache nach Prognose, Doppelzählung zwischen
Saisondateien, malformed Altstatistik, fehlendes Team-Gegenargument und
unerreichbare kompakte Gegenfakten. Bestehende Cricket-Bytes bleiben unverändert.

354 betroffene Tests plus 26 Untertests bestanden. Unabhängiges Read-only-Review
nach Korrektur der gefundenen Daten-/Anzeigegrenzen ohne offenen Codebefund.
Die breite Suite ist noch im Lauf; das ist ausdrücklich kein Vollsuite-Abschluss.
Browser- und Produktionsnachweis folgen getrennt nach dem bestehenden Code-only-
Pull. Keine neue Sicherung, keine sportlichen API-Abfragen und keine Paywall-
Aktivierung. Bestehende ungetrackte Prüfdateien bleiben unberührt.
