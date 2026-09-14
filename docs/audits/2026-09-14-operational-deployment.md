# Operativer Release statt historischer Vollauswertung

## Autorisierung und Vertrag

Am 14.09.2026 ausdrücklich vom Nutzer freigegeben: historische Vollanalysen
vom Deployment trennen, Backup/Wiederherstellung/Kontointegrität/Schema/Start
weiter verbindlich prüfen. Keine zusätzliche Modellfreigabe.

## Reparatur

- Neue, explizite `--deployment-check`-Betriebsart: schema 2, level deployment.
- Vollständige SQLite-Struktur-, Integritäts- und Fremdschlüsselprüfung.
- Manifestidentität und -kette, aktive Artefakthashes und tatsächliches Laden
  der getrennten ATP-/WTA-Modelle inklusive gültiger Prognosewerte.
- Typ-/Referenz-/Zeitprüfung aktiver Effekte und Freigaben; keine Änderung an
  der eigentlichen, weiterhin evidenzprüfenden Modellaktivierung.
- Historische Receipt-/Snapshot-/Fit-/Evaluierungsreplays gehören weiter zur
  expliziten alten Prüfung, nicht zu jedem Softwareupdate.
- `historical_analysis_verified=false`, `empirical_approval_verified=false`;
  das Root-Protokoll akzeptiert ausschließlich diesen vollständigen neuen
  Bericht, keine alten/invollständigen Prüfberichte als Ersatz.
- Root-versiegelter SQLite-Input, vor/nachher Hash- und Dateiprüfung, read-only.
  4-GiB-Dateigrenze beim Streaming, unveränderte begrenzte Prozessressourcen.
- Onlinebackup und tatsächliche Wiederherstellung jeder Datenbank vor
  Updaterreparatur; erneut vor eigentlicher Veröffentlichung und nach Stoppen
  der Writer. Geldbewegungen/HMAC bleiben durch denselben gepinnten Helfer geprüft.
- Zusätzlicher behobener Integrationsfehler: `runtime_paths.py` hatte durch
  den bestätigten Windows-Temporärnamenfix bereits einen neuen Hash. Beide
  Updateprogramme verlangten fälschlich noch ausschließlich den alten.
  Zielpin korrigiert, exakter alter Vorgänger erlaubt; Pfadregeln unverändert.

## Abgrenzung

Kein erneuter historischer 900-/1800-CPU-Prüflauf, kein Löschen von Daten oder
Journalen, keine Erstattung alter Budgets, keine Aufhebung von Preis- oder
Modellregeln. Die bisherigen historischen Fehlversuche bleiben Fehlversuche.

Vor Release frisch bestätigt: VPS-App `2dd1116`, installierter Updater
`74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`,
App/Caddy aktiv und interner Healthcheck ok. Tennis-/Wettfinder-Dienste zeigten
noch fehlgeschlagene letzte Läufe. Diese Befunde sind getrennt vom Updatefehler.

## Ausführungsnachweise

### Zusätzlicher tatsächlich reproduzierter Platzfehler

Der erste echte Reparaturaufruf stoppte VOR Backup/Updater-/Appänderung:
`insufficient combined repair backup/restore capacity`.
Lesender Befund: 88 Datenbanken inklusive Journalen mit 1.043.849.216 Byte;
Platzreservierung 16.291.610.624 Byte, verfügbar 11.570.561.024 Byte.

Korrektur: maximal inventarisierte DB-/WAL-/Journalbytes plus 64 MiB Wachstum
statt pauschaler Verdopplung. Der bereits vorhandene Producer erzwingt diese
ENGERE Grenze für die gesamte SQLite-Snapshotmenge und die Archivdatei.
Onlinewachstum jenseits dieser Grenze bricht den Vorgang weiter ab.
Die normale Update-Platzrechnung entspricht nun diesen tatsächlich erzwungenen
Grenzen und zählt Belegungen je physischem Dateisystem weiterhin gemeinsam.

Nur die neu erzeugte doppelte `capture.zip`-Arbeitskopie wird nach vollständiger
Wiederherstellungs-/HMAC-Prüfung, fsync und Veröffentlichung des unabhängigen
Root-Backups entfernt. Vorher werden Herkunft, Pfad, Eigentümer, Dateisignatur,
Länge und beide Dateihashes geprüft. Das verifizierte Backup bleibt vollständig.
Keine bestehenden Backups, alten QA-Verzeichnisse oder Runtime-Daten werden gelöscht.

