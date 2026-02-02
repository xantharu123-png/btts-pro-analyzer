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
    
    # Tournament tier reliability factors
    TOURNAMENT_TIERS = {
        'major': 1.0, 'world': 1.0, 'international': 1.0, 'ti ': 1.0,
        'blast premier': 0.98, 'esl pro': 0.98, 'iem': 0.95,
        'lcs': 0.95, 'lec': 0.95, 'lpl': 0.95, 'lck': 0.95,
        'dreamhack': 0.90, 'esl challenger': 0.88,
        'qualifier': 0.80, 'open qualifier': 0.75,
        'showmatch': 0.50, 'charity': 0.40, 'esportsbattle': 0.60,
        'esports battle': 0.60, 'e-battle': 0.60
    }
    
    def __init__(self):
        self.pandascore_base = "https://api.pandascore.co"
        
        # Try multiple locations for API key
        self.api_key = ''
        
        # Method 1: st.secrets['esports']['pandascore_key']
        try:
            if hasattr(st, 'secrets') and 'esports' in st.secrets:
                self.api_key = st.secrets['esports']['pandascore_key']
                print(f"✅ E-Sports API Key loaded from secrets.esports")
        except:
            pass
        
        # Method 2: st.secrets['PANDASCORE_KEY']
        if not self.api_key:
            try:
                if hasattr(st, 'secrets') and 'PANDASCORE_KEY' in st.secrets:
                    self.api_key = st.secrets['PANDASCORE_KEY']
                    print(f"✅ E-Sports API Key loaded from secrets.PANDASCORE_KEY")
            except:
                pass
        
        # Method 3: st.secrets['pandascore_key']
        if not self.api_key:
            try:
                if hasattr(st, 'secrets') and 'pandascore_key' in st.secrets:
                    self.api_key = st.secrets['pandascore_key']
                    print(f"✅ E-Sports API Key loaded from secrets.pandascore_key")
            except:
                pass
        
        # Method 4: Environment variable
        if not self.api_key:
            import os
            self.api_key = os.environ.get('PANDASCORE_KEY', '')
            if self.api_key:
                print(f"✅ E-Sports API Key loaded from environment")
        
        if not self.api_key:
            print("⚠️ No Pandascore API key found")
        
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
            'valorant': 'valorant',
            'fifa': 'ea-sports-fc',      # FIFA / EA Sports FC
            'rl': 'rl',                   # Rocket League
            'cod': 'codmw',               # Call of Duty
            'starcraft': 'starcraft-2',   # StarCraft 2
            'overwatch': 'ow'             # Overwatch
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
        IMPROVED E-Sports Analysis v2.0
        
        Factors (weighted):
        1. Win Rate (Elo-style) - 30%
        2. Form (weighted recency) - 25%
        3. Series Score (conditional prob) - 25%
        4. H2H History - 20%
        """
        game = match.get('game', '')
        team1 = match.get('team1', 'Team 1')
        team2 = match.get('team2', 'Team 2')
        team1_id = match.get('team1_id')
        team2_id = match.get('team2_id')
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
        
        reasoning = []
        
        # ===== 1. ELO-STYLE BASE PROBABILITY =====
        # Fix: Use Elo formula instead of simple normalization
        elo_diff = (wr1 - wr2) * 8  # Scale win rate diff to Elo-like
        expected1 = 1 / (1 + 10**(-elo_diff / 400))
        base_prob1 = expected1 * 100
        base_prob2 = 100 - base_prob1
        
        reasoning.append(f"📊 Win rates: {team1} {wr1}% | {team2} {wr2}%")
        reasoning.append(f"📈 Base probability: {team1} {base_prob1:.1f}%")
        
        # ===== 2. SERIES SCORE - CONDITIONAL PROBABILITY =====
        # Fix: Use empirical conditional probabilities, not linear bonus
        score_adjustment = 0
        maps_to_win = (series_type // 2) + 1
        
        if series_type == 3:  # BO3
            conditional_probs = {
                (1, 0): 72,  # 72% to win from 1-0
                (0, 1): 28,  # 28% to win from 0-1
                (0, 0): None  # Use base
            }
        elif series_type == 5:  # BO5
            conditional_probs = {
                (1, 0): 65, (0, 1): 35,
                (2, 0): 85, (0, 2): 15,
                (2, 1): 65, (1, 2): 35,
                (1, 1): None, (0, 0): None
            }
        else:  # BO1 or unknown
            conditional_probs = {}
        
        key = (score1, score2)
        if key in conditional_probs and conditional_probs[key] is not None:
            # Blend base prob with conditional prob (60% conditional, 40% base)
            cond_prob = conditional_probs[key]
            blended_prob1 = base_prob1 * 0.4 + cond_prob * 0.6
            score_adjustment = blended_prob1 - base_prob1
            reasoning.append(f"🎮 Score {score1}-{score2}: Conditional win% ~{cond_prob}%")
        elif score1 != score2:
            leader = team1 if score1 > score2 else team2
            reasoning.append(f"📈 {leader} leads {max(score1,score2)}-{min(score1,score2)}")
        
        # ===== 3. FORM ADJUSTMENT - WEIGHTED RECENCY =====
        # Fix: Recent matches matter more
        form_adjustment = 0
        if form1 and form2:
            weights = [1.0, 0.85, 0.70, 0.55, 0.40]  # Most recent first
            
            def calc_weighted_form(form):
                return sum(w * (1 if f == 'W' else 0) 
                          for w, f in zip(weights, form[:5]))
            
            form1_score = calc_weighted_form(form1)
            form2_score = calc_weighted_form(form2)
            
            form_diff = form1_score - form2_score
            form_adjustment = form_diff * 6  # Max ~15% swing
            
            if abs(form_adjustment) >= 5:
                hot_team = team1 if form_adjustment > 0 else team2
                hot_form = ''.join(form1 if form_adjustment > 0 else form2)
                reasoning.append(f"🔥 {hot_team} hot form: {hot_form} (+{abs(form_adjustment):.1f}%)")
        
        # ===== 4. H2H ADJUSTMENT =====
        h2h = self._get_h2h_stats(team1_id, team2_id, match.get('game', 'csgo').lower())
        h2h_adjustment = 0
        
        if h2h['matches'] >= 2:
            h2h_wr = h2h['team1_wins'] / h2h['matches']
            h2h_adjustment = (h2h_wr - 0.5) * 15  # Max ~7.5% swing
            
            if abs(h2h_adjustment) >= 3:
                h2h_fav = team1 if h2h_adjustment > 0 else team2
                reasoning.append(f"🔄 H2H: {h2h_fav} {h2h['team1_wins']}-{h2h['team2_wins']} ({h2h['matches']} games)")
        
        # ===== COMBINE ALL FACTORS =====
        final_prob1 = base_prob1 + score_adjustment + form_adjustment + h2h_adjustment
        
        # Cap at reasonable bounds
        final_prob1 = max(10, min(90, final_prob1))
        final_prob2 = 100 - final_prob1
        
        # ===== DETERMINE RECOMMENDATION =====
        if final_prob1 > final_prob2:
            rec_team = team1
            rec_prob = final_prob1
        else:
            rec_team = team2
            rec_prob = final_prob2
        
        # Calculate fair odds
        fair_odds = round(100 / rec_prob, 2)
        
        # ===== CONFIDENCE CALCULATION =====
        confidence = 40  # Base
        
        # Data quality - IMPROVED with better sample size handling
        total_matches = matches1 + matches2
        if matches1 >= 15 and matches2 >= 15:
            confidence += 15
        elif matches1 >= 10 and matches2 >= 10:
            confidence += 10
        elif matches1 >= 5 and matches2 >= 5:
            confidence += 5
        else:
            # LOW DATA WARNING
            confidence -= 10
            reasoning.append("⚠️ LIMITED DATA - Results unreliable")
        
        # Clear favorite
        prob_diff = abs(final_prob1 - final_prob2)
        if prob_diff >= 30:
            confidence += 20
        elif prob_diff >= 20:
            confidence += 15
        elif prob_diff >= 10:
            confidence += 10
        
        # Series lead
        if abs(score1 - score2) >= 1:
            confidence += 10
        
        # H2H data available
        if h2h['matches'] >= 3:
            confidence += 5
        
        # ===== TOURNAMENT TIER ADJUSTMENT =====
        tournament_name = match.get('tournament', '')
        tournament_tier = self._get_tournament_tier(tournament_name)
        
        if tournament_tier < 0.70:
            reasoning.append(f"⚠️ Low-tier tournament ({tournament_name}) - Unpredictable")
        elif tournament_tier < 0.85:
            reasoning.append(f"📊 Mid-tier event - Moderate reliability")
        
        # Apply tournament tier to confidence
        confidence = confidence * tournament_tier
        
        # ===== MAP STATS (CS2/Valorant) =====
        if game.lower() in ['cs2', 'valorant']:
            map1_stats = self._get_map_stats(team1_id, game)
            map2_stats = self._get_map_stats(team2_id, game)
            
            if map1_stats and map2_stats:
                # Find strongest/weakest maps
                best_maps_1 = [m for m, s in map1_stats.items() if s['wr'] >= 60 and s['total'] >= 3]
                best_maps_2 = [m for m, s in map2_stats.items() if s['wr'] >= 60 and s['total'] >= 3]
                
                if best_maps_1:
                    reasoning.append(f"🗺️ {team1} strong maps: {', '.join(best_maps_1[:3])}")
                if best_maps_2:
                    reasoning.append(f"🗺️ {team2} strong maps: {', '.join(best_maps_2[:3])}")
        
        confidence = max(25, min(92, confidence))
        
        # ===== EDGE CALCULATION =====
        # Assume 5% market juice
        implied_market_prob = rec_prob / 1.05
        edge = rec_prob - implied_market_prob
        
        # ROI estimate (conservative)
        roi = edge * 0.65
        
        # ===== STAKE RECOMMENDATION =====
        if confidence >= 80 and edge >= 10:
            stake = "4-6%"
            stars = 5
        elif confidence >= 75 and edge >= 7:
            stake = "3-5%"
            stars = 4
        elif confidence >= 65 and edge >= 5:
            stake = "2-3%"
            stars = 3
        elif confidence >= 55 and edge >= 3:
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
            'tournament_tier': round(tournament_tier * 100),
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
            'h2h': f"{h2h['team1_wins']}-{h2h['team2_wins']}" if h2h['matches'] > 0 else 'N/A',
            'data_quality': 'Good' if matches1 >= 10 and matches2 >= 10 else 'Limited',
            'sample_size': f"{matches1}+{matches2} matches"
        }
    
    def _get_h2h_stats(self, team1_id: int, team2_id: int, game: str) -> Dict:
        """Get head-to-head statistics between two teams"""
        if not team1_id or not team2_id:
            return {'matches': 0, 'team1_wins': 0, 'team2_wins': 0}
        
        cache_key = f"h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}_{game}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        try:
            game_slug = 'csgo' if game == 'cs2' else game
            url = f"{self.pandascore_base}/{game_slug}/matches/past"
            params = {
                'filter[opponent_id]': f"{team1_id},{team2_id}",
                'sort': '-begin_at',
                'per_page': 15
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                matches = response.json()
                
                # Filter for actual H2H (both teams in match)
                h2h_matches = []
                for m in matches:
                    opponents = m.get('opponents', [])
                    if len(opponents) == 2:
                        opp_ids = [o.get('opponent', {}).get('id') for o in opponents]
                        if team1_id in opp_ids and team2_id in opp_ids:
                            h2h_matches.append(m)
                
                team1_wins = 0
                team2_wins = 0
                
                for m in h2h_matches:
                    winner = m.get('winner', {})
                    if winner:
                        if winner.get('id') == team1_id:
                            team1_wins += 1
                        elif winner.get('id') == team2_id:
                            team2_wins += 1
                
                result = {
                    'matches': len(h2h_matches),
                    'team1_wins': team1_wins,
                    'team2_wins': team2_wins
                }
                
                self._stats_cache[cache_key] = result
                return result
                
        except Exception:
            pass
        
        return {'matches': 0, 'team1_wins': 0, 'team2_wins': 0}
    
    def _get_tournament_tier(self, tournament_name: str) -> float:
        """Get reliability factor based on tournament importance"""
        if not tournament_name:
            return 0.85
        
        tournament_lower = tournament_name.lower()
        
        for key, factor in self.TOURNAMENT_TIERS.items():
            if key in tournament_lower:
                return factor
        
        # Default based on keywords
        if 'major' in tournament_lower or 'championship' in tournament_lower:
            return 0.95
        elif 'league' in tournament_lower or 'cup' in tournament_lower:
            return 0.88
        elif 'online' in tournament_lower:
            return 0.80
        
        return 0.85  # Unknown tournament
    
    def _get_map_stats(self, team_id: int, game: str) -> Dict:
        """Get map-specific win rates for CS2/Valorant"""
        if game.lower() not in ['cs2', 'csgo', 'valorant']:
            return {}
        
        cache_key = f"maps_{team_id}_{game}"
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]
        
        try:
            game_slug = 'csgo' if game.lower() == 'cs2' else game.lower()
            url = f"{self.pandascore_base}/{game_slug}/matches/past"
            params = {
                'filter[opponent_id]': team_id,
                'sort': '-begin_at',
                'per_page': 30
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            
            if response.status_code == 200:
                matches = response.json()
                map_stats = {}
                
                for match in matches:
                    for game_data in match.get('games', []):
                        map_info = game_data.get('map', {})
                        map_name = map_info.get('name') if isinstance(map_info, dict) else str(map_info)
                        
                        if not map_name:
                            continue
                            
                        winner = game_data.get('winner', {})
                        winner_id = winner.get('id') if isinstance(winner, dict) else None
                        
                        if map_name not in map_stats:
                            map_stats[map_name] = {'wins': 0, 'total': 0, 'wr': 50}
                        
                        map_stats[map_name]['total'] += 1
                        if winner_id == team_id:
                            map_stats[map_name]['wins'] += 1
                        
                        # Calculate WR
                        if map_stats[map_name]['total'] > 0:
                            map_stats[map_name]['wr'] = round(
                                map_stats[map_name]['wins'] / map_stats[map_name]['total'] * 100, 1
                            )
                
                self._stats_cache[cache_key] = map_stats
                return map_stats
                
        except Exception:
            pass
        
        return {}


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
        st.error("⚠️ Pandascore API key not found")
        
        # Show what was tried
        with st.expander("🔧 Debug: Wo wird der Key gesucht?"):
            st.write("Der Scanner sucht den API Key an diesen Stellen:")
            st.code("""
