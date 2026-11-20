"""Rule abstractions.

* ``FilterRule`` is a Template Method: subclasses implement ``_evaluate`` while the
  base class guarantees graceful failure (log, fallback score, never raise).
* ``CheckCollector`` is a small Builder that accumulates checks, scores, metrics
  and reasons so rules stay declarative.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List, Optional

import numpy as np

from investor_lens.domain.models import EvaluationContext, RuleResult

LOGGER = logging.getLogger(__name__)


def combine_checks(checks: Dict[str, Optional[bool]]) -> Optional[bool]:
    """Any ``False`` -> ``False``; else any ``None`` -> ``None``; else ``True``."""
    values = list(checks.values())
    if any(value is False for value in values):
        return False
    if any(value is None for value in values):
        return None
    return True


class CheckCollector:
    """Accumulates the outcome of the individual checks inside one rule."""

    def __init__(self) -> None:
        self.metrics: Dict[str, Any] = {}
        self.reasons: List[str] = []
        self._checks: Dict[str, Optional[bool]] = {}
        self._scores: List[float] = []

    def set_metrics(self, **values: Any) -> None:
        self.metrics.update(values)

    def skip(self, name: str, reason: str) -> None:
        """The check could not be computed (outcome unknown)."""
        self._checks[name] = None
        self.reasons.append(reason)

    def fail(self, name: str, reason: str) -> None:
        """Hard failure without a meaningful score."""
        self._checks[name] = False
        self.reasons.append(reason)

    def record(self, name: str, passed: bool, score: float, failure_reason: Optional[str] = None) -> None:
        """A computed check with its 0..1 quality score."""
        self._checks[name] = passed
        self._scores.append(score)
        if not passed and failure_reason:
            self.reasons.append(failure_reason)

    @property
    def checks(self) -> Dict[str, Optional[bool]]:
        return dict(self._checks)

    @property
    def passed(self) -> Optional[bool]:
        return combine_checks(self._checks)

    @property
    def has_scores(self) -> bool:
        return bool(self._scores)

    def score(self, fallback: float) -> float:
        return float(np.mean(self._scores)) if self._scores else fallback


class FilterRule(ABC):
    """Base class for every investor rule. Add a rule by subclassing; no pipeline change."""

    name: ClassVar[str] = "abstract_rule"
    investor: ClassVar[str] = "n/a"
    gating: ClassVar[bool] = True

    def __init__(self, fallback_score: float) -> None:
        self._fallback_score = fallback_score

    def evaluate(self, ctx: EvaluationContext) -> RuleResult:
        """Run the rule; any exception becomes a ``FALLBACK`` result."""
        try:
            return self._evaluate(ctx)
        except Exception as exc:
            LOGGER.exception("[%s] rule %s failed", ctx.asset.ticker, self.name)
            return self._fallback([f"Calculation failed: {exc!r}"])

    @abstractmethod
    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        """Compute the result; may raise (handled by ``evaluate``)."""

    def _finalize(self, collector: CheckCollector) -> RuleResult:
        collector.metrics["checks"] = collector.checks
        return RuleResult(
            rule_name=self.name,
            investor=self.investor,
            gating=self.gating,
            passed=collector.passed,
            score=collector.score(self._fallback_score),
            status="OK" if collector.has_scores else "FALLBACK",
            metrics=collector.metrics,
            reasons=collector.reasons,
        )

    def _fallback(self, reasons: List[str]) -> RuleResult:
        return RuleResult(
            rule_name=self.name,
            investor=self.investor,
            gating=self.gating,
            passed=None,
            score=self._fallback_score,
            status="FALLBACK",
            metrics={},
            reasons=reasons,
        )
