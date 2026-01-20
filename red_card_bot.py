"""
RED CARD BOT - STANDALONE VERSION
==================================
Runs on GitHub Actions every 5 minutes
Sends Telegram alerts when red cards are detected
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Set


class RedCardBot:
    """Standalone red card monitoring bot"""
    
    def __init__(self):
        # API Keys from environment variables
        self.api_key = os.environ.get('API_FOOTBALL_KEY')
        self.telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not self.api_key:
            raise ValueError("❌ API_FOOTBALL_KEY not set!")
        if not self.telegram_token or not self.telegram_chat_id:
            raise ValueError("❌ Telegram credentials not set!")
        
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': self.api_key}
        
        # File to track alerted cards (persists between runs)
        self.state_file = 'alerted_cards.json'
        self.alerted_cards = self._load_state()
    
    def _load_state(self) -> Set[str]:
        """Load previously alerted cards from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Only keep cards from last 24 hours to avoid file growing forever
                    cutoff = datetime.now().timestamp() - (24 * 60 * 60)
                    return {k for k, v in data.items() if v > cutoff}
            return set()
        except:
            return set()
    
    def _save_state(self):
        """Save alerted cards to file"""
        try:
            # Save with timestamp
            data = {card_id: datetime.now().timestamp() 
                   for card_id in self.alerted_cards}
            with open(self.state_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Could not save state: {e}")
    
    def get_live_matches(self) -> List[Dict]:
        """Get all live matches"""
        try:
            print("📡 Fetching live matches...")
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            if response.status_code == 200:
                matches = response.json().get('response', [])
                print(f"   Found {len(matches)} live matches")
                return matches
            else:
                print(f"❌ API Error: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error fetching matches: {e}")
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
            print(f"❌ Error checking events: {e}")
            return []
    
    def send_telegram_alert(self, card_info: Dict):
        """Send Telegram notification"""
        match = card_info['match']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        score = f"{match['goals']['home']}-{match['goals']['away']}"
        league = match['league']['name']
        country = match['league']['country']
        
        message = f"""
🔴 *RED CARD ALERT!*

*Player:* {card_info['player']}
*Team:* {card_info['team']}
*Match:* {home} vs {away}
*Score:* {score}
*Minute:* {card_info['minute']}'
*League:* {country} - {league}

💡 *Betting Impact:*
✅ Team down to 10 men
✅ BTTS more likely (desperate attack)
❌ Over 2.5 less likely (defensive focus)
✅ Opponent win more likely

⚡ Quick action needed for live betting!

🕒 Alert sent: {datetime.now().strftime('%H:%M:%S')}
        """
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            response = requests.post(url, json={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Telegram alert sent for {card_info['player']}")
            else:
                print(f"❌ Telegram failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Telegram error: {e}")
    
    def scan(self):
        """Main scan function"""
        print("\n" + "="*60)
        print(f"🔍 RED CARD SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Get live matches
        live_matches = self.get_live_matches()
        
        if not live_matches:
            print("⚽ No live matches at the moment")
            return
        
        # Check each match
        total_red_cards = 0
        
        for match in live_matches:
            home = match['teams']['home']['name']
            away = match['teams']['away']['name']
            minute = match['fixture']['status']['elapsed'] or 0
            
            # Only check matches that are actually playing (not halftime, etc)
            status = match['fixture']['status']['short']
            if status in ['1H', '2H', 'ET', 'P']:  # First half, Second half, Extra time, Penalties
                print(f"   Checking: {home} vs {away} ({minute}')")
                
                red_cards = self.check_match_for_red_cards(match)
                
                if red_cards:
                    for card in red_cards:
                        print(f"\n🔴 RED CARD DETECTED!")
                        print(f"   Player: {card['player']}")
                        print(f"   Team: {card['team']}")
                        print(f"   Match: {home} vs {away}")
                        print(f"   Minute: {card['minute']}'")
                        
                        # Send alert
                        self.send_telegram_alert(card)
                        total_red_cards += 1
        
        # Save state
        self._save_state()
        
        print(f"\n✅ Scan complete!")
        print(f"   Live matches checked: {len(live_matches)}")
        print(f"   New red cards found: {total_red_cards}")
        print(f"   Total tracked cards: {len(self.alerted_cards)}")
        print("="*60 + "\n")


if __name__ == "__main__":
    try:
        bot = RedCardBot()
        bot.scan()
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        exit(1)
