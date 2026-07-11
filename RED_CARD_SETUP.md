# RED CARD ALERT SYSTEM - GITHUB ACTIONS

Automatische Telegram-Benachrichtigungen bei roten Karten in Live-Spielen.

## ⚡ WIE ES FUNKTIONIERT

- ✅ Läuft **alle 5 Minuten** automatisch auf GitHub Actions
- ✅ Checkt **alle Live-Spiele** weltweit
- ✅ Sendet **Telegram-Nachricht** bei roter Karte
- ✅ Komplett **kostenlos**
- ⚠️ Verzögerung: bis zu 5 Minuten

---

## 📱 SCHRITT 1: TELEGRAM BOT ERSTELLEN

1. **Öffne Telegram** und suche nach **@BotFather**

2. **Sende** `/newbot`

3. **Gib einen Namen ein** (z.B. "Red Card Alerts")

4. **Gib einen Username ein** (z.B. "myredcard_bot")

5. **Kopiere den Bot Token** - sieht aus wie:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

6. **Starte deinen Bot** - Klick auf den Link oder such nach dem Username

7. **Sende eine Nachricht** an deinen Bot (z.B. "Hallo")

8. **Hole deine Chat ID:**
   - Geh zu: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
   - Ersetze `<BOT_TOKEN>` mit deinem Token
   - Suche nach `"chat":{"id":123456789` 
   - Die Zahl ist deine Chat ID

---

## 🔧 SCHRITT 2: GITHUB REPOSITORY SETUP

### Option A: Neues Repository erstellen

1. **Geh zu GitHub** → Create new repository
2. **Name:** `red-card-alerts` (oder beliebig)
3. **Visibility:** Private (empfohlen)
4. **Create repository**

### Option B: Bestehendes Repository nutzen

Du kannst die Dateien auch in dein `btts-pro-analyzer` Repo packen.

---

## 📁 SCHRITT 3: DATEIEN HOCHLADEN

Lade diese 2 Dateien in dein GitHub Repo:

```
dein-repo/
├── red_card_bot.py              ← Das Bot-Script
└── .github/
    └── workflows/
        └── red_card_monitor.yml ← GitHub Actions Config
```

**So lädst du hoch:**

1. Geh zu deinem Repo auf GitHub
2. Klick **Add file** → **Upload files**
3. Ziehe `red_card_bot.py` rein
4. Klick **Commit changes**
5. Erstelle Ordner `.github/workflows/`
6. Upload `red_card_monitor.yml` dort rein

---

## 🔑 SCHRITT 4: SECRETS KONFIGURIEREN

1. **Geh zu deinem Repo** → **Settings** → **Secrets and variables** → **Actions**

2. **Klick "New repository secret"** und füge hinzu:

   **Secret 1:**
   - Name: `API_FOOTBALL_KEY`
   - Value: `<DEIN_API_FOOTBALL_KEY>`

   **Secret 2:**
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: `<DEIN_BOT_TOKEN_VON_SCHRITT_1>`

   **Secret 3:**
   - Name: `TELEGRAM_CHAT_ID`
   - Value: `<DEINE_CHAT_ID_VON_SCHRITT_1>`

---

## ▶️ SCHRITT 5: AKTIVIEREN & TESTEN

### Actions aktivieren:

1. **Geh zu** → **Actions** Tab in deinem Repo
2. Falls deaktiviert: **"I understand my workflows, go ahead and enable them"**

### Manueller Test:

1. **Geh zu** → **Actions** → **Red Card Monitor**
2. **Klick** → **Run workflow** → **Run workflow**
3. **Warte 30 Sekunden**
4. **Klick auf den laufenden Job** um Logs zu sehen

**Du solltest sehen:**
```
🔍 RED CARD SCAN - 2026-01-20 12:34:56
📡 Fetching live matches...
   Found X live matches
   Checking: Team A vs Team B (45')
   Checking: Team C vs Team D (72')
✅ Scan complete!
```

### Wenn eine rote Karte passiert:

```
🔴 RED CARD DETECTED!
   Player: Max Mustermann
   Team: FC Example
   Match: Home vs Away
   Minute: 34'
✅ Telegram alert sent for Max Mustermann
```

**UND** du bekommst eine Telegram-Nachricht! 📱

---

## 📊 WIE OFT LÄUFT ES?

**Automatisch:** Alle 5 Minuten (über den Cron-Job)

**Cron-Schedule:** `*/5 * * * *`

**Ändern?** Editiere `.github/workflows/red_card_monitor.yml`:
```yaml
schedule:
  - cron: '*/3 * * * *'  # Alle 3 Minuten
```

⚠️ **Minimum ist 3 Minuten** (GitHub Actions Limit)

---

## 🐛 TROUBLESHOOTING

### Keine Telegram-Nachricht?

1. **Check Secrets:** Sind alle 3 Secrets korrekt gesetzt?
2. **Check Bot:** Hast du deinem Bot eine Nachricht gesendet?
3. **Check Chat ID:** Richtige Nummer? (keine Anführungszeichen!)

### "API Error 401"?

→ `API_FOOTBALL_KEY` ist falsch oder abgelaufen

### Workflow läuft nicht?

1. **Actions Tab** → Check ob aktiviert
2. **Secrets** → Prüfe alle 3 Secrets
3. **Main Branch** → Workflow muss auf `main` Branch sein

---

## 💰 KOSTEN

✅ **Komplett kostenlos!**

- GitHub Actions: 2000 Minuten/Monat gratis
- Dieser Bot braucht: ~30 Sekunden pro Run = ~150 Min/Monat
- Telegram: kostenlos

---

## ⚡ UPGRADE AUF RAILWAY (INSTANT ALERTS)

Falls die 5-Minuten-Verzögerung zu viel ist:

→ Sag Bescheid, dann baue ich dir die Railway-Version (ca. $6/Monat)
→ Alerts innerhalb von 30 Sekunden statt 5 Minuten!

---

## 📝 WICHTIG

- **Erster Lauf dauert:** 24 Std bis alles getrackt ist
- **State File:** `alerted_cards.json` speichert bereits gemeldete Karten
- **Automatisches Cleanup:** Karten älter als 24h werden gelöscht

**Fertig! 🎉**

Bei Fragen einfach melden!
