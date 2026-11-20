"""``ReportWriter`` adapter producing ``market_intelligence_payload.md``."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from investor_lens.application.ports import ReportWriter
from investor_lens.domain.models import PipelineReport
from investor_lens.infrastructure.filesystem import atomic_write_text
from investor_lens.infrastructure.reporting.markdown_renderer import MarkdownRenderer
from investor_lens.infrastructure.reporting.payload_builder import PayloadBuilder


class MarkdownJsonReportWriter(ReportWriter):
    """Composes a payload builder, a renderer and an atomic file write."""

    def __init__(
        self,
        payload_builder: Optional[PayloadBuilder] = None,
        renderer: Optional[MarkdownRenderer] = None,
    ) -> None:
        self._payload_builder = payload_builder or PayloadBuilder()
        self._renderer = renderer or MarkdownRenderer()

    def write(self, report: PipelineReport, destination: Path) -> Path:
        payload = self._payload_builder.build(report)
        body = self._renderer.render(report, payload)
        return atomic_write_text(destination, body)
