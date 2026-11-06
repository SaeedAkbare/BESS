# BESS — approved DE–LU day-ahead research design (v0.3)

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

## Mathematical optimization problem — explicit three-model formulation

**Scope and decision timing.** This first version studies a *price-taking, pre-auction fixed physical schedule* for the Germany–Luxembourg day-ahead market. The quantities chosen before the auction must be identical across all price scenarios. **This is a scheduling benchmark, not yet a simulation of limit orders, auction acceptance, or actual market settlements.** Later we can separately implement price-contingent bids and the associated market mechanism.

### Sets, parameters, and units

- `t ∈ {1,…,T}`: 15-minute delivery intervals in one local delivery day (`Δt = 0.25` h). Normally `T = 96`; DST days use their actual 92/100 slots.
- `s ∈ {1,…,S}`: price scenarios; initial target `S=50`.
- `p[s,t]`: forecast scenario day-ahead price (EUR/MWh). `w[s] ≥ 0`, `Σ_s w[s] = 1` (initially equal weights).
- `p_actual[t]`: actual cleared day-ahead price, used **only after the fact** for evaluation and the oracle.
- `Pmax`: symmetric charge/discharge power rating (MW). Separate charge/discharge limits are easy extensions.
- `Emax`: usable energy capacity (MWh), and `Emin`: lower allowable energy bound (MWh).
- `ηc, ηd ∈ (0,1]`: charging and discharging efficiencies (not round-trip efficiency inserted twice).
- `Einit` and `Efinal`: initial and required final stored energy (MWh). An identical terminal condition is used for all models; a simple default for daily comparison is `Efinal = Einit`.
- `c_c, c_d`: non-price variable operating/degradation costs (EUR/MWh of charging/discharging throughput). For a minimalist experiment these can each be the same illustrative cost or zero; report the assumption.
- `α ∈ (0,1)`: CVaR confidence level; `λ ≥ 0`: dimensionless risk-aversion weight. These are *design parameters* to be chosen and disclosed, **not estimates from market data**.

### Common first-stage decision variables

- `ch[t] ≥ 0`: charging power (MW).
- `dis[t] ≥ 0`: discharging power (MW).
- `E[t]`: stored energy at the beginning of interval `t` (MWh), with `E[T+1]` after the final interval.
- `u[t] ∈ {0,1}`: charging/discharging exclusivity indicator; `u=1` allows charging, `u=0` allows discharging.
- In the risk model only: `ζ ∈ ℝ`, a free loss threshold (VaR auxiliary variable), and `z[s] ≥ 0`, each scenario's excess loss above `ζ`.

**All** `ch[t], dis[t], E[t], u[t]` are **shared across scenarios** (nonanticipativity). The stochastic model must NOT use `ch[s,t]` or `dis[s,t]` selected after observing the day-ahead price.

### Common physical constraints (apply to all three models)

For every `t = 1,…,T`:

```text
0 ≤ ch[t]  ≤ Pmax * u[t]
0 ≤ dis[t] ≤ Pmax * (1-u[t])
u[t] ∈ {0,1}

E[t+1] = E[t] + ηc*ch[t]*Δt - (dis[t]/ηd)*Δt

Emin ≤ E[t] ≤ Emax                    for t=1,…,T+1
E[1]   = Einit
E[T+1] = Efinal
```

The binary `u[t]` prevents simultaneous charge and discharge, including pathological cycles that can arise under negative spot prices. The bounds and energy balance have consistent MW/MWh/hour dimensions. A valid starting example is a 2-hour battery (`Emax/Pmax = 2 h`), but the actual numeric battery specification **has not yet been approved**.

Optional future constraints: cycle/throughput limit, availability windows, ramp constraints, grid import/export limits, battery degradation curve, or reserve capacity. Do **not** present them as implemented yet.

### Revenue and profit under a given price path

For **any** price vector `p[t]`, define

```text
Profit(ch, dis | p)
 = Σ_(t=1)^T Δt * [ p[t]*(dis[t]-ch[t])
                    - c_c*ch[t] - c_d*dis[t] ]       [EUR]
```

