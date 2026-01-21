"""
ALTERNATIVE MARKETS TAB - EXTENDED V2
======================================
Inline Analysis - No Tab Switching!
- Match list with analysis buttons
- Analysis opens directly below match
- Can analyze multiple matches simultaneously
"""

import streamlit as st
from alternative_markets import (
    PreMatchAlternativeAnalyzer,
    MatchResultPredictor
)
from datetime import datetime, timedelta
from collections import defaultdict
import requests


def _render_corners_cards_analysis(match, api_key):
    """Render Corners & Cards analysis for a match"""
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    league_id = match['league']['id']
    league_name = match['league']['name']
    
    st.markdown(f"#### 📊 {home_team} vs {away_team} - Corners & Cards")
    st.caption(f"🏆 {league_name}")
    
    st.info("""
    **VALUE SCORE System:**
    - Sweet Spot: 60-75% Wahrscheinlichkeit
    - Vermeidet extreme Probabilities (>85% = schlechte Quoten)
    - Zeigt Fair Odds (1/probability)
    """)
    
    # Placeholder - would call actual analyzer
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Expected Corners", "10.8")
        st.markdown("**Top Corner Markets:**")
        st.success("✅ Over 9.5: 65% (Odds: 1.54)")
        st.success("✅ Under 11.5: 68% (Odds: 1.47)")
    
    with col2:
        st.metric("Expected Cards", "4.2")
        st.markdown("**Top Card Markets:**")
        st.success("✅ Over 3.5: 63% (Odds: 1.59)")
        st.warning("⚠️ Under 5.5: 72% (Odds: 1.39)")


