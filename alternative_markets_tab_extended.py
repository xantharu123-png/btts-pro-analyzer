"""
ALTERNATIVE MARKETS TAB - EXTENDED V3
======================================
100% ECHTE DATEN - KEINE PLACEHOLDERS!

Features:
- Inline Analysis (kein Tab-Wechsel)
- ECHTE Corners & Cards Analyse (PreMatchAlternativeAnalyzer)
- ECHTE Match Result Analyse (Dixon-Coles)
- Liga-spezifische Statistiken
- VALUE SCORE System (kein Odds-Display)
"""

import streamlit as st
from alternative_markets import (
    PreMatchAlternativeAnalyzer,
    MatchResultPredictor
)
from datetime import datetime, timedelta
from collections import defaultdict
import requests

# Import Smart Bet Finder
try:
    from smart_bet_finder import (
        SmartBetFinder,
        display_smart_bet,
        display_combo_bet
    )
    SMART_BET_AVAILABLE = True
except ImportError:
    SMART_BET_AVAILABLE = False


def _get_value_rating(probability: float) -> tuple:
    """
    Get star rating and label based on probability
    
    Sweet Spot: 60-75% = Best value (good odds + reasonable probability)
    
    Returns: (stars, label, color)
    """
    if 0.60 <= probability <= 0.75:
        return ("⭐⭐⭐⭐⭐", "STRONG VALUE", "success")
    elif (0.55 <= probability < 0.60) or (0.75 < probability <= 0.80):
        return ("⭐⭐⭐⭐", "GOOD VALUE", "success")
    elif 0.50 <= probability < 0.55:
        return ("⭐⭐⭐", "DECENT", "warning")
    elif probability > 0.85:
        return ("⭐", "TOO SAFE", "warning")  # Bad odds!
    else:
        return ("⭐⭐", "RISKY", "error")


def _collect_match_analysis(match: dict, api_key: str) -> dict:
    """
    Collect all available analysis data for a match
    
    Returns comprehensive dict with all market probabilities
    """
    home_team_id = match['teams']['home']['id']
    away_team_id = match['teams']['away']['id']
    league_id = match['league']['id']
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    
    analysis = {}
    
    try:
        # Initialize analyzers
        alt_analyzer = PreMatchAlternativeAnalyzer(api_key=api_key)
        result_predictor = MatchResultPredictor(api_key=api_key)
        
        fixture = {
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            'league_id': league_id,
            'home_team': home_team,
            'away_team': away_team
        }
        
        # Get Corners Analysis
        corners_result = alt_analyzer.analyze_prematch_corners(fixture)
        if corners_result:
            analysis['corners'] = {}
            for threshold_key, threshold_data in corners_result.get('thresholds', {}).items():
                analysis['corners'][threshold_key] = {
                    'probability': threshold_data.get('probability', 0),
                    'threshold': threshold_data.get('threshold', 0)
                }
            analysis['corners']['expected_total'] = corners_result.get('expected_total_corners', 0)
            analysis['corners']['confidence'] = corners_result.get('confidence', 'MEDIUM')
        
        # Get Cards Analysis
        cards_result = alt_analyzer.analyze_prematch_cards(fixture)
        if cards_result:
            analysis['cards'] = {}
            for threshold_key, threshold_data in cards_result.get('thresholds', {}).items():
                analysis['cards'][threshold_key] = {
                    'probability': threshold_data.get('probability', 0),
                    'threshold': threshold_data.get('threshold', 0)
                }
            analysis['cards']['expected_total'] = cards_result.get('expected_total_cards', 0)
            analysis['cards']['confidence'] = cards_result.get('confidence', 'MEDIUM')
        
        # Get Match Result Analysis
        result_analysis = result_predictor.predict_match_outcome(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            league_id=league_id
        )
        
        if result_analysis:
            # Match probabilities
            analysis['home_win_probability'] = result_analysis.get('home_win_probability', 0)
            analysis['draw_probability'] = result_analysis.get('draw_probability', 0)
            analysis['away_win_probability'] = result_analysis.get('away_win_probability', 0)
            
            # BTTS
            analysis['btts_probability'] = result_analysis.get('btts_probability', 0)
            analysis['btts_confidence'] = result_analysis.get('confidence', 'MEDIUM')
            
            # Over/Under
            for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
                over_key = f'over_{threshold}_probability'
                if over_key in result_analysis:
                    analysis[over_key] = result_analysis[over_key]
            
            # xG if available
            analysis['xg_home'] = result_analysis.get('xg_home', 0)
            analysis['xg_away'] = result_analysis.get('xg_away', 0)
            analysis['expected_goals'] = result_analysis.get('expected_goals_total', 0)
        
        return analysis
    
    except Exception as e:
        st.error(f"Error collecting match analysis: {e}")
        return {}