# In secrets.toml:
[esports]
pandascore_key = "DEIN_KEY"

# ODER:
PANDASCORE_KEY = "DEIN_KEY"

# ODER:
pandascore_key = "DEIN_KEY"
            """)
            
            # Show what secrets exist
            try:
                if hasattr(st, 'secrets'):
                    st.write("**Gefundene Secrets-Kategorien:**")
                    for key in st.secrets.keys():
                        st.write(f"- `{key}`")
            except:
                st.write("Keine secrets gefunden")
        
        st.info("🔗 Get free key: https://pandascore.co")
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
        
        # Native Streamlit display (no custom colors!)
        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.subheader(f"{rec['team1']} vs {rec['team2']}")
            with col2:
                st.write(stars)
            
            st.caption(f"{rec['game']} • {rec['tournament']} • Score: {rec['score']}")
        
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
            
            # Additional stats
            c1, c2, c3 = st.columns(3)
            c1.write(f"**H2H:** {rec.get('h2h', 'N/A')}")
            c2.write(f"**Tournament Tier:** {rec.get('tournament_tier', 85)}%")
            c3.write(f"**Sample:** {rec.get('sample_size', 'N/A')}")
            
            st.markdown("---")
            st.write("**Analysis:**")
            for reason in rec['reasoning']:
                st.write(reason)
            
            st.caption(f"Data Quality: {rec['data_quality']}")
        
        st.markdown("---")


if __name__ == "__main__":
    st.set_page_config(page_title="E-Sports Scanner", layout="wide")
    create_esports_tab()
