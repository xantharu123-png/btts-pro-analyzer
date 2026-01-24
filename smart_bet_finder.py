"""
SMART BET FINDER - KI GESTÜTZTE WETTEMPFEHLUNGEN
=================================================

3 intelligente Button-Modi:
1. 🎯 Value Bet Scanner - Findet Wetten mit höchstem Edge
2. 🔥 Multi-Market Combos - Findet profitable Kombinationen
3. 💎 High Confidence Filter - Nur sehr sichere Wetten
"""

import streamlit as st
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import math


@dataclass
class SmartBet:
    """Struktur für eine Smart Bet Empfehlung"""
    market: str
    sub_market: str
    probability: float
    confidence: str
    edge: float  # In percentage
    expected_roi: float
    reasoning: str
    stake_recommendation: str
    risk_level: str
    
    def to_dict(self):
        return {
            'market': self.market,
            'sub_market': self.sub_market,
            'probability': self.probability,
            'confidence': self.confidence,
            'edge': self.edge,
            'expected_roi': self.expected_roi,
            'reasoning': self.reasoning,
            'stake_recommendation': self.stake_recommendation,
            'risk_level': self.risk_level
        }


class SmartBetFinder:
    """
    Intelligente Wettfinder-Engine
    
    Analysiert ALLE verfügbaren Märkte und findet:
    - Value Bets (höchster Edge)
    - Kombinations-Wetten (Parlay)
    - High Confidence Bets (>75%)
    """
    
    def __init__(self):
        # Durchschnittliche Bookmaker Odds für verschiedene Märkte
        # (Diese sollten später aus echten Bookmaker APIs kommen)
        self.typical_odds = {
            'btts_yes': 1.85,
            'btts_no': 1.95,
            'over_0.5': 1.10,
            'over_1.5': 1.35,
            'over_2.5': 2.10,
            'over_3.5': 3.50,
            'over_4.5': 6.00,
            'under_2.5': 1.75,
            'under_3.5': 1.40,
            'home_win': 2.20,
            'draw': 3.40,
            'away_win': 3.00,
            'home_clean_sheet': 2.80,
            'away_clean_sheet': 3.50,
            'corners_over_8.5': 1.70,
            'corners_over_10.5': 2.20,
            'corners_over_12.5': 3.00,
            'cards_over_3.5': 1.80,
            'cards_over_4.5': 2.40,
            'cards_over_5.5': 3.50,
        }
    
    def _calculate_edge(self, probability: float, odds: float) -> float:
        """
        Berechne Edge (Vorteil gegenüber Bookmaker)
        
        Edge = Model Probability - Implied Probability
        Implied Probability = 1 / odds
        """
        if odds <= 1.0:
            return 0.0
        
        implied_prob = (1.0 / odds) * 100  # Mit Vig
        model_prob = probability
        
        edge = model_prob - implied_prob
        return edge
    
    def _calculate_expected_roi(self, probability: float, odds: float) -> float:
        """
        Berechne Expected ROI
        
        ROI = (Probability × (Odds - 1)) - (1 - Probability)
        """
        roi = (probability / 100 * (odds - 1)) - (1 - probability / 100)
        return roi * 100
    
    def _get_odds_for_market(self, market_key: str) -> float:
        """Get typical odds for a market"""
        return self.typical_odds.get(market_key, 2.0)
    
    def _assess_risk_level(self, probability: float, confidence: str) -> str:
        """Bewerte Risiko-Level"""
        if confidence == 'VERY_HIGH' and probability >= 75:
            return 'LOW'
        elif confidence == 'HIGH' and probability >= 65:
            return 'MEDIUM'
        elif probability >= 55:
            return 'MEDIUM-HIGH'
        else:
            return 'HIGH'
    
    def _get_stake_recommendation(self, edge: float, confidence: str, risk: str) -> str:
        """Kelly Criterion basierte Stake Empfehlung"""
        if risk == 'LOW' and edge > 20:
            return '5-8% of bankroll'
        elif risk == 'LOW':
            return '3-5% of bankroll'
        elif risk == 'MEDIUM' and edge > 15:
            return '2-4% of bankroll'
        elif risk == 'MEDIUM':
            return '1-3% of bankroll'
        else:
            return '0.5-2% of bankroll (risky!)'
    
    def find_value_bets(self, match_analysis: Dict) -> List[SmartBet]:
        """
        🎯 VALUE BET SCANNER
        
        Findet Top 3 Wetten mit höchstem Edge
        """
        all_bets = []
        
        # === BTTS ===
        btts_prob = match_analysis.get('btts_probability', 0)
        btts_conf = match_analysis.get('btts_confidence', 'MEDIUM')
        
        if btts_prob >= 50:
            odds = self._get_odds_for_market('btts_yes')
            edge = self._calculate_edge(btts_prob, odds)
            roi = self._calculate_expected_roi(btts_prob, odds)
            risk = self._assess_risk_level(btts_prob, btts_conf)
            
            if edge > 0:  # Nur positive Edge
                bet = SmartBet(
                    market='BTTS',
                    sub_market='Yes',
                    probability=btts_prob,
                    confidence=btts_conf,
                    edge=edge,
                    expected_roi=roi,
                    reasoning=self._get_btts_reasoning(match_analysis),
                    stake_recommendation=self._get_stake_recommendation(edge, btts_conf, risk),
                    risk_level=risk
                )
                all_bets.append(bet)
        
        # === OVER/UNDER ===
        for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
            over_key = f'over_{threshold}'
            over_prob = match_analysis.get(f'over_{threshold}_probability', 0)
            
            if over_prob >= 50:
                odds = self._get_odds_for_market(over_key)
                edge = self._calculate_edge(over_prob, odds)
                roi = self._calculate_expected_roi(over_prob, odds)
                conf = self._estimate_confidence(over_prob)
                risk = self._assess_risk_level(over_prob, conf)
                
                if edge > 5:  # Mindestens 5% Edge
                    bet = SmartBet(
                        market='Over/Under',
                        sub_market=f'Over {threshold}',
                        probability=over_prob,
                        confidence=conf,
                        edge=edge,
                        expected_roi=roi,
                        reasoning=self._get_over_reasoning(threshold, match_analysis),
                        stake_recommendation=self._get_stake_recommendation(edge, conf, risk),
                        risk_level=risk
                    )
                    all_bets.append(bet)
        
        # === MATCH RESULT ===
        home_win = match_analysis.get('home_win_probability', 0)
        draw = match_analysis.get('draw_probability', 0)
        away_win = match_analysis.get('away_win_probability', 0)
        
        results = [
            ('home_win', home_win, 'Home Win'),
            ('draw', draw, 'Draw'),
            ('away_win', away_win, 'Away Win')
        ]
        
        for key, prob, label in results:
            if prob >= 35:  # Lower threshold for match results
                odds = self._get_odds_for_market(key)
                edge = self._calculate_edge(prob, odds)
                roi = self._calculate_expected_roi(prob, odds)
                conf = self._estimate_confidence(prob)
                risk = self._assess_risk_level(prob, conf)
                
                if edge > 3:
                    bet = SmartBet(
                        market='Match Result',
                        sub_market=label,
                        probability=prob,
                        confidence=conf,
                        edge=edge,
                        expected_roi=roi,
                        reasoning=self._get_result_reasoning(label, match_analysis),
                        stake_recommendation=self._get_stake_recommendation(edge, conf, risk),
                        risk_level=risk
                    )
                    all_bets.append(bet)
        
        # === CORNERS ===
        corners_data = match_analysis.get('corners', {})
        for threshold in [8.5, 10.5, 12.5]:
            over_key = f'over_{threshold}'
            over_prob = corners_data.get(f'over_{threshold}', {}).get('probability', 0)
            
            if over_prob >= 55:
                odds = self._get_odds_for_market(f'corners_over_{threshold}')
                edge = self._calculate_edge(over_prob, odds)
                roi = self._calculate_expected_roi(over_prob, odds)
                conf = corners_data.get('confidence', 'MEDIUM')
                risk = self._assess_risk_level(over_prob, conf)
                
                if edge > 5:
                    bet = SmartBet(
                        market='Corners',
                        sub_market=f'Over {threshold}',
                        probability=over_prob,
                        confidence=conf,
                        edge=edge,
                        expected_roi=roi,
                        reasoning=f"Expected corners: {corners_data.get('expected_total', 0):.1f}",
                        stake_recommendation=self._get_stake_recommendation(edge, conf, risk),
                        risk_level=risk
                    )
                    all_bets.append(bet)
        
        # === CARDS ===
        cards_data = match_analysis.get('cards', {})
        for threshold in [3.5, 4.5, 5.5]:
            over_key = f'over_{threshold}'
            over_prob = cards_data.get(f'over_{threshold}', {}).get('probability', 0)
            
            if over_prob >= 55:
                odds = self._get_odds_for_market(f'cards_over_{threshold}')
                edge = self._calculate_edge(over_prob, odds)
                roi = self._calculate_expected_roi(over_prob, odds)
                conf = cards_data.get('confidence', 'MEDIUM')
                risk = self._assess_risk_level(over_prob, conf)
                
                if edge > 5:
                    bet = SmartBet(
                        market='Cards',
                        sub_market=f'Over {threshold}',
                        probability=over_prob,
                        confidence=conf,
                        edge=edge,
                        expected_roi=roi,
                        reasoning=f"Expected cards: {cards_data.get('expected_total', 0):.1f}",
                        stake_recommendation=self._get_stake_recommendation(edge, conf, risk),
                        risk_level=risk
                    )
                    all_bets.append(bet)
        
        # Sortiere nach Edge (höchster zuerst)
        all_bets.sort(key=lambda x: x.edge, reverse=True)
        
        # Return Top 3
        return all_bets[:3]
    
    def find_combo_bets(self, match_analysis: Dict) -> List[Dict]:
        """
        🔥 MULTI-MARKET COMBO FINDER
        
        Findet profitable 2-3 Wetten Kombinationen
        """
        combos = []
        
        btts_prob = match_analysis.get('btts_probability', 0)
        over_25_prob = match_analysis.get('over_2.5_probability', 0)
        over_15_prob = match_analysis.get('over_1.5_probability', 0)
        
        # Combo 1: BTTS + Over 2.5
        if btts_prob >= 65 and over_25_prob >= 70:
            combined_prob = (btts_prob / 100) * (over_25_prob / 100) * 100
            combined_odds = 1.85 * 2.10  # Typical parlay odds
            
            combos.append({
                'name': 'BTTS + Over 2.5',
                'bets': ['BTTS Yes', 'Over 2.5'],
                'combined_probability': combined_prob,
                'parlay_odds': combined_odds,
                'expected_roi': self._calculate_expected_roi(combined_prob, combined_odds),
                'risk_level': 'MEDIUM',
                'reasoning': 'Both teams scoring with high goal expectation'
            })
        
        # Combo 2: Over 1.5 + Corners Over 9.5
        corners_data = match_analysis.get('corners', {})
        corners_prob = corners_data.get('over_9.5', {}).get('probability', 0)
        
        if over_15_prob >= 75 and corners_prob >= 65:
            combined_prob = (over_15_prob / 100) * (corners_prob / 100) * 100
            combined_odds = 1.35 * 1.90
            
            combos.append({
                'name': 'Over 1.5 + Corners Over 9.5',
                'bets': ['Over 1.5 Goals', 'Over 9.5 Corners'],
                'combined_probability': combined_prob,
                'parlay_odds': combined_odds,
                'expected_roi': self._calculate_expected_roi(combined_prob, combined_odds),
                'risk_level': 'LOW-MEDIUM',
                'reasoning': 'Attacking game with high corner frequency'
            })
        
        # Combo 3: BTTS + Cards Over 3.5
        cards_data = match_analysis.get('cards', {})
        cards_prob = cards_data.get('over_3.5', {}).get('probability', 0)
        
        if btts_prob >= 70 and cards_prob >= 70:
            combined_prob = (btts_prob / 100) * (cards_prob / 100) * 100
            combined_odds = 1.85 * 1.80
            
            combos.append({
                'name': 'BTTS + Cards Over 3.5',
                'bets': ['BTTS Yes', 'Over 3.5 Cards'],
                'combined_probability': combined_prob,
                'parlay_odds': combined_odds,
                'expected_roi': self._calculate_expected_roi(combined_prob, combined_odds),
                'risk_level': 'MEDIUM',
                'reasoning': 'Competitive match with referee strictness'
            })
        
        # Sort by expected ROI
        combos.sort(key=lambda x: x['expected_roi'], reverse=True)
        
        return combos[:3]
    
    def find_high_confidence_bets(self, match_analysis: Dict) -> List[SmartBet]:
        """
        💎 HIGH CONFIDENCE FILTER
        
        Nur Wetten mit Probability >75% und Confidence VERY_HIGH
        Falls nicht genug gefunden: Threshold wird auf 72% gesenkt
        """
        high_conf_bets = []
        threshold_lowered = False
        
        # Alle Value Bets durchsuchen
        all_bets = self.find_value_bets(match_analysis)
        
        # STRICT Filter: Probability >75% UND Confidence VERY_HIGH
        for bet in all_bets:
            if bet.probability >= 75 and bet.confidence == 'VERY_HIGH':
                high_conf_bets.append(bet)
        
        # Falls weniger als 3, senke Threshold auf 72%
        if len(high_conf_bets) < 3:
            threshold_lowered = True
            for bet in all_bets:
                if bet.probability >= 72 and bet.confidence in ['VERY_HIGH', 'HIGH']:
                    if bet not in high_conf_bets:
                        high_conf_bets.append(bet)
        
        # Sort by probability
        high_conf_bets.sort(key=lambda x: x.probability, reverse=True)
        
        # Add warning if threshold was lowered
        if threshold_lowered and high_conf_bets:
            import streamlit as st
            st.info("ℹ️ Nicht genug Wetten >75% gefunden. Threshold auf 72% gesenkt.")
        
        return high_conf_bets[:3]
    
    def _estimate_confidence(self, probability: float) -> str:
        """Estimate confidence level from probability"""
        if probability >= 85:
            return 'VERY_HIGH'
        elif probability >= 70:
            return 'HIGH'
        elif probability >= 55:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_btts_reasoning(self, analysis: Dict) -> str:
        """Generate reasoning for BTTS bet"""
        reasons = []
        
        btts_prob = analysis.get('btts_probability', 0)
        xg_home = analysis.get('xg_home', 0)
        xg_away = analysis.get('xg_away', 0)
        
        if xg_home > 1.2 and xg_away > 1.0:
            reasons.append("Both teams with strong xG")
        
        if btts_prob >= 75:
            reasons.append("Very high probability")
        
        reasons.append(f"xG: {xg_home:.1f} - {xg_away:.1f}")
        
        return " | ".join(reasons)
    
    def _get_over_reasoning(self, threshold: float, analysis: Dict) -> str:
        """Generate reasoning for Over bet"""
        expected = analysis.get('expected_goals', threshold + 1)
        return f"Expected goals: {expected:.1f} (>{threshold})"
    
    def _get_result_reasoning(self, result: str, analysis: Dict) -> str:
        """Generate reasoning for match result bet"""
        if 'Home' in result:
            return f"Home advantage with strong form"
        elif 'Draw' in result:
            return f"Evenly matched teams"
        else:
            return f"Away team showing superior form"


