"""Executable architecture rules: the dependency rule is enforced, not just documented."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "investor_lens"
PACKAGE = "investor_lens"

# layer -> first-party layers it may import (itself is always allowed)
ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "application": {"domain"},
    "config": {"domain"},
    "infrastructure": {"domain", "application", "config"},
    "bootstrap": {"domain", "application", "config", "infrastructure"},
    "cli": {"domain", "application", "config", "infrastructure", "bootstrap"},
    "__main__": {"cli"},
}


def layer_of(path: Path) -> str:
    return path.relative_to(SRC).parts[0].removesuffix(".py")


def first_party_imports(source: str) -> set[str]:
    """Top-level layer names imported from this package (``from investor_lens.domain... import``)."""
    layers: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            if parts[0] == PACKAGE and len(parts) > 1:
                layers.add(parts[1])
            elif parts == [PACKAGE]:
                layers.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == PACKAGE and len(parts) > 1:
                    layers.add(parts[1])
    return layers


def violations(layer: str, source: str) -> set[str]:
    allowed = ALLOWED[layer] | {layer}
    # ``from investor_lens import __version__`` is a package-level constant, not a layer
    return {name for name in first_party_imports(source) - allowed if name != "__version__"}


SOURCE_FILES = sorted(SRC.rglob("*.py"))


CHECKED_FILES = [p for p in SOURCE_FILES if p.parent != SRC or p.name != "__init__.py"]


def test_all_source_files_belong_to_a_known_layer():
    unknown = {layer_of(p) for p in CHECKED_FILES} - set(ALLOWED)
    assert unknown == set()


@pytest.mark.parametrize(
    "path", [p for p in SOURCE_FILES if p.parent != SRC or p.name != "__init__.py"], ids=str
)
def test_imports_point_inward_only(path):
    found = violations(layer_of(path), path.read_text(encoding="utf-8"))
    assert not found, f"{path.relative_to(SRC)} imports forbidden layer(s): {sorted(found)}"


def third_party_roots(source: str) -> set[str]:
    """Top-level names of every module imported by ``source``."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
    return roots


def test_vendor_sdk_is_confined_to_the_yfinance_adapter():
    for path in SOURCE_FILES:
        if path.name != "yfinance_gateway.py":
            roots = third_party_roots(path.read_text(encoding="utf-8"))
            assert "yfinance" not in roots, f"{path.relative_to(SRC)} imports yfinance directly"


def test_domain_has_no_io_or_vendor_dependencies():
    banned = {"requests", "yfinance", "os", "pathlib", "subprocess", "sqlite3", "socket"}
    for path in (SRC / "domain").rglob("*.py"):
        found = third_party_roots(path.read_text(encoding="utf-8")) & banned
        assert not found, f"{path.relative_to(SRC)} imports {sorted(found)}"


class TestTheCheckerItself:
    """Guards against the rule silently passing because the detector is broken."""

    def test_flags_an_inward_violation(self):
        assert violations("domain", "from investor_lens.infrastructure.filesystem import x") == {
            "infrastructure"
        }

    def test_flags_plain_imports(self):
        assert violations("application", "import investor_lens.config.settings") == {"config"}

    def test_allows_same_layer_and_inner_layers(self):
        source = "from investor_lens.domain.models import A\nfrom investor_lens.application.ports import B"
        assert violations("application", source) == set()

    def test_infrastructure_must_not_reach_the_composition_root(self):
        assert violations("infrastructure", "from investor_lens.bootstrap import build_use_case") == {
            "bootstrap"
        }
