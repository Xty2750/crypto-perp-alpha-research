# Bugs and Lessons

Every bug below silently produced a *plausible* result. None raised an exception. That is
the category that matters in backtesting: the failure mode is not a crash, it is a number
that looks right.

Ordered by how much damage each one did.

---

## 1. Look-ahead through calendar misalignment

**Symptom.** A market-breadth filter appeared to double a short strategy's Sharpe, from
0.68 to 2.07.

**Mechanism.** The strategy traded open→close on day D+1 from a signal generated on day D.
The filter was computed on D+1's breadth — which is built from D+1's *closing* prices. The
condition therefore knew the outcome of the trade it was gating.

**Fix and result.** Move the filter to information available at signal time (day D). Every
threshold from 0.2 to 0.67 then turned negative in-sample, and the filter was killed.

**Lesson.** Condition and return must be calendar-aligned field by field. Write down, for
every field, the exact timestamp at which it becomes knowable, and compare it to the entry
timestamp. "It's a daily bar" is not an answer.

---

## 2. Annualization inflated by a destroyed calendar index

**Symptom.** Sharpe 2.18 on a strategy whose true value was 0.87.

**Mechanism.** `dropna()` on a signal Series removed non-signal days entirely. Merging on
the surviving index produced a return series with no calendar structure, so elapsed years
were computed as 0.28 instead of ~1.0 — inflating the annualization factor by 3.6×.

**Fix.** Portfolio daily returns must retain the full calendar index, with 0 filled on
non-signal days. Compute elapsed time from the calendar, never from the number of rows.

---

## 3. Rolling indicator NaNs silently mislabeling a regime

**Symptom.** A conclusion that a rebound effect was "a bear-market phenomenon."

**Mechanism.** A 200-day moving average is NaN for the first 200 days. `close >= NaN`
evaluates to `False`, so every early event was labeled bear. Five bull-market events were
misfiled, and the bull in-sample cell dropped from 7 observations to 2.

**Fix.** Any regime condition must explicitly drop the period where its indicator is
undefined. Never let a boolean comparison swallow NaN.

**Lesson.** This one is nasty because the bug *creates* a clean story rather than a noisy
one, and a clean story is exactly what you were hoping for.

---

## 4. Stop-loss checked only at exit time

**Symptom.** Time-exit trades recorded as winners that had actually been stopped out.

**Mechanism.** The time-based exit compared exit price against the stop level. A position
that traded through its stop mid-hold and recovered was scored on the recovered price.

**Fix.** Bar-by-bar stop monitoring for the entire holding period, not a single check.

---

## 5. Monitoring window shorter than the holding period

**Symptom.** One trade in a full audit exited below its stop and was still recorded as a
time exit.

**Mechanism.** The stop-monitoring window ended at 48h, but the time exit used the first
hourly close *after* 48h. A break in that final hour was invisible.

**Fix.** Extend monitoring through the exit bar. Aggregate impact was ≈ 0 (+1.04% → +1.05%
per trade) — the point is not the number, it is that a trade-by-trade audit must return
*zero* violations before any result is reported.

---

## 6. Position size missing a price factor

**Symptom.** All early total-return figures wrong.

**Mechanism.** `size = risk / stop_distance` omitted multiplication by entry price, so
notional value was understated by roughly 60,000×.

**Lesson.** Assert on units. A dimensional check on position sizing takes one line and
would have caught this before it contaminated every downstream result.

---

## 7. Mixed-unit comparisons

**Symptom.** Conditions that were always true or always false.

**Mechanism.** Comparing a candle body expressed as a *fraction* against `k × ATR`
expressed in *price*. Separately, a range band written as `c0 ± r × ATR_pct` subtracted a
fraction from a price, producing a band of ±0.0025%.

**Fix.** Normalize before comparing (divide by ATR or by close), and multiply explicitly
when a band must live in price space.

---

## 8. Short-side cost sign

**Mechanism.** Reusing the long-side cost formula with a `direction = −1` multiplier
inverts the cost direction. A short must be modeled as sell at `price × (1 − c)` and cover
at `price × (1 + c)`. The shortcut overstated returns by ~0.14% per trade.

**Lesson.** Write directional formulas separately. Do not fold direction into a sign
multiplier on a quantity that is not antisymmetric.

---

## 9. `rank()` without `pct=True`

**Mechanism.** `df.rank(axis=1)` returns integer ranks 1..n. A subsequent `rank < 0.1`
is therefore always `False` and `rank > 0.9` always `True` — the "top decile" silently
became the entire sample. Spearman IC was unaffected, which is what made it hard to notice:
one diagnostic looked fine while the quantile selection was completely wrong.

---

## 10. `groupby().nth()` returning original row indices

**Mechanism.** `groupby('day')['close'].nth(1)` and `.last()` return the *original*
timestamp index (01:00, 23:00), while `.first()` returns the group key (00:00). Dividing
two such Series aligns on nothing and yields all-NaN.