Positive `dis-ch` sells energy; negative `dis-ch` purchases energy. With a **negative** price, buying energy can create positive price revenue, but still consumes physical capacity and incurs any throughput cost. `Π[s] = Profit(ch,dis | p[s,:])`.

### Model A — Deterministic (forecast-based MILP)

Let the point forecast equal the **probability-weighted ensemble mean**

`p_mean[t] = Σ_s w[s] p[s,t]`.

Choose the common power schedule and SOC to solve

```text
maximize   Profit(ch,dis | p_mean)
subject to all common physical constraints
```

The same forecast-origin and inputs must be used for the stochastic model. A median forecast is a different point forecast; using it here would confound risk with the forecast choice.

### Model B — Stochastic risk-aware (mean–CVaR MILP)

Minimize *downside losses* by incorporating `CVaR_α(L)` where scenario loss is `L[s] = -Π[s]`; profit is scenario-dependent only through the ex-ante uncertain prices.

Use the exact linear CVaR epigraph:

```text
maximize   Σ_s w[s]*Π[s]
           - λ * ( ζ + [1/(1-α)] * Σ_s w[s]*z[s] )

subject to all common physical constraints
           z[s] ≥ -Π[s] - ζ           for every scenario s
           z[s] ≥ 0                   for every scenario s
           ζ free (can be positive or negative)
```

When `λ=0`, the stochastic objective reduces **exactly** to the deterministic objective with `p_mean`, assuming matching costs and constraints. **Therefore a difference between Models A and B requires risk aversion, valid recourse, or other nonlinear/price-contingent market features.** For the initial comparison we use `λ>0` and no recourse.

With 50 equally weighted scenarios, an `α=0.95` tail contains only about 2–3 scenarios, making CVaR estimates noisy. Prefer a sensitivity analysis including `α=0.90` (about five tail scenarios) and/or more scenarios, with seeds and validation reported. `λ` must be selected before the held-out test or on a **separate** validation interval; never tune it on October outcomes.

### Model C — Perfect-foresight MILP (evaluation oracle only)

After delivery, solve

```text
maximize   Profit(ch,dis | p_actual)
subject to exactly the same common physical constraints
```

This is the **idealized upper bound on realized profit in this fixed-schedule model** for each individual delivery day. It is not an actionable pre-auction strategy; it deliberately sees the actual price that Models A/B cannot know.

### Realized out-of-sample comparison

For each held-out day `D`, calculate the pre-auction schedules `x_A(D)` and `x_B(D)`, then evaluate **both fixed schedules** at the *same realized* `p_actual(D)`. Solve the oracle only afterward.

```text
realized_A[D] = Profit(x_A(D) | p_actual(D))
realized_B[D] = Profit(x_B(D) | p_actual(D))
oracle[D]     = max_x Profit(x | p_actual(D))
regret_A[D]   = oracle[D] - realized_A[D]
regret_B[D]   = oracle[D] - realized_B[D]
```

Report realized total/mean profit, lower-tail outcomes and CVaR across evaluation days, scenario calibration, SOC profiles, number of cycles/throughput, and regret relative to the oracle. The regret is nonnegative **only under exactly identical feasible sets and cost assumptions**, which is why the same constraints and costs are crucial.

**Solver classification:** because `u[t]` is binary and all remaining expressions are linear, all three problems are **mixed-integer linear programs (MILPs)**. `scikit-learn` is used for price forecasts, *not* for the battery optimization. A MILP-capable solver (e.g., SciPy's `scipy.optimize.milp` backed by HiGHS, or a similarly documented alternative) is required in addition to NumPy, Pandas and Matplotlib.

### Pending numerical specification (intentionally not invented)

Before implementing, choose and record `Pmax, Emax, Emin, ηc, ηd, Einit, Efinal, c_c, c_d, α, λ`, and the solver. Until those are confirmed, **no computed dispatch or performance results exist**.


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
