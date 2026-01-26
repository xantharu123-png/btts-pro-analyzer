"""
ULTRA SCANNER - REAL IMPLEMENTATION
Multi-Sport Opportunity Ranker - NO DEMOS

Combines opportunities from:
- Football
- Basketball (NBA + Euroleague)
- Tennis (ATP/WTA)
- Cricket (IPL/T20/ODI)

Ranks by composite score:
Score = (Edge × 0.4) + (ROI × 0.3) + (Confidence × 0.3)

Author: Miroslav
Date: January 2026
"""

import streamlit as st
from typing import List, Dict
from datetime import datetime

class MultiSportRanker:
    """
    Ranks opportunities across all sports
    REAL implementation - combines live scanners
    """
    
    def __init__(self):
        self.opportunities = []
    
    def add_opportunity(self, sport: str, opp: Dict):
        """Add an opportunity from any sport"""
        opp['sport'] = sport
        opp['sport_emoji'] = self._get_sport_emoji(sport)
        opp['score'] = self.calculate_score(opp)
        opp['timestamp'] = datetime.now()
        self.opportunities.append(opp)
    
    def _get_sport_emoji(self, sport: str) -> str:
        """Get emoji for sport"""
        emojis = {
            'Football': '⚽',
            'Basketball': '🏀',
            'Tennis': '🎾',
            'Cricket': '🏏'
        }
        return emojis.get(sport, '🎯')
    
    def calculate_score(self, opp: Dict) -> float:
        """
        Calculate composite score
        Formula: (Edge × 0.4) + (ROI × 0.3) + (Confidence/100 × 30 × 0.3)
        """
        edge = opp.get('edge', 0)
        roi = opp.get('roi', 0)
        confidence = opp.get('confidence', 0) / 100
        
        score = (edge * 0.4) + (roi * 0.3) + (confidence * 30 * 0.3)
        return round(score, 1)
    
    def get_top_opportunities(self, limit: int = 10, filters: Dict = None) -> List[Dict]:
        """
        Get top N opportunities sorted by score
        Optionally filter by sport, min_edge, min_roi, min_confidence
        """
        filtered = self.opportunities
        
        if filters:
            if 'sports' in filters and filters['sports']:
                filtered = [o for o in filtered if o['sport'] in filters['sports']]
            
            if 'min_edge' in filters:
                filtered = [o for o in filtered if o['edge'] >= filters['min_edge']]
            
            if 'min_roi' in filters:
                filtered = [o for o in filtered if o['roi'] >= filters['min_roi']]
            
            if 'min_confidence' in filters:
                filtered = [o for o in filtered if o['confidence'] >= filters['min_confidence']]
        
        # Sort by score
        sorted_opps = sorted(filtered, key=lambda x: x['score'], reverse=True)
        
        return sorted_opps[:limit]
    
    def clear(self):
        """Clear all opportunities"""
        self.opportunities = []
    
    def get_stats(self) -> Dict:
        """Get statistics about collected opportunities"""
        if not self.opportunities:
            return {
                'total': 0,
                'by_sport': {},
                'avg_score': 0,
                'avg_edge': 0,
                'avg_roi': 0
            }
        
        by_sport = {}
        for opp in self.opportunities:
            sport = opp['sport']
            by_sport[sport] = by_sport.get(sport, 0) + 1
        
        return {
            'total': len(self.opportunities),
            'by_sport': by_sport,
            'avg_score': round(sum(o['score'] for o in self.opportunities) / len(self.opportunities), 1),
            'avg_edge': round(sum(o['edge'] for o in self.opportunities) / len(self.opportunities), 1),
            'avg_roi': round(sum(o['roi'] for o in self.opportunities) / len(self.opportunities), 1)
        }


