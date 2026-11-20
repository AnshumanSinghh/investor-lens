"""Ray Dalio: volatility, Sharpe and benchmark-correlation filter (non-gating)."""

from __future__ import annotations

from typing import List

from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.calculators.risk import (
    annualized_volatility,
    pearson_correlation,
    sharpe_ratio,
    trailing_annualized_return,
)
from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import EvaluationContext, RuleResult
from investor_lens.domain.parameters import DalioParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_SHARPE = "sharpe"
_BENCHMARK_CORRELATION = "benchmark_correlation"


class DalioRule(FilterRule):
    """Flags low Sharpe and high benchmark correlation.

    Non-gating: breaches never disqualify an asset; the ``PortfolioAllocator``
    scales the weight of flagged assets instead.
    """

    name = RuleName.DALIO
    investor = "Ray Dalio"
    gating = False

    def __init__(self, parameters: DalioParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        p, market = self._p, ctx.market
        returns = ctx.asset.log_returns()

        volatility = annualized_volatility(returns, p.vol_window)
        if volatility is None:
            return self._fallback(["Insufficient return history for volatility."])

        collector = CheckCollector()
        flags: List[str] = []
        annual_return = trailing_annualized_return(returns, p.corr_lookback)
        collector.set_metrics(
            annualized_return_12m=annual_return,
            risk_free_rate=market.risk_free_rate,
            observations_12m=min(len(returns), p.corr_lookback),
            **{Metric.VOLATILITY: volatility},
        )

        sharpe = sharpe_ratio(annual_return, market.risk_free_rate, volatility)
        if sharpe is None:
            collector.skip(_SHARPE, "Volatility is zero or undefined; Sharpe not computable.")
        else:
            collector.set_metrics(**{Metric.SHARPE_RATIO: sharpe})
            passed = sharpe >= p.min_sharpe
            collector.record(
                _SHARPE,
                passed,
                clip(sharpe / p.min_sharpe, 0.0, 1.0),
                f"Sharpe {sharpe:.2f} < {p.min_sharpe:.2f}.",
            )
            if not passed:
                flags.append("LOW_SHARPE")

        if market.benchmark_returns.empty:
            collector.skip(_BENCHMARK_CORRELATION, "Benchmark returns unavailable.")
        else:
            result = pearson_correlation(returns, market.benchmark_returns, p.corr_lookback, p.min_corr_obs)
            if result.coefficient is None:
                collector.skip(
                    _BENCHMARK_CORRELATION,
                    f"Correlation to benchmark not computable ({result.observations} overlapping days, "
                    f"minimum {p.min_corr_obs}).",
                )
            else:
                r = result.coefficient
                collector.set_metrics(
                    correlation_observations=result.observations, **{Metric.BENCHMARK_CORRELATION: r}
                )
                passed = r <= p.max_market_corr
                collector.record(
                    _BENCHMARK_CORRELATION,
                    passed,
                    clip(1.0 - r, 0.0, 1.0),
                    f"Correlation to benchmark {r:.2f} > {p.max_market_corr:.2f}: weak diversifier.",
                )
                if not passed:
                    flags.append("HIGH_MARKET_CORRELATION")

        collector.set_metrics(flags=flags)
        return self._finalize(collector)
