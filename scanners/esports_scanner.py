"""Exploratory e-sports estimates from observed match histories."""

import math
import streamlit as st
import requests
from datetime import datetime
from typing import Dict, List, Optional

from config_loader import load_app_config

class EsportsScanner:
    """
    E-Sports live scanner with explicitly uncalibrated history estimates.
    """

    MAX_LIVE_MATCHES_PER_GAME = 6
    
    def __init__(self):
        self.pandascore_base = "https://api.pandascore.co"
        self.api_key = load_app_config(st).pandascore_key or ''
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
        
        # Cache for team stats to avoid repeated API calls
        self._stats_cache = {}
        self.errors: Dict[str, str] = {}
    
    def get_live_matches(self, game: str = "all") -> List[Dict]:
        """Get live matches from Pandascore"""
        self.errors = {}
        if not self.api_key:
            self.errors["credentials"] = "PandaScore key missing"
            return []
        all_matches = []
        
        games_map = {
            'cs2': 'csgo',
            'lol': 'lol',
            'dota2': 'dota2',
            'valorant': 'valorant'
        }

        if game != 'all' and game not in games_map:
            self.errors['selection'] = 'Unsupported game'
            return []
        
        games_to_scan = list(games_map.keys()) if game == 'all' else [game]
        
        for g in games_to_scan:
            try:
                api_game = games_map.get(g, g)
                url = f"{self.pandascore_base}/{api_game}/matches/running"
                
                response = requests.get(
                    url,
                    headers=self.headers,
                    params={'per_page': self.MAX_LIVE_MATCHES_PER_GAME},
                    timeout=10,
                )
                
                if response.status_code == 200:
                    matches = response.json()
                    if not isinstance(matches, list):
                        self.errors[g] = "Invalid provider payload"
                        continue
                    for match in matches[:self.MAX_LIVE_MATCHES_PER_GAME]:
                        formatted = self._format_match(match, g.upper())
                        if formatted:
                            all_matches.append(formatted)
                else:
                    self.errors[g] = f"HTTP {response.status_code}"

            except (requests.RequestException, ValueError) as exc:
                self.errors[g] = type(exc).__name__
                continue
        
        return all_matches
    
    def _format_match(self, match: Dict, game: str) -> Optional[Dict]:
        """Format match with team stats"""
        try:
            if not isinstance(match, dict):
                return None
            opponents = match.get('opponents', [])
            if not isinstance(opponents, list) or len(opponents) != 2:
                return None

            if not all(isinstance(item, dict) for item in opponents):
                return None
            team1 = opponents[0].get('opponent', {})
            team2 = opponents[1].get('opponent', {})
            if not isinstance(team1, dict) or not isinstance(team2, dict):
                return None
            
            team1_id = team1.get('id')
            team2_id = team2.get('id')
            team1_name = str(team1.get('name') or '').strip()
            team2_name = str(team2.get('name') or '').strip()
            match_id = match.get('id')
            if (
                not isinstance(team1_id, int)
                or isinstance(team1_id, bool)
                or team1_id <= 0
                or not isinstance(team2_id, int)
                or isinstance(team2_id, bool)
                or team2_id <= 0
                or team1_id == team2_id
                or not team1_name
                or not team2_name
                or team1_name.casefold() == team2_name.casefold()
                or not isinstance(match_id, int)
                or isinstance(match_id, bool)
                or match_id <= 0
            ):
                return None
            
            results = match.get('results', [])
            if not isinstance(results, list):
                return None
            scores_by_team = {
                result.get('team_id'): result.get('score')
                for result in results
                if isinstance(result, dict) and result.get('team_id') is not None
            }
            score1 = scores_by_team.get(team1_id)
            score2 = scores_by_team.get(team2_id)
            if (
                isinstance(score1, bool)
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

            series_type = match.get('number_of_games')
            can_estimate = (
                isinstance(series_type, int)
                and not isinstance(series_type, bool)
                and series_type > 0
                and series_type % 2 == 1
            )

            # Historical calls are useful only when the series model can consume them.
            game_slug = 'csgo' if game == 'CS2' else game.lower()
            if can_estimate:
                team1_stats = self._get_team_stats(team1_id, game_slug)
                team2_stats = self._get_team_stats(team2_id, game_slug)
            else:
                team1_stats = self._empty_stats()
                team2_stats = self._empty_stats()

            tournament = match.get('tournament', {})
            tournament_name = (
                str(tournament.get('name') or 'Unknown').strip()
                if isinstance(tournament, dict)
                else 'Unknown'
            ) or 'Unknown'
            
            return {
                'id': match_id,
                'game': game if game != 'CSGO' else 'CS2',
                'team1': team1_name,
                'team2': team2_name,
                'team1_id': team1_id,
                'team2_id': team2_id,
                'team1_score': score1,
                'team2_score': score2,
                'tournament': tournament_name,
                'series_type': series_type,
                'team1_stats': team1_stats,
                'team2_stats': team2_stats,
                'source': 'PandaScore',
            }
        except (AttributeError, KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _empty_stats() -> Dict:
        return {'win_rate': None, 'matches': 0, 'wins': 0, 'form': []}
    
    def _get_team_stats(self, team_id: int, game: str) -> Dict:
        """Get REAL team statistics from last matches"""
        if not isinstance(team_id, int) or isinstance(team_id, bool) or team_id <= 0:
            return self._empty_stats()
        
        # Check cache
        cache_key = f"{game}_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        try:
            # The team endpoint guarantees membership. The former
            # filter[opponent_id] query selected the opponent instead.
            url = f"{self.pandascore_base}/teams/{team_id}/matches"
            params = {
                'sort': '-begin_at',
                'per_page': 50,
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                matches = response.json()
                if not isinstance(matches, list):
                    self.errors[f'team_{team_id}'] = 'Invalid provider payload'
                    stats = self._empty_stats()
                    self._stats_cache[cache_key] = stats
                    return stats
                if matches:
                    wins = 0
                    total = 0
                    form = []  # Last 5 results: W/L
                    
                    for m in matches:
                        if str(m.get('status') or '').lower() != 'finished':
                            continue
                        opponent_ids = {
                            item.get('opponent', {}).get('id')
                            for item in (m.get('opponents') or [])
                            if isinstance(item, dict)
                        }
                        if team_id not in opponent_ids:
                            continue
                        winner = m.get('winner', {})
                        winner_id = winner.get('id') if winner else None
                        if winner_id is None:
                            continue
                        won = winner_id == team_id
                        total += 1
                        
                        if won:
                            wins += 1
                        
                        if len(form) < 5:
                            form.append('W' if won else 'L')
                        if total >= 20:
                            break
                    
                    if total == 0:
                        stats = self._empty_stats()
                        self._stats_cache[cache_key] = stats
                        return stats
                    win_rate = wins / total * 100
                    
                    stats = {
                        'win_rate': round(win_rate, 1),
                        'matches': total,
                        'wins': wins,
                        'form': form
                    }
                    
                    self._stats_cache[cache_key] = stats
                    return stats
            else:
                self.errors[f'team_{team_id}'] = f'HTTP {response.status_code}'
        except (requests.RequestException, ValueError) as exc:
            self.errors[f'team_{team_id}'] = type(exc).__name__

        stats = self._empty_stats()
        self._stats_cache[cache_key] = stats
        return stats

    @staticmethod
    def _series_win_probability(
        map_probability: float,
        team_maps: int,
        opponent_maps: int,
        maps_to_win: int,
    ) -> float:
        if (
            isinstance(map_probability, bool)
            or not isinstance(map_probability, (int, float))
            or not math.isfinite(float(map_probability))
            or not 0.0 <= float(map_probability) <= 1.0
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in (team_maps, opponent_maps, maps_to_win)
            )
            or maps_to_win < 1
        ):
            raise ValueError("Invalid first-to-N series state")
        memo = {}

        def solve(team_score: int, opponent_score: int) -> float:
            if team_score >= maps_to_win:
                return 1.0
            if opponent_score >= maps_to_win:
                return 0.0
            key = (team_score, opponent_score)
            if key not in memo:
                memo[key] = (
                    map_probability * solve(team_score + 1, opponent_score)
                    + (1.0 - map_probability) * solve(team_score, opponent_score + 1)
                )
            return memo[key]

        return solve(team_maps, opponent_maps)
    
    def analyze_match(self, match: Dict) -> Optional[Dict]:
        """
        Produce a non-actionable exploratory estimate when inputs are sufficient.
        """
        if not isinstance(match, dict):
            return None
        game = match.get('game', '')
        team1 = str(match.get('team1') or '').strip()
        team2 = str(match.get('team2') or '').strip()
        score1 = match.get('team1_score')
        score2 = match.get('team2_score')
        series_type = match.get('series_type', 3)
        
        stats1 = match.get('team1_stats', {})
        stats2 = match.get('team2_stats', {})
        if not isinstance(stats1, dict) or not isinstance(stats2, dict):
            return None
        
        wr1 = stats1.get('win_rate')
        wr2 = stats2.get('win_rate')
        form1 = stats1.get('form', [])
        form2 = stats2.get('form', [])
        matches1_raw = stats1.get('matches')
        matches2_raw = stats2.get('matches')
        wins1_raw = stats1.get('wins')
        wins2_raw = stats2.get('wins')
        if (
            not team1
            or not team2
            or team1 == team2
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in (matches1_raw, matches2_raw, wins1_raw, wins2_raw)
            )
        ):
            return None
        try:
            score1_value = float(score1)
            score2_value = float(score2)
            matches1 = matches1_raw
            matches2 = matches2_raw
            wins1 = wins1_raw
            wins2 = wins2_raw
        except (TypeError, ValueError, OverflowError):
            return None
        if (
            wr1 is None
            or wr2 is None
            or isinstance(wr1, bool)
            or isinstance(wr2, bool)
            or not math.isfinite(float(wr1))
            or not math.isfinite(float(wr2))
            or not 0.0 <= float(wr1) <= 100.0
            or not 0.0 <= float(wr2) <= 100.0
            or not math.isfinite(score1_value)
            or not math.isfinite(score2_value)
            or not score1_value.is_integer()
            or not score2_value.is_integer()
            or matches1 < 5
            or matches2 < 5
            or not 0 <= wins1 <= matches1
            or not 0 <= wins2 <= matches2
            or not math.isclose(float(wr1), wins1 / matches1 * 100.0, abs_tol=0.2)
            or not math.isclose(float(wr2), wins2 / matches2 * 100.0, abs_tol=0.2)
        ):
            return None
        
        # ===== PROBABILITY CALCULATION =====
        
        # Beta(1,1) shrinkage avoids zero/one estimates. Relative odds form an
        # uncalibrated map-strength matchup; opponent strength is not adjusted.
        rate1 = (wins1 + 1) / (matches1 + 2)
        rate2 = (wins2 + 1) / (matches2 + 2)
        strength1 = rate1 / (1.0 - rate1)
        strength2 = rate2 / (1.0 - rate2)
        map_probability1 = strength1 / (strength1 + strength2)
        
        reasoning = []
        reasoning.append(f"📊 Win rates: {team1} {wr1}% | {team2} {wr2}%")
        
        if isinstance(series_type, bool) or not isinstance(series_type, int):
            return None
        series_maps = series_type
        if series_maps <= 0 or series_maps % 2 == 0:
            return None
        maps_to_win = (series_maps // 2) + 1
        if (
            score1_value < 0
            or score2_value < 0
        ):
            return None
        score1_int = int(score1_value)
        score2_int = int(score2_value)
        if score1_int >= maps_to_win or score2_int >= maps_to_win:
            return None
        prob1 = self._series_win_probability(
            map_probability1,
            score1_int,
            score2_int,
            maps_to_win,
        ) * 100
        prob2 = 100 - prob1
        reasoning.append(
            f"Series state {score1_int}-{score2_int} evaluated as a first-to-{maps_to_win} race"
        )
        reasoning.append("Opponent strength and map-specific lineups are not adjusted")
        
        # ===== DETERMINE RECOMMENDATION =====
        
        if prob1 > prob2:
            rec_team = team1
            rec_prob = prob1
            opp_team = team2
            opp_prob = prob2
        else:
            rec_team = team2
            rec_prob = prob2
            opp_team = team1
            opp_prob = prob1
        
        # ===== CONFIDENCE CALCULATION =====

        data_coverage = min(100.0, min(matches1, matches2) / 20.0 * 100.0)
        
        probability_gap = abs(rec_prob - opp_prob)

        if data_coverage >= 75 and probability_gap >= 20:
            stars = 5
        elif data_coverage >= 60 and probability_gap >= 15:
            stars = 4
        elif data_coverage >= 50 and probability_gap >= 10:
            stars = 3
        elif probability_gap >= 5:
            stars = 2
        else:
            stars = 1
        
        return {
            'match_id': match.get('id'),
            'game': game,
            'team1': team1,
            'team2': team2,
            'score': f"{score1}-{score2}",
            'tournament': match.get('tournament', 'Unknown'),
            'market': 'Match Winner',
            'team': rec_team,
            'model_price': None,
            'win_probability': round(rec_prob, 1),
            'probability_gap': round(probability_gap, 1),
            'data_coverage': round(data_coverage),
            'stars': stars,
            'recommendation_type': 'EXPLORATORY_ESTIMATE',
            'calibrated': False,
            'actionable': False,
            'reasoning': reasoning,
            'team1_wr': wr1,
            'team2_wr': wr2,
            'team1_form': ''.join(form1) if form1 else 'N/A',
            'team2_form': ''.join(form2) if form2 else 'N/A',
            'data_quality': 'MEDIUM' if matches1 >= 10 and matches2 >= 10 else 'LIMITED'
        }


def create_esports_tab():
    """E-Sports Tab"""
    st.header("🎮 E-SPORTS LIVE SCANNER")
    st.markdown("**CS2 • League of Legends • Dota 2 • Valorant**")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        game_filter = st.radio(
            "Filter:",
            ["All", "CS2", "LoL", "Dota2", "Valorant"],
            horizontal=True,
            key="esports_game_filter"
        )
    with col2:
        if st.button("🔄 Refresh", key="esports_refresh"):
            st.rerun()
    
    scanner = EsportsScanner()
    
    if not scanner.api_key:
        st.error("⚠️ Pandascore API key required")
        st.info("Get free key: https://pandascore.co")
        return
    
    with st.spinner(f"🔍 Scanning {game_filter} matches..."):
        matches = scanner.get_live_matches(game_filter.lower() if game_filter != "All" else "all")
    
    if not matches:
        st.info(f"No live {game_filter} matches")
        return
    
    st.success(f"✅ {len(matches)} live matches")
    
    recommendations = []
    
    for match in matches:
        analysis = scanner.analyze_match(match)
        if analysis:
            recommendations.append(analysis)
    
    recommendations.sort(
        key=lambda x: (x['data_coverage'], x['probability_gap']),
        reverse=True,
    )
    
    for rec in recommendations:
        # Stars display
        stars = "⭐" * rec['stars']
        
        # Color based on strength
        if rec['stars'] >= 4:
            color = "#00ff00"
        elif rec['stars'] >= 3:
            color = "#ffcc00"
        else:
            color = "#888888"
        
        st.markdown(f"""
        <div style="border-left: 4px solid {color}; padding: 15px; margin: 10px 0; background: #1a1a2e; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-size: 1.1em; font-weight: bold;">{rec['team1']} vs {rec['team2']}</span>
                <span>{stars}</span>
            </div>
            <div style="color: #888; font-size: 0.9em;">{rec['game']} • {rec['tournament']} • {rec['score']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Stats
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Exploratory estimate", f"{rec['win_probability']}%")
        c2.metric("Fair price", "n/a")
        c3.metric("Probability gap", f"{rec['probability_gap']} pp")
        c4.metric("Data coverage", f"{rec['data_coverage']}%")
        
        st.info(
            f"**{rec['team']}** is the exploratory favorite. This estimate is "
            "uncalibrated and cannot be used as a bet or fair price."
        )
        
        # Details expander
        with st.expander("📊 Analysis"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**{rec['team1']}**")
                st.write(f"Win Rate: {rec['team1_wr']}%")
                st.write(f"Form: {rec['team1_form']}")
            with col2:
                st.write(f"**{rec['team2']}**")
                st.write(f"Win Rate: {rec['team2_wr']}%")
                st.write(f"Form: {rec['team2_form']}")
            
            st.markdown("---")
            for reason in rec['reasoning']:
                st.write(reason)
            
            st.caption(f"Data Quality: {rec['data_quality']}")
        
        st.markdown("---")


if __name__ == "__main__":
    st.set_page_config(page_title="E-Sports Scanner", layout="wide")
    create_esports_tab()
