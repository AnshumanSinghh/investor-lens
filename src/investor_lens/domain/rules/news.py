"""News: an advisory early-warning flag from recent headlines (keyword screen)."""

from __future__ import annotations

import re
from typing import List, Sequence

from investor_lens.domain.calculators.math_utils import clip
from investor_lens.domain.constants import RuleName
from investor_lens.domain.models import EvaluationContext, NewsItem, RuleResult
from investor_lens.domain.parameters import NewsParameters
from investor_lens.domain.rules.base import CheckCollector, FilterRule

_RED_FLAGS = "red_flag_headlines"


def _compile(terms: Sequence[str]) -> re.Pattern[str]:
    # Longest first so "profit warning" wins over a shorter overlapping term; word boundaries avoid
    # matching "ban" inside "banking".
    ordered = sorted({t.strip().lower() for t in terms if t.strip()}, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in ordered) + r")\b", re.IGNORECASE)


class NewsRule(FilterRule):
    """Flags tickers whose recent headlines contain risk terms (lawsuit, fraud, downgrade, probe, ...).

    Advisory and deliberately simple: keywords miss context and negation. The headlines themselves are
    included in the report so a reader (or Claude) can judge them properly. No headlines means the
    check is inconclusive, never a pass.
    """

    name = RuleName.NEWS
    investor = "News flow"
    gating = False

    def __init__(self, parameters: NewsParameters, fallback_score: float) -> None:
        super().__init__(fallback_score)
        self._p = parameters
        self._risk = _compile(parameters.risk_terms) if parameters.risk_terms else None
        self._positive = _compile(parameters.positive_terms) if parameters.positive_terms else None

    def _evaluate(self, ctx: EvaluationContext) -> RuleResult:
        collector = CheckCollector()
        news = ctx.asset.news
        collector.set_metrics(headline_count=len(news))
        if not news:
            collector.skip(_RED_FLAGS, "No headlines available; news not assessed.")
            return self._finalize(collector)

        risky = self._matches(news, self._risk)
        positive = self._matches(news, self._positive)
        collector.set_metrics(
            risk_headline_count=len(risky),
            positive_headline_count=len(positive),
            risk_headlines=[{"title": item.title, "terms": terms} for item, terms in risky],
            positive_headlines=[{"title": item.title, "terms": terms} for item, terms in positive],
        )
        limit = self._p.max_risk_headlines
        collector.record(
            _RED_FLAGS,
            passed=len(risky) <= limit,
            score=clip(1.0 - len(risky) / max(1, len(news)), 0.0, 1.0),
            failure_reason=f"{len(risky)} of {len(news)} recent headlines contain risk terms; read them.",
        )
        return self._finalize(collector)

    @staticmethod
    def _matches(news: List[NewsItem], pattern: re.Pattern[str] | None) -> list[tuple[NewsItem, list[str]]]:
        if pattern is None:
            return []
        found: list[tuple[NewsItem, list[str]]] = []
        for item in news:
            text = f"{item.title} {item.summary or ''}"
            terms = sorted({m.group(1).lower() for m in pattern.finditer(text)})
            if terms:
                found.append((item, terms))
        return found
