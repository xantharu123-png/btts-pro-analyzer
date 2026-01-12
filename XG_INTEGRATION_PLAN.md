# 🎯 xG (Expected Goals) Integration - Der Plan

## 📊 WAS IST xG?

**Expected Goals (xG)** misst die **Qualität** von Torchancen:

```
Beispiel:
Team A: 2 Tore aus xG 0.8  → Überperfomed! (Glück)
Team B: 1 Tor aus xG 2.3   → Underperfomed! (Pech)

→ Team B hatte bessere Chancen, BTTS wahrscheinlicher!
```

---

## 🚀 3 WEGE ZU xG-DATEN:

### **Option 1: Understat.com (Web Scraping) - KOSTENLOS! ✅**

**Verfügbarkeit:**
- ✅ Premier League
- ✅ La Liga
- ✅ Bundesliga
- ✅ Serie A
- ✅ Ligue 1
- ❌ Championship, Eredivisie, etc.

**Wie funktioniert's:**
```python
import requests
from bs4 import BeautifulSoup

url = "https://understat.com/match/12345"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Extract xG from JavaScript
# Home xG: 1.85
# Away xG: 2.13
```

**Vorteile:**
- ✅ Kostenlos
- ✅ Sehr gute Daten
- ✅ Top 5 Ligen

**Nachteile:**
- ❌ Web Scraping (rechtlich grau)
- ❌ Kann brechen bei Layout-Änderungen
- ❌ Nicht alle Ligen

---

### **Option 2: FBref.com (Web Scraping) - KOSTENLOS! ✅**

**Verfügbarkeit:**
- ✅ ALLE Ligen die wir haben!
- ✅ Championship
- ✅ Eredivisie
- ✅ Brasileirão

**Wie funktioniert's:**
```python
url = f"https://fbref.com/en/matches/{match_id}"
# Scrape xG from match report
```

**Vorteile:**
- ✅ Kostenlos
- ✅ ALLE unsere Ligen!
- ✅ Sehr detailliert

**Nachteile:**
- ❌ Web Scraping
- ❌ Komplexer zu parsen

---

### **Option 3: Premium APIs - KOSTENPFLICHTIG 💰**

#### **A) StatsBomb API**
- 💰 **$500-1000+/Monat**
- ✅ Professionelle Daten
- ✅ Alle Ligen
- ❌ Sehr teuer!

#### **B) Opta API**
- 💰 **$1000+/Monat**
- ✅ Best in class
- ❌ Nur für große Firmen

#### **C) API-Football (RapidAPI)**
- 💰 **$50-100/Monat**
- ✅ Einige Ligen haben xG
- ⚠️ Nicht alle Spiele

---

## 🎯 MEINE EMPFEHLUNG: FBref Web Scraping!

**Warum FBref?**
- ✅ Kostenlos
- ✅ ALLE unsere Ligen
- ✅ Zuverlässig
- ✅ Sehr gute Daten

---

## 🛠️ IMPLEMENTATION PLAN:

### **Phase 1: FBref Scraper (2-3 Stunden)**

```python
# fbref_scraper.py

def get_match_xg(match_date, home_team, away_team):
    """
    Scrape xG from FBref for a specific match
    """
    # 1. Search for match on FBref
    # 2. Extract xG values
    # 3. Return home_xg, away_xg
    
    return {
        'home_xg': 1.85,
        'away_xg': 2.13,
        'home_xg_per_shot': 0.12,
        'away_xg_per_shot': 0.18
    }
```

### **Phase 2: xG in Datenbank (30 Min)**

```sql
ALTER TABLE matches ADD COLUMN home_xg REAL;
ALTER TABLE matches ADD COLUMN away_xg REAL;
```

### **Phase 3: xG in ML-Modell (1 Stunde)**

```python
# Neue Features:
features = [
    home_btts_rate,
    away_btts_rate,
    home_xg,           # NEU!
    away_xg,           # NEU!
    xg_difference,     # NEU!
    # ... rest
]

# Impact: +5-8% Genauigkeit!
```

---

## 📈 ERWARTETE VERBESSERUNG:

### **Ohne xG (aktuell):**
```
Genauigkeit: 65-67%
ROI: +17%
```

### **Mit xG:**
```
Genauigkeit: 70-75% 🔥
ROI: +30-40% 💰
```

**Das wäre MASSIV!**

---

## ⏰ ZEITPLAN:

### **Sofort (Heute):**
- ✅ H2H-Gewichtung (FERTIG!)
- ✅ Wetter-Integration (IN ARBEIT!)

### **Nächste Woche:**
- 🔨 FBref Scraper bauen
- 🔨 xG in DB speichern
- 🔨 Historische Daten laden

### **Übernächste Woche:**
- 🔨 xG in ML-Modell integrieren
- 🔨 Retrain mit xG
- 🔨 Testen & Optimieren

---

## 🚨 WICHTIGE HINWEISE:

### **Web Scraping:**
⚠️ Rechtlich grau - nicht 100% legal
⚠️ FBref könnte es blockieren
⚠️ Rate Limiting beachten!

### **Alternative - Manuell:**
- Nur Top-Spiele mit xG analysieren
- xG manuell von FBref holen
- In Excel tracken
- Für wichtige Wetten nutzen

---

## 💡 PRAGMATISCHER ANSATZ:

### **Phase 1: Hybrid-Lösung**

**Für Top 5 Ligen:**
- Understat scraping (einfacher)
- Funktioniert gut für BL, PL, etc.

**Für andere Ligen:**
- Ohne xG (nutze aktuelle Features)
- ODER manuell für wichtige Spiele

### **Phase 2: Voll-Integration**
- FBref für ALLE Ligen
- Wenn Phase 1 gut funktioniert

---

## 🎯 NÄCHSTE SCHRITTE FÜR xG:

1. ✅ **Entscheidung:** Understat ODER FBref?
2. ✅ **Scraper bauen** (2-3 Std)
3. ✅ **Testen** mit paar Matches
4. ✅ **DB updaten**
5. ✅ **ML-Modell erweitern**
6. ✅ **Retrain**
7. ✅ **Live schalten**

**Geschätzter Zeitaufwand: 6-8 Stunden total**
**Impact: +5-8% Genauigkeit = RIESIG!**

---

## 🤔 DEINE ENTSCHEIDUNG:

**Willst du xG wirklich?**

**JA → Dann:**
1. Ich baue Understat Scraper (2-3 Std)
2. Für Top 5 Ligen
3. Du testest es
4. Wenn gut → FBref für alle Ligen

**NEIN → Dann:**
- H2H + Wetter reichen erst mal
- xG kommt später

---

**Was sagst du? xG jetzt oder später?** 🤔
