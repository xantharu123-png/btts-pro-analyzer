# BetBoy

Persönliche Sportanalyse-App: Wettfinder, eigene Suche, RisikoBet, Daily3,
15K und manuell bestätigte Wettbuchhaltung. Modellschätzungen sind keine
Gewinnzusagen; Softwaretests belegen keine Überrendite.

## Wo weiterarbeiten?

- **Aktiver Checkout:** `.worktrees/audit-repairs-20261013`, Branch
  `codex/audit-repairs-20261013`. Der ältere Hauptcheckout enthält fremde WIP.
- **Aktueller Abgleich:** [Audit vom 17.10.2026](docs/audits/2026-10-17-claude-gegenpruefung.md).
- **Aufbau, Start und Prüfung:** [ARCHITECTURE.md](ARCHITECTURE.md).
- **Restarbeiten:** jeweils oberster datierter Abschnitt in
  [TODO_AKTUELL.md](TODO_AKTUELL.md). Darunter steht historische Evidenz,
  keine zusätzliche aktuelle Freigabe.

Keine Secrets, Laufzeitdatenbanken, privaten Sicherungen oder QA-Ausgaben
committen. Keine automatische Bereinigung alter Checkouts. Produktion auf
dem VPS ist getrennt von GitHub; ein Push allein ist kein Deployment.
