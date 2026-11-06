"""آزمون‌های سادهٔ سناریوسازی؛ داده‌های این فایل فقط برای تستِ کد ساختگی‌اند."""

# کتابخانهٔ داخلی پایتون برای تست.
import unittest
# numpy و pandas برای آزمون اعداد و تاریخ‌ها هستند.
import numpy as np
import pandas as pd

# فقط توابعِ قابل آزمایش را وارد می‌کنیم.
from scenarios import prepare, sample_scenarios, calibration_gap, coverage_rate


class ScenarioTests(unittest.TestCase):
    """صحت بازتولید سناریو و جلوگیری از نشت قیمت روز هدف را بررسی می‌کند."""

    def test_daily_bootstrap_keeps_whole_paths(self):
        """هر سناریو باید یک مسیر کاملِ یک روز قدیمی باشد، نه ترکیب تصادفی ساعت‌ها."""

        # سه مسیر تاریخی مشخص با ۴ بازهٔ آزمایشی می‌سازیم.
        paths = np.array([[1., 1., 1., 1.],
                          [-1., -1., -1., -1.],
                          [0.5, 0.5, 0.5, 0.5]])
        median = np.full(4, 50.)
        low = np.full(4, 49.)
        high = np.full(4, 51.)

        # ۲۰ سناریو با بذر ثابت تولید می‌شوند.
        result = sample_scenarios(median, low, high, paths, count=20, seed=7)
        self.assertEqual(result.shape, (20, 4))
        for row in result:
            self.assertTrue(any(np.allclose(row - median, p) for p in paths))

        # اجرای دوباره با همان بذر باید دقیقاً یکسان باشد.
        other = sample_scenarios(median, low, high, paths, count=20, seed=7)
        np.testing.assert_array_equal(result, other)

    def test_calibration_gap_uses_only_known_errors(self):
        """حاشیهٔ کالیبراسیون باید پوشش نمونهٔ تاریخی را زیاد کند."""

        # چهار قیمت فرضی داریم که دو مورد بیرون از بازهٔ خام‌اند.
        true_price = np.array([5., 10., 15., 20.])
        lower = np.array([7., 7., 7., 7.])
        upper = np.array([18., 18., 18., 18.])
        gap = calibration_gap(true_price, lower, upper, target_coverage=0.75)
        self.assertEqual(gap, 2.0)
        self.assertGreaterEqual(
            coverage_rate(true_price, lower - gap, upper + gap), 0.75
        )

    def test_calibration_does_not_mutate_predictions(self):
        """محاسبهٔ حاشیه نباید قیمت‌ها یا حدهای اولیه را دستکاری کند."""

        actual = np.array([5., 20.])
        low = np.array([7., 7.])
        high = np.array([18., 18.])
        old_low, old_high = low.copy(), high.copy()
        calibration_gap(actual, low, high)
        np.testing.assert_array_equal(low, old_low)
        np.testing.assert_array_equal(high, old_high)

    def test_previous_day_feature_does_not_see_target_price(self):
        """خلاصهٔ قیمت روز هدف نباید در ویژگی همان روز وارد شود."""

        # این دادهٔ ساختگی سه روز معمولی با قیمت متفاوت دارد.
        times = pd.date_range("2026-01-12", periods=96 * 3, freq="15min",
                              tz="Europe/Berlin")
        prices = [10.] * 96 + [999.] * 96 + [20.] * 96
        fake = pd.DataFrame({"timestamp_utc": times.tz_convert("UTC"),
                             "price_eur_mwh": prices})
        # یک فایل موقت برای آزمون تابع خواندن CSV می‌سازیم.
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "test.csv"
            fake.to_csv(filename, index=False)
            result = prepare(filename)

        # ویژگی روز دوم باید صرفاً قیمت روز اول باشد: ۱۰ نه ۹۹۹.
        day_two = result[result["day"].astype(str) == "2026-01-13"]
        self.assertEqual(len(day_two), 96)
        self.assertTrue((day_two["prev_mean"] == 10.).all())

        # ویژگی روز سوم باید از روز دوم بیاید: ۹۹۹ نه ۲۰.
        day_three = result[result["day"].astype(str) == "2026-01-14"]
        self.assertTrue((day_three["prev_mean"] == 999.).all())


# اجرای مستقیم فایل، آزمون‌ها را فعال می‌کند.
if __name__ == "__main__":
    unittest.main()
