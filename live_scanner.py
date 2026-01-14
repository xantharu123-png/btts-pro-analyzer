"""
Live BTTS Scanner for Local Streamlit
Real-time match analysis with auto-refresh
"""

import streamlit as st
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

class LiveBTTSScanner:
    """
    Live BTTS Scanner
    Monitors live matches and identifies betting opportunities
    """
    
    def __init__(self, analyzer, api_football):
        self.analyzer = analyzer
        self.api_football = api_football
    
    def get_live_matches(self) -> List[Dict]:
        """
        Get all currently live matches from supported leagues
        """
        try:
            # League IDs from API-Football
            league_ids = [78, 39, 140, 135, 61, 88, 40, 94, 71, 144, 113, 103]
            
            all_live_matches = []
            
            for league_id in league_ids:
                self.api_football._rate_limit()
                
                response = requests.get(
                    f"{self.api_football.base_url}/fixtures",
                    headers=self.api_football.headers,
                    params={
                        'league': league_id,
                        'live': 'all',
                        'season': 2024
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    matches = data.get('response', [])
                    all_live_matches.extend(matches)
                
                time.sleep(0.3)  # Rate limiting
            
            return all_live_matches
        
        except Exception as e:
            print(f"Error getting live matches: {e}")
            return []
    
    def analyze_live_match(self, match: Dict) -> Optional[Dict]:
        """
        Analyze a live match for BTTS opportunity
        """
        try:
            fixture = match['fixture']
            teams = match['teams']
            goals = match['goals']
            
            home_team = teams['home']['name']
            away_team = teams['away']['name']
            home_team_id = teams['home']['id']
            away_team_id = teams['away']['id']
            
            minute = fixture['status']['elapsed']
            home_score = goals['home'] if goals['home'] is not None else 0
            away_score = goals['away'] if goals['away'] is not None else 0
            
            # Get live statistics
            stats = self.api_football.get_match_statistics(fixture['id'])
            
            # Calculate live BTTS probability
            live_btts = self.calculate_live_btts(
                home_team_id,
                away_team_id,
                minute,
                home_score,
                away_score,
                stats
            )
            
            return {
                'fixture_id': fixture['id'],
                'home_team': home_team,
                'away_team': away_team,
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'minute': minute,
                'score': f"{home_score}-{away_score}",
                'home_score': home_score,
                'away_score': away_score,
                'btts_prob': live_btts['probability'],
                'confidence': live_btts['confidence'],
                'stats': stats,
                'league': match['league']['name'],
                'recommendation': live_btts['recommendation']
            }
        
        except Exception as e:
            print(f"Error analyzing match: {e}")
            return None
    
    def calculate_live_btts(self, home_id: int, away_id: int, 
                           minute: int, home_score: int, away_score: int,
                           stats: Optional[Dict]) -> Dict:
        """
        Calculate live BTTS probability based on current match state
        """
        # Get pre-match prediction (base)
        try:
            pre_match = self.analyzer.analyze_match(home_id, away_id)
            base_btts = pre_match['ensemble_prediction']
        except:
            base_btts = 70  # Fallback
        
        # Time factor (how much time left)
        time_factor = self.calculate_time_factor(minute, home_score, away_score)
        
        # Score adjustment
        score_adjustment = self.calculate_score_adjustment(
            minute, home_score, away_score
        )
        
        # Stats boost (if available)
        stats_boost = 0
        if stats and stats.get('xg_home') and stats.get('xg_away'):
            xg_home = stats['xg_home']
            xg_away = stats['xg_away']
            
            # Both teams creating chances = higher BTTS
            if xg_home > 0.5 and xg_away > 0.5:
                stats_boost = 5
            if xg_home > 1.0 and xg_away > 1.0:
                stats_boost = 10
        
        # Calculate final probability
        live_btts = (base_btts * time_factor) + score_adjustment + stats_boost
        
        # Bounds
        live_btts = max(20, min(95, live_btts))
        
        # Confidence
        confidence = self.calculate_confidence(minute, stats)
        
        # Recommendation
        recommendation = self.get_recommendation(live_btts, confidence, minute)
        
        return {
            'probability': round(live_btts, 1),
            'confidence': confidence,
            'recommendation': recommendation,
            'factors': {
                'base': base_btts,
                'time_factor': time_factor,
                'score_adj': score_adjustment,
                'stats_boost': stats_boost
            }
        }
    
    def calculate_time_factor(self, minute: int, home_score: int, 
                             away_score: int) -> float:
        """
        Calculate time-based factor for BTTS probability
        More time = higher probability
        """
        # If already BTTS, return high factor
        if home_score > 0 and away_score > 0:
            return 1.0
        
        # Time remaining
        time_left = 90 - minute
        
        if time_left >= 60:
            return 1.05  # Lots of time
        elif time_left >= 45:
            return 1.03
        elif time_left >= 30:
            return 1.0
        elif time_left >= 15:
            return 0.95
        else:
            return 0.85  # Running out of time
    
    def calculate_score_adjustment(self, minute: int, 
                                   home_score: int, away_score: int) -> float:
        """
        Adjust BTTS probability based on current score
        """
        # Already BTTS - probability is 100% (for live betting "will BTTS happen")
        # But we're looking at "total BTTS" market
        if home_score > 0 and away_score > 0:
            return 20  # Big boost - already happened!
        
        # 0-0 - both need to score
        if home_score == 0 and away_score == 0:
            if minute < 30:
                return 0  # Neutral, early game
            elif minute < 60:
                return -5  # Some pressure
            else:
                return -10  # Time running out
        
        # 1-0 or 0-1 - one team needs to score
        if (home_score == 1 and away_score == 0) or (home_score == 0 and away_score == 1):
            if minute < 45:
                return 5  # Good chance
            elif minute < 70:
                return 0
            else:
                return -5  # Time pressure
        
        # High scoring game - both likely to score
        if home_score + away_score >= 3:
            return 10
        
        return 0
    
    def calculate_confidence(self, minute: int, stats: Optional[Dict]) -> str:
        """
        Calculate confidence level for the prediction
        """
        confidence_score = 0
        
        # More match time = more confidence
        if minute >= 30:
            confidence_score += 30
        if minute >= 45:
            confidence_score += 20
        
        # Stats available = more confidence
        if stats and stats.get('xg_home'):
            confidence_score += 30
        
        if confidence_score >= 70:
            return "HIGH"
        elif confidence_score >= 40:
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_recommendation(self, btts_prob: float, confidence: str, 
                          minute: int) -> str:
        """
        Get betting recommendation based on probability and confidence
        """
        if btts_prob >= 85 and confidence == "HIGH" and minute < 70:
            return "🔥 STRONG BET"
        elif btts_prob >= 80 and confidence in ["HIGH", "MEDIUM"]:
            return "✅ GOOD BET"
        elif btts_prob >= 75:
            return "⚠️ CONSIDER"
        else:
            return "❌ SKIP"


def display_live_opportunity(match: Dict):
    """
    Display a live match opportunity card
    """
    # Recommendation color
    rec_colors = {
        "🔥 STRONG BET": "success",
        "✅ GOOD BET": "success", 
        "⚠️ CONSIDER": "warning",
        "❌ SKIP": "error"
    }
    
    color = rec_colors.get(match['recommendation'], "info")
    
    with st.container():
        # Card border
        if match['recommendation'] in ["🔥 STRONG BET", "✅ GOOD BET"]:
            st.markdown("---")
            st.markdown(f"### 🔴 LIVE - {match['minute']}'")
        
        # Match header
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.subheader(f"{match['home_team']} vs {match['away_team']}")
            st.caption(f"{match['league']} | Score: {match['score']}")
        
        with col2:
            if match['btts_prob'] >= 85:
                st.metric("BTTS", f"{match['btts_prob']}%", delta="🔥")
            else:
                st.metric("BTTS", f"{match['btts_prob']}%")
        
        with col3:
            st.metric("Confidence", match['confidence'])
        
        # Stats row
        if match['stats']:
            col1, col2, col3, col4 = st.columns(4)
            
            stats = match['stats']
            
            with col1:
                if stats.get('shots_home'):
                    st.metric("Shots", 
                             f"{stats['shots_home']}-{stats['shots_away']}")
            
            with col2:
                if stats.get('xg_home'):
                    st.metric("xG", 
                             f"{stats['xg_home']:.1f}-{stats['xg_away']:.1f}")
            
            with col3:
                if stats.get('shots_on_target_home'):
                    st.metric("On Target", 
                             f"{stats['shots_on_target_home']}-{stats['shots_on_target_away']}")
            
            with col4:
                st.metric("Minute", f"{match['minute']}'")
        
        # Recommendation
        if match['recommendation'] in ["🔥 STRONG BET", "✅ GOOD BET"]:
            st.success(f"**{match['recommendation']}**")
        elif match['recommendation'] == "⚠️ CONSIDER":
            st.warning(f"**{match['recommendation']}**")
        else:
            st.info(f"**{match['recommendation']}**")
        
        # Action button
        if match['recommendation'] in ["🔥 STRONG BET", "✅ GOOD BET"]:
            fortune_url = f"https://www.fortuneplay.com/de/sports"
            st.link_button(
                "🎯 BET NOW ON FORTUNEPLAY",
                fortune_url,
                type="primary"
            )
        
        st.markdown("---")
