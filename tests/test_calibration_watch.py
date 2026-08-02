"""Tests for the calibration watchdog thresholds (synthetic buckets)."""

from __future__ import annotations

from tennis.calibration_watch import evaluate, RMS_DRIFT_LIMIT, BIAS_DRIFT_LIMIT


def _buckets(market_values):
    """market_values: {market: [(bucket, n, p_avg, empirical), ...]}"""
    out = {}
    for market, rows in market_values.items():
        for b, n, p_avg, emp in rows:
            out[(market, b)] = [n, p_avg * n, emp * n]
    return out


class TestWatchdogEvaluation:
    def test_calibrated_markets_pass(self):
        buckets = _buckets({
            "over_2_5_sets": [(0.5, 1000, 0.49, 0.46)],
            "under_2_5_sets": [(0.5, 1000, 0.51, 0.54)],
            "set_a_2_0": [(0.3, 800, 0.30, 0.31)],
            "set_b_2_0": [(0.3, 800, 0.30, 0.31)],
        })
        result = evaluate(buckets, n_scored=1800)
        assert result["status"] == "ok"
        assert result["markets"]["over_2_5_sets"]["drift"] is False

    def test_rms_drift_triggers_alarm(self):
        # model says 0.70, reality 0.55 across a big bucket -> RMS way over limit
        buckets = _buckets({
            "over_2_5_sets": [(0.7, 2000, 0.70, 0.55)],
            "set_a_2_0": [(0.3, 800, 0.30, 0.31)],
        })
        result = evaluate(buckets, n_scored=2800)
        assert result["markets"]["over_2_5_sets"]["rms"] > RMS_DRIFT_LIMIT
        assert result["status"] == "drift"

    def test_mid_bias_drift_triggers_alarm(self):
        # small RMS but a big systematic bias in the mid bucket
        buckets = _buckets({
            "under_2_5_sets": [(0.5, 1500, 0.50, 0.50 + BIAS_DRIFT_LIMIT + 0.02)],
        })
        result = evaluate(buckets, n_scored=1500)
        assert result["markets"]["under_2_5_sets"]["drift"] is True
        assert result["status"] == "drift"

    def test_reference_market_drift_does_not_alarm(self):
        # game totals are UI-banned: their drift is informational only
        buckets = _buckets({
            "over_21_5_games": [(0.7, 2000, 0.70, 0.55)],
            "over_2_5_sets": [(0.5, 1000, 0.49, 0.46)],
            "under_2_5_sets": [(0.5, 1000, 0.51, 0.54)],
            "set_a_2_0": [(0.3, 800, 0.30, 0.31)],
            "set_b_2_0": [(0.3, 800, 0.30, 0.31)],
        })
        result = evaluate(buckets, n_scored=3000)
        assert result["markets"]["over_21_5_games"]["drift"] is True
        assert result["status"] == "ok"

    def test_tiny_buckets_ignored(self):
        buckets = _buckets({
            "set_b_2_0": [(0.9, 10, 0.90, 0.10)],  # n < 15 -> skipped
        })
        result = evaluate(buckets, n_scored=10)
        assert "set_b_2_0" not in result["markets"]
        assert result["status"] == "insufficient"
        assert "set_b_2_0" in result["missing_markets"]
