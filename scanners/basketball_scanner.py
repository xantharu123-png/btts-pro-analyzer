"""
BASKETBALL & NHL LIVE OBSERVATION SCANNER
API observations are real; no betting probability is inferred from score alone.

Features:
- Real NBA API Integration (stats.nba.com)
- Real Euroleague API Integration
- Real NHL API Integration (api-web.nhle.com)
- Live scores and clock-aware straight-line scoring projections

Author: Miroslav
Date: January 2026
"""

import streamlit as st
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import re
import math

logger = logging.getLogger(__name__)

class BasketballScanner:
    """
    Real Basketball + NHL Scanner - NBA + Euroleague + NHL
    Uses actual APIs and real-time data
    """
    
    def __init__(self):
        self.errors: Dict[str, str] = {}
        # NBA Stats API
        self.nba_api_base = "https://stats.nba.com/stats"
        self.nba_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'x-nba-stats-origin': 'stats',
            'x-nba-stats-token': 'true',
            'Referer': 'https://stats.nba.com/',
        }
        
        # Euroleague API
        self.euroleague_api_base = "https://live.euroleague.net/api"
        
        # Alternative: NBA.com live scoreboard
        self.nba_live_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        
        # NHL API
        self.nhl_api_url = "https://api-web.nhle.com/v1/scoreboard/now"
    
    def get_live_nhl_games(self) -> List[Dict]:
        """Get real-time NHL games"""
        try:
            response = requests.get(
                self.nhl_api_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, dict):
                    self.errors['nhl'] = 'Invalid provider payload'
                    logger.warning("NHL live API returned an invalid payload")
                    return []
                date_groups = data.get('gamesByDate', [])
                if not isinstance(date_groups, list):
                    self.errors['nhl'] = 'Invalid games list'
                    return []
                live_games = []
                
                # NHL API returns games grouped by date
                for date_group in date_groups:
                    games = date_group.get('games', []) if isinstance(date_group, dict) else []
                    if not isinstance(games, list):
                        continue
                    for game in games:
                        if not isinstance(game, dict):
                            continue
                        # LIVE, CRIT (critical/close game), or in progress
                        if game.get('gameState') in ['LIVE', 'CRIT']:
                            parsed = self._parse_nhl_game(game)
                            if parsed:
                                live_games.append(parsed)
                
                return live_games
            logger.warning("NHL live API returned HTTP %s", response.status_code)
            self.errors['nhl'] = f"HTTP {response.status_code}"
            return []
                
        except (requests.RequestException, ValueError) as exc:
            self.errors['nhl'] = type(exc).__name__
            logger.warning("NHL live data request failed: %s", type(exc).__name__)
            return []
    
    def _parse_nhl_game(self, game: Dict) -> Optional[Dict]:
        """Parse NHL game data into our format"""
        if not isinstance(game, dict):
            return None
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        home_score = home.get('score')
        away_score = away.get('score')
        period = game.get('period')
        clock = game.get('clock')
        if (
            isinstance(home_score, bool)
            or isinstance(away_score, bool)
            or not isinstance(home_score, (int, float))
            or not isinstance(away_score, (int, float))
            or not math.isfinite(float(home_score))
            or not math.isfinite(float(away_score))
            or float(home_score) < 0
            or float(away_score) < 0
            or not float(home_score).is_integer()
            or not float(away_score).is_integer()
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, dict)
            or not isinstance(clock.get('timeRemaining'), str)
        ):
            return None
        
        return {
            'league': 'NHL',
            'game_id': game.get('id'),
            'home_team': home.get('abbrev', 'HOME'),
            'away_team': away.get('abbrev', 'AWAY'),
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock['timeRemaining'],
            'game_status': game.get('gameState', 'Live'),
            'venue': game.get('venue', {}).get('default', 'Unknown')
        }
    
    def analyze_nhl_game(self, game: Dict) -> Optional[Dict]:
        """No NHL signal is emitted without team-strength and goalie inputs."""
        return None
        
    def get_live_nba_games(self) -> List[Dict]:
        """
        Get real-time NBA games
        Uses NBA.com live scoreboard API
        """
        try:
            response = requests.get(self.nba_live_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, dict):
                    self.errors['nba'] = 'Invalid provider payload'
                    logger.warning("NBA live API returned an invalid payload")
                    return []
                games = data.get('scoreboard', {}).get('games', [])
                if not isinstance(games, list):
                    self.errors['nba'] = 'Invalid games list'
                    return []
                
                live_games = []
                for game in games:
                    if not isinstance(game, dict):
                        continue
                    if game.get('gameStatus') == 2:  # 2 = Live
                        parsed = self._parse_nba_game(game)
                        if parsed:
                            live_games.append(parsed)
                
                return live_games
            else:
                logger.warning("NBA live API returned HTTP %s", response.status_code)
                self.errors['nba'] = f"HTTP {response.status_code}"
                return []
                
        except (requests.RequestException, ValueError) as exc:
            self.errors['nba'] = type(exc).__name__
            logger.warning("NBA live data request failed: %s", type(exc).__name__)
            return []
    
    def _parse_nba_game(self, game: Dict) -> Optional[Dict]:
        """Parse NBA game data into our format"""
        if not isinstance(game, dict):
            return None
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        home_score = home.get('score')
        away_score = away.get('score')
        period = game.get('period')
        clock = game.get('gameClock')
        if (
            isinstance(home_score, bool)
            or isinstance(away_score, bool)
            or not isinstance(home_score, (int, float))
            or not isinstance(away_score, (int, float))
            or not math.isfinite(float(home_score))
            or not math.isfinite(float(away_score))
            or float(home_score) < 0
            or float(away_score) < 0
            or not float(home_score).is_integer()
            or not float(away_score).is_integer()
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, str)
        ):
            return None
        
        return {
            'league': 'NBA',
            'game_id': game.get('gameId'),
            'home_team': home.get('teamTricode', 'HOME'),
            'away_team': away.get('teamTricode', 'AWAY'),
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock,
            'game_status': game.get('gameStatusText', 'Live'),
            'home_stats': home.get('statistics', {}),
            'away_stats': away.get('statistics', {}),
        }
    
    def get_live_euroleague_games(self) -> List[Dict]:
        """
        Get real-time Euroleague games
        """
        try:
            # Euroleague Live endpoint
            url = f"{self.euroleague_api_base}/Games"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if not isinstance(data, list):
                    self.errors['euroleague'] = 'Invalid provider payload'
                    logger.warning("Euroleague live API returned an invalid payload")
                    return []
                
                live_games = []
                for game in data:
                    if not isinstance(game, dict):
                        continue
                    if game.get('Live', False):
                        parsed = self._parse_euroleague_game(game)
                        if parsed:
                            live_games.append(parsed)
                
                return live_games
            logger.warning("Euroleague live API returned HTTP %s", response.status_code)
            self.errors['euroleague'] = f"HTTP {response.status_code}"
            return []
                
        except (requests.RequestException, ValueError) as exc:
            self.errors['euroleague'] = type(exc).__name__
            logger.warning("Euroleague live data request failed: %s", type(exc).__name__)
            return []
    
    def _parse_euroleague_game(self, game: Dict) -> Optional[Dict]:
        """Parse Euroleague game data"""
        if not isinstance(game, dict):
            return None
        home_score = game.get('HomeScore')
        away_score = game.get('AwayScore')
        period = game.get('Quarter')
        clock = game.get('Clock')
        if (
            isinstance(home_score, bool)
            or isinstance(away_score, bool)
            or not isinstance(home_score, (int, float))
            or not isinstance(away_score, (int, float))
            or not math.isfinite(float(home_score))
            or not math.isfinite(float(away_score))
            or float(home_score) < 0
            or float(away_score) < 0
            or not float(home_score).is_integer()
            or not float(away_score).is_integer()
            or isinstance(period, bool)
            or not isinstance(period, int)
            or period < 1
            or not isinstance(clock, str)
        ):
            return None
        return {
            'league': 'Euroleague',
            'game_id': game.get('GameCode'),
            'home_team': game.get('HomeTeam', {}).get('Name', 'HOME'),
            'away_team': game.get('AwayTeam', {}).get('Name', 'AWAY'),
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'game_clock': clock,
            'game_status': 'Live',
        }
    
    def scan_live_games(self, league: str = "All") -> List[Dict]:
        """
        Scan for all live games based on league selection
        
        Args:
            league: "NBA", "Euroleague", or "All"
        """
        all_games = []
        
        if league in ["NBA", "All"]:
            nba_games = self.get_live_nba_games()
            all_games.extend(nba_games)
        
        if league in ["Euroleague", "All"]:
            euroleague_games = self.get_live_euroleague_games()
            all_games.extend(euroleague_games)
        
        return all_games
    
    @staticmethod
    def _clock_minutes_remaining(clock) -> Optional[float]:
        if not isinstance(clock, str):
            return None
        iso_match = re.fullmatch(r"PT(?:(\d+)M)?([\d.]+)S", clock)
        if iso_match:
            try:
                minutes = int(iso_match.group(1) or 0)
                seconds = float(iso_match.group(2))
            except ValueError:
                return None
            if not math.isfinite(seconds) or not 0 <= seconds < 60:
                return None
            return minutes + seconds / 60.0
        plain_match = re.fullmatch(r"(\d+):(\d{2})", clock)
        if plain_match:
            seconds = int(plain_match.group(2))
            if seconds > 59:
                return None
            return int(plain_match.group(1)) + seconds / 60.0
        return None

    def calculate_scoring_projection(self, game: Dict) -> Optional[float]:
        """Straight-line projection from score and actual game clock."""
        league = game.get('league')
        if league not in {'NBA', 'Euroleague'}:
            return None
        try:
            period = int(game.get('period'))
            home_score = float(game.get('home_score'))
            away_score = float(game.get('away_score'))
            total_score = home_score + away_score
        except (TypeError, ValueError):
            return None
        if (
            isinstance(game.get('period'), bool)
            or isinstance(game.get('home_score'), bool)
            or isinstance(game.get('away_score'), bool)
            or not math.isfinite(home_score)
            or not math.isfinite(away_score)
            or not math.isfinite(total_score)
            or home_score < 0
            or away_score < 0
            or not home_score.is_integer()
            or not away_score.is_integer()
            or total_score < 0
            or period < 1
            or period > 4
        ):
            return None

        period_minutes = 12 if league == 'NBA' else 10
        remaining = self._clock_minutes_remaining(game.get('game_clock'))
        if remaining is None or not 0 <= remaining <= period_minutes:
            return None
        elapsed = (period - 1) * period_minutes + (period_minutes - remaining)
        regulation_minutes = period_minutes * 4
        if elapsed < 2:
            return None
        return round(total_score / elapsed * regulation_minutes, 1)
    
    def analyze_quarter_winner(self, game: Dict) -> Optional[Dict]:
        """No quarter-winner signal is emitted from score differential alone."""
        return None
    
    def analyze_total_points(self, game: Dict) -> Optional[Dict]:
        """No totals signal is emitted without a validated scoring model and line."""
        return None
    
    def analyze_player_props(self, game: Dict) -> List[Dict]:
        """No player output is emitted without detailed player statistics."""
        return []


