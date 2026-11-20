from __future__ import annotations

from pathlib import Path

import pytest

from investor_lens import cli
from investor_lens.config import load_settings


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch):
    for name in ("LENS_TICKERS", "LENS_OUTPUT_PATH", "LENS_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)


class StubUseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[tuple[str, ...], Path]] = []

    def execute(self, tickers, destination):
        if self.error:
            raise self.error
        self.calls.append((tuple(tickers), destination))


def install(monkeypatch, use_case: StubUseCase) -> StubUseCase:
    monkeypatch.setattr(cli, "build_use_case", lambda settings: use_case)
    return use_case


class TestOverrides:
    def test_flags_beat_environment(self, monkeypatch):
        monkeypatch.setenv("LENS_TICKERS", "KO")
        args = cli.build_parser().parse_args(
            ["--tickers", "msft,aapl", "--output", "x.md", "--log-level", "warning"]
        )
        settings = cli.apply_overrides(load_settings(), args)
        assert settings.tickers == ("MSFT", "AAPL")
        assert settings.output_path == Path("x.md")
        assert settings.logging.level == "WARNING"

    def test_environment_is_used_when_no_flags_are_given(self, monkeypatch):
        monkeypatch.setenv("LENS_TICKERS", "ko, pep")
        settings = cli.apply_overrides(load_settings(), cli.build_parser().parse_args([]))
        assert settings.tickers == ("KO", "PEP")

    def test_duplicate_tickers_in_the_flag_are_collapsed(self):
        args = cli.build_parser().parse_args(["--tickers", "ko,KO, ko"])
        assert cli.apply_overrides(load_settings(), args).tickers == ("KO",)

    def test_source_and_data_dir_flags_override_the_environment(self, monkeypatch):
        monkeypatch.setenv("LENS_DATA_SOURCE", "yfinance")
        args = cli.build_parser().parse_args(["--source", "FILES", "--data-dir", "my/data"])
        ingestion = cli.apply_overrides(load_settings(), args).ingestion
        assert (ingestion.data_source, ingestion.data_dir) == ("files", Path("my/data"))

    def test_market_reference_flags(self):
        args = cli.build_parser().parse_args(["--benchmark", "^NSEI", "--risk-free-ticker", "None"])
        ingestion = cli.apply_overrides(load_settings(), args).ingestion
        assert (ingestion.benchmark_ticker, ingestion.risk_free_ticker) == ("^NSEI", "")

    def test_a_named_risk_free_ticker_is_kept(self):
        args = cli.build_parser().parse_args(["--risk-free-ticker", " IN10Y "])
        assert cli.apply_overrides(load_settings(), args).ingestion.risk_free_ticker == "IN10Y"


class TestMain:
    def test_a_successful_run_returns_ok_and_passes_settings_to_the_use_case(self, monkeypatch, tmp_path):
        use_case = install(monkeypatch, StubUseCase())
        code = cli.main(["--tickers", "KO", "--output", str(tmp_path / "p.md")])
        assert code == cli.EXIT_OK
        assert use_case.calls == [(("KO",), tmp_path / "p.md")]

    def test_a_missing_dependency_has_its_own_exit_code_and_an_install_hint(self, monkeypatch, capsys):
        def boom(_settings):
            raise ImportError("yfinance")

        monkeypatch.setattr(cli, "build_use_case", boom)
        assert cli.main(["--tickers", "KO"]) == cli.EXIT_MISSING_DEPENDENCY
        assert "pip install" in capsys.readouterr().err

    def test_a_runtime_failure_is_logged_and_returns_a_nonzero_code(self, monkeypatch, capsys):
        install(monkeypatch, StubUseCase(RuntimeError("disk full")))
        assert cli.main(["--tickers", "KO"]) == cli.EXIT_RUNTIME_ERROR
        assert "disk full" in capsys.readouterr().err

    def test_exit_codes_are_distinct(self):
        assert len({cli.EXIT_OK, cli.EXIT_RUNTIME_ERROR, cli.EXIT_MISSING_DEPENDENCY}) == 3

    def test_help_exits_cleanly(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--help"])
        assert excinfo.value.code == 0
        assert "--tickers" in capsys.readouterr().out
