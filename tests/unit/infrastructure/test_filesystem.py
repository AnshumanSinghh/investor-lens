from __future__ import annotations

import os

import pytest

from investor_lens.infrastructure.filesystem import atomic_write_text


def test_writes_and_overwrites_without_leaving_temp_files(tmp_path):
    target = tmp_path / "file.md"
    atomic_write_text(target, "first")
    atomic_write_text(target, "second")
    assert target.read_text() == "second"
    assert [p.name for p in tmp_path.iterdir()] == ["file.md"]


def test_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "a" / "b" / "out.md"
    assert atomic_write_text(target, "x") == target
    assert target.read_text() == "x"


def test_utf8_content_round_trips(tmp_path):
    target = tmp_path / "u.md"
    atomic_write_text(target, "na\u00efve \u2013 \u20ac100 \u2713")
    assert target.read_text(encoding="utf-8") == "na\u00efve \u2013 \u20ac100 \u2713"


def test_failed_replace_keeps_the_original_and_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "file.md"
    target.write_text("original")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        atomic_write_text(target, "new content")

    assert target.read_text() == "original"  # readers never see a partial file
    assert [p.name for p in tmp_path.iterdir()] == ["file.md"]  # temp file removed
