"""Walk-forward evaluation with purge and embargo.

A single train/test split has one free parameter - the cut date - and a well-chosen cut
rescues almost anything. Walk-forward replaces the point estimate with a distribution of
folds, and the useful summary is not the mean but *how many folds carry the same sign*.

Overlapping labels leak across a naive boundary: a trade opened before the split and held
across it shares information with both sides. `purge` removes training samples whose label
horizon crosses into the test window; `embargo` additionally drops test samples immediately
after the boundary.

Dependencies: numpy, pandas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Fold:
    index: int
    train: pd.Index
    test: pd.Index

    def __str__(self) -> str:
        return (f"fold {self.index}: train {len(self.train)} "
                f"[{self.train.min()} .. {self.train.max()}], "
                f"test {len(self.test)} [{self.test.min()} .. {self.test.max()}]")


def _to_offset(x) -> pd.Timedelta:
    return x if isinstance(x, pd.Timedelta) else pd.Timedelta(x)


def walk_forward_splits(
    index: pd.DatetimeIndex,
    train_span: str | pd.Timedelta,
    test_span: str | pd.Timedelta,
    *,
    anchored: bool = False,
    label_horizon: str | pd.Timedelta = "0D",
    embargo: str | pd.Timedelta = "0D",
    min_train: int = 30,
    min_test: int = 5,
) -> Iterator[Fold]:
    """Yield successive walk-forward folds.

    Parameters
    ----------
    anchored : if True the training window always starts at the beginning (expanding);
               otherwise it rolls with a fixed span.
    label_horizon : how far forward a label looks. Training samples within this distance of
               the test start are purged.
    embargo : additional gap dropped from the start of each test window.
    """
    train_span = _to_offset(train_span)
    test_span = _to_offset(test_span)
    horizon = _to_offset(label_horizon)
    emb = _to_offset(embargo)

    index = pd.DatetimeIndex(index).sort_values()
    start, end = index.min(), index.max()

    fold_i, test_start = 0, start + train_span
    while test_start + test_span <= end + pd.Timedelta("1ns"):
        test_end = test_start + test_span
        train_start = start if anchored else test_start - train_span

        train_mask = (index >= train_start) & (index < test_start - horizon)
        test_mask = (index >= test_start + emb) & (index < test_end)

        train_idx, test_idx = index[train_mask], index[test_mask]
        if len(train_idx) >= min_train and len(test_idx) >= min_test:
            yield Fold(fold_i, train_idx, test_idx)
            fold_i += 1
        test_start = test_end


# --------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------

def _sharpe(r: np.ndarray, periods_per_year: float) -> float:
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    return float("nan") if sd == 0 else float(r.mean() / sd * np.sqrt(periods_per_year))


def _tstat(r: np.ndarray) -> float:
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    return float("nan") if sd == 0 else float(r.mean() / (sd / np.sqrt(len(r))))


def evaluate_folds(
    data: pd.DataFrame,
    folds: Iterator[Fold] | list[Fold],
    fit_predict: Callable[[pd.DataFrame, pd.DataFrame], pd.Series],
    return_col: str = "fwd_return",
    periods_per_year: float = 252.0,
) -> pd.DataFrame:
    """Run `fit_predict(train_df, test_df) -> positions` over folds and score each one.

    `fit_predict` must fit everything - scaling, feature selection, hyperparameters - on
    `train_df` alone. Anything fitted on the full frame outside this callback silently
    reintroduces the bias walk-forward exists to remove.

    Returns one row per fold with mean return, t-statistic, Sharpe and hit rate.
    """
    rows = []
    for f in folds:
        train_df, test_df = data.loc[f.train], data.loc[f.test]
        pos = fit_predict(train_df, test_df).reindex(test_df.index).fillna(0.0)
        r = (pos * test_df[return_col]).to_numpy(dtype=float)
        r = r[np.isfinite(r)]
        rows.append({
            "fold": f.index,
            "test_start": f.test.min(),
            "test_end": f.test.max(),
            "n": len(r),
            "mean": float(r.mean()) if len(r) else np.nan,
            "t": _tstat(r),
            "sharpe": _sharpe(r, periods_per_year),
            "hit_rate": float((r > 0).mean()) if len(r) else np.nan,
        })
    return pd.DataFrame(rows)


def fold_summary(fold_results: pd.DataFrame) -> str:
    """The headline that actually matters: how many folds share a sign.

    A strategy with 6/6 positive folds and a modest mean is worth more than one with a
    spectacular mean carried by a single fold.
    """
    n = len(fold_results)
    if n == 0:
        return "no folds"
    pos = int((fold_results["mean"] > 0).sum())
    mean = fold_results["mean"].mean()
    worst = fold_results["mean"].min()
    return (f"{pos}/{n} folds positive | mean of fold means {mean:+.4%} | "
            f"worst fold {worst:+.4%}")