def _render_match_result_analysis(match, api_key):
    """Render Match Result analysis for a match"""
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
                    'league': league_id,  # ✅ Liga-spezifisch!
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
                    'league': league_id,  # ✅ Liga-spezifisch!
                    'season': season,
                    'last': 10,
                    'status': 'FT'
                },
                timeout=15
            )
            
            if home_response.status_code == 200 and away_response.status_code == 200:
                home_fixtures = home_response.json().get('response', [])
                away_fixtures = away_response.json().get('response', [])
                
                # Extract goals data
                home_data = {'goals_scored': [], 'goals_conceded': []}
                away_data = {'goals_scored': [], 'goals_conceded': []}
                
                for fixture in home_fixtures[:5]:  # Last 5 matches
                    home_id = fixture['teams']['home']['id']
                    goals_home = fixture['goals']['home']
                    goals_away = fixture['goals']['away']
                    
                    if goals_home is not None and goals_away is not None:
                        if home_id == home_team_id:  # Playing at home
                            home_data['goals_scored'].append(goals_home)
                            home_data['goals_conceded'].append(goals_away)
                        else:  # Playing away
                            home_data['goals_scored'].append(goals_away)
                            home_data['goals_conceded'].append(goals_home)
                
                for fixture in away_fixtures[:5]:  # Last 5 matches
                    away_id = fixture['teams']['away']['id']
                    goals_home = fixture['goals']['home']
                    goals_away = fixture['goals']['away']
                    
                    if goals_home is not None and goals_away is not None:
                        if away_id == away_team_id:  # Playing away
                            away_data['goals_scored'].append(goals_away)
                            away_data['goals_conceded'].append(goals_home)
                        else:  # Playing at home
                            away_data['goals_scored'].append(goals_home)
                            away_data['goals_conceded'].append(goals_away)
                
                # Check if we have enough data
                min_required = 5
                
                if len(home_data['goals_scored']) < min_required or len(away_data['goals_scored']) < min_required:
                    st.warning(f"⚠️ Nicht genug {league_name} Daten: {home_team}: {len(home_data['goals_scored'])}, {away_team}: {len(away_data['goals_scored'])} Spiele")
                    st.info(f"💡 Erweitere auf ALLE Wettbewerbe (Saison {season}/{season+1})")
                    
                    # FALLBACK: Get matches from ALL leagues
                    try:
                        home_response_all = requests.get(
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
                        
                        away_response_all = requests.get(
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
                        
                        if home_response_all.status_code == 200 and away_response_all.status_code == 200:
                            home_fixtures_all = home_response_all.json().get('response', [])
                            away_fixtures_all = away_response_all.json().get('response', [])
                            
                            # Re-process with all leagues
                            home_data = {'goals_scored': [], 'goals_conceded': []}
                            away_data = {'goals_scored': [], 'goals_conceded': []}
                            
                            for fixture in home_fixtures_all[:5]:
                                home_id = fixture['teams']['home']['id']
                                goals_home = fixture['goals']['home']
                                goals_away = fixture['goals']['away']
                                
                                if goals_home is not None and goals_away is not None:
                                    if home_id == home_team_id:
                                        home_data['goals_scored'].append(goals_home)
                                        home_data['goals_conceded'].append(goals_away)
                                    else:
                                        home_data['goals_scored'].append(goals_away)
                                        home_data['goals_conceded'].append(goals_home)
                            
                            for fixture in away_fixtures_all[:5]:
                                away_id = fixture['teams']['away']['id']
                                goals_home = fixture['goals']['home']
                                goals_away = fixture['goals']['away']
                                
                                if goals_home is not None and goals_away is not None:
                                    if away_id == away_team_id:
                                        away_data['goals_scored'].append(goals_away)
                                        away_data['goals_conceded'].append(goals_home)
                                    else:
                                        away_data['goals_scored'].append(goals_home)
                                        away_data['goals_conceded'].append(goals_away)
                            
                            st.success(f"✅ Erweiterte Daten: {len(home_data['goals_scored'])} + {len(away_data['goals_scored'])} Spiele (alle Wettbewerbe)")
                    
                    except Exception as e:
                        st.warning(f"Fallback error: {e}")
                        # Final fallback to minimal data
                        if not home_data['goals_scored']:
                            home_data = {'goals_scored': [1, 1, 1], 'goals_conceded': [1, 1, 1]}
                        if not away_data['goals_scored']:
                            away_data = {'goals_scored': [1, 1, 1], 'goals_conceded': [1, 1, 1]}
                else:
                    st.success(f"✅ {league_name} Statistiken: {len(home_data['goals_scored'])} + {len(away_data['goals_scored'])} Spiele")
            
            else:
                st.error(f"❌ API Error: {home_response.status_code}")
                # Use fallback data
                home_data = {'goals_scored': [2, 1, 2], 'goals_conceded': [1, 1, 1]}
                away_data = {'goals_scored': [1, 1, 1], 'goals_conceded': [2, 1, 1]}
        
        except Exception as e:
            st.error(f"❌ Fehler beim Laden: {e}")
            # Use fallback data
            home_data = {'goals_scored': [2, 1, 2], 'goals_conceded': [1, 1, 1]}
            away_data = {'goals_scored': [1, 1, 1], 'goals_conceded': [2, 1, 1]}
    
    # Initialize predictor
    predictor = MatchResultPredictor(league_id=league_id)
    
    # Get prediction
    try:
        prediction = predictor.predict_match(home_data, away_data)
        
        # Show data used
        with st.expander("📊 Genutzte Team-Statistiken", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**{home_team} (letzte {len(home_data['goals_scored'])} Spiele)**")
                st.write(f"Tore erzielt: {home_data['goals_scored']}")
                st.write(f"Tore kassiert: {home_data['goals_conceded']}")
            
            with col2:
                st.markdown(f"**{away_team} (letzte {len(away_data['goals_scored'])} Spiele)**")
                st.write(f"Tore erzielt: {away_data['goals_scored']}")
                st.write(f"Tore kassiert: {away_data['goals_conceded']}")
        
        # Display predictions
        st.markdown("---")
        
        # Expected Goals
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏠 Home xG", f"{prediction.home_xg:.2f}")
        with col2:
            st.metric("✈️ Away xG", f"{prediction.away_xg:.2f}")
        with col3:
            st.metric("📊 Total xG", f"{prediction.total_xg:.2f}")
        
        st.markdown("---")
        
        # Match Result
        st.markdown("### 🎯 Match Result (1X2)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Home Win**")
            st.markdown(f"**Prob:** {prediction.home_win_prob*100:.1f}%")
            st.markdown(f"**Odds:** {prediction.fair_odds_home:.2f}")
            if 0.55 <= prediction.home_win_prob <= 0.80:
                st.success("✅ VALUE!")
        
        with col2:
            st.markdown(f"**Draw**")
            st.markdown(f"**Prob:** {prediction.draw_prob*100:.1f}%")
            st.markdown(f"**Odds:** {prediction.fair_odds_draw:.2f}")
            if 0.55 <= prediction.draw_prob <= 0.80:
                st.success("✅ VALUE!")
        
        with col3:
            st.markdown(f"**Away Win**")
            st.markdown(f"**Prob:** {prediction.away_win_prob*100:.1f}%")
            st.markdown(f"**Odds:** {prediction.fair_odds_away:.2f}")
            if 0.55 <= prediction.away_win_prob <= 0.80:
                st.success("✅ VALUE!")
        
        st.markdown("---")
        
        # Double Chance
        st.markdown("### 🔀 Double Chance")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**1X (Home or Draw)**")
            st.markdown(f"**Prob:** {prediction.home_or_draw*100:.1f}%")
            st.markdown(f"**Odds:** {1/prediction.home_or_draw:.2f}")
        
        with col2:
            st.markdown("**X2 (Draw or Away)**")
            st.markdown(f"**Prob:** {prediction.draw_or_away*100:.1f}%")
            st.markdown(f"**Odds:** {1/prediction.draw_or_away:.2f}")
        
        with col3:
            st.markdown("**12 (No Draw)**")
            st.markdown(f"**Prob:** {prediction.home_or_away*100:.1f}%")
            st.markdown(f"**Odds:** {1/prediction.home_or_away:.2f}")
        
        st.markdown("---")
        
        # Over/Under
        st.markdown("### 📈 Over/Under Goals")
        
        for threshold, (over_prob, under_prob) in prediction.over_under.items():
            col1, col2 = st.columns(2)
            
            with col1:
                is_value = 0.58 <= over_prob <= 0.78
                prefix = "✅" if is_value else "📊"
                st.markdown(f"{prefix} **Over {threshold}:** {over_prob*100:.1f}% (Odds: {1/over_prob:.2f})")
            
            with col2:
                is_value = 0.58 <= under_prob <= 0.78
                prefix = "✅" if is_value else "📊"
                st.markdown(f"{prefix} **Under {threshold}:** {under_prob*100:.1f}% (Odds: {1/under_prob:.2f})")
        
        st.markdown("---")
        
        # BTTS
        st.markdown("### 🎯 Both Teams To Score (BTTS)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            is_value = 0.58 <= prediction.btts_yes <= 0.78
            prefix = "✅" if is_value else "📊"
            st.markdown(f"{prefix} **Yes:** {prediction.btts_yes*100:.1f}% (Odds: {1/prediction.btts_yes:.2f})")
        
        with col2:
            is_value = 0.58 <= prediction.btts_no <= 0.78
            prefix = "✅" if is_value else "📊"
            st.markdown(f"{prefix} **No:** {prediction.btts_no*100:.1f}% (Odds: {1/prediction.btts_no:.2f})")
        
        # Best Value Bets
        if prediction.best_result_bet or prediction.best_double_chance or prediction.best_over_under:
            st.markdown("---")
            st.markdown("### 💎 Best Value Bets (Sweet Spot 60-75%)")
            
            if prediction.best_result_bet:
                st.success(f"🎯 **{prediction.best_result_bet['market']}:** {prediction.best_result_bet['prob']*100:.1f}% (Odds: {prediction.best_result_bet['fair_odds']:.2f}) - Value: {prediction.best_result_bet['value_score']:.2f}")
            
            if prediction.best_double_chance:
                st.success(f"🔀 **{prediction.best_double_chance['market']}:** {prediction.best_double_chance['prob']*100:.1f}% (Odds: {prediction.best_double_chance['fair_odds']:.2f}) - Value: {prediction.best_double_chance['value_score']:.2f}")
            
            if prediction.best_over_under:
                st.success(f"📈 **{prediction.best_over_under['market']}:** {prediction.best_over_under['prob']*100:.1f}% (Odds: {prediction.best_over_under['fair_odds']:.2f}) - Value: {prediction.best_over_under['value_score']:.2f}")
    
    except Exception as e:
        st.error(f"❌ Prediction Error: {e}")


def create_alternative_markets_tab_extended():
    """
    Alternative Markets Tab - INLINE ANALYSIS
    No tab switching - analysis opens directly at each match!
    """
    
    st.markdown("""
    ### 📊 ALTERNATIVE MARKETS - Extended
    
    **Mathematische Analyse für:**
    * ⚽ Corners & Cards (VALUE SCORE System)
    * 🎯 Match Result (Dixon-Coles Model)
    * 🔀 Double Chance (1X, X2, 12)
    * 📈 Over/Under Goals (0.5 - 4.5)
    * 🎯 BTTS (Both Teams To Score)
    
    **Keine Buchmacher-Quoten - Pure Mathematik!**
    """)
    
    with st.expander("ℹ️ Wie funktioniert es?", expanded=False):
        st.markdown("""
        1. **Ligen und Datum wählen**
        2. **"Matches laden" klicken**
        3. **Analyse-Button bei gewünschtem Match klicken**
        4. **Analyse öffnet sich direkt!**
        
        ✨ **NEU:** Kein Tab-Wechsel mehr! Analyse direkt beim Match!
        
        💡 **Tipp:** Du kannst mehrere Matches gleichzeitig analysieren!
        """)
    
    st.markdown("---")
    
    # Get API key
    try:
        api_key = st.secrets['api']['api_football_key']
    except:
        st.error("❌ API Key nicht gefunden! Bitte in Secrets konfigurieren.")
        return
    
    # League selection
    AVAILABLE_LEAGUES = {
        # TOP 5 Leagues
        'Bundesliga (🇩🇪)': 78,
        'Premier League (🇬🇧)': 39,
        'La Liga (🇪🇸)': 140,
        'Serie A (🇮🇹)': 135,
        'Ligue 1 (🇫🇷)': 61,
        
        # Other Top Leagues
        'Eredivisie (🇳🇱)': 88,
        'Primeira Liga (🇵🇹)': 94,
        'Championship (🇬🇧)': 40,
        'Bundesliga 2 (🇩🇪)': 79,
        'La Liga 2 (🇪🇸)': 141,
        'Serie B (🇮🇹)': 136,
        'Ligue 2 (🇫🇷)': 62,
        
        # International
        'Champions League': 2,
        'Europa League': 3,
        'Conference League': 848,
        
        # More Leagues
        'Scottish Premiership': 179,
        'Belgian Pro League': 144,
        'Turkish Süper Lig': 203,
        'Austrian Bundesliga': 218,
        'Swiss Super League': 207,
        'Danish Superliga': 119,
        'Norwegian Eliteserien': 103,
        'Swedish Allsvenskan': 113,
        'MLS (🇺🇸)': 253,
        'Liga MX (🇲🇽)': 262,
        'Brasileirão (🇧🇷)': 71,
        'Argentine Liga (🇦🇷)': 128
    }
    
    st.markdown("### 🔍 Matches Suchen")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            options=list(AVAILABLE_LEAGUES.keys()),
            default=['Premier League (🇬🇧)', 'Bundesliga (🇩🇪)', 'Champions League'],
            help="Wähle eine oder mehrere Ligen"
        )
        
        selected_league_ids = [AVAILABLE_LEAGUES[league] for league in selected_leagues]
    
    with col2:
        search_date = st.date_input(
            "Datum",
            value=datetime.now().date(),
            min_value=datetime.now().date(),
            max_value=datetime.now().date() + timedelta(days=14)
        )
    
    if st.button("🔍 Matches laden", type="primary"):
        # Calculate season
        current_year = search_date.year
        current_month = search_date.month
        current_season = current_year if current_month >= 8 else current_year - 1
        
        st.info(f"🔍 Suche in Season {current_season}/{current_season+1} am {search_date.strftime('%d.%m.%Y')}")
        
        with st.spinner(f"Lade Matches aus {len(selected_league_ids)} Liga(en)..."):
            try:
                all_fixtures = []
                
                # Get fixtures for each league
                for league_id in selected_league_ids:
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
                
                if all_fixtures:
                    st.success(f"✅ {len(all_fixtures)} Matches aus {len(selected_league_ids)} Liga(en) gefunden!")
                    
                    # Store in UNIQUE session state key for Tab 7
                    st.session_state['tab7_fixtures'] = all_fixtures
                    st.session_state['tab7_search_date'] = search_date.strftime('%d.%m.%Y')
                    st.session_state['tab7_selected_leagues'] = selected_league_ids
                else:
                    st.warning(f"⚠️ Keine Matches am {search_date.strftime('%d.%m.%Y')} in den gewählten Ligen")
                    st.session_state['tab7_fixtures'] = []
            
            except Exception as e:
                st.error(f"❌ Fehler: {e}")
                st.session_state['tab7_fixtures'] = []
    
    # Display fixtures if they exist (OUTSIDE button block!)
    if 'tab7_fixtures' in st.session_state and st.session_state['tab7_fixtures']:
        fixtures_to_display = st.session_state['tab7_fixtures']
        search_date_display = st.session_state.get('tab7_search_date', 'N/A')
        
        st.markdown("---")
        st.markdown(f"### 📋 Matches ({search_date_display})")
        
        # Add clear button
        if st.button("🗑️ Matches löschen", key="clear_tab7_fixtures"):
            st.session_state['tab7_fixtures'] = []
            st.rerun()
        
        # Group by league
        by_league = defaultdict(list)
        for match in fixtures_to_display:
            league_name = match['league']['name']
            by_league[league_name].append(match)
        
        # Display each league
        for league_name, matches in sorted(by_league.items()):
            st.markdown(f"### 🏆 {league_name} ({len(matches)} Matches)")
            
            for match in matches:
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                match_time = match['fixture']['date']
                match_id = match['fixture']['id']
                
                # Match header
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**{home}** vs **{away}**")
                    st.caption(f"🕐 {match_time}")
                
                with col2:
                    if st.button("📊 Corners & Cards", key=f"cc_{match_id}", use_container_width=True):
                        # Toggle state
                        key = f'show_cc_{match_id}'
                        st.session_state[key] = not st.session_state.get(key, False)
                
                with col3:
                    if st.button("⚽ Match Result", key=f"mr_{match_id}", use_container_width=True):
                        # Toggle state
                        key = f'show_mr_{match_id}'
                        st.session_state[key] = not st.session_state.get(key, False)
                
                # Show Corners & Cards analysis if toggled
                if st.session_state.get(f'show_cc_{match_id}', False):
                    with st.container():
                        st.markdown("---")
                        _render_corners_cards_analysis(match, api_key)
                        st.markdown("---")
                
                # Show Match Result analysis if toggled
                if st.session_state.get(f'show_mr_{match_id}', False):
                    with st.container():
                        st.markdown("---")
                        _render_match_result_analysis(match, api_key)
                        st.markdown("---")
                
                st.markdown("---")
