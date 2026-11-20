"""Rule outcomes and per-asset evaluation aggregates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, List, Optional

from investor_lens.domain.models.asset import AssetSnapshot
from investor_lens.domain.models.market import MarketContext


class Verdict(StrEnum):
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


@dataclass(frozen=True, eq=False)
class EvaluationContext:
    """Immutable input handed to every rule."""

    asset: AssetSnapshot
    market: MarketContext


@dataclass
class RuleResult:
    rule_name: str
    investor: str
    gating: bool
    passed: Optional[bool]  # None => the check could not be evaluated
    score: float  # 0..1, higher is better
    status: str  # "OK" | "FALLBACK"
    metrics: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


@dataclass
class AssetEvaluation:
    ticker: str
    verdict: Verdict
    composite_score: float
    snapshot: Optional[AssetSnapshot] = None
    rule_results: List[RuleResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggested_weight: Optional[float] = None
    avg_portfolio_correlation: Optional[float] = None
    weight_adjustments: List[str] = field(default_factory=list)

    def result_for(self, rule_name: str) -> Optional[RuleResult]:
        return next((r for r in self.rule_results if r.rule_name == rule_name), None)

    def metric(self, rule_name: str, key: str) -> Optional[Any]:
        result = self.result_for(rule_name)
        return None if result is None else result.metrics.get(key)
