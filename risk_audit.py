"""بررسی ریسک ۵۰ سناریوی قیمت با دادهٔ واقعی اکتبر ۲۰۲۶.

این فایل فقط کیفیت سناریوهای قیمت را می‌سنجد؛ سود باتری یا CVaR آن را محاسبه نمی‌کند.
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# توابع سناریوسازی قبلی را استفاده می‌کنیم تا روش آزمون دقیقاً همان روش پروژه باشد.
from scenarios import (prepare, fit_quantiles, predict, past_residual_days,
                       september_diagnostic, sample_scenarios)


def serial_correlation(values):
    """همبستگی قیمت دو بازهٔ ۱۵دقیقه‌ایِ متوالی در یک روز را برمی‌گرداند."""

    # برای روزهای با قیمت ثابت، همبستگی تعریف نشده است.
    if np.std(values[:-1]) == 0 or np.std(values[1:]) == 0:
        return float("nan")
    return float(np.corrcoef(values[:-1], values[1:])[0, 1])


def risk_metrics(actual, paths, historical_low, historical_high):
    """قیمت واقعی را با توزیع سناریوها و دم‌های بالایی/پایینی مقایسه می‌کند.

    actual: آرایهٔ (روز، ۹۶ بازه)؛ paths: آرایهٔ (روز، ۵۰ سناریو، ۹۶ بازه).
    """

    # ابتدا شکل ورودی را بررسی می‌کنیم؛ هیچ قیمتِ آزمایشی نباید گم شود.
    if actual.ndim != 2 or paths.ndim != 3:
        raise ValueError("شکل آرایه‌های قیمت/سناریو درست نیست.")
    if actual.shape[0] != paths.shape[0] or actual.shape[1] != paths.shape[2]:
        raise ValueError("تعداد روزها یا بازه‌ها بین قیمت و سناریو متفاوت است.")
    if not np.isfinite(actual).all() or not np.isfinite(paths).all():
        raise ValueError("قیمت NaN یا نامتناهی وجود دارد.")

    # صدک ۱۰ و ۹۰ هر بازه از ۵۰ سناریو محاسبه می‌شود.
    p10, p90 = np.quantile(paths, [0.1, 0.9], axis=1)
    below = float(np.mean(actual < p10))
    above = float(np.mean(actual > p90))

    # آستانه‌های نادر در این اجرا فقط از دورهٔ آموزش (قبل از اکتبر) آمده‌اند.
    # مقایسهٔ فراوانی قیمت منفی و قیمت‌های خارج از ۵/۹۵ تاریخی.
    extreme_rates = {
        "negative_actual": float(np.mean(actual < 0)),
        # تعداد صریح را هم می‌نویسیم تا گردکردن صفرِ اشتباه نشان ندهد.
        "negative_actual_count": int(np.sum(actual < 0)),
        "negative_scenarios": float(np.mean(paths < 0)),
        "below_training_p05_actual": float(np.mean(actual < historical_low)),
        "below_training_p05_scenarios": float(np.mean(paths < historical_low)),
        "above_training_p95_actual": float(np.mean(actual > historical_high)),
        "above_training_p95_scenarios": float(np.mean(paths > historical_high)),
    }

    # اختلاف بیشترین و کمترین قیمت در کل یک روز را مقایسه می‌کنیم.
    real_range = np.ptp(actual, axis=1)
    scenario_range = np.ptp(paths, axis=2)
    high_range = np.quantile(scenario_range, 0.9, axis=1)

    # سنجش دمِ کمینه و بیشینهٔ یک روز، نه فقط تک‌بازه‌ها.
    real_min, real_max = actual.min(axis=1), actual.max(axis=1)
    predicted_min = paths.min(axis=2)
    predicted_max = paths.max(axis=2)
    low_min = np.quantile(predicted_min, 0.1, axis=1)
    high_max = np.quantile(predicted_max, 0.9, axis=1)

    # همبستگی بازه‌های مجاور را هم مقایسه می‌کنیم.
    real_corr = [serial_correlation(day) for day in actual]
    path_corr = [serial_correlation(path) for day in paths for path in day]

    # عددهای گزارش فقط معیارهای تشخیصی‌اند، نه سود/زیان یک برنامهٔ باتری.
    return {
        "days_evaluated": int(len(actual)),
        "intervals_evaluated": int(actual.size),
        "scenarios_per_day": int(paths.shape[1]),
        "training_p05_eur_mwh": float(historical_low),
        "training_p95_eur_mwh": float(historical_high),
        "below_scenario_p10_rate": below,     # هدف اسمی حدود ۱۰٪
        "above_scenario_p90_rate": above,     # هدف اسمی حدود ۱۰٪
        "scenario_p10_p90_coverage": 1.0 - below - above,  # هدف اسمی ۸۰٪
        "extreme_interval_rates": extreme_rates,
        "mean_actual_daily_range_eur_mwh": float(real_range.mean()),
        "mean_scenario_daily_range_eur_mwh": float(scenario_range.mean()),
        "actual_daily_range_above_scenario_p90_rate":
            float(np.mean(real_range > high_range)),
        "actual_daily_min_below_scenario_min_p10_rate":
            float(np.mean(real_min < low_min)),
        "actual_daily_max_above_scenario_max_p90_rate":
            float(np.mean(real_max > high_max)),
        "mean_actual_adjacent_quarterhour_correlation":
            float(np.nanmean(real_corr)),
        "mean_scenario_adjacent_quarterhour_correlation":
            float(np.nanmean(path_corr)),
        "risk_ready": False,  # این تست، دنبالهٔ سود و CVaR را تأیید نمی‌کند.
        "notes": [
            "قیمت‌های اکتبر فقط بعد از تولید سناریوی هر روز برای ارزیابی خوانده شدند.",
            "روز ۲۵ اکتبر با ۱۰۰ بازه هنوز پشتیبانی نمی‌شود و حذف شده است.",
            "برای صدک ۹۵ زیان، فقط حدود ۲ تا ۳ سناریو از ۵۰ مسیر در دم قرار دارد.",
            "تست قیمت به‌تنهایی صحت دم زیان یک باتری با برنامهٔ مشخص را ثابت نمی‌کند.",
        ],
    }


def main():
    """از تاریخچهٔ ذخیره‌شده، سناریوهای اکتبر را می‌سازد و گزارش ریسک می‌دهد."""

    import argparse
    parser = argparse.ArgumentParser(description="آزمون دم‌های قیمت و نوسان روزانه")
    parser.add_argument("--input", required=True, help="فایل CSV تاریخچهٔ DE-LU")
    parser.add_argument("--output", default="output/risk_report.json")
    args = parser.parse_args()

    table = prepare(args.input)
    train = table[table["day"] < date(2026, 10, 1)]
    october = table[(table["day"] >= date(2026, 10, 1)) &
                    (table["day"] <= date(2026, 10, 31))]

    # تمام پارامترها از داده‌های قبل از آزمون اکتبر تعیین می‌شوند.
    residuals, gap, _, _, past_scores = past_residual_days(train)
    _, _, _, _, _, final_gap, factor = september_diagnostic(
        train, residuals, gap, past_scores)
    models = fit_quantiles(train)

    # آستانهٔ افراطی ۵ و ۹۵ درصد را فقط از قیمت‌های پیش از اکتبر می‌گیریم.
    prices_before_october = train["price_eur_mwh"].to_numpy()
    p05, p95 = np.quantile(prices_before_october, [0.05, 0.95])

    actual_days, scenario_days = [], []
    for day, rows in october.groupby("day", sort=True):
        # روز تغییر ساعت پاییزی ۱۰۰ بازه دارد؛ فعلاً بی‌صدا جایگزین نمی‌کنیم.
        if len(rows) != 96:
            print(f"روز {day} با {len(rows)} بازه در آزمون سناریو لحاظ نشد.")
            continue

        # پیش‌بینی و نمونه‌گیری بدون استفاده از قیمت واقعی همین روز.
        low, middle, high = predict(models, rows)
        paths = sample_scenarios(
            middle, low - final_gap, high + final_gap,
            residuals, seed=42 + len(actual_days))
        paths = middle + factor * (paths - middle)
        scenario_days.append(paths)

        # این خط فقط در پایان پیش‌بینی، قیمت واقعی را برای ارزیابی می‌خواند.
        actual_days.append(rows["price_eur_mwh"].to_numpy())

    report = risk_metrics(np.array(actual_days), np.array(scenario_days), p05, p95)
    report["training_last_day"] = "2026-09-30"
    report["evaluation_month"] = "2026-10"

    # گزارش قابل بازتولید برای پژوهش ذخیره می‌شود.
    filename = Path(args.output)
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"روزها/بازه‌ها: {report['days_evaluated']} / {report['intervals_evaluated']}")
    print(f"پوشش سناریوهای ۱۰–۹۰٪: {report['scenario_p10_p90_coverage']:.3f}")
    print(f"خروج از پایین/بالای بازه: {report['below_scenario_p10_rate']:.3f} / "
          f"{report['above_scenario_p90_rate']:.3f}")
    print(f"دامنهٔ روزانه واقعی/سناریویی (میانگین EUR/MWh): "
          f"{report['mean_actual_daily_range_eur_mwh']:.1f} / "
          f"{report['mean_scenario_daily_range_eur_mwh']:.1f}")
    print("قیمت‌های منفی واقعی: "
          f"{report['extreme_interval_rates']['negative_actual_count']} بازه از "
          f"{report['intervals_evaluated']} بازه")
    print("سهم قیمت منفی واقعی/سناریویی: "
          f"{100*report['extreme_interval_rates']['negative_actual']:.3f}% / "
          f"{100*report['extreme_interval_rates']['negative_scenarios']:.2f}%")
    print(f"گزارش ذخیره شد: {filename}")
    print("هشدار: این بررسی قیمت است؛ کالیبراسیون سودِ منفی یا CVaR باتری نیست.")


if __name__ == "__main__":
    main()
