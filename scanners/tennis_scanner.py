"""
TENNIS LIVE OBSERVATION SCANNER
API observations are displayed without manufacturing betting probabilities.

Features:
- Real Sofascore API Integration
- Live Match Scanning
- Live scores and available serve statistics

APIs:
- Sofascore API (primary)
- Flashscore backup

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

logger = logging.getLogger(__name__)

class TennisScanner:
    """
    Real Tennis Scanner - ATP/WTA
    Uses actual APIs and real-time data
    """
    
    def __init__(self):
        # Sofascore API
        self.sofascore_base = "https://api.sofascore.com/api/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.sofascore.com/',
            'Origin': 'https://www.sofascore.com'
        }
    
    def get_live_matches(self) -> List[Dict]:
        """
        Get real-time tennis matches from Sofascore
        Note: Sofascore may block cloud server IPs (works locally)
        """
        try:
            # Sofascore live tennis endpoint
            url = f"{self.sofascore_base}/sport/tennis/events/live"
            
            # Try with different headers
            headers_options = [
                self.headers,
                {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': '*/*',
                },
                {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
            ]
            
            for headers in headers_options:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        events = data.get('events', [])
                        
                        live_matches = []
                        for event in events:
                            status = event.get('status', {})
                            if status.get('type') == 'inprogress':
                                match = self._parse_match(event)
                                if match:
                                    live_matches.append(match)
                        
                        if live_matches:
                            return live_matches
                    elif response.status_code == 403:
                        continue  # Try next headers
                except requests.RequestException:
                    continue
            
            # All attempts failed
            logger.info("Tennis live provider did not return a usable response")
            return []
                
        except Exception as e:
            logger.warning("Tennis live request failed: %s", type(e).__name__)
            return []
    
    def _parse_match(self, event: Dict) -> Optional[Dict]:
        """Parse Sofascore match data"""
        try:
            home_team = event.get('homeTeam', {})
            away_team = event.get('awayTeam', {})
            
            # Get serve stats if available
            match_id = event.get('id')
            serve_stats = self._get_serve_stats(match_id)
            
            return {
                'match_id': match_id,
                'tournament': event.get('tournament', {}).get('name', 'Unknown'),
                'surface': event.get('groundType', 'Hard'),
                'player1': home_team.get('name', 'Player 1'),
                'player2': away_team.get('name', 'Player 2'),
                'player1_score': event.get('homeScore', {}).get('current'),
                'player2_score': event.get('awayScore', {}).get('current'),
                'current_set': event.get('homeScore', {}).get('current', 0),
                'server': self._determine_server(event),
                'serve_stats': serve_stats,
                'status': event.get('status', {}).get('description', 'Live')
            }
        except Exception as e:
            logger.warning("Tennis match payload rejected: %s", type(e).__name__)
            return None
    
    def _get_serve_stats(self, match_id: int) -> Dict:
        """
        Get detailed serve statistics for a match
        """
        try:
            url = f"{self.sofascore_base}/event/{match_id}/statistics"
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                stats = data.get('statistics', [])
                
                # Extract serve stats
                serve_data = {}
                for period in stats:
                    for group in period.get('groups', []):
                        for item in group.get('statisticsItems', []):
                            name = item.get('name', '')
                            if 'serve' in name.lower() or 'ace' in name.lower():
                                serve_data[name] = {
                                    'home': item.get('home'),
                                    'away': item.get('away')
                                }
                
                return serve_data
            
            return {}
        except requests.RequestException:
            return {}
    
    def _determine_server(self, event: Dict) -> Optional[str]:
        """Return a server only when the upstream event identifies one."""
        serving = event.get('serving')
        if serving == 1:
            return 'player1'
        if serving == 2:
            return 'player2'
        return None
    
    def analyze_next_game(self, match: Dict) -> Optional[Dict]:
        """No game probability is emitted without point-level serve/return inputs."""
        return None
    
    def analyze_set_winner(self, match: Dict) -> Optional[Dict]:
        """No set probability is emitted from score differential alone."""
        return None
    
    def analyze_total_games(self, match: Dict) -> Optional[Dict]:
        """No totals signal is emitted without a validated point-level model."""
        return None


def create_tennis_tab():
    """
    Main Tennis Tab Creator
    API-backed observations with explicitly heuristic model signals.
    """
    st.header("🎾 TENNIS LIVE SCANNER")
    st.markdown("### ATP/WTA - Real-Time Analysis")
    
    scanner = TennisScanner()
    
    # Scan for live matches
    with st.spinner("🔍 Scanning for live tennis matches..."):
        matches = scanner.get_live_matches()
    
    if not matches:
        st.warning("⚠️ No live tennis matches at this moment")
        return
    
    st.success(f"✅ Found {len(matches)} live tennis match(es)!")
    
    # Analyze each match
    for match in matches:
        analyze_and_display_match(match, scanner)


def analyze_and_display_match(match: Dict, scanner: TennisScanner):
    """
    Analyze and display a single tennis match
    """
    player1 = match['player1']
    player2 = match['player2']
    score1 = match.get('player1_score', 0)
    score2 = match.get('player2_score', 0)
    
    with st.expander(
        f"🎾 {player1} vs {player2} [{score1}-{score2}] - {match.get('tournament', 'ATP/WTA')}",
        expanded=True
    ):
        # Match Info
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Tournament", match.get('tournament', 'N/A'))
        
        with col2:
            st.metric("Surface", match.get('surface', 'Hard'))
        
        with col3:
            st.metric("Current Score", f"{score1}-{score2}")
        
        with col4:
            server = match.get('server')
            if server == 'player1':
                serving = player1
            elif server == 'player2':
                serving = player2
            else:
                serving = None
            st.metric("Server", serving.split()[-1] if serving else "n/a")
        
        st.markdown("---")
        
        st.info(
            "Live observation only. Point-level serve and return inputs plus "
            "out-of-sample calibration are required before a model signal is emitted."
        )


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Tennis Scanner - Real Time",
        page_icon="🎾",
        layout="wide"
    )
    
    st.title("🎾 Tennis Scanner - Real-Time Analysis")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    create_tennis_tab()
