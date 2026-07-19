"""Red-card event monitor with optional live fixture statistics.

Available API fields feed an explicitly uncalibrated impact model. Missing
fields remain missing rather than being converted into observed zeroes.
"""

import os
import json
import math
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Import predictor
try:
    from red_card_impact_predictor import RedCardImpactPredictor
    PREDICTOR_AVAILABLE = True
except ImportError:
    PREDICTOR_AVAILABLE = False
    print("Warning: red_card_impact_predictor not found; alerts contain event data only")

# Streamlit import (optional)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


def _format_stat(value, decimals: int = 0, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{numeric:.{decimals}f}{suffix}" if math.isfinite(numeric) else "n/a"


class RedCardBotEnhanced:
    """Enhanced red card bot with real live statistics integration"""

    MODEL_END_MINUTE = 93
    
    def __init__(self, api_key: str = None, telegram_token: str = None, 
                 telegram_chat_id: str = None, streamlit_mode: bool = False):
        
        self.streamlit_mode = streamlit_mode
        self.api_key = api_key or os.environ.get('API_FOOTBALL_KEY')
        self.telegram_token = telegram_token or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = telegram_chat_id or os.environ.get('TELEGRAM_CHAT_ID')
        self.errors: List[Dict[str, str]] = []
        
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
                st.session_state.alerted_cards = {}
            elif not isinstance(st.session_state.alerted_cards, dict):
                now = datetime.now().timestamp()
                st.session_state.alerted_cards = {
                    card_id: now for card_id in st.session_state.alerted_cards
                }
            self.alerted_cards = st.session_state.alerted_cards
        else:
            self.state_file = 'alerted_cards.json'
            self.alerted_cards = self._load_state()
    
    def _load_state(self) -> Dict[str, float]:
        """Load previously alerted cards from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        return {}
                    cutoff = datetime.now().timestamp() - (24 * 60 * 60)
                    return {
                        str(card_id): float(timestamp)
                        for card_id, timestamp in data.items()
                        if isinstance(timestamp, (int, float)) and timestamp > cutoff
                    }
            return {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}
    
    def _save_state(self):
        """Save alerted cards to file"""
        if self.streamlit_mode:
            return
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.alerted_cards, f)
        except Exception as e:
            print(f"WARNING: Could not save state: {e}")

    def _mark_alerted(self, card_id: str) -> None:
        self.alerted_cards[card_id] = datetime.now().timestamp()

    def _record_error(self, operation: str, message: str) -> None:
        self.errors.append({'operation': operation, 'message': str(message)})
        if not self.streamlit_mode:
            print(f"WARNING: {operation}: {message}")

    def _response_items(self, response, operation: str) -> Optional[List[Dict]]:
        if response.status_code != 200:
            self._record_error(operation, f"HTTP {response.status_code}")
            return None
        try:
            payload = response.json()
        except ValueError:
            self._record_error(operation, "invalid JSON")
            return None
        if not isinstance(payload, dict):
            self._record_error(operation, "invalid provider payload")
            return None
        provider_errors = payload.get('errors')
        if provider_errors:
            self._record_error(operation, str(provider_errors))
            return None
        items = payload.get('response')
        if not isinstance(items, list):
            self._record_error(operation, "invalid response payload")
            return None
        if any(not isinstance(item, dict) for item in items):
            self._record_error(operation, "invalid response entries")
            return None
        return items

    @classmethod
    def model_snapshot_minute(cls, match: Dict) -> Optional[int]:
        """Return the current regulation-time minute used by the impact model."""
        if not isinstance(match, dict):
            return None
        fixture = match.get('fixture')
        if not isinstance(fixture, dict):
            return None
        status = fixture.get('status')
        if not isinstance(status, dict):
            return None
        minute = status.get('elapsed')
        if (
            isinstance(minute, bool)
            or not isinstance(minute, int)
            or not 0 <= minute <= cls.MODEL_END_MINUTE
        ):
            return None
        return minute

    @staticmethod
    def _live_match_identity(match: Dict) -> Optional[tuple[int, int, int, int]]:
        if not isinstance(match, dict):
            return None
        fixture = match.get('fixture')
        league = match.get('league')
        teams = match.get('teams')
        goals = match.get('goals')
        if not all(isinstance(value, dict) for value in (fixture, league, teams, goals)):
            return None
        home = teams.get('home')
        away = teams.get('away')
        status = fixture.get('status')
        if not isinstance(home, dict) or not isinstance(away, dict) or not isinstance(status, dict):
            return None
        fixture_id = fixture.get('id')
        league_id = league.get('id')
        home_id = home.get('id')
        away_id = away.get('id')
        elapsed = status.get('elapsed')
        home_score = goals.get('home')
        away_score = goals.get('away')
        if (
            any(
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in (fixture_id, league_id, home_id, away_id)
            )
            or home_id == away_id
            or isinstance(elapsed, bool)
            or not isinstance(elapsed, int)
            or not 0 <= elapsed <= 120
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 30
                for value in (home_score, away_score)
            )
        ):
            return None
        return fixture_id, league_id, home_id, away_id
    
    def get_live_stats(
        self,
        fixture_id: int,
        home_team_id: Optional[int] = None,
        away_team_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """
        Hole ECHTE Live-Statistiken für ein Spiel
        
        Returns dict with:
        - xg_home, xg_away: Expected Goals
        - shots_home, shots_away: Shots on goal
        - possession_home, possession_away: Ball possession %
        - attacks_home, attacks_away: Total attacks
        - corners_home, corners_away: Corners
        """
        if (
            isinstance(fixture_id, bool)
            or not isinstance(fixture_id, int)
            or fixture_id <= 0
            or isinstance(home_team_id, bool)
            or isinstance(away_team_id, bool)
            or not isinstance(home_team_id, int)
            or not isinstance(away_team_id, int)
            or home_team_id <= 0
            or away_team_id <= 0
            or home_team_id == away_team_id
        ):
            self._record_error('live_stats', 'invalid identifiers')
            return None
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/statistics",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            stats_data = self._response_items(response, 'live_stats')
            if stats_data is None:
                return None
            if len(stats_data) < 2:
                return None

            stats_by_team = {}
            for item in stats_data:
                if not isinstance(item, dict):
                    continue
                team = item.get('team')
                statistics = item.get('statistics')
                team_id = team.get('id') if isinstance(team, dict) else None
                if (
                    isinstance(team_id, int)
                    and not isinstance(team_id, bool)
                    and team_id > 0
                    and isinstance(statistics, list)
                    and team_id not in stats_by_team
                ):
                    stats_by_team[team_id] = statistics
            home_stats = stats_by_team.get(home_team_id)
            away_stats = stats_by_team.get(away_team_id)
            if home_stats is None or away_stats is None:
                return None
            
            def extract_stat(stats_list: list, stat_type: str) -> Optional[float]:
                """Extract specific stat from API response"""
                for stat in stats_list:
                    if not isinstance(stat, dict):
                        continue
                    if stat.get('type') == stat_type:
                        value = stat.get('value')
                        if value is None or isinstance(value, bool):
                            return None
                        # Remove % sign if present
                        if isinstance(value, str):
                            value = value.replace('%', '').strip()
                        try:
                            numeric = float(value)
                        except (TypeError, ValueError):
                            return None
                        if stat_type == 'Ball Possession':
                            return numeric if math.isfinite(numeric) and 0 <= numeric <= 100 else None
                        if stat_type == 'expected_goals':
                            return numeric if math.isfinite(numeric) and 0 <= numeric <= 20 else None
                        return (
                            numeric
                            if math.isfinite(numeric)
                            and 0 <= numeric <= 5000
                            and numeric.is_integer()
                            else None
                        )
                return None
            
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
            self._record_error('live_stats', str(e))
            return None
    
    def get_live_matches(self, league_ids: List[int] = None) -> List[Dict]:
        """Get all live matches"""
        if league_ids is not None and (
            not isinstance(league_ids, list)
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
                for value in league_ids
            )
        ):
            self._record_error('live_matches', 'invalid league scope')
            return []
        try:
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self.headers,
                params={'live': 'all'},
                timeout=15
            )
            
            matches = self._response_items(response, 'live_matches')
            if matches is not None:
                matches = [
                    match
                    for match in matches
                    if self._live_match_identity(match) is not None
                ]
                if league_ids is not None:
                    allowed_leagues = set(league_ids)
                    matches = [
                        match for match in matches
                        if isinstance(match, dict)
                        and isinstance(match.get('league'), dict)
                        and match['league'].get('id') in allowed_leagues
                    ]
                
                return matches
            return []
        except Exception as e:
            self._record_error('live_matches', str(e))
            return []
    
    def check_match_for_red_cards(self, match: Dict) -> List[Dict]:
        """Check single match for red card events"""
        red_cards = []
        identity = self._live_match_identity(match)
        if identity is None:
            self._record_error('red_card_events', 'invalid live match')
            return red_cards
        fixture_id, _, home_team_id, away_team_id = identity
        
        try:
            response = requests.get(
                f"{self.base_url}/fixtures/events",
                headers=self.headers,
                params={'fixture': fixture_id},
                timeout=15
            )
            
            events = self._response_items(response, f'red_card_events_{fixture_id}')
            if events is not None:
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    event_type = event.get('type', '')
                    event_detail = event.get('detail', '')
                    
                    if event_type == 'Card' and event_detail in {
                        'Red Card',
                        'Second Yellow card',
                    }:
                        player = event.get('player')
                        team = event.get('team')
                        event_time = event.get('time')
                        if not all(isinstance(value, dict) for value in (player, team, event_time)):
                            continue
                        player_id = player.get('id')
                        team_id = team.get('id')
                        minute = event_time.get('elapsed')
                        if (
                            isinstance(player_id, bool)
                            or not isinstance(player_id, int)
                            or player_id <= 0
                            or isinstance(team_id, bool)
                            or not isinstance(team_id, int)
                            or team_id not in {home_team_id, away_team_id}
                            or isinstance(minute, bool)
                            or not isinstance(minute, int)
                            or not 0 <= minute <= 120
                        ):
                            continue
                        raw_extra = event_time.get('extra')
                        extra = 0 if raw_extra is None else raw_extra
                        if (
                            isinstance(extra, bool)
                            or not isinstance(extra, int)
                            or not 0 <= extra <= 30
                        ):
                            continue
                        card_id = f"{fixture_id}_{team_id}_{player_id}_{minute}_{extra}"
                        
                        if card_id not in self.alerted_cards:
                            red_cards.append({
                                'card_id': card_id,
                                'player': str(player.get('name') or 'Unknown'),
                                'team': str(team.get('name') or 'Unknown'),
                                'team_id': team_id,
                                'minute': minute,
                                'extra_minute': extra,
                                'detail': event_detail,
                                'match': match
                            })
            
            return red_cards
        except Exception as e:
            self._record_error('red_card_events', str(e))
            return []
    
    def send_telegram_alert_with_stats(
        self,
        card_info: Dict,
        live_stats: Optional[Dict] = None,
        fetch_live_stats: bool = True,
    ) -> bool:
        """
        Send enhanced Telegram alert with REAL live stats and predictions
        """
        if not self.telegram_token or not self.telegram_chat_id:
            return False
        
        match = card_info['match']
        fixture_id = match['fixture']['id']
        home = match['teams']['home']['name']
        away = match['teams']['away']['name']
        home_id = match['teams']['home']['id']
        away_id = match['teams']['away']['id']
        home_goals = match.get('goals', {}).get('home')
        away_goals = match.get('goals', {}).get('away')
        if home_goals is None or away_goals is None:
            return False
        score = f"{home_goals}-{away_goals}"
        league = match['league']['name']
        country = match['league']['country']
        event_minute = card_info['minute']
        snapshot_minute = self.model_snapshot_minute(match)
        
        # Determine red card team
        red_team_name = card_info['team']
        red_team_id = card_info.get('team_id')
        if red_team_id == home_id:
            red_card_team = 'home'
            opponent_name = away
        elif red_team_id == away_id:
            red_card_team = 'away'
            opponent_name = home
        else:
            return False
        
        # =====================================================
        # HOLE ECHTE LIVE-STATS!
        # =====================================================
        
        if live_stats is None and fetch_live_stats:
            live_stats = self.get_live_stats(fixture_id, home_id, away_id)
        
        # =====================================================
        # BERECHNE MIT PREDICTOR (falls verfügbar)
        # =====================================================
        
        if self.predictor and snapshot_minute is not None:
            prediction = self.predictor.predict(
                minute=snapshot_minute,
                home_goals=home_goals,
                away_goals=away_goals,
                red_card_team=red_card_team,
                live_stats=live_stats
            )
            
            # Format prediction
            message = self.predictor.format_prediction(
                prediction,
                home,
                away,
                red_card_minute=event_minute,
            )
            
            # Add live stats to message
            if live_stats:
                stats_text = f"""
━━━━━━━━━━━━━━━━━━

📊 *LIVE STATISTIKEN:*

*Ballbesitz:*
{home}: {_format_stat(live_stats['possession_home'], suffix='%')}
{away}: {_format_stat(live_stats['possession_away'], suffix='%')}

*Schüsse aufs Tor:*
{home}: {_format_stat(live_stats['shots_on_goal_home'])}
{away}: {_format_stat(live_stats['shots_on_goal_away'])}

*Angriffe:*
{home}: {_format_stat(live_stats['total_attacks_home'])}
{away}: {_format_stat(live_stats['total_attacks_away'])}

*Gefährliche Angriffe:*
{home}: {_format_stat(live_stats['dangerous_attacks_home'])}
{away}: {_format_stat(live_stats['dangerous_attacks_away'])}

*Ecken:*
{home}: {_format_stat(live_stats['corners_home'])}
{away}: {_format_stat(live_stats['corners_away'])}
"""
                message += stats_text
        
        else:
            # Fallback: basic calculation without predictor
            message = self._create_basic_alert(
                card_info, home, away, home_goals, away_goals,
                score, league, country, event_minute, snapshot_minute, red_card_team,
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
                return True
            self._record_error('telegram', f"HTTP {response.status_code}")
            return False
        except Exception as e:
            self._record_error('telegram', str(e))
            return False
    
    def _create_basic_alert(self, card_info, home, away, home_goals, away_goals,
                           score, league, country, event_minute, snapshot_minute,
                           red_card_team,
                           opponent_name, red_team_name, live_stats):
        """Fallback alert without predictor"""

        remaining = (
            max(0, self.MODEL_END_MINUTE - snapshot_minute)
            if snapshot_minute is not None
            else None
        )
        snapshot_label = (
            f"{snapshot_minute}'" if snapshot_minute is not None else "n/a"
        )
        remaining_label = (
            f"~{remaining} Minuten verbleibend"
            if remaining is not None
            else "Restzeit nicht berechenbar"
        )
        
        message = f"""
🔴 *ROTE KARTE - ENHANCED*

*Spieler:* {card_info['player']}
*Team:* {red_team_name}
*Match:* {home} vs {away}
*Spielstand:* {score}
*Platzverweis:* Minute {event_minute}'
*Snapshot:* {snapshot_label}
*Liga:* {country} - {league}

━━━━━━━━━━━━━━━━━━

⏱️ *{remaining_label}*
"""
        
        if live_stats:
            message += f"""
📊 *LIVE STATISTIKEN:*

*Ballbesitz:*
{home}: {_format_stat(live_stats['possession_home'], suffix='%')}
{away}: {_format_stat(live_stats['possession_away'], suffix='%')}

*Schüsse aufs Tor:*
{home}: {_format_stat(live_stats['shots_on_goal_home'])}
{away}: {_format_stat(live_stats['shots_on_goal_away'])}

*Angriffe:*
{home}: {_format_stat(live_stats['total_attacks_home'])}
{away}: {_format_stat(live_stats['total_attacks_away'])}
"""
        
        message += f"\n🕒 {datetime.now().strftime('%H:%M:%S')}"
        
        return message
    
    def monitor_loop(self, league_ids: List[int] = None, 
                    check_interval: int = 60):
        """Main monitoring loop"""
        
        print("Enhanced Red Card Bot started")
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
                        print("\nRED CARD DETECTED")
                        print(f"   Player: {card['player']}")
                        print(f"   Team: {card['team']}")
                        
                        if self.send_telegram_alert_with_stats(card):
                            self._mark_alerted(card['card_id'])
                
                self._save_state()
                
                import time
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\nBot stopped by user")
                break
            except Exception as e:
                print(f"ERROR in monitoring loop: {e}")
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

        auto_refresh = st.checkbox("Auto-Refresh aktivieren (alle 60 Sek.)")
        if auto_refresh:
            try:
                from streamlit_autorefresh import st_autorefresh
                st_autorefresh(interval=60_000, key="red-card-auto-refresh")
            except ImportError:
                st.warning("streamlit-autorefresh ist nicht installiert.")

        check_requested = st.button("🔍 Jetzt nach Roten Karten suchen", type="primary")
        if auto_refresh:
            check_requested = True

        if check_requested:
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
                                    home_id = match['teams']['home']['id']
                                    away_id = match['teams']['away']['id']
                                    live_stats = bot.get_live_stats(fixture_id, home_id, away_id)
                                    
                                    if live_stats:
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.metric(
                                                "Ballbesitz Home", 
                                                _format_stat(live_stats['possession_home'], suffix='%')
                                            )
                                            st.metric(
                                                "Schüsse Home",
                                                _format_stat(live_stats['shots_on_goal_home'])
                                            )
                                        
                                        with col2:
                                            st.metric(
                                                "Ballbesitz Away",
                                                _format_stat(live_stats['possession_away'], suffix='%')
                                            )
                                            st.metric(
                                                "Schüsse Away",
                                                _format_stat(live_stats['shots_on_goal_away'])
                                            )
                                    bot._mark_alerted(card['card_id'])
                            else:
                                st.success("✅ Keine roten Karten in diesem Spiel")
        
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
