"""Paired day-level bootstrap uncertainty for walk-forward battery profits.

Bootstrap resamples delivery days as paired observations so both strategies
are evaluated on the same sampled days. Confidence intervals are descriptive
and do not establish independent market-month generalization.
"""
import numpy as np


def paired_profit_bootstrap(daily, *, n_boot=5000, seed=42, confidence=.95):
    """Estimate uncertainty in selected minus risk-neutral total profit.

    The interval applies to the mean daily profit difference. Daily
    observations may be serially dependent; use month-block inference once
    enough evaluation months are available.
    """
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    if n_boot < 1:
        raise ValueError("n_boot must be positive")
    if not daily:
        raise ValueError("At least one evaluation day is required")
    differences = np.asarray(
        [row["selected"] - row["risk_neutral"] for row in daily], dtype=float)
    if not np.isfinite(differences).all():
        raise ValueError("Daily profit differences must be finite")
    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(n_boot)
    for i in range(n_boot):
        bootstrap_means[i] = rng.choice(differences, len(differences),
                                        replace=True).mean()
    lower, upper = np.quantile(
        bootstrap_means, [(1 - confidence) / 2, (1 + confidence) / 2])
    return {
        "method": "paired_iid_day_bootstrap",
        "confidence": confidence,
        "bootstrap_samples": n_boot,
        "seed": seed,
        "days": len(differences),
        "mean_daily_difference_eur": float(differences.mean()),
        "total_difference_eur": float(differences.sum()),
        "mean_daily_difference_ci_eur": [float(lower), float(upper)],
        "probability_positive_mean_bootstrap": float(
            np.mean(bootstrap_means > 0)),
        "limitations": [
            "Day-level iid resampling ignores serial dependence and month effects",
            "Bootstrap probability is not a frequentist p-value",
            "Small numbers of evaluation months cannot establish generalization",
        ],
    }
