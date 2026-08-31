# Crypto Perpetual Futures — Alpha Research Program

A two-year, pre-registered research program testing whether intraday panic and crowding
events in crypto perpetual futures carry edge that survives transaction costs.

**94 experiments. 25 candidates killed with documented cause. One strategy family survived.**

This repository publishes the *method* and the *negative results*, not the parameters.
Specific thresholds, frozen strategy configs and trade logs are deliberately excluded —
see [What is not here](#what-is-not-here).

---

## The question

Crypto perpetuals trade 24/7 with high leverage and a visible funding mechanism. That
combination produces recurring forced-flow events: liquidation cascades, crowded
positioning, panic volume. The question was narrow and testable:

> After realistic costs, does any of that leave a tradable edge — and can it be shown
> to survive a regime change rather than a single favorable market?

Not "can I find a profitable backtest." Two years of one-minute crypto data will produce
profitable backtests on demand. The program was designed around the opposite goal:
making it hard for a false positive to survive.

## The data

| Dataset | Coverage | Scale |
|---|---|---|
| OHLCV, 1m / 5m / 15m | 2024-08-13 → 2026-08-13 | 12 USDT-margined perpetual pairs, 1,051,200 one-minute bars per pair (**12.6M total**) |
| Funding rates | same window | ~2,190 settlements per pair, mostly 8h; some pairs have 1h intervals that must be handled at true timestamps |
| Open interest | 2024-06 → 2026-08 | daily, 800 observations per pair, stamped 16:00 UTC |
| Implied volatility | 2024-06 → 2026-08 | BTC DVOL daily OHLC |

Pairs: BTC, ETH, SOL, XRP, DOGE, ADA, BNB, AVAX, LINK, LTC, APT, ARB.
Integrity: manifest check reports zero gaps and zero duplicate timestamps across the window.

**What the data does not contain**, and therefore what was never assumed: order book depth,
bid/ask spread, trade-level aggressor side, liquidation prints, spot–perp basis, and
cross-exchange flow. Fill quality inside a bar is not observable from OHLCV, so it was
never treated as known.

## The protocol

Seven rules, fixed before the experiments and applied to all of them.

1. **Prove alpha before building an engine.** Grouped returns, rank IC and t-statistics
   first. Only a candidate that passes gets a backtest. This kills most ideas at a fraction
   of the effort.
2. **Model costs honestly.** Default: taker 5bp fee + 2bp slippage per side. Maker 2bp as a
   sensitivity. Double-cost stress as a robustness check. Funding is settled at true
   timestamps, not approximated.
3. **Freeze an out-of-sample cut.** 2025-08-13. In-sample and out-of-sample must *both* be
   positive. No sliding the cut to make a result work.
4. **Cross-sectional robustness.** A result on one pair is not a result. Twelve pairs,
   volatility-normalized and equally weighted.
5. **Parameter plateaus over single-point optima.** A lone peak in a parameter grid is
   an artifact. A plateau is a property.
6. **New mechanisms, not recombinations.** Combining existing components to raise a
   portfolio Sharpe was explicitly not the goal, and is not evidence of anything.
7. **One step, one verification.** Every directional condition must pass the four-cell
   regime test (below) before it is considered real.

## What survived

One strategy family: an **event-conditioned structural entry** — a market-wide flow event
establishes context, a lower-timeframe structure confirms it, the entry carries a
structural stop, fixed-fraction position sizing at 1% of account equity, and a
time-based exit.

Validation actually performed on it:

| Check | Result |
|---|---|
| Walk-forward folds, BTC | 6/6 positive (long and short) |
| Walk-forward folds, ETH | 12/12 positive |
| Merged per-trade return | +1.44% (long) / +1.75% (short) |
| t-statistic | 6.9 / 7.3 |
| Trade-by-trade audit (look-ahead, stop monitoring) | 0 violations |
| Fine parameter grid | 97% of 201 configurations positive in both periods |
| Stress: doubled costs, three alternate cut dates, 0.05% slippage, real funding | all pass |
| Swing-definition sensitivity (5 variants) | numerically near-identical → definition-insensitive |

**Stated limitations, because they are the honest part of the result:** two years is one
market cycle. The out-of-sample period is a single regime. No live-slippage forward
validation has been completed. This is a candidate with strong internal evidence, not a
proven strategy.

## What did not survive — and why that is the point

25 candidates were killed. The [failure library](docs/FAILURE_LIBRARY.md) lists each one
with its hypothesis, its cause of death, and the experiment that killed it: cross-sectional
momentum, opening-range breakouts, funding-settlement microstructure, mean reversion,
liquidation rebounds, calendar effects, aggregate leverage, market breadth as a filter,
absorption patterns, lead-lag, implied-volatility timing, volatility asymmetry, intraday
anchoring, deep-drawdown reversal, and more.

Two kills matter more than the rest, because they were kills of my own apparently-good
results:

- **A strategy showing Sharpe 2.07** turned out to apply its filter on the *next* trading
  day's close, while trading that same day's open-to-close. Once the filter was moved to
  information available at the signal, every threshold in the range turned negative
  in-sample. The switch was killed rather than kept.
- **A strategy showing Sharpe 2.18** was inflated by a calendar bug: dropping NaNs from a
  signal series destroyed the calendar index, so the annualization factor was 3.6× too
  large. True value: 0.87.

Both are documented in [BUGS_AND_LESSONS.md](docs/BUGS_AND_LESSONS.md) with the mechanism
and the fix. The rest of that file is 20 more bugs found the same way.

## The methodological finding

Roughly a third of the killed candidates died the same death: positive in-sample, sign-flipped
out-of-sample. That pattern is usually read as "the effect decayed."

It wasn't. The frozen cut date happened to sit almost exactly on a bull-to-bear turn:
**90% of the in-sample period had BTC above its 200-day moving average; 79% of the
out-of-sample period had it below.** A large class of "decayed" signals were regime-conditional
all along — reversal-type signals worked in the bull half, momentum and short-side signals in
the bear half.

That is a comfortable story, and comfortable stories are how overfitting gets rationalized.
So it was turned into a test that can fail:

> **Four-cell validation.** Split every result into bull/bear × in-sample/out-of-sample.
> Every populated cell must carry the same sign. A single favorable regime observation is
> not evidence — you need two independent observations *within the same regime*.

Applied to the six candidates the regime story would have revived, it rejected five and
validated one. See [REGIME_CONDITIONING.md](docs/REGIME_CONDITIONING.md). The value of a
methodological insight is measured by what it kills, not what it saves.

## Reusable tools

The parts of this program that generalize beyond crypto:

| Module | What it does |
|---|---|
| [`tools/leakage_audit.py`](tools/leakage_audit.py) | Point-in-time auditor. Truncation test (recompute features on prefixes, assert values never change), signal-before-entry ordering check, and same-bar-close usage detection. |
| [`tools/walkforward.py`](tools/walkforward.py) | Anchored and rolling walk-forward splits with purge and embargo for overlapping labels; per-fold statistics and a fold-sign summary. |
| [`tools/bootstrap.py`](tools/bootstrap.py) | Stationary block bootstrap for per-trade and daily returns, with confidence intervals on mean return and Sharpe. Blocks, because trades cluster. |
| [`tools/four_cell.py`](tools/four_cell.py) | The regime × sample four-cell test described above, with minimum-observation guards and explicit NaN handling for undefined regime periods. |

Each runs standalone on synthetic data: `python examples/demo.py`.

## What is not here

Deliberately excluded, and I would rather say so than have it look like an omission:

- Exact entry/exit thresholds, lookback windows and position caps
- `frozen_strategy.json` and execution profiles
- Trade-level logs and equity curves
- Raw market data (redistribution) and exchange credentials

The methodology is the transferable part. The thresholds are not what makes the work
interesting, and the strategy is still under forward validation.

## Repository layout

```
docs/
  RESEARCH_PROTOCOL.md   the seven rules, and why each exists
  FAILURE_LIBRARY.md     25 killed candidates with cause of death
  BUGS_AND_LESSONS.md    22 bugs found, with mechanism and fix
  REGIME_CONDITIONING.md the four-cell test and what it rejected
tools/                   reusable, standalone validation modules
examples/demo.py         runs every tool on synthetic data
```

## License

MIT — see [LICENSE](LICENSE).
