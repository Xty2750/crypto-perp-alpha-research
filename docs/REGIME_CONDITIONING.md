# Regime Conditioning and the Four-Cell Test

How a comfortable explanation was turned into a test that could fail — and what it killed.

---

## The observation

Roughly a third of the killed candidates died the same way: positive in-sample,
sign-flipped out-of-sample. Realized volatility percentiles, volatility asymmetry, intraday
anchoring, deep-drawdown reversal, cross-sectional 20-day reversal, BTC→altcoin lead-lag.

Consistent sign flipping is a different failure mode from randomness. A signal with no edge
produces noise around zero across periods. A signal that is reliably positive in one period
and reliably negative in the next is being conditioned by something that changed between
them.

## What changed

The frozen out-of-sample cut date landed almost exactly on a market regime turn:

| Period | BTC above 200-day MA | Character |
|---|---|---|
| In-sample | 90% of days | bull |
| Out-of-sample | 79% of days below | bear |

So the split was not "earlier vs later." It was, very nearly, "bull vs bear."

That reframes every sign flip. Rebound and reversal signals were positive in the bull half
and negative in the bear half; momentum and short-side signals the reverse. The obvious
conclusion is that these signals are regime-conditional and were never dead.

The 200-day moving average is knowable in real time, so conditioning on it is legitimate —
it is not a hindsight label.

## Why this is dangerous

This is exactly the shape of a rationalization. A batch of failed candidates, and a story
that explains why they should be revived. Applied loosely, it would resurrect a third of
the failure library and let each one be re-fit inside its favorable regime — every one
supported by a single stretch of favorable market.

The problem is structural: after conditioning on regime, most candidates have exactly *one*
populated regime cell with meaningful sample size. A positive result in one bull period is
not evidence that the effect is a bull-market effect. It is one observation.

## The test

> **Four-cell validation.** Partition every result into
> `{bull, bear} × {in-sample, out-of-sample}`. Every cell with a meaningful number of
> observations must carry the same sign. A signal claimed to be regime-conditional must be
> observed **twice independently within the same regime** — once in-sample, once
> out-of-sample.

Implementation requirements that turned out to matter:

- **Minimum observation guard.** Cells below a threshold are reported as underpowered, not
  as passes. Several candidates had bear cells with N = 2 or N = 7.
- **Explicit NaN handling.** The regime indicator is undefined during its warm-up window.
  Those observations must be dropped, not silently classified — see bug #3 in
  [BUGS_AND_LESSONS.md](BUGS_AND_LESSONS.md), where NaN handling alone manufactured a
  false conclusion.
- **Report all four cells always**, including the empty ones. An unpopulated cell is a
  statement about what the sample cannot support.
- **A cell indistinguishable from zero cannot confirm anything.** A purely sign-based rule
  is weaker than it looks: two cells of pure noise agree in sign half the time, so a dead
  signal passes at a 50% rate. Cells below a minimum |t| are marked *inconclusive* rather
  than counted as confirmations. This is a weak guard, not a significance test — the
  bootstrap remains the final arbiter.

Implemented in [`tools/four_cell.py`](../tools/four_cell.py).

## What it rejected

Six candidates that the regime story would have revived:

| Candidate | Four-cell outcome |
|---|---|
| Realized-volatility spike, regime version | Bull leg flipped (+1.34 IS / −0.39 OOS); bear leg was a single observation |
| Fear-extreme, regime version | Bear leg unstable (−3.07 IS / +1.84 OOS); bull leg positive in both cells but too weak to matter |
| Intraday anchoring, regime version | Bull leg ≈ 0 in-sample; bear leg a single observation |
| Deep drawdown → bear-market short | Negative within the in-sample bear segment — the bear leg contradicted itself |
| BTC lead-lag beta, regime version | All four cells negative (t = −5.4 to −16.9); 14bp round-trip costs consume a lagged beta of ±0.03–0.08 |
| Panic-day flow event with regime gate | **Passed.** Positive in the bull cell in-sample and again in a separate out-of-sample bull stretch. Post-cost Sharpe 0.68 → 1.03 |

**Five rejected, one validated.** The retest list closed completely; the single survivor
was a candidate that was not on it.

## Follow-through on the survivor

Passing the four-cell test earned the survivor further scrutiny, not acceptance. Eight
refinement directions were tested against it:

| Direction | Outcome |
|---|---|
| Extended holding period | **Adopted** — Sharpe 1.03 → 1.25 |
| Funding-rate filter | Rejected — the pattern held in both funding states; the filter only removed positive-expectancy trades |
| Event synchronization across pairs | No filtering value — high synchronization covers most events |
| Generalizing the mechanism to a different event type | Rejected — sign-flipped out-of-sample. The mechanism belongs to one event class, not to crowding events generally |
| Volatility-adaptive threshold | Rejected — every adaptive variant underperformed the fixed threshold monotonically |
| Trigger-window scan | Confirmed the existing window sits on a plateau |
| Early-move protective exit | Rejected — every threshold hurt |
| Entry microstructure variants | Confirmed the existing choice |

One adopted out of eight. The design sits at a robust local optimum, and knowing *that* is
worth more than another parameter.

## Where it did not help

Six separate conditioning variables were tested to explain a quarterly alternation in one
strategy leg's performance: regime, momentum, realized volatility, drop depth, early-move
protection, and cross-pair synchronization. All six failed. Good and bad quarters spanned
both bull and bear periods, and no observable rule separated them.

That line was closed and documented rather than pursued. Not every pattern has an
observable condition, and the honest answer to "what explains this?" is sometimes "nothing
I can measure, and I stopped looking."
