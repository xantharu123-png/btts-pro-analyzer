# VOLLSTÄNDIGES TAB BEISPIEL - MIT PROGRESS BAR

# ==============================================================================
# TAB 1: TOP TIPS 🔥
# ==============================================================================

with tabs[0]:  # Angenommen tabs[0] ist "Top Tips"
    st.header("🔥 Premium Tips - Highest Confidence")
    st.markdown("Filtering for BTTS ≥ 60% AND Confidence ≥ 60%")
    
    # Config Sliders
    col1, col2 = st.columns(2)
    
    with col1:
        min_btts = st.slider(
            "Min BTTS %",
            min_value=50,
            max_value=90,
            value=60,
            step=5,
            key='min_btts_toptips'
        )
    
    with col2:
        min_conf = st.slider(
            "Min Confidence %",
            min_value=50,
            max_value=95,
            value=60,
            step=5,
            key='min_conf_toptips'
        )
    
    st.markdown("---")
    
    # Analyze Button
    if st.button("🔍 Analyze Matches", key='analyze_top_tips_btn'):
        
        # ======================================================================
        # HIER BEGINNT DER PROGRESS BAR CODE
        # ======================================================================
        
        # Import Progress Bar (nur einmal am Anfang der Datei!)
        from modern_progress_bar import ModernProgressBar
        
        # Create Progress Bar
        leagues = list(analyzer.engine.LEAGUES_CONFIG.items())
        progress = ModernProgressBar(
            total_items=len(leagues),
            title="Analyzing Leagues for Premium Tips"
        )
        
        # Collect all matches
        all_matches = []
        
        # Loop through leagues
        for idx, (league_code, league_id) in enumerate(leagues):
            # Update Progress Bar mit aktueller Liga
            progress.update(league_code, idx)
            
            try:
                # Analyze matches
                matches = analyzer.analyze_upcoming_matches(league_id, league_code)
                
                # Filter by thresholds
                filtered = [
                    m for m in matches
                    if m.get('btts_percentage', 0) >= min_btts
                    and m.get('confidence', 0) >= min_conf
                ]
                
                all_matches.extend(filtered)
                
            except Exception as e:
                st.error(f"❌ Error analyzing {league_code}: {e}")
                continue
        
        # Complete Progress Bar
        progress.complete(
            success_message=f"✅ Found {len(all_matches)} premium tips!"
        )
        
        # ======================================================================
        # HIER ENDET DER PROGRESS BAR CODE
        # ======================================================================
        
        # Display Results
        if all_matches:
            # Sort by confidence
            all_matches.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            
            st.success(f"🔥 Found {len(all_matches)} premium tips!")
            
            # Display each match
            for match in all_matches:
                with st.expander(
                    f"🔥 {match['home_team']} vs {match['away_team']} - "
                    f"BTTS {match['btts_percentage']:.1f}% | "
                    f"Conf {match['confidence']:.1f}%"
                ):
                    # Match Details
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("BTTS %", f"{match['btts_percentage']:.1f}%")
                    
                    with col2:
                        st.metric("Confidence", f"{match['confidence']:.1f}%")
                    
                    with col3:
                        st.metric("xG Total", f"{match.get('xg_total', 0):.2f}")
                    
                    st.markdown(f"**League:** {match['league']}")
                    st.markdown(f"**Date:** {match.get('date', 'TBD')}")
        
        else:
            st.info(f"⚠️ No matches found with BTTS ≥ {min_btts}% and Confidence ≥ {min_conf}%")
            st.markdown("💡 Try lowering the thresholds!")
