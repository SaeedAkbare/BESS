# BESS — approved DE–LU day-ahead research design (v0.2)

**Status (2026-11-06): project design approved; this file contains specifications, NOT executed results.** No verified API download, trained forecast, optimizer run, or measured performance is claimed.

## Goal and three strategies

Compare the **same battery** over historical Germany–Luxembourg (DE-LU) day-ahead delivery days. All live strategies act on information available **before the day-ahead auction**, not on future cleared prices.

1. **Deterministic (forecast-based)**: optimize one common 15-minute charge/discharge schedule using one point forecast. For comparability to the risk-neutral stochastic objective, use the **arithmetic expected price from the scenario ensemble** (not the median, which in general differs from the expectation).
2. **Stochastic (risk-aware)**: optimize one common, nonanticipative schedule against all weighted price paths; objective **maximize expected profit minus λ × CVaR of loss** at a chosen tail level (e.g. 95%, tunable). The schedule is the *same* in every price scenario because the auction price is not yet known when the decision is made. Scenarios affect the profit distribution and risk term, not which schedule gets submitted after the fact. At λ=0 and with linear price revenue, this collapses mathematically to strategy 1 with ensemble-mean prices.
3. **Perfect-foresight oracle**: retrospectively optimize a feasible schedule using **actual** cleared day-ahead prices. This is an optimistic reference/upper bound for the simplified scheduling model, **not a deployable pre-auction trading strategy**. It is not legitimate to claim an oracle schedule could have been bid at those already-revealed prices.

Real-world auction bids may be price-contingent and have more complex acceptance, clearing, and product constraints. v0.2 uses an explicitly simplified **price-taker, fixed pre-auction schedule** for an apples-to-apples educational benchmark. It does not simulate the auction clearing mechanism, execution risks, intraday corrections, or imbalance settlements.

## Actual market data and timestamps

- Bidding zone: **DE–LU**; settlement price **EUR/MWh**.
- Day-ahead resolution from 2025-10-01 is **15-minute MTU**: normally 96 slots/day. Treat timestamps as timezone-aware `Europe/Berlin`; DST changeover days can contain 92 or 100 slots (October 25, 2026 has 100). Define the optimizer horizon dynamically instead of assuming 96 always.
- Data candidate: Fraunhofer ISE Energy-Charts API `https://api.energy-charts.info/v2/price?bzn=DE-LU&start=2026-10-01&end=2026-10-31`; endpoint, timestamps, schema and actual historical completeness **must be verified by an actual fetch** before implementation is claimed. Retain source and licensing attribution.
- For initial backtest: hold out **October 2026**. Fit parameters only using past data, e.g. Oct 2025–Sep 2026, then test day-by-day on Oct 2026 in a reproducible out-of-sample procedure. The tested day must never appear in fitted features, residuals, or calibration data.
- Use only ex-ante-known covariates at forecast issue time: calendar, eligible lagged day-ahead prices, and if accessible *archived forecasts* for wind, solar and load. **Do not leak actual next-day demand or generation.**

## Scenario generator — primary approach: quantile regression + trajectory residual bootstrap

Target: ~**50 complete day-ahead price-path scenarios** per delivery day, with initially equal probabilities (2% each) and optionally a time-valid weighting scheme.

1. **Data engineering** using `pandas` and `numpy`: align prices on timezone-aware 15-minute delivery timestamps, and construct features available before the auction. Handle DST and missing slots explicitly.
2. **Chronological training/validation**: fit a consistent `scikit-learn` pipeline only on prior days. Use rolling-origin or temporally separated validation; fit preprocessing/scaling on each training fold only.
3. **Quantile regression**: use `sklearn.ensemble.HistGradientBoostingRegressor(loss="quantile", quantile=q)` for q = 0.10, 0.50, 0.90, with a small, transparently tuned hyperparameter grid. Check quantile crossing and recalibrate on prior held-out dates.
4. **Honest daily residuals**: obtain historically *out-of-sample* predictions, then compute complete daily residual vectors `r[d,t] = actual_price[d,t] - predicted_median[d,t]`. Never build residual samples from in-sample fitted residuals.
5. **Scale by conditional uncertainty**: if used, scale positive residuals by historical upper predicted spread (`q90-q50`) and negative residuals by lower spread (`q50-q10`); use minimum positive denominators and safe handling for quantile crossing. Reapply target-day conditional spread on reconstruction. This is an approximation requiring empirical calibration.
6. **Whole-day bootstrap**: sample 50 past *daily residual vectors* (optionally conditioned on similar features/market regime) **as blocks**, not slot-by-slot independently. Apply the target day median and spreads to each vector. A whole-day block better preserves intraday residual autocorrelation, spikes and negative-price sequences. It does **not** by itself guarantee correct scenario dependence or calibration.
7. **DST**: never add 96-length residuals to 100-length price paths. Use a defined DST-aware matching/alignment scheme or analyze DST dates separately and label exclusions.
8. **Scenario output**: matrix `prices[scenario, interval]` and nonnegative weights `probabilities[scenario]` summing to one; store forecast issue time, data cutoff, random seed, and source version.

