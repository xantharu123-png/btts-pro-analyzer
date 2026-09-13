# Daily3-Freigabe und angeforderter VPS-Pull

Stand: 13.09.2026; frische lesende SSH-Prüfung ab 18:04:48 UTC.

## Auftrag und Grenze

Der Nutzer hat die Übernachtregel mit „ja passt und vps pullen“ bestätigt.
Die Spezifikation wird entsprechend aktualisiert. Daily3 ist weiterhin
Dokumentation, kein implementierter neuer Wettbereich. Eine ausschließlich
dokumentarische Übernahme darf die noch nicht freigegebene C/B-Reparatur nicht
nebenbei nach main oder in die laufende App bringen.

## Tatsächlicher Serverzustand vor jeder Updateaktion

- App-Checkout `/opt/betboy/app`, Branch `main`, HEAD
  `2dd1116b68f3d94e9c24338c6c9dff9b01799221`; keine gemeldeten Änderungen an
  getrackten Dateien. Ungetrackte Laufzeitdaten wurden nicht verändert.
- Installierter `/usr/local/sbin/betboy-update`: `root:root`, Modus `0755`,
  SHA-256 `74b1c4b1aa88788f6a8e1050905215953b5938faad0009719aa15164a494b78f`.
- Kontextdatenbank `/opt/betboy/app/runtime_state/context_models.db`:
  `499855360` Byte, etwa `476,70 MiB`.
- App und Caddy aktiv; interner und öffentlicher `/_stcore/health` liefern `ok`.
- Sieben Timer mit nächsten Terminen. `betboy-tennis.service` und
  `betboy-wettfinder.service` sind jedoch weiterhin `failed`; nicht durch diese
  Dokumentationsänderung behoben oder zurückgesetzt.
- Installierter Markerprüfer meldet `status=complete`; kein laufendes Update.
  Keine Schlüssel oder anderen Secrets ausgelesen oder geändert.

## Konkreter Pull-/Deploymentblocker

Der installierte Updater enthält in Zeile 1066
`MAX_IMAGE = 64 * 1024 * 1024` und prüft in Zeile 1439 die vollständige
Backup-Datenbank gegen diese Grenze. Sie beträgt `67108864` Byte und ist
deutlich kleiner als die aktuell vorhandene Datenbank.

Die echte Reihenfolge des installierten Skripts wurde ebenfalls gelesen:

1. Zeile 3206: `systemctl stop betboy-app.service`.
2. Zeile 3222: `prepare_challenge_migration_boundary`.
3. Zeile 3224: `verify_context_runtime_before_update`.
4. Erst anschließend Übernahme des neuen App-Payloads.

Die Prüfung ist nicht auf Python-Änderungen beschränkt und besitzt keinen
dokumentierten Nur-Dokumente-Schalter. Ein Aufruf mit reinem Dokumentationsziel
wäre daher kein einfacher risikoloser Textdatei-Pull: Er würde bereits die
laufende App stoppen, bevor diese bekannte Größenprüfung stattfindet.

Der Updater wurde deshalb nicht aufgerufen. Kein direkter `git pull`/Reset als
Umgehung der vorgeschriebenen Update-/Markerprüfung, kein Root-Tool-Austausch,
keine Grenzwerterhöhung, kein Löschen von Historie und kein Neustart.
Das ist eine frische Vorprüfung des vorhandenen Engpasses, kein neuer
fehlgeschlagener Deploymentversuch und kein erfolgreicher VPS-Pull.

## Fortsetzung

Dokumentation und Freigabe können unabhängig versioniert werden. Der
Produktiv-Pull bleibt bis zur bereits separat begonnenen, geprüften
Updater-Reparatur offen. Deren aktuelle Prüfarchitektur-/CPU-Entscheidung wird
nicht durch die Daily3-Antwort ersetzt. Noch keine Freigabe von Daily3-Code,
keine behauptete neue Modellqualität und keine vollständige Betriebsentwarnung.

Belege der lesenden Werkzeuge dieser Fortsetzung: `ea8d00` (Server-HEAD,
Updater und Dienste), `0ad152` (Dateigröße, Timer und öffentlicher Healthcheck),
`eb8105` (installierte Zeilen und Markerstatus). Quellabgleich des installierten
Hashes mit dem lokalen main-Updater; keine Ausführung eines Checkout-Skripts
mit Root-Rechten.
