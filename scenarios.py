"""ساخت ۵۰ سناریوی قیمت Day-Ahead با رگرسیون چندکی و بوت‌استرپِ کل روز.

فقط برای روزهای معمولی ۹۶ بازه‌ای. برای روزهای ۹۲/۱۰۰ بازه‌ای فعلاً خطا می‌دهیم.
قیمت‌های اکتبر ۲۰۲۶ هرگز برای آموزش یا ساختِ باقیمانده‌ها استفاده نمی‌شوند.
"""
import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


# چهار بازهٔ اعتبارسنجی زمانی؛ آموزشِ هر بازه فقط با گذشتهٔ همان بازه است.
FOLDS = [
    ("2026-02-01", "2026-04-01"),
    ("2026-04-01", "2026-06-01"),
    ("2026-06-01", "2026-08-01"),
    ("2026-08-01", "2026-10-01"),
]
FEATURES = ["sin_hour", "cos_hour", "sin_year", "cos_year",
            "weekday", "prev_mean", "prev_min", "prev_max"]


def prepare(csv_file):
    """CSV واقعی را به جدولِ قیمت و ویژگی‌های قابل دانستن قبل از حراج تبدیل می‌کند."""

    # همهٔ زمان‌ها را ابتدا در UTC می‌خوانیم تا ساعت تکراری پاییز مشکلی نسازد.
    df = pd.read_csv(csv_file)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    if df["timestamp_utc"].duplicated().any():
        raise ValueError("زمان تکراری در فایل قیمت وجود دارد.")

    df["price_eur_mwh"] = pd.to_numeric(df["price_eur_mwh"], errors="coerce")
    if df["price_eur_mwh"].isna().any():
        raise ValueError("قیمت نامعتبر یا خالی وجود دارد.")

    # تاریخِ تحویل و ساعت محلی را به وقت برلین استخراج می‌کنیم.
    local = df["timestamp_utc"].dt.tz_convert("Europe/Berlin")
    df["day"] = local.dt.date
    hour = local.dt.hour + local.dt.minute / 60
    year_day = local.dt.dayofyear
    df["sin_hour"] = np.sin(2 * np.pi * hour / 24)
    df["cos_hour"] = np.cos(2 * np.pi * hour / 24)
    df["sin_year"] = np.sin(2 * np.pi * year_day / 365.25)
    df["cos_year"] = np.cos(2 * np.pi * year_day / 365.25)
    df["weekday"] = local.dt.dayofweek

    # خلاصهٔ قیمت «روز قبل» در زمانِ حراج امروز از قبل منتشر شده است.
    daily = df.groupby("day")["price_eur_mwh"].agg(["mean", "min", "max"])
    previous = daily.shift(1)  # از قیمت خودِ روز هدف استفاده نمی‌کنیم.
    for feature, column in [("prev_mean", "mean"), ("prev_min", "min"),
                            ("prev_max", "max")]:
        df[feature] = df["day"].map(previous[column])

    # روز نخست، تاریخچهٔ روز قبل را در این فایل ندارد؛ حذفش می‌کنیم.
    return df.dropna(subset=FEATURES).copy()


def fit_quantiles(train):
    """سه مدل کوچک sklearn برای چندک‌های ۱۰، ۵۰ و ۹۰ درصد می‌سازد."""

    models = {}
    for quantile in (0.1, 0.5, 0.9):
        model = HistGradientBoostingRegressor(
            loss="quantile", quantile=quantile, max_iter=80,
            max_leaf_nodes=15, min_samples_leaf=80,
            learning_rate=0.08, random_state=42,
        )
        model.fit(train[FEATURES], train["price_eur_mwh"])
        models[quantile] = model
    return models


def predict(models, rows):
    """پیش‌بینی‌ها را مرتب می‌کند تا چندک پایین از میانه بالاتر نباشد."""

    x = rows[FEATURES]
    middle = models[0.5].predict(x)
    lower = np.minimum(models[0.1].predict(x), middle)
    upper = np.maximum(models[0.9].predict(x), middle)
    return lower, middle, upper


def scale_residual(actual, lower, middle, upper):
    """خطای مثبت/منفی را با پهنای چندکی مناسب نرمال می‌کند."""

    # کف ۱ یورو/MWh مانع تقسیم بر صفر در قیمت‌های کم‌نوسان می‌شود.
    error = actual - middle
    positive_spread = np.maximum(upper - middle, 1.0)
    negative_spread = np.maximum(middle - lower, 1.0)
    return np.where(error >= 0, error / positive_spread, error / negative_spread)