def create_basketball_tab(league: str = "All"):
    """
    Main Basketball Tab Creator
    API-backed live observations.
    """
    st.header("🏀 BASKETBALL LIVE SCANNER")
    st.markdown(f"### {league} - Real-Time Analysis")
    
    scanner = BasketballScanner()
    
    # Scan for live games
    with st.spinner(f"🔍 Scanning for live {league} games..."):
        games = scanner.scan_live_games(league)
    
    if not games:
        st.warning(f"⚠️ No live {league} games at this moment")
        return
    
    st.success(f"✅ Found {len(games)} live {league} game(s)!")
    
    # Analyze each game
    for game in games:
        analyze_and_display_game(game, scanner)


def analyze_and_display_game(game: Dict, scanner: BasketballScanner):
    """Display one live game and its clock-aware score projection."""
    home = game['home_team']
    away = game['away_team']
    period = game.get('period', 1)
    clock = game.get('game_clock', '12:00')
    
    with st.expander(
        f"🏀 {home} vs {away} - Q{period} {clock} [{game['home_score']}-{game['away_score']}]",
        expanded=True
    ):
        # Game Info
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("League", game['league'])
        
        with col2:
            score_diff = abs(game['home_score'] - game['away_score'])
            leader = home if game['home_score'] > game['away_score'] else away
            st.metric("Score", f"{game['home_score']}-{game['away_score']}", 
                     f"{leader} +{score_diff}")
        
        with col3:
            projection = scanner.calculate_scoring_projection(game)
            st.metric(
                "Straight-line total",
                f"{projection:.1f}" if projection is not None else "n/a",
            )
        
        with col4:
            st.metric("Period", f"Q{period}", clock)
        
        st.markdown("---")
        
        st.info(
            "Live observation only. Team-strength, possession, lineup, and "
            "out-of-sample calibration are required before a model signal is emitted."
        )


# For standalone testing
if __name__ == "__main__":
    st.set_page_config(
        page_title="Basketball Scanner - Real Time",
        page_icon="🏀",
        layout="wide"
    )
    
    st.title("🏀 Basketball Scanner - Real-Time Analysis")
    
    league = st.radio(
        "Select League:",
        ["NBA", "Euroleague", "All"],
        horizontal=True
    )
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()
    
    create_basketball_tab(league)
