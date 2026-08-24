# BetBoy - Übergabe auf einen neuen PC

## 1. Ziel dieser Übergabe

Diese Anleitung bringt einen neuen Windows-PC in einen sicheren,
reproduzierbaren BetBoy-Arbeitsstand. Der laufende Produktionsserver hängt
nicht vom alten PC ab und arbeitet während des Wechsels weiter.

Am 24. August 2026 wurde nach der kontrollierten Nutzwert- und
Repricing-Härtung der
folgende **aktuelle Produktionsstand** verifiziert:

| Prüfung | Ergebnis |
|---|---|
| Aktueller Funktionscommit | `08778fdc29a7275c21fc23671d4763290273c435` (`Restore team under 1.5 eligibility`) |
| GitHub und VPS | Funktionscommit per vollständigem Hash identisch; ein späterer reiner Dokumentationscommit muss erneut per vollständigem Hash verglichen werden |
| `betboy-app.service` | `active` |
| Streamlit-Health | lokal und öffentlich `200 / ok` |
| BetBoy-Timer | exakt 7 aktiv und enabled; echter automatischer Wettfinder-Lauf `success / 0` |
| Fehlgeschlagene systemd-Units | 0 |
| Deploy-Recovery | Root-geschütztes `betboy-preupdate-20260824T094247Z-069033f2891f.zip` |
| Automatisches v13-Artefakt | Lauf um 11:44 CEST: 17 Fußballspiele gefunden, 14 modelliert, 16 sichtbare Modellprognosen, 10 exakt zuordenbare Fußball-Preisprüfungen, 0 operative Fehler und korrekt 0 strikte Tipps |
| Team-Unter-1,5 | Drei normale Modellprognosen mit `is_basic_forecast: false`; der Markt kann Featured, Strict und Ticket erreichen. Aktuelle Bestquoten 1,18, 1,29 und 1,30 lagen lediglich konkret unter den jeweiligen Value-Grenzen. |
| Gerenderte Live-UI | `Oţelul - Arges Pitesti: Team 2 unter 1,5` als zweite hervorgehobene Auswahl; Bestquote 1,29 transparent gegen Value-Grenze 1,65; Desktop und Mobil 390 x 844 ohne Überlauf, 0 Konsolenfehler |

Der Nutzwert-Katalog verwendet Automationsartefakt v13 und Auswahlrichtlinie
v11. Er zeigt bis zu 15 Fußball-Modellprognosen und behandelt Quoten
ausschließlich als Preishinweis. Team-Unter-1,5 ist ausdrücklich keine
Basisprognose und wird nicht pauschal aus Featured, Strict oder Ticket
entfernt. Nur eine konkret bestätigte Extrem-Kurzquote darf die Darstellung
zurückstufen; die Prognose bleibt sichtbar. Künftige Tagesprognosen werden
automatisch neu bepreist; strikte Freigaben verlangen frischen, vollständigen
Kontext und eine exakt identische Providerzuordnung. Die QA umfasst 886 Python-Tests, 38
Subtests und 3/3 JavaScript-Tests; Syntax- und Diff-Prüfungen waren grün.
Commit, Push, VPS-Deploy, echter Automatiklauf und Produktions-Browserprüfung
sind abgeschlossen. In der Produktion fehlt derzeit der Odds-API-Schlüssel
für Tennispreise; E-Sport hat keinen verifizierten Quotenprovider und
Basketball/NHL/Cricket noch kein validiertes automatisches Prematch-Modell.
Diese Grenzen werden sichtbar und fail-closed behandelt, nicht durch
erfundene Quoten oder Tipps kaschiert.

Nach jedem Commit gilt ausschließlich der frisch abgefragte vollständige
`origin/main`-Hash. Hash und Produktionsstand werden nach einem Deploy erneut
verglichen; alte Chatangaben sind keine Betriebswahrheit.

## 2. Was wo lebt

