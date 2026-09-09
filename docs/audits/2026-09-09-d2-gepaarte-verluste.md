# D2: Gepaarte Verlustrechnung – geprüfter Teilstand

Stand 9. September 2026. Diese Abnahme betrifft die Rechenbausteine,
nicht eine empirische Freigabe von Verletzungs-, Belastungs- oder Wettereinflüssen.

- Die bestehende HAC-/BH-Statistik wurde ohne Formel-/Eingabeänderung aus dem
  Challenge-Kern ausgelagert. Der alte Wrapper bleibt erhalten. Das unabhängige
  Review verglich die echte Engine aus `3e9ce2c`, deren AST und 3.000 zusätzliche
  Eingabekombinationen einschließlich ungültiger Werte. Keine 15K-Regel geändert.
- Jeder native Event liefert einen ungewichteten Brier-Vergleich über genau
  seine eingefrorenen Zielmärkte. 199 Events mit je 900 Märkten bleiben 199 Events.
  Fehlende Ziele werden diagnostiziert; die finale Kohortenrechnung akzeptiert
  keine andere Teilmenge für den Verteilungsverlust.
- Die Rechenprüfung enthält die bestehenden Mindestanzahlen, aufeinanderfolgende
  Zeitblöcke, 2-Prozent-Grenze, HAC-Untergrenze, Verteilungs- und
  marktspezifischen Kalibrierungsdiagnosen. Sie erzeugt absichtlich weder
  Modellfreigabe noch einen alleinstehenden BH-/Erfolgsschalter.
- Ein unabhängiger Gegentest fand eine echte Rundungskante: Zwei große,
  getrennt gerundete Mittelwerte verdeckten eine gepaarte Verschlechterung.
  Der Vergleich mittelt jetzt die einzelnen exakten Zahlendifferenzen vor der
  einzigen Ausgaberundung. Gemischte Integer/Float-Werte bleiben erhalten;
  nicht darstellbarer Über-/Unterlauf wird explizit abgelehnt, nicht zu null.
  Unveränderte alte Statistik und Freigabeschwellen bleiben davon getrennt.

## Frische Nachweise

- 139 permanente D2-Rechenfälle; die ursprüngliche zusätzliche 91er- sowie
  die 16er-Gegenprobe blieben bytegleich. Zusammen: **246 bestanden**.
- Vollsuite im integrierten Arbeitsbaum auf `0d000f6` plus D2-WIP:
  **3.752 bestanden, 15 erwartete Windows/POSIX-Skips, 97 Untertests**,
  76,92 Sekunden, `.pytest_tmp/root-d2-math-freeze-full-01`.
  Die Suite enthielt zusätzlich die separat entwickelte, noch nicht unabhängig
  abgenommene Experiment-Registry. Grün bedeutet nicht, dass diese bereits
  freigegeben oder produktiv eingebunden wäre.
- Finaler unabhängiger Bericht:
  `.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-17-mechanics-final-review-20260909.md`.
- Beim Staging wurden ausschließlich überzählige EOF-Leerzeilen der alten
  Referenzfixture und der zwei kopierten Reviewtexte entfernt. Kein Funktions-
  oder Testinhalt geändert; danach erneut alle **246 Rechen-/Gegenfälle** grün.
- Keine offene Feststellung im begrenzten Rechenpaket. Kein Quellenabruf,
  Modelltraining mit echten Fällen, Experimentopening, Echtgeldvorgang oder
  neues Deployment durch diesen Teilstand.

Offen bleiben die vollständige eingefrorene Hypothesen-/Kohortensteuerung,
aus echten Ergebnissen berechnete gemeinsame Verteilungsverluste, native
Quellenauflösung, gemeinsame BH-Entscheidung, verknüpfte Freigabe und Betrieb.
Die synthetischen Softwaretests ersetzen nicht die 200 echten zeitkorrekten
Testevents über mindestens drei Blöcke.
