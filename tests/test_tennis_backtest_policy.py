import unittest

from tennis.backtest import BacktestReport, BacktestRow


def _row(*, p_cal: float, odds_w: float, odds_l: float) -> BacktestRow:
    return BacktestRow(
        date="2026-01-01",
        tour="ATP",
        surface="Hard",
        best_of=3,
        winner="Winner",
        loser="Loser",
        p_elo=p_cal,
        p_serve=p_cal,
        p_model=p_cal,
        p_cal=p_cal,
        p_market_alpha=0.5,
        edge_w=0.0,
        edge_l=0.0,
        chosen_side="W",
        chosen_edge=0.0,
        chosen_odds=odds_w,
        odds_w=odds_w,
        odds_l=odds_l,
        bet_won=True,
        gated=True,
        y_alpha=1,
        p_alpha=p_cal,
        p_alpha_raw=p_cal,
    )


class TennisPolicyReplayTests(unittest.TestCase):
    def test_replay_selects_side_by_risk_ev_not_legacy_edge(self):
        report = BacktestReport(
            rows=[
                _row(p_cal=0.70, odds_w=2.00, odds_l=4.00),
                _row(p_cal=0.80, odds_w=1.50, odds_l=3.00),
            ]
        )

        result = report.policy_summary(
            probability_haircut=0.15,
            minimum_expected_roi=0.03,
        )

        self.assertEqual(result["bets"], 1)
        self.assertEqual(result["wins"], 1)
        self.assertEqual(result["roi"], 1.0)
        self.assertEqual(result["avg_odds"], 2.0)

    def test_replay_returns_empty_summary_when_price_gate_fails(self):
        report = BacktestReport(rows=[_row(p_cal=0.70, odds_w=1.50, odds_l=2.50)])

        result = report.policy_summary(
            probability_haircut=0.15,
            minimum_expected_roi=0.03,
        )

        self.assertEqual(result["bets"], 0)
        self.assertIsNone(result["roi"])

    def test_replay_excludes_positive_ev_prices_below_publication_floor(self):
        report = BacktestReport(rows=[_row(p_cal=0.99, odds_w=1.10, odds_l=50.0)])

        result = report.policy_summary(
            probability_haircut=0.0,
            minimum_expected_roi=0.03,
        )

        self.assertEqual(result["bets"], 0)
        self.assertEqual(result["minimum_published_odds"], 1.20)

    def test_replay_rejects_invalid_policy_inputs(self):
        report = BacktestReport()

        with self.assertRaises(ValueError):
            report.policy_summary(probability_haircut=-0.01)
        with self.assertRaises(ValueError):
            report.policy_summary(
                probability_haircut=0.15,
                minimum_expected_roi=float("nan"),
            )


if __name__ == "__main__":
    unittest.main()
