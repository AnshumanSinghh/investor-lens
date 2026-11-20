"""Joseph Piotroski: nine-signal F-score for financial strength."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from investor_lens.domain.calculators.statements import last_two
from investor_lens.domain.constants import RuleName, Statement
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import PiotroskiParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_F_SCORE = "f_score"
Signal = Optional[bool]


def _ratio(
    num: Optional[Tuple[float, float]], den: Optional[Tuple[float, float]]
) -> Optional[Tuple[float, float]]:
    """Year-by-year ratio ``(previous, current)``; ``None`` if any input is missing or a denominator is 0."""
    if num is None or den is None or den[0] == 0 or den[1] == 0:
        return None
    return num[0] / den[0], num[1] / den[1]


def _improved(pair: Optional[Tuple[float, float]], *, higher_is_better: bool = True) -> Signal:
    if pair is None:
        return None
    previous, current = pair
    return current > previous if higher_is_better else current < previous


class PiotroskiRule(FilterRule):
    """Advisory: F-score >= 7 of 9 (profitability, leverage/liquidity, operating efficiency).

    A signal without enough data is unknown, not failed: the score is a lower bound. The check passes
    when the lower bound already reaches the cut-off, fails when even the best case cannot, and is
    inconclusive in between. Simplification: ratios use year-end (not average) assets.
    """

    name = RuleName.PIOTROSKI
    investor = "Joseph Piotroski"
    gating = False

    def __init__(self, parameters: PiotroskiParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        signals = self._signals(ctx.asset)
        earned = sum(1 for v in signals.values() if v is True)
        unknown = sum(1 for v in signals.values() if v is None)
        collector.set_metrics(
            f_score=earned,
            unknown_signals=unknown,
            best_possible_f_score=earned + unknown,
            signals=dict(signals),
        )
        cutoff = self._p.min_f_score
        if unknown == len(signals):
            collector.skip(_F_SCORE, "No statement data available for any Piotroski signal.")
        elif earned >= cutoff:
            collector.record(_F_SCORE, True, score=earned / 9)
        elif earned + unknown < cutoff:
            collector.record(
                _F_SCORE, False, score=earned / 9, failure_reason=f"F-score {earned}/9 below {cutoff}."
            )
        else:
            collector.skip(
                _F_SCORE,
                f"F-score {earned}/9 with {unknown} unknown signal(s): inconclusive against {cutoff}.",
            )
        return self._finalize(collector)

    @staticmethod
    def _signals(asset: AssetSnapshot) -> Dict[str, Signal]:
        s = asset.statements
        net_income, assets = last_two(s, Statement.NET_INCOME), last_two(s, Statement.TOTAL_ASSETS)
        cfo = last_two(s, Statement.OPERATING_CASH_FLOW)
        roa = _ratio(net_income, assets)
        long_debt_ratio = _ratio(last_two(s, Statement.LONG_TERM_DEBT), assets)
        current_ratio = _ratio(
            last_two(s, Statement.CURRENT_ASSETS), last_two(s, Statement.CURRENT_LIABILITIES)
        )
        revenue = last_two(s, Statement.REVENUE)
        gross_margin = _ratio(last_two(s, Statement.GROSS_PROFIT), revenue)
        asset_turnover = _ratio(revenue, assets)
        shares = last_two(s, Statement.SHARES)

        return {
            "roa_positive": roa[1] > 0 if roa else None,
            "operating_cash_flow_positive": cfo[1] > 0 if cfo else None,
            "roa_improving": _improved(roa),
            "cash_flow_exceeds_net_income": cfo[1] > net_income[1] if cfo and net_income else None,
            "leverage_falling": _improved(long_debt_ratio, higher_is_better=False),
            "current_ratio_improving": _improved(current_ratio),
            "no_new_shares": shares[1] <= shares[0] if shares else None,
            "gross_margin_improving": _improved(gross_margin),
            "asset_turnover_improving": _improved(asset_turnover),
        }
