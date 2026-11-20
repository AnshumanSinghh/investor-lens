"""Renders the markdown envelope around the JSON payload."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List

from investor_lens.domain.constants import Metric, RuleName
from investor_lens.domain.models import AssetEvaluation, PipelineReport

_TABLE_HEADER = (
    "| Ticker | Verdict | Score | Price | Intrinsic Value | Price/IV | "
    "Z (valuation) | Price/SMA200 | Sharpe | Weight |"
)
_TABLE_RULE = "|---|---|---|---|---|---|---|---|---|---|"

_READING_GUIDE = [
    "- `verdict`: QUALIFIED (passed every gating rule), DISQUALIFIED (failed >= 1), "
    "INSUFFICIENT_DATA (a gating check could not run), DATA_UNAVAILABLE (fetch failed).",
    "- Buffett and Marks rules gate. Dalio, Graham and Lynch are advisory: they never change the verdict "
    "(Dalio also scales `suggested_weight`); read their `passed` flags and metrics as supporting evidence.",
    "- `assets[].news` holds recent headlines. The `News flow` rule only flags risk keywords; "
    "read the headlines themselves and judge their meaning, since keywords miss context and negation.",
    "- `score` is 0-1 (higher is better); fallback scores mean the calculation did not run.",
    "- `metadata.thresholds` lists every cut-off used. `metadata.limitations` lists known data caveats.",
]


def format_number(value: Any, pattern: str = "{:.2f}") -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return pattern.format(value)


class MarkdownRenderer:
    def render(self, report: PipelineReport, payload: Dict[str, Any]) -> str:
        risk_free = format_number(report.market.risk_free_rate * 100, "{:.2f}%")
        lines: List[str] = [
            "# Market Intelligence Payload",
            "",
            f"Generated (UTC): {report.generated_at.strftime('%Y-%m-%d %H:%M')} | "
            f"Risk-free: {risk_free} ({report.market.risk_free_source})",
            "",
            "## Reading guide",
            *_READING_GUIDE,
            "",
            "## Summary",
            "",
            _TABLE_HEADER,
            _TABLE_RULE,
            *[self._row(e) for e in report.evaluations],
            "",
            "## Data (JSON)",
            "",
            "```json",
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
            "```",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _row(e: AssetEvaluation) -> str:
        f = format_number
        price = e.snapshot.current_price if e.snapshot else None
        weight = None if e.suggested_weight is None else e.suggested_weight * 100
        cells = [
            e.ticker,
            e.verdict.value,
            f(e.composite_score),
            f(price),
            f(e.metric(RuleName.BUFFETT, Metric.INTRINSIC_VALUE)),
            f(e.metric(RuleName.BUFFETT, Metric.PRICE_TO_INTRINSIC_VALUE)),
            f(e.metric(RuleName.MARKS, Metric.Z_VALUATION)),
            f(e.metric(RuleName.MARKS, Metric.PRICE_TO_SMA200)),
            f(e.metric(RuleName.DALIO, Metric.SHARPE_RATIO)),
            f(weight, "{:.1f}%"),
        ]
        return "| " + " | ".join(cells) + " |"
