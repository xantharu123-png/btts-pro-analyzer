"""
RED CARD ALERT SYSTEM
=====================
Detects red cards in live matches and sends notifications
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Set
import streamlit as st


class RedCardAlertSystem:
    """System to monitor live matches and alert on red cards"""
    
    def __init__(self, api_football_key: str):
        self.api_key = api_football_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': api_football_key}
        
        # Track red cards we've already alerted for (to avoid duplicates)
        self.alerted_cards: Set[str] = set()
        
        # Telegram config (optional)
        self.telegram_bot_token = None
        self.telegram_chat_id = None
        
        # Email config (optional)
        self.email_config = None
    
    def setup_telegram(self, bot_token: str, chat_id: str):
        """Setup Telegram notifications"""
        self.telegram_bot_token = bot_token
        self.telegram_chat_id = chat_id
        print("✅ Telegram notifications enabled!")
    
    def setup_email(self, smtp_server: str, smtp_port: int, email: str, password: str, to_email: str):
        """Setup Email notifications"""
        self.email_config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'email': email,
            'password': password,
            'to_email': to_email
        }
        print("✅ Email notifications enabled!")
    
    def get_live_matches(self, league_ids: List[int]) -> List[Dict]:
        """Get all live matches for specified leagues"""
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            if response.status_code == 200:
                all_matches = response.json().get('response', [])
                
                # Filter for our leagues
                return [m for m in all_matches 
                       if m.get('league', {}).get('id') in league_ids]
            
            return []
        except Exception as e:
            print(f"❌ Error fetching live matches: {e}")
            return []
    
    def check_for_red_cards(self, match: Dict) -> List[Dict]:
        """Check if match has red card events"""
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
                        # Create unique ID for this card
                        card_id = f"{fixture_id}_{event.get('player', {}).get('id')}_{event.get('time', {}).get('elapsed')}"
                        
                        # Only alert if we haven't seen this card before
                        if card_id not in self.alerted_cards:
                            red_cards.append({
                                'card_id': card_id,
                                'player': event.get('player', {}).get('name', 'Unknown'),
                                'team': event.get('team', {}).get('name', 'Unknown'),
                                'minute': event.get('time', {}).get('elapsed', '?'),
                                'match': match
                            })
                            self.alerted_cards.add(card_id)
            
            return red_cards
            
        except Exception as e:
            print(f"❌ Error checking red cards: {e}")
            return []
    
    def send_browser_alert(self, card_info: Dict):
        """Send browser toast notification"""
        match = card_info['match']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        score = f"{match['goals']['home']}-{match['goals']['away']}"
        
        message = f"""
🔴 RED CARD!

{card_info['player']} ({card_info['team']})
{home} vs {away} ({score})
Minute: {card_info['minute']}'

💡 Betting Tip: Team down to 10 men!
- BTTS more likely
- Over 2.5 less likely
- Opponent win more likely
        """
        
        st.toast(message, icon="🔴")
        st.error(message)
    
    def send_telegram_alert(self, card_info: Dict):
        """Send Telegram notification"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        
        match = card_info['match']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        score = f"{match['goals']['home']}-{match['goals']['away']}"
        
        message = f"""
🔴 *RED CARD ALERT!*

*Player:* {card_info['player']}
*Team:* {card_info['team']}
*Match:* {home} vs {away}
*Score:* {score}
*Minute:* {card_info['minute']}'

💡 *Betting Impact:*
- Team down to 10 men
- BTTS more likely
- Over 2.5 less likely
- Opponent win more likely

⚡ Quick action needed!
        """
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            requests.post(url, json={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            })
            print("✅ Telegram alert sent!")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def send_email_alert(self, card_info: Dict):
        """Send Email notification"""
        if not self.email_config:
            return
        
        match = card_info['match']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        score = f"{match['goals']['home']}-{match['goals']['away']}"
        
        subject = f"🔴 RED CARD: {card_info['player']} - {home} vs {away}"
        
        body = f"""
RED CARD ALERT!

Player: {card_info['player']}
Team: {card_info['team']}
Match: {home} vs {away}
Score: {score}
Minute: {card_info['minute']}'

BETTING IMPACT:
- Team down to 10 men
- BTTS more likely (desperate play)
- Over 2.5 less likely (defensive focus)
- Opponent win more likely

Quick action needed for live betting!

Sent by BTTS Pro Analyzer
        """
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.email_config['email']
            msg['To'] = self.email_config['to_email']
            
            with smtplib.SMTP(self.email_config['smtp_server'], 
                             self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['email'], 
                           self.email_config['password'])
                server.send_message(msg)
            
            print("✅ Email alert sent!")
        except Exception as e:
            print(f"❌ Email error: {e}")
    
    def scan_for_red_cards(self, league_ids: List[int]):
        """Main scanning function - checks all live matches"""
        print(f"\n{'='*60}")
        print(f"🔍 SCANNING FOR RED CARDS...")
        print(f"{'='*60}")
        
        # Get live matches
        live_matches = self.get_live_matches(league_ids)
        print(f"📊 Found {len(live_matches)} live matches")
        
        if not live_matches:
            print("⚽ No live matches at the moment")
            return
        
        # Check each match for red cards
        for match in live_matches:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']
            minute = match['fixture']['status']['elapsed']
            
            print(f"   Checking: {home} vs {away} ({minute}')")
            
            red_cards = self.check_for_red_cards(match)
            
            if red_cards:
                for card in red_cards:
                    print(f"\n🔴 RED CARD DETECTED!")
                    print(f"   Player: {card['player']}")
                    print(f"   Team: {card['team']}")
                    print(f"   Minute: {card['minute']}'")
                    
                    # Send all configured alerts
                    self.send_browser_alert(card)
                    self.send_telegram_alert(card)
                    self.send_email_alert(card)
        
        print(f"\n✅ Scan complete at {datetime.now().strftime('%H:%M:%S')}")


