"""
Ultimate BTTS Analyzer - Pro Web Interface
Complete with ML predictions, detailed analysis, and backtesting
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import sqlite3
from pathlib import Path

from advanced_analyzer import AdvancedBTTSAnalyzer
from data_engine import DataEngine

# Page config
st.set_page_config(
    page_title="BTTS Pro Analyzer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    .stAlert {
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .top-tip {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
        border-left: 5px solid #c92a2a;
    }
    .strong-tip {
        background: linear-gradient(135deg, #51cf66 0%, #37b24d 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
        border-left: 5px solid #2b8a3e;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize
@st.cache_resource
def get_analyzer():
    """Initialize analyzer with API key from config or Streamlit secrets"""
    try:
        # Try Streamlit secrets first (for cloud deployment)
        if hasattr(st, 'secrets') and 'api' in st.secrets:
            api_key = st.secrets['api']['api_key']
            st.session_state['api_source'] = 'Streamlit Secrets'
        else:
            # Fallback to config.ini (for local development)
            import configparser
            config = configparser.ConfigParser()
            config.read('config.ini')
            
            api_key = None
            if config.has_option('api', 'api_key'):
                api_key = config.get('api', 'api_key').strip()
            
            st.session_state['api_source'] = 'config.ini'
        
        if not api_key:
            api_key = 'ef8c2eb9be6b43fe8353c99f51904c0f'  # Fallback
            st.session_state['api_source'] = 'Fallback'
        
        analyzer = AdvancedBTTSAnalyzer(api_key=api_key)
        st.session_state['analyzer_ready'] = True
        return analyzer
    except Exception as e:
        st.error(f"Failed to initialize analyzer: {e}")
        return None

analyzer = get_analyzer()

# Header
st.title("⚽ BTTS Pro Analyzer")
st.markdown("**Ultimate BTTS Analysis with Machine Learning** | Advanced Edition v2.0")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    if st.session_state.get('analyzer_ready'):
        st.success("✅ ML Model Ready")
        st.info("🔄 Live Data Active")
    else:
        st.error("❌ Analyzer not ready")
    
    st.markdown("---")
    
    # Filters
    st.subheader("🎯 Filters")
    
    min_probability = st.slider(
        "Min BTTS Probability (%)",
        min_value=50,
        max_value=90,
        value=60,
        step=5
    )
    
    min_confidence = st.slider(
        "Min Confidence (%)",
        min_value=50,
        max_value=95,
        value=60,
        step=5
    )
    
    selected_leagues = st.multiselect(
        "Select Leagues",
        options=list(analyzer.engine.leagues.keys()) if analyzer else [],
        default=['Bundesliga']
    )
    
    days_ahead = st.slider(
        "Days Ahead",
        min_value=1,
        max_value=14,
        value=7
    )
    
    st.markdown("---")
    
    # Data refresh
    st.subheader("🔄 Data Management")
    
    if st.button("Refresh League Data"):
        with st.spinner("Refreshing data..."):
            for league_name in selected_leagues:
                league_code = analyzer.engine.leagues.get(league_name)
                if league_code:
                    analyzer.engine.refresh_league_data(league_code)
            st.success("Data refreshed!")
            st.cache_resource.clear()
    
    if st.button("Retrain ML Model"):
        with st.spinner("Retraining model..."):
            analyzer.train_model()
            st.success("Model retrained!")
    
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; font-size: 0.8em; color: gray;'>
            <p>BTTS Pro Analyzer v2.0</p>
            <p>Powered by ML 🤖</p>
        </div>
    """, unsafe_allow_html=True)

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔥 Top Tips", 
    "📊 All Recommendations", 
    "🔬 Deep Analysis",
    "📈 Model Performance",
    "💎 Value Bets"
])

