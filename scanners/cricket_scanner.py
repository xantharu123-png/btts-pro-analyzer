"""
CRICKET LIVE OBSERVATION SCANNER
API observations are displayed without manufacturing betting probabilities.

Features:
- Real Cricbuzz API Integration
- Live Match Scanning
- Innings state and exact run-rate calculation

APIs:
- Cricbuzz API (primary)
- Cricinfo backup

No ROI claim is made without historical market prices and settlement data.

Author: Miroslav
Date: January 2026
"""

import streamlit as st
import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from config_loader import load_app_config

logger = logging.getLogger(__name__)

class CricketScanner:
    """
    Real Cricket Scanner - IPL/T20/ODI
    Uses actual APIs and real-time data
    """
    
    def __init__(self):
        # Cricbuzz unofficial API endpoints
        self.cricbuzz_base = "https://cricbuzz-cricket.p.rapidapi.com"
        
        config = load_app_config(st)
        self.rapidapi_key = config.rapidapi_key
        self.cricket_api_key = config.cricket_api_key
        self.headers = {
            'X-RapidAPI-Key': self.rapidapi_key or '',
            'X-RapidAPI-Host': 'cricbuzz-cricket.p.rapidapi.com'
        }
        
        # Alternative: Public endpoints (may be rate limited)
        self.public_api = "https://api.cricapi.com/v1"
    
    def get_live_matches(self) -> List[Dict]:
        """
        Get real-time cricket matches
        """
        if not self.rapidapi_key and not self.cricket_api_key:
            return []
        try:
            if self.rapidapi_key:
                url = f"{self.cricbuzz_base}/matches/v1/live"
                response = requests.get(url, headers=self.headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    matches = data.get('typeMatches', [])

                    live_matches = []
                    for match_type in matches:
                        for series in match_type.get('seriesMatches', []):
                            wrapper = series.get('seriesAdWrapper') or {}
                            for match in wrapper.get('matches', []):
                                if match.get('matchInfo', {}).get('state') == 'In Progress':
                                    parsed = self._parse_match(match)
                                    if parsed:
                                        live_matches.append(parsed)

                    return live_matches
            return self._get_matches_alternative()
                
        except Exception as e:
            logger.warning("Cricket live request failed: %s", type(e).__name__)
            return []
    
    def _get_matches_alternative(self) -> List[Dict]:
        """
        Alternative method using public cricket API
        """
        try:
            # This would require API key from cricapi.com
            url = f"{self.public_api}/currentMatches"
            if not self.cricket_api_key:
                return []
            params = {'apikey': self.cricket_api_key, 'offset': 0}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                matches = data.get('data', [])
                
                live_matches = []
                for match in matches:
                    if match.get('matchStarted') and not match.get('matchEnded'):
                        parsed = self._parse_match_alternative(match)
                        if parsed:
                            live_matches.append(parsed)
                
                return live_matches
            
            return []
        except requests.RequestException:
            return []
    
    def _parse_match(self, match: Dict) -> Optional[Dict]:
        """Parse Cricbuzz match data"""
        try:
            match_info = match.get('matchInfo', {})
            match_score = match.get('matchScore', {})
            
            # Get detailed scores
            team1_innings = match_score.get('team1Score', {}).get('inngs1', {})
            team2_innings = match_score.get('team2Score', {}).get('inngs1', {})
            
            return {
                'match_id': match_info.get('matchId'),
                'format': match_info.get('matchFormat', 'T20'),
                'tournament': match_info.get('seriesName', 'Unknown'),
                'team1': match_info.get('team1', {}).get('teamName', 'Team 1'),
                'team2': match_info.get('team2', {}).get('teamName', 'Team 2'),
                'team1_score': team1_innings.get('runs'),
                'team1_wickets': team1_innings.get('wickets'),
                'team1_overs': team1_innings.get('overs'),
                'team2_score': team2_innings.get('runs'),
                'team2_wickets': team2_innings.get('wickets'),
                'team2_overs': team2_innings.get('overs'),
                'batting_team': self._determine_batting_team(match_score),
                'current_over': self._get_current_over(match_score),
                'run_rate': self._calculate_run_rate(match_score),
                'status': match_info.get('status', 'Live')
            }
        except Exception as e:
            logger.warning("Cricket match payload rejected: %s", type(e).__name__)
            return None
    
    def _parse_match_alternative(self, match: Dict) -> Optional[Dict]:
        """Parse alternative API match data"""
        # Simpler parsing for alternative API
        return {
            'match_id': match.get('id'),
            'format': match.get('matchType', 'T20'),
            'tournament': match.get('name', 'Unknown'),
            'team1': match.get('teams', ['Team 1', 'Team 2'])[0] if len(match.get('teams', [])) > 0 else 'Team 1',
            'team2': match.get('teams', ['Team 1', 'Team 2'])[1] if len(match.get('teams', [])) > 1 else 'Team 2',
            'status': 'Live'
        }
    
    def _determine_batting_team(self, match_score: Dict) -> str:
        """Determine which team is currently batting"""
        team2 = match_score.get('team2Score', {}).get('inngs1', {})
        return 'team2' if team2 and team2.get('overs') is not None else 'team1'
    
    def _get_current_over(self, match_score: Dict) -> Optional[float]:
        """Get current over being bowled"""
        batting_team = self._determine_batting_team(match_score)
        score_key = 'team2Score' if batting_team == 'team2' else 'team1Score'
        innings = match_score.get(score_key, {}).get('inngs1', {})
        try:
            value = innings.get('overs')
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    def _calculate_run_rate(self, match_score: Dict) -> Optional[float]:
        """Calculate current run rate"""
        batting_team = self._determine_batting_team(match_score)
        score_key = 'team2Score' if batting_team == 'team2' else 'team1Score'
        innings = match_score.get(score_key, {}).get('inngs1', {})
        try:
            runs_value = innings.get('runs')
            overs_value = innings.get('overs')
            if runs_value is None or overs_value is None:
                return None
            runs = float(runs_value)
            overs = float(overs_value)
        except (TypeError, ValueError):
            return None

        completed_overs = int(overs)
        balls_in_over = int(round((overs - completed_overs) * 10))
        if balls_in_over < 0 or balls_in_over > 5:
            return None
        balls = completed_overs * 6 + balls_in_over
        return round(runs * 6 / balls, 2) if balls > 0 else None
    
    def analyze_current_over(self, match: Dict) -> Optional[Dict]:
        """No next-over signal is emitted without ball-level batter/bowler inputs."""
        return None
    
    def analyze_total_runs(self, match: Dict) -> Optional[Dict]:
        """No innings-total signal is emitted from run rate alone."""
        return None


def create_cricket_tab():
    """
    Main Cricket Tab Creator
    API-backed live observations.
    """
    st.header("🏏 CRICKET LIVE SCANNER")
    st.markdown("### IPL/T20/ODI - Real-Time Analysis")
    
    scanner = CricketScanner()
    
    # Scan for live matches
    with st.spinner("🔍 Scanning for live cricket matches..."):
        matches = scanner.get_live_matches()
    
    if not matches:
        st.warning("⚠️ No live cricket matches at this moment")
        if not scanner.rapidapi_key and not scanner.cricket_api_key:
            st.info("Configure `RAPIDAPI_KEY` or `CRICKET_API_KEY` to load matches.")
        return
    
    st.success(f"✅ Found {len(matches)} live cricket match(es)!")
    
    # Analyze each match
    for match in matches:
        analyze_and_display_match(match, scanner)


def analyze_and_display_match(match: Dict, scanner: CricketScanner):
    """
    Analyze and display a single cricket match
    """
    team1 = match['team1']
    team2 = match['team2']
    
    with st.expander(
        f"🏏 {team1} vs {team2} - {match.get('tournament', 'T20')}",
        expanded=True
    ):
        # Match Info
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Format", match.get('format', 'T20'))
        
        batting_team = match.get('batting_team')
        score_prefix = 'team2' if batting_team == 'team2' else 'team1'
        runs = match.get(f'{score_prefix}_score')
        wickets = match.get(f'{score_prefix}_wickets')
        overs = match.get(f'{score_prefix}_overs')

        with col2:
            score = f"{runs}/{wickets}" if runs is not None and wickets is not None else "n/a"
            st.metric("Current Score", score)
        
        with col3:
            st.metric("Overs", str(overs) if overs is not None else "n/a")
        
        with col4:
            run_rate = match.get('run_rate')
            st.metric("Run Rate", str(run_rate) if run_rate is not None else "n/a")
        
        st.markdown("---")
        
        st.info(
            "Live observation only. Ball-level batter, bowler, wicket-state, and "
            "out-of-sample calibration are required before a model signal is emitted."
        )


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Cricket Scanner - Real Time",
        page_icon="🏏",
        layout="wide"
    )
    
    st.title("🏏 Cricket Scanner - Real-Time Analysis")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    create_cricket_tab()
