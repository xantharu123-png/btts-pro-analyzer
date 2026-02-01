"""
BTTS Pro Analyzer V3.0 - Clean Modern Interface
================================================
KEINE SIDEBAR - Alles inline in Tabs
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import sqlite3
import os
from pathlib import Path
from typing import Optional

# Page config - MUST BE FIRST
st.set_page_config(
    page_title="BTTS Pro Analyzer V3.0",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide sidebar with CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem 2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
    }
    
    .status-bar {
        display: flex;
        gap: 1rem;
        align-items: center;
        padding: 0.5rem 1rem;
        background: #f0f2f6;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .top-tip {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

from advanced_analyzer import AdvancedBTTSAnalyzer
from data_engine import DataEngine

# Optional imports
try:
    from modern_progress_bar import ModernProgressBar
    PROGRESS_BAR_AVAILABLE = True
except ImportError:
    PROGRESS_BAR_AVAILABLE = False

try:
    from alternative_markets_tab_extended import create_alternative_markets_tab_extended
    ALTERNATIVE_MARKETS_AVAILABLE = True
except ImportError:
    ALTERNATIVE_MARKETS_AVAILABLE = False


def _get_supabase_url() -> Optional[str]:
    try:
        if hasattr(st, 'secrets') and 'SUPABASE_DB_URL' in st.secrets:
            return st.secrets['SUPABASE_DB_URL']
    except:
        pass
    return os.environ.get('SUPABASE_DB_URL')


def _get_db_connection(db_path: str = "btts_data.db"):
    supabase_url = _get_supabase_url()
    if supabase_url:
        try:
            import psycopg2
            return psycopg2.connect(supabase_url)
        except:
            pass
    return sqlite3.connect(db_path)


# =============================================================================
# INITIALIZE ANALYZER
# =============================================================================

@st.cache_resource
def get_analyzer():
    try:
        api_key = st.secrets.get("FOOTBALL_DATA_API_KEY") if hasattr(st, 'secrets') else None
        weather_key = st.secrets.get("OPENWEATHER_API_KEY") if hasattr(st, 'secrets') else None
        api_football_key = st.secrets.get("API_FOOTBALL_KEY") if hasattr(st, 'secrets') else None
        
        analyzer = AdvancedBTTSAnalyzer(
            api_key=api_key, 
            weather_api_key=weather_key,
            api_football_key=api_football_key
        )
        return analyzer, True
    except Exception as e:
        st.error(f"Failed to initialize: {e}")
        return None, False

analyzer, analyzer_ready = get_analyzer()

# =============================================================================
# HEADER - Compact & Professional
# =============================================================================

# Status badges as small inline indicators
status_ml = "✅" if analyzer_ready else "❌"
status_text = f"**⚽ BTTS Pro Analyzer** &nbsp;&nbsp; | &nbsp;&nbsp; V3.0 &nbsp;&nbsp; | &nbsp;&nbsp; {status_ml} ML &nbsp;&nbsp; | &nbsp;&nbsp; 🔄 Live"

st.markdown(f"## {status_text}", unsafe_allow_html=True)

st.markdown("---")

# =============================================================================
# TABS
# =============================================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🔥 Top Tips", 
    "📊 All Matches", 
    "🔥 LIVE SCANNER",
    "📊 ALT. MARKETS",
    "📈 Model Info",
    "🔴 RED CARDS",
    "⚙️ Settings"
])

# =============================================================================
# TAB 1: TOP TIPS
# =============================================================================

with tab1:
    st.header("🔥 Premium BTTS Tips")
    
    # Get available leagues
    available_leagues = list(analyzer.engine.LEAGUES_CONFIG.keys()) if analyzer else []
    
    # ROW 1: Liga Selection
    col_check, col_leagues = st.columns([1, 5])
    
    with col_check:
        select_all = st.checkbox("Alle Ligen", value=False, key="tab1_all")
    
    with col_leagues:
        if select_all:
            selected_leagues = available_leagues
            st.info(f"✅ Alle {len(available_leagues)} Ligen ausgewählt")
        else:
            default = ['BL1', 'PL', 'PD'] if all(l in available_leagues for l in ['BL1', 'PL', 'PD']) else available_leagues[:3]
            selected_leagues = st.multiselect(
                "Ligen auswählen",
                options=available_leagues,
                default=default,
                key="tab1_leagues",
                label_visibility="collapsed"
            )
    
    # ROW 2: Filters + Button
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    
    with col1:
        min_btts = st.number_input("Min BTTS %", 50, 90, 65, 5, key="tab1_btts")
    
    with col2:
        min_conf = st.number_input("Min Conf %", 50, 95, 60, 5, key="tab1_conf")
    
    with col3:
        days_ahead = st.number_input("Tage voraus", 1, 14, 7, key="tab1_days")
    
    with col4:
        st.write("")  # Spacer
        analyze_btn = st.button("🔍 ANALYSIEREN", key="analyze_top", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # SEARCH LOGIC
    if analyze_btn:
        if not selected_leagues:
            st.warning("⚠️ Bitte mindestens eine Liga auswählen!")
        else:
            # Debug: Check API key
            api_key_available = hasattr(analyzer, 'api_football_key') and analyzer.api_football_key
            if not api_key_available:
                st.error("❌ API_FOOTBALL_KEY nicht konfiguriert! Bitte in Streamlit Secrets hinzufügen.")
                st.stop()
            
            all_results = []
            errors = []
            
            progress = st.progress(0)
            status = st.empty()
            
            for idx, league_code in enumerate(selected_leagues):
                status.text(f"🔍 Analysiere {league_code}... ({idx+1}/{len(selected_leagues)})")
                
                try:
                    results = analyzer.analyze_upcoming_matches(
                        league_code, 
                        days_ahead=days_ahead,
                        min_probability=min_btts
                    )
                    
                    if results is not None and not results.empty:
                        results['League'] = league_code
                        all_results.append(results)
                        status.text(f"✅ {league_code}: {len(results)} Spiele")
                    else:
                        errors.append(f"{league_code}: Keine Spiele")
                except Exception as e:
                    errors.append(f"{league_code}: {str(e)[:50]}")
                
                progress.progress((idx + 1) / len(selected_leagues))
            
            progress.empty()
            status.empty()
            
            # Show errors if any
            if errors and not all_results:
                with st.expander("⚠️ Debug Info", expanded=True):
                    for err in errors:
                        st.text(err)
            
            if all_results:
                combined = pd.concat(all_results, ignore_index=True)
                
                combined['BTTS_num'] = combined['BTTS %'].str.rstrip('%').astype(float)
                combined['Conf_num'] = combined['Confidence'].str.rstrip('%').astype(float)
                
                top_tips = combined[
                    (combined['BTTS_num'] >= min_btts) & 
                    (combined['Conf_num'] >= min_conf)
                ].sort_values('BTTS_num', ascending=False)
                
                st.session_state['all_results'] = combined
                st.session_state['top_tips'] = top_tips
                
                if not top_tips.empty:
                    st.success(f"🔥 {len(top_tips)} Premium Tips gefunden!")
                    
                    for idx, row in top_tips.head(20).iterrows():
                        with st.container():
                            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                            
                            with c1:
                                st.markdown(f"**{row['Home']}** vs **{row['Away']}**")
                                st.caption(f"{row['League']} | {row['Date']}")
                            
                            with c2:
                                st.metric("BTTS", row['BTTS %'])
                            
                            with c3:
                                st.metric("Confidence", row['Confidence'])
                            
                            with c4:
                                st.metric("xG Total", row['xG Total'])
                            
                            st.markdown("---")
                else:
                    st.warning(f"⚠️ Keine Tips mit BTTS ≥ {min_btts}% und Confidence ≥ {min_conf}% gefunden")
                    st.info(f"📊 {len(combined)} Spiele analysiert, aber keines erfüllt die Kriterien. Versuche niedrigere Filter.")
            else:
                st.error("❌ Keine Spiele in den ausgewählten Ligen gefunden")
                st.info("💡 Mögliche Gründe: API-Limit erreicht, keine geplanten Spiele, oder Datenbankfehler. Versuche 'Settings' → 'Smart Update'")
    else:
        # Initial state - no button clicked yet
        st.info("👆 Wähle Ligen und klicke auf 'ANALYSIEREN' um Tips zu finden")

# =============================================================================
# TAB 2: ALL MATCHES
# =============================================================================

with tab2:
    st.header("📊 Alle Empfehlungen")
    
    if 'all_results' in st.session_state and st.session_state['all_results'] is not None:
        df = st.session_state['all_results']
        
        col1, col2 = st.columns([1, 3])
        with col1:
            min_filter = st.slider("Min BTTS %", 50, 90, 55, key="tab2_filter")
        
        df_filtered = df[df['BTTS_num'] >= min_filter].copy()
        
        if not df_filtered.empty:
            st.success(f"📋 {len(df_filtered)} Spiele")
            
            display_df = df_filtered[[
                'Date', 'League', 'Home', 'Away', 'BTTS %', 
                'Confidence', 'Tip', 'xG Total'
            ]].sort_values('BTTS %', key=lambda x: x.str.rstrip('%').astype(float), ascending=False)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Ø BTTS", f"{df_filtered['BTTS_num'].mean():.1f}%")
            with col2:
                st.metric("Ø Confidence", f"{df_filtered['Conf_num'].mean():.1f}%")
            with col3:
                st.metric("🔥 Top Tips", len(df_filtered[df_filtered['Tip'] == '🔥 TOP TIP']))
            with col4:
                st.metric("✅ Strong", len(df_filtered[df_filtered['Tip'] == '✅ STRONG']))
    else:
        st.info("👆 Erst im Tab 'Top Tips' analysieren")

# =============================================================================
# TAB 3: LIVE SCANNER
# =============================================================================

with tab3:
    st.header("🔥 ULTRA LIVE SCANNER V3.0")
    
    try:
        from ultra_live_scanner_v3 import UltraLiveScanner, display_ultra_opportunity
        from api_football import APIFootball
        
        api_key = st.secrets.get("API_FOOTBALL_KEY") if hasattr(st, 'secrets') else None
        
        if not api_key:
            st.error("❌ API_FOOTBALL_KEY fehlt in secrets!")
        else:
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                min_btts_live = st.number_input("Min BTTS %", 50, 95, 70, 5, key="live_btts")
            
            with col2:
                min_conf_live = st.selectbox("Min Confidence", ["ALL", "MEDIUM", "HIGH", "VERY_HIGH"], key="live_conf")
            
            with col3:
                st.write("")
                scan_btn = st.button("🔴 LIVE SCAN STARTEN", key="live_scan", type="primary")
            
            if scan_btn:
                with st.spinner("🔍 Scanne Live-Spiele..."):
                    api = APIFootball(api_key)
                    scanner = UltraLiveScanner(api)
                    
                    live_matches = api.get_live_matches()
                    
                    if live_matches:
                        st.info(f"📊 {len(live_matches)} Live-Spiele gefunden")
                        
                        opportunities = []
                        progress = st.progress(0)
                        
                        for idx, match in enumerate(live_matches):
                            analysis = scanner.analyze_live_match_ultra(match)
                            
                            if analysis:
                                btts_prob = analysis.get('btts_prob', analysis.get('btts', {}).get('probability', 0))
                                btts_conf = analysis.get('btts_confidence', analysis.get('btts', {}).get('confidence', ''))
                                
                                if btts_prob >= min_btts_live:
                                    conf_ok = (
                                        min_conf_live == "ALL" or
                                        (min_conf_live == "VERY_HIGH" and btts_conf == "VERY_HIGH") or
                                        (min_conf_live == "HIGH" and btts_conf in ["VERY_HIGH", "HIGH"]) or
                                        (min_conf_live == "MEDIUM" and btts_conf in ["VERY_HIGH", "HIGH", "MEDIUM"])
                                    )
                                    if conf_ok:
                                        opportunities.append(analysis)
                            
                            progress.progress((idx + 1) / len(live_matches))
                        
                        progress.empty()
                        
                        if opportunities:
                            opportunities.sort(key=lambda x: x.get('btts_prob', x.get('btts', {}).get('probability', 0)), reverse=True)
                            
                            st.success(f"🔥 {len(opportunities)} Opportunities!")
                            
                            for opp in opportunities:
                                display_ultra_opportunity(opp)
                        else:
                            st.warning("Keine starken Opportunities gefunden")
                    else:
                        st.warning("Keine Live-Spiele momentan")
                        
    except ImportError as e:
        st.error(f"⚠️ Module fehlen: {e}")

# =============================================================================
# TAB 4: ALTERNATIVE MARKETS
# =============================================================================

with tab4:
    st.header("📊 Alternative Markets")
    
    if ALTERNATIVE_MARKETS_AVAILABLE:
        try:
            api_key = st.secrets.get("API_FOOTBALL_KEY") if hasattr(st, 'secrets') else None
            if api_key:
                create_alternative_markets_tab_extended(api_key)
            else:
                st.error("API_FOOTBALL_KEY fehlt")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.info("Alternative Markets Modul nicht verfügbar")

# =============================================================================
# TAB 5: MODEL INFO
# =============================================================================

with tab5:
    st.header("📈 ML Model Info")
    
    if analyzer and analyzer.model_trained:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Status", "✅ Trained")
        
        with col2:
            n_models = len(analyzer.ml_models) if hasattr(analyzer, 'ml_models') else 1
            st.metric("Models", n_models)
        
        with col3:
            st.metric("Features", "20")
        
        st.markdown("---")
        
        if hasattr(analyzer, 'ml_models') and analyzer.ml_models:
            st.subheader("🤖 Ensemble Models")
            
            for name, weight in analyzer.ml_weights.items():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{name.replace('_', ' ').title()}**")
                with col2:
                    st.write(f"{weight*100:.0f}%")
        
        try:
            if os.path.exists('ml_model.pkl'):
                mod_time = os.path.getmtime('ml_model.pkl')
                last_trained = datetime.fromtimestamp(mod_time).strftime('%d.%m.%Y %H:%M')
                st.caption(f"🕐 Last trained: {last_trained}")
        except:
            pass
    else:
        st.warning("Model nicht trainiert")

# =============================================================================
# TAB 6: RED CARDS
# =============================================================================

with tab6:
    st.header("🔴 Red Card Alert System")
    st.info("🚧 Coming soon - Live Red Card Detection")

# =============================================================================
# TAB 7: SETTINGS
# =============================================================================

with tab7:
    st.header("⚙️ Einstellungen & Admin")
    
    with st.expander("🔄 Daten aktualisieren"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⚡ Smart Update", help="Nur neue Spiele"):
                with st.spinner("Updating..."):
                    try:
                        for league in ['BL1', 'PL', 'PD', 'SA', 'FL1']:
                            if analyzer:
                                analyzer.engine.fetch_league_matches(league, season=2025, force_refresh=False)
                        st.success("✅ Updated!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with col2:
            if st.button("🔄 Full Refresh", help="Alle Daten neu"):
                with st.spinner("Refreshing..."):
                    try:
                        all_leagues = list(analyzer.engine.LEAGUES_CONFIG.keys()) if analyzer else []
                        for league in all_leagues[:10]:
                            analyzer.engine.fetch_league_matches(league, season=2025, force_refresh=True)
                        st.success("✅ Refreshed!")
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    with st.expander("🤖 ML Model Training"):
        st.warning("⚠️ Training dauert einige Minuten!")
        
        if st.button("🚀 Retrain ML Model"):
            with st.spinner("Training V3.0 Ensemble..."):
                try:
                    analyzer.train_model()
                    st.success("✅ Model trained!")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Training failed: {e}")
    
    with st.expander("ℹ️ System Info"):
        st.write(f"**Version:** 3.0")
        st.write(f"**Analyzer Ready:** {analyzer_ready}")
        st.write(f"**ML Trained:** {analyzer.model_trained if analyzer else False}")
        
        if analyzer and hasattr(analyzer, 'ml_models'):
            st.write(f"**Ensemble Models:** {list(analyzer.ml_models.keys())}")
        
        try:
            conn = _get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM matches")
            total = cursor.fetchone()[0]
            conn.close()
            st.write(f"**Matches in DB:** {total}")
        except:
            pass

# =============================================================================
# FOOTER
# =============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    ⚽ BTTS Pro Analyzer V3.0 | Powered by ML Ensemble | For informational purposes only
</div>
""", unsafe_allow_html=True)