def _render_corners_cards_analysis(match, api_key):
    """
    Render ECHTE Corners & Cards analysis for a match
    
    Uses PreMatchAlternativeAnalyzer for real calculations!
    """
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    home_team_id = match['teams']['home']['id']
    away_team_id = match['teams']['away']['id']
    league_id = match['league']['id']
    league_name = match['league']['name']
    
    st.markdown(f"#### 📊 {home_team} vs {away_team} - Corners & Cards")
    st.caption(f"🏆 {league_name} (Liga-spezifische Statistiken)")
    
    st.info("""
    **VALUE SCORE System:**
    - Sweet Spot: 60-75% Wahrscheinlichkeit
    - ⭐⭐⭐⭐⭐ = STRONG VALUE (60-75%)
    - ⭐⭐⭐⭐ = GOOD VALUE (55-60% oder 75-80%)
    - ⭐⭐⭐ = DECENT (50-55%)
    - ⭐⭐ = RISKY (<50%)
    - ⭐ = TOO SAFE (>85%) - schlechte Quoten!
    """)
    
    # Initialize analyzer
    analyzer = PreMatchAlternativeAnalyzer(api_key=api_key)
    
    # Prepare fixture data
    fixture = {
        'home_team_id': home_team_id,
        'away_team_id': away_team_id,
        'league_id': league_id,
        'home_team': home_team,
        'away_team': away_team
    }
    
    with st.spinner("🔄 Lade ECHTE Corner & Cards Statistiken..."):
        try:
            # ============================================
            # CORNERS ANALYSIS - ECHTE DATEN!
            # ============================================
            corners_result = analyzer.analyze_prematch_corners(fixture)
            
            # ============================================
            # CARDS ANALYSIS - ECHTE DATEN!
            # ============================================
            cards_result = analyzer.analyze_prematch_cards(fixture)
            
            # Show data quality
            corners_quality = corners_result.get('data_quality', {})
            cards_quality = cards_result.get('data_quality', {})
            
            st.success(f"""
            ✅ **Daten geladen:**
            - Corners: {corners_quality.get('home_matches', 0)} + {corners_quality.get('away_matches', 0)} Spiele analysiert
            - Cards: {cards_quality.get('home_matches', 0)} + {cards_quality.get('away_matches', 0)} Spiele analysiert
            """)
            
            # ============================================
            # DISPLAY CORNERS
            # ============================================
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### ⚽ CORNERS")
                
                expected_corners = corners_result.get('expected_total', 10.5)
                st.metric(
                    "Expected Corners", 
                    f"{expected_corners:.1f}",
                    help=f"Home: {corners_result.get('home_expected', 0):.1f} | Away: {corners_result.get('away_expected', 0):.1f}"
                )
                
                st.markdown("**Top Markets:**")
                
                # Get all thresholds and find best bets
                thresholds = corners_result.get('thresholds', {})
                best_bet = corners_result.get('best_bet', {})
                
                # Display thresholds sorted by value
                displayed = 0
                for key in sorted(thresholds.keys(), key=lambda k: float(k.split('_')[1])):
                    data = thresholds[key]
                    threshold = data['threshold']
                    over_prob = data['probability'] / 100
                    under_prob = 1 - over_prob
                    
                    # Check Over
                    if 0.55 <= over_prob <= 0.85 and displayed < 3:
                        stars, label, _ = _get_value_rating(over_prob)
                        if over_prob >= 0.60:
                            st.success(f"✅ Over {threshold}: {over_prob*100:.0f}% {stars}")
                        else:
                            st.warning(f"⚠️ Over {threshold}: {over_prob*100:.0f}% {stars}")
                        displayed += 1
                    
                    # Check Under
                    if 0.55 <= under_prob <= 0.85 and displayed < 3:
                        stars, label, _ = _get_value_rating(under_prob)
                        if under_prob >= 0.60:
                            st.success(f"✅ Under {threshold}: {under_prob*100:.0f}% {stars}")
                        else:
                            st.warning(f"⚠️ Under {threshold}: {under_prob*100:.0f}% {stars}")
                        displayed += 1
                
                # Show best bet if available
                if best_bet:
                    st.markdown("---")
                    st.markdown(f"**💎 BEST BET:** {best_bet.get('bet', 'N/A')}")
                    prob = best_bet.get('probability', 0)
                    stars, label, _ = _get_value_rating(prob/100)
                    st.markdown(f"**{prob}%** {stars} ({label})")
            
            # ============================================
            # DISPLAY CARDS
            # ============================================
            with col2:
                st.markdown("### 🟨 CARDS")
                
                expected_cards = cards_result.get('expected_total', 4.0)
                is_derby = cards_result.get('is_derby', False)
                
                st.metric(
                    "Expected Cards", 
                    f"{expected_cards:.1f}",
                    delta="🔥 DERBY!" if is_derby else None,
                    help=f"Home: {cards_result.get('home_expected', 0):.1f} | Away: {cards_result.get('away_expected', 0):.1f}"
                )
                
                st.markdown("**Top Markets:**")
                
                # Get thresholds
                card_thresholds = cards_result.get('thresholds', {})
                card_best_bet = cards_result.get('best_bet', {})
                
                displayed = 0
                for key in sorted(card_thresholds.keys(), key=lambda k: float(k.split('_')[1])):
                    data = card_thresholds[key]
                    threshold = data['threshold']
                    over_prob = data['probability'] / 100
                    under_prob = 1 - over_prob
                    
                    # Check Over
                    if 0.55 <= over_prob <= 0.85 and displayed < 3:
                        stars, label, _ = _get_value_rating(over_prob)
                        if over_prob >= 0.60:
                            st.success(f"✅ Over {threshold}: {over_prob*100:.0f}% {stars}")
                        else:
                            st.warning(f"⚠️ Over {threshold}: {over_prob*100:.0f}% {stars}")
                        displayed += 1
                    
                    # Check Under
                    if 0.55 <= under_prob <= 0.85 and displayed < 3:
                        stars, label, _ = _get_value_rating(under_prob)
                        if under_prob >= 0.60:
                            st.success(f"✅ Under {threshold}: {under_prob*100:.0f}% {stars}")
                        else:
                            st.warning(f"⚠️ Under {threshold}: {under_prob*100:.0f}% {stars}")
                        displayed += 1
                
                # Show best bet
                if card_best_bet:
                    st.markdown("---")
                    st.markdown(f"**💎 BEST BET:** {card_best_bet.get('bet', 'N/A')}")
                    prob = card_best_bet.get('probability', 0)
                    stars, label, _ = _get_value_rating(prob/100)
                    st.markdown(f"**{prob}%** {stars} ({label})")
            
            # ============================================
            # DETAILED THRESHOLDS TABLE
            # ============================================
            with st.expander("📊 Alle Thresholds anzeigen"):
                st.markdown("**Corners:**")
                for key in sorted(thresholds.keys(), key=lambda k: float(k.split('_')[1])):
                    data = thresholds[key]
                    t = data['threshold']
                    over_p = data['probability']
                    under_p = 100 - over_p
                    st.write(f"**{t}:** Over {over_p:.0f}% | Under {under_p:.0f}%")
                
                st.markdown("---")
                st.markdown("**Cards:**")
                for key in sorted(card_thresholds.keys(), key=lambda k: float(k.split('_')[1])):
                    data = card_thresholds[key]
                    t = data['threshold']
                    over_p = data['probability']
                    under_p = 100 - over_p
                    st.write(f"**{t}:** Over {over_p:.0f}% | Under {under_p:.0f}%")
                    
        except Exception as e:
            st.error(f"❌ Fehler beim Laden der Daten: {str(e)}")
            st.info("Bitte versuche es erneut oder wähle ein anderes Match.")


