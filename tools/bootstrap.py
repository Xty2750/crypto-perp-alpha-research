"""Stationary block bootstrap for trade and daily return series.

Point estimates decide nothing. Several candidates in this program had attractive
out-of-sample per-trade returns - +0.203% (t = 1.25), +0.596% (t = 1.51), +0.129%
(t = 0.86) - and every one was rejected here, because the confidence interval contained
zero.

Blocks, not i.i.d. resampling: trades cluster in time (a market-wide panic fires many
positions in the same hour), so an i.i.d. bootstrap treats correlated observations as
independent and reports an interval that is too narrow.

Politis & Romano (1994) stationary bootstrap: geometric block lengths with mean
`mean_block`, which keeps the resampled series stationary instead of imposing a fixed
block grid.

Dependencies: numpy, pandas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BootstrapCI:
    statistic: str
    point: float
    lower: float
    upper: float
    level: float
    n_obs: int
    n_boot: int
    mean_block: float

    @property
    def excludes_zero(self) -> bool:
        return (self.lower > 0) or (self.upper < 0)

    def __str__(self) -> str:
        verdict = "excludes zero" if self.excludes_zero else "CONTAINS ZERO"
        return (f"{self.statistic}: {self.point:+.4f}  "
                f"{self.level:.0%} CI [{self.lower:+.4f}, {self.upper:+.4f}]  "
                f"({verdict}; n={self.n_obs}, B={self.n_boot}, mean block={self.mean_block:.1f})")


def _stationary_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Index sequence of length n built from geometric-length wrapped blocks."""
    p = 1.0 / max(mean_block, 1.0)
    idx = np.empty(n, dtype=np.int64)
    i = 0
    while i < n:
        start = rng.integers(0, n)
        length = min(rng.geometric(p), n - i)
        idx[i:i + length] = (start + np.arange(length)) % n
        i += length
    return idx


def block_bootstrap(
    returns: pd.Series | np.ndarray,
    statistic: str = "mean",
    *,
    n_boot: int = 10_000,
    mean_block: float | None = None,
    level: float = 0.95,
    periods_per_year: float = 252.0,
    seed: int | None = 0,
) -> BootstrapCI:
    """Percentile confidence interval for `mean` or `sharpe` of a return series.

    `mean_block` defaults to n**(1/3), the usual rule of thumb. Raise it when the series is
    strongly autocorrelated or when observations arrive in bursts.
    """
    r = np.asarray(pd.Series(returns).dropna(), dtype=float)
    n = len(r)
    if n < 8:
        raise ValueError(f"need at least 8 observations, got {n}")
    if mean_block is None:
        mean_block = max(2.0, float(np.ceil(n ** (1 / 3))))

    def stat(x: np.ndarray) -> float:
        if statistic == "mean":
            return float(x.mean())
        if statistic == "sharpe":
            sd = x.std(ddof=1)
            return float("nan") if sd == 0 else float(x.mean() / sd * np.sqrt(periods_per_year))
        raise ValueError(f"unknown statistic {statistic!r}")

    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        draws[b] = stat(r[_stationary_indices(n, mean_block, rng)])

    draws = draws[np.isfinite(draws)]
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(draws, [a, 1.0 - a])
    return BootstrapCI(statistic, stat(r), float(lo), float(hi),
                       level, n, len(draws), mean_block)


def drop_best_trades(returns: pd.Series | np.ndarray, k: int = 3) -> float:
    """Mean return after removing the k largest winners.

    A cheap tail-dependence probe. One candidate in this program showed +8.08bp per trade
    and Sharpe 1.25 on its lock-box set; removing the best three trades left +0.35bp. That
    is not an edge, it is three lucky trades, and the point estimate alone never says so.
    """
    r = np.sort(np.asarray(pd.Series(returns).dropna(), dtype=float))
    return float(r[:-k].mean()) if len(r) > k else float("nan")
