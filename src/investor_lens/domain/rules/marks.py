"""Howard Marks: valuation mean reversion and trend over-extension."""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.calculators.valuation import build_valuation_multiples, latest_sma, z_score
from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import AssetSnapshot, EvaluationContext, RuleResult
from investor_lens.domain.parameters import MarksParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_VALUATION_Z = "valuation_z"
_SMA_EXTENSION = "sma_extension"


class MarksRule(FilterRule):
    """Disqualify if Z_Valuation > +1.5 or Price > 1.25 x SMA200."""

    name = RuleName.MARKS
    investor = "Howard Marks"
    gating = True

    def __init__(self, parameters: MarksParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        self._check_valuation(ctx.asset, collector)
        self._check_trend(ctx.asset, collector)
        return self._finalize(collector)

    def _check_valuation(self, asset: AssetSnapshot, c: CheckCollector) -> None:
        p = self._p
        multiples = build_valuation_multiples(
            asset.price_close,
            asset.eps_history,
            asset.equity_history,
            asset.shares_history,
            asset.shares_outstanding,
            p.fundamentals_lag_days,
            p.valuation_window_years,
        )
        z_by_multiple = self._multiple_z_scores(multiples, c)
        c.set_metrics(z_pe=z_by_multiple["pe"], z_pb=z_by_multiple["pb"])

        z_valuation, basis = z_by_multiple["pe"], "P/E"
        if z_valuation is None and z_by_multiple["pb"] is not None:
            z_valuation, basis = z_by_multiple["pb"], "P/B (P/E unavailable)"
        c.set_metrics(
            **{Metric.Z_VALUATION: z_valuation},
            z_valuation_basis=basis if z_valuation is not None else None,
        )

        if z_valuation is None:
            c.skip(_VALUATION_Z, "Not enough valuation history to compute Z-score.")
            return
        c.record(
            _VALUATION_Z,
            passed=z_valuation <= p.max_valuation_z,
            score=clip((p.max_valuation_z - z_valuation) / (2 * p.max_valuation_z), 0.0, 1.0),
            failure_reason=(
                f"Z_valuation {z_valuation:.2f} > {p.max_valuation_z:.2f}: euphoria-stage valuation."
            ),
        )

    def _multiple_z_scores(self, multiples: pd.DataFrame, c: CheckCollector) -> Dict[str, Optional[float]]:
        z_by_multiple: Dict[str, Optional[float]] = {"pe": None, "pb": None}
        if multiples.empty:
            return z_by_multiple
        for column in ("pe", "pb"):
            series = multiples[column]
            current = series.iloc[-1]
            current_value = float(current) if pd.notna(current) else None
            history = series.iloc[:-1]
            c.set_metrics(
                **{
                    f"current_{column}": current_value,
                    f"mean_{column}_history": float(history.mean()) if history.notna().any() else None,
                    f"std_{column}_history": float(history.std(ddof=1))
                    if history.notna().sum() > 1
                    else None,
                    f"{column}_observations": int(history.notna().sum()),
                }
            )
            z_by_multiple[column] = z_score(history, current_value, self._p.min_valuation_obs)
        return z_by_multiple

    def _check_trend(self, asset: AssetSnapshot, c: CheckCollector) -> None:
        p = self._p
        sma = latest_sma(asset.price_close, p.sma_window)
        if sma is None:
            c.skip(_SMA_EXTENSION, f"Fewer than {p.sma_window} price observations for SMA{p.sma_window}.")
            return
        ratio = asset.current_price / sma
        c.set_metrics(sma_200=sma, **{Metric.PRICE_TO_SMA200: ratio})
        extension = max(0.0, ratio - 1.0) / (p.max_sma_extension - 1.0)
        c.record(
            _SMA_EXTENSION,
            passed=ratio <= p.max_sma_extension,
            score=clip(1.0 - extension, 0.0, 1.0),
            failure_reason=f"Price is {ratio:.2f}x SMA200 (limit {p.max_sma_extension:.2f}x).",
        )
