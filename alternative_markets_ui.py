"""
ALTERNATIVE MARKETS UI - Streamlit Integration
==============================================
UI for Pre-Match Corners, Cards and "Highest Probability" Scanner
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import time

# Import from alternative_markets
try:
    from alternative_markets import (
        PreMatchAlternativeAnalyzer,
        HighestProbabilityFinder,
        CardPredictor,
        CornerPredictor
    )
except ImportError:
    # Fallback für lokale Entwicklung
    pass


def create_alternative_markets_tab(api_key: str, league_ids: Dict[str, int]):
    """
    Main function to create the Alternative Markets tab in Streamlit
    
    Args:
        api_key: API-Football key
        league_ids: Dict of league codes to IDs
    """
    st.header("📊 ALTERNATIVE MARKETS")
    
    st.markdown("""
    **Mathematische Analyse ohne Buchmacher-Quoten!**
    
    Unsere Algorithmen analysieren:
    - 🟨 **Cards**: Gelbe/Rote Karten Vorhersagen
    - ⚽ **Corners**: Ecken-Vorhersagen  
    - 🎯 **Höchste Wahrscheinlichkeit**: Findet die beste Wette automatisch
    """)
    
    # Tabs für verschiedene Modi
    tab1, tab2, tab3 = st.tabs([
        "🔮 Pre-Match Analyse", 
        "🏆 Höchste Wahrscheinlichkeit",
        "📺 Live Alternative Markets"
    ])
    
    with tab1:
        render_prematch_analysis(api_key, league_ids)
    
    with tab2:
        render_highest_probability(api_key, league_ids)
    
    with tab3:
        render_live_alternatives(api_key, league_ids)


def render_prematch_analysis(api_key: str, league_ids: Dict[str, int]):
    """Render Pre-Match Analysis UI"""
    
    st.subheader("🔮 Pre-Match Corners & Cards Analyse")
    
    st.markdown("""
    Analysiert **kommende Spiele** und berechnet erwartete Corners/Cards 
    basierend auf Team-Statistiken der letzten Spiele.
    """)
    
    # Settings
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_leagues = st.multiselect(
            "Ligen auswählen",
            options=list(league_ids.keys()),
            default=['BL1', 'PL', 'PD'],
            help="Wähle die Ligen für die Analyse"
        )
    
    with col2:
        days_ahead = st.slider(
            "Tage voraus",
            min_value=1,
            max_value=7,
            value=3,
            help="Wie viele Tage in die Zukunft"
        )
    
    with col3:
        market_type = st.selectbox(
            "Markt",
            options=['Corners', 'Cards', 'Beide'],
            help="Welchen Markt analysieren"
        )
    
    min_probability = st.slider(
        "Minimum Wahrscheinlichkeit %",
        min_value=60,
        max_value=90,
        value=70,
        help="Nur Wetten mit mindestens dieser Wahrscheinlichkeit"
    )
    
    if st.button("🔍 Analyse starten", type="primary", key="prematch_analyze"):
        
        if not selected_leagues:
            st.warning("Bitte wähle mindestens eine Liga!")
            return
        
        with st.spinner("Lade Fixtures und analysiere..."):
            
            try:
                # Initialize analyzer
                analyzer = PreMatchAlternativeAnalyzer(api_key)
                
                # Get fixtures from API
                from api_football import APIFootball
                api = APIFootball(api_key)
                
                all_fixtures = []
                
                progress = st.progress(0)
                status = st.empty()
                
                for idx, league_code in enumerate(selected_leagues):
                    status.text(f"Lade {league_code}...")
                    
                    fixtures = api.get_upcoming_fixtures(league_code, days_ahead)
                    
                    for f in fixtures:
                        f['league_id'] = league_ids.get(league_code, 39)
                        f['league_code'] = league_code
                    
                    all_fixtures.extend(fixtures)
                    progress.progress((idx + 1) / len(selected_leagues))
                
                status.text(f"✅ {len(all_fixtures)} Fixtures geladen. Analysiere...")
                
                # Analyze each fixture
                results = []
                
                for idx, fixture in enumerate(all_fixtures):
                    try:
                        if market_type in ['Corners', 'Beide']:
                            corners = analyzer.analyze_prematch_corners(fixture)
                            
                            if corners['best_bet'] and corners['best_bet'].get('probability', 0) >= min_probability:
                                results.append({
                                    'Fixture': corners['fixture'],
                                    'Liga': fixture.get('league_code', ''),
                                    'Datum': fixture.get('date', '')[:10],
                                    'Markt': 'CORNERS',
                                    'Wette': corners['best_bet']['bet'],
                                    'Wahrsch.': f"{corners['best_bet']['probability']}%",
                                    'Erwartet': corners['expected_total'],
                                    'Stärke': corners['best_bet']['strength'],
                                    'Konfidenz': corners['confidence']
                                })
                        
                        if market_type in ['Cards', 'Beide']:
                            cards = analyzer.analyze_prematch_cards(fixture)
                            
                            if cards['best_bet'] and cards['best_bet'].get('probability', 0) >= min_probability:
                                results.append({
                                    'Fixture': cards['fixture'],
                                    'Liga': fixture.get('league_code', ''),
                                    'Datum': fixture.get('date', '')[:10],
                                    'Markt': 'CARDS',
                                    'Wette': cards['best_bet']['bet'],
                                    'Wahrsch.': f"{cards['best_bet']['probability']}%",
                                    'Erwartet': cards['expected_total'],
                                    'Stärke': cards['best_bet']['strength'],
                                    'Konfidenz': cards['confidence'],
                                    'Derby': '🔥' if cards.get('is_derby') else ''
                                })
                        
                        # Rate limit
                        time.sleep(0.3)
                        
                    except Exception as e:
                        continue
                    
                    progress.progress((idx + 1) / len(all_fixtures))
                
                progress.empty()
                status.empty()
                
                # Display results
                if results:
                    st.success(f"✅ {len(results)} Wett-Empfehlungen gefunden!")
                    
                    # Sort by probability
                    df = pd.DataFrame(results)
                    df['Prob_Num'] = df['Wahrsch.'].str.replace('%', '').astype(float)
                    df = df.sort_values('Prob_Num', ascending=False)
                    df = df.drop(columns=['Prob_Num'])
                    
                    # Styling
                    def highlight_strength(val):
                        if val == 'VERY_STRONG':
                            return 'background-color: #28a745; color: white'
                        elif val == 'STRONG':
                            return 'background-color: #17a2b8; color: white'
                        elif val == 'GOOD':
                            return 'background-color: #ffc107; color: black'
                        return ''
                    
                    st.dataframe(
                        df.style.applymap(highlight_strength, subset=['Stärke']),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Summary
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        very_strong = len(df[df['Stärke'] == 'VERY_STRONG'])
                        st.metric("🔥🔥 VERY STRONG", very_strong)
                    
                    with col2:
                        strong = len(df[df['Stärke'] == 'STRONG'])
                        st.metric("🔥 STRONG", strong)
                    
                    with col3:
                        corners_count = len(df[df['Markt'] == 'CORNERS'])
                        cards_count = len(df[df['Markt'] == 'CARDS'])
                        st.metric("📊 Corners / Cards", f"{corners_count} / {cards_count}")
                
                else:
                    st.info(f"Keine Empfehlungen mit ≥{min_probability}% Wahrscheinlichkeit gefunden.")
                
            except Exception as e:
                st.error(f"Fehler: {e}")


def render_highest_probability(api_key: str, league_ids: Dict[str, int]):
    """Render Highest Probability Scanner UI"""
    
    st.subheader("🏆 Höchste Wahrscheinlichkeit Scanner")
    
    st.markdown("""
    **Scannt ALLE Märkte** und findet automatisch die Wette mit der 
    **höchsten mathematischen Wahrscheinlichkeit**.
    
    📊 **Märkte**: BTTS, Goals, Corners, Cards  
    🧮 **Methode**: Reine Statistik - KEINE Buchmacher-Quoten!
    """)
    
    # Settings
    col1, col2 = st.columns(2)
    
    with col1:
        selected_leagues = st.multiselect(
            "Ligen",
            options=list(league_ids.keys()),
            default=['BL1', 'PL', 'PD', 'SA', 'FL1'],
            key="hp_leagues"
        )
    
    with col2:
        min_prob = st.slider(
            "Minimum %",
            min_value=65,
            max_value=90,
            value=75,
            key="hp_min_prob"
        )
    
    if st.button("🚀 Scanner starten", type="primary", key="hp_scan"):
        
        if not selected_leagues:
            st.warning("Bitte wähle mindestens eine Liga!")
            return
        
        with st.spinner("Scanne alle Märkte..."):
            
            try:
                finder = HighestProbabilityFinder(api_key)
                
                from api_football import APIFootball
                api = APIFootball(api_key)
                
                # Get fixtures
                all_fixtures = []
                
                progress = st.progress(0)
                
                for idx, league_code in enumerate(selected_leagues):
                    fixtures = api.get_upcoming_fixtures(league_code, days_ahead=3)
                    
                    for f in fixtures:
                        f['league_id'] = league_ids.get(league_code, 39)
                        f['league_code'] = league_code
                    
                    all_fixtures.extend(fixtures)
                    progress.progress((idx + 1) / len(selected_leagues))
                
                st.info(f"📋 {len(all_fixtures)} Fixtures gefunden. Analysiere...")
                
                # Scan all fixtures
                all_opportunities = finder.scan_all_fixtures(all_fixtures)
                
                # Filter by min probability
                filtered = [o for o in all_opportunities 
                           if o['best_bet']['probability'] >= min_prob]
                
                progress.empty()
                
                if filtered:
                    st.success(f"🎯 {len(filtered)} Top-Gelegenheiten gefunden!")
                    
                    # Display as cards
                    for opp in filtered[:10]:  # Top 10
                        with st.container():
                            best = opp['best_bet']
                            
                            # Emoji based on strength
                            if best['strength'] == 'VERY_STRONG':
                                emoji = "🔥🔥"
                                color = "green"
                            elif best['strength'] == 'STRONG':
                                emoji = "🔥"
                                color = "blue"
                            else:
                                emoji = "✅"
                                color = "orange"
                            
                            st.markdown(f"""
                            <div style="
                                border: 2px solid {color}; 
                                border-radius: 10px; 
                                padding: 15px; 
                                margin: 10px 0;
                                background-color: rgba(0,0,0,0.05);
                            ">
                                <h4>{emoji} {opp['fixture']}</h4>
                                <p><b>Liga:</b> {opp['league']} | <b>Datum:</b> {opp.get('date', '')[:10]}</p>
                                <p style="font-size: 1.2em;">
                                    <b>BESTE WETTE:</b> {best['bet']} 
                                    <span style="color: {color}; font-weight: bold;">
                                        ({best['probability']}%)
                                    </span>
                                </p>
                                <p><b>Markt:</b> {best['market']} | <b>Edge:</b> +{best['edge']}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Export
                    st.markdown("---")
                    
                    export_data = []
                    for opp in filtered:
                        export_data.append({
                            'Fixture': opp['fixture'],
                            'Liga': opp['league'],
                            'Datum': opp.get('date', '')[:10],
                            'Beste Wette': opp['best_bet']['bet'],
                            'Wahrscheinlichkeit': f"{opp['best_bet']['probability']}%",
                            'Markt': opp['best_bet']['market'],
                            'Stärke': opp['best_bet']['strength']
                        })
                    
                    df = pd.DataFrame(export_data)
                    
                    st.download_button(
                        "📥 Als CSV exportieren",
                        df.to_csv(index=False),
                        "highest_probability_bets.csv",
                        "text/csv"
                    )
                
                else:
                    st.info(f"Keine Wetten mit ≥{min_prob}% gefunden.")
                
            except Exception as e:
                st.error(f"Fehler: {e}")


