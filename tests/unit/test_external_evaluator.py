"""Trusted-local loading validates the existing contract without registry writes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from sloplab.evaluators import base
from sloplab.evaluators.external import (
    ExternalEvaluatorError,
    load_external_evaluator,
    resolve_evaluators,
)
from sloplab.scoring.harness import run_case
from tests._byoe_helpers import evaluator_file
from tests.regression.test_evaluator_isolation import _direct_cases


@pytest.mark.parametrize("attribute", ["evaluator", "make", "Example"])
def test_file_object_factory_and_class(tmp_path: Path, attribute: str) -> None:
    before = dict(base._EVALUATOR_REGISTRY)
    evaluator = load_external_evaluator(f"{evaluator_file(tmp_path)}:{attribute}")
    assert evaluator.name == "byoe-test" and evaluator.version == "1.2"
    result = run_case(evaluator, _direct_cases()[0])
    assert result.evaluator_name == "byoe-test"
    assert before == base._EVALUATOR_REGISTRY


@pytest.mark.parametrize("attribute", ["evaluator", "make"])
def test_importable_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attribute: str) -> None:
    module = evaluator_file(tmp_path)
    module.rename(tmp_path / "byoe_import_test.py")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("byoe_import_test", None)
    try:
        evaluator = load_external_evaluator(f"byoe_import_test:{attribute}")
        assert run_case(evaluator, _direct_cases()[0]).evaluator_name == "byoe-test"
    finally:
        sys.modules.pop("byoe_import_test", None)


@pytest.mark.parametrize("spec", ["", "module", "file.py", "module:", ":make", "module:a.b"])
def test_missing_attribute_spec(spec: str) -> None:
    with pytest.raises(ExternalEvaluatorError, match=":ATTR"):
        load_external_evaluator(spec)


def test_missing_file_and_module(tmp_path: Path) -> None:
    with pytest.raises(ExternalEvaluatorError, match="file not found"):
        load_external_evaluator(f"{tmp_path / 'missing.py'}:make")
    with pytest.raises(ExternalEvaluatorError, match="Cannot import evaluator module"):
        load_external_evaluator("sloplab_nonexistent_package:make")


def test_attribute_missing(tmp_path: Path) -> None:
    with pytest.raises(ExternalEvaluatorError, match="attribute 'missing'"):
        load_external_evaluator(f"{evaluator_file(tmp_path)}:missing")


@pytest.mark.parametrize(
    "extra, message",
    [
        ("def make(required): return Example()\n", "factory 'make' failed"),
        ("def make(): raise RuntimeError('SECRET_FACTORY')\n", "factory 'make' failed"),
        ("def make(): return None\n", "name must"),
        ("def make(): return {}\n", "name must"),
        ("evaluator.name = ''\nmake = lambda: evaluator\n", "name must"),
        ("del evaluator.name\nExample.name = None\nmake = lambda: evaluator\n", "name must"),
        ("evaluator.name = 17\nmake = lambda: evaluator\n", "name must"),
        ("evaluator.name = ' padded '\nmake = lambda: evaluator\n", "name must"),
        ("evaluator.version = ''\nmake = lambda: evaluator\n", "version must"),
        ("evaluator.version = None\nmake = lambda: evaluator\n", "version must"),
        ("evaluator.evaluate = False\nmake = lambda: evaluator\n", "evaluate must be callable"),
        (
            "evaluator.evaluate = lambda: None\nmake = lambda: evaluator\n",
            "accept \\(report, context\\)",
        ),
        ("evaluator.requires_labels = True\nmake = lambda: evaluator\n", "ground-truth labels"),
        ("evaluator.requires_labels = 'yes'\nmake = lambda: evaluator\n", "ground-truth labels"),
    ],
)
def test_actionable_validation(tmp_path: Path, extra: str, message: str) -> None:
    with pytest.raises(ExternalEvaluatorError, match=message) as caught:
        load_external_evaluator(f"{evaluator_file(tmp_path, extra)}:make")
    assert "SECRET_FACTORY" not in str(caught.value)


@pytest.mark.parametrize("stage", ["import", "factory"])
@pytest.mark.parametrize("operation", ["register", "direct", "rebind"])
def test_registry_mutation_is_rejected_and_restored(
    tmp_path: Path, stage: str, operation: str
) -> None:
    registry = base._EVALUATOR_REGISTRY
    before = dict(registry)
    mutations = {
        "register": "base.register_evaluator(evaluator)",
        "direct": "base._EVALUATOR_REGISTRY['rules-baseline'] = evaluator",
        "rebind": "base._EVALUATOR_REGISTRY = {'rogue': evaluator}",
    }
    extra = "\nfrom sloplab.evaluators import base\n"
    if stage == "import":
        extra += mutations[operation] + "\n"
    else:
        extra += f"def make():\n    {mutations[operation]}\n    return evaluator\n"
    with pytest.raises(ExternalEvaluatorError, match="registry"):
        load_external_evaluator(f"{evaluator_file(tmp_path, extra)}:make")
    assert base._EVALUATOR_REGISTRY is registry
    assert registry == before
    assert all(registry[name] is instance for name, instance in before.items())


def test_registry_restored_on_failed_import(tmp_path: Path) -> None:
    before = dict(base._EVALUATOR_REGISTRY)
    file = evaluator_file(
        tmp_path,
        "\nfrom sloplab.evaluators import base\n"
        "base.register_evaluator(evaluator)\nraise RuntimeError('SECRET_IMPORT')\n",
    )
    with pytest.raises(ExternalEvaluatorError) as caught:
        load_external_evaluator(f"{file}:make")
    assert "SECRET_IMPORT" not in str(caught.value)
    assert before == base._EVALUATOR_REGISTRY


@pytest.mark.parametrize("selected", [(), ("rules-baseline",)])
def test_builtin_name_collision_even_when_unselected(
    tmp_path: Path, selected: tuple[str, ...]
) -> None:
    file = evaluator_file(tmp_path, "evaluator.name = 'rules-baseline'\n")
    with pytest.raises(ExternalEvaluatorError, match="collision"):
        resolve_evaluators(selected, [f"{file}:evaluator"])


def test_duplicate_specs_and_duplicate_builtins(tmp_path: Path) -> None:
    file = evaluator_file(tmp_path)
    with pytest.raises(ExternalEvaluatorError, match="collision"):
        resolve_evaluators([], [f"{file}:make", f"{file}:evaluator"])
    with pytest.raises(ExternalEvaluatorError, match="Duplicate"):
        resolve_evaluators(["rules-baseline", "rules-baseline"])
    with pytest.raises(ExternalEvaluatorError, match="at least one"):
        resolve_evaluators([], [])
    with pytest.raises(ExternalEvaluatorError, match="unknown evaluator"):
        resolve_evaluators(["not-registered"])


def test_two_external_names_resolve_with_builtin(tmp_path: Path) -> None:
    first = evaluator_file(tmp_path / "a")
    second = evaluator_file(tmp_path / "b", "evaluator.name = 'second'\n")
    evaluators = resolve_evaluators(["rules-baseline"], [f"{first}:make", f"{second}:evaluator"])
    assert [ev.name for ev in evaluators] == ["rules-baseline", "byoe-test", "second"]


@pytest.mark.parametrize(
    "change, message",
    [
        ("evaluator.evaluate = lambda r, c: {}", "return EvaluationResult"),
        ("evaluator.name = 'changed'", "must match"),
        ("evaluator.requires_labels = True", "ground-truth labels"),
    ],
)
def test_execution_contract_and_capability_rechecked(
    tmp_path: Path, change: str, message: str
) -> None:
    file = evaluator_file(tmp_path)
    ev = load_external_evaluator(f"{file}:evaluator")
    # Mutation by the evaluator's own module after initial resolution.
    module = next(
        m for m in list(sys.modules.values()) if getattr(m, "__file__", None) == str(file)
    )
    exec(change, vars(module))
    with pytest.raises(ExternalEvaluatorError, match=message):
        run_case(ev, _direct_cases()[0])


def test_different_external_files_with_same_name_collide(tmp_path: Path) -> None:
    first, second = evaluator_file(tmp_path / "one"), evaluator_file(tmp_path / "two")
    with pytest.raises(ExternalEvaluatorError, match="collision"):
        resolve_evaluators([], [f"{first}:make", f"{second}:make"])
