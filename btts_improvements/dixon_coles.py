"""
DIXON-COLES KORREKTUR MODUL
===========================
Korrigiert die Unterschätzung von Unentschieden (0:0, 1:1) im Standard-Poisson-Modell.

Mathematische Grundlage:
- Das Standard-Poisson-Modell nimmt Unabhängigkeit zwischen Heim- und Auswärtstoren an
- In der Realität korrelieren niedrige Ergebnisse (defensive Spiele)
- Dixon & Coles (1997) führten einen Korrekturparameter ρ (rho) ein

Die Korrekturformel:
P_DC(x,y) = τ(x,y,λ,μ,ρ) × P_Poisson(x;λ) × P_Poisson(y;μ)

Wobei τ (tau) die Korrekturfunktion ist:
- τ(0,0) = 1 - λ×μ×ρ
- τ(1,0) = 1 + λ×ρ  
- τ(0,1) = 1 + μ×ρ
- τ(1,1) = 1 - ρ
- τ(x,y) = 1 für alle anderen Ergebnisse

ρ < 0: Weniger niedrige Ergebnisse als Poisson vorhersagt (offensiver Fußball)
ρ > 0: Mehr niedrige Ergebnisse als Poisson vorhersagt (defensiver Fußball)
"""

import math
import numpy as np
from typing import Dict, Tuple, Optional
from scipy.stats import poisson
from scipy.optimize import minimize


