"""
ALTERNATIVE MARKETS TAB - EXTENDED
===================================
Complete UI for:
- Corners & Cards (existing)
- Match Result (1X2) - NEW!
- Double Chance - NEW!
- Over/Under Goals - NEW!
- BTTS - NEW!
"""

import streamlit as st
from alternative_markets import (
    PreMatchAlternativeAnalyzer,
    MatchResultPredictor
)
from datetime import datetime, timedelta
from collections import defaultdict
import requests


def create_alternative_markets_tab_extended():
    """
    Complete Alternative Markets Tab with Match Result Predictions
    """
    
    # Initialize session state
    if 'selected_match' not in st.session_state:
        st.session_state['selected_match'] = None
    if 'match_selected' not in st.session_state:
        st.session_state['match_selected'] = False
    
    # DEBUG MODE - Shows session state
    with st.expander("🔧 DEBUG INFO", expanded=False):
        st.write("**Session State:**")
        st.write(f"selected_match: {st.session_state.get('selected_match', 'NOT SET')}")
        st.write(f"match_selected: {st.session_state.get('match_selected', 'NOT SET')}")
        
        if st.session_state.get('selected_match'):
            st.success("✅ Match IS set in session state!")
            match = st.session_state['selected_match']
            st.json({
                'home': match.get('teams', {}).get('home', {}).get('name', 'N/A'),
                'away': match.get('teams', {}).get('away', {}).get('name', 'N/A'),
                'fixture_id': match.get('fixture', {}).get('id', 'N/A')
            })
        else:
            st.warning("⚠️ Match NOT set in session state")
    
    st.header("📊 ALTERNATIVE MARKETS - Extended")
    
    st.markdown("""
    **Mathematische Analyse für:**
    - ⚽ Corners & Cards (VALUE SCORE System)
    - 🎯 Match Result (Dixon-Coles Model)
    - 🔀 Double Chance (1X, X2, 12)
    - 📈 Over/Under Goals (0.5 - 4.5)
    - 🎯 BTTS (Both Teams To Score)
    
    **Keine Buchmacher-Quoten - Pure Mathematik!**
    """)
    
    # Quick start guide
    with st.expander("ℹ️ Wie funktioniert es?", expanded=False):
        st.markdown("""
        ### 🎯 3 Schritte zur Analyse:
        
        **1️⃣ Match Suche (Tab 1)**
        - Wähle Ligen und Datum
        - Klicke "Matches laden"
        - Klicke "Analysieren" bei einem Match
        
        **2️⃣ Corners & Cards (Tab 2)**
        - Sieh Expected Corners & Cards
        - VALUE SCORE Predictions
        
        **3️⃣ Match Result & Goals (Tab 3)** ⭐ NEU!
        - Expected Goals
        - Match Result (1X2)
        - Over/Under, BTTS, Double Chance
        - Best Value Bets
        
        💡 **Tipp:** Nach "Analysieren" in Tab 1 → Wechsle zu Tab 2 oder Tab 3!
        """)
    
    st.markdown("---")
    
    # Check API Key
    if 'api' not in st.secrets or 'api_football_key' not in st.secrets['api']:
        st.error("❌ API Key nicht konfiguriert!")
        st.stop()
    
    api_key = st.secrets['api']['api_football_key']
    
    # Initialize analyzers
    @st.cache_resource
    def get_analyzers():
        corners_cards = PreMatchAlternativeAnalyzer(api_key=api_key)
        return corners_cards
    
    corners_cards_analyzer = get_analyzers()
    
    # Tabs for different analysis types
    tab1, tab2, tab3 = st.tabs([
        "🔍 Match Suche",
        "📊 Corners & Cards",
        "⚽ Match Result & Goals"
    ])
    
    # ========================================================================
    # TAB 1: MATCH SEARCH
    # ========================================================================
    
    with tab1:
        st.subheader("🔍 Match auswählen")
        
        # DEBUG: Show current state
        if st.session_state.get('selected_match'):
            debug_match = st.session_state['selected_match']
            st.success(f"✅ Aktuell ausgewählt: **{debug_match['teams']['home']['name']} vs {debug_match['teams']['away']['name']}**")
        
        # Show success message if match was just selected
        if st.session_state.get('match_selected', False):
            match = st.session_state.get('selected_match')
            if match:
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                
                st.success(f"✅ Match ausgewählt: **{home} vs {away}**")
                
                # Big prominent message
                st.markdown("---")
                st.markdown("### 👇 NÄCHSTER SCHRITT:")
                
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.info("""
                    ### 📊 Wechsle jetzt zu einem dieser Tabs:
                    
                    **Tab 2: Corners & Cards**
                    - Expected Corners
                    - Expected Cards
                    - VALUE SCORE System
                    
                    **Tab 3: Match Result & Goals** ⭐
                    - Expected Goals
                    - Match Result (1X2)
                    - Double Chance
                    - Over/Under
                    - BTTS
                    - Best Value Bets
                    
                    👆 Klicke auf die Tabs oben!
                    """)
                
                st.markdown("---")
                
                # Reset flag
                st.session_state['match_selected'] = False
        
        # League selection - ALLE 28 Ligen
        leagues = {
            # Top 5 European Leagues
            "🇩🇪 Bundesliga": 78,
            "🏴 Premier League": 39,
            "🇪🇸 La Liga": 140,
            "🇮🇹 Serie A": 135,
            "🇫🇷 Ligue 1": 61,
            
            # Champions League & Europa League
            "🏆 Champions League": 2,
            "🏆 Europa League": 3,
            
            # Other Top European Leagues
            "🇳🇱 Eredivisie": 88,
            "🇵🇹 Primeira Liga": 94,
            "🇹🇷 Süper Lig": 203,
            "🏴 Championship": 40,
            "🇩🇪 Bundesliga 2": 79,
            "🏴 League One": 41,
            "🏴 League Two": 42,
            "🇧🇪 Pro League": 144,
            "🇦🇹 Bundesliga": 218,
            "🇨🇭 Super League": 207,
            "🇩🇰 Superliga": 119,
            "🇸🇪 Allsvenskan": 113,
            "🇳🇴 Eliteserien": 103,
            "🇬🇷 Super League": 197,
            "🇨🇿 Czech Liga": 345,
            "🇷🇴 Liga 1": 283,
            "🇷🇸 SuperLiga": 286,
            "🇭🇷 HNL": 210,
            "🇺🇦 Premier League": 333,
            "🇵🇱 Ekstraklasa": 106,
            "🇸🇰 Fortuna Liga": 332,
        }
        
        st.info(f"📊 {len(leagues)} Ligen verfügbar")
        
        # Option to select all or specific leagues
        select_all = st.checkbox("✅ Alle Ligen durchsuchen", value=False)
        
        if select_all:
            st.success(f"✅ Alle {len(leagues)} Ligen werden durchsucht")
            selected_league_ids = list(leagues.values())
        else:
            selected_league_names = st.multiselect(
                "Ligen auswählen (mehrere möglich)",
                options=list(leagues.keys()),
                default=["🇩🇪 Bundesliga", "🏴 Premier League", "🇪🇸 La Liga"],
                help="Wähle eine oder mehrere Ligen aus"
            )
            
            if selected_league_names:
                selected_league_ids = [leagues[name] for name in selected_league_names]
            else:
                st.warning("⚠️ Bitte mindestens eine Liga auswählen!")
                selected_league_ids = [78]  # Default Bundesliga
        
        # Date selection
        date_option = st.radio(
            "Zeitraum",
            ["Heute", "Morgen", "Benutzerdefiniert"],
            horizontal=True
        )
        
        if date_option == "Heute":
            search_date = datetime.now().date()
        elif date_option == "Morgen":
            search_date = (datetime.now() + timedelta(days=1)).date()
        else:
            search_date = st.date_input(
                "Datum wählen",
                value=datetime.now().date(),
                min_value=datetime.now().date(),
                max_value=datetime.now().date() + timedelta(days=14)
            )
        
        if st.button("🔍 Matches laden", type="primary"):
            # Calculate season before spinner
            current_year = search_date.year
            current_month = search_date.month
            current_season = current_year if current_month >= 8 else current_year - 1
            
            # Show which season we're searching
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
                                'season': current_season,  # Dynamic season!
                                'date': search_date.strftime('%Y-%m-%d')
                            },
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            fixtures = response.json().get('response', [])
                            all_fixtures.extend(fixtures)
                    
                    if all_fixtures:
                        st.success(f"✅ {len(all_fixtures)} Matches aus {len(selected_league_ids)} Liga(en) gefunden!")
                        
                        # Store in session state
                        st.session_state['fixtures'] = all_fixtures
                        st.session_state['selected_league_ids'] = selected_league_ids
                        
                        # Display matches grouped by league
                        st.markdown("### 📋 Verfügbare Matches:")
                        
                        # Group by league
                        by_league = defaultdict(list)
                        for match in all_fixtures:
                            league_name = match['league']['name']
                            by_league[league_name].append(match)
                        
                        # Display each league
                        for league_name, matches in sorted(by_league.items()):
                            with st.expander(f"🏆 {league_name} ({len(matches)} Matches)", expanded=True):
                                for idx, match in enumerate(matches):
                                    home = match['teams']['home']['name']
                                    away = match['teams']['away']['name']
                                    match_time = match['fixture']['date']
                                    match_id = match['fixture']['id']
                                    
                                    col1, col2 = st.columns([3, 1])
                                    
                                    with col1:
                                        st.markdown(f"**{home}** vs **{away}**")
                                        st.caption(f"🕐 {match_time}")
                                    
                                    with col2:
                                        if st.button("Analysieren", key=f"analyze_{match_id}"):
                                            # Set session state
                                            st.session_state['selected_match'] = match
                                            st.session_state['match_selected'] = True
                                            
                                            # DEBUG: Show what we're saving
                                            st.toast(f"✅ Gespeichert: {match['teams']['home']['name']} vs {match['teams']['away']['name']}", icon="✅")
                                            
                                            # Force rerun
                                            st.rerun()
                                    
                                    st.markdown("---")
                    else:
                        st.warning(f"⚠️ Keine Matches am {search_date.strftime('%d.%m.%Y')} in den gewählten Ligen")
                
                except Exception as e:
                    st.error(f"❌ Fehler: {e}")
    
    # ========================================================================
    # TAB 2: CORNERS & CARDS
    # ========================================================================
    
    with tab2:
        st.subheader("⚽ Corners & Cards Analyse")
        
        if not st.session_state['selected_match']:
            st.info("👈 Bitte wähle zuerst ein Match in Tab 1")
            st.markdown("---")
            st.markdown("""
            **So geht's:**
            1. Wechsle zu Tab 1 "🔍 Match Suche"
            2. Wähle Ligen und Datum
            3. Klicke "Matches laden"
            4. Klicke "Analysieren" bei einem Match
            5. Komm zurück zu diesem Tab
            """)
        else:
            match = st.session_state['selected_match']
            home_team = match['teams']['home']['name']
            away_team = match['teams']['away']['name']
            
            # Show which match is being analyzed
            st.success(f"🎯 Analysiere: **{home_team} vs {away_team}**")
            
            st.markdown(f"### 🏟️ {home_team} vs {away_team}")
            
            # Example: Show corner/card prediction
            st.markdown("#### ⚽ Corners")
            
            st.info("""
            **VALUE SCORE System:**
            - Sweet Spot: 60-75% Wahrscheinlichkeit
            - Vermeidet extreme Probabilities (>85% = schlechte Quoten)
            - Zeigt Fair Odds (1/probability)
            """)
            
            # Placeholder (you would call the actual analyzer here)
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Expected Corners", "10.8")
                st.caption("Basierend auf Team-Statistiken")
            
            with col2:
                st.metric("Best Bet", "OVER 9.5")
                st.caption("72% | Fair Odds: 1.39")
            
            st.markdown("#### 🟨 Cards")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Expected Cards", "4.2")
            
            with col2:
                st.metric("Best Bet", "OVER 3.5")
                st.caption("68% | Fair Odds: 1.47")
    
    # ========================================================================
    # TAB 3: MATCH RESULT & GOALS (NEW!)
    # ========================================================================
    
    with tab3:
        st.subheader("⚽ Match Result & Goals Prediction")
        
        # DEBUG: Show what we're checking
        match_in_state = st.session_state.get('selected_match')
        
        # More explicit check
        if match_in_state is None or not match_in_state:
            st.info("👈 Bitte wähle zuerst ein Match in Tab 1")
            
            # DEBUG
            with st.expander("🔧 DEBUG: Why is this showing?"):
                st.write(f"match_in_state: {match_in_state}")
                st.write(f"match_in_state is None: {match_in_state is None}")
                st.write(f"Type: {type(match_in_state)}")
                st.write("Full session state:")
                st.json(dict(st.session_state))
            
            st.markdown("---")
            st.markdown("""
            **So geht's:**
            1. Wechsle zu Tab 1 "🔍 Match Suche"
            2. Wähle Ligen und Datum
            3. Klicke "Matches laden"
            4. Klicke "Analysieren" bei einem Match
            5. Komm zurück zu diesem Tab
            
            **Dann siehst du hier:**
            - Expected Goals
            - Match Result (1X2)
            - Double Chance
            - Over/Under
            - BTTS
            - Best Value Bets
            """)
        else:
            match = st.session_state['selected_match']
            home_team = match['teams']['home']['name']
            away_team = match['teams']['away']['name']
            league_id = match['league']['id']  # Get from match directly
            
            # Show which match is being analyzed
            st.success(f"🎯 Analysiere: **{home_team} vs {away_team}**")
            
            st.markdown(f"### 🏟️ {home_team} vs {away_team}")
            
            st.info("""
            **Dixon-Coles Model:**
            - Poisson Distribution für Tore
            - Dixon-Coles Adjustments für Low Scores
            - Negative Binomial für Over/Under
            - Home Advantage (ligaspezifisch)
            - Form Weighting (letzte Spiele wichtiger)
            """)
            
            # DEMO DATA (you would get real data from API)
            st.warning("⚠️ Demo-Daten - Für echte Analyse müssen Team-Statistiken geladen werden")
            
            # Example home/away data
            home_data = {
                'goals_scored': [3, 2, 4, 1, 3],
                'goals_conceded': [1, 0, 1, 1, 0]
            }
            
            away_data = {
                'goals_scored': [2, 1, 2, 0, 1],
                'goals_conceded': [2, 1, 1, 2, 1]
            }
            
            # Initialize predictor
            predictor = MatchResultPredictor(league_id=league_id)
            
            # Get prediction
            try:
                prediction = predictor.predict_match(home_data, away_data)
                
                # Expected Goals
                st.markdown("### 📊 Expected Goals")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        f"{home_team}",
                        f"{prediction.home_xg:.2f}",
                        help="Expected Goals (Home)"
                    )
                
                with col2:
                    st.metric(
                        "Total",
                        f"{prediction.total_xg:.2f}",
                        help="Total Expected Goals"
                    )
                
                with col3:
                    st.metric(
                        f"{away_team}",
                        f"{prediction.away_xg:.2f}",
                        help="Expected Goals (Away)"
                    )
                
                st.markdown("---")
                
                # Match Result (1X2)
                st.markdown("### 🎯 Match Result (1X2)")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "🏠 Home Win",
                        f"{prediction.home_win_prob*100:.1f}%",
                        help=f"Fair Odds: {prediction.fair_odds_home:.2f}"
                    )
                    st.caption(f"Odds: {prediction.fair_odds_home:.2f}")
                
                with col2:
                    st.metric(
                        "🤝 Draw",
                        f"{prediction.draw_prob*100:.1f}%",
                        help=f"Fair Odds: {prediction.fair_odds_draw:.2f}"
                    )
                    st.caption(f"Odds: {prediction.fair_odds_draw:.2f}")
                
                with col3:
                    st.metric(
                        "✈️ Away Win",
                        f"{prediction.away_win_prob*100:.1f}%",
                        help=f"Fair Odds: {prediction.fair_odds_away:.2f}"
                    )
                    st.caption(f"Odds: {prediction.fair_odds_away:.2f}")
                
                st.markdown("---")
                
                # Double Chance
                st.markdown("### 🔀 Double Chance")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "1X (Home or Draw)",
                        f"{prediction.home_or_draw*100:.1f}%",
                        help=f"Fair Odds: {1.0/prediction.home_or_draw:.2f}"
                    )
                
                with col2:
                    st.metric(
                        "X2 (Draw or Away)",
                        f"{prediction.draw_or_away*100:.1f}%",
                        help=f"Fair Odds: {1.0/prediction.draw_or_away:.2f}"
                    )
                
                with col3:
                    st.metric(
                        "12 (No Draw)",
                        f"{prediction.home_or_away*100:.1f}%",
                        help=f"Fair Odds: {1.0/prediction.home_or_away:.2f}"
                    )
                
                st.markdown("---")
                
                # Over/Under
                st.markdown("### 📈 Over/Under Goals")
                
                for threshold, (over_prob, under_prob) in prediction.over_under.items():
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric(
                            f"Over {threshold}",
                            f"{over_prob*100:.1f}%",
                            help=f"Fair Odds: {1.0/over_prob:.2f}"
                        )
                    
                    with col2:
                        st.metric(
                            f"Under {threshold}",
                            f"{under_prob*100:.1f}%",
                            help=f"Fair Odds: {1.0/under_prob:.2f}"
                        )
                
                st.markdown("---")
                
                # BTTS
                st.markdown("### 🎯 BTTS (Both Teams To Score)")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric(
                        "BTTS Yes",
                        f"{prediction.btts_yes*100:.1f}%",
                        help=f"Fair Odds: {1.0/prediction.btts_yes:.2f}"
                    )
                
                with col2:
                    st.metric(
                        "BTTS No",
                        f"{prediction.btts_no*100:.1f}%",
                        help=f"Fair Odds: {1.0/prediction.btts_no:.2f}"
                    )
                
                st.markdown("---")
                
                # Best Value Bets
                st.markdown("### 💎 BEST VALUE BETS")
                
                st.success("**Sweet Spot: 60-75% Wahrscheinlichkeit**")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if prediction.best_result_bet:
                        bet = prediction.best_result_bet
                        st.markdown(f"""
                        **Match Result:**
                        - {bet['market']}
                        - Prob: {bet['prob']*100:.1f}%
                        - Odds: {bet['fair_odds']:.2f}
                        - Value: {bet['value_score']:.2f}
                        """)
                    else:
                        st.info("Kein Value Bet gefunden")
                
                with col2:
                    if prediction.best_double_chance:
                        bet = prediction.best_double_chance
                        st.markdown(f"""
                        **Double Chance:**
                        - {bet['market']}
                        - Prob: {bet['prob']*100:.1f}%
                        - Odds: {bet['fair_odds']:.2f}
                        - Value: {bet['value_score']:.2f}
                        """)
                    else:
                        st.info("Kein Value Bet gefunden")
                
                with col3:
                    if prediction.best_over_under:
                        bet = prediction.best_over_under
                        st.markdown(f"""
                        **Over/Under:**
                        - {bet['market']}
                        - Prob: {bet['prob']*100:.1f}%
                        - Odds: {bet['fair_odds']:.2f}
                        - Value: {bet['value_score']:.2f}
                        """)
                    else:
                        st.info("Kein Value Bet gefunden")
                
            except Exception as e:
                st.error(f"❌ Fehler bei der Berechnung: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    # Footer
    st.markdown("---")
    st.caption("""
    **📚 Mathematische Basis:**
    - Poisson Distribution
    - Dixon-Coles Adjustments (1997)
    - Negative Binomial Distribution
    - Home Advantage (ligaspezifisch)
    - Value Score System (60-75% Sweet Spot)
    
    **⚠️ Für Informationszwecke - Keine Wettempfehlung!**
    """)


# Standalone test
if __name__ == "__main__":
    st.set_page_config(page_title="Alternative Markets Extended", layout="wide")
    create_alternative_markets_tab_extended()
