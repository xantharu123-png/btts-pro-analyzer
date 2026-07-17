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
import math
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class TennisScanner:
    """
    Real Tennis Scanner - ATP/WTA
    Uses actual APIs and real-time data
    """
    
    def __init__(self):
        self.last_error: Optional[str] = None
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
        self.last_error = None
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
            
            usable_response = False
            last_status = None
            for headers in headers_options:
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if not isinstance(data, dict):
                            self.last_error = "Invalid provider payload"
                            continue
                        usable_response = True
                        events = data.get('events', [])
                        if not isinstance(events, list):
                            self.last_error = "Invalid events payload"
                            continue
                        
                        live_matches = []
                        for event in events:
                            if not isinstance(event, dict):
                                continue
                            status = event.get('status', {})
                            if not isinstance(status, dict):
                                continue
                            if status.get('type') == 'inprogress':
                                match = self._parse_match(event)
                                if match:
                                    live_matches.append(match)
                        
                        return live_matches
                    elif response.status_code == 403:
                        last_status = response.status_code
                        continue  # Try next headers
                    else:
                        last_status = response.status_code
                except (requests.RequestException, ValueError):
                    continue
            
            # All attempts failed
            if not usable_response:
                self.last_error = f"HTTP {last_status}" if last_status else "Provider unavailable"
            logger.info("Tennis live provider did not return a usable response")
            return []
                
        except Exception as e:
            self.last_error = type(e).__name__
            logger.warning("Tennis live request failed: %s", type(e).__name__)
            return []
    
    def _parse_match(self, event: Dict) -> Optional[Dict]:
        """Parse Sofascore match data"""
        try:
            if not isinstance(event, dict):
                return None
            home_team = event.get('homeTeam', {})
            away_team = event.get('awayTeam', {})
            match_id = event.get('id')
            player1 = str(home_team.get('name') or '').strip()
            player2 = str(away_team.get('name') or '').strip()
            score1 = event.get('homeScore', {}).get('current')
            score2 = event.get('awayScore', {}).get('current')
            if (
                not isinstance(match_id, int)
                or isinstance(match_id, bool)
                or match_id <= 0
                or not player1
                or not player2
                or player1 == player2
                or isinstance(score1, bool)
                or isinstance(score2, bool)
                or not isinstance(score1, (int, float))
                or not isinstance(score2, (int, float))
                or not math.isfinite(float(score1))
                or not math.isfinite(float(score2))
                or float(score1) < 0
                or float(score2) < 0
                or not float(score1).is_integer()
                or not float(score2).is_integer()
            ):
                return None
            
            # Get serve stats if available
            serve_stats = self._get_serve_stats(match_id)
            
            return {
                'match_id': match_id,
                'tournament': event.get('tournament', {}).get('name', 'Unknown'),
                'surface': event.get('groundType', 'Hard'),
                'player1': player1,
                'player2': player2,
                'player1_score': score1,
                'player2_score': score2,
                'current_set': event.get('status', {}).get('period'),
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
                if not isinstance(data, dict):
                    return {}
                stats = data.get('statistics', [])
                if not isinstance(stats, list):
                    return {}
                
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
        except (requests.RequestException, ValueError):
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