**Fix.** `series.index = series.index.floor('D')` before aligning.

---

## 11. Duplicate entries from overlapping windows

**Mechanism.** Adjacent trigger runs had overlapping 48h detection windows, so a single
breakout bar was recorded as two trades, inflating both the trade count and the aggregate.

**Fix.** Deduplicate by entry bar — at most one position per entry timestamp.

---

## 12. Structure detection using a global extremum

**Mechanism.** Using `argmax` over the whole window to locate a swing high pushes the pivot
to the end of the window during a rally, making the subsequent pullback-and-break
undetectable.

**Fix.** Detect the *first* swing point confirmed by N subsequent opposite bars, not the
global extremum. Sensitivity testing across five swing definitions later showed results are
insensitive to the definition — but only once the definition is causal.

---

## 13. Consecutive-count sentinel off by one

**Mechanism.** A run counter initialized without a sentinel returned 0 instead of 1 when the
condition was already true at the start of a segment. Use `last_false = -1`.

---

## 14. Self-inclusion in a cross-sectional confirmation count

**Mechanism.** `confirmations_all - self_confirmation` always subtracts 1 on the signal bar,
because the pair itself is necessarily inside its own window. A threshold of "≥ 2
confirmations" silently became "≥ 3".

---

## 15. Chained comparison on a Series

**Mechanism.** `a < x == b` parses as `(a < x) and (x == b)`, and `and` on a Series raises
an ambiguity error — or worse, works by accident on scalars. Write `((a < x) == b).mean()`.

---

## 16. Timestamp convention mismatch between datasets

**Mechanism.** Daily open interest is stamped 16:00 UTC while daily candles close at 00:00
UTC. Using day D's OI to predict the D→D+1 return embeds 8 hours of look-ahead.

**Note.** In this case the bias favored the hypothesis and the hypothesis still failed, so
no conclusion changed — but the reporting convention has to be stated either way.

---

## 17. Genetic programming overfitting to a single training window

**Symptom.** Best evolved formula reached training t = 2.96 and IC t = 2.64; all 20 top
formulas had out-of-sample IC ≈ 0 or negative. **0 of 20 passed.**

**Mechanism.** Using the training-window t-statistic as the fitness function lets the
search select noise formulas directly.

**Fix.** Fitness = minimum t across three internal walk-forward folds, requiring all three
positive. Plus semantic deduplication of the candidate pool — algebraically equivalent
expressions such as `min(close, close) = close` were flooding the top rankings. Pass rate
went from 0/20 to 4/20; all four were still rejected at the bootstrap stage.

**Lesson.** An overfitting-resistant fitness function is necessary, not sufficient.

---

## 18. Parameter selection inside the training window still overfits

**Symptom.** Parameters chosen by three-fold minimum-t within the training window selected
a near-fully-invested quantile; out-of-sample performance immediately degraded to t = 0.50.

**Fix.** Nested selection — choose parameters on the first 60% of the training window,
validate on the remaining 40%, then touch the true out-of-sample once. Final result improved
to t = 1.51, and was *still* rejected because the bootstrap CI contained zero.

**Lesson.** In a single-instrument two-year price sample, "best on training" carries no
reliable mapping to "good out-of-sample." The endpoint of any automated search must be data
that participated in no selection step whatsoever.

---

## 19. Selection bias measured directly

Six factors hand-picked from the full sample gave out-of-sample IC +0.190 and post-cost
Sharpe 2.40. Restricting factor choice and sign determination to the training window — same
factor family, same combination method — gave IC +0.081 and Sharpe 1.11, with a bootstrap
95% CI spanning zero.

**The difference between those two numbers is the selection bias, quantified.** Any feature
selection, sign choice or weighting must be decided on training data alone, and out-of-sample
may be touched exactly once.

---

## 20. Pooled t-statistics

Covered in the [failure library](FAILURE_LIBRARY.md): cross-pair pooling inflates
significance through event clustering, unnormalized averaging and mixed session effects.
Pooled t of 3.6–10 produced a portfolio engine Sharpe of −0.76.

---

## Smaller traps

- A pandas `DatetimeIndex` comparison returns a plain ndarray — no `.to_numpy()` needed, and
  calling it raises.
- Exchange OI endpoints have per-granularity history limits (daily ~730 days, hourly ~30
  days, 5-minute ~3 days). Design collection around this rather than discovering it late.
- Some endpoints require authentication and are simply unavailable for research. Plan the
  data inventory before designing a study around a field you cannot get.

---

## The general lesson

Every one of these produced a runnable backtest and a plausible number. The defenses that
actually worked were structural, not vigilance:

- A **truncation test** that recomputes features on data prefixes and asserts values never
  change afterwards.
- A **trade-by-trade audit** that must return zero violations before any result is reported.
- **Unit assertions** on anything that mixes price, fraction and volatility scales.
- **Bootstrap confidence intervals** as the final arbiter, not point estimates.

Those four are implemented in [`tools/`](../tools).