class DixonColesModel:
    """
    Dixon-Coles Korrektur für Poisson-basierte Fußballvorhersagen
    
    Verbessert die Genauigkeit bei:
    - BTTS-Vorhersagen (besonders BTTS=Nein)
    - Unentschieden-Märkte
    - Niedrige Ergebnisse (0:0, 1:0, 0:1, 1:1)
    """
    
    def __init__(self, rho: float = -0.05):
        """
        Initialisiere das Dixon-Coles Modell
        
        Args:
            rho: Korrekturparameter (typischerweise zwischen -0.15 und 0.05)
                 - Negativer Wert: Weniger niedrige Ergebnisse
                 - Positiver Wert: Mehr niedrige Ergebnisse
                 - Default -0.05: Typischer Wert für moderne Ligen
        """
        self.rho = rho
        self.max_goals = 10  # Maximale Tore für Wahrscheinlichkeitsmatrix
    
    def tau_correction(self, x: int, y: int, lambda_home: float, 
                       mu_away: float, rho: float) -> float:
        """
        Berechne den Dixon-Coles Korrekturfaktor τ (tau)
        
        Args:
            x: Heimtore
            y: Auswärtstore
            lambda_home: Erwartete Heimtore (λ)
            mu_away: Erwartete Auswärtstore (μ)
            rho: Korrekturparameter (ρ)
        
        Returns:
            Korrekturfaktor τ
        """
        if x == 0 and y == 0:
            return 1 - lambda_home * mu_away * rho
        elif x == 1 and y == 0:
            return 1 + lambda_home * rho
        elif x == 0 and y == 1:
            return 1 + mu_away * rho
        elif x == 1 and y == 1:
            return 1 - rho
        else:
            return 1.0
    
    def probability_matrix(self, lambda_home: float, mu_away: float, 
                           use_correction: bool = True) -> np.ndarray:
        """
        Erstelle die korrigierte Wahrscheinlichkeitsmatrix für alle Ergebnisse
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
            use_correction: True für Dixon-Coles, False für Standard-Poisson
        
        Returns:
            Matrix[i,j] = P(Heim=i, Auswärts=j)
        """
        matrix = np.zeros((self.max_goals + 1, self.max_goals + 1))
        
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                # Standard Poisson-Wahrscheinlichkeiten
                p_home = poisson.pmf(i, lambda_home)
                p_away = poisson.pmf(j, mu_away)
                
                # Dixon-Coles Korrektur anwenden
                if use_correction:
                    tau = self.tau_correction(i, j, lambda_home, mu_away, self.rho)
                else:
                    tau = 1.0
                
                matrix[i, j] = p_home * p_away * tau
        
        # Normalisiere die Matrix (sollte zu 1 summieren)
        total = matrix.sum()
        if total > 0:
            matrix = matrix / total
        
        return matrix
    
    def calculate_btts_probability(self, lambda_home: float, mu_away: float) -> Dict[str, float]:
        """
        Berechne BTTS-Wahrscheinlichkeiten mit Dixon-Coles Korrektur
        
        WICHTIG: Dies ist die KORREKTE Berechnung mittels Matrixausschluss:
        P(BTTS=Ja) = 1 - [P(Home=0) + P(Away=0) - P(0:0)]
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
        
        Returns:
            Dict mit 'btts_yes', 'btts_no', 'prob_0_0'
        """
        matrix = self.probability_matrix(lambda_home, mu_away, use_correction=True)
        
        # P(Home = 0) = Summe der ersten Zeile
        p_home_zero = matrix[0, :].sum()
        
        # P(Away = 0) = Summe der ersten Spalte
        p_away_zero = matrix[:, 0].sum()
        
        # P(0:0) = Matrix[0,0]
        p_zero_zero = matrix[0, 0]
        
        # BTTS = Nein: Mindestens ein Team schießt 0 Tore
        # P(BTTS=Nein) = P(Home=0 ∪ Away=0) = P(Home=0) + P(Away=0) - P(0:0)
        btts_no = p_home_zero + p_away_zero - p_zero_zero
        
        # BTTS = Ja: Beide Teams schießen mindestens 1 Tor
        btts_yes = 1 - btts_no
        
        return {
            'btts_yes': btts_yes * 100,
            'btts_no': btts_no * 100,
            'prob_0_0': p_zero_zero * 100,
            'p_home_zero': p_home_zero * 100,
            'p_away_zero': p_away_zero * 100
        }
    
    def calculate_over_under(self, lambda_home: float, mu_away: float, 
                            goals_line: float = 2.5) -> Dict[str, float]:
        """
        Berechne Over/Under Wahrscheinlichkeiten
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
            goals_line: Torlinie (z.B. 2.5, 1.5, 3.5)
        
        Returns:
            Dict mit over und under Wahrscheinlichkeiten
        """
        matrix = self.probability_matrix(lambda_home, mu_away, use_correction=True)
        
        over_prob = 0.0
        under_prob = 0.0
        
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                total_goals = i + j
                if total_goals > goals_line:
                    over_prob += matrix[i, j]
                else:
                    under_prob += matrix[i, j]
        
        return {
            f'over_{goals_line}': over_prob * 100,
            f'under_{goals_line}': under_prob * 100
        }
    
    def calculate_match_result(self, lambda_home: float, mu_away: float) -> Dict[str, float]:
        """
        Berechne 1X2 Wahrscheinlichkeiten (Heimsieg, Unentschieden, Auswärtssieg)
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
        
        Returns:
            Dict mit home_win, draw, away_win
        """
        matrix = self.probability_matrix(lambda_home, mu_away, use_correction=True)
        
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        
        for i in range(self.max_goals + 1):
            for j in range(self.max_goals + 1):
                if i > j:
                    home_win += matrix[i, j]
                elif i == j:
                    draw += matrix[i, j]
                else:
                    away_win += matrix[i, j]
        
        return {
            'home_win': home_win * 100,
            'draw': draw * 100,
            'away_win': away_win * 100
        }
    
    def calculate_correct_score_probs(self, lambda_home: float, mu_away: float, 
                                      top_n: int = 10) -> list:
        """
        Berechne die wahrscheinlichsten Ergebnisse
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
            top_n: Anzahl der Top-Ergebnisse
        
        Returns:
            Liste der wahrscheinlichsten Ergebnisse mit Wahrscheinlichkeiten
        """
        matrix = self.probability_matrix(lambda_home, mu_away, use_correction=True)
        
        scores = []
        for i in range(min(6, self.max_goals + 1)):  # Maximal 5:x
            for j in range(min(6, self.max_goals + 1)):  # Maximal x:5
                scores.append({
                    'score': f"{i}:{j}",
                    'home': i,
                    'away': j,
                    'probability': matrix[i, j] * 100
                })
        
        # Sortiere nach Wahrscheinlichkeit
        scores.sort(key=lambda x: x['probability'], reverse=True)
        
        return scores[:top_n]
    
    def full_analysis(self, lambda_home: float, mu_away: float) -> Dict:
        """
        Vollständige Match-Analyse mit allen Märkten
        
        Args:
            lambda_home: Erwartete Heimtore
            mu_away: Erwartete Auswärtstore
        
        Returns:
            Umfassendes Analyse-Dictionary
        """
        btts = self.calculate_btts_probability(lambda_home, mu_away)
        result = self.calculate_match_result(lambda_home, mu_away)
        over_15 = self.calculate_over_under(lambda_home, mu_away, 1.5)
        over_25 = self.calculate_over_under(lambda_home, mu_away, 2.5)
        over_35 = self.calculate_over_under(lambda_home, mu_away, 3.5)
        top_scores = self.calculate_correct_score_probs(lambda_home, mu_away)
        
        return {
            'expected_goals': {
                'home': lambda_home,
                'away': mu_away,
                'total': lambda_home + mu_away
            },
            'btts': btts,
            'result': result,
            'over_under': {
                **over_15,
                **over_25,
                **over_35
            },
            'top_scores': top_scores,
            'correction_factor': self.rho
        }
    
    @staticmethod
    def estimate_rho_from_data(historical_results: list) -> float:
        """
        Schätze den optimalen ρ-Wert aus historischen Daten
        
        Args:
            historical_results: Liste von Dicts mit 'home_goals', 'away_goals',
                               'lambda_home', 'mu_away'
        
        Returns:
            Geschätzter ρ-Wert
        """
        if len(historical_results) < 50:
            return -0.05  # Default für kleine Datensätze
        
        def neg_log_likelihood(rho):
            model = DixonColesModel(rho=rho[0])
            ll = 0
            for match in historical_results:
                matrix = model.probability_matrix(
                    match['lambda_home'], 
                    match['mu_away'], 
                    use_correction=True
                )
                prob = matrix[match['home_goals'], match['away_goals']]
                if prob > 0:
                    ll += np.log(prob)
            return -ll
        
        result = minimize(neg_log_likelihood, x0=[-0.05], 
                         bounds=[(-0.3, 0.3)], method='L-BFGS-B')
        
        return result.x[0]


