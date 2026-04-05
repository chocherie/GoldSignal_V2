"""
Conservative multiplicity adjustment for grid-searched Sharpe ratios.

When ``N`` independent (or approximately independent) strategies are tested and the
best in-sample Sharpe is reported, a naive OOS Sharpe should be discounted. This
module implements a simple **haircut** (not a full Bailey–López de Prado DSR), suitable
for research dashboards. See ``specs/wf-tuning-research.md``.
"""

from __future__ import annotations

import math


def expected_sharpe_selection_bias(n_trials: int, n_obs: int) -> float:
    """
    Order-magnitude bias from picking the max of ``n_trials`` Sharpe estimates,
    each from ~``n_obs`` i.i.d. normal returns under null (heuristic).

    Returns a value to **subtract** from a raw Sharpe when ``n_trials > 1``.
    """
    if n_trials < 2 or n_obs < 6:
        return 0.0
    # Extreme value scale for max of N standard normals ~ sqrt(2 log N);
    # map to Sharpe-like units via sqrt(observation fraction of year).
    ev = math.sqrt(2.0 * math.log(n_trials))
    return float(ev / math.sqrt(max(n_obs, 1) / 252.0))


def deflated_sharpe_haircut(estimated_sharpe: float, n_trials: int, n_obs: int) -> float:
    """``estimated_sharpe - bias``; NaN if input Sharpe is NaN."""
    if estimated_sharpe != estimated_sharpe:
        return float("nan")
    return float(estimated_sharpe - expected_sharpe_selection_bias(n_trials, n_obs))
