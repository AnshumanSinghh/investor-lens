"""Joel Greenblatt: Magic Formula (cheap relative to earnings, high return on capital)."""

from __future__ import annotations

from typing import Optional

from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.calculators.statements import latest
from investor_lens.domain.constants import RuleName, Statement
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import GreenblattParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_EARNINGS_YIELD = "earnings_yield"
_RETURN_ON_CAPITAL = "return_on_capital"


class GreenblattRule(FilterRule):
    """Advisory: earnings yield (EBIT / EV) >= 8% and return on capital >= 25%.

    EV = market cap + total debt - cash. Invested capital = (current assets - cash) -
    (current liabilities - current debt) + net PP&E. Financials and utilities are not assessed.
    The book ranks a whole universe; this rule applies absolute cut-offs instead.
    """

    name = RuleName.GREENBLATT
    investor = "Joel Greenblatt"
    gating = False

    def __init__(self, parameters: GreenblattParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        asset = ctx.asset
        if asset.sector in self._p.excluded_sectors:
            reason = f"Sector '{asset.sector}' is excluded from the Magic Formula."
            collector.skip(_EARNINGS_YIELD, reason)
            collector.skip(_RETURN_ON_CAPITAL, reason)
            return self._finalize(collector)

        ebit = latest(asset.statements, Statement.EBIT)
        collector.set_metrics(ebit=ebit)
        self._check_earnings_yield(asset, ebit, collector)
        self._check_return_on_capital(asset, ebit, collector)
        return self._finalize(collector)

    def _check_earnings_yield(self, asset: AssetSnapshot, ebit: Optional[float], c: CheckCollector) -> None:
        cash = latest(asset.statements, Statement.CASH) or 0.0
        if ebit is None or asset.market_cap is None or asset.total_debt is None:
            c.skip(_EARNINGS_YIELD, "EBIT, market cap or total debt unavailable.")
            return
        enterprise_value = asset.market_cap + asset.total_debt - cash
        c.set_metrics(enterprise_value=enterprise_value)
        if enterprise_value <= 0:
            c.skip(_EARNINGS_YIELD, "Non-positive enterprise value: earnings yield not meaningful.")
            return
        earnings_yield = ebit / enterprise_value
        c.set_metrics(earnings_yield=earnings_yield)
        threshold = self._p.min_earnings_yield
        c.record(
            _EARNINGS_YIELD,
            passed=earnings_yield >= threshold,
            score=clip(earnings_yield / (2 * threshold), 0.0, 1.0),
            failure_reason=f"Earnings yield {earnings_yield:.1%} below {threshold:.1%}.",
        )

    def _check_return_on_capital(
        self, asset: AssetSnapshot, ebit: Optional[float], c: CheckCollector
    ) -> None:
        s = asset.statements
        current_assets = latest(s, Statement.CURRENT_ASSETS)
        current_liabilities = latest(s, Statement.CURRENT_LIABILITIES)
        net_ppe = latest(s, Statement.NET_PPE)
        if ebit is None or current_assets is None or current_liabilities is None or net_ppe is None:
            c.skip(_RETURN_ON_CAPITAL, "EBIT, working-capital lines or net PP&E unavailable.")
            return
        cash = latest(s, Statement.CASH) or 0.0
        current_debt = latest(s, Statement.CURRENT_DEBT) or 0.0
        working_capital = (current_assets - cash) - (current_liabilities - current_debt)
        invested_capital = working_capital + net_ppe
        c.set_metrics(net_working_capital=working_capital, invested_capital=invested_capital)
        if invested_capital <= 0:
            c.skip(_RETURN_ON_CAPITAL, "Non-positive invested capital: return on capital not meaningful.")
            return
        roc = ebit / invested_capital
        c.set_metrics(return_on_capital=roc)
        threshold = self._p.min_return_on_capital
        c.record(
            _RETURN_ON_CAPITAL,
            passed=roc >= threshold,
            score=clip(roc / (2 * threshold), 0.0, 1.0),
            failure_reason=f"Return on capital {roc:.1%} below {threshold:.1%}.",
        )