# Vergleichsfunktion: Standard-Poisson vs Dixon-Coles
def compare_models(lambda_home: float, mu_away: float) -> Dict:
    """
    Vergleiche Standard-Poisson mit Dixon-Coles Modell
    
    Zeigt den Unterschied in den Vorhersagen für niedrige Ergebnisse.
    """
    dc_model = DixonColesModel(rho=-0.05)
    
    # Dixon-Coles Ergebnisse
    dc_matrix = dc_model.probability_matrix(lambda_home, mu_away, use_correction=True)
    
    # Standard Poisson Ergebnisse (ohne Korrektur)
    poisson_matrix = dc_model.probability_matrix(lambda_home, mu_away, use_correction=False)
    
    comparison = {
        'low_score_corrections': {
            '0:0': {
                'poisson': poisson_matrix[0, 0] * 100,
                'dixon_coles': dc_matrix[0, 0] * 100,
                'difference': (dc_matrix[0, 0] - poisson_matrix[0, 0]) * 100
            },
            '1:0': {
                'poisson': poisson_matrix[1, 0] * 100,
                'dixon_coles': dc_matrix[1, 0] * 100,
                'difference': (dc_matrix[1, 0] - poisson_matrix[1, 0]) * 100
            },
            '0:1': {
                'poisson': poisson_matrix[0, 1] * 100,
                'dixon_coles': dc_matrix[0, 1] * 100,
                'difference': (dc_matrix[0, 1] - poisson_matrix[0, 1]) * 100
            },
            '1:1': {
                'poisson': poisson_matrix[1, 1] * 100,
                'dixon_coles': dc_matrix[1, 1] * 100,
                'difference': (dc_matrix[1, 1] - poisson_matrix[1, 1]) * 100
            }
        }
    }
    
    # BTTS Vergleich
    dc_btts = dc_model.calculate_btts_probability(lambda_home, mu_away)
    
    # Standard Poisson BTTS
    p_home_zero = sum(poisson.pmf(0, lambda_home) * poisson.pmf(j, mu_away) 
                      for j in range(11))
    p_away_zero = sum(poisson.pmf(i, lambda_home) * poisson.pmf(0, mu_away) 
                      for i in range(11))
    p_zero_zero = poisson.pmf(0, lambda_home) * poisson.pmf(0, mu_away)
    poisson_btts_no = p_home_zero + p_away_zero - p_zero_zero
    
    comparison['btts_comparison'] = {
        'poisson_btts_yes': (1 - poisson_btts_no) * 100,
        'dixon_coles_btts_yes': dc_btts['btts_yes'],
        'difference': dc_btts['btts_yes'] - (1 - poisson_btts_no) * 100
    }
    
    return comparison


