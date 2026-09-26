"""Rejected MODULE:ATTR loads must not become accepted through Python's cache."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from sloplab.evaluators import base
from sloplab.evaluators.external import ExternalEvaluatorError, load_external_evaluator

PLUGIN = """\
from sloplab.evaluators import base
class Example:
    name = "cache-test"
    version = "1"
    def evaluate(self, report, context):
        raise AssertionError("loading does not evaluate")
evaluator = Example()
def make():
    return evaluator
"""
MUTATIONS = {
    "register": "base.register_evaluator(evaluator)",
    "direct": "base._EVALUATOR_REGISTRY['rules-baseline'] = evaluator",
    "rebind": "base._EVALUATOR_REGISTRY = {'rogue': evaluator}",
}


@pytest.fixture
def import_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    # Test isolation only: production must not sweep the entire module cache.
    for name, module in tuple(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_relative_to(tmp_path):
            sys.modules.pop(name, None)


def assert_registry(registry: dict[str, Any], before: dict[str, Any]) -> None:
    assert base._EVALUATOR_REGISTRY is registry
    assert registry == before
    assert all(registry[name] is instance for name, instance in before.items())


@pytest.mark.parametrize("mutation", MUTATIONS.values(), ids=MUTATIONS)
@pytest.mark.parametrize("attribute", ["evaluator", "make"])
def test_importable_registry_mutation_rejected_on_every_load(
    import_root: Path, mutation: str, attribute: str
) -> None:
    (import_root / "bad_plugin.py").write_text(PLUGIN + mutation + "\n")
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    for _ in range(3):
        with pytest.raises(ExternalEvaluatorError, match="registry"):
            load_external_evaluator(f"bad_plugin:{attribute}")
        assert_registry(registry, before)
    assert "bad_plugin" not in sys.modules


@pytest.mark.parametrize(
    "extra,attribute,match",
    [
        ("evaluator.version = ''\n", "evaluator", "version must"),
        ("def make(): raise ValueError('secret')\n", "make", "factory"),
        ("def make(): return None\n", "make", "name must"),
        ("", "missing", "not found"),
        ("evaluator.requires_labels = True\n", "evaluator", "ground-truth labels"),
    ],
)
def test_rejected_fresh_contract_or_factory_does_not_leave_cache(
    import_root: Path, extra: str, attribute: str, match: str
) -> None:
    (import_root / "bad_contract.py").write_text(PLUGIN + extra)
    for _ in range(2):
        with pytest.raises(ExternalEvaluatorError, match=match):
            load_external_evaluator(f"bad_contract:{attribute}")
        assert "bad_contract" not in sys.modules


@pytest.mark.parametrize("attribute", ["evaluator", "make"])
def test_valid_module_reuses_cached_object(import_root: Path, attribute: str) -> None:
    (import_root / "valid_cached.py").write_text(PLUGIN)
    first = load_external_evaluator(f"valid_cached:{attribute}")
    module = sys.modules["valid_cached"]
    second = load_external_evaluator(f"valid_cached:{attribute}")
    assert first.name == second.name == "cache-test"
    assert sys.modules["valid_cached"] is module
    # Reimporting would create another class/instance and break this identity.
    assert vars(first)["_evaluator"] is vars(second)["_evaluator"] is module.evaluator


@pytest.mark.parametrize("mutation", MUTATIONS.values(), ids=MUTATIONS)
def test_preimported_module_survives_failed_factory(import_root: Path, mutation: str) -> None:
    (import_root / "preloaded.py").write_text(
        PLUGIN + f"def make():\n    {mutation}\n    return evaluator\n"
    )
    module = importlib.import_module("preloaded")
    contents = dict(vars(module))
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    for _ in range(3):
        with pytest.raises(ExternalEvaluatorError, match="registry"):
            load_external_evaluator("preloaded:make")
        assert sys.modules["preloaded"] is module
        assert vars(module) == contents
        assert_registry(registry, before)


def test_preimported_bad_contract_and_none_entry_are_untouched(
    import_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (import_root / "preloaded_bad.py").write_text(PLUGIN + "evaluator.name = ''\n")
    module = importlib.import_module("preloaded_bad")
    with pytest.raises(ExternalEvaluatorError, match="name must"):
        load_external_evaluator("preloaded_bad:evaluator")
    assert sys.modules["preloaded_bad"] is module
    monkeypatch.setitem(sys.modules, "blocked_plugin", None)
    with pytest.raises(ExternalEvaluatorError, match="Cannot import"):
        load_external_evaluator("blocked_plugin:evaluator")
    assert "blocked_plugin" in sys.modules and sys.modules["blocked_plugin"] is None


@pytest.mark.parametrize("preload_parent", [False, True])
def test_package_relative_import_and_parent_binding_ownership(
    import_root: Path, preload_parent: bool
) -> None:
    package = import_root / "cache_package"
    package.mkdir()
    (package / "__init__.py").write_text("sentinel = object()\nplugin = sentinel\n")
    (package / "helper.py").write_text(PLUGIN)
    (package / "plugin.py").write_text(
        "from .helper import evaluator\nfrom sloplab.evaluators import base\n"
        "base.register_evaluator(evaluator)\n"
    )
    parent = importlib.import_module("cache_package") if preload_parent else None
    helper = importlib.import_module("cache_package.helper") if preload_parent else None
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    for _ in range(3):
        with pytest.raises(ExternalEvaluatorError, match="registry"):
            load_external_evaluator("cache_package.plugin:evaluator")
        assert "cache_package.plugin" not in sys.modules
        if parent is not None:
            assert sys.modules["cache_package"] is parent
            assert parent.plugin is parent.sentinel
            assert sys.modules["cache_package.helper"] is helper
        assert_registry(registry, before)


@pytest.mark.parametrize("mutation", MUTATIONS.values(), ids=MUTATIONS)
def test_new_parent_package_import_is_not_left_as_a_policy_bypass(
    import_root: Path, mutation: str
) -> None:
    package = import_root / "bad_parent"
    package.mkdir()
    (package / "__init__.py").write_text(PLUGIN + mutation + "\n")
    (package / "plugin.py").write_text("from . import evaluator\n")
    for _ in range(3):
        with pytest.raises(ExternalEvaluatorError, match="registry"):
            load_external_evaluator("bad_parent.plugin:evaluator")
        assert "bad_parent" not in sys.modules
        assert "bad_parent.plugin" not in sys.modules


@pytest.mark.parametrize("exception", ["RuntimeError", "KeyboardInterrupt", "SystemExit"])
def test_failed_import_cleans_only_owned_package_chain(import_root: Path, exception: str) -> None:
    package = import_root / "broken_chain"
    package.mkdir()
    (package / "__init__.py").write_text(PLUGIN + MUTATIONS["register"] + "\n")
    (package / "plugin.py").write_text(f"raise {exception}('load interrupted')\n")
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    expected = {
        "RuntimeError": ExternalEvaluatorError,
        "KeyboardInterrupt": KeyboardInterrupt,
        "SystemExit": SystemExit,
    }[exception]
    for _ in range(2):
        with pytest.raises(expected):
            load_external_evaluator("broken_chain.plugin:evaluator")
        assert "broken_chain" not in sys.modules
        assert "broken_chain.plugin" not in sys.modules
        assert_registry(registry, before)


def test_failed_factory_does_not_delete_replacement_cache_entry(import_root: Path) -> None:
    (import_root / "replaced_entry.py").write_text(
        PLUGIN + "import sys\nfrom types import ModuleType\n"
        "def make():\n"
        "    sys.modules[__name__] = ModuleType('replacement')\n"
        "    raise ValueError('factory failed')\n"
    )
    try:
        with pytest.raises(ExternalEvaluatorError, match="factory"):
            load_external_evaluator("replaced_entry:make")
        assert sys.modules["replaced_entry"].__name__ == "replacement"
    finally:
        sys.modules.pop("replaced_entry", None)


def test_valid_package_relative_import_stays_cached(import_root: Path) -> None:
    package = import_root / "valid_package"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "helper.py").write_text(PLUGIN)
    (package / "plugin.py").write_text("from .helper import evaluator, make\n")
    first = load_external_evaluator("valid_package.plugin:make")
    modules = {
        name: sys.modules[name]
        for name in ("valid_package", "valid_package.helper", "valid_package.plugin")
    }
    second = load_external_evaluator("valid_package.plugin:evaluator")
    assert vars(first)["_evaluator"] is vars(second)["_evaluator"]
    assert all(sys.modules[name] is module for name, module in modules.items())
    assert modules["valid_package"].plugin is modules["valid_package.plugin"]


@pytest.mark.parametrize("stage", ["import", "factory"])
def test_relative_helper_cannot_cache_registry_mutation(import_root: Path, stage: str) -> None:
    package = import_root / "relative_bad"
    package.mkdir()
    (package / "__init__.py").write_text("sentinel = object()\n")
    (package / "helper.py").write_text(PLUGIN + MUTATIONS["register"] + "\n")
    code = (
        "from .helper import evaluator\n"
        if stage == "import"
        else ("def make():\n    from .helper import evaluator\n    return evaluator\n")
    )
    (package / "plugin.py").write_text(code)
    parent = importlib.import_module("relative_bad")
    sentinel = parent.sentinel
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    for _ in range(3):
        attribute = "evaluator" if stage == "import" else "make"
        with pytest.raises(ExternalEvaluatorError, match="registry"):
            load_external_evaluator(f"relative_bad.plugin:{attribute}")
        assert_registry(registry, before)
        assert sys.modules["relative_bad"] is parent and parent.sentinel is sentinel
        assert "relative_bad.plugin" not in sys.modules and "relative_bad.helper" not in sys.modules
        assert "plugin" not in vars(parent) and "helper" not in vars(parent)


def test_unrelated_import_cache_is_not_swept(import_root: Path) -> None:
    (import_root / "unrelated_dependency.py").write_text("marker = object()\n")
    (import_root / "bad_with_dependency.py").write_text(
        PLUGIN + "import unrelated_dependency\n" + MUTATIONS["register"] + "\n"
    )
    with pytest.raises(ExternalEvaluatorError, match="registry"):
        load_external_evaluator("bad_with_dependency:evaluator")
    dependency = sys.modules["unrelated_dependency"]
    with pytest.raises(ExternalEvaluatorError, match="registry"):
        load_external_evaluator("bad_with_dependency:evaluator")
    assert sys.modules["unrelated_dependency"] is dependency
    assert "bad_with_dependency" not in sys.modules


def test_failed_factory_does_not_overwrite_replacement_parent_binding(import_root: Path) -> None:
    package = import_root / "changed_binding"
    package.mkdir()
    (package / "__init__.py").write_text("marker = object()\n")
    (package / "plugin.py").write_text(
        "import changed_binding\n"
        "def make():\n"
        "    changed_binding.plugin = changed_binding.marker\n"
        "    raise ValueError('fail')\n"
    )
    parent = importlib.import_module("changed_binding")
    with pytest.raises(ExternalEvaluatorError, match="factory"):
        load_external_evaluator("changed_binding.plugin:make")
    assert sys.modules["changed_binding"] is parent
    assert parent.plugin is parent.marker
    assert "changed_binding.plugin" not in sys.modules


def test_corrected_module_can_load_after_rejection(import_root: Path) -> None:
    path = import_root / "correctable.py"
    path.write_text(PLUGIN + MUTATIONS["register"] + "\n")
    with pytest.raises(ExternalEvaluatorError, match="registry"):
        load_external_evaluator("correctable:evaluator")
    path.write_text(PLUGIN)  # Different size invalidates Python's bytecode cache.
    importlib.invalidate_caches()
    assert load_external_evaluator("correctable:evaluator").name == "cache-test"


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit])
def test_factory_interrupt_preserves_primary_exception_and_cleans_cache(
    import_root: Path, exception: type[BaseException]
) -> None:
    (import_root / "interrupted_factory.py").write_text(
        PLUGIN + "def make():\n"
        "    base.register_evaluator(evaluator)\n"
        f"    raise {exception.__name__}('interrupted factory')\n"
    )
    registry, before = base._EVALUATOR_REGISTRY, dict(base._EVALUATOR_REGISTRY)
    with pytest.raises(exception, match="interrupted factory"):
        load_external_evaluator("interrupted_factory:make")
    assert "interrupted_factory" not in sys.modules
    assert_registry(registry, before)
