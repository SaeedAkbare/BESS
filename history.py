"""دانلود تاریخچهٔ واقعی قیمت‌های ۱۵دقیقه‌ای؛ هر ماه جداگانه کنترل می‌شود."""

# pandas برای ساخت ماه‌ها و ترکیب جدول‌هاست.
import pandas as pd
# برای توقف کوتاه بین درخواست‌ها به API.
import time
# برای کنترل محدودیت تعداد درخواست‌های API.
import requests
# برای ساخت پوشهٔ خروجی.
from pathlib import Path

# همان تابع سادهٔ دانلود و بررسیِ data.py را دوباره استفاده می‌کنیم.
from data import fetch_prices


def main():
    """ماه‌های آموزش و آزمون را می‌گیرد، کامل‌بودن را می‌سنجد و یک CSV می‌سازد."""

    # فقط قیمت‌های بعد از آغاز بازار ۱۵دقیقه‌ای را انتخاب می‌کنیم.
    months = pd.date_range("2025-10-01", "2026-10-01", freq="MS")

    # جدول هر ماه فقط پس از اعتبارسنجی به این فهرست اضافه می‌شود.
    monthly_tables = []

    # فایل هر ماه را همان لحظه ذخیره می‌کنیم تا در خطا از دست نرود.
    output_dir = Path("output/history")
    output_dir.mkdir(parents=True, exist_ok=True)

    # هر درخواست یک ماه است تا خطا و ماه ناقص راحت شناسایی شوند.
    for month in months:
        # اولین روز و آخرین روز تقویمی همان ماه.
        start = month.strftime("%Y-%m-%d")
        end = (month + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")

        # اگر API خطای 429 بدهد، به‌جای درخواست‌های پشت‌سرهم صبر می‌کنیم.
        for attempt in range(3):
            try:
                # این تابع تمام روزها، قیمت‌ها و تغییر ساعت را بررسی می‌کند.
                df = fetch_prices(start, end)
                break
            except requests.HTTPError as error:
                # بقیهٔ خطاهای سرور را پنهان نمی‌کنیم.
                if error.response is None or error.response.status_code != 429 or attempt == 2:
                    raise
                # پس از محدودیت API به‌ترتیب ۶۰ و ۱۲۰ ثانیه مکث می‌کنیم.
                wait = 60 * (attempt + 1)
                print(f"محدودیت API (429)، تلاش دوباره پس از {wait} ثانیه...", flush=True)
                time.sleep(wait)

        # هر ماه یک فایلِ واقعی و بررسی‌شده خواهد داشت.
        table = df[["timestamp_utc", "timestamp_berlin", "price_eur_mwh"]]
        table.to_csv(output_dir / f"DE-LU_{month.strftime('%Y-%m')}.csv", index=False)
        monthly_tables.append(table)
        print(f"ماه {month.strftime('%Y-%m')}: {len(df)} بازهٔ معتبر", flush=True)

        # ۱۵ ثانیه فاصله می‌گذاریم تا API را با درخواست سریع تحت فشار نگذاریم.
        time.sleep(15)

    # تمام ماه‌ها را پشت سر هم قرار می‌دهیم.
    result = pd.concat(monthly_tables, ignore_index=True)

    # حتی بین دو ماه نیز نباید یک زمان دوبار دیده شود.
    if result["timestamp_utc"].duplicated().any():
        raise ValueError("زمان تکراری بین فایل‌های ماهانه پیدا شد.")

    # زمان‌ها را مرتب می‌کنیم تا فایل برای آموزش آماده باشد.
    result = result.sort_values("timestamp_utc").reset_index(drop=True)

    # تنها پس از صحت‌سنجی کامل فایل ترکیبی خروجی تولید می‌شود.
    filename = "output/prices_DE-LU_2025-10_to_2026-10.csv"
    result.to_csv(filename, index=False)
    print(f"تعداد کل بازه‌های معتبر: {len(result)}")
    print(f"فایل نهایی: {filename}")
    print("منبع: Energy-Charts.info")


# اجرای مستقیم این فایل، کار را آغاز می‌کند.
if __name__ == "__main__":
    main()
