"""Installed entry-point metadata is passive; selected plugins retain the BYOE gates."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.evaluators import base, plugins
from sloplab.evaluators.external import ExternalEvaluatorError, resolve_evaluators
from sloplab.reporting.writers import read_run_jsonl
from tests._byoe_helpers import EVALUATOR_SOURCE, evaluator_file, tiny_suite


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name, module in tuple(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_relative_to(tmp_path):
            sys.modules.pop(name, None)


def package(
    root: Path,
    *,
    distribution: str = "toy_plugin",
    name: str = "byoe-test",
    module: str = "toy_evaluator",
    attribute: str = "make",
    extra: str = "",
) -> Path:
    info = root / f"{distribution}-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {distribution}\nVersion: 1.0\n")
    (info / "entry_points.txt").write_text(f"[sloplab.evaluators]\n{name} = {module}:{attribute}\n")
    source = root / f"{module}.py"
    source.write_text(EVALUATOR_SOURCE + extra)
    return source


def test_discovery_and_cli_list_metadata_without_importing_target(installed: Path) -> None:
    package(installed, extra="raise RuntimeError('must not import during discovery')\n")
    result = CliRunner().invoke(cli, ["evaluators"])
    assert result.exit_code == 0, result.output
    listing = json.loads(result.output)
    found = next(p for p in listing["plugins"] if p["name"] == "byoe-test")
    assert found == {
        "name": "byoe-test",
        "target": "toy_evaluator:make",
        "distribution": "toy_plugin",
        "distribution_version": "1.0",
        "name_conflict": False,
    }
    assert "toy_evaluator" not in sys.modules
    assert "rules-baseline" in {p["name"] for p in listing["builtins"]}


def test_builtin_selection_never_reads_plugin_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(**kwargs: object) -> None:
        pytest.fail("built-in-only selection inspected plugin metadata")

    monkeypatch.setattr(metadata, "entry_points", unexpected)
    assert resolve_evaluators(["rules-baseline"])[0].name == "rules-baseline"


def test_mixed_benchmark_and_plugin_only_evaluate(installed: Path) -> None:
    package(installed)
    suite = tiny_suite(installed)
    direct = evaluator_file(installed / "direct", "evaluator.name = 'direct-test'\n")
    out = installed / "run"
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(suite),
            "--evaluator",
            "rules-baseline",
            "--evaluator-module",
            f"{direct}:evaluator",
            "--evaluator-plugin",
            "byoe-test",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    metadata, records = read_run_jsonl(out / "run.jsonl")
    assert metadata is not None
    assert {r.evaluator_name for r in records} == {"rules-baseline", "direct-test", "byoe-test"}
    assert len(records) == 12
    again = installed / "evaluated"
    result = CliRunner().invoke(
        cli,
        [
            "evaluate",
            str(out),
            "--evaluator-plugin",
            "byoe-test",
            "--out",
            str(again),
        ],
    )
    assert result.exit_code == 0, result.output
    _, records = read_run_jsonl(again / "run.jsonl")
    assert len(records) == 4 and all(r.evaluator_name == "byoe-test" for r in records)
    assert "byoe-test" not in base.list_evaluators()


def test_unknown_plugin_fails_before_creating_output(installed: Path) -> None:
    suite = tiny_suite(installed)
    out = installed / "absent"
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(suite),
            "--evaluator-plugin",
            "missing-plugin",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code != 0 and "not installed" in result.output
    assert not out.exists()


def test_duplicate_distribution_registration_is_ambiguous(installed: Path) -> None:
    package(installed, distribution="first_package")
    package(installed, distribution="second_package")
    rows = [r for r in plugins.list_plugins() if r["name"] == "byoe-test"]
    assert len(rows) == 2 and all(r["name_conflict"] for r in rows)
    with pytest.raises(ExternalEvaluatorError, match="Multiple installed"):
        resolve_evaluators([], plugins=["byoe-test"])
    assert "toy_evaluator" not in sys.modules


@pytest.mark.parametrize("selection", ["duplicate", "builtin", "module"])
def test_selection_collisions_are_rejected(installed: Path, selection: str) -> None:
    name = "rules-baseline" if selection == "builtin" else "byoe-test"
    package(installed, name=name)
    if selection == "duplicate":
        with pytest.raises(ExternalEvaluatorError, match="Duplicate"):
            resolve_evaluators([], plugins=[name, name])
    elif selection == "builtin":
        with pytest.raises(ExternalEvaluatorError, match="collides"):
            resolve_evaluators([], plugins=[name])
    else:
        direct = evaluator_file(installed / "direct")
        with pytest.raises(ExternalEvaluatorError, match="collision"):
            resolve_evaluators([], [f"{direct}:make"], [name])
    assert "toy_evaluator" not in sys.modules


@pytest.mark.parametrize(
    "extra,match",
    [
        ("evaluator.name = 'wrong-name'\n", "entry-point name"),
        ("evaluator.requires_labels = True\n", "ground-truth labels"),
        ("from sloplab.evaluators import base\nbase.register_evaluator(evaluator)\n", "registry"),
    ],
)
def test_rejected_plugin_restores_registry_and_does_not_leave_import_cache(
    installed: Path, extra: str, match: str
) -> None:
    package(installed, attribute="evaluator", extra=extra)
    before = dict(base._EVALUATOR_REGISTRY)
    for _ in range(2):
        with pytest.raises(ExternalEvaluatorError, match=match):
            resolve_evaluators([], plugins=["byoe-test"])
        assert before == base._EVALUATOR_REGISTRY
        assert "toy_evaluator" not in sys.modules


def test_factory_failure_does_not_expose_exception_text(installed: Path) -> None:
    package(installed, extra="def make(): raise RuntimeError('SECRET_PLUGIN_TOKEN')\n")
    suite = tiny_suite(installed)
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(suite),
            "--evaluator-plugin",
            "byoe-test",
            "--out",
            str(installed / "run"),
        ],
    )
    assert result.exit_code != 0 and "factory" in result.output
    assert "SECRET_PLUGIN_TOKEN" not in result.output


def test_nested_attribute_target_is_supported(installed: Path) -> None:
    package(
        installed,
        attribute="factories.make",
        extra="""
class factories:
    make = staticmethod(make)
""",
    )
    assert resolve_evaluators([], plugins=["byoe-test"])[0].name == "byoe-test"


def test_importable_module_named_py_is_not_treated_as_a_source_file(installed: Path) -> None:
    package(installed, module="plugin_package.py")
    directory = installed / "plugin_package"
    directory.mkdir()
    (directory / "__init__.py").write_text("")
    (directory / "py.py").write_text(EVALUATOR_SOURCE)
    # Metadata points at plugin_package.py, an importable module inside a package.
    # The similarly named standalone file must never be used for this entry point.
    (installed / "plugin_package.py.py").write_text("raise RuntimeError('wrong target')\n")
    assert resolve_evaluators([], plugins=["byoe-test"])[0].name == "byoe-test"
