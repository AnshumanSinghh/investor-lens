"""Peter Lynch: growth at a reasonable price (PEG), sane growth band and modest debt."""

from __future__ import annotations

from investor_lens.domain.calculators.dcf import historical_eps_growth
from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.constants import RuleName
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import LynchParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_PEG = "peg"
_GROWTH_BAND = "growth_band"
_LEVERAGE = "leverage"


class LynchRule(FilterRule):
    """Advisory: PEG <= 1, EPS growth within 10-50%, debt/equity <= 0.80.

    PEG = (P/E on the latest EPS) / (EPS CAGR in percent). Advisory by default; set ``gating = True``
    to make failures disqualifying.
    """

    name = RuleName.LYNCH
    investor = "Peter Lynch"
    gating = False

    def __init__(self, parameters: LynchParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        growth = self._check_growth_band(ctx.asset, collector)
        self._check_peg(ctx.asset, growth, collector)
        self._check_leverage(ctx.asset, collector)
        return self._finalize(collector)

    def _check_growth_band(self, asset: AssetSnapshot, c: CheckCollector) -> float | None:
        p = self._p
        growth = historical_eps_growth(asset.eps_history, p.eps_growth_min_points, p.eps_growth_max_points)
        c.set_metrics(eps_growth=growth)
        if growth is None:
            c.skip(_GROWTH_BAND, "EPS growth could not be estimated (short or non-positive history).")
            return None
        in_band = p.min_growth <= growth <= p.max_growth
        centre = (p.min_growth + p.max_growth) / 2
        c.record(
            _GROWTH_BAND,
            passed=in_band,
            score=clip(1.0 - abs(growth - centre) / (p.max_growth - centre), 0.0, 1.0),
            failure_reason=f"EPS growth {growth:.1%} outside {p.min_growth:.0%}-{p.max_growth:.0%}.",
        )
        return growth

    def _check_peg(self, asset: AssetSnapshot, growth: float | None, c: CheckCollector) -> None:
        p = self._p
        eps = asset.eps_history.dropna().sort_index()
        if growth is None or eps.empty:
            c.skip(_PEG, "PEG needs both a latest EPS and an EPS growth estimate.")
            return
        latest_eps = float(eps.iloc[-1])
        if latest_eps <= 0 or growth <= 0:
            c.set_metrics(pe=None, peg=None)
            c.fail(_PEG, "Non-positive earnings or growth: PEG undefined, fails.")
            return
        pe = asset.current_price / latest_eps
        peg = pe / (growth * 100.0)
        c.set_metrics(pe=pe, peg=peg)
        c.record(
            _PEG,
            passed=peg <= p.max_peg,
            score=clip((2.0 * p.max_peg - peg) / (1.5 * p.max_peg), 0.0, 1.0),
            failure_reason=f"PEG {peg:.2f} exceeds {p.max_peg:.2f}.",
        )

    def _check_leverage(self, asset: AssetSnapshot, c: CheckCollector) -> None:
        p = self._p
        if asset.total_debt is None or asset.total_equity is None:
            c.skip(_LEVERAGE, "Total debt or total equity unavailable.")
            return
        if asset.total_equity <= 0:
            c.fail(_LEVERAGE, "Non-positive shareholder equity: leverage undefined, fails.")
            return
        leverage = asset.total_debt / asset.total_equity
        c.set_metrics(debt_to_equity=leverage)
        c.record(
            _LEVERAGE,
            passed=leverage <= p.max_leverage,
            score=clip(1.0 - leverage / p.max_leverage, 0.0, 1.0),
            failure_reason=f"Debt/equity {leverage:.2f} exceeds {p.max_leverage:.2f}.",
        )
