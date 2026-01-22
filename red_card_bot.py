"""
RED CARD BOT - ENHANCED WITH LIVE STATS
=========================================
Verbesserter Bot der:
1. Rote Karten erkennt
2. ECHTE Live-Stats holt (xG, Ballbesitz, Schüsse, etc.)
3. RedCardImpactPredictor mit allen Daten füttert
4. Präzise Vorhersagen macht

KEINE FAKE DATEN - ALLES ECHT!
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Set, Optional

# Import predictor
try:
    from red_card_impact_predictor import RedCardImpactPredictor
    PREDICTOR_AVAILABLE = True
except ImportError:
    PREDICTOR_AVAILABLE = False
    print("⚠️ Warning: red_card_impact_predictor not found, using basic calculations")

# Streamlit import (optional)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


class RedCardBotEnhanced:
    """Enhanced red card bot with real live statistics integration"""
    
    def __init__(self, api_key: str = None, telegram_token: str = None, 
                 telegram_chat_id: str = None, streamlit_mode: bool = False):
        
        self.streamlit_mode = streamlit_mode
        
        # Get credentials
        if streamlit_mode:
            self.api_key = api_key
            self.telegram_token = telegram_token
            self.telegram_chat_id = telegram_chat_id
        else:
            self.api_key = os.environ.get('API_FOOTBALL_KEY')
            self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not self.api_key:
            raise ValueError("❌ API_FOOTBALL_KEY not set!")
        
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': self.api_key}
        
        # Initialize predictor
        if PREDICTOR_AVAILABLE:
            self.predictor = RedCardImpactPredictor()
        else:
            self.predictor = None
        
        # State tracking
        if streamlit_mode and STREAMLIT_AVAILABLE:
            if 'alerted_cards' not in st.session_state:
                st.session_state.alerted_cards = set()
            self.alerted_cards = st.session_state.alerted_cards
        else:
            self.state_file = 'alerted_cards.json'
            self.alerted_cards = self._load_state()
    
    def _load_state(self) -> Set[str]:
        """Load previously alerted cards from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    cutoff = datetime.now().timestamp() - (24 * 60 * 60)
                    return {k for k, v in data.items() if v > cutoff}
            return set()
        except:
            return set()
    
    def _save_state(self):
        """Save alerted cards to file"""
        if self.streamlit_mode:
            return
        
        try:
            data = {card_id: datetime.now().timestamp() 
                   for card_id in self.alerted_cards}
            with open(self.state_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Could not save state: {e}")
    
    def get_live_stats(self, fixture_id: int) -> Optional[Dict]:
        """
        Hole ECHTE Live-Statistiken für ein Spiel
        
        Returns dict with:
        - xg_home, xg_away: Expected Goals
        - shots_home, shots_away: Shots on goal
        - possession_home, possession_away: Ball possession %
        - attacks_home, attacks_away: Total attacks
        - corners_home, corners_away: Corners
        """
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            if response.status_code != 200:
                return None
            
            stats_data = response.json().get('response', [])
            if len(stats_data) < 2:
                return None
            
            # Parse home stats (first team)
            home_stats = stats_data[0].get('statistics', [])
            # Parse away stats (second team)
            away_stats = stats_data[1].get('statistics', [])
            
            def extract_stat(stats_list: list, stat_type: str) -> float:
                """Extract specific stat from API response"""
                for stat in stats_list:
                    if stat.get('type') == stat_type:
                        value = stat.get('value')
                        if value is None:
                            return 0.0
                        # Remove % sign if present
                        if isinstance(value, str):
                            value = value.replace('%', '').strip()
                        try:
                            return float(value)
                        except:
                            return 0.0
                return 0.0
            
            live_stats = {
                # Expected Goals (xG) - möglicherweise nicht in allen APIs verfügbar
                'xg_home': extract_stat(home_stats, 'expected_goals'),
                'xg_away': extract_stat(away_stats, 'expected_goals'),
                
                # Schüsse aufs Tor
                'shots_on_goal_home': extract_stat(home_stats, 'Shots on Goal'),
                'shots_on_goal_away': extract_stat(away_stats, 'Shots on Goal'),
                
                # Ballbesitz
                'possession_home': extract_stat(home_stats, 'Ball Possession'),
                'possession_away': extract_stat(away_stats, 'Ball Possession'),
                
                # Angriffe
                'total_attacks_home': extract_stat(home_stats, 'Total attacks'),
                'total_attacks_away': extract_stat(away_stats, 'Total attacks'),
                
                # Gefährliche Angriffe
                'dangerous_attacks_home': extract_stat(home_stats, 'Dangerous attacks'),
                'dangerous_attacks_away': extract_stat(away_stats, 'Dangerous attacks'),
                
                # Ecken
                'corners_home': extract_stat(home_stats, 'Corner Kicks'),
                'corners_away': extract_stat(away_stats, 'Corner Kicks'),
                
                # Gesamtschüsse
                'total_shots_home': extract_stat(home_stats, 'Total Shots'),
                'total_shots_away': extract_stat(away_stats, 'Total Shots'),
            }
            
            return live_stats
            
        except Exception as e:
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.warning(f"⚠️ Could not fetch live stats: {e}")
            else:
                print(f"⚠️ Could not fetch live stats: {e}")
            return None
    
    def get_live_matches(self, league_ids: List[int] = None) -> List[Dict]:
        """Get all live matches"""
        try:
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.write("📡 Fetching live matches...")
            else:
                print("📡 Fetching live matches...")
            
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            if response.status_code == 200:
                matches = response.json().get('response', [])
                
                if league_ids:
                    matches = [m for m in matches 
                             if m.get('league', {}).get('id') in league_ids]
                
                msg = f"   Found {len(matches)} live matches"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.write(msg)
                else:
                    print(msg)
                
                return matches
            else:
                msg = f"❌ API Error: {response.status_code}"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.error(msg)
                else:
                    print(msg)
                return []
        except Exception as e:
            msg = f"❌ Error fetching matches: {e}"
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.error(msg)
            else:
                print(msg)
            return []
    
    def check_match_for_red_cards(self, match: Dict) -> List[Dict]:
        """Check single match for red card events"""
        red_cards = []
        
        try:
            fixture_id = match['fixture']['id']
            
            response = requests.get(
                f"{self.base_url}/fixtures/events",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            if response.status_code == 200:
                events = response.json().get('response', [])
                
                for event in events:
                    event_type = event.get('type', '')
                    event_detail = event.get('detail', '')
                    
                    if event_type == 'Card' and event_detail == 'Red Card':
                        player_id = event.get('player', {}).get('id', 'unknown')
                        minute = event.get('time', {}).get('elapsed', 0)
                        card_id = f"{fixture_id}_{player_id}_{minute}"
                        
                        if card_id not in self.alerted_cards:
                            red_cards.append({
                                'card_id': card_id,
                                'player': event.get('player', {}).get('name', 'Unknown'),
                                'team': event.get('team', {}).get('name', 'Unknown'),
                                'minute': minute,
                                'match': match
                            })
                            self.alerted_cards.add(card_id)
            
            return red_cards
        except Exception as e:
            msg = f"❌ Error checking events: {e}"
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.error(msg)
            else:
                print(msg)
            return []
    
    def send_telegram_alert_with_stats(self, card_info: Dict) -> bool:
        """
        Send enhanced Telegram alert with REAL live stats and predictions
        """
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        
        match = card_info['match']
        fixture_id = match['fixture']['id']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        home_goals = match['goals']['home'] or 0
        away_goals = match['goals']['away'] or 0
        score = f"{home_goals}-{away_goals}"
        league = match['league']['name']
        country = match['league']['country']
        minute = card_info['minute']
        
        # Determine red card team
        red_team_name = card_info['team']
        if red_team_name == home:
            red_card_team = 'home'
            opponent_name = away
        else:
            red_card_team = 'away'
            opponent_name = home
        
        # =====================================================
        # HOLE ECHTE LIVE-STATS!
        # =====================================================
        
        if self.streamlit_mode and STREAMLIT_AVAILABLE:
            st.write(f"📊 Fetching live stats for fixture {fixture_id}...")
        else:
            print(f"📊 Fetching live stats for fixture {fixture_id}...")
        
        live_stats = self.get_live_stats(fixture_id)
        
        # =====================================================
        # BERECHNE MIT PREDICTOR (falls verfügbar)
        # =====================================================
        
        if self.predictor and live_stats:
            # Use full predictor with live stats
            prediction = self.predictor.predict(
                minute=minute,
                home_goals=home_goals,
                away_goals=away_goals,
                red_card_team=red_card_team,
                live_stats=live_stats  # ← JETZT MIT ECHTEN STATS!
            )
            
            # Format prediction
            message = self.predictor.format_prediction(
                prediction, home, away
            )
            
            # Add live stats to message
            if live_stats:
                stats_text = f"""
━━━━━━━━━━━━━━━━━━

📊 *LIVE STATISTIKEN:*

*Ballbesitz:*
{home}: {live_stats['possession_home']:.0f}%
{away}: {live_stats['possession_away']:.0f}%

*Schüsse aufs Tor:*
{home}: {live_stats['shots_on_goal_home']:.0f}
{away}: {live_stats['shots_on_goal_away']:.0f}

*Angriffe:*
{home}: {live_stats['total_attacks_home']:.0f}
{away}: {live_stats['total_attacks_away']:.0f}

*Gefährliche Angriffe:*
{home}: {live_stats['dangerous_attacks_home']:.0f}
{away}: {live_stats['dangerous_attacks_away']:.0f}

*Ecken:*
{home}: {live_stats['corners_home']:.0f}
{away}: {live_stats['corners_away']:.0f}
"""
                # Insert stats before recommendations
                message = message.replace("💡 *WETT-EMPFEHLUNGEN:*", 
                                        stats_text + "\n💡 *WETT-EMPFEHLUNGEN:*")
        
        else:
            # Fallback: basic calculation without predictor
            message = self._create_basic_alert(
                card_info, home, away, home_goals, away_goals,
                score, league, country, minute, red_card_team,
                opponent_name, red_team_name, live_stats
            )
        
        # Send to Telegram
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=10)
            
            if response.status_code == 200:
                msg = f"✅ Enhanced alert sent for {card_info['player']}"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.success(msg)
                else:
                    print(msg)
                return True
            else:
                msg = f"❌ Telegram error: {response.status_code}"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.error(msg)
                else:
                    print(msg)
                return False
        except Exception as e:
            msg = f"❌ Error sending alert: {e}"
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.error(msg)
            else:
                print(msg)
            return False
    
    def _create_basic_alert(self, card_info, home, away, home_goals, away_goals,
                           score, league, country, minute, red_card_team,
                           opponent_name, red_team_name, live_stats):
        """Fallback alert without predictor"""
        
        remaining = max(0, 93 - minute)
        
        message = f"""
🔴 *ROTE KARTE - ENHANCED*

*Spieler:* {card_info['player']}
*Team:* {red_team_name}
*Match:* {home} vs {away}
*Spielstand:* {score}
*Minute:* {minute}'
*Liga:* {country} - {league}

━━━━━━━━━━━━━━━━━━

⏱️ *~{remaining} Minuten verbleibend*
"""
        
        if live_stats:
            message += f"""
📊 *LIVE STATISTIKEN:*

*Ballbesitz:*
{home}: {live_stats['possession_home']:.0f}%
{away}: {live_stats['possession_away']:.0f}%

*Schüsse aufs Tor:*
{home}: {live_stats['shots_on_goal_home']:.0f}
{away}: {live_stats['shots_on_goal_away']:.0f}

*Angriffe:*
{home}: {live_stats['total_attacks_home']:.0f}
{away}: {live_stats['total_attacks_away']:.0f}
"""
        
        message += f"\n🕒 {datetime.now().strftime('%H:%M:%S')}"
        
        return message
    
    def monitor_loop(self, league_ids: List[int] = None, 
                    check_interval: int = 60):
        """Main monitoring loop"""
        
        print("🚀 Enhanced Red Card Bot started!")
        print(f"   Checking every {check_interval} seconds")
        if league_ids:
            print(f"   Monitoring leagues: {league_ids}")
        print("")
        
        while True:
            try:
                matches = self.get_live_matches(league_ids)
                
                for match in matches:
                    red_cards = self.check_match_for_red_cards(match)
                    
                    for card in red_cards:
                        print(f"\n🔴 RED CARD DETECTED!")
                        print(f"   Player: {card['player']}")
                        print(f"   Team: {card['team']}")
                        
                        self.send_telegram_alert_with_stats(card)
                
                self._save_state()
                
                import time
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n👋 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                import time
                time.sleep(check_interval)


# =====================================================
# STREAMLIT TAB FUNCTION
# =====================================================

def create_red_card_monitor_tab_enhanced():
    """Streamlit tab with enhanced monitoring"""
    
    if not STREAMLIT_AVAILABLE:
        st.error("Streamlit not available!")
        return
    
    st.title("🔴 Red Card Monitor - ENHANCED")
    st.caption("Mit ECHTEN Live-Statistiken (xG, Ballbesitz, Schüsse, etc.)")
    
    # API Key
    api_key = st.text_input(
        "API-Football Key",
        type="password",
        help="Your API key from api-football.com"
    )
    
    if not api_key:
        st.warning("⚠️ Bitte API Key eingeben!")
        return
    
    # Initialize bot
    try:
        bot = RedCardBotEnhanced(
            api_key=api_key,
            streamlit_mode=True
        )
        
        # League selection
        st.subheader("Liga Auswahl")
        
        top_leagues = {
            'Premier League': 39,
            'La Liga': 140,
            'Bundesliga': 78,
            'Serie A': 135,
            'Ligue 1': 61,
            'Champions League': 2,
            'Europa League': 3
        }
        
        selected = st.multiselect(
            "Zu überwachende Ligen",
            options=list(top_leagues.keys()),
            default=['Premier League', 'Bundesliga']
        )
        
        league_ids = [top_leagues[name] for name in selected] if selected else None
        
        # Manual check
        if st.button("🔍 Jetzt nach Roten Karten suchen", type="primary"):
            with st.spinner("Suche Live-Spiele..."):
                matches = bot.get_live_matches(league_ids)
                
                if not matches:
                    st.info("Keine Live-Spiele gefunden")
                else:
                    st.success(f"Gefunden: {len(matches)} Live-Spiele")
                    
                    for match in matches:
                        with st.expander(
                            f"⚽ {match['teams']['home']['name']} vs "
                            f"{match['teams']['away']['name']} "
                            f"({match['goals']['home']}-{match['goals']['away']})"
                        ):
                            red_cards = bot.check_match_for_red_cards(match)
                            
                            if red_cards:
                                for card in red_cards:
                                    st.error(f"🔴 ROTE KARTE: {card['player']} ({card['team']})")
                                    
                                    # Get and display live stats
                                    fixture_id = match['fixture']['id']
                                    live_stats = bot.get_live_stats(fixture_id)
                                    
                                    if live_stats:
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.metric(
                                                "Ballbesitz Home", 
                                                f"{live_stats['possession_home']:.0f}%"
                                            )
                                            st.metric(
                                                "Schüsse Home",
                                                f"{live_stats['shots_on_goal_home']:.0f}"
                                            )
                                        
                                        with col2:
                                            st.metric(
                                                "Ballbesitz Away",
                                                f"{live_stats['possession_away']:.0f}%"
                                            )
                                            st.metric(
                                                "Schüsse Away",
                                                f"{live_stats['shots_on_goal_away']:.0f}"
                                            )
                            else:
                                st.success("✅ Keine roten Karten in diesem Spiel")
        
        # Auto-refresh option
        st.divider()
        st.subheader("Auto-Refresh")
        
        auto_refresh = st.checkbox("Auto-Refresh aktivieren (alle 60 Sek.)")
        
        if auto_refresh:
            import time
            
            # Create placeholder
            placeholder = st.empty()
            
            while True:
                with placeholder.container():
                    st.info(f"🔄 Letzter Check: {datetime.now().strftime('%H:%M:%S')}")
                    
                    matches = bot.get_live_matches(league_ids)
                    
                    if matches:
                        for match in matches:
                            red_cards = bot.check_match_for_red_cards(match)
                            
                            if red_cards:
                                for card in red_cards:
                                    st.error(
                                        f"🔴 NEUE ROTE KARTE: {card['player']} "
                                        f"({card['team']}) - Minute {card['minute']}'"
                                    )
                
                time.sleep(60)
                
    except Exception as e:
        st.error(f"❌ Fehler beim Initialisieren: {e}")


# =====================================================
# MAIN (für standalone Verwendung)
# =====================================================

if __name__ == "__main__":
    # Example: Monitor top leagues
    bot = RedCardBotEnhanced()
    
    top_leagues = [39, 140, 78, 135, 61]  # EPL, LaLiga, Bundesliga, SerieA, Ligue1
    
    bot.monitor_loop(league_ids=top_leagues, check_interval=60)
