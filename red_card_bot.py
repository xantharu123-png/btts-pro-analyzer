"""
RED CARD BOT - DUAL MODE
=========================
Works as:
1. Standalone bot (GitHub Actions)
2. Streamlit monitoring tab
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Set, Optional

# Streamlit import (optional - only needed for UI mode)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


class RedCardBot:
    """Red card monitoring bot - works standalone or in Streamlit"""
    
    def __init__(self, api_key: str = None, telegram_token: str = None, 
                 telegram_chat_id: str = None, streamlit_mode: bool = False):
        
        self.streamlit_mode = streamlit_mode
        
        # Get credentials (from env or parameters)
        if streamlit_mode:
            # Streamlit mode: use parameters or session state
            self.api_key = api_key
            self.telegram_token = telegram_token
            self.telegram_chat_id = telegram_chat_id
        else:
            # Standalone mode: use environment variables
            self.api_key = os.environ.get('API_FOOTBALL_KEY')
            self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not self.api_key:
            raise ValueError("❌ API_FOOTBALL_KEY not set!")
        if not self.telegram_token or not self.telegram_chat_id:
            if not streamlit_mode:
                raise ValueError("❌ Telegram credentials not set!")
        
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': self.api_key}
        
        # State tracking
        if streamlit_mode and STREAMLIT_AVAILABLE:
            # Use Streamlit session state
            if 'alerted_cards' not in st.session_state:
                st.session_state.alerted_cards = set()
            self.alerted_cards = st.session_state.alerted_cards
        else:
            # Use file-based state
            self.state_file = 'alerted_cards.json'
            self.alerted_cards = self._load_state()
    
    def _load_state(self) -> Set[str]:
        """Load previously alerted cards from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Only keep cards from last 24 hours
                    cutoff = datetime.now().timestamp() - (24 * 60 * 60)
                    return {k for k, v in data.items() if v > cutoff}
            return set()
        except:
            return set()
    
    def _save_state(self):
        """Save alerted cards to file"""
        if self.streamlit_mode:
            # Streamlit: state is already in session_state
            return
        
        try:
            data = {card_id: datetime.now().timestamp() 
                   for card_id in self.alerted_cards}
            with open(self.state_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Could not save state: {e}")
    
    def get_live_matches(self, league_ids: List[int] = None) -> List[Dict]:
        """Get all live matches (optionally filtered by leagues)"""
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
                
                # Filter by leagues if specified
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
            
            # Get match events
            response = requests.get(
                f"{self.base_url}/fixtures/events",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            if response.status_code == 200:
                events = response.json().get('response', [])
                
                # Look for red cards
                for event in events:
                    event_type = event.get('type', '')
                    event_detail = event.get('detail', '')
                    
                    if event_type == 'Card' and event_detail == 'Red Card':
                        # Create unique ID
                        player_id = event.get('player', {}).get('id', 'unknown')
                        minute = event.get('time', {}).get('elapsed', 0)
                        card_id = f"{fixture_id}_{player_id}_{minute}"
                        
                        # Only process if new
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
    
    def send_telegram_alert(self, card_info: Dict) -> bool:
        """Send Telegram notification with REAL predictions"""
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        
        match = card_info['match']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        home_goals = match['goals']['home'] or 0
        away_goals = match['goals']['away'] or 0
        score = f"{home_goals}-{away_goals}"
        league = match['league']['name']
        country = match['league']['country']
        minute = card_info['minute']
        
        # Determine which team got the red card
        red_team_name = card_info['team']
        if red_team_name == home:
            red_card_team = 'home'
            opponent_name = away
        else:
            red_card_team = 'away'
            opponent_name = home
        
        # =====================================================
        # ECHTE BERECHNUNGEN!
        # =====================================================
        
        # Verbleibende Zeit
        total_time = 93  # inkl. Nachspielzeit
        remaining = max(0, total_time - minute)
        
        # Basis Tor-Wahrscheinlichkeiten
        BASE_GOAL_RATE = 0.028  # pro Minute
        OPPONENT_BOOST = 1.45   # 11-Mann +45%
        RED_PENALTY = 0.40      # 10-Mann nur 40%
        
        opponent_rate = BASE_GOAL_RATE * OPPONENT_BOOST
        red_team_rate = BASE_GOAL_RATE * RED_PENALTY
        
        # Wahrscheinlichkeiten berechnen
        any_goal_prob = 1 - ((1 - opponent_rate) ** remaining * (1 - red_team_rate) ** remaining)
        no_goal_prob = 1 - any_goal_prob
        
        total_rate = opponent_rate + red_team_rate
        if total_rate > 0:
            opponent_scores = (opponent_rate / total_rate) * any_goal_prob
            red_team_scores = (red_team_rate / total_rate) * any_goal_prob
        else:
            opponent_scores = 0
            red_team_scores = 0
        
        # Endstand-Prognose (vereinfacht)
        if remaining >= 30:
            opp_wins = 0.48
            draw_prob = 0.32
            red_wins = 0.20
        elif remaining >= 15:
            opp_wins = 0.38
            draw_prob = 0.38
            red_wins = 0.24
        elif remaining >= 5:
            opp_wins = 0.28
            draw_prob = 0.48
            red_wins = 0.24
        else:
            opp_wins = 0.15
            draw_prob = 0.70
            red_wins = 0.15
        
        # Spielstand-Anpassung
        goal_diff = home_goals - away_goals
        if red_card_team == 'home' and goal_diff < 0:
            opp_wins *= 1.2
            red_wins *= 0.6
        elif red_card_team == 'away' and goal_diff > 0:
            opp_wins *= 1.15
            red_wins *= 0.65
        
        # Normalisieren
        total = opp_wins + draw_prob + red_wins
        opp_wins /= total
        draw_prob /= total
        red_wins /= total
        
        # Erwartete Zeit bis Tor
        combined_rate = opponent_rate + red_team_rate
        if combined_rate > 0:
            exp_minutes = min(1 / combined_rate, remaining)
        else:
            exp_minutes = remaining
        
        # Zu spät für Wetten?
        too_late = remaining <= 3
        
        # =====================================================
        # NACHRICHT FORMATIEREN
        # =====================================================
        
        message = f"""
🔴 *ROTE KARTE - LIVE ANALYSE*

*Spieler:* {card_info['player']}
*Team:* {red_team_name}
*Match:* {home} vs {away}
*Spielstand:* {score}
*Minute:* {minute}'
*Liga:* {country} - {league}

━━━━━━━━━━━━━━━━━━

📊 *WAS PASSIERT ALS NÄCHSTES?*
(~{remaining} Minuten verbleibend)

*Nächstes Tor:* {any_goal_prob*100:.0f}%
├─ {opponent_name}: {opponent_scores*100:.0f}%
├─ {red_team_name}: {red_team_scores*100:.0f}%
└─ Kein Tor mehr: {no_goal_prob*100:.0f}%

⏱️ *Zeit bis Tor:* ~{exp_minutes:.0f} Min

━━━━━━━━━━━━━━━━━━

🏆 *ENDSTAND-PROGNOSE:*
{opponent_name} gewinnt: {opp_wins*100:.0f}%
Unentschieden: {draw_prob*100:.0f}%
{red_team_name} gewinnt: {red_wins*100:.0f}%

━━━━━━━━━━━━━━━━━━

💡 *WETT-EMPFEHLUNGEN:*
"""
        
        if too_late:
            message += "\n⚠️ ZU SPÄT - Spiel fast vorbei!"
        else:
            if opponent_scores >= 0.55:
                message += f"\n✅ {opponent_name} nächstes Tor: {opponent_scores*100:.0f}%"
            if opp_wins >= 0.45 and remaining >= 20:
                message += f"\n✅ {opponent_name} gewinnt: {opp_wins*100:.0f}%"
            if no_goal_prob >= 0.35 and remaining >= 15:
                message += f"\n✅ Keine weiteren Tore: {no_goal_prob*100:.0f}%"
        
        message += "\n\n🚫 *VERMEIDEN:*"
        if red_team_scores < 0.25:
            message += f"\n❌ BTTS (10-Mann trifft nur {red_team_scores*100:.0f}%)"
        if red_wins < 0.25:
            message += f"\n❌ {red_team_name} gewinnt ({red_wins*100:.0f}%)"
        
        message += f"\n\n🕒 {datetime.now().strftime('%H:%M:%S')}"
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=10)
            
            if response.status_code == 200:
                msg = f"✅ Telegram alert sent for {card_info['player']}"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.success(msg)
                else:
                    print(msg)
                return True
            else:
                msg = f"❌ Telegram failed: {response.status_code}"
                if self.streamlit_mode and STREAMLIT_AVAILABLE:
                    st.warning(msg)
                else:
                    print(msg)
                return False
        except Exception as e:
            msg = f"❌ Telegram error: {e}"
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.error(msg)
            else:
                print(msg)
            return False
    
    def scan(self, league_ids: List[int] = None) -> Dict:
        """Main scan function"""
        if not self.streamlit_mode:
            print("\n" + "="*60)
            print(f"🔍 RED CARD SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*60)
        
        # Get live matches
        live_matches = self.get_live_matches(league_ids)
        
        results = {
            'live_matches': len(live_matches),
            'red_cards_found': 0,
            'alerts_sent': 0,
            'matches': []
        }
        
        if not live_matches:
            msg = "⚽ No live matches at the moment"
            if self.streamlit_mode and STREAMLIT_AVAILABLE:
                st.info(msg)
            else:
                print(msg)
            return results
        
        # Check each match
        for match in live_matches:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']
            minute = match['fixture']['status']['elapsed'] or 0
            status = match['fixture']['status']['short']
            
            # Only check matches that are actually playing
            if status in ['1H', '2H', 'ET', 'P']:
                results['matches'].append({
                    'home': home,
                    'away': away,
                    'minute': minute,
                    'score': f"{match['goals']['home']}-{match['goals']['away']}"
                })
                
                if not self.streamlit_mode:
                    print(f"   Checking: {home} vs {away} ({minute}')")
                
                red_cards = self.check_match_for_red_cards(match)
                
                if red_cards:
                    for card in red_cards:
                        results['red_cards_found'] += 1
                        
                        # Display alert
                        alert_msg = f"""
🔴 RED CARD DETECTED!
   Player: {card['player']}
   Team: {card['team']}
   Match: {home} vs {away}
   Minute: {card['minute']}'
                        """
                        
                        if self.streamlit_mode and STREAMLIT_AVAILABLE:
                            st.success(alert_msg)
                        else:
                            print(alert_msg)
                        
                        # Send Telegram
                        if self.send_telegram_alert(card):
                            results['alerts_sent'] += 1
        
        # Save state
        self._save_state()
        
        if not self.streamlit_mode:
            print(f"\n✅ Scan complete!")
            print(f"   Live matches checked: {results['live_matches']}")
            print(f"   New red cards found: {results['red_cards_found']}")
            print(f"   Total tracked cards: {len(self.alerted_cards)}")
            print("="*60 + "\n")
        
        return results


# ============================================================================
# STREAMLIT UI
# ============================================================================

def create_red_card_monitor_tab():
    """Create Streamlit monitoring tab"""
    
    if not STREAMLIT_AVAILABLE:
        st.error("❌ Streamlit not available!")
        return
    
    st.header("🔴 Red Card Monitor")
    
    # Description
    st.markdown("""
    **Automatische Benachrichtigung bei roten Karten!**
    
    💡 **Warum wichtig:**
    - Team mit 10 Mann = Game-Changer
    - BTTS wahrscheinlicher
    - Over 2.5 unwahrscheinlicher
    - Gegner-Sieg wahrscheinlicher
    """)
    
    st.markdown("---")
    
    # Settings
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ Einstellungen")
        
        # Check Telegram
        telegram_configured = False
        telegram_token = None
        telegram_chat_id = None
        
        if 'telegram' in st.secrets:
            telegram_token = st.secrets['telegram'].get('bot_token')
            telegram_chat_id = st.secrets['telegram'].get('chat_id')
            telegram_configured = telegram_token and telegram_chat_id
        
        if telegram_configured:
            st.success("✅ Telegram konfiguriert")
        else:
            st.warning("⚠️ Telegram nicht konfiguriert")
        
        # Scan interval
        scan_interval = st.slider(
            "Scan Interval (Sekunden)",
            min_value=30,
            max_value=300,
            value=60,
            step=30
        )
    
    with col2:
        st.subheader("📊 Status")
        status_placeholder = st.empty()
        stats_placeholder = st.empty()
    
    st.markdown("---")
    
    # Initialize session state
    if 'monitoring_active' not in st.session_state:
        st.session_state.monitoring_active = False
    
    # Control buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Start", type="primary", disabled=st.session_state.monitoring_active):
            st.session_state.monitoring_active = True
            st.rerun()
    
    with col2:
        if st.button("⏸️ Stop", disabled=not st.session_state.monitoring_active):
            st.session_state.monitoring_active = False
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset"):
            st.session_state.alerted_cards = set()
            st.success("✅ Zurückgesetzt!")
    
    st.markdown("---")
    
    # Matches display
    matches_placeholder = st.empty()
    
    # Monitoring loop
    if st.session_state.monitoring_active:
        
        # Get API key
        api_key = None
        if 'api' in st.secrets and 'api_football_key' in st.secrets['api']:
            api_key = st.secrets['api']['api_football_key']
        
        if not api_key:
            st.error("❌ API Key nicht gefunden!")
            st.session_state.monitoring_active = False
            st.stop()
        
        # Initialize bot
        bot = RedCardBot(
            api_key=api_key,
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
            streamlit_mode=True
        )
        
        # League IDs
        league_ids = [
            78, 39, 140, 135, 61,  # Top 5
            2, 3,  # CL, EL
            88, 94, 203, 40, 79
        ]
        
        # Status
        with status_placeholder.container():
            st.info(f"✅ Monitoring aktiv - Scan in {scan_interval}s")
        
        # Scan
        import time
        results = bot.scan(league_ids)
        
        # Stats
        with stats_placeholder.container():
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Live", results['live_matches'])
            with c2:
                st.metric("Rote Karten", results['red_cards_found'])
            with c3:
                st.metric("Alerts", results['alerts_sent'])
            with c4:
                st.metric("Getrackt", len(st.session_state.alerted_cards))
        
        # Matches
        if results['matches']:
            with matches_placeholder.container():
                st.subheader("⚽ Live Spiele")
                for m in results['matches']:
                    st.text(f"{m['home']} vs {m['away']} | {m['score']} | {m['minute']}'")
        else:
            with matches_placeholder.container():
                st.info("Keine Live-Spiele")
        
        # Auto-refresh
        time.sleep(scan_interval)
        st.rerun()
    
    else:
        with status_placeholder.container():
            st.warning("⏸️ Monitoring gestoppt")


# ============================================================================
# MAIN - Dual mode support
# ============================================================================

if __name__ == "__main__":
    if STREAMLIT_AVAILABLE:
        # Streamlit mode
        create_red_card_monitor_tab()
    else:
        # Standalone mode (GitHub Actions)
        try:
            bot = RedCardBot()
            bot.scan()
        except Exception as e:
            print(f"❌ FATAL ERROR: {e}")
            exit(1)
