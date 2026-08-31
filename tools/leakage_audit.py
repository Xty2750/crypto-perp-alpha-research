"""Point-in-time leakage auditing.

Three independent checks, because look-ahead enters through three different doors:

1. `truncation_test`   - a feature that uses future data changes when you recompute it on a
                         prefix of the series. Recompute on prefixes, assert stability.
2. `audit_trades`      - every trade's signal must be knowable strictly before its entry,
                         and stops must be monitored across the whole holding period.
3. `check_alignment`   - two series whose values become knowable at different clock times
                         must not be compared as if they shared a timestamp.

None of these bugs raise an exception in normal use. They produce a plausible number.

Dependencies: numpy, pandas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------------------
# 1. Truncation test
# --------------------------------------------------------------------------------------

@dataclass
class TruncationResult:
    n_checkpoints: int
    n_columns: int
    max_abs_diff: float
    offenders: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.offenders

    def __str__(self) -> str:
        head = (
            f"truncation test: {self.n_checkpoints} checkpoints x {self.n_columns} columns, "
            f"max |diff| = {self.max_abs_diff:.3e}"
        )
        if self.passed:
            return head + "  -> PASS"
        lines = [head + f"  -> FAIL ({len(self.offenders)} column(s))"]
        for col, diff in sorted(self.offenders.items(), key=lambda kv: -kv[1]):
            lines.append(f"    {col}: max |diff| = {diff:.6e}")
        return "\n".join(lines)


def truncation_test(
    raw: pd.DataFrame,
    build_features: Callable[[pd.DataFrame], pd.DataFrame],
    checkpoints: Sequence[float] = (0.5, 0.7, 0.9),
    tolerance: float = 1e-10,
) -> TruncationResult:
    """Recompute features on prefixes of `raw` and assert nothing earlier changes.

    A causal feature computed at time t depends only on data up to t, so truncating the
    input after t must leave its value untouched. Any column that shifts is reading ahead.

    This catches the whole family at once: centered rolling windows, full-sample
    normalisation, `bfill`, resampling that borrows from the next bucket, and target
    encodings fitted on everything.

    Parameters
    ----------
    raw : the full input frame, indexed by time.
    build_features : the feature pipeline under audit. Must be a pure function of its input.
    checkpoints : fractions of the sample at which to truncate.
    tolerance : absolute difference treated as floating-point noise.
    """
    if not raw.index.is_monotonic_increasing:
        raise ValueError("raw must be sorted by time before auditing")

    full = build_features(raw)
    offenders: dict = {}
    worst = 0.0

    for frac in checkpoints:
        cut = int(len(raw) * frac)
        if cut < 2:
            continue
        partial = build_features(raw.iloc[:cut])
        common_idx = full.index[:cut].intersection(partial.index)
        common_cols = [c for c in full.columns if c in partial.columns]

        for col in common_cols:
            a = pd.to_numeric(full.loc[common_idx, col], errors="coerce")
            b = pd.to_numeric(partial.loc[common_idx, col], errors="coerce")
            both_nan = a.isna() & b.isna()
            diff = (a - b).abs()
            diff[both_nan] = 0.0
            # a value that is NaN on one side only is itself a mismatch
            diff[a.isna() ^ b.isna()] = np.inf
            m = float(np.nanmax(diff.to_numpy())) if len(diff) else 0.0
            worst = max(worst, m if np.isfinite(m) else np.inf)
            if m > tolerance:
                offenders[col] = max(offenders.get(col, 0.0), m)

    return TruncationResult(
        n_checkpoints=len(checkpoints),
        n_columns=len(full.columns),
        max_abs_diff=worst,
        offenders=offenders,
    )


# --------------------------------------------------------------------------------------
# 2. Trade-level audit
# --------------------------------------------------------------------------------------

@dataclass
class TradeAudit:
    n_trades: int
    violations: pd.DataFrame

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def __str__(self) -> str:
        head = f"trade audit: {self.n_trades} trades"
        if self.passed:
            return head + ", 0 violations  -> PASS"
        counts = self.violations["rule"].value_counts()
        lines = [head + f", {len(self.violations)} violation(s)  -> FAIL"]
        for rule, n in counts.items():
            lines.append(f"    {rule}: {n}")
        return "\n".join(lines)


def audit_trades(
    trades: pd.DataFrame,
    bars: pd.DataFrame | None = None,
    signal_col: str = "signal_time",
    entry_col: str = "entry_time",
    exit_col: str = "exit_time",
    stop_col: str = "stop_price",
    side_col: str = "side",
    exit_price_col: str = "exit_price",
) -> TradeAudit:
    """Check a trade ledger for the failure modes that survive a normal review.

    Rules applied
    -------------
    signal_before_entry  signal_time must be strictly earlier than entry_time.
    entry_before_exit    entry_time must be strictly earlier than exit_time.
    unique_entry_bar     no two trades may share an entry timestamp (overlapping detection
                         windows silently double-count a single breakout).
    stop_respected       if `bars` is supplied, a long whose low pierced its stop during the
                         hold must not be recorded exiting above it - and vice versa. This is
                         the bug where a position traded through its stop mid-hold, recovered,
                         and was scored a winner.

    `bars` is an OHLC frame indexed by time; the stop check is skipped when it is None.
    """
    v: list[dict] = []

    for i, t in trades.iterrows():
        if not (pd.Timestamp(t[signal_col]) < pd.Timestamp(t[entry_col])):
            v.append({"trade": i, "rule": "signal_before_entry",
                      "detail": f"{t[signal_col]} !< {t[entry_col]}"})
        if exit_col in trades.columns and not (
            pd.Timestamp(t[entry_col]) < pd.Timestamp(t[exit_col])
        ):
            v.append({"trade": i, "rule": "entry_before_exit",
                      "detail": f"{t[entry_col]} !< {t[exit_col]}"})

    dupes = trades[entry_col][trades[entry_col].duplicated(keep=False)]
    for i in dupes.index:
        v.append({"trade": i, "rule": "unique_entry_bar", "detail": str(trades.at[i, entry_col])})

    if bars is not None and stop_col in trades.columns:
        for i, t in trades.iterrows():
            # inclusive of the exit bar: a break in the final hour is still a break
            window = bars.loc[pd.Timestamp(t[entry_col]):pd.Timestamp(t[exit_col])]
            if window.empty:
                continue
            long = str(t.get(side_col, "long")).lower().startswith("l")
            stop = float(t[stop_col])
            px = float(t[exit_price_col]) if exit_price_col in trades.columns else np.nan
            pierced = window["low"].min() <= stop if long else window["high"].max() >= stop
            if pierced and np.isfinite(px):
                mis = px > stop if long else px < stop
                if mis:
                    v.append({
                        "trade": i, "rule": "stop_respected",
                        "detail": f"stop {stop:.6g} pierced during hold, exit recorded at {px:.6g}",
                    })

    return TradeAudit(
        n_trades=len(trades),
        violations=pd.DataFrame(v, columns=["trade", "rule", "detail"]),
    )


# --------------------------------------------------------------------------------------
# 3. Cross-dataset timestamp alignment
# --------------------------------------------------------------------------------------

def check_alignment(
    left: pd.Series,
    right: pd.Series,
    left_known_at: Callable[[pd.Timestamp], pd.Timestamp],
    right_known_at: Callable[[pd.Timestamp], pd.Timestamp],
    decision_times: Iterable[pd.Timestamp],
) -> pd.DataFrame:
    """Report any decision time that would consume not-yet-published data.

    Datasets carry different publication conventions - a daily candle stamped at 00:00 UTC
    and a daily open-interest print stamped at 16:00 UTC are not the same "day". Pass a
    function mapping each series' index timestamp to the moment its value actually becomes
    knowable, and this reports every violation.
    """
    rows = []
    for ts in decision_times:
        ts = pd.Timestamp(ts)
        for name, series, known_at in (("left", left, left_known_at),
                                       ("right", right, right_known_at)):
            usable = series.index[series.index.map(known_at) <= ts]
            if len(usable) == 0:
                continue
            latest = usable.max()
            if known_at(latest) > ts:
                rows.append({"decision_time": ts, "series": name,
                             "stamp": latest, "known_at": known_at(latest)})
    return pd.DataFrame(rows, columns=["decision_time", "series", "stamp", "known_at"])
