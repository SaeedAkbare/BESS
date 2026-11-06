# BESS — Day-ahead DE–LU price scenario design (v0.1)

**Status:** Methodological design only. No market prices have been downloaded, no forecast model trained, and no battery-optimization results have been produced yet.

## Decision

Start with **conditional historical analogue days** (k-nearest-neighbours; `sklearn.neighbors.NearestNeighbors`) for *full-day price-path scenarios*. It is a published, reproducible benchmark for the German–Luxembourg day-ahead electricity market, not a claim that all industrial traders use it. Later compare it with a quantile-regression + whole-day residual bootstrap method.

A random independent Gaussian perturbation of each 15-minute price is **not** a good baseline: it destroys within-day dependence and often poorly represents spikes and negative prices.

## Market definition and historical data

- Market: coupled **Germany–Luxembourg (DE-LU)** bidding zone, day-ahead, EUR/MWh.
- Since delivery day 2025-10-01, the official European day-ahead MTU is **15 minutes**. Usually 96 intervals per local day.
- **DST exception**: 2026-10-25 in Europe/Berlin has 100 15-minute intervals. Do not silently discard or merge the repeated hour; use timezone-aware timestamps and verify expected interval counts.
- Public read-only candidate: Fraunhofer ISE Energy-Charts API `GET https://api.energy-charts.info/v2/price?bzn=DE-LU&start=2026-10-01&end=2026-10-31`. API documents EUR/MWh, DE-LU, and licensing/attribution to Energy-Charts.info and SMARD/Bundesnetzagentur. **This exact October query has not been executed successfully from this session**. Do not invent price data.
- To backtest **October 2026**, fit only on information available *before each forecast issue time*. For a simple frozen holdout, use training through 2026-09-30; October 2026 must not also be in training. Prefer at least ~12 months of 15-minute history where available, and monitor shifts in market regime.

## Baseline method: conditional historical analogue days

1. For each target delivery day D, build a feature vector using **only data that would have been known before the day-ahead auction**: calendar/day-of-week/season, previous-day price shape, and ideally published *day-ahead forecasts* of wind, solar generation, and load. Never substitute tomorrow's realised generation/load.
2. Build the same feature vectors for historical days, standardized using a scaler fit on training data only. If using weather/load vectors, scale groups sensibly so a large-magnitude feature does not dominate the Euclidean distance.
3. `NearestNeighbors` finds K historically similar days (initial experiment K=30 or 50; tune in chronological validation). Take their **complete, actual price trajectories** as scenarios. A full-day trajectory retains adjacent-interval dependence, troughs, and peaks.
4. Give scenarios equal weights initially (1/K) or optionally distance-based nonnegative weights normalized to one. Record the choice.
5. Keep a separate *unconditional full-day historical sampling* baseline to quantify whether conditioning really helps. Do not treat K=50 as an optimal number without testing.
6. Dates with 92/100 intervals require explicit DST handling (e.g. a DST-aware horizon / separate analogue pool). Never force invalid 96-length arrays through the battery optimizer.

This directly adapts the *informed historical kNN* baseline described in Hilger et al., **Applied Energy 367 (2024), 123241**. Their paper used scikit-learn `NearestNeighbors` and day-level price paths conditioned on forecasts of wind, solar, load and the previous day's prices. Their study predates the 2025 move to quarter-hourly day-ahead trading; this project adapts rather than copies their hourly implementation.

## Later extension: probabilistic forecast + trajectory-residual bootstrap

After baseline performance is established:

1. Train a point price forecast and a few conditional quantiles (e.g. q10/q50/q90) with `sklearn.ensemble.HistGradientBoostingRegressor(loss="quantile", quantile=q)` (or `GradientBoostingRegressor` if a smaller dataset favours simplicity).
2. Compute **out-of-sample, past-only** historical residual *vectors covering entire days*, ideally stratified by comparable day/market conditions. Sample these vectors as blocks and add them to a conditional point forecast; optionally calibrate scenario spreads to held-out quantiles.
3. Preserve day-path dependence and negative prices. Do not claim a quantile interval by itself gives a coherent joint distribution; evaluate whether the reconstructed paths are calibrated.
4. Consider more complex multivariate normalizing flows only if simple methods fail on real out-of-sample diagnostics; the research shows they can outperform kNN baselines, but they do **not** fit the minimal-scikit-learn-only first version.

## Deterministic versus stochastic BESS comparison

- Same battery physical parameters in both runs: power (MW), energy (MWh), charge/discharge efficiencies, SOC limits/initial-final conditions, cycle or degradation costs, and interval duration `Δt=0.25 h`.
- **Deterministic**: optimize against one point forecast (e.g. calibrated expected price).
- **Stochastic**: optimize against a weighted set of full-day price scenarios **at the correct decision stage**. If the entire power schedule is chosen before prices are known and the objective is *only* expected linear profit, the stochastic formulation collapses to optimizing against expected prices. For a meaningful comparison include an explicit risk objective (e.g. mean–CVaR) **or** correctly defined post-revelation recourse/nonanticipativity. Otherwise differing results can be a modeling artefact.
- Distinguish **pre-auction bidding** (day-ahead prices uncertain) from **post-auction dispatch** (cleared day-ahead prices already observed). Scenario-dependent schedules chosen before prices are revealed without nonanticipativity constitute unrealistic perfect foresight.

## Out-of-sample evaluation

Use walk-forward / rolling-origin splits, recalibrating as time advances, with no look-ahead. Compare:
- Forecast point error (MAE); prediction-interval **empirical coverage** and pinball loss.
- Full trajectory reliability: distribution of negative prices, spikes, day spread, autocorrelation and within-day price differences; energy score / variogram score if practical.
- Operational value: feasible BESS schedule, realized profit under actual historical prices, risk measures such as lower-tail profit/CVaR, and effect of degradation/fees.
- Report uncertainty and avoid declaring an economic winner from one illustrative day.

## Suggested very small Python project later

`data.py`: API fetch, timezone-aware validation and local caching.  
`scenarios.py`: scikit-learn analogue-day scenario generator.  
`battery.py`: deterministic and stochastic/risk-aware optimizer.  
`compare.py`: walk-forward experiment and plots with pandas, numpy, matplotlib.  
`requirements.txt`: numpy, pandas, matplotlib, scikit-learn, requests, plus a deliberately selected optimization library.

**The user has not yet finalized how scikit-learn should be used; do not lock in the later model implementation before that specification.**

## Sources (verified documentation / published research)

1. Hilger, H., et al. (2024), *Multivariate scenario generation of day-ahead electricity prices using normalizing flows*, Applied Energy 367, 123241. Section 3.4 describes the informed historical / kNN scenario baseline: https://doi.org/10.1016/j.apenergy.2024.123241 ; open-access PDF: https://discovery.ucl.ac.uk/10212406/1/1-s2.0-S030626192400624X-main.pdf
2. European Commission (2025-10-01), *EU electricity trading in the day-ahead markets becomes more dynamic*: https://energy.ec.europa.eu/news/eu-electricity-trading-day-ahead-markets-becomes-more-dynamic-2025-10-01_en
3. Fraunhofer ISE, Energy-Charts API catalogue and licence information: https://api.energy-charts.info/ ; /v2/price endpoint.
4. scikit-learn, `NearestNeighbors`: https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.NearestNeighbors.html
5. scikit-learn, `HistGradientBoostingRegressor` quantile-loss documentation: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html
6. DST switch on 2026-10-25: https://www.timeanddate.com/time/change/germany/berlin?year=2026
