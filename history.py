"""دانلود تاریخچهٔ واقعی قیمت‌های ۱۵دقیقه‌ای؛ هر ماه جداگانه کنترل می‌شود."""

# pandas برای ساخت ماه‌ها و ترکیب جدول‌هاست.
import pandas as pd

# همان تابع سادهٔ دانلود و بررسیِ data.py را دوباره استفاده می‌کنیم.
from data import fetch_prices


def main():
    """ماه‌های آموزش و آزمون را می‌گیرد، کامل‌بودن را می‌سنجد و یک CSV می‌سازد."""

    # فقط قیمت‌های بعد از آغاز بازار ۱۵دقیقه‌ای را انتخاب می‌کنیم.
    months = pd.date_range("2025-10-01", "2026-10-01", freq="MS")

    # جدول هر ماه فقط پس از اعتبارسنجی به این فهرست اضافه می‌شود.
    monthly_tables = []

    # هر درخواست یک ماه است تا خطا و ماه ناقص راحت شناسایی شوند.
    for month in months:
        # اولین روز و آخرین روز تقویمی همان ماه.
        start = month.strftime("%Y-%m-%d")
        end = (month + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")

        # همین تابع تمام روزها و تغییر ساعت را بررسی می‌کند.
        df = fetch_prices(start, end)

        # زمان و قیمت کافی است؛ داده‌ها به سال/ماه وابسته نیستند.
        monthly_tables.append(df[["timestamp_utc", "timestamp_berlin", "price_eur_mwh"]])
        print(f"ماه {month.strftime('%Y-%m')}: {len(df)} بازهٔ معتبر")

    # تمام ماه‌ها را پشت سر هم قرار می‌دهیم.
    result = pd.concat(monthly_tables, ignore_index=True)

    # حتی بین دو ماه نیز نباید یک زمان دوبار دیده شود.
    if result["timestamp_utc"].duplicated().any():
        raise ValueError("زمان تکراری بین فایل‌های ماهانه پیدا شد.")

    # زمان‌ها را مرتب می‌کنیم تا فایل برای آموزش آماده باشد.
    result = result.sort_values("timestamp_utc").reset_index(drop=True)

    # تنها پس از صحت‌سنجی کامل فایل خروجی تولید می‌شود.
    filename = "prices_DE-LU_2025-10_to_2026-10.csv"
    result.to_csv(filename, index=False)
    print(f"تعداد کل بازه‌های معتبر: {len(result)}")
    print(f"فایل نهایی: {filename}")
    print("منبع: Energy-Charts.info")


# اجرای مستقیم این فایل، کار را آغاز می‌کند.
if __name__ == "__main__":
    main()