| Bestandteil | Kanonischer Ort | Muss auf den neuen PC? |
|---|---|---|
| Quellcode und Dokumentation | GitHub `xantharu123-png/btts-pro-analyzer` | Ja, per Clone |
| Produktions-App | `/opt/betboy/app` auf VPS `141.95.41.27` | Nein |
| Python-Venv Produktion | `/opt/betboy/venv` | Nein |
| Runtime-Datenbanken | VPS unter `/opt/betboy/app` | Nein |
| Planmäßige SQLite-Backups | `/var/backups/betboy` | Nein, aber unabhängige Offsite-Kopie empfohlen |
| Deploy-Recovery | `/var/backups/betboy-update` | Nein; Root-only, vor Updates erzeugt |
| Runtime-Migrationssicherung | `/var/backups/betboy-migration-9171bdb` | Nein; Root-only, bis zum bestätigten DR-Entscheid erhalten |
| SSH-Key-Recovery | `/var/backups/betboy-ssh` | Nein; Root-only, enthält nur öffentliche `authorized_keys`-Bytes |
| Produktions-Secrets | `/etc/betboy/betboy.env` und ignorierte `config.ini` | Nein |
| Lokale Entwicklungs-Secrets | alter PC, ignorierte Dateien | Nur sicher neu beziehen oder verschlüsselt übertragen |
| Privater SSH-Schlüssel | altes Benutzerprofil `.ssh` | Besser neuen Schlüssel erzeugen |
| 15K-/Tipps-Browser-ID | `localStorage` des alten Browserprofils | Nicht automatisch |
| Alte Venvs und Caches | alter PC | Nein |

Der neue PC ist eine Entwicklungs- und Administrationsstation. Er ist nicht
der Scheduler. Die sieben produktiven Jobs laufen per systemd auf dem VPS.

## 3. Vor dem Abschalten des alten PCs

### Pflichtprüfungen

Im aktuellen Repository:

```powershell
Set-Location C:\Projekt\BetBoy\betboy-app
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
```

`HEAD` und `origin/main` müssen identisch sein. Erwartete lokale Altdateien
können weiterhin ungetrackt erscheinen:

```text
AUDIT_BERICHT_2026-08-09.md
logs/pipeline_2026-07-31.log
logs/pipeline_2026-08-02.log
```

Die validierten Inhalte des Auditberichts sind in `PROJECT_HANDBUCH.md` und
`PROJEKTBIBEL.md` übernommen. Die beiden Logs sind historischer Laufoutput.
Keine dieser Dateien ist für den Betrieb nötig. Nur bei gewünschter Archivierung
verschlüsselt separat kopieren; nicht versehentlich committen.

### Zugangsdaten sichern

Die folgenden Dinge gehören in einen Passwortmanager oder direkt in das
jeweilige Providerkonto, niemals in diese Dokumentation:

- GitHub-Zugang;
- OVH-Zugang inklusive 2FA-Recovery;
- API-Football-Zugang;
- OpenWeather-, PandaScore-, Telegram- und gegebenenfalls Cricket-Schlüssel;
- weitere aktive Providerzugänge.

Historisch im Chat oder in Git veröffentlichte Schlüssel gelten bis zu ihrer
Rotation als kompromittiert. Nicht einfach dieselben Werte in eine neue
Datei kopieren und damit die Rotation als erledigt betrachten.

### 15K-Konto und „Meine Tipps“

BetBoy besitzt noch kein Login. Das Browserprofil speichert eine zufällige
128-Bit-Konto-ID unter `betboy.account.v1`. Ein neuer PC oder Browser erzeugt
eine neue ID und zeigt deshalb ein neues Konto, obwohl die alte Datenbank auf
dem VPS weiterhin vorhanden ist.

Vor dem Löschen des alten Browserprofils eine Entscheidung treffen:

1. **Neues Konto beginnen:** Auf dem neuen PC die App öffnen und den aktuellen
   Stand bei Bedarf über `Einstellungen -> 15K-Konto` korrekt setzen.
2. **Historie exakt behalten:** Das alte Browserprofil vorerst erhalten. Eine
   sichere Account-Transfer-/Login-Funktion muss implementiert oder die
   Zuordnung administrativ migriert werden, bevor das Profil gelöscht wird.

Die rohe Browser-ID ist praktisch ein Bearer-Identifier für dieses lokale
Konto. Sie gehört nicht in Chat, Git oder Screenshots. Browser-Synchronisierung
ist kein verlässlicher Transfer für `localStorage`.

