# Tennisquoten und RisikoBet-Kurzform – 30.09.2026

## Auftrag und Grenzen

Bestehenden Tennisquotenzugang wieder anbinden; beanstandete RisikoBet-
Protokolltexte durch kompakte vorhandene Sportfakten ersetzen. Keine erfundenen
Müdigkeitseffekte, Modelländerungen, zusätzlichen Sport-/Historienläufe,
Finanzbuchungen, neuen Sicherungen oder Bereinigungen.

## Nachgewiesene Ursachen

1. Der automatische Tennis-Preisabruf war ausdrücklich deaktiviert. Die
   gespeicherte Gea/Zhang-Auswahl hatte 79,367393 % und keine Vergleichsquote.
2. Der Provider schreibt `Zhizhen Zhang`, die Statistikquelle `Zhang Zhizhen`.
   Die bisherige geordnete Namensbindung fand das identische Match nicht.
   Der aktive China-Open-Quotenkatalog enthält Arthur Gea gegen Zhizhen Zhang
   am 30.09.2026 um 09:00 UTC; kein Terminunterschied.
3. Eine Quotenaktualisierung um 07:26 UTC behielt den Modellzeitpunkt
   01:52 UTC korrekt bei. Der öffentliche Leser prüfte die neuen Preise aber
   gegen diesen alten Zeitpunkt und verwarf den gesamten Katalog. Der erste
   Nachabruf hatte drei Preisprüfungen, zwei reale Preise und null Providerfehler;
   trotzdem lieferte der öffentliche Leser null Prognosen. Nicht als Erfolg
   gewertet. Reproduktion ist durch einen tatsächlichen Reader-Test abgesichert.
4. RisikoBet gab vorhandene interne Simulation-/Erholungsprotokolle aus und
   erzeugte auch ohne weitere Informationen einen Analyse-Expander.

## Umsetzung

- Automatischer Abruf nur im Produktionslauf oder mit ausdrücklich injiziertem
  Testloader; bestehender Pool und gemeinsamer Budgetschutz bleiben erhalten.
- Expliziter Tennis-Quotenlauf ohne Modelle. Automatische Wiederholungen bleiben
  begrenzt; ursprüngliche Beobachtungszeiten werden im Cache nicht erneuert.
- Tennis-Namensreihenfolge darf abweichen, aber alle vollständigen normalisierten
  Wörter einschließlich Wiederholungen müssen übereinstimmen. Keine Initialen-,
  Teilnamen- oder unscharfe Zuordnung. Ereignis-/Duplikatsbindung unverändert.
- Nur eine explizite Preisaktualisierung führt einen eigenen Preisprüfzeitpunkt
  je bepreister Modellzeile. Modellzeit, Wahrscheinlichkeiten und Reihenfolge
  bleiben unangetastet; finanzielle Ausführungsnachweise werden nicht erzeugt.
- RisikoBet: kurze Belagangabe und getrennte 5-/10-Spielerquotienten; technische
  Absätze, identische doppelte Marktüberschrift und leere Detailbereiche entfallen.
  Echte Ergebnisse, Gegner, Kader-/Wetterinformationen und Gegenargumente bleiben.
  Originalbelege und Snapshots werden nicht umgeschrieben.

## Bisherige Prüfung

696 betroffene Tests nach dem ersten Patch bestanden; unabhängige Quoten- und
UI-Reviews bestanden. Zwei danach erst im echten Abruf gefundene Grenzen
(Namensreihenfolge und Preis-/Modellzeit) sind zusätzliche Reparaturen, keine
rückwirkend als bestanden dargestellten Tests. Die endgültige Abschlussrunde
und der endgültige Produktionsnachweis folgen im Abschnitt darunter.

Konkreter RisikoBet-Nutzerfall lokal und produktiv bei 1440/390/320 px geprüft:
50,0 % unverändert, beide Spielerbilanzen sichtbar, keine beanstandeten Protokolle
oder doppelte Marktüberschrift; kein horizontaler Überlauf. Bekannte iframe-
Warnungen bleiben separat. Screenshot-/CLI-Artefakte liegen ungetrackt unter
`output/playwright/` und wurden nicht ins Repository gepackt.

## Separat offen

Numerische Verletzungs-/Wetter-/Müdigkeitseffekte und bessere Wettqualität sind
hiermit nicht nachgewiesen. Die RisikoBet-Oberfläche zeigt weiterhin auch bereits
begonnene Tagesszenarien; deren zeitliche Katalogprojektion ist ein gesonderter
UI-/Auswahlpunkt. Keine abgeschlossene Gesamt-App-Abnahme behaupten.

## Endgültiger Produktionsnachweis

- UI-/Anbindungscommit `bf62ab76ca6cf140baaf9dcbaf71a3432c650336`;
  Folgekorrektur `7b60496b60b53eb6f8ebfa3a7fd79725408db524`.
  Beide auf main gepusht und ohne neues Backup auf dem VPS veröffentlicht.
- Finale lokale Runde: 767 Tests und 26 Untertests bestanden. Unabhängige
  Abschlussprüfungen der Namensbindung, Reader-Zeitgrenze und Textprojektion
  ohne offene P1/P2-Befunde. Kein Vollsuite- oder Wettqualitätsnachweis behauptet.
- Echter Quotenlauf um 09:44 CEST: drei anstehende Tennis-Auswahlen, drei echte
  Preise, null Fehler. Gea 1,28/20 Buchmacher, Sakamoto 1,73/16, Djokovic 1,42/20.
  Preisgrenze/Value-Status ist intern vom Modell getrennt; kein Einsatz ausgelöst.
- Vorher-/Nachhervergleich: alle nichtpreislichen Modellfelder und deren
  Reihenfolge gleich, `generated_at` weiterhin 01:52:46.928449 UTC. Andere
  Sportquellen und deren Ausführungszeilen unverändert. Der tatsächliche
  Produktionsleser ist wieder gültig und liefert zehn aktive Prognosen.
- Live Gea/Zhang bei 1440/390/320 px: Quote 1,28 und Modell 79,4 % sichtbar,
  kein horizontaler Überlauf, Page-/Console-/Request-Fehler null. RisikoBet-
  Originalfall ebenfalls in der echten Seite bei allen drei Breiten geprüft.
- Interner und öffentlicher Healthcheck `ok`, App/Caddy aktiv. Kein Timer-/
  Dienstneubau, neuer Modell-/Sportscan, Backup oder Löschvorgang. Die einzigen
  zusätzlich aufgerufenen Providerendpunkte waren die beauftragte Quotenkatalog-
  Prüfung und die zwei begrenzten Quoten-Nachläufe, nicht Historienaufnahme.
- Der folgende Commit hält nur diese Nachweise fest; er ändert keinen Appcode.