# =============================================================================
# STREAMLIT INTEGRATION
# =============================================================================

def create_red_card_monitor_tab():
    """Create Streamlit tab for red card monitoring"""
    st.header("🔴 Red Card Alert System")
    
    st.markdown("""
    Get **instant notifications** when a red card happens in live matches!
    
    💡 **Why this matters for betting:**
    - Team down to 10 men changes everything
    - BTTS becomes more likely (desperate attack)
    - Over 2.5 becomes less likely (defensive focus)
    - Opponent win becomes more likely
    
    ⚡ **Quick reaction = Better odds!**
    """)
    
    # Settings
    st.subheader("⚙️ Notification Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        enable_browser = st.checkbox("🔔 Browser Alerts", value=True,
                                     help="Show alerts in this browser window")
    
    with col2:
        enable_telegram = st.checkbox("📱 Telegram Alerts", value=False,
                                      help="Send alerts to your Telegram")
    
    # Telegram setup
    if enable_telegram:
        with st.expander("📱 Setup Telegram"):
            st.markdown("""
            **How to setup:**
            1. Message @BotFather on Telegram
            2. Create new bot: `/newbot`
            3. Copy your Bot Token
            4. Message your bot to get Chat ID
            5. Use @userinfobot to get your Chat ID
            """)
            
            telegram_token = st.text_input("Bot Token", type="password")
            telegram_chat_id = st.text_input("Chat ID")
    
    st.markdown("---")
    
    # Start monitoring
    if st.button("🚀 Start Monitoring", type="primary"):
        if 'api' in st.secrets and 'api_football_key' in st.secrets['api']:
            api_key = st.secrets['api']['api_football_key']
            
            # Initialize alert system
            alert_system = RedCardAlertSystem(api_key)
            
            # Setup Telegram if enabled
            if enable_telegram and telegram_token and telegram_chat_id:
                alert_system.setup_telegram(telegram_token, telegram_chat_id)
            
            # Get league IDs (use your existing leagues)
            league_ids = [
                78, 39, 140, 135, 61, 88, 94, 203, 40, 79, 262, 71,  # Top leagues
                2, 3, 848,  # European cups
                179, 144, 207, 218,  # EU Expansion
                265, 330, 165, 188, 89, 209, 113, 292, 301  # Goal festivals
            ]
            
            # Monitoring loop
            st.success("✅ Monitoring started! Checking every 30 seconds...")
            
            # Create placeholder for status
            status_placeholder = st.empty()
            alerts_placeholder = st.empty()
            
            while True:
                with status_placeholder.container():
                    st.info(f"🔍 Scanning... {datetime.now().strftime('%H:%M:%S')}")
                
                # Scan for red cards
                alert_system.scan_for_red_cards(league_ids)
                
                # Wait 30 seconds
                time.sleep(30)
        else:
            st.error("❌ API key not configured!")


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Example usage
    api_key = "YOUR_API_KEY"
    
    # Initialize
    alert_system = RedCardAlertSystem(api_key)
    
    # Optional: Setup Telegram
    alert_system.setup_telegram(
        bot_token="YOUR_BOT_TOKEN",
        chat_id="YOUR_CHAT_ID"
    )
    
    # Monitor league IDs
    league_ids = [39, 140, 135, 78]  # PL, La Liga, Serie A, Bundesliga
    
    # Scan every 30 seconds
    while True:
        alert_system.scan_for_red_cards(league_ids)
        time.sleep(30)
