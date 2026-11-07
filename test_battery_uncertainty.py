"""Deterministic tests for paired bootstrap inference."""
import unittest

from battery_uncertainty import paired_profit_bootstrap


class UncertaintyTests(unittest.TestCase):
    def test_constant_difference_has_exact_interval(self):
        rows = [{"selected": 12., "risk_neutral": 10.} for _ in range(10)]
        result = paired_profit_bootstrap(rows, n_boot=200, seed=7)
        self.assertEqual(result["total_difference_eur"], 20.)
        self.assertEqual(result["mean_daily_difference_ci_eur"], [2., 2.])
        self.assertEqual(result["probability_positive_mean_bootstrap"], 1.)

    def test_no_difference_has_zero_interval(self):
        rows = [{"selected": 10., "risk_neutral": 10.} for _ in range(4)]
        result = paired_profit_bootstrap(rows, n_boot=100)
        self.assertEqual(result["mean_daily_difference_ci_eur"], [0., 0.])

    def test_seed_reproducible(self):
        rows = [{"selected": float(i), "risk_neutral": 3.} for i in range(8)]
        a = paired_profit_bootstrap(rows, n_boot=100, seed=13)
        b = paired_profit_bootstrap(rows, n_boot=100, seed=13)
        self.assertEqual(a, b)

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            paired_profit_bootstrap([])
        with self.assertRaises(ValueError):
            paired_profit_bootstrap([{"selected": float("nan"), "risk_neutral": 1.}])
        with self.assertRaises(ValueError):
            paired_profit_bootstrap([{"selected": 1., "risk_neutral": 1.}],
                                    confidence=1)


if __name__ == "__main__":
    unittest.main()