- Neuer Update-/Root-Hook-/Reparaturpfad: 467 bestanden, 1 Windows-Skip;
  anschließend drei zusätzliche Aktivierungsabgrenzungsfälle ergänzt und alle
  13 Tests des neuen Moduls erneut bestanden. Zusammen 470 verschiedene Tests.
  XML: `.pytest_tmp/deployment-separation-20260914-05.xml`.
- Angrenzende Pfad-/Daily3-/Konten-/Backup-/Tennis-Tests: 336 bestanden,
  1 Windows-Skip, 71 Untertests. 23,34 Sekunden.
  XML: `.pytest_tmp/deployment-money-20260914-01.xml`.
- Beide Shellprogramme mit echtem Bash syntaktisch geprüft; gemeinsame
  Root-Funktionen bytegleich und unveränderten Backup-Helferpin geprüft.
- Zwei zusätzlich gestartete historische Regressionsteilmengen wurden vor
  Abschluss beendet und ausdrücklich NICHT als bestanden gezählt. Unveränderte
  vollständige historische Fit-Replays sind nicht der neue Release-Nachweis.
- main-Dokumentationsmerge enthält keine weiteren Programmänderungen.
- Nach der Platz-/Duplikatkorrektur gesamter betroffener Update-Testlauf erneut:
  477 bestanden, 1 Windows-Skip, 55,32 Sekunden; einschließlich beider
  Server-Platzgrenzen und vier Aufräum-Negativ-/Positivfälle.
  XML: `.pytest_tmp/deployment-capacity-20260914-02.xml`.

### Tatsächlicher Release und Restfehler

Updater-Reparatur und reguläres Deployment von `66b113b` auf dem VPS haben beide
Exit 0 erreicht. 88 Datenbanken wurden gesichert und tatsächlich wiederhergestellt;
HMAC-Kontoprüfung erfolgreich. Die operative Kontextprüfung brauchte 10,44 Sekunden
und 154.247.168 Byte RSS, ohne historische/empirische Modellabnahme zu behaupten.
App/Caddy und sieben Timer sind aktiv; beide Healthchecks liefern `ok`.
Daily3 wurde öffentlich bei 1440×1000 und 390×844 geprüft, ohne Budgetbestätigung
oder Wettplatzierung. Generierte Belege liegen unter `output/playwright/`.

Der erste Wettfinderlauf erzeugte 69 Modellprognosen, endete aber wegen
`football:result_identity_mismatch` in der nachgelagerten Evidenzprüfung mit Exit 1.
Der begrenzte Abgleich am 14.09.2026 zeigte zwei tatsächlich verschobene Spiele:

- Spiel 1505529, Teams 2324/2328: ursprünglich 13.09.2026 15:30 UTC,
  jetzt 02.10.2026 23:00 UTC, Anbieterstatus NS.
- Spiel 1549774, Teams 1138/1126: ursprünglich 13.09.2026 01:15 UTC,
  jetzt 15.09.2026 01:00 UTC, Anbieterstatus NS.

Korrektur: Eine gültige Terminänderung bei identischer Anbieter-Spiel-ID und
identischen Teams wird als `schedule_revision_unresolved` sichtbar gehalten,
nicht als technischer Fehler gewertet. Sie erzeugt weiterhin KEIN Ergebnis,
auch nicht nach späterem FT. Die alte Prognoseidentität wird nicht umgeschrieben.
Abweichende IDs/Teams, unlesbare Termine, ungültige Statusdaten und angebliche
Endergebnisse vor einem zukünftigen neuen Anstoß bleiben technische Fehler.
Eine spätere kausale Zuordnung der alten Prognose zu einem verschobenen Spiel
wird damit ausdrücklich nicht behauptet.

Die neuen Fälle wurden zuerst rot reproduziert; anschließend 198 Tests für
Evidenz, native Ergebnisse, RisikoBet-Abrechnung und Wettfinder bestanden
(8,71 Sekunden). Wiederholung, unveränderte Datenbankbytes bei offenem Spiel,
Zählmärkte ohne Statistikabruf und unabhängige Abrechnung anderer Spiele belegt.
XML: `.pytest_tmp/schedule-20260914-green.xml`.

Keine Erfindung fehlender Daily3-Auswahlen oder Verletzungs-/Müdigkeitswirkung.
Die Timer berechnen weiter nur; Code wird durch das autorisierte Deployment
veröffentlicht, nicht automatisch durch diese Timer gepullt.