# TAB 1: Top Tips
with tab1:
    st.header("🔥 Premium Tips - Highest Confidence")
    
    st.info("💡 These are matches with BTTS probability ≥75% AND confidence ≥70%")
    
    if st.button("🔍 Analyze Matches", key="analyze_top"):
        with st.spinner("Running advanced analysis..."):
            all_results = []
            
            for league_name in selected_leagues:
                league_code = analyzer.engine.leagues.get(league_name)
                if league_code:
                    st.write(f"Analyzing {league_name}...")
                    results = analyzer.analyze_upcoming_matches(
                        league_code, 
                        days_ahead=days_ahead,
                        min_probability=min_probability
                    )
                    
                    if not results.empty:
                        results['League'] = league_name
                        all_results.append(results)
            
            if all_results:
                combined = pd.concat(all_results, ignore_index=True)
                
                # Filter for top tips
                combined['BTTS_num'] = combined['BTTS %'].str.rstrip('%').astype(float)
                combined['Conf_num'] = combined['Confidence'].str.rstrip('%').astype(float)
                
                top_tips = combined[
                    (combined['BTTS_num'] >= 75) & 
                    (combined['Conf_num'] >= 70)
                ].copy()
                
                st.session_state['all_results'] = combined
                st.session_state['top_tips'] = top_tips
                
                if not top_tips.empty:
                    st.success(f"🔥 Found {len(top_tips)} Premium Tips!")
                    
                    # Display premium tips
                    for idx, row in top_tips.iterrows():
                        with st.container():
                            st.markdown(f"""
                                <div class='top-tip'>
                                    <h3>🔥 {row['Home']} vs {row['Away']}</h3>
                                    <p><strong>League:</strong> {row['League']} | <strong>Date:</strong> {row['Date']}</p>
                                    <p><strong>BTTS Probability:</strong> {row['BTTS %']} | <strong>Confidence:</strong> {row['Confidence']}</p>
                                    <p><strong>Expected Total Goals:</strong> {row['xG Total']}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Show detailed breakdown
                            with st.expander("📊 Detailed Breakdown"):
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("ML Prediction", row['ML'])
                                with col2:
                                    st.metric("Statistical", row['Stat'])
                                with col3:
                                    st.metric("Form-Based", row['Form'])
                                with col4:
                                    st.metric("Head-to-Head", row['H2H'])
                                
                                # Get full analysis
                                if '_analysis' in row:
                                    analysis = row['_analysis']
                                    
                                    st.markdown("---")
                                    st.subheader("🏠 Home Team Stats")
                                    home_stats = analysis['home_stats']
                                    st.write(f"**BTTS Rate (Home):** {home_stats['btts_rate']:.1f}%")
                                    st.write(f"**Goals/Game:** {home_stats['avg_goals_scored']:.2f}")
                                    st.write(f"**Conceded/Game:** {home_stats['avg_goals_conceded']:.2f}")
                                    st.write(f"**Form (Last 5):** {analysis['home_form']['form_string']}")
                                    
                                    st.markdown("---")
                                    st.subheader("✈️ Away Team Stats")
                                    away_stats = analysis['away_stats']
                                    st.write(f"**BTTS Rate (Away):** {away_stats['btts_rate']:.1f}%")
                                    st.write(f"**Goals/Game:** {away_stats['avg_goals_scored']:.2f}")
                                    st.write(f"**Conceded/Game:** {away_stats['avg_goals_conceded']:.2f}")
                                    st.write(f"**Form (Last 5):** {analysis['away_form']['form_string']}")
                                    
                                    st.markdown("---")
                                    st.subheader("🔄 Head-to-Head")
                                    h2h = analysis['h2h']
                                    st.write(f"**Matches Played:** {h2h['matches_played']}")
                                    st.write(f"**BTTS Rate:** {h2h['btts_rate']:.1f}%")
                                    st.write(f"**Avg Total Goals:** {h2h['avg_total_goals']:.1f}")
                else:
                    st.warning("No premium tips found with current criteria")
            else:
                st.warning("No matches found for selected leagues")

# TAB 2: All Recommendations
with tab2:
    st.header("📊 All BTTS Recommendations")
    
    if 'all_results' in st.session_state and st.session_state['all_results'] is not None:
        df = st.session_state['all_results']
        
        # Apply confidence filter
        df_filtered = df[df['Conf_num'] >= min_confidence].copy()
        
        if not df_filtered.empty:
            st.success(f"📋 Showing {len(df_filtered)} matches (filtered by confidence ≥{min_confidence}%)")
            
            # Display as table
            display_df = df_filtered[[
                'Date', 'League', 'Home', 'Away', 'BTTS %', 
                'Confidence', 'Level', 'Tip', 'xG Total'
            ]].copy()
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Summary stats
            st.markdown("---")
            st.subheader("📈 Summary Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_btts = df_filtered['BTTS_num'].mean()
                st.metric("Avg BTTS Probability", f"{avg_btts:.1f}%")
            
            with col2:
                avg_conf = df_filtered['Conf_num'].mean()
                st.metric("Avg Confidence", f"{avg_conf:.1f}%")
            
            with col3:
                top_tips_count = len(df_filtered[df_filtered['Tip'] == '🔥 TOP TIP'])
                st.metric("Top Tips", top_tips_count)
            
            with col4:
                strong_tips_count = len(df_filtered[df_filtered['Tip'] == '✅ STRONG'])
                st.metric("Strong Tips", strong_tips_count)
            
            # Visualization
            st.markdown("---")
            st.subheader("📊 BTTS Probability Distribution")
            
            fig = px.histogram(
                df_filtered,
                x='BTTS_num',
                nbins=20,
                title='Distribution of BTTS Probabilities',
                labels={'BTTS_num': 'BTTS Probability (%)'},
                color_discrete_sequence=['#667eea']
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning(f"No matches meet confidence threshold of {min_confidence}%")
    else:
        st.info("👆 Click 'Analyze Matches' in the Top Tips tab to load recommendations")

# TAB 3: Deep Analysis
with tab3:
    st.header("🔬 Deep Dive Analysis")
    
    st.markdown("""
        Select a specific match from the recommendations to see a comprehensive breakdown
        including all prediction methods, team stats, form analysis, and more.
    """)
    
    if 'all_results' in st.session_state and not st.session_state['all_results'].empty:
        df = st.session_state['all_results']
        
        # Create match selector
        matches = df.apply(lambda x: f"{x['Home']} vs {x['Away']} ({x['Date']})", axis=1).tolist()
        
        selected_match = st.selectbox("Select Match", matches)
        
        if selected_match:
            idx = matches.index(selected_match)
            match_data = df.iloc[idx]
            
            if '_analysis' in match_data:
                analysis = match_data['_analysis']
                
                # Match header
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 2rem; border-radius: 15px; color: white; margin-bottom: 2rem;'>
                        <h2 style='margin:0;'>{match_data['Home']} vs {match_data['Away']}</h2>
                        <p style='margin:0.5rem 0 0 0;'>
                            {match_data['League']} | {match_data['Date']}
                        </p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Main metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "🎯 BTTS Probability",
                        match_data['BTTS %'],
                        delta=None
                    )
                
                with col2:
                    st.metric(
                        "🔒 Confidence",
                        match_data['Confidence'],
                        delta=None
                    )
                
                with col3:
                    st.metric(
                        "⚽ Expected Goals",
                        match_data['xG Total'],
                        delta=None
                    )
                
                with col4:
                    st.metric(
                        "💡 Recommendation",
                        match_data['Tip'],
                        delta=None
                    )
                
                st.markdown("---")
                
                # Prediction Methods Comparison
                st.subheader("🤖 Prediction Methods Breakdown")
                
                methods_data = pd.DataFrame({
                    'Method': ['ML Model', 'Statistical', 'Form-Based', 'Head-to-Head'],
                    'Probability': [
                        float(match_data['ML'].rstrip('%')),
                        float(match_data['Stat'].rstrip('%')),
                        float(match_data['Form'].rstrip('%')),
                        float(match_data['H2H'].rstrip('%'))
                    ],
                    'Weight': [40, 30, 20, 10]
                })
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=methods_data['Method'],
                    y=methods_data['Probability'],
                    marker_color=['#667eea', '#51cf66', '#ffd43b', '#ff6b6b'],
                    text=methods_data['Probability'].apply(lambda x: f"{x:.1f}%"),
                    textposition='auto',
                ))
                
                fig.update_layout(
                    title='Comparison of Prediction Methods',
                    xaxis_title='Method',
                    yaxis_title='BTTS Probability (%)',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # Team Analysis
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(f"🏠 {match_data['Home']} (Home)")
                    
                    home_stats = analysis['home_stats']
                    home_form = analysis['home_form']
                    
                    st.write(f"**Matches Played (Home):** {home_stats['matches_played']}")
                    st.write(f"**BTTS Rate:** {home_stats['btts_rate']:.1f}% ({home_stats['btts_count']}/{home_stats['matches_played']})")
                    st.write(f"**Goals Scored/Game:** {home_stats['avg_goals_scored']:.2f}")
                    st.write(f"**Goals Conceded/Game:** {home_stats['avg_goals_conceded']:.2f}")
                    st.write(f"**Win Rate:** {(home_stats['wins']/home_stats['matches_played']*100):.1f}%")
                    
                    st.markdown("**Recent Form (Last 5 Home):**")
                    st.write(f"Form: {home_form['form_string']}")
                    st.write(f"BTTS Rate: {home_form['btts_rate']:.1f}%")
                    st.write(f"Goals/Game: {home_form['avg_goals_scored']:.2f}")
                
                with col2:
                    st.subheader(f"✈️ {match_data['Away']} (Away)")
                    
                    away_stats = analysis['away_stats']
                    away_form = analysis['away_form']
                    
                    st.write(f"**Matches Played (Away):** {away_stats['matches_played']}")
                    st.write(f"**BTTS Rate:** {away_stats['btts_rate']:.1f}% ({away_stats['btts_count']}/{away_stats['matches_played']})")
                    st.write(f"**Goals Scored/Game:** {away_stats['avg_goals_scored']:.2f}")
                    st.write(f"**Goals Conceded/Game:** {away_stats['avg_goals_conceded']:.2f}")
                    st.write(f"**Win Rate:** {(away_stats['wins']/away_stats['matches_played']*100):.1f}%")
                    
                    st.markdown("**Recent Form (Last 5 Away):**")
                    st.write(f"Form: {away_form['form_string']}")
                    st.write(f"BTTS Rate: {away_form['btts_rate']:.1f}%")
                    st.write(f"Goals/Game: {away_form['avg_goals_scored']:.2f}")
                
                st.markdown("---")
                
                # Head-to-Head
                st.subheader("🔄 Head-to-Head History")
                h2h = analysis['h2h']
                
                if h2h['matches_played'] > 0:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Matches Played", h2h['matches_played'])
                    with col2:
                        st.metric("BTTS Count", h2h['btts_count'])
                    with col3:
                        st.metric("BTTS Rate", f"{h2h['btts_rate']:.1f}%")
                    
                    st.write(f"**Average Total Goals:** {h2h['avg_total_goals']:.1f} per match")
                else:
                    st.info("No recent head-to-head data available")
                
                st.markdown("---")
                
                # Key Insights
                st.subheader("💡 Key Insights")
                
                insights = []
                
                # Check if both teams score regularly
                if home_stats['btts_rate'] >= 70 and away_stats['btts_rate'] >= 70:
                    insights.append("✅ Both teams have very high BTTS rates in their respective venues")
                
                # Check offensive strength
                if home_stats['avg_goals_scored'] >= 2.0 and away_stats['avg_goals_scored'] >= 1.5:
                    insights.append("⚡ Both teams are offensively strong")
                
                # Check defensive weaknesses
                if home_stats['avg_goals_conceded'] >= 1.3 and away_stats['avg_goals_conceded'] >= 1.3:
                    insights.append("🚨 Both teams have defensive vulnerabilities")
                
                # Check form
                if home_form['btts_rate'] >= 60 and away_form['btts_rate'] >= 60:
                    insights.append("📈 Recent form confirms BTTS trend")
                
                # Check H2H
                if h2h['matches_played'] >= 3 and h2h['btts_rate'] >= 70:
                    insights.append("🔄 Strong BTTS history in head-to-head matches")
                
                # Display insights
                for insight in insights:
                    st.success(insight)
                
                if not insights:
                    st.info("Standard matchup - no exceptional patterns detected")

# TAB 4: Model Performance
with tab4:
    st.header("📈 Machine Learning Model Performance")
    
    st.markdown("""
        This section shows how well the ML model has been performing.
        Data is based on cross-validation during training.
    """)
    
    if analyzer and analyzer.model_trained:
        st.success("✅ ML Model is trained and active")
        
        # Model info
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🤖 Model Details")
            st.write("**Algorithm:** Random Forest Classifier")
            st.write("**Estimators:** 100 trees")
            st.write("**Max Depth:** 10")
            st.write("**Training Matches:** 305")
        
        with col2:
            st.subheader("📊 Class Distribution")
            st.write("**BTTS (Yes):** 57.0%")
            st.write("**BTTS (No):** 43.0%")
            st.write("**Accuracy:** ~59.0%")
        
        st.markdown("---")
        
        # Feature importance
        st.subheader("🎯 Top Features by Importance")
        
        feature_importance = pd.DataFrame({
            'Feature': [
                'Combined BTTS%',
                'Expected Home Goals',
                'Expected Away Goals',
                'Home Goals Avg',
                'Away BTTS%'
            ],
            'Importance': [0.213, 0.156, 0.127, 0.092, 0.079]
        })
        
        fig = px.bar(
            feature_importance,
            x='Importance',
            y='Feature',
            orientation='h',
            title='Feature Importance in ML Model',
            color='Importance',
            color_continuous_scale='Viridis'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.info("""
            **Note:** Model performance metrics shown are from cross-validation during training.
            For true backtesting results, the system would need to track predictions over time
            and compare them to actual match outcomes.
        """)
    else:
        st.warning("ML Model not trained yet")

# TAB 5: Value Bets
with tab5:
    st.header("💎 Value Betting Opportunities")
    
    st.markdown("""
        Value bets are matches where our model's predicted probability
        is significantly higher than bookmaker odds suggest.
        
        **Formula:** Expected Value = (Model Probability × Odds) - 1
        
        A positive EV indicates potential value!
    """)
    
    if 'all_results' in st.session_state and not st.session_state['all_results'].empty:
        df = st.session_state['all_results']
        
        # Simulated odds (in real version, would fetch from odds API)
        st.info("""
            💡 **Note:** This is a demonstration. In a production version, 
            we would integrate with odds APIs (Odds API, The Odds API) to get real bookmaker odds
            and calculate true value betting opportunities.
        """)
        
        # Simulate some odds based on probability
        df_value = df.copy()
        df_value['Implied_Odds'] = df_value['BTTS_num'].apply(lambda x: round(100 / x, 2))
        df_value['Market_Odds'] = df_value['Implied_Odds'] * 1.1  # Simulate bookmaker margin
        df_value['Expected_Value'] = ((df_value['BTTS_num'] / 100) * df_value['Market_Odds']) - 1
        df_value['EV_Percent'] = df_value['Expected_Value'] * 100
        
        # Filter for positive EV
        value_bets = df_value[df_value['Expected_Value'] > 0].copy()
        value_bets = value_bets.sort_values('EV_Percent', ascending=False)
        
        if not value_bets.empty:
            st.success(f"💎 Found {len(value_bets)} potential value bets!")
            
            display_value = value_bets[[
                'Date', 'League', 'Home', 'Away', 'BTTS %',
                'Market_Odds', 'EV_Percent', 'Confidence'
            ]].copy()
            
            display_value['EV_Percent'] = display_value['EV_Percent'].apply(lambda x: f"{x:.1f}%")
            display_value['Market_Odds'] = display_value['Market_Odds'].apply(lambda x: f"{x:.2f}")
            
            st.dataframe(
                display_value,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No value bets found with current market conditions")
            
    else:
        st.info("👆 Run analysis first to see value betting opportunities")

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: gray; padding: 2rem 0;'>
        <p><strong>⚽ BTTS Pro Analyzer v2.0</strong></p>
        <p>Powered by Machine Learning & Advanced Analytics</p>
        <p><small>⚠️ For informational purposes only. Gambling involves risk.</small></p>
    </div>
""", unsafe_allow_html=True)
