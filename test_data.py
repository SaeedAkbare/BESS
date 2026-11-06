"""تست‌های سادهٔ داده: بدون دانلود واقعی و بدون داده‌سازی برای نتایج پژوهش."""

# کتابخانهٔ استاندارد تست پایتون.
import unittest
# برای مشخص‌کردن انتهای روز محلی.
from datetime import timedelta
# ساخت چند ردیف آزمایشی برای کنترل صحت برنامه.
import pandas as pd

# تنها تابعی را وارد می‌کنیم که قرار است تست شود.
from data import validate_prices


def make_day(day):
    """برای تست نرم‌افزار، زمان‌های یک روز محلی را می‌سازد؛ این‌ها قیمت واقعی نیستند."""

    # ساعت صفر روز به وقت برلین را می‌گیریم.
    start = pd.Timestamp(day, tz="Europe/Berlin")
    # ساعت صفر روز بعد را می‌گیریم تا تغییر ساعت رعایت شود.
    next_day = pd.Timestamp(start.date() + timedelta(days=1), tz="Europe/Berlin")
    # زمان‌های دقیق پانزده‌دقیقه‌ای را در UTC می‌سازیم.
    times = pd.date_range(start, next_day, freq="15min", inclusive="left").tz_convert("UTC")
    # یک جدول کوچک با قیمت‌های ساختگی فقط برای TEST می‌سازیم.
    return pd.DataFrame({"timestamp_utc": times, "price_eur_mwh": [25.0] * len(times)})


class PriceValidationTests(unittest.TestCase):
    """بررسی می‌کند برنامه اطلاعات ناقص یا زمان نادرست را قبول نکند."""

    def test_normal_day(self):
        """روز معمولی باید دقیقاً ۹۶ بازه داشته باشد."""
        df = make_day("2026-10-26")
        self.assertEqual(len(validate_prices(df, "2026-10-26", "2026-10-26")), 96)

    def test_dst_fall(self):
        """روز پایان ساعت تابستانی در برلین ۱۰۰ بازه دارد."""
        df = make_day("2026-10-25")
        self.assertEqual(len(validate_prices(df, "2026-10-25", "2026-10-25")), 100)

    def test_dst_spring(self):
        """روز شروع ساعت تابستانی در برلین ۹۲ بازه دارد."""
        df = make_day("2026-03-29")
        self.assertEqual(len(validate_prices(df, "2026-03-29", "2026-03-29")), 92)

    def test_missing_interval_rejected(self):
        """اگر یک بازهٔ قیمت حذف شود، برنامه باید خطا بدهد."""
        df = make_day("2026-10-26").iloc[:-1]
        with self.assertRaises(ValueError):
            validate_prices(df, "2026-10-26", "2026-10-26")

    def test_duplicate_interval_rejected(self):
        """زمان تکراری—even با تعداد ردیف درست—باید رد شود."""
        df = make_day("2026-10-26")
        df.loc[1, "timestamp_utc"] = df.loc[0, "timestamp_utc"]
        with self.assertRaises(ValueError):
            validate_prices(df, "2026-10-26", "2026-10-26")

    def test_negative_price_allowed(self):
        """قیمت منفی واقعی در بازار ممکن است، پس نباید حذف شود."""
        df = make_day("2026-10-26")
        df.loc[0, "price_eur_mwh"] = -30.0
        self.assertEqual(validate_prices(df, "2026-10-26", "2026-10-26").loc[0, "price_eur_mwh"], -30.0)


# وقتی فایل تست را اجرا می‌کنیم، همهٔ تست‌ها آغاز می‌شوند.
if __name__ == "__main__":
    unittest.main()
