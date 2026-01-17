# BEST BET FINDER - Integration Guide 🎯

## ✨ WAS IST DAS?

Ein **MEGA-ANALYZER** der für jedes Live-Match die **HÖCHSTE WAHRSCHEINLICHKEIT** über **ALLE Märkte** findet!

### Analysierte Märkte:
1. ⚽ **Match Result** (1X2) - Heimsieg/Unentschieden/Auswärtssieg
2. 🎯 **Over/Under Goals** (0.5-6.5) - Alle Schwellen
3. 🟨 **Over/Under Cards** (2.5-6.5) - Alle Schwellen
4. ⚽ **Over/Under Corners** (7.5-13.5) - Alle Schwellen
5. 🎯 **Over/Under Shots** (15.5-25.5) - Alle Schwellen
6. ⚽ **BTTS Yes/No** - Both Teams To Score
7. 🛡️ **Clean Sheet** - Home/Away kein Gegentor
8. 🎯 **Team Total Goals** - Home/Away Over/Under
9. ⚽ **Next Goal** - Home/Away/None
10. 📊 **Halftime Result** (optional)

**RESULTAT:** Die Wette mit der **HÖCHSTEN WAHRSCHEINLICHKEIT** für jedes Match!

---

## 📦 INSTALLATION

### Schritt 1: Datei kopieren
```bash
cp best_bet_finder.py /dein-pfad/btts-pro-analyzer/

git add best_bet_finder.py
git commit -m "Add: Best Bet Finder"
git push origin main
```

### Schritt 2: Integration in btts_pro_app.py

Füge diesen Code **AM ENDE** von btts_pro_app.py hinzu (vor `if __name__ == "__main__":`):

```python
# =============================================
# TAB 9: BEST BET FINDER 🎯
# =============================================
with tabs[8]:  # oder tabs[9] je nachdem wie viele tabs du hast
    st.header("🎯 BEST BET FINDER - Höchste Wahrscheinlichkeit")
    st.markdown("""
    **Findet automatisch die wahrscheinlichste Wette über ALLE Märkte:**
    - Match Result (1X2)
    - Over/Under Goals/Cards/Corners
    - BTTS Yes/No
    - Clean Sheet
    - Team Totals
    - Next Goal
    
    **Empfiehlt nur die HÖCHSTE Wahrscheinlichkeit pro Match!**
    """)
    
    st.markdown("---")
    
    # Config
    col1, col2 = st.columns(2)
    
    with col1:
        min_prob_best = st.slider(
            "Min Probability %",
            min_value=50,
            max_value=95,
            value=65,
            step=5,
            key='min_prob_best'
        )
    
    with col2:
        auto_refresh_best = st.checkbox(
            "Auto-Refresh (30s)",
            value=False,
            key='auto_refresh_best'
        )
    
    if auto_refresh_best:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=30000, key="best_bet_refresh")
        except:
            st.warning("streamlit-autorefresh not available")
    
    st.markdown("---")
    
    if st.button("🎯 Find Best Bets", key='find_best_bets'):
        with st.spinner("Analyzing all markets..."):
            try:
                from best_bet_finder import BestBetFinder, display_best_bet
                
                # Get live matches
                live_matches = api_football.get_live_matches()
                
                if not live_matches:
                    st.info("No live matches at the moment")
                else:
                    # Filter our leagues
                    our_league_ids = list(analyzer.engine.LEAGUES_CONFIG.values())
                    live_matches = [m for m in live_matches 
                                  if m['league']['id'] in our_league_ids]
                    
                    st.success(f"📊 Found {len(live_matches)} live matches in our leagues")
                    
                    if len(live_matches) == 0:
                        st.info("No matches in our configured leagues")
                    else:
                        # Analyze each match
                        finder = BestBetFinder()
                        
                        best_bets_found = []
                        
                        for match in live_matches:
                            fixture = match['fixture']
                            teams = match['teams']
                            goals = match['goals']
                            
                            fixture_id = fixture['id']
                            home_team = teams['home']['name']
                            away_team = teams['away']['name']
                            minute = fixture['status']['elapsed'] or 0
                            home_score = goals['home'] if goals['home'] is not None else 0
                            away_score = goals['away'] if goals['away'] is not None else 0
                            
                            # Skip if too early
                            if minute < 10:
                                continue
                            
                            # Get stats
                            stats = api_football.get_match_statistics(fixture_id)
                            
                            if not stats:
                                continue
                            
                            # Extract xG
                            try:
                                xg_home = float(stats.get('xg_home') or 0)
                                xg_away = float(stats.get('xg_away') or 0)
                            except:
                                # Estimate from shots
                                shots_home = int(stats.get('shots_home') or 0)
                                shots_away = int(stats.get('shots_away') or 0)
                                shots_target_home = int(stats.get('shots_on_target_home') or 0)
                                shots_target_away = int(stats.get('shots_on_target_away') or 0)
                                
                                xg_home = shots_home * 0.08 + shots_target_home * 0.25
                                xg_away = shots_away * 0.08 + shots_target_away * 0.25
                            
                            # Create match_data
                            match_data = {
                                'home_team': home_team,
                                'away_team': away_team,
                                'home_score': home_score,
                                'away_score': away_score,
                                'minute': minute,
                                'league': match['league']['name']
                            }
                            
                            # Find best bet
                            result = finder.find_best_bet(match_data, minute, stats)
                            
                            # Filter by probability
                            if result['best_bet']['probability'] >= min_prob_best:
                                best_bets_found.append(result)
                        
                        # Display results
                        if not best_bets_found:
                            st.warning(f"⚠️ No bets with probability >= {min_prob_best}%")
                            st.info("💡 Try lowering Min Probability or wait for better opportunities!")
                        else:
                            st.success(f"🔥 Found {len(best_bets_found)} high-probability bets!")
                            
                            # Sort by probability
                            best_bets_found.sort(
                                key=lambda x: x['best_bet']['probability'],
                                reverse=True
                            )
                            
                            # Display each
                            for result in best_bets_found:
                                display_best_bet(result)
                                st.markdown("---")
            
            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())
```

