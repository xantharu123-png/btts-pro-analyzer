"""
TENNIS LIVE OBSERVATION SCANNER
API observations are displayed without manufacturing betting probabilities.

Features:
- Real Sofascore API Integration
- Live Match Scanning
- Live set, phase, and point scores

APIs:
- Sofascore API (primary)
- ESPN scoreboard fallback

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
        sofascore_error = None
        try:
            url = f"{self.sofascore_base}/sport/tennis/events/live"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and isinstance(data.get('events', []), list):
                    live_matches = []
                    for event in data.get('events', []):
                        if not isinstance(event, dict):
                            continue
                        status = event.get('status', {})
                        if isinstance(status, dict) and status.get('type') == 'inprogress':
                            match = self._parse_match(event)
                            if match:
                                match['source'] = 'SofaScore'
                                live_matches.append(match)
                    return live_matches
                sofascore_error = 'Invalid provider payload'
            else:
                sofascore_error = f"HTTP {response.status_code}"
        except (requests.RequestException, ValueError) as exc:
            sofascore_error = type(exc).__name__

        fallback = self._get_espn_live_matches()
        if fallback is not None:
            return fallback
        self.last_error = f"SofaScore {sofascore_error or 'unavailable'}; ESPN unavailable"
        logger.info("Tennis live providers did not return a usable response")
        return []

    def _get_espn_live_matches(self) -> Optional[List[Dict]]:
        """Use ESPN's public ATP/WTA scoreboards when SofaScore blocks the host."""
        matches = []
        errors = []
        successful_feeds = 0
        for tour in ('atp', 'wta'):
            url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    errors.append(f"{tour.upper()} HTTP {response.status_code}")
                    continue
                data = response.json()
                events = data.get('events', []) if isinstance(data, dict) else None
                if not isinstance(events, list):
                    errors.append(f"{tour.upper()} invalid payload")
                    continue
                successful_feeds += 1
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    for grouping in event.get('groupings', []):
                        if not isinstance(grouping, dict):
                            continue
                        competitions = grouping.get('competitions', [])
                        if not isinstance(competitions, list):
                            continue
                        for competition in competitions:
                            parsed = self._parse_espn_match(event, competition)
                            if parsed:
                                matches.append(parsed)
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{tour.upper()} {type(exc).__name__}")

        if successful_feeds == 0:
            return None
        self.last_error = '; '.join(errors) if errors else None
        return matches

    def _parse_espn_match(self, event: Dict, competition: Dict) -> Optional[Dict]:
        """Parse one in-progress ESPN tennis competition without inventing point data."""
        if not isinstance(event, dict) or not isinstance(competition, dict):
            return None
        status = competition.get('status', {})
        status_type = status.get('type', {}) if isinstance(status, dict) else {}
        if not isinstance(status_type, dict) or status_type.get('state') != 'in':
            return None
        competitors = competition.get('competitors', [])
        if not isinstance(competitors, list) or len(competitors) != 2:
            return None
        by_side = {
            item.get('homeAway'): item
            for item in competitors
            if isinstance(item, dict) and item.get('homeAway') in {'home', 'away'}
        }
        home = by_side.get('home')
        away = by_side.get('away')
        if not isinstance(home, dict) or not isinstance(away, dict):
            return None

        def competitor_name(item: Dict) -> str:
            athlete = item.get('athlete', {})
            return (
                str(athlete.get('displayName') or '').strip()
                if isinstance(athlete, dict)
                else ''
            )

        def won_sets(item: Dict) -> Optional[int]:
            linescores = item.get('linescores', [])
            if not isinstance(linescores, list):
                return None
            return sum(
                1
                for score in linescores
                if isinstance(score, dict) and score.get('winner') is True
            )

        player1 = competitor_name(home)
        player2 = competitor_name(away)
        score1 = won_sets(home)
        score2 = won_sets(away)
        match_id = competition.get('id')
        if (
            not player1
            or not player2
            or player1.casefold() == player2.casefold()
            or score1 is None
            or score2 is None
            or isinstance(match_id, bool)
            or not isinstance(match_id, (int, str))
            or not str(match_id).strip()
        ):
            return None

        period = status.get('period')
        if isinstance(period, bool) or not isinstance(period, int) or period < 1:
            period = None
        phase = str(
            status_type.get('detail')
            or status_type.get('description')
            or 'Live'
        ).strip() or 'Live'
        tournament = str(event.get('name') or 'ATP/WTA').strip() or 'ATP/WTA'
        return {
            'match_id': match_id,
            'tournament': tournament,
            'surface': 'Unknown',
            'player1': player1,
            'player2': player2,
            'player1_score': score1,
            'player2_score': score2,
            'current_set': period,
            'point_score': None,
            'server': None,
            'serve_stats': {},
            'status': phase,
            'source': 'ESPN',
        }
    
    def _parse_match(self, event: Dict) -> Optional[Dict]:
        """Parse Sofascore match data"""
        try:
            if not isinstance(event, dict):
                return None
            home_team = event.get('homeTeam', {})
            away_team = event.get('awayTeam', {})
            home_score = event.get('homeScore', {})
            away_score = event.get('awayScore', {})
            status = event.get('status', {})
            tournament = event.get('tournament', {})
            if not all(
                isinstance(value, dict)
                for value in (home_team, away_team, home_score, away_score, status, tournament)
            ):
                return None
            match_id = event.get('id')
            player1 = str(home_team.get('name') or '').strip()
            player2 = str(away_team.get('name') or '').strip()
            score1 = home_score.get('current')
            score2 = away_score.get('current')
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

            phase = str(status.get('description') or 'Live').strip() or 'Live'
            current_period = event.get('lastPeriod') or status.get('period')
            point_score = self._format_point_score(
                home_score.get('point'),
                away_score.get('point'),
            )
            tournament_name = str(tournament.get('name') or 'Unknown').strip() or 'Unknown'
            surface = str(event.get('groundType') or 'Unknown').strip() or 'Unknown'
            
            return {
                'match_id': match_id,
                'tournament': tournament_name,
                'surface': surface,
                'player1': player1,
                'player2': player2,
                'player1_score': int(score1),
                'player2_score': int(score2),
                'current_set': current_period,
                'point_score': point_score,
                'server': self._determine_server(event),
                'serve_stats': {},
                'status': phase,
            }
        except Exception as e:
            logger.warning("Tennis match payload rejected: %s", type(e).__name__)
            return None

    @staticmethod
    def _format_point_score(home_point, away_point) -> Optional[str]:
        """Return only recognisable tennis point values from the live payload."""
        formatted = []
        for value in (home_point, away_point):
            if isinstance(value, bool) or value is None:
                return None
            text = str(value).strip().upper()
            if not text or not (text.isdigit() or text in {'A', 'AD'}):
                return None
            formatted.append(text)
        return f"{formatted[0]}-{formatted[1]}"
    
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