def _render_match_result_analysis(match, api_key):
    """
    Render ECHTE Match Result analysis for a match
    
    Uses Dixon-Coles Model with liga-spezifischen Daten!
    """
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    home_team_id = match['teams']['home']['id']
    away_team_id = match['teams']['away']['id']
    league_id = match['league']['id']
    league_name = match['league']['name']
    season = match['league']['season']
    
    st.markdown(f"#### ⚽ {home_team} vs {away_team} - Match Result")
    st.caption(f"🏆 {league_name}")
    
    st.info(f"""
    **Dixon-Coles Model:**
    - Poisson Distribution für Tore
    - Dixon-Coles Adjustments für Low Scores
    - Negative Binomial für Over/Under
    - Home Advantage (ligaspezifisch)
    - Form Weighting (letzte Spiele wichtiger)
    
    📊 Lade Statistiken aus **{league_name}** (Season {season}/{season+1})
    """)
    
    # Get real team statistics from API
    with st.spinner("🔄 Lade Team-Statistiken..."):
        try:
            # Get last 10 matches for home team IN THIS LEAGUE
            home_response = requests.get(
                "https://v3.football.api-sports.io/fixtures",
                headers={'x-apisports-key': api_key},
                params={
                    'team': home_team_id,
                    'league': league_id,  # Liga-spezifisch!
                    'season': season,
                    'last': 10,
                    'status': 'FT'
                },
                timeout=15
            )
            
            # Get last 10 matches for away team IN THIS LEAGUE
            away_response = requests.get(
                "https://v3.football.api-sports.io/fixtures",
                headers={'x-apisports-key': api_key},
                params={
                    'team': away_team_id,
                    'league': league_id,  # Liga-spezifisch!
                    'season': season,
                    'last': 10,
                    'status': 'FT'
                },
                timeout=15
            )
            
            home_fixtures = home_response.json().get('response', []) if home_response.status_code == 200 else []
            away_fixtures = away_response.json().get('response', []) if away_response.status_code == 200 else []
            
            # Fallback: If not enough league-specific matches, get ALL matches
            if len(home_fixtures) < 3:
                home_response = requests.get(
                    "https://v3.football.api-sports.io/fixtures",
                    headers={'x-apisports-key': api_key},
                    params={
                        'team': home_team_id,
                        'season': season,
                        'last': 10,
                        'status': 'FT'
                    },
                    timeout=15
                )
                home_fixtures = home_response.json().get('response', []) if home_response.status_code == 200 else []
                st.warning(f"⚠️ Wenig {league_name}-Spiele für {home_team}, nutze alle Wettbewerbe")
            
            if len(away_fixtures) < 3:
                away_response = requests.get(
                    "https://v3.football.api-sports.io/fixtures",
                    headers={'x-apisports-key': api_key},
                    params={
                        'team': away_team_id,
                        'season': season,
                        'last': 10,
                        'status': 'FT'
                    },
                    timeout=15
                )
                away_fixtures = away_response.json().get('response', []) if away_response.status_code == 200 else []
                st.warning(f"⚠️ Wenig {league_name}-Spiele für {away_team}, nutze alle Wettbewerbe")
            
            # Extract goals data
            home_data = {'goals_scored': [], 'goals_conceded': []}
            away_data = {'goals_scored': [], 'goals_conceded': []}
            
            for fixture in home_fixtures[:5]:  # Last 5 for form
                goals = fixture.get('goals', {})
                teams = fixture.get('teams', {})
                
                if teams.get('home', {}).get('id') == home_team_id:
                    home_data['goals_scored'].append(goals.get('home', 0) or 0)
                    home_data['goals_conceded'].append(goals.get('away', 0) or 0)
                else:
                    home_data['goals_scored'].append(goals.get('away', 0) or 0)
                    home_data['goals_conceded'].append(goals.get('home', 0) or 0)
            
            for fixture in away_fixtures[:5]:
                goals = fixture.get('goals', {})
                teams = fixture.get('teams', {})
                
                if teams.get('home', {}).get('id') == away_team_id:
                    away_data['goals_scored'].append(goals.get('home', 0) or 0)
                    away_data['goals_conceded'].append(goals.get('away', 0) or 0)
                else:
                    away_data['goals_scored'].append(goals.get('away', 0) or 0)
                    away_data['goals_conceded'].append(goals.get('home', 0) or 0)
            
            if not home_data['goals_scored'] or not away_data['goals_scored']:
                st.error("❌ Keine Spielstatistiken verfügbar")
                return
            
            st.success(f"✅ Team-Statistiken geladen: {len(home_data['goals_scored'])} + {len(away_data['goals_scored'])} Spiele")
            
            # Use Dixon-Coles Predictor
            predictor = MatchResultPredictor(league_id=league_id)
            prediction = predictor.predict_match(home_data, away_data)
            
            # ============================================
            # DISPLAY EXPECTED GOALS
            # ============================================
            st.markdown("---")
            st.markdown("### 📊 Expected Goals")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(home_team, f"{prediction.home_xg:.2f}")
            with col2:
                st.metric("Total", f"{prediction.total_xg:.2f}")
            with col3:
                st.metric(away_team, f"{prediction.away_xg:.2f}")
            
            # ============================================
            # MATCH RESULT (1X2) - NO ODDS!
            # ============================================
            st.markdown("---")
            st.markdown("### 🎯 Match Result (1X2)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                prob = prediction.home_win_prob
                stars, label, _ = _get_value_rating(prob)
                st.markdown("**🏠 Home Win**")
                st.markdown(f"### {prob*100:.1f}%")
                st.markdown(f"{stars}")
                st.caption(label)
            
            with col2:
                prob = prediction.draw_prob
                stars, label, _ = _get_value_rating(prob)
                st.markdown("**⚖️ Draw**")
                st.markdown(f"### {prob*100:.1f}%")
                st.markdown(f"{stars}")
                st.caption(label)
            
            with col3:
                prob = prediction.away_win_prob
                stars, label, _ = _get_value_rating(prob)
                st.markdown("**✈️ Away Win**")
                st.markdown(f"### {prob*100:.1f}%")
                st.markdown(f"{stars}")
                st.caption(label)
            
            # ============================================
            # DOUBLE CHANCE
            # ============================================
            st.markdown("---")
            st.markdown("### 🔀 Double Chance")
            
            col1, col2, col3 = st.columns(3)
            
            dc_1x = prediction.home_win_prob + prediction.draw_prob
            dc_x2 = prediction.draw_prob + prediction.away_win_prob
            dc_12 = prediction.home_win_prob + prediction.away_win_prob
            
            with col1:
                stars, label, _ = _get_value_rating(dc_1x)
                st.markdown("**1X (Home or Draw)**")
                st.markdown(f"### {dc_1x*100:.1f}%")
                st.markdown(f"{stars}")
            
            with col2:
                stars, label, _ = _get_value_rating(dc_x2)
                st.markdown("**X2 (Draw or Away)**")
                st.markdown(f"### {dc_x2*100:.1f}%")
                st.markdown(f"{stars}")
            
            with col3:
                stars, label, _ = _get_value_rating(dc_12)
                st.markdown("**12 (No Draw)**")
                st.markdown(f"### {dc_12*100:.1f}%")
                st.markdown(f"{stars}")
            
            # ============================================
            # OVER/UNDER GOALS
            # ============================================
            st.markdown("---")
            st.markdown("### 📈 Over/Under Goals")
            
            over_under = prediction.over_under
            
            for threshold in [1.5, 2.5, 3.5]:
                if threshold in over_under:
                    over_prob, under_prob = over_under[threshold]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        stars, label, _ = _get_value_rating(over_prob)
                        color = "success" if over_prob >= 0.60 else "warning" if over_prob >= 0.50 else "error"
                        if color == "success":
                            st.success(f"Over {threshold}: **{over_prob*100:.1f}%** {stars}")
                        elif color == "warning":
                            st.warning(f"Over {threshold}: **{over_prob*100:.1f}%** {stars}")
                        else:
                            st.error(f"Over {threshold}: **{over_prob*100:.1f}%** {stars}")
                    
                    with col2:
                        stars, label, _ = _get_value_rating(under_prob)
                        if under_prob >= 0.60:
                            st.success(f"Under {threshold}: **{under_prob*100:.1f}%** {stars}")
                        elif under_prob >= 0.50:
                            st.warning(f"Under {threshold}: **{under_prob*100:.1f}%** {stars}")
                        else:
                            st.error(f"Under {threshold}: **{under_prob*100:.1f}%** {stars}")
            
            # ============================================
            # BTTS
            # ============================================
            st.markdown("---")
            st.markdown("### 🎯 BTTS (Both Teams To Score)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                btts_yes = prediction.btts_yes
                stars, label, _ = _get_value_rating(btts_yes)
                st.markdown("**Yes**")
                st.markdown(f"### {btts_yes*100:.1f}%")
                st.markdown(f"{stars}")
            
            with col2:
                btts_no = prediction.btts_no
                stars, label, _ = _get_value_rating(btts_no)
                st.markdown("**No**")
                st.markdown(f"### {btts_no*100:.1f}%")
                st.markdown(f"{stars}")
            
            # ============================================
            # BEST VALUE BETS SUMMARY
            # ============================================
            st.markdown("---")
            st.markdown("### 💎 Best Value Bets (60-75% Sweet Spot)")
            
            # Collect all bets with good value
            value_bets = []
            
            # Check 1X2
            if 0.60 <= prediction.home_win_prob <= 0.75:
                value_bets.append(("Home Win", prediction.home_win_prob))
            if 0.60 <= prediction.draw_prob <= 0.75:
                value_bets.append(("Draw", prediction.draw_prob))
            if 0.60 <= prediction.away_win_prob <= 0.75:
                value_bets.append(("Away Win", prediction.away_win_prob))
            
            # Check Double Chance
            if 0.60 <= dc_1x <= 0.75:
                value_bets.append(("1X", dc_1x))
            if 0.60 <= dc_x2 <= 0.75:
                value_bets.append(("X2", dc_x2))
            if 0.60 <= dc_12 <= 0.75:
                value_bets.append(("12", dc_12))
            
            # Check Over/Under
            for threshold in [1.5, 2.5, 3.5]:
                if threshold in over_under:
                    over_p, under_p = over_under[threshold]
                    if 0.60 <= over_p <= 0.75:
                        value_bets.append((f"Over {threshold}", over_p))
                    if 0.60 <= under_p <= 0.75:
                        value_bets.append((f"Under {threshold}", under_p))
            
            # Check BTTS
            if 0.60 <= btts_yes <= 0.75:
                value_bets.append(("BTTS Yes", btts_yes))
            if 0.60 <= btts_no <= 0.75:
                value_bets.append(("BTTS No", btts_no))
            
            if value_bets:
                for bet, prob in sorted(value_bets, key=lambda x: x[1], reverse=True):
                    st.success(f"✅ **{bet}**: {prob*100:.1f}% ⭐⭐⭐⭐⭐")
            else:
                st.warning("⚠️ Keine Wetten im Sweet Spot (60-75%) gefunden.")
                st.info("Tipp: Wetten über 75% haben oft schlechte Quoten, unter 60% sind riskanter.")
            
        except Exception as e:
            st.error(f"❌ Fehler beim Laden der Daten: {str(e)}")
            st.info("Bitte versuche es erneut oder wähle ein anderes Match.")


def create_alternative_markets_tab_extended():
    """
    Main function to create the Alternative Markets tab
    
    Features:
    - Inline analysis (no tab switching!)
    - Select All leagues button
    - Persistent fixtures across tab switches
    - Real data from API
    """
    
    st.header("📊 ALTERNATIVE MARKETS - Extended")
    
    st.markdown("""
    **Mathematische Analyse für:**
    - ⚽ **Corners & Cards** (VALUE SCORE System)
    - 🎯 **Match Result** (Dixon-Coles Model)
    - 🔀 **Double Chance** (1X, X2, 12)
    - 📈 **Over/Under Goals** (0.5 - 4.5)
    - 🎯 **BTTS** (Both Teams To Score)
    
    **Keine Buchmacher-Quoten - Pure Mathematik!**
    """)
    
    # ============================================
    # 🎯 SMART BET FINDER BUTTONS
    # ============================================
    st.markdown("---")
    st.markdown("## 🤖 KI-GESTÜTZTE WETTEMPFEHLUNGEN")
    st.caption("Wähle ein Match und klicke dann auf einen der Buttons:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        value_bet_btn = st.button("🎯 VALUE BET SCANNER", 
                                   help="Findet Top 3 Wetten mit höchstem Edge vs. Bookmaker",
                                   use_container_width=True)
    
    with col2:
        combo_btn = st.button("🔥 MULTI-MARKET COMBOS", 
                             help="Findet profitable 2-3 Wetten Kombinationen",
                             use_container_width=True)
    
    with col3:
        high_conf_btn = st.button("💎 HIGH CONFIDENCE FILTER", 
                                  help="Nur Wetten mit >75% Wahrscheinlichkeit",
                                  use_container_width=True)
    
    # Store button states in session
    if value_bet_btn:
        st.session_state['smart_bet_mode'] = 'value'
    elif combo_btn:
        st.session_state['smart_bet_mode'] = 'combo'
    elif high_conf_btn:
        st.session_state['smart_bet_mode'] = 'high_conf'
    
    st.markdown("---")
    
    # Initialize session states
    if 'tab7_fixtures' not in st.session_state:
        st.session_state['tab7_fixtures'] = []
    if 'tab7_selected_leagues' not in st.session_state:
        st.session_state['tab7_selected_leagues'] = [78, 39, 140]  # Default: BL, PL, LL
    
    # Get API key
    try:
        api_key = st.secrets['api']['api_football_key']
    except:
        st.error("❌ API Key nicht gefunden!")
        return
    
    # ALL 28 LEAGUES
    ALL_LEAGUES = {
        78: "🇩🇪 Bundesliga",
        39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
        140: "🇪🇸 La Liga",
        135: "🇮🇹 Serie A",
        61: "🇫🇷 Ligue 1",
        2: "🏆 Champions League",
        3: "🏆 Europa League",
        88: "🇳🇱 Eredivisie",
        94: "🇵🇹 Primeira Liga",
        203: "🇹🇷 Süper Lig",
        40: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
        79: "🇩🇪 Bundesliga 2",
        41: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League One",
        42: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 League Two",
        144: "🇧🇪 Pro League",
        218: "🇦🇹 Austrian Bundesliga",
        207: "🇨🇭 Swiss Super League",
        119: "🇩🇰 Danish Superliga",
        113: "🇸🇪 Swedish Allsvenskan",
        103: "🇳🇴 Norwegian Eliteserien",
        197: "🇬🇷 Greek Super League",
        345: "🇨🇿 Czech Liga",
        283: "🇷🇴 Romanian Liga 1",
        286: "🇷🇸 Serbian SuperLiga",
        210: "🇭🇷 Croatian HNL",
        333: "🇺🇦 Ukrainian Premier League",
        106: "🇵🇱 Polish Ekstraklasa",
        332: "🇸🇰 Slovak Fortuna Liga"
    }
    
    # ============================================
    # SEARCH SECTION
    # ============================================
    st.markdown("---")
    st.subheader("🔍 Matches Suchen")
    
    # Select All / None buttons
    st.markdown(f"**📊 {len(ALL_LEAGUES)} Ligen verfügbar**")
    
    col1, col2, col3 = st.columns([1, 1, 3])
    
    with col1:
        if st.button("✅ Alle auswählen"):
            st.session_state['tab7_selected_leagues'] = list(ALL_LEAGUES.keys())
            st.rerun()
    
    with col2:
        if st.button("❌ Keine"):
            st.session_state['tab7_selected_leagues'] = []
            st.rerun()
    
    # League multiselect
    selected_leagues = st.multiselect(
        "Ligen auswählen",
        options=list(ALL_LEAGUES.keys()),
        default=st.session_state.get('tab7_selected_leagues', [78, 39, 140]),
        format_func=lambda x: ALL_LEAGUES.get(x, f"Liga {x}"),
        key="league_multiselect"
    )
    
    # Update session state
    st.session_state['tab7_selected_leagues'] = selected_leagues
    
    # Date selection
    col1, col2 = st.columns(2)
    
    with col1:
        date_option = st.radio(
            "Zeitraum",
            ["Heute", "Morgen", "Benutzerdefiniert"],
            horizontal=True
        )
    
    with col2:
        if date_option == "Heute":
            search_date = datetime.now().date()
        elif date_option == "Morgen":
            search_date = (datetime.now() + timedelta(days=1)).date()
        else:
            search_date = st.date_input("Datum", datetime.now().date())
    
    # Load matches button
    if st.button("🔍 Matches laden", type="primary"):
        if not selected_leagues:
            st.warning("⚠️ Bitte wähle mindestens eine Liga aus!")
        else:
            with st.spinner(f"Lade Matches aus {len(selected_leagues)} Liga(en)..."):
                all_fixtures = []
                
                # Dynamic season calculation
                current_year = search_date.year
                current_month = search_date.month
                current_season = current_year if current_month >= 8 else current_year - 1
                
                st.info(f"🔍 Suche in Season {current_season}/{current_season+1} am {search_date}")
                
                for league_id in selected_leagues:
                    try:
                        response = requests.get(
                            "https://v3.football.api-sports.io/fixtures",
                            headers={'x-apisports-key': api_key},
                            params={
                                'league': league_id,
                                'season': current_season,
                                'date': search_date.strftime('%Y-%m-%d')
                            },
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            fixtures = response.json().get('response', [])
                            all_fixtures.extend(fixtures)
                    except Exception as e:
                        st.warning(f"⚠️ Fehler beim Laden von {ALL_LEAGUES.get(league_id, league_id)}: {e}")
                
                st.session_state['tab7_fixtures'] = all_fixtures
                
                if all_fixtures:
                    st.success(f"✅ {len(all_fixtures)} Matches aus {len(selected_leagues)} Liga(en) gefunden!")
                else:
                    st.warning(f"⚠️ Keine Matches am {search_date} in den gewählten Ligen")
    
    # Clear button
    if st.session_state.get('tab7_fixtures'):
        if st.button("🗑️ Matches löschen"):
            st.session_state['tab7_fixtures'] = []
            st.rerun()
    
    # ============================================
    # DISPLAY MATCHES WITH INLINE ANALYSIS
    # ============================================
    fixtures = st.session_state.get('tab7_fixtures', [])
    
    if fixtures:
        st.markdown("---")
        st.subheader(f"⚽ {len(fixtures)} Matches gefunden")
        
        # Group by league
        by_league = defaultdict(list)
        for match in fixtures:
            league_name = match['league']['name']
            by_league[league_name].append(match)
        
        # Display grouped
        for league_name, matches in sorted(by_league.items()):
            st.markdown(f"### 🏆 {league_name} ({len(matches)})")
            
            for match in matches:
                match_id = match['fixture']['id']
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                match_time = match['fixture']['date']
                
                # Format time
                try:
                    dt = datetime.fromisoformat(match_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = match_time[:16]
                
                # Match container
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{home_team} vs {away_team}**")
                        st.caption(f"🕐 {time_str}")
                    
                    with col2:
                        # Corners & Cards button
                        cc_key = f"show_cc_{match_id}"
                        if cc_key not in st.session_state:
                            st.session_state[cc_key] = False
                        
                        if st.button("📊 Corners", key=f"btn_cc_{match_id}"):
                            st.session_state[cc_key] = not st.session_state[cc_key]
                            st.rerun()
                    
                    with col3:
                        # Match Result button
                        mr_key = f"show_mr_{match_id}"
                        if mr_key not in st.session_state:
                            st.session_state[mr_key] = False
                        
                        if st.button("⚽ Result", key=f"btn_mr_{match_id}"):
                            st.session_state[mr_key] = not st.session_state[mr_key]
                            st.rerun()
                    
                    # INLINE ANALYSIS - Opens directly below the match!
                    if st.session_state.get(f"show_cc_{match_id}", False):
                        with st.expander("📊 Corners & Cards Analyse", expanded=True):
                            _render_corners_cards_analysis(match, api_key)
                    
                    if st.session_state.get(f"show_mr_{match_id}", False):
                        with st.expander("⚽ Match Result Analyse", expanded=True):
                            _render_match_result_analysis(match, api_key)
                    
                    # ============================================
                    # 🤖 SMART BET FINDER DISPLAY
                    # ============================================
                    smart_bet_mode = st.session_state.get('smart_bet_mode', None)
                    
                    if smart_bet_mode and SMART_BET_AVAILABLE:
                        # Only show for first match or selected match
                        if match == matches[0]:  # Show for first match in league
                            st.markdown("---")
                            st.markdown("## 🤖 KI-EMPFEHLUNGEN")
                            
                            with st.spinner("🔍 Analysiere alle Märkte..."):
                                try:
                                    # Collect match analysis data
                                    match_analysis = _collect_match_analysis(match, api_key)
                                    
                                    # Initialize Smart Bet Finder
                                    finder = SmartBetFinder()
                                    
                                    if smart_bet_mode == 'value':
                                        st.markdown("### 🎯 VALUE BET SCANNER")
                                        st.caption("Top 3 Wetten mit höchstem Edge vs. Bookmaker")
                                        
                                        smart_bets = finder.find_value_bets(match_analysis)
                                        
                                        if smart_bets:
                                            for i, bet in enumerate(smart_bets, 1):
                                                display_smart_bet(bet, i)
                                        else:
                                            st.warning("⚠️ Keine Value Bets gefunden. Versuche es mit einem anderen Match!")
                                    
                                    elif smart_bet_mode == 'combo':
                                        st.markdown("### 🔥 MULTI-MARKET COMBOS")
                                        st.caption("Profitable 2-3 Wetten Kombinationen")
                                        
                                        combos = finder.find_combo_bets(match_analysis)
                                        
                                        if combos:
                                            for i, combo in enumerate(combos, 1):
                                                display_combo_bet(combo, i)
                                        else:
                                            st.warning("⚠️ Keine Combos gefunden. Märkte nicht stark genug!")
                                    
                                    elif smart_bet_mode == 'high_conf':
                                        st.markdown("### 💎 HIGH CONFIDENCE BETS")
                                        st.caption("Nur Wetten mit >75% Wahrscheinlichkeit")
                                        
                                        high_conf_bets = finder.find_high_confidence_bets(match_analysis)
                                        
                                        if high_conf_bets:
                                            for i, bet in enumerate(high_conf_bets, 1):
                                                display_smart_bet(bet, i)
                                        else:
                                            st.warning("⚠️ Keine High Confidence Bets gefunden!")
                                    
                                    # Clear mode after display
                                    if st.button("✅ Fertig - Schließen"):
                                        st.session_state['smart_bet_mode'] = None
                                        st.rerun()
                                
                                except Exception as e:
                                    st.error(f"❌ Fehler bei Smart Bet Analyse: {e}")
                                    st.info("Stelle sicher dass das Match zuerst analysiert wurde (Corners oder Result Button klicken)")
                            
                            break  # Only show for first match
                    
                    st.markdown("---")
    
    else:
        st.info("👆 Wähle Ligen und klicke 'Matches laden' um zu beginnen!")