### Schritt 3: Tabs Array anpassen

Finde die Zeile mit:
```python
tabs = st.tabs([
    "📊 Pre-Match",
    "🔴 Ultra Live",
    "🌍 League Data",
    # ... weitere tabs
])
```

Füge hinzu:
```python
tabs = st.tabs([
    "📊 Pre-Match",
    "🔴 Ultra Live",
    "🌍 League Data",
    # ... weitere tabs
    "🎯 Best Bet Finder"  # ← NEU!
])
```

---

## 🚀 USAGE

Nach Deploy:

1. Öffne **"🎯 Best Bet Finder"** Tab
2. Setze Min Probability (empfohlen: 65%)
3. Optional: Auto-Refresh aktivieren
4. Click **"🎯 Find Best Bets"**

### Erwartetes Ergebnis:
```
🏆 HIGHEST PROBABILITY BET

Match: Bayern vs Dortmund (Min 67', Score 2-1)

Market: Total Goals Over 2.5
Selection: Over 2.5
Probability: 89.3% 🔥🔥

Current Status: 3 goals scored
Why? Current: 3, Expected total: 4.2, High xG momentum

---

📊 TOP 5 BETS:
1. Total Goals Over 2.5 (89.3%)
2. Match Result: 1 (Home Win) (81.2%)
3. BTTS Yes (76.5%)
4. Bayern Total Goals Over 1.5 (74.3%)
5. Total Corners Over 9.5 (68.7%)

---

📈 Total markets analyzed: 47
✅ High probability bets (≥60%): 12
```

---

## 🎯 WAS MACHT ES ANDERS?

### Traditionelle Alternative Markets:
- Zeigt ALLE Opportunities mit min 60% an
- User muss selbst entscheiden

### Best Bet Finder:
- ✅ Findet automatisch die **HÖCHSTE** Wahrscheinlichkeit
- ✅ Vergleicht **ALLE Märkte** (nicht nur Cards/Corners)
- ✅ Gibt **EINE klare Empfehlung** pro Match
- ✅ Zeigt Top 5 als Backup

**Für Wettende die wissen wollen: "Was ist die sicherste Wette JETZT?"**

---

## 📊 BERECHNUNGEN

