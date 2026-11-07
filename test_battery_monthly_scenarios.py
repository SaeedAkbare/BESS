"""Boundary and temporal-isolation tests for rolling monthly scenarios."""
import unittest
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd

from battery_monthly_scenarios import month_bounds, build_month


class MonthlyScenarioTests(unittest.TestCase):
    def test_month_bounds_including_year_boundary(self):
        self.assertEqual(month_bounds("2026-12"),
                         (date(2026, 12, 1), date(2027, 1, 1)))
        self.assertEqual(month_bounds("2027-02"),
                         (date(2027, 2, 1), date(2027, 3, 1)))

    def test_invalid_month(self):
        with self.assertRaises(ValueError):
            month_bounds("2026-13")

    def test_rejects_unsupported_early_month(self):
        with self.assertRaises(ValueError):
            build_month(pd.DataFrame(), "2026-09")

    def test_no_target_prices_in_model_or_calibration(self):
        # Synthetic data: one day each for prior-month calibration and target.
        times = pd.date_range("2026-09-30", periods=96, freq="15min", tz="UTC")
        target = pd.date_range("2026-10-01", periods=96, freq="15min", tz="UTC")
        table = pd.DataFrame({
            "day": [date(2026, 9, 30)] * 96 + [date(2026, 10, 1)] * 96,
            "price_eur_mwh": [10.0] * 96 + [999.0] * 96,
        })
        seen_training = []
        def fake_fit(rows):
            seen_training.append(set(rows["day"]))
            return object()
        def fake_predict(model, rows):
            return (np.zeros(len(rows)), np.ones(len(rows)),
                    np.full(len(rows), 2.0))
        def fake_residuals(rows):
            return np.zeros((60, 96)), 0.0, 0.0, 0.0, None
        with patch("battery_monthly_scenarios.fit_quantiles", fake_fit), \
             patch("battery_monthly_scenarios.predict", fake_predict), \
             patch("battery_monthly_scenarios.past_residual_days", fake_residuals):
            result, meta = build_month(table, "2026-10")
        self.assertEqual(len(result), 1)
        self.assertEqual(len(seen_training), 2)
        self.assertTrue(all(date(2026, 10, 1) not in days
                            for days in seen_training))
        self.assertEqual(meta["model_training_before"], "2026-10-01")


if __name__ == "__main__":
    unittest.main()
