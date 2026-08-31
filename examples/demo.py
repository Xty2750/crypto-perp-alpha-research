"""Runs every tool on synthetic data. `python examples/demo.py`

Each section is built so the tool has something real to find - a planted leak, a planted
underpowered cell - because a validation tool that only ever prints PASS on a toy example
tells you nothing about whether it works.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.bootstrap import block_bootstrap, drop_best_trades          # noqa: E402
from tools.four_cell import four_cell_test, regime_from_ma            # noqa: E402
from tools.leakage_audit import audit_trades, truncation_test         # noqa: E402
from tools.walkforward import (evaluate_folds, fold_summary,          # noqa: E402
                               walk_forward_splits)

rng = np.random.default_rng(7)
N = 1200
idx = pd.date_range("2024-01-01", periods=N, freq="D")
price = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, N))), index=idx, name="close")
raw = pd.DataFrame({"close": price,
                    "high": price * (1 + rng.uniform(0, 0.01, N)),
                    "low": price * (1 - rng.uniform(0, 0.01, N))})


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------- 1. truncation test
rule("1. Truncation test - one causal feature, one that peeks")


def features_clean(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"mom_20": df["close"].pct_change(20)}, index=df.index)


def features_leaky(df: pd.DataFrame) -> pd.DataFrame:
    out = features_clean(df)
    # z-scored on the whole sample: every value depends on data that arrives later
    out["z_full_sample"] = (df["close"] - df["close"].mean()) / df["close"].std()
    # centered window: literally reads the future
    out["centered_ma"] = df["close"].rolling(21, center=True, min_periods=1).mean()
    return out


print(truncation_test(raw, features_clean))
print()
print(truncation_test(raw, features_leaky))

# ---------------------------------------------------------------- 2. trade audit
rule("2. Trade audit - a clean ledger, then three planted defects")

entries = idx[100:160:6]
clean = pd.DataFrame({
    "signal_time": entries - pd.Timedelta("1D"),
    "entry_time": entries,
    "exit_time": entries + pd.Timedelta("2D"),
    "side": "long",
    "stop_price": raw.loc[entries, "low"].to_numpy() * 0.90,
    "exit_price": raw.loc[entries, "close"].to_numpy() * 1.01,
}).reset_index(drop=True)
print(audit_trades(clean, bars=raw))

dirty = clean.copy()
dirty.loc[0, "signal_time"] = dirty.loc[0, "entry_time"]          # signal not before entry
dirty.loc[1, "entry_time"] = dirty.loc[2, "entry_time"]           # duplicate entry bar
dirty.loc[3, "stop_price"] = raw.loc[dirty.loc[3, "entry_time"], "close"] * 1.05
print()
print(audit_trades(dirty, bars=raw))

# ---------------------------------------------------------------- 3. walk-forward
rule("3. Walk-forward - folds, purge, embargo")

data = pd.DataFrame({"mom": price.pct_change(20),
                     "fwd_return": price.pct_change(5).shift(-5)}, index=idx).dropna()
folds = list(walk_forward_splits(data.index, "365D", "90D",
                                 label_horizon="5D", embargo="5D"))
for f in folds[:3]:
    print(f)
print(f"... {len(folds)} folds total")


def fit_predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    # sign chosen on training data only - this is the whole discipline in one line
    sign = np.sign(train["mom"].corr(train["fwd_return"]) or 0.0)
    return pd.Series(np.sign(test["mom"]) * sign, index=test.index)


res = evaluate_folds(data, folds, fit_predict)
print()
print(res.to_string(index=False, float_format=lambda v: f"{v:+.4f}"))
print("\n" + fold_summary(res))

# ---------------------------------------------------------------- 4. bootstrap
rule("4. Block bootstrap - a real edge, then noise, then tail dependence")

real = pd.Series(rng.normal(0.004, 0.02, 300))
noise = pd.Series(rng.normal(0.0004, 0.02, 120))
print(block_bootstrap(real, "mean"))
print(block_bootstrap(noise, "mean"))

tail = pd.Series(np.r_[rng.normal(0.0002, 0.01, 297), [0.25, 0.22, 0.19]])
print(f"\ntail check: mean {tail.mean():+.4f} -> "
      f"{drop_best_trades(tail, 3):+.4f} after dropping the best 3 trades")
print(block_bootstrap(tail, "mean"))

# ---------------------------------------------------------------- 5. four-cell
rule("5. Four-cell regime test")

regime = regime_from_ma(price, window=200)
print(f"regime labels: {regime.notna().sum()} defined, "
      f"{regime.isna().sum()} undefined (dropped, not labelled 'bear')")

cut = idx[int(N * 0.75)]
trade_idx = idx[220::4]
bull_only = pd.Series(
    np.where(regime.reindex(trade_idx) == "bull",
             rng.normal(0.006, 0.02, len(trade_idx)),
             rng.normal(-0.005, 0.02, len(trade_idx))),
    index=trade_idx)

print("\n-- signal that is genuinely bull-conditional --")
print(four_cell_test(bull_only, regime, cut))

print("\n-- signal that looked bull-conditional but reversed out-of-sample --")
reg_at_trade = regime.reindex(trade_idx)
one_shot = pd.Series(rng.normal(0.0, 0.02, len(trade_idx)), index=trade_idx)
is_bull = (reg_at_trade == "bull").to_numpy()
one_shot[is_bull & (trade_idx < cut)] += 0.014     # strong in-sample bull leg
one_shot[is_bull & (trade_idx >= cut)] -= 0.010    # reverses out-of-sample
print(four_cell_test(one_shot, regime, cut))

print("\nDone.")
