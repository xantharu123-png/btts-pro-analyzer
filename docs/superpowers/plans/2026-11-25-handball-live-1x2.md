# Handball live: API‑SPORTS als einzige Quelle

Die Freigabe gilt für den bestehenden Handball-Europa-Pilot, nicht für eine
öffentliche Wettfreigabe. Fünf getrennte Herrenligen, keine weitere Quelle,
kein zusätzlicher Timer und kein Backup.

1. Echtes Schema absichern: Liga/Saison über `/odds?league=…&season=…&bet=1`,
   native Felder `game.id` und `update`; alte Aliasformen nur widerspruchsfrei.
   Vorab-1X2 pro Buchmacher, genau gebundene Spiel-ID, Zeit und Liga.
2. Einen Quoten-Sammelabruf je geeigneter Liga statt rotierender Einzelprobe;
   unveränderte erste Prognosen, getrennte Anbieter- und Abrufzeitpunkte.
   Höchstens elf Abrufe je Tag, mehr als neun pro Minute nur bei belegtem
   PRO-Tarif. Leere Antworten sind keine Preise und kein Ersatzanbieter.
3. Reales Anbieterformat und Regressionspfade testen; geprüften Branch über
   PR/CI in `main` übernehmen. No-Backup-Fast-forward; Handball-Schlüssel
   separat, begrenzter Handball-Abnahmelauf, Healthchecks. Produktionsdateien
   anderer Sportarten und Timer unverändert.
