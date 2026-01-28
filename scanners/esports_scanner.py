"""
E-SPORTS SCANNER - PROPER IMPLEMENTATION
Like Football/Basketball: Stats-based analysis with clear recommendations

Author: BetBoy
Date: January 2026
"""

import streamlit as st
import requests
from datetime import datetime
from typing import Dict, List, Optional

class EsportsScanner:
    """
    E-Sports Scanner - Same approach as Football/Basketball
    Fetch real stats, calculate probabilities, give recommendations
    """
    
    def __init__(self):
        self.pandascore_base = "https://api.pandascore.co"
        
        try:
            self.api_key = st.secrets.get('esports', {}).get('pandascore_key', '')
        except:
            self.api_key = ''
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        }
        
        # Cache for team stats to avoid repeated API calls
        self._stats_cache = {}
    
    def get_live_matches(self, game: str = "all") -> List[Dict]:
        """Get live matches from Pandascore"""
        all_matches = []
        
        games_map = {
            'cs2': 'csgo',
            'lol': 'lol',
            'dota2': 'dota2',
            'valorant': 'valorant'
        }
        
        games_to_scan = list(games_map.keys()) if game == 'all' else [game]
        
        for g in games_to_scan:
            try:
                api_game = games_map.get(g, g)
                url = f"{self.pandascore_base}/{api_game}/matches/running"
                
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    matches = response.json()
                    for match in matches:
                        formatted = self._format_match(match, g.upper())
                        if formatted:
                            all_matches.append(formatted)
                            
            except Exception as e:
                pass  # Silent fail, show what we can
        
        return all_matches
    
    def _format_match(self, match: Dict, game: str) -> Optional[Dict]:
        """Format match with team stats"""
        try:
            opponents = match.get('opponents', [])
            if len(opponents) < 2:
                return None
            
            team1 = opponents[0].get('opponent', {})
            team2 = opponents[1].get('opponent', {})
            
            team1_id = team1.get('id')
            team2_id = team2.get('id')
            
            results = match.get('results', [])
            score1 = results[0].get('score', 0) if len(results) > 0 else 0
            score2 = results[1].get('score', 0) if len(results) > 1 else 0
            
            # Get REAL team statistics
            game_slug = 'csgo' if game == 'CS2' else game.lower()
            team1_stats = self._get_team_stats(team1_id, game_slug)
            team2_stats = self._get_team_stats(team2_id, game_slug)
            
            return {
                'id': match.get('id'),
                'game': game if game != 'CSGO' else 'CS2',
                'team1': team1.get('name', 'Team 1'),
                'team2': team2.get('name', 'Team 2'),
                'team1_id': team1_id,
                'team2_id': team2_id,
                'team1_score': score1,
                'team2_score': score2,
                'tournament': match.get('tournament', {}).get('name', 'Unknown'),
                'series_type': match.get('number_of_games', 3),
                'team1_stats': team1_stats,
                'team2_stats': team2_stats
            }
        except:
            return None
    
    def _get_team_stats(self, team_id: int, game: str) -> Dict:
        """Get REAL team statistics from last matches"""
        if not team_id:
            return {'win_rate': 50, 'matches': 0, 'wins': 0, 'form': []}
        
        # Check cache
        cache_key = f"{game}_{team_id}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        try:
            # Get last 20 matches for this team
            url = f"{self.pandascore_base}/{game}/matches/past"
            params = {
                'filter[opponent_id]': team_id,
                'sort': '-begin_at',
                'per_page': 20
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                matches = response.json()
                
                if matches:
                    wins = 0
                    total = len(matches)
                    form = []  # Last 5 results: W/L
                    
                    for i, m in enumerate(matches):
                        winner = m.get('winner', {})
                        won = winner and winner.get('id') == team_id
                        
                        if won:
                            wins += 1
                        
                        if i < 5:  # Last 5 for form
                            form.append('W' if won else 'L')
                    
                    win_rate = (wins / total * 100) if total > 0 else 50
                    
                    stats = {
                        'win_rate': round(win_rate, 1),
                        'matches': total,
                        'wins': wins,
                        'form': form
                    }
                    
                    self._stats_cache[cache_key] = stats
                    return stats
        except:
            pass
        
        return {'win_rate': 50, 'matches': 0, 'wins': 0, 'form': []}
    
    def analyze_match(self, match: Dict) -> Optional[Dict]:
        """
        Analyze match and give recommendation
        Same approach as Football/Basketball scanners
        """
        game = match.get('game', '')
        team1 = match.get('team1', 'Team 1')
        team2 = match.get('team2', 'Team 2')
        score1 = match.get('team1_score', 0)
        score2 = match.get('team2_score', 0)
        series_type = match.get('series_type', 3)
        
        stats1 = match.get('team1_stats', {})
        stats2 = match.get('team2_stats', {})
        
        wr1 = stats1.get('win_rate', 50)
        wr2 = stats2.get('win_rate', 50)
        form1 = stats1.get('form', [])
        form2 = stats2.get('form', [])
        matches1 = stats1.get('matches', 0)
        matches2 = stats2.get('matches', 0)
        
        # ===== PROBABILITY CALCULATION =====
        
        # Base probability from win rates (normalized)
        total_wr = wr1 + wr2
        if total_wr > 0 and total_wr != 100:
            prob1 = (wr1 / total_wr) * 100
            prob2 = (wr2 / total_wr) * 100
        else:
            prob1 = 50
            prob2 = 50
        
        reasoning = []
        reasoning.append(f"📊 Win rates: {team1} {wr1}% | {team2} {wr2}%")
        
        # Adjust for current series score
        score_diff = score1 - score2
        maps_to_win = (series_type // 2) + 1  # BO3 = 2, BO5 = 3
        
        if score_diff != 0:
            # Each map lead = significant advantage
            # Closer to winning = bigger advantage
            maps_needed_1 = maps_to_win - score1
            maps_needed_2 = maps_to_win - score2
            
            if maps_needed_1 < maps_needed_2:
                # Team 1 closer to winning
                advantage = (maps_needed_2 - maps_needed_1) * 12  # 12% per map closer
                prob1 += advantage
                prob2 -= advantage
                reasoning.append(f"📈 {team1} leads {score1}-{score2} (needs {maps_needed_1} more)")
            else:
                advantage = (maps_needed_1 - maps_needed_2) * 12
                prob2 += advantage
                prob1 -= advantage
                reasoning.append(f"📈 {team2} leads {score2}-{score1} (needs {maps_needed_2} more)")
        else:
            reasoning.append(f"⚖️ Series tied {score1}-{score2}")
        
        # Form adjustment (last 5 matches)
        form1_wins = form1.count('W') if form1 else 0
        form2_wins = form2.count('W') if form2 else 0
        
        if form1 and form2:
            form_diff = form1_wins - form2_wins
            if form_diff >= 2:
                prob1 += 5
                prob2 -= 5
                reasoning.append(f"🔥 {team1} hot form: {''.join(form1)}")
            elif form_diff <= -2:
                prob2 += 5
                prob1 -= 5
                reasoning.append(f"🔥 {team2} hot form: {''.join(form2)}")
        
        # Normalize to 100%
        total = prob1 + prob2
        prob1 = (prob1 / total) * 100
        prob2 = (prob2 / total) * 100
        
        # Cap at reasonable bounds
        prob1 = max(15, min(85, prob1))
        prob2 = 100 - prob1
        
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
        
        # Calculate fair odds from our probability
        fair_odds = round(100 / rec_prob, 2)
        
        # ===== CONFIDENCE CALCULATION =====
        
        confidence = 50  # Base
        
        # More data = more confidence
        if matches1 >= 10:
            confidence += 10
        if matches2 >= 10:
            confidence += 10
        
        # Clear favorite = more confidence
        prob_diff = abs(prob1 - prob2)
        if prob_diff >= 20:
            confidence += 15
        elif prob_diff >= 10:
            confidence += 10
        elif prob_diff >= 5:
            confidence += 5
        
        # Series lead = more confidence
        if abs(score_diff) >= 1:
            confidence += 10
        
        confidence = min(90, confidence)
        
        # ===== EDGE & VALUE CALCULATION =====
        
        # Assume market odds are ~5% worse than fair (juice)
        # We estimate market odds and calculate edge
        estimated_market_odds = fair_odds * 1.05
        implied_prob = 100 / estimated_market_odds
        
        edge = rec_prob - implied_prob
        
        # ROI estimate
        roi = edge * 0.7  # Conservative
        
        # ===== STAKE RECOMMENDATION =====
        
        if confidence >= 75 and edge >= 8:
            stake = "3-5%"
            stars = 5
        elif confidence >= 70 and edge >= 5:
            stake = "2-4%"
            stars = 4
        elif confidence >= 60 and edge >= 3:
            stake = "1-3%"
            stars = 3
        elif edge >= 2:
            stake = "1-2%"
            stars = 2
        else:
            stake = "0.5-1%"
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
            'odds': fair_odds,
            'win_probability': round(rec_prob, 1),
            'edge': round(edge, 1),
            'roi': round(roi, 1),
            'confidence': round(confidence),
            'stake': stake,
            'stars': stars,
            'reasoning': reasoning,
            'team1_wr': wr1,
            'team2_wr': wr2,
            'team1_form': ''.join(form1) if form1 else 'N/A',
            'team2_form': ''.join(form2) if form2 else 'N/A',
            'data_quality': 'Good' if matches1 >= 5 and matches2 >= 5 else 'Limited'
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
    
    # Sort by confidence and edge
    recommendations.sort(key=lambda x: (x['confidence'], x['edge']), reverse=True)
    
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
        c1.metric("Win Prob", f"{rec['win_probability']}%")
        c2.metric("Fair Odds", f"{rec['odds']}")
        c3.metric("Edge", f"+{rec['edge']}%")
        c4.metric("Confidence", f"{rec['confidence']}%")
        
        # Recommendation
        if rec['stars'] >= 3:
            st.success(f"✅ **{rec['team']}** to WIN @ {rec['odds']} • Edge: +{rec['edge']}% • Stake: {rec['stake']}")
        else:
            st.info(f"📊 **{rec['team']}** slight favorite @ {rec['odds']} • Low confidence")
        
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