# Quick Test
if __name__ == '__main__':
    print("=" * 60)
    print("DIXON-COLES MODEL TEST")
    print("=" * 60)
    
    # Beispiel: Bayern München vs Dortmund
    lambda_home = 2.1  # Bayern erwartete Tore
    mu_away = 1.3      # Dortmund erwartete Tore
    
    model = DixonColesModel(rho=-0.05)
    analysis = model.full_analysis(lambda_home, mu_away)
    
    print(f"\n📊 Match: λ_home={lambda_home}, μ_away={mu_away}")
    print(f"\n🎯 BTTS Wahrscheinlichkeiten:")
    print(f"   BTTS Ja:  {analysis['btts']['btts_yes']:.1f}%")
    print(f"   BTTS Nein: {analysis['btts']['btts_no']:.1f}%")
    print(f"   P(0:0):   {analysis['btts']['prob_0_0']:.1f}%")
    
    print(f"\n⚽ Spielausgang (1X2):")
    print(f"   Heimsieg:     {analysis['result']['home_win']:.1f}%")
    print(f"   Unentschieden: {analysis['result']['draw']:.1f}%")
    print(f"   Auswärtssieg: {analysis['result']['away_win']:.1f}%")
    
    print(f"\n📈 Over/Under:")
    print(f"   Over 1.5:  {analysis['over_under']['over_1.5']:.1f}%")
    print(f"   Over 2.5:  {analysis['over_under']['over_2.5']:.1f}%")
    print(f"   Over 3.5:  {analysis['over_under']['over_3.5']:.1f}%")
    
    print(f"\n🏆 Top 5 Wahrscheinlichste Ergebnisse:")
    for i, score in enumerate(analysis['top_scores'][:5], 1):
        print(f"   {i}. {score['score']} → {score['probability']:.1f}%")
    
    print("\n" + "=" * 60)
    print("MODELL-VERGLEICH: Poisson vs Dixon-Coles")
    print("=" * 60)
    
    comparison = compare_models(lambda_home, mu_away)
    
    print("\n📊 Korrektur bei niedrigen Ergebnissen:")
    for score, data in comparison['low_score_corrections'].items():
        print(f"   {score}: Poisson {data['poisson']:.2f}% → DC {data['dixon_coles']:.2f}% "
              f"(Δ {data['difference']:+.2f}%)")
    
    print(f"\n🎯 BTTS Vergleich:")
    btts = comparison['btts_comparison']
    print(f"   Poisson BTTS Ja:      {btts['poisson_btts_yes']:.1f}%")
    print(f"   Dixon-Coles BTTS Ja: {btts['dixon_coles_btts_yes']:.1f}%")
    print(f"   Differenz:           {btts['difference']:+.1f}%")
    
    print("\n✅ Dixon-Coles Modul erfolgreich geladen!")
