# BetBoy - Übergabe auf einen neuen PC

## 1. Ziel dieser Übergabe

Diese Anleitung bringt einen neuen Windows-PC in einen sicheren,
reproduzierbaren BetBoy-Arbeitsstand. Der laufende Produktionsserver hängt
nicht vom alten PC ab und arbeitet während des Wechsels weiter.

Am 10. August 2026 wurde verifiziert:

| Prüfung | Ergebnis |
|---|---|
| Lokaler Git-Stand | `5fe7ef7` vor Erstellung dieser Übergabedokumente |
| GitHub `origin/main` | identisch |
| VPS-Stand | identisch |
| `betboy-app.service` | `active` |
| Streamlit-Health | `ok` |
| BetBoy-Timer | 7 aktiv und terminiert |
| Fehlgeschlagene systemd-Units | 0 |
| Letztes sichtbares Backup | `betboy-sqlite-20260810T011730Z.zip` |

Nach dem Dokumentationscommit gilt der aktuelle `origin/main`-Hash. Der
funktionale Produktstand bleibt `6a59f3e`; spätere Dokumentationscommits
ändern keine Wettlogik.

## 2. Was wo lebt

| Bestandteil | Kanonischer Ort | Muss auf den neuen PC? |
|---|---|---|
| Quellcode und Dokumentation | GitHub `xantharu123-png/btts-pro-analyzer` | Ja, per Clone |
| Produktions-App | `/opt/betboy/app` auf VPS `141.95.41.27` | Nein |
| Python-Venv Produktion | `/opt/betboy/venv` | Nein |
| Runtime-Datenbanken | VPS unter `/opt/betboy/app` | Nein |
| Server-Backups | `/var/backups/betboy` | Nein, aber Offsite-Kopie empfohlen |
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
Set-Location C:\Users\miros\Desktop\BetBoy\betboy-app
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
ssh-keygen -t ed25519 -a 100 -f "$env:USERPROFILE\.ssh\betboy_ovh_ed25519" -C "betboy-new-pc"
Get-Content "$env:USERPROFILE\.ssh\betboy_ovh_ed25519.pub"
```

Nur den Inhalt der `.pub`-Datei auf dem VPS unter
`/home/ubuntu/.ssh/authorized_keys` ergänzen. Solange der alte PC noch
verfügbar ist:

```powershell
ssh -i "$env:USERPROFILE\.ssh\betboy_ovh_ed25519" ubuntu@141.95.41.27
nano ~/.ssh/authorized_keys
```

Im Editor den **öffentlichen** Schlüssel des neuen PCs als neue Zeile
einfügen. Den alten Eintrag erst entfernen, nachdem der neue Zugang in einem
separaten Terminal erfolgreich getestet wurde.

Auf dem neuen PC testen:

```powershell
ssh -o BatchMode=yes -i "$env:USERPROFILE\.ssh\betboy_ovh_ed25519" ubuntu@141.95.41.27 "hostname"
```

Falls der alte PC nicht mehr verfügbar ist, den Zugang über die OVH-Konsole
beziehungsweise KVM/Recovery wiederherstellen. Der Server darf dafür nicht neu
installiert werden.

### Nicht empfohlen: privaten Schlüssel kopieren

Der vorhandene private Schlüssel liegt auf dem alten PC unter
`C:\Users\miros\.ssh\betboy_ovh_ed25519`. Eine Kopie ist nur über einen
verschlüsselten, kontrollierten Datenträger vertretbar. Niemals per E-Mail,
Chat, GitHub oder unverschlüsseltem Cloudordner übertragen.

## 9. Tests auf dem neuen PC

Vollständiger Python-Testlauf:

```powershell
New-Item -ItemType Directory -Force .pytest_tmp | Out-Null
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest_tmp\full
```

Erneut verifizierter Ausgangswert am 10. August 2026:

```text
693 passed, 5 subtests passed
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

Serverprüfung:

```powershell
ssh -i "$env:USERPROFILE\.ssh\betboy_ovh_ed25519" ubuntu@141.95.41.27
```

Auf dem VPS:

```bash
sudo -u betboy git -C /opt/betboy/app rev-parse --short HEAD
systemctl is-active betboy-app.service
systemctl list-timers --all 'betboy-*'
systemctl --failed
sudo ls -lt /var/backups/betboy | head
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

Danach Produktion aktualisieren:

```powershell
ssh -i "$env:USERPROFILE\.ssh\betboy_ovh_ed25519" ubuntu@141.95.41.27 "sudo /opt/betboy/app/deploy/update_server.sh"
```

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

- [ ] GitHub-Zugang auf neuem PC funktioniert.
- [ ] Repository wurde als `betboy-app` geklont.
- [ ] `HEAD` entspricht `origin/main`.
- [ ] Python 3.12 und lokale Venv funktionieren.
- [ ] Tests sind grün oder Abweichungen sind dokumentiert.
- [ ] Neuer SSH-Schlüssel wurde autorisiert und getestet.
- [ ] Privater Schlüssel wurde nicht unsicher übertragen.
- [ ] Produktions-Health liefert `ok`.
- [ ] App-Service und sieben Timer sind aktiv.
- [ ] Backup-Aktualität wurde geprüft.
- [ ] Secrets liegen nur in sicheren, ignorierten Speicherorten.
- [ ] Entscheidung zur alten Browser-/15K-Identität wurde getroffen.
- [ ] Alte lokale/KIMI-Automationen bleiben deaktiviert.
- [ ] `PROJEKTBIBEL.md` und `PROJECT_HANDBUCH.md` wurden gelesen.