### Match Result (1X2)
```python
# Nutzt:
- Aktueller Spielstand (Basis)
- xG Momentum (verbleibende Zeit)
- Possession
- Dangerous Attacks
- Zeit Faktor (später = aktuelles Ergebnis wahrscheinlicher)

# Bei 2-1 in Min 75:
base_home = 70 (führt)
+ xG adjustment (momentum)
+ time_weight (1.5x für späte Phase)
= 78.5% Home Win
```

### Over/Under Goals
```python
# Poisson-basiert:
current_goals = 3
xg_rate = 0.05 goals/min
expected_remaining = 0.05 × 15 min = 0.75
expected_total = 3 + 0.75 = 3.75

P(Over 3.5) = 1 - Poisson(0, λ=0.75) = 52.8%
P(Over 2.5) = 100% (bereits getroffen)
```

### Cards Market
```python
# Fouls-basiert:
current_cards = 4
fouls_per_min = 0.4
expected_fouls_remaining = 0.4 × 15 = 6
expected_cards = 6 / 4.5 = 1.33

Phase bonus (Min 75+): ×1.3 = 1.73
expected_total = 4 + 1.73 = 5.73

P(Over 5.5) = 48.2%
P(Over 4.5) = 86.7%
```

### BTTS Yes/No
```python
# Wenn 2-0 in Min 60:
P(Away scores) = 1 - e^(-xG_remaining)
P(Away scores) = 1 - e^(-0.8) = 55.1%

P(BTTS Yes) = 100% × 55.1% = 55.1%
P(BTTS No) = 44.9%
```

---

## 🧪 BEISPIELE

### Beispiel 1: Führendes Team spätes Spiel
```
Min 78', Score 2-1, xG 1.8-1.2

BEST BET: Match Result - Home Win (84.7%)
- Score advantage
- Late game (time weight 1.4x)
- xG momentum positive
- 12 min remaining
```

### Beispiel 2: Hohe xG Rate
```
Min 55', Score 1-1, xG 2.5-2.3

BEST BET: Over 3.5 Goals (78.3%)
- High xG rate (0.087/min)
- Expected total: 4.5 goals
- Only 0.5 more needed
- 35 min remaining
```

### Beispiel 3: Viele Fouls
```
Min 62', Score 0-0, 18 fouls

BEST BET: Over 4.5 Cards (82.1%)
- High foul rate (0.29/min)
- Expected 8.1 more fouls
- Already 3 cards
- Late phase boost
```

---

## 🔒 FEATURES

✅ **Automatische Markt-Analyse** - Alle 40+ Märkte
✅ **Intelligente Priorisierung** - Höchste Wahrscheinlichkeit first
✅ **Klare Begründung** - Warum ist das die beste Wette?
✅ **Top 5 Backup** - Falls Best Bet nicht gefällt
✅ **Live Updates** - Mit Auto-Refresh
✅ **Filter** - Min Probability einstellbar
✅ **League Filter** - Nur unsere konfigurierten Ligen

---

## 💡 PRO TIPS

1. **Min Probability 65-75%** für conservative Wetten
2. **Min Probability 55-65%** für mehr Opportunities
3. **Auto-Refresh ON** für schnelle Updates
4. **Top 5 checken** wenn Best Bet nicht gefällt
5. **Reasoning lesen** um Logik zu verstehen

---

## 🎓 PHILOSOPHIE

**Buchmacher tricksen mit Quoten!**
- Niedrige Quoten bei hoher Wahrscheinlichkeit
- Hohe Quoten bei niedriger Wahrscheinlichkeit

**Unser Ansatz:**
- Ignoriere Quoten komplett
- Finde HÖCHSTE WAHRSCHEINLICHKEIT
- Lass Buchmacher ihre Quoten anpassen
- **Value = Wahrscheinlichkeit, nicht Quote!**

**Beispiel:**
- Bayern gewinnt: 95% Wahrscheinlichkeit, Quote 1.05 ❌
- Over 2.5: 89% Wahrscheinlichkeit, Quote 1.80 ✅

**Best Bet Finder wählt Over 2.5!**

---

Made with 🎯 (findet IMMER die höchste Wahrscheinlichkeit!)
