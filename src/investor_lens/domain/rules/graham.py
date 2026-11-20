"""Benjamin Graham: defensive-investor value tests (price vs. earnings and book value)."""

from __future__ import annotations

from typing import Optional

from investor_lens.domain.calculators.dcf import historical_eps_growth
from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.constants import RuleName
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import GrahamParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_EARNINGS_MULTIPLE = "earnings_multiple"
_ASSET_MULTIPLE = "asset_multiple"
_EARNINGS_STABILITY = "earnings_stability"
_EARNINGS_GROWTH = "earnings_growth"


class GrahamRule(FilterRule):
    """Advisory: P/E <= 15 on 3-year average EPS, P/B <= 1.5 (or P/E x P/B <= 22.5), steady growing EPS.

    Not applied: the current-ratio and dividend-record tests (the data layer does not supply them).
    Advisory by default because Graham's absolute caps exclude most large caps; set ``gating = True``
    to make failures disqualifying.
    """

    name = RuleName.GRAHAM
    investor = "Benjamin Graham"
    gating = False

    def __init__(self, parameters: GrahamParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        pe = self._check_earnings_multiple(ctx.asset, collector)
        self._check_asset_multiple(ctx.asset, pe, collector)
        self._check_stability_and_growth(ctx.asset, collector)
        return self._finalize(collector)

    def _check_earnings_multiple(self, asset: AssetSnapshot, c: CheckCollector) -> Optional[float]:
        p = self._p
        eps = asset.eps_history.dropna().sort_index()
        if len(eps) < p.earnings_avg_years:
            c.skip(_EARNINGS_MULTIPLE, f"Fewer than {p.earnings_avg_years} years of EPS for the average.")
            return None
        average_eps = float(eps.tail(p.earnings_avg_years).mean())
        c.set_metrics(average_eps=average_eps)
        if average_eps <= 0:
            c.set_metrics(pe_3y_average=None)
            c.fail(_EARNINGS_MULTIPLE, "Non-positive average earnings: P/E undefined, fails.")
            return None
        pe = asset.current_price / average_eps
        c.set_metrics(pe_3y_average=pe)
        c.record(
            _EARNINGS_MULTIPLE,
            passed=pe <= p.max_pe,
            score=clip(1.0 - pe / (2 * p.max_pe), 0.0, 1.0),
            failure_reason=f"P/E {pe:.1f} (3y average EPS) exceeds {p.max_pe:.1f}.",
        )
        return pe

    def _check_asset_multiple(self, asset: AssetSnapshot, pe: Optional[float], c: CheckCollector) -> None:
        p = self._p
        if not asset.total_equity or not asset.shares_outstanding or asset.shares_outstanding <= 0:
            c.skip(_ASSET_MULTIPLE, "Book value or share count unavailable.")
            return
        book_per_share = asset.total_equity / asset.shares_outstanding
        c.set_metrics(book_value_per_share=book_per_share)
        if book_per_share <= 0:
            c.set_metrics(price_to_book=None)
            c.fail(_ASSET_MULTIPLE, "Non-positive book value: P/B undefined, fails.")
            return
        pb = asset.current_price / book_per_share
        c.set_metrics(price_to_book=pb)
        if pe is None:
            # Without a usable P/E only the plain P/B cap can be applied.
            passed, product = pb <= p.max_pb, None
        else:
            product = pe * pb
            passed = pb <= p.max_pb or product <= p.max_pe_times_pb
        c.set_metrics(pe_times_pb=product)
        average_eps = c.metrics.get("average_eps")
        if average_eps and average_eps > 0:
            graham_number = (p.max_pe_times_pb * average_eps * book_per_share) ** 0.5
            c.set_metrics(
                graham_number=graham_number, price_to_graham_number=asset.current_price / graham_number
            )
        c.record(
            _ASSET_MULTIPLE,
            passed=passed,
            score=clip(1.0 - pb / (2 * p.max_pb), 0.0, 1.0),
            failure_reason=f"P/B {pb:.2f} > {p.max_pb:.2f} and P/E x P/B above {p.max_pe_times_pb:.1f}.",
        )

    def _check_stability_and_growth(self, asset: AssetSnapshot, c: CheckCollector) -> None:
        p = self._p
        eps = asset.eps_history.dropna().sort_index()
        if len(eps) < p.min_eps_points:
            reason = f"Fewer than {p.min_eps_points} years of EPS."
            c.skip(_EARNINGS_STABILITY, reason)
            c.skip(_EARNINGS_GROWTH, reason)
            return
        losses = int((eps <= 0).sum())
        c.set_metrics(loss_years=losses, eps_years_observed=len(eps))
        c.record(
            _EARNINGS_STABILITY,
            passed=losses == 0,
            score=clip(1.0 - losses / len(eps), 0.0, 1.0),
            failure_reason=f"{losses} year(s) of non-positive earnings.",
        )
        growth = historical_eps_growth(eps, p.min_eps_points, len(eps))
        c.set_metrics(eps_cagr=growth)
        if growth is None:
            c.fail(_EARNINGS_GROWTH, "EPS growth undefined (non-positive end points or short history).")
            return
        c.record(
            _EARNINGS_GROWTH,
            passed=growth >= p.min_eps_cagr,
            score=clip(growth / (4 * p.min_eps_cagr), 0.0, 1.0),
            failure_reason=f"EPS CAGR {growth:.1%} below {p.min_eps_cagr:.1%}.",
        )
