"""دریافت قیمت واقعی Day-Ahead منطقه DE-LU از Energy-Charts."""

# کتابخانهٔ ورودی‌های خط فرمان را وارد می‌کنیم.
import argparse
# برای محاسبهٔ روز بعد از آن استفاده می‌کنیم.
from datetime import timedelta
# پوشهٔ خروجی CSV را در صورت نیاز می‌سازیم.
from pathlib import Path

# pandas برای جدول داده و تاریخ‌های دارای منطقهٔ زمانی است.
import pandas as pd
# requests درخواست اینترنتی به API را ارسال می‌کند.
import requests


# آدرس رسمی API و منطقهٔ بازار مورد مطالعه.
API_URL = "https://api.energy-charts.info/price"
ZONE = "DE-LU"
TIMEZONE = "Europe/Berlin"


def validate_prices(df, start, end):
    """بررسی می‌کند که قیمت تمام بازه‌های ۱۵دقیقه‌ای، حتی روز تغییر ساعت، موجود باشد."""

    # داده را بر اساس زمان جهانی مرتب می‌کنیم.
    df = df.sort_values("timestamp_utc").reset_index(drop=True)

    # زمان یا قیمت خالی و قیمت غیرعددی نباید وارد مدل شوند.
    if df[["timestamp_utc", "price_eur_mwh"]].isna().any().any():
        raise ValueError("قیمت یا زمان نامعتبر/خالی در پاسخ API وجود دارد.")

    # timestampهای تکراری نشانهٔ مشکل هستند.
    if df["timestamp_utc"].duplicated().any():
        raise ValueError("در داده‌ها زمان تکراری وجود دارد.")

    # برای هر روز تقویمیِ برلین، همهٔ بازه‌های لازم را بررسی می‌کنیم.
    for day in pd.date_range(start, end, freq="D"):
        # ابتدای روز محلی؛ منطقهٔ زمانی به تغییر ساعت آگاه است.
        first = pd.Timestamp(day.date(), tz=TIMEZONE)
        # ابتدای روز بعد؛ نباید به سادگی ۲۴ ساعت اضافه کنیم.
        following = pd.Timestamp(day.date() + timedelta(days=1), tz=TIMEZONE)

        # فهرست کامل زمان‌های ۱۵دقیقه‌ای روز را می‌سازیم (۹۲، ۹۶ یا ۱۰۰ مورد).
        expected = pd.date_range(first, following, freq="15min", inclusive="left")
        # فقط زمان‌های همین روز را از داده انتخاب می‌کنیم.
        observed = df.loc[
            (df["timestamp_utc"] >= first.tz_convert("UTC"))
            & (df["timestamp_utc"] < following.tz_convert("UTC")),
            "timestamp_utc",
        ]
        # اگر حتی یک ردیف کم یا اضافه باشد، فایل ناقص را قبول نمی‌کنیم.
        if len(observed) != len(expected) or set(observed) != set(expected):
            raise ValueError(
                f"روز {day.date()} ناقص است: {len(observed)} "
                f"بازه به جای {len(expected)} بازهٔ ۱۵دقیقه‌ای."
            )

    # دادهٔ بررسی‌شده را برمی‌گردانیم.
    return df


def fetch_prices(start, end):
    """قیمت‌های واقعی را از API می‌گیرد و آن‌ها را اعتبارسنجی می‌کند."""

    # ابتدا مطمئن می‌شویم تاریخ‌های ورودی درست و مرتب هستند.
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("تاریخ شروع نمی‌تواند بعد از پایان باشد.")

    # هر دو تاریخ در API شامل روز کامل هستند.
    parameters = {"bzn": ZONE, "start": start, "end": end}
    # درخواست با حداکثر ۶۰ ثانیه مهلت ارسال می‌شود.
    response = requests.get(API_URL, params=parameters, timeout=60)
    # خطاهای شبکه/سرور، مثلاً ۴۲۹، را پنهان نمی‌کنیم.
    response.raise_for_status()
    # متن JSON دریافتی را به دیکشنری پایتون تبدیل می‌کنیم.
    raw = response.json()

    # طبق مستندات، قیمت باید به EUR/MWh باشد.
    if raw.get("unit") != "EUR/MWh":
        raise ValueError(f"واحد قیمت غیرمنتظره: {raw.get('unit')}")

    # دو آرایهٔ زمان و قیمت باید موجود و هم‌طول باشند.
    times, prices = raw.get("unix_seconds"), raw.get("price")
    if not isinstance(times, list) or not isinstance(prices, list) or len(times) != len(prices):
        raise ValueError("پاسخ API فاقد آرایه‌های معتبر زمان و قیمت است.")

    # جدول سادهٔ دو ستون زمان یونیکس و قیمت را می‌سازیم.
    df = pd.DataFrame({"unix_seconds": times, "price_eur_mwh": prices})
    # اطمینان از عددی‌بودن قیمت‌ها؛ مقادیر خراب به NaN تبدیل می‌شوند.
    df["price_eur_mwh"] = pd.to_numeric(df["price_eur_mwh"], errors="coerce")
    # یونیکس برحسب ثانیه است و ابتدا به زمان جهانی تبدیل می‌شود.
    df["timestamp_utc"] = pd.to_datetime(df["unix_seconds"], unit="s", utc=True)
    # زمان محلی برلین را هم برای بررسی روز تحویل اضافه می‌کنیم.
    df["timestamp_berlin"] = df["timestamp_utc"].dt.tz_convert(TIMEZONE)

    # تنها در صورت کامل‌بودن تمام روزها داده را برمی‌گردانیم.
    return validate_prices(df, start, end)


def main():
    """تاریخ‌ها را می‌خواند، دانلود می‌کند و CSV قابل بازتولید می‌سازد."""

    # پارامترهای قابل‌تغییر اجرا را تعریف می‌کنیم.
    parser = argparse.ArgumentParser(description="دریافت قیمت ۱۵دقیقه‌ای Day-Ahead بازار DE-LU")
    parser.add_argument("--start", default="2026-10-01", help="تاریخ شروع YYYY-MM-DD")
    parser.add_argument("--end", default="2026-10-31", help="تاریخ پایان YYYY-MM-DD")
    parser.add_argument("--output", default="prices_DE-LU.csv", help="نام فایل CSV")
    # آرگومان‌هایی که کاربر وارد کرده خوانده می‌شوند.
    args = parser.parse_args()

    # دریافت و کنترل داده انجام می‌شود؛ در خطا فایل ساخته نمی‌شود.
    df = fetch_prices(args.start, args.end)
    # پوشهٔ مقصد را فقط پس از تأیید داده‌ها می‌سازیم.
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    # زمان‌های UTC/برلین و قیمت را با حفظ قیمت‌های منفی ذخیره می‌کنیم.
    df[["timestamp_utc", "timestamp_berlin", "price_eur_mwh"]].to_csv(
        args.output, index=False
    )
    # تعداد بازه‌های معتبر را به کاربر گزارش می‌کنیم.
    print(f"{len(df)} بازهٔ معتبر ذخیره شد: {args.output}")
    # برای رعایت مجوز منبع، نام منبع را نمایش می‌دهیم.
    print("منبع: Energy-Charts.info / Bundesnetzagentur (CC BY 4.0)")


# این بخش فقط وقتی فایل مستقیماً اجرا شود فعال می‌شود.
if __name__ == "__main__":
    main()
