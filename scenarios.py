"""ساخت ۵۰ سناریوی قیمت Day-Ahead با رگرسیون چندکی و بوت‌استرپِ کل روز.

فقط برای روزهای معمولی ۹۶ بازه‌ای. برای روزهای ۹۲/۱۰۰ بازه‌ای فعلاً خطا می‌دهیم.
قیمت‌های اکتبر ۲۰۲۶ هرگز برای آموزش یا ساختِ باقیمانده‌ها استفاده نمی‌شوند.
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


# سه بازهٔ گذشته برای کالیبراسیون؛ سپتامبر را برای آزمون مستقل نگه می‌داریم.
FOLDS = [
    ("2026-02-01", "2026-04-01"),
    ("2026-04-01", "2026-06-01"),
    ("2026-06-01", "2026-09-01"),
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


def score_quantile(scores, target_coverage=0.80):
    """صدک تجربیِ خطاهای قبلی با اصلاح تعداد نمونه را برمی‌گرداند."""

    scores = np.asarray(scores)
    if len(scores) == 0:
        raise ValueError("هیچ خطای قبلی برای کالیبراسیون وجود ندارد.")
    # رتبهٔ صدک تنها با مشاهده‌های گذشته تعیین می‌شود.
    rank = min(len(scores) - 1, int(np.ceil((len(scores) + 1) * target_coverage)) - 1)
    return float(np.sort(scores)[rank])


def calibration_gap(actual, lower, upper, target_coverage=0.80):
    """میزان بیرون‌زدگی قیمت از بازهٔ خام را با خطاهای واقعیِ گذشته می‌سنجد."""

    scores = np.maximum.reduce([lower - actual, actual - upper,
                                np.zeros(len(actual))])
    return score_quantile(scores, target_coverage)


def coverage_rate(actual, lower, upper):
    """سهم قیمت‌های واقعی درون بازه را محاسبه می‌کند."""

    return float(np.mean((actual >= lower) & (actual <= upper)))


def past_residual_days(table):
    """با Foldهای زمانی، خطای روزانه و حاشیهٔ کالیبراسیون را می‌سازد."""

    # دادهٔ فوریه تا اوت برای کالیبراسیون؛ سپتامبر را نمی‌بینیم.
    parts = []
    for start, end in FOLDS:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        train = table[table["day"] < first]
        valid = table[(table["day"] >= first) & (table["day"] < last)].copy()
        if len(train) < 2000 or valid.empty:
            raise ValueError("دادهٔ تاریخی کافی برای اعتبارسنجی زمانی نیست.")

        # مدل هر Fold فقط از ماه‌های قبل از آن Fold آموزش می‌بیند.
        lower, middle, upper = predict(fit_quantiles(train), valid)
        valid["lower"], valid["middle"], valid["upper"] = lower, middle, upper
        parts.append(valid)

    # باقیمانده‌های «واقعاً خارج از نمونه» را کنار هم می‌گذاریم.
    past = pd.concat(parts, ignore_index=True)
    actual = past["price_eur_mwh"].to_numpy()
    lower = past["lower"].to_numpy()
    middle = past["middle"].to_numpy()
    upper = past["upper"].to_numpy()
    raw_coverage = coverage_rate(actual, lower, upper)

    # فقط همین بازهٔ کالیبراسیون می‌تواند اندازهٔ حاشیه را تعیین کند.
    gap = calibration_gap(actual, lower, upper)
    calibrated_coverage = coverage_rate(actual, lower - gap, upper + gap)

    # خطای نرمال‌شده نسبت به بازهٔ جدید را برای کل مسیرهای روزانه می‌سازیم.
    # پهنای بازه در روز هدف نیز همین‌طور اصلاح خواهد شد.
    past["residual"] = scale_residual(actual, lower - gap, middle, upper + gap)
    days = []
    for _, one_day in past.groupby("day", sort=True):
        if len(one_day) == 96:
            days.append(one_day["residual"].to_numpy())

    # نمونه‌گیری روزانه باید روی تعداد کافی از روزهای گذشته باشد.
    if len(days) < 50:
        raise ValueError("کمتر از ۵۰ روز باقیماندهٔ تاریخی معتبر داریم.")
    # این جدول برای کالیبراسیون غلتان به‌کار می‌رود؛ فقط روزهای گذشته را دارد.
    past["score"] = np.maximum.reduce([lower - actual, actual - upper,
                                       np.zeros(len(actual))])
    return np.array(days), gap, raw_coverage, calibrated_coverage, past[["day", "score"]]


def september_diagnostic(table, residuals, fixed_gap, past_scores):
    """پوشش سپتامبر را با حاشیهٔ ثابت و کالیبراسیون غلتان مقایسه می‌کند.

    الگوریتم غلتان بعد از مشاهدهٔ نتیجهٔ روش ثابت طراحی شده است؛
    پس سپتامبر دیگر آزمونِ کاملاً دست‌نخورده محسوب نمی‌شود.
    """

    first, last = date(2026, 9, 1), date(2026, 10, 1)
    train = table[table["day"] < first]
    valid = table[(table["day"] >= first) & (table["day"] < last)]
    lower, middle, upper = predict(fit_quantiles(train), valid)
    actual = valid["price_eur_mwh"].to_numpy()

    # معیارهای روش قبلی را حفظ می‌کنیم تا مقایسه شفاف باشد.
    before = coverage_rate(actual, lower, upper)
    after = coverage_rate(actual, lower - fixed_gap, upper + fixed_gap)
    valid = valid.assign(lower=lower, middle=middle, upper=upper)

    # خطای تمام روزهای قبلی آماده است؛ روزهای سپتامبر تدریجاً اضافه می‌شوند.
    errors = past_scores.copy()
    count_inside, total, scenarios_inside, n_days = 0, 0, 0, 0
    # نسبت خطای واقعی به پهنای ۱۰–۹۰٪ سناریوها را برای تنظیم ماه بعد نگه می‌داریم.
    positive_ratios, negative_ratios = [], []
    for day, one_day in valid.groupby("day", sort=True):
        if len(one_day) != 96:
            continue

        # در آغاز هر روز فقط خطاهای ۳۰ روز تقویمیِ پیش از آن مجازند.
        recent = errors[(errors["day"] < day) &
                        (errors["day"] >= day - timedelta(days=30))]
        if len(recent) < 96 * 10:
            raise ValueError("کمتر از ده روز خطای تاریخی در پنجرهٔ غلتان وجود دارد.")
        day_gap = score_quantile(recent["score"].to_numpy())

        # بازهٔ کالیبره‌شده را پیش از خواندن قیمت حقیقی همین روز تعیین می‌کنیم.
        lo = one_day["lower"].to_numpy()
        mid = one_day["middle"].to_numpy()
        hi = one_day["upper"].to_numpy()
        actual_day = one_day["price_eur_mwh"].to_numpy()
        count_inside += int(((actual_day >= lo - day_gap) &
                             (actual_day <= hi + day_gap)).sum())

        # پوشش تجربیِ صدک ۱۰ و ۹۰ سناریوها یک معیارِ مستقل از بازه است.
        paths = sample_scenarios(mid, lo - day_gap, hi + day_gap,
                                 residuals, seed=42 + n_days)
        band10, band90 = np.quantile(paths, [0.1, 0.9], axis=0)
        scenarios_inside += int(((actual_day >= band10) &
                                 (actual_day <= band90)).sum())
        # میزان افزایش لازمِ سناریوهای مثبت و منفی نسبت به میانه.
        positive_width = np.maximum(band90 - mid, 1.0)
        negative_width = np.maximum(mid - band10, 1.0)
        ratios_day = np.where(actual_day >= mid,
                              (actual_day - mid) / positive_width,
                              (mid - actual_day) / negative_width)
        positive_ratios.extend(ratios_day[actual_day >= mid])
        negative_ratios.extend(ratios_day[actual_day < mid])
        total += len(one_day)
        n_days += 1

        # اکنون قیمت روز سپری‌شده مجاز است به تاریخچهٔ روز بعد اضافه شود.
        scores = np.maximum.reduce([lo - actual_day, actual_day - hi,
                                    np.zeros(len(actual_day))])
        errors = pd.concat([
            errors, pd.DataFrame({"day": [day] * len(scores), "score": scores})
        ], ignore_index=True)

    if total == 0:
        raise ValueError("هیچ روز عادی در سپتامبر برای ارزیابی وجود ندارد.")

    # خطاهای کل سپتامبر در پایان ماه معلوم‌اند و برای پیش‌بینی اکتبر مجازند.
    sep = errors[(errors["day"] >= first) & (errors["day"] < last)]
    gap_october = score_quantile(sep["score"].to_numpy())
    # فقط پس از پایان سپتامبر، یک ضریب پهنا برای کل سناریوهای اکتبر تعیین می‌کنیم.
    positive_factor = max(1.0, score_quantile(np.array(positive_ratios)))
    negative_factor = max(1.0, score_quantile(np.array(negative_ratios)))
    return (before, after, count_inside / total, scenarios_inside / total,
            n_days, gap_october, positive_factor, negative_factor)


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


def evaluate_october(table, models, residuals, gap, positive_factor, negative_factor):
    """آزمون نهایی اکتبر: قیمت واقعی فقط پس از ساخت سناریو خوانده می‌شود."""

    october = table[(table["day"] >= date(2026, 10, 1)) &
                    (table["day"] <= date(2026, 10, 31))]
    in_band, in_scenarios, n, n_days = 0, 0, 0, 0
    for day, rows in october.groupby("day", sort=True):
        # نسخهٔ فعلی روز تغییر ساعت پاییزیِ ۱۰۰ بازه‌ای را پشتیبانی نمی‌کند.
        if len(rows) != 96:
            continue
        low, median, high = predict(models, rows)
        low, high = low - gap, high + gap
        # از قیمت روز برای تولید مسیرها استفاده نشده است.
        paths = sample_scenarios(median, low, high, residuals,
                                 seed=42 + n_days)
        paths = median + np.where(paths >= median, positive_factor, negative_factor) * (paths - median)
        p10, p90 = np.quantile(paths, [0.1, 0.9], axis=0)
        actual = rows["price_eur_mwh"].to_numpy()
        in_band += int(((actual >= low) & (actual <= high)).sum())
        in_scenarios += int(((actual >= p10) & (actual <= p90)).sum())
        n += len(actual)
        n_days += 1
    if n == 0:
        raise ValueError("هیچ روز عادی در اکتبر برای آزمون وجود ندارد.")
    return in_band / n, in_scenarios / n, n_days


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

    # کالیبراسیون مقدماتی با فوریه تا اوت؛ سپتامبر ماه توسعه است.
    residuals, gap, raw_calib, fixed_calib, past_scores = past_residual_days(train)
    raw_sep, fixed_sep, rolling_sep, scenario_sep, sep_days, october_gap, positive_factor, negative_factor = (
        september_diagnostic(train, residuals, gap, past_scores)
    )

    # مدل نهایی تا پایان سپتامبر آموزش می‌بیند؛ قیمت‌های اکتبر وارد آموزش نمی‌شوند.
    models = fit_quantiles(train)
    # معیارهای اکتبر فقط یک بار، بعد از قفل‌کردن ضریب‌ها، گزارش می‌شوند.
    october_band, october_paths, october_days = evaluate_october(
        table, models, residuals, october_gap, positive_factor, negative_factor
    )
    lower, middle, upper = predict(models, test)
    # حاشیهٔ نهایی فقط از خطاهای سپتامبر ۲۰۲۶ تعیین شده است.
    lower, upper = lower - october_gap, upper + october_gap
    scenarios = sample_scenarios(middle, lower, upper, residuals)
    # ضریبِ فقط-سپتامبر، پراکندگی همهٔ مسیرها را حول پیش‌بینی مرکزی افزایش می‌دهد.
    scenarios = middle + np.where(scenarios >= middle, positive_factor, negative_factor) * (scenarios - middle)
    p10, p90 = np.quantile(scenarios, [0.1, 0.9], axis=0)

    # این فایل فقط پیش‌بینی و سناریوست؛ قیمت واقعی روز هدف در آن نیست.
    # «بازهٔ کالیبره» لزوماً چندک حقیقی q10/q90 نیست؛ نام درست می‌گذاریم.
    result = pd.DataFrame({
        "timestamp_utc": test["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lower_calibrated": lower, "q50_forecast": middle, "upper_calibrated": upper,
        "scenario_p10": p10, "scenario_p90": p90,
    })
    for i, one_path in enumerate(scenarios, start=1):
        result[f"scenario_{i:02d}"] = one_path

    # فایل خروجی شامل ۵۰ ستون سناریو و سه ستون چندکی است.
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(f"روز آزمون: {target}، تعداد بازه‌ها: {len(test)}")
    print(f"روزهای باقیماندهٔ خارج از نمونه: {len(residuals)}")
    print(f"حاشیهٔ کالیبراسیون از فوریه تا اوت: {gap:.2f} یورو/MWh")
    print(f"پوشش همان دوره قبل/بعد از اصلاح: {raw_calib:.3f} / {fixed_calib:.3f}")
    print(f"سپتامبر ({sep_days} روز)، پوشش خام/اصلاح ثابت/اصلاح غلتان: "
          f"{raw_sep:.3f} / {fixed_sep:.3f} / {rolling_sep:.3f}")
    print(f"پوشش صدک ۱۰–۹۰٪ سناریوهای غلتان سپتامبر: {scenario_sep:.3f}")
    print(f"حاشیهٔ صرفاً گذشته برای شروع اکتبر: {october_gap:.2f} یورو/MWh")
    print(f"ضرایب سمت مثبت/منفی (فقط سپتامبر): {positive_factor:.3f} / {negative_factor:.3f}")
    print(f"آزمون دست‌نخوردهٔ اکتبر ({october_days} روز عادی)، "
          f"پوشش بازه/صدک سناریوها: {october_band:.3f} / {october_paths:.3f}")
    print("هشدار: سپتامبر ماه توسعه است؛ ۲۵ اکتبر ۱۰۰بازه‌ای در آزمون سناریو حذف شده.")
    print(f"۵۰ سناریو با وزن برابر ۱/۵۰ ساخته شد: {args.output}")
    print("نکته: کالیبراسیون حاشیه‌ای تضمین CVaR یا اعتبار اقتصادی نمی‌دهد.")


if __name__ == "__main__":
    main()
