"""Whole-system tests: real bootstrap wiring, real writer, real files; only the vendor is faked."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from investor_lens import bootstrap, cli
from investor_lens.domain.models import Verdict
from support.reports import SAMPLE_TICKERS, extract_json_block, sample_gateway


@pytest.fixture
def use_case(settings):
    return bootstrap.build_use_case(settings, sample_gateway())


def test_pipeline_to_file_with_real_wiring(use_case, tmp_path):
    destination = tmp_path / "market_intelligence_payload.md"
    result = use_case.execute(SAMPLE_TICKERS, destination)

    assert result.path == destination
    assert result.qualified_tickers == ("CHEAP",)

    payload = extract_json_block(destination.read_text(encoding="utf-8"))
    verdicts = {a["ticker"]: a["verdict"] for a in payload["assets"]}
    assert verdicts == {
        "CHEAP": Verdict.QUALIFIED.value,
        "PRICEY": Verdict.DISQUALIFIED.value,
        "LEVERED": Verdict.DISQUALIFIED.value,
        "NODATA": Verdict.INSUFFICIENT_DATA.value,
        "BOOM": Verdict.DATA_UNAVAILABLE.value,
    }
    assert payload["portfolio"]["suggested_weights"] == {"CHEAP": pytest.approx(1.0)}


def test_the_default_clock_stamps_the_report_with_the_current_utc_time(use_case, tmp_path):
    before = datetime.now(UTC)
    report = use_case.execute(["CHEAP"], tmp_path / "p.md").report
    assert before - timedelta(seconds=1) <= report.generated_at <= datetime.now(UTC) + timedelta(seconds=1)
    assert report.generated_at.tzinfo is not None


def test_market_data_outages_still_produce_a_complete_payload(settings, tmp_path):
    gateway = sample_gateway(risk_free_fails=True, benchmark_fails=True)
    destination = tmp_path / "p.md"
    bootstrap.build_use_case(settings, gateway).execute(["CHEAP", "BOOM"], destination)

    meta = extract_json_block(destination.read_text(encoding="utf-8"))["metadata"]
    assert meta["risk_free_source"] == "fallback_constant"
    assert meta["risk_free_rate"] == settings.ingestion.risk_free_fallback
    assert len(meta["market_data_notes"]) == 2


def test_cli_main_writes_the_payload(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(cli, "build_use_case", lambda s: bootstrap.build_use_case(settings, sample_gateway()))
    destination = tmp_path / "cli.md"

    code = cli.main(["--tickers", "CHEAP,PRICEY", "--output", str(destination), "--log-level", "ERROR"])

    assert code == cli.EXIT_OK
    payload = extract_json_block(destination.read_text(encoding="utf-8"))
    assert [a["ticker"] for a in payload["assets"]] == ["CHEAP", "PRICEY"]


def test_python_dash_m_entry_point_delegates_to_the_cli(monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv=None: 7)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("investor_lens", run_name="__main__")
    assert excinfo.value.code == 7


def test_the_module_is_runnable_as_a_subprocess():
    src = Path(__file__).resolve().parents[2] / "src"
    env = {**os.environ, "PYTHONPATH": str(src)}
    done = subprocess.run(
        [sys.executable, "-m", "investor_lens", "--help"], capture_output=True, text=True, timeout=60, env=env
    )
    assert done.returncode == 0, done.stderr
    assert "investor-lens" in done.stdout


def test_the_cli_runs_the_whole_pipeline_from_local_files(tmp_path, monkeypatch):
    from support.data_dir import make_data_dir

    data = make_data_dir(tmp_path / "data", tickers=("AAA", "BBB"))
    (data / "AAA.news.json").write_text(
        '[{"title": "Regulator opens probe", "publisher": "Wire", "published_at": "2026-11-18T09:30:00Z"},'
        ' {"title": "Analyst downgrade after lawsuit"}]'
    )
    destination = tmp_path / "from_files.md"
    for name in ("LENS_TICKERS", "LENS_DATA_SOURCE", "LENS_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)

    code = cli.main(
        [
            "--source",
            "files",
            "--data-dir",
            str(data),
            "--tickers",
            "AAA,BBB,MISSING",
            "--output",
            str(destination),
        ]
    )

    assert code == cli.EXIT_OK
    payload = extract_json_block(destination.read_text(encoding="utf-8"))
    assert payload["metadata"]["data_source"].startswith("files:")
    assert payload["metadata"]["risk_free_source"] == "live"
    assert payload["metadata"]["risk_free_rate"] == pytest.approx(0.043)
    by_ticker = {a["ticker"]: a for a in payload["assets"]}
    assert by_ticker["MISSING"]["verdict"] == Verdict.DATA_UNAVAILABLE.value
    assert by_ticker["AAA"]["verdict"] != Verdict.DATA_UNAVAILABLE.value
    investors = [r["investor"] for r in by_ticker["AAA"]["rules"]]
    assert investors == [
        "Warren Buffett",
        "Howard Marks",
        "Ray Dalio",
        "Benjamin Graham",
        "Peter Lynch",
        "Joel Greenblatt",
        "Joseph Piotroski",
        "News flow",
    ]
    assert [n["title"] for n in by_ticker["AAA"]["news"]] == [
        "Regulator opens probe",
        "Analyst downgrade after lawsuit",
    ]
    news_rule = by_ticker["AAA"]["rules"][-1]
    assert news_rule["passed"] is False and news_rule["gating"] is False
    assert by_ticker["AAA"]["verdict"] != Verdict.DISQUALIFIED.value or news_rule["gating"] is False


def test_the_shipped_example_data_runs_and_exercises_every_lens(tmp_path, monkeypatch):
    examples = Path(__file__).resolve().parents[2] / "examples" / "data"
    for name in ("LENS_TICKERS", "LENS_DATA_SOURCE", "LENS_DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    destination = tmp_path / "demo.md"

    code = cli.main(
        [
            "--source",
            "files",
            "--data-dir",
            str(examples),
            "--tickers",
            "DEMOA,DEMOB",
            "--output",
            str(destination),
        ]
    )

    assert code == cli.EXIT_OK
    payload = extract_json_block(destination.read_text(encoding="utf-8"))
    for asset in payload["assets"]:
        assert asset["verdict"] in {v.value for v in Verdict}
        assert asset["verdict"] != Verdict.DATA_UNAVAILABLE.value
        assert len(asset["rules"]) == 8
        statuses = {r["investor"]: r["status"] for r in asset["rules"]}
        assert statuses["Joel Greenblatt"] == "OK" and statuses["Joseph Piotroski"] == "OK"
    demob = next(a for a in payload["assets"] if a["ticker"] == "DEMOB")
    assert len(demob["news"]) == 3