## 4. Empfohlene Software auf dem neuen PC

Installieren:

- Git for Windows;
- Python 3.12 x64;
- Microsoft Edge oder Google Chrome;
- optional Visual Studio Code;
- optional Node.js LTS für den stillgelegten Browserimport-Test;
- Codex Desktop beziehungsweise das gewünschte Entwicklungswerkzeug.

Python 3.12 entspricht dem Produktionsserver. Ein neueres lokales Python kann
funktionieren, ist aber kein besserer Kompatibilitätsbeweis.

Kontrolle in PowerShell:

```powershell
git --version
py -3.12 --version
```

## 5. Repository neu einrichten

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Desktop\BetBoy" | Out-Null
Set-Location "$env:USERPROFILE\Desktop\BetBoy"
git clone https://github.com/xantharu123-png/btts-pro-analyzer.git betboy-app
Set-Location .\betboy-app
git switch main
git pull --ff-only
git status --short --branch
git log -3 --oneline
```

Für spätere Pushes verwendet das Repository weiterhin HTTPS. Git for Windows
öffnet beim ersten authentifizierten Push den Git Credential Manager. Keine
Tokens in die Remote-URL schreiben.

## 6. Lokale Python-Umgebung

```powershell
Set-Location "$env:USERPROFILE\Desktop\BetBoy\betboy-app"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest pytest-subtests
```

Lokale App starten:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit zeigt anschließend die lokale URL, normalerweise
`http://localhost:8501`.

Der Kompatibilitäts-Shim `btts_pro_app.py` bleibt vorhanden, aber der echte
Einstieg ist `app.py`.

## 7. Lokale Konfiguration und Secrets

Für reine Tests ist keine produktive Secret-Datei nötig. Für lokale Live-
Providerprüfungen kann eine ignorierte Konfiguration angelegt werden:

```powershell
Copy-Item config.ini.example config.ini
```

Zulässige Konfigurationswege, in steigender Priorität:

1. `config.ini`;
2. Umgebungsvariablen;
3. `.streamlit/secrets.toml`.

Unterstützte Umgebungsvariablen:

```text
FOOTBALL_DATA_API_KEY
API_FOOTBALL_KEY
OPENWEATHER_API_KEY
SUPABASE_DB_URL
ODDS_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PANDASCORE_KEY
RAPIDAPI_KEY
CRICKET_API_KEY
BETBOY_FREEMODE
```

Nicht alle Variablen sind im aktuellen Produktionspfad erforderlich. Der
alte Supabase-Zugang und football-data.org sind keine Pflicht für den
kanonischen Single-VPS-Betrieb.

Vor jedem Commit:

```powershell
git status --short
git check-ignore -v config.ini .streamlit\secrets.toml
```

Beide Secret-Dateien müssen ignoriert bleiben.

## 8. SSH-Zugang zum VPS

### Empfohlener Weg: neuer Schlüssel

Auf dem neuen PC:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$newKey = "$env:USERPROFILE\.ssh\betboy_ovh_ed25519_$stamp"
if (Test-Path -LiteralPath $newKey) { throw "Schlüsseldatei existiert bereits: $newKey" }
ssh-keygen -t ed25519 -a 100 -f $newKey -C "betboy-new-pc"
Get-Content "$newKey.pub"
```

Nur den Inhalt der `.pub`-Datei auf dem VPS unter
`/home/ubuntu/.ssh/authorized_keys` ergänzen. Solange der alte PC noch
verfügbar ist:

```powershell
ssh betboy-vps
nano ~/.ssh/authorized_keys
```

Im Editor den **öffentlichen** Schlüssel des neuen PCs als neue Zeile
einfügen. Den alten Eintrag erst entfernen, nachdem der neue Zugang in einem
separaten Terminal erfolgreich getestet wurde.

Auf dem neuen PC den normalen ED25519-Hostfingerprint beim ersten Kontakt
**out-of-band** gegen
`SHA256:YiFROIss/l4MjHP8y5+zYmjBiN8dxJVZXRVQ7SU6Rgo` vergleichen. Nur bei
exakter Übereinstimmung die OpenSSH-Frage mit `yes` bestätigen:

```powershell
ssh -F NUL -o IdentitiesOnly=yes `
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no `
  -o StrictHostKeyChecking=ask -o HostKeyAlgorithms=ssh-ed25519 `
  -i $newKey ubuntu@vps-a30a123f.vps.ovh.net "hostname"
```

