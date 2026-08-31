# Failure Library

25 candidates tested and killed, with hypothesis and cause of death. Kept because a
research program's negative results are the part that stays true — a killed candidate
saves the next person the same month of work, and the *pattern* of how things die is more
informative than any single survivor.

Costs assumed throughout: taker 5bp + 2bp slippage per side, unless noted. `IS` =
in-sample, `OOS` = out-of-sample, split at a frozen cut date.

---

## Cross-sectional and ranking signals

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Cross-sectional momentum | Strong pairs keep outperforming; rotate across the 12 | Rank IC ≈ 0 (−0.005 to +0.012) at every horizon tested |
| Cross-sectional 1-day reversal | Yesterday's winners underperform today | IC only −0.014 to −0.022 (t < 1.5); long/short daily return −0.12% to −0.16%, below daily turnover cost |
| Cross-sectional 20-day reversal | Longer-horizon mean reversion | IC weak and sign-flipped across periods; weekly long/short Sharpe −0.32 |
| Aggregate open-interest ranking | Crowding ranks predict relative returns | No cross-period stable configuration |

## Time-of-day, calendar and seasonality

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Intraday seasonality (standalone) | Session effects are tradable | IS patterns fully decayed OOS |
| Day-of-week effects | Monday / weekend effects | All effects sign-flipped OOS |
| Intraday anchoring (first 2h → rest of session) | 24/7 markets manufacture a synthetic "open" | Both day boundaries (00:00 and 12:00 UTC) sign-flipped. 12:00 boundary: first-2h-strong gave IS +0.83% (t=3.2) → OOS −0.67% (t=−4.2) |

## Funding-rate signals

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Funding sentiment extremes | Extreme rates mark reversals | Sign-flipped OOS. **Finding:** high positive funding = long crowding = price *continues*. Funding is a crowding gauge, not a contrarian signal |
| Funding settlement microstructure | Position closing around settlement creates pressure | No detectable effect — arbitrageurs already absorb it |
| Pure funding harvesting (delta-exposed) | Collect the rate on the paying side | Directional exposure runs against the carry; noise dwarfs the rent |
| Funding + OI dual confirmation | Two crowding gauges are better than one | Redundant — OI and funding crowding overlap, leaving only 9 events |

## Open-interest and leverage

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Liquidation rebound (OI collapse + sharp drop) | Cascade produces oversold bounce | Catching a falling knife; continuation, not reversal |
| Aggregate leverage / deleveraging speed | Market-wide leverage state times the market | All three metrics sign-flipped IS→OOS; interaction cells underpopulated |

## Breadth and dispersion

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Breadth / dispersion as standalone signal | Breadth collapse → bounce; extreme breadth → short | All sign-flipped. Breadth describes the regime; it does not predict returns |
| Breadth as a filter on a short strategy | Low breadth should double the edge | **Look-ahead artifact.** The filter was evaluated on the trade day D+1, whose breadth includes D+1's close, while the trade ran open→close on D+1. Corrected to signal-day D: every threshold from 0.2 to 0.67 turned negative in-sample. The apparent Sharpe 2.07 was the bug |
| Breadth as a filter on an OI-crowding strategy | Same switch, different base | A 200-day moving-average regime switch (Sharpe 1.15) beat every breadth threshold (0.20–0.44). The switch does not generalize |

**Conclusion across these:** aggregate market-level indicators — total OI, breadth,
dispersion — never found a single leak-free use, as standalone signals or as conditioning
switches.

## Volatility and price structure

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| Implied volatility (DVOL) timing | IV extremes mark fear/complacency | All metrics sign-flipped. IV below the 15th percentile: IS +1.2% over 10d → OOS −4.1% (t=−5.4). The data pipeline was kept; the signal was not |
| Realized-volatility level and change percentiles | Expansion → bounce, compression → breakout | RV expansion 5d: IS +3.67% (t=3.0) → OOS −1.40% (t=−2.7) |
| Volatility asymmetry (down-volume share) | Fear extremes → bounce, complacency → short | Fear extreme 1d: IS +0.41% (t=2.4) → OOS −0.37% (t=−2.4); engine Sharpe −0.55 |
| Absorption (high volume, small body) + close location | Distribution/accumulation mechanics | Combined conditions gave N ≈ 0; relaxing them produced sign flips. Close-location value alone had no predictive power |
| Deep-drawdown first green day | Recovery has an identifiable start | All three variants sign-flipped |
| Opening-range breakout (Asian session) | Compression precedes expansion | Naked breakout has no edge; even with two filters the win rate was 50.2% |

## Higher-frequency and lead-lag

| Candidate | Hypothesis | Cause of death |
|---|---|---|
| 1h volume spike → 2h long | Hourly version of the panic-rebound structure | **Pooled t-statistic illusion.** Pooled t of 3.6–10; the combined engine returned Sharpe −0.76 (IS +1.77 / OOS −2.78). Half the pairs were negative individually |
| BTC → altcoin 1h lead-lag | Altcoin beta to BTC is lagged | Lag-1 beta was negative (reversal, t = −2 to −4.7) in-sample and positive (momentum) out-of-sample |
| BTC lead-lag, regime-conditioned | Momentum in bull, reversal in bear | All four cells negative (t = −5.4 to −16.9). 14bp round-trip costs consume a lagged beta of ±0.03–0.08. The original flip was sub-cost noise |
| State-switch mean reversion | Contraction phases revert | At the 1h scale this market is momentum, not reversion |
| Altcoin 30-minute crash rebound | Oversold bounce | Fully negative OOS — altcoin crashes are noise, not events |
| Short-horizon momentum, daily rebalanced | 3–5 day momentum | Daily re-evaluation produced 78–103 turns per year. Holding-period locking is the hidden design feature that makes trend-following work |

## Regime-conditioned retests

After the regime discovery, five previously-killed candidates were retested under the
four-cell rule. All five failed again — a single favorable regime observation was the whole
result each time. Details in [REGIME_CONDITIONING.md](REGIME_CONDITIONING.md).

---

## Patterns worth extracting

1. **Costs are the binding constraint.** At the 1-minute scale, 1R ≈ 0.07% while fixed cost
   is ≈ 1.6R. Minute-level directional trading is arithmetically impossible here, which is
   why an entire early version of this work lost money across its whole parameter space.
2. **Strong signals are low-frequency.** Every candidate with a 58–78% hit rate fired
   ≤ 0.5 times per day. "Daily, and accurate" does not exist in a 24/7 liquid market.
3. **Pooled t-statistics inflate.** Cross-pair pooling is inflated by event clustering (12
   pairs firing in the same hour), by unnormalized averaging that lets the most volatile
   pair dominate, and by mixed session effects. A pooled screen must be followed by a
   volatility-normalized, equal-weighted portfolio engine before it counts.
4. **Sign flips are informative, not terminal.** The failure mode was overwhelmingly
   "flipped," not "random." That says the effects exist and are conditional — which is what
   made the regime work worth doing, and what made a test that can *fail* necessary.
5. **State indicators are not alpha; event sequences are.** Every survivor was built from
   per-pair event extremes, not from market-state descriptors.
