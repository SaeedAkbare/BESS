# Repository audit and walk-forward development plan

Audit date: 2026-11-07. Scope: `feature/battery-optimization-foundation`.

## Verified inventory

The branch contains 17 Python files (including tests), 9 GitHub Actions workflows,
two Markdown research notes, and `requirements.txt`. There is no root README
in the inspected tree.

## Reproducibility and scientific limitations

1. `scenarios.py` is hard-coded to 2026 folds and September-to-October
   calibration. Do not describe October results as independent external
   validation after using them for development.
2. `battery_risk_sensitivity.py` is hard-coded to October 2026. It must be
   generalized before any multi-month walk-forward experiment.
3. `battery_chronological_holdout.py` selects the risk weight using the first
   half of October and evaluates on the second half. This is a single split,
   not a multi-month test.
4. The 100-interval October 25 daylight-saving day is skipped. Future code
   must either support variable-length local delivery days or explicitly
   report exclusions for each month.
5. Battery size, power, efficiencies, and daily cyclic SOC are illustrative;
   they are not verified plant operating specifications.
6. The 95% empirical CVaR of 15 holdout days is highly uncertain.
7. `requirements.txt` previously omitted solver dependencies used by the
   battery optimization scripts. The CI workflow installs them separately.
8. Legacy Persian comments/docstrings remain in `scenarios.py` and other
   older files. Translation must preserve logic and scientific qualifications.

## Walk-forward acceptance criteria

- Parameterize training cutoff, calibration window, evaluation month, and
  scenario random seeds; prohibit training or calibration on evaluation dates.
- Keep scenario-generation parameters fixed before observing evaluation-month
  outcomes. Separate model selection from final assessment.
- For each month, produce dated per-day realized profits and scenario
  diagnostics using identical eligible days for all strategies.
- Select risk weight using earlier months only; never select it using the
  evaluation month's realized profits.
- Include baseline, selected stochastic policy, and perfect-foresight oracle.
- Record skipped days, solver failures, parameter provenance, and model version.
- Add synthetic tests for temporal leakage, insufficient historical data,
  boundary dates, and daylight-saving transitions.
- Report month-level metrics and uncertainty; retain October 2026 as a
  development/reference experiment rather than claiming it is untouched.

This file is a development audit, not evidence that walk-forward evaluation
has already been implemented or executed.