Danach den später in allen Runbooks verwendeten Alias einrichten. Einen bereits
vorhandenen Alias nicht überschreiben, sondern zuerst manuell prüfen:

```powershell
$sshConfig = "$env:USERPROFILE\.ssh\config"
if (Test-Path -LiteralPath $sshConfig) {
    if (Select-String -LiteralPath $sshConfig -Pattern '^\s*Host\s+betboy-vps\s*$' -Quiet) {
        throw 'Host betboy-vps existiert bereits; vorhandenen Block zuerst prüfen.'
    }
}
$identityForConfig = $newKey.Replace('\', '/')
@"
Host betboy-vps
    HostName vps-a30a123f.vps.ovh.net
    User ubuntu
    IdentityFile $identityForConfig
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
    HostKeyAlgorithms ssh-ed25519
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    ForwardAgent no
"@ | Add-Content -LiteralPath $sshConfig -Encoding utf8
```

Damit der Alias mit `BatchMode yes` und einem verschlüsselten Schlüssel
funktioniert, den Windows-OpenSSH-Agent einmalig in einer als Administrator
geöffneten PowerShell aktivieren und den Schlüssel anschließend in einer
normalen PowerShell laden. Die Passphrase nur am sichtbaren OpenSSH-Prompt
eingeben:

```powershell
# Einmalig als Administrator:
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent

# Danach als normaler Benutzer:
ssh-add $newKey
ssh betboy-vps "id -un"
```

Erwartete Ausgabe: `ubuntu`.

Falls der alte PC nicht mehr verfügbar ist, den Zugang über die OVH-Konsole
beziehungsweise KVM/Recovery wiederherstellen. Der Server darf dafür nicht neu
installiert werden.

### Auf diesem PC verifizierter Zugang am 17. August 2026

- Aktiver verschlüsselter Schlüssel:
  `C:\Users\miros\.ssh\betboy_ovh_ed25519_20260814`; Fingerprint
  `SHA256:AIawx5EsF/j6XhvIdmueox2yqSDQurgWSXB8e/RlRms`.
- Der öffentliche Schlüssel wurde per OVH-Rescue zusätzlich und atomar in
  `/home/ubuntu/.ssh/authorized_keys` eingetragen. Nach erfolgreichem Deploy
  wurden die zwei alten, unbeschränkten Schlüssel atomar entfernt. Ein
  Root-only-Backup aller drei vorherigen Einträge liegt unter
  `/var/backups/betboy-ssh/authorized_keys.pre-prune-20260817T105940Z-d861d647`
  (`root:root`, Modus `0600`, SHA-256
  `770369de3b59fab49778e360c971705a59cbbef0a118ccd0c061cca82138d265`).
- Zwei unabhängige, streng gepinnte Batch-Logins als `ubuntu` bestanden nach
  der Entfernung. Der normale
  Server-Hostfingerprint ist
  `SHA256:YiFROIss/l4MjHP8y5+zYmjBiN8dxJVZXRVQ7SU6Rgo`.
- Der Alias `betboy-vps` verwendet ausschließlich den neuen Schlüssel,
  `StrictHostKeyChecking yes`, `BatchMode yes`, nur Public-Key-Authentifizierung
  und kein Agent-Forwarding. `ssh-agent` läuft automatisch.
- OVH zeigt wieder `Aktiv` und Boot `LOCAL`. Das temporäre Rescue-Passwort wurde
  weder in Dateien noch in Git oder in diese Dokumentation übernommen.
- `authorized_keys` enthält genau noch den neuen Schlüssel; Dateihash
  `8bd63630dcd79db8a4fd9e105ce2f52bccbe8869b2b770df297d3f5441aaa64e`.
  Er sperrt Agent-, Port- und X11-Forwarding, behält aber bewusst administrativen
  Shell-/Command-Zugang.

### Nicht empfohlen: privaten Schlüssel kopieren