def display_smart_bet(bet: SmartBet, rank: int):
    """Display a smart bet recommendation"""
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    medal = medals.get(rank, '💎')
    
    st.markdown(f"### {medal} #{rank} SMART BET")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Market", bet.market)
        st.metric("Selection", bet.sub_market)
    
    with col2:
        st.metric("Probability", f"{bet.probability:.1f}%")
        st.metric("Confidence", bet.confidence)
        st.metric("Edge", f"+{bet.edge:.1f}%", 
                 delta="vs Bookmaker" if bet.edge > 0 else None)
    
    with col3:
        st.metric("Expected ROI", f"{bet.expected_roi:+.1f}%")
        st.metric("Risk Level", bet.risk_level)
        
        # Color-coded by risk
        if bet.risk_level == 'LOW':
            st.success(f"💰 Stake: {bet.stake_recommendation}")
        elif bet.risk_level in ['MEDIUM', 'MEDIUM-HIGH']:
            st.info(f"💰 Stake: {bet.stake_recommendation}")
        else:
            st.warning(f"⚠️ Stake: {bet.stake_recommendation}")
    
    st.info(f"**💡 Reasoning:** {bet.reasoning}")
    st.markdown("---")


def display_combo_bet(combo: Dict, rank: int):
    """Display a combo bet recommendation"""
    medals = {1: '🔥', 2: '🔥', 3: '🔥'}
    medal = medals.get(rank, '🔥')
    
    st.markdown(f"### {medal} #{rank} COMBO BET")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Bets in Combo:**")
        for bet in combo['bets']:
            st.write(f"✅ {bet}")
    
    with col2:
        st.metric("Combined Probability", f"{combo['combined_probability']:.1f}%")
        st.metric("Parlay Odds", f"{combo['parlay_odds']:.2f}")
        st.metric("Expected ROI", f"{combo['expected_roi']:+.1f}%")
        st.metric("Risk Level", combo['risk_level'])
    
    st.info(f"**💡 Reasoning:** {combo['reasoning']}")
    st.markdown("---")
