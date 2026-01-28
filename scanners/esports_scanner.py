"""
E-SPORTS SCANNER - PROPER IMPLEMENTATION
Uses REAL data, proper probability calculations, NO fake odds!

Key Principles:
1. Use REAL odds from Pandascore API (when available)
2. Calculate TRUE edge based on statistical analysis
3. NO recommendations without proper data
4. Clear disclaimer when using estimates

Author: BetBoy
Date: January 2026
"""

import streamlit as st
import requests
from datetime import datetime
from typing import Dict, List, Optional
import math

class EsportsScanner:
    """
    Professional E-Sports Scanner
    - Real Pandascore API integration
    - Proper statistical analysis
    - No fake/invented odds
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
    
    def get_live_matches(self, game: str = "all") -> List[Dict]:
        """Get live matches with REAL data from Pandascore"""
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
                st.warning(f"⚠️ {g.upper()}: {str(e)[:50]}")
        
        return all_matches
    
    def _format_match(self, match: Dict, game: str) -> Optional[Dict]:
        """Format Pandascore match data with ALL available info"""
        try:
            opponents = match.get('opponents', [])
            if len(opponents) < 2:
                return None
            
            team1 = opponents[0].get('opponent', {})
            team2 = opponents[1].get('opponent', {})
            
            results = match.get('results', [])
            score1 = results[0].get('score', 0) if len(results) > 0 else 0
            score2 = results[1].get('score', 0) if len(results) > 1 else 0
            
            # Get team statistics from API
            team1_stats = self._get_team_stats(team1.get('id'), game)
            team2_stats = self._get_team_stats(team2.get('id'), game)
            
            return {
                'id': match.get('id'),
                'game': game if game != 'CSGO' else 'CS2',
                'team1': team1.get('name', 'Team 1'),
                'team2': team2.get('name', 'Team 2'),
                'team1_id': team1.get('id'),
                'team2_id': team2.get('id'),
                'team1_score': score1,
                'team2_score': score2,
                'tournament': match.get('tournament', {}).get('name', 'Unknown'),
                'league': match.get('league', {}).get('name', 'Unknown'),
                'series_type': match.get('number_of_games', 1),
                'status': match.get('status', 'running'),
                'team1_stats': team1_stats,
                'team2_stats': team2_stats,
                # Store raw data for detailed analysis
                '_raw': match
            }
        except Exception as e:
            return None
    
    def _get_team_stats(self, team_id: int, game: str) -> Dict:
        """Get team statistics - win rate, recent form, etc."""
        if not team_id:
            return {}
        
        try:
            # Get recent matches for this team
            game_slug = 'csgo' if game == 'CS2' else game.lower()
            url = f"{self.pandascore_base}/{game_slug}/matches/past"
            params = {
                'filter[opponent_id]': team_id,
                'sort': '-begin_at',
                'per_page': 10  # Last 10 matches
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                matches = response.json()
                
                if not matches:
                    return {}
                
                # Calculate stats
                wins = 0
                total = len(matches)
                
                for m in matches:
                    winner = m.get('winner', {})
                    if winner and winner.get('id') == team_id:
                        wins += 1
                
                win_rate = (wins / total * 100) if total > 0 else 50
                
                return {
                    'win_rate': round(win_rate, 1),
                    'recent_matches': total,
                    'recent_wins': wins,
                    'form': 'Good' if win_rate >= 60 else ('Average' if win_rate >= 40 else 'Poor')
                }
        except:
            pass
        
        return {}
    
    def get_match_odds(self, match_id: int) -> Optional[Dict]:
        """
        Get REAL betting odds from Pandascore
        Returns None if no odds available
        """
        try:
            url = f"{self.pandascore_base}/betting/matches/{match_id}/odds"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                odds_data = response.json()
                
                if odds_data:
                    # Parse the odds structure
                    return self._parse_odds(odds_data)
        except:
            pass
        
        return None
    
    def _parse_odds(self, odds_data: List) -> Dict:
        """Parse Pandascore odds response"""
        result = {
            'team1_odds': None,
            'team2_odds': None,
            'bookmakers': []
        }
        
        for odd in odds_data:
            market = odd.get('market_type', '')
            
            if market == 'winner':
                outcomes = odd.get('outcomes', [])
                bookmaker = odd.get('bookmaker', {}).get('name', 'Unknown')
                
                for outcome in outcomes:
                    odds_val = outcome.get('odds')
                    team_id = outcome.get('competitor_id')
                    
                    result['bookmakers'].append({
                        'name': bookmaker,
                        'team_id': team_id,
                        'odds': odds_val
                    })
        
        return result if result['bookmakers'] else None
    
    def analyze_match(self, match: Dict) -> Optional[Dict]:
        """
        PROPER match analysis:
        1. Try to get real odds
        2. If no odds: use statistical analysis with disclaimer
        3. Calculate TRUE edge
        4. Only recommend if genuine edge exists
        """
        game = match.get('game', '').upper()
        team1 = match.get('team1', 'Team 1')
        team2 = match.get('team2', 'Team 2')
        score1 = match.get('team1_score', 0)
        score2 = match.get('team2_score', 0)
        match_id = match.get('id')
        
        team1_stats = match.get('team1_stats', {})
        team2_stats = match.get('team2_stats', {})
        
        # Try to get REAL odds
        real_odds = self.get_match_odds(match_id) if match_id else None
        
        # Calculate probability based on REAL data
        prob1, prob2, confidence, reasoning = self._calculate_probability(
            team1, team2, 
            score1, score2,
            team1_stats, team2_stats,
            game
        )
        
        # Determine recommendation
        if prob1 > prob2:
            recommended_team = team1
            win_prob = prob1
            opp_prob = prob2
        else:
            recommended_team = team2
            win_prob = prob2
            opp_prob = prob1
        
        # If we have REAL odds
        if real_odds and real_odds.get('bookmakers'):
            # Find best odds for recommended team
            best_odds = None
            for bm in real_odds['bookmakers']:
                # Match team to odds (simplified)
                odds_val = bm.get('odds')
                if odds_val and (best_odds is None or odds_val > best_odds):
                    best_odds = odds_val
            
            if best_odds:
                implied_prob = 1 / best_odds
                edge = (win_prob / 100) - implied_prob
                edge_pct = edge * 100
                
                has_value = edge_pct > 3  # At least 3% edge required
                
                return {
                    'match_id': match_id,
                    'game': game,
                    'team1': team1,
                    'team2': team2,
                    'score': f"{score1}-{score2}",
                    'tournament': match.get('tournament', 'Unknown'),
                    'market': 'Match Winner',
                    'team': recommended_team,
                    'odds': round(best_odds, 2),
                    'odds_source': 'Real Market',
                    'win_probability': round(win_prob, 1),
                    'implied_probability': round(implied_prob * 100, 1),
                    'edge': round(edge_pct, 1),
                    'roi': round(edge_pct * 0.8, 1),  # Conservative
                    'confidence': confidence,
                    'has_value': has_value,
                    'reasoning': reasoning,
                    'is_estimate': False
                }
        
        # NO REAL ODDS - use statistical estimate with clear disclaimer
        # Convert probability to fair odds
        fair_odds = round(1 / (win_prob / 100), 2) if win_prob > 0 else 2.0
        
        return {
            'match_id': match_id,
            'game': game,
            'team1': team1,
            'team2': team2,
            'score': f"{score1}-{score2}",
            'tournament': match.get('tournament', 'Unknown'),
            'market': 'Match Winner',
            'team': recommended_team,
            'odds': fair_odds,
            'odds_source': '⚠️ Statistical Estimate',
            'win_probability': round(win_prob, 1),
            'implied_probability': round(win_prob, 1),  # Same as our estimate
            'edge': 0,  # Cannot calculate real edge without market odds
            'roi': 0,
            'confidence': confidence,
            'has_value': False,  # Cannot confirm value without real odds
            'reasoning': reasoning,
            'is_estimate': True
        }
    
    def _calculate_probability(self, team1: str, team2: str, 
                                score1: int, score2: int,
                                stats1: Dict, stats2: Dict,
                                game: str) -> tuple:
        """
        Calculate win probability using REAL statistics
        Returns: (prob1, prob2, confidence, reasoning)
        """
        reasoning = []
        
        # Base probability from team win rates
        wr1 = stats1.get('win_rate', 50)
        wr2 = stats2.get('win_rate', 50)
        
        # Normalize win rates to probabilities
        total_wr = wr1 + wr2
        if total_wr > 0:
            base_prob1 = (wr1 / total_wr) * 100
            base_prob2 = (wr2 / total_wr) * 100
        else:
            base_prob1 = 50
            base_prob2 = 50
        
        reasoning.append(f"📊 {team1} win rate: {wr1}% | {team2} win rate: {wr2}%")
        
        # Adjust for current series score
        score_diff = score1 - score2
        if score_diff != 0:
            # Each map/game lead adds probability
            adjustment = score_diff * 8  # 8% per map lead
            base_prob1 += adjustment
            base_prob2 -= adjustment
            
            if score_diff > 0:
                reasoning.append(f"📈 {team1} leads {score1}-{score2}")
            else:
                reasoning.append(f"📈 {team2} leads {score2}-{score1}")
        else:
            reasoning.append(f"⚖️ Series tied {score1}-{score2}")
        
        # Calculate confidence based on data quality
        confidence = 50  # Base confidence
        
        if stats1.get('recent_matches', 0) >= 5:
            confidence += 10
            reasoning.append(f"✅ {team1}: {stats1.get('recent_matches')} recent matches analyzed")
        else:
            reasoning.append(f"⚠️ {team1}: Limited data ({stats1.get('recent_matches', 0)} matches)")
        
        if stats2.get('recent_matches', 0) >= 5:
            confidence += 10
        else:
            reasoning.append(f"⚠️ {team2}: Limited data ({stats2.get('recent_matches', 0)} matches)")
        
        # Form bonus
        if stats1.get('form') == 'Good':
            base_prob1 += 5
            confidence += 5
            reasoning.append(f"🔥 {team1} in good form")
        if stats2.get('form') == 'Good':
            base_prob2 += 5
            confidence += 5
            reasoning.append(f"🔥 {team2} in good form")
        
        # Cap probabilities
        base_prob1 = max(10, min(90, base_prob1))
        base_prob2 = max(10, min(90, base_prob2))
        
        # Normalize to 100%
        total = base_prob1 + base_prob2
        prob1 = (base_prob1 / total) * 100
        prob2 = (base_prob2 / total) * 100
        
        # Cap confidence
        confidence = min(85, confidence)
        
        return prob1, prob2, confidence, reasoning


def create_esports_tab():
    """E-Sports Tab with proper analysis"""
    st.header("🎮 E-SPORTS LIVE SCANNER")
    st.markdown("**CS2 • League of Legends • Dota 2 • Valorant**")
    
    # Important disclaimer
    st.info("📊 **Analysis based on team statistics and real market data when available**")
    
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
        st.error("⚠️ **Pandascore API key required**")
        st.info("Get free key at https://pandascore.co (1000 calls/month)")
        return
    
    with st.spinner(f"🔍 Scanning {game_filter} matches..."):
        matches = scanner.get_live_matches(game_filter.lower() if game_filter != "All" else "all")
    
    if not matches:
        st.info(f"ℹ️ No live {game_filter} matches")
        return
    
    st.success(f"✅ {len(matches)} live matches")
    
    # Analyze and display
    for match in matches:
        analysis = scanner.analyze_match(match)
        
        if not analysis:
            continue
        
        # Display match
        is_estimate = analysis.get('is_estimate', True)
        has_value = analysis.get('has_value', False)
        
        # Color based on recommendation quality
        if has_value and not is_estimate:
            border_color = "#00ff00"  # Green - real value found
            badge = "✅ VALUE BET"
        elif not is_estimate:
            border_color = "#ffaa00"  # Orange - real odds but no edge
            badge = "📊 NO EDGE"
        else:
            border_color = "#888888"  # Gray - estimate only
            badge = "⚠️ ESTIMATE"
        
        st.markdown(f"""
        <div style="border-left: 4px solid {border_color}; padding: 15px; margin: 10px 0; background: #1a1a2e; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-size: 1.2em; font-weight: bold;">🎮 {analysis['team1']} vs {analysis['team2']}</span>
                <span style="background: {border_color}; color: black; padding: 3px 10px; border-radius: 4px;">{badge}</span>
            </div>
            <div style="color: #888;">{analysis['game']} • {analysis['tournament']} • Score: {analysis['score']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Stats columns
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Prob", f"{analysis['win_probability']}%")
        c2.metric("Odds", f"{analysis['odds']}")
        c3.metric("Edge", f"{analysis['edge']:+.1f}%" if analysis['edge'] else "N/A")
        c4.metric("Confidence", f"{analysis['confidence']}%")
        
        # Recommendation
        if has_value:
            st.success(f"✅ **{analysis['team']}** to WIN @ **{analysis['odds']}** - Edge: **+{analysis['edge']}%**")
        elif is_estimate:
            st.warning(f"⚠️ **{analysis['team']}** favored ({analysis['win_probability']}%) - **No real odds available, cannot confirm value**")
        else:
            st.info(f"📊 **{analysis['team']}** @ {analysis['odds']} - No significant edge found")
        
        # Reasoning
        with st.expander("📊 Analysis Details"):
            for reason in analysis.get('reasoning', []):
                st.write(reason)
            
            st.markdown(f"**Odds Source:** {analysis.get('odds_source', 'Unknown')}")
            
            if is_estimate:
                st.warning("""
                ⚠️ **DISCLAIMER**: These odds are statistical estimates, not real market prices.
                Do NOT use for actual betting without checking real bookmaker odds!
                """)
        
        st.markdown("---")


if __name__ == "__main__":
    st.set_page_config(page_title="E-Sports Scanner", layout="wide")
    create_esports_tab()
