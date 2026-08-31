"""Four-cell regime validation.

A signal that is positive in one market regime and negative in the next is not necessarily
dead - it may be regime-conditional. That is a true statement and also a very convenient
one, so it needs a test that can fail.

    Partition results into {bull, bear} x {in-sample, out-of-sample}.
    Every adequately-populated cell must carry the same sign.

The requirement is two *independent* observations within the same regime: once in-sample,
once out-of-sample. A single favorable regime stretch is one observation, no matter how
large its t-statistic.

Applied to six candidates that a regime story would have revived, this rejected five.

Two implementation details that are not optional:

* Rolling regime indicators are undefined during warm-up. `close >= NaN` evaluates to False,
  which silently labels every early observation "bear" - and in this program that alone
  manufactured a wrong conclusion. Undefined periods are dropped, never classified.
* Cells below `min_obs` are reported as UNDERPOWERED, not as passes. Several candidates had
  bear cells with N = 2.

Dependencies: numpy, pandas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Cell:
    regime: str
    sample: str
    n: int
    mean: float
    t: float

    @property
    def sign(self) -> int:
        if not np.isfinite(self.mean) or self.mean == 0:
            return 0
        return 1 if self.mean > 0 else -1


@dataclass
class FourCellResult:
    cells: list[Cell]
    min_obs: int
    min_abs_t: float
    verdict: str
    reason: str

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

    def status_of(self, c: Cell) -> str:
        if c.n == 0:
            return "empty"
        if c.n < self.min_obs:
            return "underpowered"
        if not np.isfinite(c.t) or abs(c.t) < self.min_abs_t:
            return "inconclusive"
        return "ok"

    def table(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "regime": c.regime, "sample": c.sample, "n": c.n,
            "mean": c.mean, "t": c.t, "status": self.status_of(c),
        } for c in self.cells])

    def __str__(self) -> str:
        df = self.table()
        body = df.to_string(index=False, float_format=lambda v: f"{v:+.4f}")
        return f"{body}\n\nverdict: {self.verdict} - {self.reason}"


def regime_from_ma(
    price: pd.Series,
    window: int = 200,
    *,
    require_full_window: bool = True,
) -> pd.Series:
    """Label each timestamp 'bull' / 'bear' by price vs its moving average.

    Returns NaN - not 'bear' - while the average is undefined. `require_full_window=True`
    keeps `min_periods` equal to `window` so the warm-up region is explicitly NaN rather
    than computed from a partial window.
    """
    ma = price.rolling(window, min_periods=window if require_full_window else 1).mean()
    out = pd.Series(np.where(price >= ma, "bull", "bear"), index=price.index, dtype=object)
    out[ma.isna() | price.isna()] = np.nan
    return out


def four_cell_test(
    returns: pd.Series,
    regime: pd.Series,
    cut: pd.Timestamp | str,
    *,
    min_obs: int = 10,
    min_abs_t: float = 1.0,
) -> FourCellResult:
    """Run the test on a per-trade or per-period return series.

    Parameters
    ----------
    returns : returns indexed by time (per trade or per period).
    regime : 'bull' / 'bear' / NaN, aligned to `returns`. NaN observations are dropped.
    cut : the frozen in/out-of-sample boundary.
    min_obs : cells below this are underpowered and cannot support a claim.
    min_abs_t : a cell whose |t| falls below this is *inconclusive* and cannot confirm a
        regime. Without this guard the test is purely sign-based, and two cells of pure
        noise agree in sign half the time - so a dead signal passes at a 50% rate. This is
        a weak guard, not a significance test; the bootstrap is still the final arbiter.
    """
    cut = pd.Timestamp(cut)
    df = pd.DataFrame({"r": returns}).join(regime.rename("regime"), how="left")
    dropped = int(df["regime"].isna().sum())
    df = df.dropna(subset=["regime", "r"])
    df["sample"] = np.where(df.index < cut, "in", "out")

    cells: list[Cell] = []
    for reg in ("bull", "bear"):
        for smp in ("in", "out"):
            r = df.loc[(df["regime"] == reg) & (df["sample"] == smp), "r"].to_numpy(float)
            if len(r) >= 2:
                sd = r.std(ddof=1)
                t = float(r.mean() / (sd / np.sqrt(len(r)))) if sd > 0 else np.nan
                cells.append(Cell(reg, smp, len(r), float(r.mean()), t))
            else:
                cells.append(Cell(reg, smp, len(r),
                                  float(r.mean()) if len(r) else np.nan, np.nan))

    result = FourCellResult(cells, min_obs, min_abs_t, verdict="", reason="")

    usable: dict[str, list[Cell]] = {}
    for c in cells:
        if result.status_of(c) == "ok":
            usable.setdefault(c.regime, []).append(c)

    confirmed = [reg for reg, cs in usable.items()
                 if len(cs) == 2 and cs[0].sign == cs[1].sign != 0]
    reversed_ = [reg for reg, cs in usable.items()
                 if len(cs) == 2 and cs[0].sign != cs[1].sign]
    single = [reg for reg, cs in usable.items() if len(cs) == 1]

    if confirmed:
        verdict = "PASS"
        reason = f"regime(s) {confirmed} confirmed in both samples"
    elif reversed_:
        verdict = "FAIL"
        reason = (f"sign reversal within regime(s) {reversed_} - the effect does not hold "
                  "across both samples of the same regime")
    elif single:
        verdict = "FAIL"
        reason = (f"regime(s) {single} observed only once - a single regime observation "
                  "is not evidence")
    else:
        verdict = "FAIL"
        reason = (f"no cell is both adequately populated (n>={min_obs}) and distinguishable "
                  f"from zero (|t|>={min_abs_t})")

    if dropped:
        reason += f" ({dropped} observations dropped: regime undefined)"

    result.verdict, result.reason = verdict, reason
    return result
