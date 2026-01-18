"""
ALTERNATIVE MARKETS TAB - ERWEITERTER CODE
==========================================
Kopiere diesen Code in btts_pro_app.py um Tab 7 (Alternative Markets) zu ersetzen.

NEUE FEATURES:
1. Pre-Match Analyse für Corners & Cards
2. "Höchste Wahrscheinlichkeit" Scanner
3. Verbesserte Live Analyse

INTEGRATION:
Ersetze den kompletten "with tab7:" Block (ca. Zeile 1076-1400) mit diesem Code.
"""

# ============================================================================
# TAB 7: ALTERNATIVE MARKETS - ERWEITERT
# ============================================================================
# START COPY HERE ↓↓↓

with tab7:
    st.header("📊 ALTERNATIVE MARKETS - Extended")
    
    st.markdown("""
    **Mathematische Analyse für Corners, Cards & mehr!**
    
    ✨ **NEU:** Pre-Match Analyse + "Höchste Wahrscheinlichkeit" Scanner
    """)
    
    # Sub-Tabs für verschiedene Modi
    alt_tab1, alt_tab2, alt_tab3 = st.tabs([
        "📺 Live Markets",
        "🔮 Pre-Match Analyse", 
        "🏆 Höchste Wahrscheinlichkeit"
    ])
    
    # ============================================
    # ALT TAB 1: LIVE MARKETS (Original funktionalität)
    # ============================================
    with alt_tab1:
        st.subheader("📺 Live Alternative Markets")
        
        try:
            from streamlit_autorefresh import st_autorefresh
            
            # Manual refresh
            col_r1, col_r2 = st.columns([1,3])
            with col_r1:
                if st.button("🔄 Refresh", key="refresh_alt_live"):
                    st.rerun()
            with col_r2:
                st.caption(f"Last: {datetime.now().strftime('%H:%M:%S')}")
            
            # Settings
            col1, col2 = st.columns(2)
            
            with col1:
                min_prob_alt = st.slider(
                    "Min Probability %",
                    min_value=60,
                    max_value=95,
                    value=75,
                    step=5,
                    key="min_prob_alt_live"
                )
            
            with col2:
                market_types = st.multiselect(
                    "Select Markets",
                    options=['Cards', 'Corners', 'Shots', 'Team Specials'],
                    default=['Cards', 'Corners'],
                    key="market_types_live"
                )
            
            st.markdown("---")
            
            try:
                from alternative_markets import CardPredictor, CornerPredictor, ShotPredictor, TeamSpecialPredictor
                from api_football import APIFootball
                import requests
                
                # Initialize
                api_football = APIFootball(st.secrets['api']['api_football_key'])
                
                # Get live matches
                with st.spinner("🔍 Scanning live matches..."):
                    
                    league_ids = [
                        78, 39, 140, 135, 61, 88, 94, 203, 40, 79, 262, 71,
                        2, 3, 848, 179, 144, 207, 218,
                        265, 330, 165, 188, 89, 209, 113, 292, 301
                    ]
                    
                    try:
                        api_football._rate_limit()
                        
                        response = requests.get(
                            f"{api_football.base_url}/fixtures",
                            headers=api_football.headers,
                            params={'live': 'all'},
                            timeout=15
                        )
                        
                        live_matches = []
                        
                        if response.status_code == 200:
                            data = response.json()
                            all_matches = data.get('response', [])
                            
                            for match in all_matches:
                                league_id = match.get('league', {}).get('id')
                                if league_id in league_ids:
                                    live_matches.append(match)
                            
                            st.write(f"📊 {len(all_matches)} total | ✅ {len(live_matches)} in our leagues")
                        else:
                            st.error(f"❌ API Error: {response.status_code}")
                    
                    except Exception as e:
                        st.error(f"Error: {e}")
                        live_matches = []
                
                if not live_matches:
                    st.info("⚽ No live matches in our leagues currently")
                else:
                    # Initialize predictors
                    card_pred = CardPredictor() if 'Cards' in market_types else None
                    corner_pred = CornerPredictor() if 'Corners' in market_types else None
                    shot_pred = ShotPredictor() if 'Shots' in market_types else None
                    team_pred = TeamSpecialPredictor() if 'Team Specials' in market_types else None
                    
                    all_opportunities = []
                    progress = st.progress(0)
                    
                    for idx, match in enumerate(live_matches):
                        fixture = match['fixture']
                        teams = match['teams']
                        goals = match['goals']
                        league = match['league']
                        
                        fixture_id = fixture['id']
                        home_team = teams['home']['name']
                        away_team = teams['away']['name']
                        minute = fixture['status']['elapsed'] or 0
                        home_score = goals['home'] if goals['home'] is not None else 0
                        away_score = goals['away'] if goals['away'] is not None else 0
                        
                        stats = api_football.get_match_statistics(fixture_id)
                        
                        match_data = {
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_score': home_score,
                            'away_score': away_score,
                            'minute': minute,
                            'league': league['name'],
                            'league_id': league['id'],
                            'stats': stats or {},
                            'phase_data': {'phase': 'DESPERATE' if minute >= 75 else 'NORMAL'}
                        }
                        
                        # Cards
                        if card_pred and stats:
                            try:
                                card_result = card_pred.predict_cards(match_data, minute)
                                for key, data in card_result.get('thresholds', {}).items():
                                    if (data['status'] == 'ACTIVE' and 
                                        data['probability'] >= min_prob_alt and
                                        data['strength'] in ['VERY_STRONG', 'STRONG']):
                                        all_opportunities.append({
                                            'type': 'CARDS',
                                            'match': match_data,
                                            'prediction': card_result,
                                            'threshold_data': data
                                        })
                                        break
                            except:
                                pass
                        
                        # Corners
                        if corner_pred and stats:
                            try:
                                corner_result = corner_pred.predict_corners(match_data, minute)
                                for key, data in corner_result.get('thresholds', {}).items():
                                    if (data['status'] == 'ACTIVE' and 
                                        data['probability'] >= min_prob_alt and
                                        data['strength'] in ['VERY_STRONG', 'STRONG']):
                                        all_opportunities.append({
                                            'type': 'CORNERS',
                                            'match': match_data,
                                            'prediction': corner_result,
                                            'threshold_data': data
                                        })
                                        break
                            except:
                                pass
                        
                        progress.progress((idx + 1) / len(live_matches))
                    
                    progress.empty()
                    
                    # Display
                    if not all_opportunities:
                        st.warning("⚠️ No opportunities meeting criteria")
                    else:
                        st.success(f"🔥 Found {len(all_opportunities)} opportunities!")
                        
                        for opp in all_opportunities:
                            m = opp['match']
                            p = opp['prediction']
                            t = opp['threshold_data']
                            
                            with st.expander(f"🔴 {m['minute']}' | {m['home_team']} vs {m['away_team']} | {opp['type']}"):
                                col1, col2, col3 = st.columns(3)
                                
                                if opp['type'] == 'CARDS':
                                    with col1:
                                        st.metric("Current", f"{p['current_cards']} cards")
                                    with col2:
                                        st.metric("Expected", f"{p['expected_total']:.1f}")
                                    with col3:
                                        st.metric("Probability", f"{t['probability']}%")
                                    st.info(f"**{p['recommendation']}**")
                                
                                elif opp['type'] == 'CORNERS':
                                    with col1:
                                        st.metric("Current", f"{p['current_corners']} corners")
                                    with col2:
                                        st.metric("Expected", f"{p['expected_total']:.1f}")
                                    with col3:
                                        st.metric("Probability", f"{t['probability']}%")
                                    st.info(f"**{p['recommendation']}**")
            
            except ImportError as e:
                st.error(f"❌ Import error: {e}")
        
        except ImportError:
            st.error("❌ streamlit-autorefresh not found!")
    
    # ============================================
    # ALT TAB 2: PRE-MATCH ANALYSE (NEU!)
    # ============================================
    with alt_tab2:
        st.subheader("🔮 Pre-Match Corners & Cards Analyse")
        
        st.markdown("""
        Analysiert **kommende Spiele** basierend auf Team-Statistiken.
        
        **Keine Buchmacher-Quoten** - Reine mathematische Analyse!
        """)
        
        # Settings
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pm_leagues = st.multiselect(
                "Ligen",
                options=['BL1', 'PL', 'PD', 'SA', 'FL1', 'DED', 'PPL', 'TSL'],
                default=['BL1', 'PL', 'PD'],
                key="pm_leagues"
            )
        
        with col2:
            pm_days = st.slider("Tage voraus", 1, 7, 3, key="pm_days")
        
        with col3:
            pm_market = st.selectbox("Markt", ['Corners', 'Cards', 'Beide'], key="pm_market")
        
        pm_min_prob = st.slider("Min Wahrscheinlichkeit %", 60, 90, 70, key="pm_min_prob")
        
        if st.button("🔍 Pre-Match Analyse starten", type="primary", key="pm_start"):
            
            if not pm_leagues:
                st.warning("Bitte wähle mindestens eine Liga!")
            else:
                try:
                    from alternative_markets import PreMatchAlternativeAnalyzer
                    from api_football import APIFootball
                    
                    api = APIFootball(st.secrets['api']['api_football_key'])
                    analyzer = PreMatchAlternativeAnalyzer(st.secrets['api']['api_football_key'])
                    
                    league_id_map = {
                        'BL1': 78, 'PL': 39, 'PD': 140, 'SA': 135, 'FL1': 61,
                        'DED': 88, 'PPL': 94, 'TSL': 203, 'ELC': 40, 'BL2': 79
                    }
                    
                    with st.spinner("Lade Fixtures..."):
                        all_fixtures = []
                        
                        for league_code in pm_leagues:
                            fixtures = api.get_upcoming_fixtures(league_code, pm_days)
                            for f in fixtures:
                                f['league_id'] = league_id_map.get(league_code, 39)
                                f['league_code'] = league_code
                            all_fixtures.extend(fixtures)
                        
                        st.info(f"📋 {len(all_fixtures)} Fixtures gefunden")
                    
                    if all_fixtures:
                        results = []
                        progress = st.progress(0)
                        
                        for idx, fixture in enumerate(all_fixtures):
                            try:
                                if pm_market in ['Corners', 'Beide']:
                                    corners = analyzer.analyze_prematch_corners(fixture)
                                    if corners['best_bet'] and corners['best_bet'].get('probability', 0) >= pm_min_prob:
                                        results.append({
                                            'Fixture': corners['fixture'],
                                            'Liga': fixture.get('league_code', ''),
                                            'Datum': fixture.get('date', '')[:10],
                                            'Markt': 'CORNERS',
                                            'Wette': corners['best_bet']['bet'],
                                            'Wahrsch.': f"{corners['best_bet']['probability']}%",
                                            'Erwartet': corners['expected_total'],
                                            'Stärke': corners['best_bet']['strength']
                                        })
                                
                                if pm_market in ['Cards', 'Beide']:
                                    cards = analyzer.analyze_prematch_cards(fixture)
                                    if cards['best_bet'] and cards['best_bet'].get('probability', 0) >= pm_min_prob:
                                        results.append({
                                            'Fixture': cards['fixture'],
                                            'Liga': fixture.get('league_code', ''),
                                            'Datum': fixture.get('date', '')[:10],
                                            'Markt': 'CARDS',
                                            'Wette': cards['best_bet']['bet'],
                                            'Wahrsch.': f"{cards['best_bet']['probability']}%",
                                            'Erwartet': cards['expected_total'],
                                            'Stärke': cards['best_bet']['strength'],
                                            'Derby': '🔥' if cards.get('is_derby') else ''
                                        })
                                
                                import time
                                time.sleep(0.5)  # Rate limit
                                
                            except Exception as e:
                                continue
                            
                            progress.progress((idx + 1) / len(all_fixtures))
                        
                        progress.empty()
                        
                        if results:
                            st.success(f"✅ {len(results)} Empfehlungen gefunden!")
                            
                            df = pd.DataFrame(results)
                            df['Prob_Num'] = df['Wahrsch.'].str.replace('%', '').astype(float)
                            df = df.sort_values('Prob_Num', ascending=False)
                            df = df.drop(columns=['Prob_Num'])
                            
                            st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Keine Empfehlungen gefunden.")
                    
                except ImportError as e:
                    st.error(f"Import error: {e}")
                except Exception as e:
                    st.error(f"Fehler: {e}")
    
    # ============================================
    # ALT TAB 3: HÖCHSTE WAHRSCHEINLICHKEIT (NEU!)
    # ============================================
    with alt_tab3:
        st.subheader("🏆 Höchste Wahrscheinlichkeit Scanner")
        
        st.markdown("""
        Scannt **ALLE Märkte** und findet automatisch die beste Wette.
        
        📊 **Märkte:** BTTS, Goals, Corners, Cards  
        🧮 **Methode:** Reine Statistik - **KEINE Buchmacher-Quoten!**
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            hp_leagues = st.multiselect(
                "Ligen",
                options=['BL1', 'PL', 'PD', 'SA', 'FL1', 'DED', 'PPL', 'TSL'],
                default=['BL1', 'PL', 'PD', 'SA', 'FL1'],
                key="hp_leagues"
            )
        
        with col2:
            hp_min_prob = st.slider("Min %", 65, 90, 75, key="hp_min_prob")
        
        if st.button("🚀 Scanner starten", type="primary", key="hp_start"):
            
            if not hp_leagues:
                st.warning("Bitte wähle mindestens eine Liga!")
            else:
                try:
                    from alternative_markets import HighestProbabilityFinder
                    from api_football import APIFootball
                    
                    api = APIFootball(st.secrets['api']['api_football_key'])
                    finder = HighestProbabilityFinder(st.secrets['api']['api_football_key'])
                    
                    league_id_map = {
                        'BL1': 78, 'PL': 39, 'PD': 140, 'SA': 135, 'FL1': 61,
                        'DED': 88, 'PPL': 94, 'TSL': 203, 'ELC': 40, 'BL2': 79
                    }
                    
                    with st.spinner("Scanne alle Märkte..."):
                        all_fixtures = []
                        
                        for league_code in hp_leagues:
                            fixtures = api.get_upcoming_fixtures(league_code, days_ahead=3)
                            for f in fixtures:
                                f['league_id'] = league_id_map.get(league_code, 39)
                                f['league_code'] = league_code
                            all_fixtures.extend(fixtures)
                        
                        st.info(f"📋 {len(all_fixtures)} Fixtures gefunden. Analysiere...")
                        
                        all_opportunities = finder.scan_all_fixtures(all_fixtures)
                        
                        # Filter
                        filtered = [o for o in all_opportunities 
                                   if o['best_bet']['probability'] >= hp_min_prob]
                    
                    if filtered:
                        st.success(f"🎯 {len(filtered)} Top-Gelegenheiten gefunden!")
                        
                        for opp in filtered[:10]:
                            best = opp['best_bet']
                            
                            if best['strength'] == 'VERY_STRONG':
                                emoji = "🔥🔥"
                            elif best['strength'] == 'STRONG':
                                emoji = "🔥"
                            else:
                                emoji = "✅"
                            
                            with st.expander(f"{emoji} {opp['fixture']} | {best['probability']}%"):
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    st.metric("Wette", best['bet'])
                                with col2:
                                    st.metric("Wahrscheinlichkeit", f"{best['probability']}%")
                                with col3:
                                    st.metric("Edge", f"+{best['edge']}%")
                                
                                st.caption(f"Liga: {opp['league']} | Markt: {best['market']}")
                        
                        # Export button
                        export_data = [{
                            'Fixture': o['fixture'],
                            'Liga': o['league'],
                            'Wette': o['best_bet']['bet'],
                            'Wahrscheinlichkeit': f"{o['best_bet']['probability']}%",
                            'Markt': o['best_bet']['market'],
                            'Stärke': o['best_bet']['strength']
                        } for o in filtered]
                        
                        df = pd.DataFrame(export_data)
                        
                        st.download_button(
                            "📥 Als CSV exportieren",
                            df.to_csv(index=False),
                            "highest_probability_bets.csv",
                            "text/csv",
                            key="hp_export"
                        )
                    else:
                        st.info(f"Keine Wetten mit ≥{hp_min_prob}% gefunden.")
                
                except ImportError as e:
                    st.error(f"Import error: {e}")
                except Exception as e:
                    st.error(f"Fehler: {e}")

# END COPY HERE ↑↑↑
