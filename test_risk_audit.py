"""آزمون‌های سادهٔ بررسی دم قیمت؛ اعداد این فایل کاملاً ساختگی و فقط برای تست‌اند."""

import unittest
import numpy as np

# تابع آماری را جدا از دریافت داده آزمایش می‌کنیم.
from risk_audit import risk_metrics


class PriceRiskAuditTests(unittest.TestCase):
    """موارد خیلی منفی، پوشش بازه و سالم‌بودن شکل ورودی را بررسی می‌کند."""

    def test_exact_scenarios_cover_the_actual(self):
        """اگر همهٔ سناریوها عین واقعیت باشند، هیچ خروجی از بازه نداریم."""

        # دو روز فرضی، هر روز سه بازهٔ متفاوت دارند.
        actual = np.array([[10., -5., 20.], [12., 15., -2.]])
        # پنجاه کپی از همان روز را فقط برای کنترل محاسبات می‌سازیم.
        paths = np.repeat(actual[:, None, :], repeats=50, axis=1)
        result = risk_metrics(actual, paths, -10., 25.)

        self.assertEqual(result["days_evaluated"], 2)
        self.assertEqual(result["intervals_evaluated"], 6)
        self.assertEqual(result["scenarios_per_day"], 50)
        self.assertAlmostEqual(result["scenario_p10_p90_coverage"], 1.0)
        self.assertAlmostEqual(result["below_scenario_p10_rate"], 0.0)
        self.assertAlmostEqual(result["above_scenario_p90_rate"], 0.0)
        self.assertFalse(result["risk_ready"])

    def test_extreme_negative_price_is_detected(self):
        """قیمت واقعی بسیار منفی باید بیرون دم پایین سناریو ثبت شود."""

        # قیمت واقعی منفیِ شدید در بازهٔ سومِ روز دیده شده است.
        actual = np.array([[10., 10., -100.]])
        usual = np.array([9., 10., 11.])
        paths = np.repeat(usual[None, None, :], repeats=50, axis=1)
        result = risk_metrics(actual, paths, -50., 50.)

        self.assertAlmostEqual(result["below_scenario_p10_rate"], 1 / 3)
        self.assertAlmostEqual(
            result["extreme_interval_rates"]["below_training_p05_actual"], 1 / 3
        )
        self.assertAlmostEqual(
            result["extreme_interval_rates"]["below_training_p05_scenarios"], 0.0
        )

    def test_bad_shapes_are_rejected(self):
        """اگر تعداد روزها یا بازه‌ها متفاوت باشد باید خطا بگیریم."""

        actual = np.zeros((2, 3))
        paths = np.zeros((1, 50, 3))
        with self.assertRaises(ValueError):
            risk_metrics(actual, paths, -1., 1.)

    def test_nonfinite_prices_are_rejected(self):
        """قیمت خالی یا بی‌نهایت نباید وارد گزارش ریسک شود."""

        actual = np.array([[1., float("nan"), 3.]])
        paths = np.ones((1, 50, 3))
        with self.assertRaises(ValueError):
            risk_metrics(actual, paths, -1., 1.)


if __name__ == "__main__":
    unittest.main()
