# Research Protocol

The seven rules, and how each one is actually enforced. Every rule exists because breaking
it produced a wrong answer at least once.

---

## 1. Prove alpha before building an engine

**Rule.** Grouped returns, rank IC and t-statistics first. A candidate only earns a backtest
after it clears that screen.

**Why.** A backtest engine is expensive to write and, worse, it is *persuasive* — once you
have an equity curve you start tuning it. A grouped-return table is cheap and hard to argue
with.

**Enforcement.** Bucket the signal into quantiles, compute forward returns per bucket, and
require monotonicity plus a t-statistic that survives the cost hurdle. No engine before that.

**Caveat learned the hard way.** Passing this screen is necessary, not sufficient. A pooled
cross-pair screen produced t-statistics of 3.6–10 for a candidate whose portfolio engine
returned Sharpe −0.76. See rule 4.

---

## 2. Model costs honestly

**Rule.** Taker 5bp fee + 2bp slippage per side as the default. Maker 2bp as sensitivity.
Doubled cost as a stress scenario. Funding settled at true timestamps.

**Why.** Cost is the binding constraint in this market, not signal quality. At the 1-minute
scale, 1R ≈ 0.07% while fixed cost ≈ 1.6R — an entire early version of this work lost money
across its whole parameter space for exactly this reason, and no amount of signal
improvement could have saved it.

**Enforcement.** Costs are applied inside the engine, per side, with directional formulas
written separately for long and short (folding direction into a sign multiplier inverts the
short-side cost — see bug #8). Every reported figure is post-cost. Any result that only
works at maker fees is labeled as such.

---

## 3. Freeze an out-of-sample cut

**Rule.** One cut date, fixed in advance. Both halves must be positive.

**Why.** A movable cut date is a free parameter, and a well-chosen one can rescue anything.

**Enforcement.** The cut is declared before the experiment. Robustness is tested by
*additional* cut dates reported alongside the primary one — never by replacing it. A result
that only survives at one particular cut is reported as failing.

**What this rule cannot do.** It cannot tell you *why* a candidate flipped. The cut here
landed on a regime turn, which took a separate investigation to discover — see
[REGIME_CONDITIONING.md](REGIME_CONDITIONING.md).

---

## 4. Cross-sectional robustness

**Rule.** Twelve pairs, volatility-normalized, equally weighted. A result on one pair is not
a result.

**Why.** Pooled statistics across pairs are inflated by three separate mechanisms:
event clustering (all 12 pairs firing in the same hour, so effective N is far below nominal
N), unnormalized averaging that lets the highest-volatility pair dominate, and mixed session
effects.

**Enforcement.** After any pooled screen, the candidate must pass a portfolio engine with
volatility normalization, equal weighting, a volatility target, and separate in/out-of-sample
reporting. Per-pair contribution is reported — "10 of 12 pairs contributed positively" is a
finding; a portfolio number alone is not.

---

## 5. Parameter plateaus over single-point optima

**Rule.** A lone peak in a parameter grid is an artifact. A plateau is a property.

**Enforcement.** Scan the grid and report the full surface, not the maximum. The surviving
strategy was checked across 201 configurations, of which 97% were positive in both periods.
A rejected candidate had exactly one window length that worked, with neighbors falling off —
that was recorded as a reason to reject, regardless of its point estimate.

---

## 6. New mechanisms, not recombinations

**Rule.** Combining existing components to raise a portfolio Sharpe is not a research result
and is not the goal.

**Why.** Recombination always improves the headline number and never adds knowledge. It is
the easiest way to look productive while learning nothing.

**Enforcement.** Portfolio-level results are recorded as byproducts, explicitly labeled, and
never used as evidence for a mechanism. When a target is not met, the honest report is that
it was not met — no standard gets relaxed to reach a number.

---

## 7. One step, one verification

**Rule.** Every directional condition passes the four-cell regime test before it counts.
Every result passes a trade-by-trade audit with zero violations before it is reported.

**Enforcement.** The audit is a hard gate, not a review. It checks that every trade's signal
timestamp precedes its entry timestamp, that stops were monitored bar-by-bar for the full
holding period including the exit bar, that no trade duplicates an entry bar, and that no
feature used data unavailable at decision time.

Aggregate impact of the last audit fix was ≈ 0 (+1.04% → +1.05% per trade). That is the
point: the gate is not there to improve numbers, it is there to make them reportable.

---

## The final arbiter

Point estimates do not decide anything. A candidate is accepted only if a **stationary block
bootstrap** confidence interval on its per-trade return excludes zero. Blocks, because trades
cluster in time and an i.i.d. bootstrap would understate the interval.

Several candidates with attractive point estimates were rejected at exactly this step:
out-of-sample per-trade returns of +0.203% (t = 1.25), +0.596% (t = 1.51) and +0.129%
(t = 0.86) all had confidence intervals containing zero. They are recorded as candidates,
not as findings.