def render_live_alternatives(api_key: str, league_ids: Dict[str, int]):
    """Render Live Alternative Markets UI (existing functionality)"""
    
    st.subheader("📺 Live Alternative Markets")
    
    st.markdown("""
    Analysiert **laufende Spiele** für Corners, Cards und andere Märkte.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        min_prob_live = st.slider(
            "Min Wahrscheinlichkeit %",
            60, 95, 75,
            key="live_alt_min_prob"
        )
    
    with col2:
        markets = st.multiselect(
            "Märkte",
            ['Cards', 'Corners', 'Shots'],
            default=['Cards', 'Corners'],
            key="live_alt_markets"
        )
    
    if st.button("🔄 Live Spiele laden", key="live_alt_scan"):
        
        with st.spinner("Lade Live-Spiele..."):
            
            try:
                from api_football import APIFootball
                api = APIFootball(api_key)
                
                # Get live matches
                live_matches = api.get_live_matches()
                
                # Filter for our leagues
                league_id_set = set(league_ids.values())
                our_matches = [m for m in live_matches 
                              if m.get('league', {}).get('id') in league_id_set]
                
                if not our_matches:
                    st.info("⚽ Keine Live-Spiele in unseren Ligen gerade.")
                    return
                
                st.success(f"✅ {len(our_matches)} Live-Spiele gefunden!")
                
                # Initialize predictors
                card_predictor = CardPredictor()
                corner_predictor = CornerPredictor()
                
                # Analyze each match
                for match in our_matches:
                    fixture = match.get('fixture', {})
                    teams = match.get('teams', {})
                    goals = match.get('goals', {})
                    
                    home_team = teams.get('home', {}).get('name', 'Home')
                    away_team = teams.get('away', {}).get('name', 'Away')
                    home_score = goals.get('home', 0) or 0
                    away_score = goals.get('away', 0) or 0
                    minute = fixture.get('status', {}).get('elapsed', 0) or 0
                    
                    # Get statistics
                    stats = api.get_match_statistics(fixture.get('id'))
                    
                    match_data = {
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': home_score,
                        'away_score': away_score,
                        'league_id': match.get('league', {}).get('id', 39),
                        'stats': stats or {},
                        'phase_data': {'phase': 'NORMAL'}
                    }
                    
                    with st.expander(f"⚽ {home_team} {home_score}-{away_score} {away_team} ({minute}')"):
                        
                        if 'Cards' in markets:
                            cards = card_predictor.predict_cards(match_data, minute)
                            
                            st.markdown(f"**🟨 Cards:** {cards['recommendation']}")
                            st.caption(f"Aktuell: {cards['current_cards']} | Erwartet: {cards['expected_total']}")
                        
                        if 'Corners' in markets:
                            corners = corner_predictor.predict_corners(match_data, minute)
                            
                            st.markdown(f"**⚽ Corners:** {corners['recommendation']}")
                            st.caption(f"Aktuell: {corners['current_corners']} | Erwartet: {corners['expected_total']}")
                
            except Exception as e:
                st.error(f"Fehler: {e}")


# Standalone test
if __name__ == "__main__":
    st.set_page_config(page_title="Alternative Markets Test", layout="wide")
    
    st.title("Alternative Markets - Test UI")
    
    api_key = st.text_input("API Key", type="password")
    
    if api_key:
        league_ids = {
            'BL1': 78, 'PL': 39, 'PD': 140, 'SA': 135, 'FL1': 61,
            'DED': 88, 'PPL': 94, 'TSL': 203
        }
        
        create_alternative_markets_tab(api_key, league_ids)
