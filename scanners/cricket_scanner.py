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
import math
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
        self.last_error: Optional[str] = None
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
        self.last_error = None
        if not self.rapidapi_key and not self.cricket_api_key:
            self.last_error = "Cricket API key missing"
            return []
        try:
            if self.rapidapi_key:
                url = f"{self.cricbuzz_base}/matches/v1/live"
                response = requests.get(url, headers=self.headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if not isinstance(data, dict):
                        self.last_error = "Cricbuzz invalid provider payload"
                        return self._get_matches_alternative() if self.cricket_api_key else []
                    matches = data.get('typeMatches', [])
                    if not isinstance(matches, list):
                        self.last_error = "Cricbuzz invalid matches payload"
                        return self._get_matches_alternative() if self.cricket_api_key else []

                    live_matches = []
                    for match_type in matches:
                        if not isinstance(match_type, dict):
                            continue
                        for series in match_type.get('seriesMatches', []):
                            if not isinstance(series, dict):
                                continue
                            wrapper = series.get('seriesAdWrapper') or {}
                            if not isinstance(wrapper, dict):
                                continue
                            for match in wrapper.get('matches', []):
                                if not isinstance(match, dict):
                                    continue
                                if match.get('matchInfo', {}).get('state') == 'In Progress':
                                    parsed = self._parse_match(match)
                                    if parsed:
                                        live_matches.append(parsed)

                    return live_matches
                self.last_error = f"Cricbuzz HTTP {response.status_code}"
            return self._get_matches_alternative()
                
        except Exception as e:
            self.last_error = type(e).__name__
            logger.warning("Cricket live request failed: %s", type(e).__name__)
            return self._get_matches_alternative() if self.cricket_api_key else []
    
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
                if not isinstance(data, dict):
                    self.last_error = "Cricket API invalid provider payload"
                    return []
                matches = data.get('data', [])
                if not isinstance(matches, list):
                    self.last_error = "Cricket API invalid matches payload"
                    return []
                
                live_matches = []
                for match in matches:
                    if not isinstance(match, dict):
                        continue
                    if match.get('matchStarted') and not match.get('matchEnded'):
                        parsed = self._parse_match_alternative(match)
                        if parsed:
                            live_matches.append(parsed)

                self.last_error = None
                return live_matches
            
            self.last_error = f"Cricket API HTTP {response.status_code}"
            return []
        except (requests.RequestException, ValueError) as exc:
            self.last_error = type(exc).__name__
            return []
    
    def _parse_match(self, match: Dict) -> Optional[Dict]:
        """Parse Cricbuzz match data"""
        try:
            if not isinstance(match, dict):
                return None
            match_info = match.get('matchInfo', {})
            match_score = match.get('matchScore', {})
            if not isinstance(match_info, dict) or not isinstance(match_score, dict):
                return None

            match_id = match_info.get('matchId')
            team1_data = match_info.get('team1', {})
            team2_data = match_info.get('team2', {})
            if (
                not isinstance(match_id, int)
                or isinstance(match_id, bool)
                or match_id <= 0
                or not isinstance(team1_data, dict)
                or not isinstance(team2_data, dict)
            ):
                return None
            team1 = str(team1_data.get('teamName') or '').strip()
            team2 = str(team2_data.get('teamName') or '').strip()
            if not team1 or not team2 or team1.casefold() == team2.casefold():
                return None
            
            team1_innings = self._normalise_innings(
                self._get_innings(match_score, 'team1Score', 'inngs1')
            )
            team2_innings = self._normalise_innings(
                self._get_innings(match_score, 'team2Score', 'inngs1')
            )
            current = self._select_current_innings(match_score)
            batting_team = current.get('team') if current else None
            batting_team_name = (
                team1 if batting_team == 'team1'
                else team2 if batting_team == 'team2'
                else None
            )
            
            return {
                'match_id': match_id,
                'format': str(match_info.get('matchFormat') or 'Unknown').strip() or 'Unknown',
                'tournament': str(match_info.get('seriesName') or 'Unknown').strip() or 'Unknown',
                'team1': team1,
                'team2': team2,
                'team1_score': team1_innings.get('runs'),
                'team1_wickets': team1_innings.get('wickets'),
                'team1_overs': team1_innings.get('overs'),
                'team2_score': team2_innings.get('runs'),
                'team2_wickets': team2_innings.get('wickets'),
                'team2_overs': team2_innings.get('overs'),
                'batting_team': batting_team,
                'batting_team_name': batting_team_name,
                'current_innings': current.get('innings_number') if current else None,
                'current_runs': current.get('runs') if current else None,
                'current_wickets': current.get('wickets') if current else None,
                'current_over': current.get('overs') if current else None,
                'run_rate': self._calculate_run_rate(match_score),
                'status': str(match_info.get('status') or 'Live').strip() or 'Live',
                'source': 'Cricbuzz',
            }
        except Exception as e:
            logger.warning("Cricket match payload rejected: %s", type(e).__name__)
            return None
    
    def _parse_match_alternative(self, match: Dict) -> Optional[Dict]:
        """Parse alternative API match data"""
        if not isinstance(match, dict):
            return None
        teams = match.get('teams')
        if not isinstance(teams, list) or len(teams) < 2:
            return None
        team1 = str(teams[0] or '').strip()
        team2 = str(teams[1] or '').strip()
        match_id = match.get('id')
        if (
            not team1
            or not team2
            or team1.casefold() == team2.casefold()
            or isinstance(match_id, bool)
            or not isinstance(match_id, (int, str))
            or not str(match_id).strip()
            or (isinstance(match_id, int) and match_id <= 0)
        ):
            return None

        current = None
        scores = match.get('score', [])
        if isinstance(scores, list):
            for score in scores:
                if not isinstance(score, dict):
                    continue
                innings = self._normalise_innings({
                    'runs': score.get('r'),
                    'wickets': score.get('w'),
                    'overs': score.get('o'),
                })
                if any(innings.get(key) is not None for key in ('runs', 'wickets', 'overs')):
                    label = str(score.get('inning') or '').strip()
                    current = {**innings, 'label': label or None}

        batting_team = None
        batting_team_name = None
        innings_label = current.get('label') if current else None
        if innings_label:
            folded_label = innings_label.casefold()
            for team_key, team_name in (('team1', team1), ('team2', team2)):
                if team_name.casefold() in folded_label:
                    batting_team = team_key
                    batting_team_name = team_name
                    break

        return {
            'match_id': match_id,
            'format': str(match.get('matchType') or 'Unknown').strip() or 'Unknown',
            'tournament': str(match.get('name') or 'Unknown').strip() or 'Unknown',
            'team1': team1,
            'team2': team2,
            'batting_team': batting_team,
            'batting_team_name': batting_team_name,
            'current_innings': innings_label,
            'current_runs': current.get('runs') if current else None,
            'current_wickets': current.get('wickets') if current else None,
            'current_over': current.get('overs') if current else None,
            'run_rate': self._calculate_run_rate_values(
                current.get('runs') if current else None,
                current.get('overs') if current else None,
            ),
            'status': str(match.get('status') or 'Live').strip() or 'Live',
            'source': 'CricketData',
        }

    @staticmethod
    def _normalise_count(value, maximum: Optional[int] = None) -> Optional[int]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number) or number < 0 or not number.is_integer():
            return None
        result = int(number)
        if maximum is not None and result > maximum:
            return None
        return result

    @staticmethod
    def _overs_to_balls(value) -> Optional[int]:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, float) and not math.isfinite(value):
            return None
        text = str(value).strip()
        parts = text.split('.')
        if len(parts) > 2 or not parts[0].isdigit():
            return None
        completed_overs = int(parts[0])
        if len(parts) == 1:
            balls_in_over = 0
        elif len(parts[1]) == 1 and parts[1].isdigit():
            balls_in_over = int(parts[1])
        elif parts[1] and set(parts[1]) <= {'0'}:
            balls_in_over = 0
        else:
            return None
        if balls_in_over > 5:
            return None
        return completed_overs * 6 + balls_in_over

    @classmethod
    def _normalise_over(cls, value) -> Optional[float]:
        balls = cls._overs_to_balls(value)
        if balls is None:
            return None
        completed_overs, balls_in_over = divmod(balls, 6)
        return float(f"{completed_overs}.{balls_in_over}")

    @classmethod
    def _normalise_innings(cls, innings: Dict) -> Dict:
        if not isinstance(innings, dict):
            return {'runs': None, 'wickets': None, 'overs': None}
        return {
            'runs': cls._normalise_count(innings.get('runs')),
            'wickets': cls._normalise_count(innings.get('wickets'), maximum=10),
            'overs': cls._normalise_over(innings.get('overs')),
        }

    @staticmethod
    def _get_innings(match_score: Dict, score_key: str, innings_key: str) -> Dict:
        if not isinstance(match_score, dict):
            return {}
        team_score = match_score.get(score_key, {})
        if not isinstance(team_score, dict):
            return {}
        innings = team_score.get(innings_key, {})
        return innings if isinstance(innings, dict) else {}

    @classmethod
    def _select_current_innings(cls, match_score: Dict) -> Optional[Dict]:
        """Select the latest innings without guessing ambiguous multi-innings states."""
        if not isinstance(match_score, dict):
            return None
        candidates = []
        for team_index, (team, score_key) in enumerate(
            (('team1', 'team1Score'), ('team2', 'team2Score'))
        ):
            team_score = match_score.get(score_key, {})
            if not isinstance(team_score, dict):
                continue
            for innings_key, raw_innings in team_score.items():
                if (
                    not isinstance(innings_key, str)
                    or not innings_key.startswith('inngs')
                    or not innings_key[5:].isdigit()
                    or not isinstance(raw_innings, dict)
                ):
                    continue
                innings_number = int(innings_key[5:])
                if innings_number < 1:
                    continue
                normalised = cls._normalise_innings(raw_innings)
                innings_id = cls._normalise_count(raw_innings.get('inningsId'))
                if innings_id is not None and innings_id < 1:
                    innings_id = None
                if not any(
                    normalised.get(key) is not None
                    for key in ('runs', 'wickets', 'overs')
                ):
                    continue
                candidates.append({
                    'team': team,
                    'team_index': team_index,
                    'innings_number': innings_number,
                    'innings_id': innings_id,
                    **normalised,
                })

        if not candidates:
            return None
        identified = [item for item in candidates if item['innings_id'] is not None]
        if identified:
            latest_id = max(item['innings_id'] for item in identified)
            latest = [item for item in identified if item['innings_id'] == latest_id]
            return latest[0] if len(latest) == 1 else None

        latest_number = max(item['innings_number'] for item in candidates)
        latest = [item for item in candidates if item['innings_number'] == latest_number]
        if len(latest) == 1:
            return latest[0]
        if latest_number == 1:
            return max(latest, key=lambda item: item['team_index'])
        return None

    def _determine_batting_team(self, match_score: Dict) -> Optional[str]:
        """Determine which team is currently batting"""
        current = self._select_current_innings(match_score)
        return current.get('team') if current else None

    def _get_current_over(self, match_score: Dict) -> Optional[float]:
        """Get current over being bowled"""
        current = self._select_current_innings(match_score)
        return current.get('overs') if current else None

    @classmethod
    def _calculate_run_rate_values(cls, runs_value, overs_value) -> Optional[float]:
        runs = cls._normalise_count(runs_value)
        balls = cls._overs_to_balls(overs_value)
        if runs is None or balls is None or balls <= 0:
            return None
        return round(runs * 6 / balls, 2)

    def _calculate_run_rate(self, match_score: Dict) -> Optional[float]:
        """Calculate current run rate"""
        current = self._select_current_innings(match_score)
        if not current:
            return None
        return self._calculate_run_rate_values(current.get('runs'), current.get('overs'))
    
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
        
        runs = match.get('current_runs')
        wickets = match.get('current_wickets')
        overs = match.get('current_over')

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
