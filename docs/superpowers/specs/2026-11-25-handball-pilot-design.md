# Handball: Bundesliga-Pilot

Die erste Anbindung ist die deutsche Männer-Bundesliga. Ein optionaler Schritt
im bestehenden Wettfinder-Tageslauf liest Spielplan, reguläre Endstände und
ausgewählte 1X2-Quoten von API‑SPORTS. Kein neuer Timer, keine neue Buchung
durch BetBoy und standardmässig keine Abrufe. Keine öffentlichen Handballtipps.
Die Aktivierung benötigt `BETBOY_HANDBALL_PILOT=1` und einen ausdrücklich als
`API_HANDBALL_KEY` gesetzten Zugang aus der Serverumgebung, ohne Rückgriff auf
den Fussballschlüssel. Der Pilot läuft nach der Hauptpublikation mit eigener
Sperre und höchstens 75 Sekunden Laufzeit. Maximal sechs Anbieterabrufe je
Zürcher Tag (Liga, Saisonspiele, bis zu vier Quotenabrufe).

Für jedes Spiel berechnet eine einfache gegnerbereinigte Torabstands-Basis
Heim/Remis/Auswärts, ausschliesslich aus vorhandenen regulären Endständen vor
der Prognose in derselben Saison. Mindestens 40 verbundene Ligaspiele und acht
Spiele je Team; keine Form-, Kader- oder Belastungswirkung in dieser ersten Basis.
Zu wenige Spiele ergeben keine Prognose. Die erste Prognose wird
fixiert, bevor Quoten abgefragt werden. Bei vorhandenem vollständigem 1X2
vergleicht der Pilot dieselben abgerechneten Spiele per Brier-Score mit den
vom Buchmacherrand bereinigten Marktchancen. Ein niedrigerer Score ist besser;
das ist keine Renditemessung und keine Tippfreigabe.
Die Stichprobe enthält nur Paarungen, die ins Abrufbudget fallen und vor Anpfiff
vollständige, höchstens 36 Stunden alte 1X2-Preise liefern; sie ist kein
repräsentativer Ligavergleich. Es sind beobachtete Vorabpreise, keine Schlussquoten.

Heim/Auswärts, Liga, Saison, Spiel-ID und ursprünglicher Anpfiff bleiben an
den Beleg gebunden. Andere Spiele, verspätete Preise, unvollständige Märkte
und Sonderwertungen zählen nicht als bestätigter Marktvergleich. Rohdaten und
Schlüssel werden nicht dauerhaft abgelegt. Anbieterabdeckung und tatsächliche
Nutzbarkeit des Tarifs sind erst nach einer echten Anbieterantwort belegt.
Korrigierte Ergebnisse werden neu bewertet, ohne Modellschätzung oder Preis zu
überschreiben. Der interne Bericht `python -m handball_pilot` liest ohne Abruf nur
die aktuell laufende Saisondatei. Alte Saisondateien bleiben unverändert erhalten.