Der derzeit allein autorisierte private Schlüssel liegt auf diesem PC unter
`C:\Users\miros\.ssh\betboy_ovh_ed25519_20260814`. Für einen weiteren PC ist
ein neuer, separat autorisierter Schlüssel sicherer als eine Kopie. Falls eine
Kopie ausnahmsweise unvermeidlich ist, nur über einen verschlüsselten,
kontrollierten Datenträger; niemals per E-Mail, Chat, GitHub oder
unverschlüsseltem Cloudordner.

## 9. Tests auf dem neuen PC

Vollständiger Python-Testlauf:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp | Out-Null
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp\full
```

Erneut verifizierter Ausgangswert am 17. August 2026 in einer isolierten Kopie
ohne Secrets, Laufzeitdatenbanken und Logs. Provider-Umgebungsvariablen waren
entfernt und ausgehende Python-TCP-Verbindungen im Testprozess blockiert; das
war keine betriebssystemweite Netzwerksandbox:

```text
730 passed, 5 subtests passed
3/3 JavaScript tests passed
```

Optionaler JavaScript-Test mit installiertem Node.js:

```powershell
node --test tests\n1_import_shared.test.cjs
```

Dieser Test schützt Rollback-Code. Die N1Bet-Erweiterung ist kein aktiver
Produktpfad.

Zusätzliche Basiskontrollen:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py challenge_15k.py challenge_engine.py challenge_store.py market_consensus.py
git diff --check
git status --short
```

## 10. Produktionskontrolle vom neuen PC