def create_ultra_tab(filters: Dict = None):
    """
    Main ULTRA Scanner Tab Creator
    NO DEMOS - ONLY REAL DATA from all scanners
    """
    st.header("🔥 ULTRA SCANNER")
    st.markdown("### Best Opportunities from ALL Sports - Live Rankings")
    
    # Create ranker
    ranker = MultiSportRanker()
    
    # Collect opportunities from all active scanners
    with st.spinner("🔍 Scanning ALL sports for opportunities..."):
        
        # Import and scan Football
        try:
            from football_scanner import scan_opportunities
            football_opps = scan_opportunities()
            for opp in football_opps:
                ranker.add_opportunity("Football", opp)
        except Exception as e:
            st.caption(f"Football scanner: {e}")
        
        # Import and scan Basketball
        try:
            from basketball_scanner import BasketballScanner
            bball = BasketballScanner()
            games = bball.scan_live_games("All")
            for game in games:
                # Quarter Winner
                quarter_opp = bball.analyze_quarter_winner(game)
                if quarter_opp:
                    ranker.add_opportunity("Basketball", quarter_opp)
                
                # Total Points
                total_opp = bball.analyze_total_points(game)
                if total_opp:
                    ranker.add_opportunity("Basketball", total_opp)
        except Exception as e:
            st.caption(f"Basketball scanner: {e}")
        
        # Import and scan Tennis
        try:
            from tennis_scanner import TennisScanner
            tennis = TennisScanner()
            matches = tennis.get_live_matches()
            for match in matches:
                # Next Game
                ng_opp = tennis.analyze_next_game(match)
                if ng_opp:
                    ranker.add_opportunity("Tennis", ng_opp)
                
                # Set Winner
                set_opp = tennis.analyze_set_winner(match)
                if set_opp:
                    ranker.add_opportunity("Tennis", set_opp)
        except Exception as e:
            st.caption(f"Tennis scanner: {e}")
        
        # Import and scan Cricket
        try:
            from cricket_scanner import CricketScanner
            cricket = CricketScanner()
            matches = cricket.get_live_matches()
            for match in matches:
                # Over Runs
                over_opp = cricket.analyze_current_over(match)
                if over_opp:
                    ranker.add_opportunity("Cricket", over_opp)
                
                # Total Runs
                total_opp = cricket.analyze_total_runs(match)
                if total_opp:
                    ranker.add_opportunity("Cricket", total_opp)
        except Exception as e:
            st.caption(f"Cricket scanner: {e}")
    
    # Get stats
    stats = ranker.get_stats()
    
    if stats['total'] == 0:
        st.info("ℹ️ No opportunities found across all sports at the moment")
        st.caption("Check back when there are live games in any sport")
        return
    
    # Display stats
    st.success(f"✅ Found {stats['total']} opportunities across all sports!")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Opps", stats['total'])
    with col2:
        st.metric("Avg Score", stats['avg_score'])
    with col3:
        st.metric("Avg Edge", f"{stats['avg_edge']}%")
    with col4:
        st.metric("Avg ROI", f"{stats['avg_roi']}%")
    
    # Sport breakdown
    st.markdown("### 📊 By Sport:")
    for sport, count in stats['by_sport'].items():
        st.write(f"{ranker._get_sport_emoji(sport)} **{sport}:** {count} opportunities")
    
    st.markdown("---")
    
    # Get top opportunities (with filters if provided)
    top_opps = ranker.get_top_opportunities(limit=10, filters=filters)
    
    if not top_opps:
        st.info("No opportunities match your filter criteria")
        return
    
    st.markdown("### 🏆 Top 10 Ranked Opportunities")
    
    # Display ranked opportunities
    for i, opp in enumerate(top_opps, 1):
        with st.container():
            col1, col2, col3, col4 = st.columns([0.5, 2, 2.5, 1])
            
            with col1:
                st.markdown(f"### #{i}")
            
            with col2:
                st.markdown(f"{opp['sport_emoji']} **{opp['sport']}**")
                market = opp.get('market', '')
                team = opp.get('team', '')
                player = opp.get('player', '')
                display_text = f"{team} {market}" if team else f"{player} {market}" if player else market
                st.caption(display_text)
            
            with col3:
                st.markdown(f"Edge: +{opp['edge']}% | ROI: +{opp['roi']}% | Conf: {opp['confidence']}%")
                st.caption(f"Odds: {opp.get('odds', 'N/A')}")
            
            with col4:
                stars = "⭐" * (5 if opp['score'] >= 14 else 4 if opp['score'] >= 12 else 3)
                st.markdown(f"**Score: {opp['score']}**")
                st.markdown(stars)
            
            # Details expander
            with st.expander(f"📊 View Full Analysis"):
                st.markdown(f"""
                **Bet:** {display_text} @ {opp.get('odds', 'N/A')}
                
                **Metrics:**
                - Edge: +{opp['edge']}%
                - Expected ROI: +{opp['roi']}%
                - Confidence: {opp['confidence']}%
                - Composite Score: {opp['score']}
                
                **Stake Recommendation:** {opp.get('stake', '2-3%')} of bankroll
                
                **Analysis:**
                {chr(10).join(f"- {r}" for r in opp.get('reasoning', []))}
                """)
            
            st.markdown("---")


if __name__ == "__main__":
    st.set_page_config(
        page_title="ULTRA Scanner - Multi-Sport",
        page_icon="🔥",
        layout="wide"
    )
    
    st.title("🔥 ULTRA SCANNER - Multi-Sport Opportunity Ranker")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    create_ultra_tab()