def past_residual_days(table):
    """باقیمانده‌های خارج از نمونه را از دوره‌های اعتبارسنجیِ زمانی می‌سازد."""

    days = []
    actual_all, low_all, high_all = [], [], []

    for start, end in FOLDS:
        start_day, end_day = date.fromisoformat(start), date.fromisoformat(end)
        train = table[table["day"] < start_day]
        valid = table[(table["day"] >= start_day) & (table["day"] < end_day)]
        if len(train) < 2000 or valid.empty:
            raise ValueError("دادهٔ تاریخی کافی برای اعتبارسنجی زمانی نیست.")

        # در این Fold، حتی یک ردیف از آینده وارد آموزش نمی‌شود.
        lower, middle, upper = predict(fit_quantiles(train), valid)
        actual = valid["price_eur_mwh"].to_numpy()
        scaled = scale_residual(actual, lower, middle, upper)

        # همهٔ بازه‌های این دوره را برای پوشش چندکیِ مستقل نگه می‌داریم.
        actual_all.extend(actual)
        low_all.extend(lower)
        high_all.extend(upper)

        # باقیمانده‌های یک روز را یکجا حفظ می‌کنیم؛ بازه‌ها مستقل نمونه‌گیری نمی‌شوند.
        valid = valid.assign(residual=scaled)
        for _, one_day in valid.groupby("day", sort=True):
            if len(one_day) == 96:  # فقط با روز ۹۶بازه‌ای تطبیق مستقیم داریم.
                days.append(one_day["residual"].to_numpy())

    # باید حداقل ۵۰ روز تاریخیِ مستقل داشته باشیم.
    if len(days) < 50:
        raise ValueError("کمتر از ۵۰ روز باقیماندهٔ تاریخی معتبر داریم.")
    coverage = np.mean((np.array(actual_all) >= np.array(low_all)) &
                       (np.array(actual_all) <= np.array(high_all)))
    return np.array(days), coverage


def sample_scenarios(median, lower, upper, historical_days, seed=42, count=50):
    """۵۰ مسیر کاملِ روزانه را با نمونه‌گیری تصادفی از روزهای گذشته تولید می‌کند."""

    if historical_days.shape[1] != len(median):
        raise ValueError("طول مسیرهای تاریخی و روز هدف متفاوت است.")

    # یک اندیس برای «کل روز» می‌کشیم، نه یک اندیس برای هر ساعت.
    rng = np.random.default_rng(seed)
    selected = historical_days[rng.choice(len(historical_days), count, replace=True)]
    upper_spread = np.maximum(upper - median, 1.0)
    lower_spread = np.maximum(median - lower, 1.0)

    # باقیمانده‌های نرمال‌شده را متناسب با عدم‌قطعیت روز جدید بازسازی می‌کنیم.
    spreads = np.where(selected >= 0, upper_spread, lower_spread)
    return median + selected * spreads


def main():
    """دادهٔ تاریخی را می‌خواند و سناریوهای یک روزِ اکتبر ۲۰۲۶ را ذخیره می‌کند."""

    parser = argparse.ArgumentParser(description="۵۰ سناریوی قیمت DE-LU با sklearn")
    parser.add_argument("--input", required=True, help="CSV تاریخچهٔ تأییدشده")
    parser.add_argument("--date", default="2026-10-15", help="روز آزمون YYYY-MM-DD")
    parser.add_argument("--output", default="output/scenarios_2026-10-15.csv")
    args = parser.parse_args()
    target = date.fromisoformat(args.date)

    # کل اکتبر از آموزش کنار گذاشته می‌شود؛ یک روز عادی را آزمایش می‌کنیم.
    if not (date(2026, 10, 1) <= target <= date(2026, 10, 31)):
        raise ValueError("برای آزمون فعلی، روز هدف باید در اکتبر ۲۰۲۶ باشد.")

    table = prepare(args.input)
    cutoff = date(2026, 10, 1)
    train = table[table["day"] < cutoff]
    test = table[table["day"] == target]
    if len(test) != 96:
        raise ValueError("نسخهٔ اولیه فقط روز عادی ۹۶بازه‌ای را می‌پذیرد.")

    # این خطاها فقط از پیش‌بینی‌های خارج از نمونهٔ گذشته به دست می‌آیند.
    residuals, coverage = past_residual_days(train)

    # پیش‌بینی روز هدف از مدلِ آموزش‌دیده فقط تا سپتامبر است.
    lower, middle, upper = predict(fit_quantiles(train), test)
    scenarios = sample_scenarios(middle, lower, upper, residuals)

    # قیمت واقعی روز آزمون را در خروجی قرار نمی‌دهیم تا نشت اطلاعات رخ ندهد.
    result = pd.DataFrame({
        "timestamp_utc": test["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "q10": lower, "q50": middle, "q90": upper,
    })
    for i, one_path in enumerate(scenarios, start=1):
        result[f"scenario_{i:02d}"] = one_path

    # فایل خروجی شامل ۵۰ ستون سناریو و سه ستون چندکی است.
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"روز آزمون: {target}، تعداد بازه‌ها: {len(test)}")
    print(f"روزهای باقیماندهٔ خارج از نمونه: {len(residuals)}")
    print(f"پوشش تجربی بازهٔ q10 تا q90 در اعتبارسنجی: {coverage:.3f}")
    print(f"۵۰ سناریو با وزن برابر ۱/۵۰ ساخته شد: {args.output}")
    print("هشدار: پوشش تجربی و سناریوها هنوز اعتبارسنجی کامل اقتصادی نشده‌اند.")


if __name__ == "__main__":
    main()