Keep K-nearest-neighbour historical analogue days as an **optional later forecasting benchmark**, not as a component of the accepted main pipeline. Independent Gaussian noise at every quarter-hour is a poor benchmark because it destroys the path dependence.

## Single battery specification used in all three runs

Inputs, to be confirmed: `power_mw`, `energy_mwh`, charge and discharge efficiencies, minimum/maximum SOC, initial SOC, terminal SOC requirement, transaction costs and degradation €/MWh, and optional cycle limits.

For each 15-minute slot with duration `Δt=0.25 h` (same rule on DST days), battery energy balance:

`SOC[t+1] = SOC[t] + efficiency_charge × charge_mw[t] × Δt - discharge_mw[t] × Δt / efficiency_discharge`.

Constrain `0 ≤ charge_mw,discharge_mw ≤ power_mw`, SOC bounds, and **prevent simultaneous charge and discharge** (important especially with negative prices; use binary exclusivity or a clearly justified equivalent formulation). Include appropriate initial/terminal SOC assumptions so schedules compare fairly.

Scenario profit in EUR:

`Π[s] = Σ_t { price[s,t] × (discharge_mw[t] - charge_mw[t]) × Δt - fees_and_wear[t] }`.

Deterministic solves using `mean_s price[s,t]`; stochastic uses `max E[Π] - λ × CVaR_α(-Π)` where `CVaR_α` is the mean of sufficiently bad losses (with the correct loss sign and a linear epigraph formulation). Realized profit after the fact uses the **actual** price path while keeping the pre-auction schedule fixed.

The exact choice of `λ`, tail level, and optimizer should be published before comparing results. Use a tested linear/MILP solver through a suitable Python package (e.g. SciPy HiGHS optimization), not scikit-learn to solve energy dispatch.

## Evaluation

- Day-by-day walk-forward / held-out comparison of **realized EUR profit**, risk (bad-day tail losses, CVaR), charge/discharge and SOC trajectories, throughput, and total degradation.
- Quantile forecast calibration (pinball loss and actual coverage), and scenario-path diagnostics: spikes, negative prices, intraday day spread, residual autocorrelation and daily dynamics.
- Plot distributions and daily realized profit with `matplotlib`, manipulate data with `pandas`/`numpy`, train forecasts with `scikit-learn`.
- Do not call the perfect-foresight result actual achievable economic profit. It is an **oracle upper bound for a fixed, simplified dispatch formulation**.
- Do not promise stochastic outperforming deterministic: differences depend on calibration, uncertainty, risk aversion, and realized price paths.

## Proposed small project layout (not yet implemented)

- `data.py`: API fetching / source validation / datetime and DST.
- `scenarios.py`: `scikit-learn` conditional quantile forecast and daily-vector residual bootstrap.
- `battery.py`: common physical BESS model and three objective definitions.
- `compare.py`: chronological out-of-sample experiment, summary metrics, matplotlib plots.
- `requirements.txt`: `numpy`, `pandas`, `matplotlib`, `scikit-learn`, HTTP client, and selected optimizer dependency.
- `README.md`: how to reproduce data, train, run and inspect outputs.

**Next technical dependencies:** Verify public market-price retrieval and choose illustrative BESS specs, risk coefficient, optimizer and archived features before claiming an executable result.

## Sources

1. European Commission (2025-10-01), 15-minute EU day-ahead market time unit: https://energy.ec.europa.eu/news/eu-electricity-trading-day-ahead-markets-becomes-more-dynamic-2025-10-01_en
2. Fraunhofer ISE Energy-Charts API: https://api.energy-charts.info/
3. scikit-learn quantile boosting: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html
4. Hilger et al., *Multivariate scenario generation of day-ahead electricity prices using normalizing flows*, Applied Energy 367 (2024), 123241. Provides a benchmark using informed historical nearest neighbours, not validation for this exact residual-bootstrap combination: https://doi.org/10.1016/j.apenergy.2024.123241
