# Live-Fußball: automatische Marktwahl

**Freigegebener Umfang:** [PR #157](https://github.com/xantharu123-png/btts-pro-analyzer/pull/157),
Themenstand `58f1482`, Merge `5a67a63`. Der Spielstand bleibt auch dann sichtbar,
wenn keines der unterstützten Modelle einen aktuellen Vorschlag trägt.

- Sechs PR-Prüfungen bestanden. Der [zusätzliche CI-Lauf auf dem Merge](https://github.com/xantharu123-png/btts-pro-analyzer/actions/runs/45028234476)
  bestand ebenfalls; die beiden optionalen Vollsuite-Hälften wurden nicht gestartet.
  Vor dem Release liefen 145 Live-Tests erneut erfolgreich. Die Vollsuite aus der
  Entwicklung war wegen eines bestehenden Hockey-Testfehlers nicht grün.
- Offline-Nachweis mit zwei synthetischen Spielständen und den echten Modellen:
  Ohne vorher gewähltes Spiel öffnete BetBoy den Vorschlag mit 77,84 % statt
  dem mit 66,06 %. Spielwechsel und Rückkehr zur Automatik erzeugten keine
  weiteren Datenabrufe. Nach Ablauf der Frischegrenze wurde kein Tipp protokolliert.
- Der 5-/1-Minuten-Takt bei offenem Tab und das Tageslimit von 500 Tickerabrufen
  ändern sich nicht. Die Prüfung misst keine Trefferquote und keinen Wettvorteil.

## Produktionsnachweis · 22.11.2026

Nach dem regulären Shadow-Job öffnete das Updatefenster um 14:42:46 CET.
Fast-forward auf `5a67a63fbe8bba4462ef879812bc20e9e7e0ddbf`, elf Dateien
gegen Git verifiziert. Die isolierte Linux-Prüfung bestätigte die automatische
Auswahl und die Frischegrenze vor dem Neustart; pytest war in der
Produktionsumgebung nicht installiert und wurde nicht nachinstalliert.

Die App ist seit 14:42:56 CET mit PID 1745430 aktiv (zuvor 1741786).
Release-Exit 0, Caddy und alle sieben Kerntimer aktiv. Interner und öffentlicher
Healthcheck zweimal `ok` (Helfer und unabhängige Nachprüfung). GitHub-main und
Server-HEAD identisch, keine getrackten Änderungen auf dem Server. Wettfinder- und
RisikoBet-Tagesdokument sowie Ligaabdeckungsdatenbank vor/nach dem Release mit
identischen Prüfsummen. Kein Backup, keine neue Anbieterabfrage durch die Abnahme.