Öffentliche App:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://vps-a30a123f.vps.ovh.net/_stcore/health"
```

Erwarteter Inhalt: `ok`.

Serverprüfung mit dem auf diesem PC verifizierten Alias:

```powershell
ssh betboy-vps
```

Auf dem VPS:

```bash
sudo -u betboy git -C /opt/betboy/app rev-parse --short HEAD
systemctl is-active betboy-app.service
systemctl list-timers --all 'betboy-*'
systemctl --failed
sudo ls -lt /var/backups/betboy | head
sudo ls -lt /var/backups/betboy-update | head
sudo ls -lt /var/backups/betboy-ssh | head
```

Erwartung:

- Git-Hash entspricht `origin/main`;
- App-Service ist `active`;
- sieben BetBoy-Timer sind vorhanden;
- keine fehlgeschlagene Unit;
- tägliche Backups werden fortgeschrieben.

## 11. Normaler Entwicklungs- und Deployablauf

Auf dem neuen PC:

```powershell
git pull --ff-only
git status --short
# Dateien bearbeiten und Tests ausführen
git diff --check
git add -- <bewusst-ausgewählte-Dateien>
git commit -m "Kurze sachliche Beschreibung"
git push origin main
```

Danach den gepushten vollständigen Hash erneut gegen GitHub prüfen. Vor dem
**ersten** Einsatz auf einem bestehenden VPS müssen beide geprüften Root-Tools
einmalig nach `One-time migration of an existing VPS` in `deploy/README.md`
installiert und die vorhandenen Units sowie Laufzeitpfade geprüft werden. Erst
danach den root-eigenen Updater aufrufen:

```powershell
$target = (git rev-parse HEAD).Trim()
$remote = ((git ls-remote origin refs/heads/main) -split '\s+')[0]
if ($target -notmatch '^[0-9a-f]{40}$' -or $remote -ne $target) {
    throw 'Lokaler HEAD und GitHub main sind nicht exakt identisch.'
}
ssh betboy-vps "sudo /usr/local/sbin/betboy-update $target"
```

Niemals `sudo /opt/betboy/app/deploy/update_server.sh` ausführen. Checkout und
`.git` sind absichtlich durch den unprivilegierten Dienstbenutzer beschreibbar
und deshalb keine Root-Vertrauensquelle. Details stehen in `deploy/README.md`.

Anschließend Hash, Service, Health und betroffene Nutzeroberfläche erneut
prüfen. Ein lokaler Test oder erfolgreicher Push ist noch kein verifiziertes
Deployment.

## 12. Was nicht auf dem neuen PC gestartet werden darf

Nicht reaktivieren:

- alte KIMI-BetBoy-Automationen;
- Windows Task Scheduler für BetBoy Tennis oder Scanner;
- lokale Dauerschleifen für Football Shadow, Wettfinder, Tennis, E-Sport oder
  Rotkarten;
- ein zweiter schreibender Server gegen kopierte SQLite-Datenbanken.

Der VPS ist die einzige kanonische schreibende Instanz. Lokale manuelle
Entwicklungsläufe dürfen nicht als paralleler Produktionsscheduler laufen.

## 13. Backup und Notfall

### PC defekt, VPS gesund

Kein Produktionsausfall. Neuen PC wie in dieser Anleitung einrichten. Die
öffentliche App und Timer laufen weiter.

### App-Service gestört

```bash
sudo systemctl status betboy-app.service --no-pager
sudo journalctl -u betboy-app.service -n 100 --no-pager
sudo systemctl restart betboy-app.service
```

### Worker gestört

```bash
systemctl --failed
sudo journalctl -u betboy-wettfinder.service -n 100 --no-pager
sudo systemctl start betboy-wettfinder.service
```

Den betroffenen Servicenamen entsprechend ersetzen.

### VPS-Verlust

Die ZIP-Dateien unter `/var/backups/betboy` liegen auf demselben VPS und sind
allein kein Disaster-Recovery. Für vollständigen Serververlust wird ein
externes OVH-/Offsite-Backup benötigt. Vor breiter Nutzung muss ein Restore auf
eine frische Maschine praktisch getestet werden.

## 14. Dokumente für die nächste Person oder KI

In dieser Reihenfolge lesen:

1. `PROJEKTBIBEL.md`
2. `PC_WECHSEL_UEBERGABE.md`
3. `PROJECT_HANDBUCH.md`
4. aktuelle Git-Diffs und Tests
5. ältere Auditberichte nur bei historischer Ursachenanalyse

Geeigneter Übergabeprompt:

```text
Arbeite im Repository betboy-app auf main. Lies zuerst PROJEKTBIBEL.md,
PC_WECHSEL_UEBERGABE.md und PROJECT_HANDBUCH.md. Verifiziere anschließend
git status, HEAD gegen origin/main und den VPS-Hash, bevor du Änderungen
machst. Modellwahrscheinlichkeit und Buchmacherpreis müssen getrennt bleiben.
RESEARCH/SHADOW dürfen nicht als Echtgeldtipps veröffentlicht werden. Der VPS
ist die einzige schreibende Automationsinstanz. Bestehende ungetrackte Dateien
nicht löschen oder committen. Behauptungen aus alten Chats nur nach Code- und
Testnachweis übernehmen.
```

## 15. Abschlusscheckliste

- [x] GitHub-Zugang und Schreibberechtigung wurden per Credential Manager und
  erfolgreichem Push-Dry-Run geprüft; kein Token liegt in der Remote-URL.
- [x] Repository wurde als `betboy-app` geklont.
- [x] Ausgangs-`HEAD`, frisch abgefragtes GitHub `main` und VPS waren vor dem
  Härtungscommit identisch.
- [x] Python 3.12 und lokale Venv funktionieren.
- [x] Tests sind grün oder Abweichungen sind dokumentiert.
- [x] Neuer SSH-Schlüssel wurde autorisiert und zweimal getestet.
- [x] Zwei alte Server-Schlüssel wurden nach Root-only-Backup entfernt; zwei
  neue strikt gepinnte Logins bestanden anschließend.
- [x] Privater Schlüssel wurde nicht unsicher übertragen.
- [x] Produktions-Health liefert `ok`.
- [x] App-Service und sieben Timer sind aktiv.
- [x] Backup-Aktualität und jüngstes ZIP per CRC wurden geprüft.
- [ ] Secrets liegen nur in sicheren, ignorierten Speicherorten.
- [ ] Entscheidung zur alten Browser-/15K-Identität wurde getroffen.
- [x] Keine lokale BetBoy-/KIMI-Aufgabe im Windows-Aufgabenplaner und kein
  lokaler BetBoy-Python-Runner aktiv; der VPS bleibt die einzige schreibende
  Instanz.
- [x] `PROJEKTBIBEL.md` und `PROJECT_HANDBUCH.md` wurden gelesen.
