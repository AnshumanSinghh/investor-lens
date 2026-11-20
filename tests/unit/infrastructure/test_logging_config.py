from __future__ import annotations

import logging

import pytest

from investor_lens.infrastructure.logging_config import configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def test_level_is_applied():
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.parametrize("level", ["warning", "WARNING"])
def test_level_is_case_insensitive(level):
    configure_logging(level)
    assert logging.getLogger().level == logging.WARNING


def test_unknown_level_falls_back_to_info():
    configure_logging("LOUD")
    assert logging.getLogger().level == logging.INFO


def test_reconfiguring_replaces_handlers_instead_of_stacking_them():
    configure_logging("INFO")
    configure_logging("INFO")
    assert len(logging.getLogger().handlers) == 1


def test_file_handler_receives_records(tmp_path):
    log_file = tmp_path / "run.log"
    configure_logging("INFO", str(log_file))
    logging.getLogger("investor_lens.test").info("hello from the test")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "hello from the test" in log_file.read_text()
    assert "investor_lens.test" in log_file.read_text()


def test_unwritable_log_file_never_prevents_the_run(tmp_path, capsys):
    bad_path = tmp_path / "missing-dir" / "run.log"
    configure_logging("INFO", str(bad_path))  # must not raise
    assert "Cannot open log file" in capsys.readouterr().err
    assert len(logging.getLogger().handlers) == 1  # stderr handler still works
