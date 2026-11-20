from __future__ import annotations

from pathlib import Path

from investor_lens.application.ports import ReportWriter
from investor_lens.application.use_case import GenerateMarketIntelligence
from investor_lens.domain.models import PipelineReport
from support.builders import make_snapshot
from support.fakes import FakeGateway
from support.pipelines import make_pipeline


class RecordingWriter(ReportWriter):
    def __init__(self) -> None:
        self.calls: list[tuple[PipelineReport, Path]] = []

    def write(self, report: PipelineReport, destination: Path) -> Path:
        self.calls.append((report, destination))
        return destination


def build(tickers_to_data: dict) -> tuple[GenerateMarketIntelligence, RecordingWriter]:
    writer = RecordingWriter()
    return GenerateMarketIntelligence(make_pipeline(FakeGateway(tickers_to_data)), writer), writer


def test_runs_the_pipeline_and_hands_the_report_to_the_writer(tmp_path):
    use_case, writer = build({"CHEAP": make_snapshot("CHEAP", free_cash_flow=8e9)})
    destination = tmp_path / "payload.md"

    result = use_case.execute(["CHEAP"], destination)

    assert result.path == destination
    assert writer.calls == [(result.report, destination)]
    assert [e.ticker for e in result.report.evaluations] == ["CHEAP"]


def test_reports_which_tickers_qualified(tmp_path):
    use_case, _ = build(
        {
            "CHEAP": make_snapshot("CHEAP", free_cash_flow=8e9),
            "PRICEY": make_snapshot("PRICEY", free_cash_flow=1e9),
        }
    )
    result = use_case.execute(["PRICEY", "CHEAP", "MISSING"], tmp_path / "p.md")
    assert result.qualified_tickers == ("CHEAP",)


def test_no_qualified_tickers_is_a_normal_outcome(tmp_path):
    use_case, writer = build({})
    result = use_case.execute(["NOPE"], tmp_path / "p.md")
    assert result.qualified_tickers == ()
    assert len(writer.calls) == 1  # an all-failed run still produces a (diagnostic) payload
