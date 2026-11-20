"""Warren Buffett: DCF margin of safety plus leverage guardrail."""

from __future__ import annotations

import math

from investor_lens.domain.calculators.dcf import (
    CapitalStructure,
    cost_of_equity_capm,
    historical_eps_growth,
    two_stage_dcf,
    weighted_average_cost_of_capital,
)
from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import BuffettParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_LEVERAGE = "leverage"
_MARGIN_OF_SAFETY = "margin_of_safety"


class BuffettRule(FilterRule):
    """Disqualify if Price/IntrinsicValue > 0.80 or Debt/Equity > 0.50."""

    name = RuleName.BUFFETT
    investor = "Warren Buffett"
    gating = True

    def __init__(self, parameters: BuffettParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        self._check_leverage(ctx.asset, collector)
        self._check_margin_of_safety(ctx, collector)
        return self._finalize(collector)

    def _check_leverage(self, asset: AssetSnapshot, c: CheckCollector) -> None:
        p = self._p
        if asset.total_debt is None or asset.total_equity is None:
            c.skip(_LEVERAGE, "Total debt or total equity unavailable.")
            return
        if asset.total_equity <= 0:
            c.set_metrics(leverage_ratio=None)
            c.fail(_LEVERAGE, "Non-positive shareholder equity: leverage undefined, disqualified.")
            return
        leverage = asset.total_debt / asset.total_equity
        c.set_metrics(leverage_ratio=leverage)
        c.record(
            _LEVERAGE,
            passed=leverage <= p.max_leverage,
            score=clip(1.0 - leverage / p.max_leverage, 0.0, 1.0),
            failure_reason=f"Leverage {leverage:.2f} exceeds {p.max_leverage:.2f}.",
        )

    def _check_margin_of_safety(self, ctx: EvaluationContext, c: CheckCollector) -> None:
        p, asset, market = self._p, ctx.asset, ctx.market

        g_hist = historical_eps_growth(asset.eps_history, p.eps_growth_min_points, p.eps_growth_max_points)
        c.set_metrics(eps_growth_trailing_raw=g_hist)
        if g_hist is None:
            c.skip(_MARGIN_OF_SAFETY, "Insufficient positive EPS history to estimate growth g.")
            return
        if asset.free_cash_flow is None:
            c.skip(_MARGIN_OF_SAFETY, "Free cash flow unavailable.")
            return
        if not asset.shares_outstanding or asset.shares_outstanding <= 0:
            c.skip(_MARGIN_OF_SAFETY, "Shares outstanding unavailable.")
            return

        c.set_metrics(free_cash_flow_0=asset.free_cash_flow)
        if asset.free_cash_flow <= 0:
            c.set_metrics(**{Metric.INTRINSIC_VALUE: None})
            c.fail(_MARGIN_OF_SAFETY, "Non-positive free cash flow: no DCF intrinsic value, disqualified.")
            return

        growth = clip(g_hist, p.growth_floor, p.growth_cap)
        risk_free = market.risk_free_rate
        beta = asset.beta if asset.beta is not None and math.isfinite(asset.beta) else p.default_beta
        cost_equity = cost_of_equity_capm(risk_free, beta, p.equity_risk_premium)
        wacc_breakdown = weighted_average_cost_of_capital(
            cost_equity,
            CapitalStructure(asset.market_cap, asset.total_debt, asset.interest_expense, asset.tax_rate),
            risk_free,
            p.default_credit_spread,
        )
        terminal_growth = max(0.0, min(risk_free, p.terminal_growth_cap))
        wacc = max(wacc_breakdown.wacc, terminal_growth + p.min_wacc_spread)

        dcf = two_stage_dcf(asset.free_cash_flow, growth, wacc, terminal_growth, p.dcf_years)
        intrinsic = dcf.total / asset.shares_outstanding
        c.set_metrics(
            growth_used=growth,
            beta_used=beta,
            risk_free_rate=risk_free,
            cost_of_equity_capm=cost_equity,
            wacc_unfloored=wacc_breakdown.wacc,
            wacc_used=wacc,
            terminal_growth=terminal_growth,
            wacc_components=wacc_breakdown.components(),
            pv_explicit_total=dcf.pv_explicit,
            pv_terminal_total=dcf.pv_terminal,
            **{Metric.INTRINSIC_VALUE: intrinsic},
        )
        if intrinsic <= 0:
            c.fail(_MARGIN_OF_SAFETY, "Non-positive intrinsic value, disqualified.")
            return

        ratio = asset.current_price / intrinsic
        c.set_metrics(margin_of_safety=1.0 - ratio, **{Metric.PRICE_TO_INTRINSIC_VALUE: ratio})
        c.record(
            _MARGIN_OF_SAFETY,
            passed=ratio <= p.max_price_to_value,
            score=clip((1.0 - ratio) / 0.5, 0.0, 1.0),
            failure_reason=f"Price/IV {ratio:.2f} > {p.max_price_to_value:.2f}: margin of safety below 20%.",
        )
