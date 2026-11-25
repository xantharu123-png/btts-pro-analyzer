# Umsetzung: isolierter Bundesliga-Pilot

1. API‑SPORTS-Adapter für Bundesliga/Saison, Spiele und vollständige reguläre
   1X2-Preise mit offline geprüften Quellverträgen anbinden.
2. Preisblindes, gegnerbereinigtes Heim/Remis/Auswärts-Basismodell getrennt testen.
3. Erste Prognosen separat aufzeichnen, später exakte Ergebnisse abrechnen und
   Brier-Scores nur auf identischen Spielen vergleichen. Standard aus; höchstens
   ein Versuch je Zürcher Tag, maximal vier Preisabrufe. Quotenläufe und manuelle
   Läufe mit abweichendem Pfad oder `--force-football` bleiben unverändert.
4. Offline Zusammenspiel, Opt-in und Regressionspfade prüfen; keinen Live-Abruf,
   kein Backup und keine eigenständige Produktionsfreigabe ausführen.
