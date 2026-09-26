"""Explicit, trusted-local BYOE loading. This is NOT a Python sandbox.

External objects never enter the evaluator registry. A registry snapshot protects
against accidental import/factory registration; arbitrary Python side effects
cannot be undone or isolated. Resolution must run before starting evaluations.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import cast

from pydantic import ValidationError

from sloplab.evaluators import base
from sloplab.evaluators.base import Evaluator
from sloplab.evaluators.llm.failures import EvaluationFailure
from sloplab.models.evaluation import EvaluationContext, EvaluationResult
from sloplab.models.report import ReportDocument


class ExternalEvaluatorError(ValueError):
    """An actionable loading/contract error, not a scored operational failure."""


@contextmanager
def _preserve_registry() -> Iterator[None]:
    # Preserve mapping identity too, for existing importers holding its reference.
    registry = base._EVALUATOR_REGISTRY
    snapshot = dict(registry)
    try:
        yield
        current = base._EVALUATOR_REGISTRY
        if (
            current is not registry
            or current.keys() != snapshot.keys()
            or any(current[name] is not value for name, value in snapshot.items())
        ):
            raise ExternalEvaluatorError(
                "External import/factory changed the evaluator registry; changes were restored. "
                "Remove import-time register_evaluator calls and return the object instead."
            )
    finally:
        registry.clear()
        registry.update(snapshot)
        base._EVALUATOR_REGISTRY = registry


def _import_source(source: str) -> ModuleType:
    if source.endswith(".py") or "/" in source or "\\" in source:
        path = Path(source).expanduser().resolve()
        if not path.is_file():
            raise ExternalEvaluatorError(f"Evaluator file not found: {source}")
        if path.suffix != ".py":
            raise ExternalEvaluatorError("Evaluator file must be a .py Python source file.")
        name = "_sloplab_external_" + hashlib.sha256(str(path).encode()).hexdigest()
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ExternalEvaluatorError(f"Cannot load evaluator source: {source}")
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(name)
        sys.modules[name] = module  # required by decorators such as dataclass
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
            raise
        return module
    return importlib.import_module(source)


@contextmanager
def _loaded_source(source: str) -> Iterator[ModuleType]:
    """Keep import-cache ownership alive through validation and registry exit.

    A rejected importable module must not be reused without executing its body.
    Track only newly imported entries in its package namespace, including parents
    and relative helpers; never sweep unrelated imports or evict pre-existing
    modules. Like registry restoration, this assumes serialized BYOE resolution,
    not arbitrary concurrent imports or sandboxing of Python side effects.
    """
    namespace = (
        None if source.endswith(".py") or "/" in source or "\\" in source else source.split(".")[0]
    )

    def in_namespace(name: str) -> bool:
        return namespace is not None and (name == namespace or name.startswith(namespace + "."))

    previous = {name: module for name, module in sys.modules.copy().items() if in_namespace(name)}
    bindings = {
        name: vars(module).copy()
        for name, module in previous.items()
        if isinstance(module, ModuleType)
    }
    owned: dict[str, ModuleType] = {}

    def remember_imports() -> None:
        for name, module in sys.modules.copy().items():
            if in_namespace(name) and name not in previous and isinstance(module, ModuleType):
                # Do not adopt a replacement installed later by a factory.
                owned.setdefault(name, module)

    try:
        with _preserve_registry():
            try:
                try:
                    module = _import_source(source)
                finally:
                    # Also record successful parent imports if the leaf fails.
                    remember_imports()
            except ExternalEvaluatorError:
                raise
            except Exception as exc:
                raise ExternalEvaluatorError(
                    f"Cannot import evaluator module '{source}' ({type(exc).__name__}); "
                    "check the module path and its dependencies."
                ) from exc
            try:
                yield module
            finally:
                remember_imports()  # include imports made by the factory
    except BaseException:
        missing = object()
        for name in sorted(owned, key=lambda key: (key.count("."), key), reverse=True):
            module = owned[name]
            if sys.modules.get(name) is not module:
                continue  # do not delete a replacement we did not import
            del sys.modules[name]
            parent_name, _, child = name.rpartition(".")
            parent = previous.get(parent_name, owned.get(parent_name))
            if (
                isinstance(parent, ModuleType)
                and sys.modules.get(parent_name) is parent
                and vars(parent).get(child, missing) is module
            ):
                # importlib binds a submodule on its parent as well as in the
                # cache. Restore only that binding, not the parent's whole dict.
                prior = bindings.get(parent_name, {}).get(child, missing)
                if prior is missing:
                    del vars(parent)[child]
                else:
                    vars(parent)[child] = prior
        raise


def _validate(candidate: object) -> Evaluator:
    for field in ("name", "version"):
        value = getattr(candidate, field, None)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ExternalEvaluatorError(f"Evaluator {field} must be a non-empty, unpadded string.")
    method = getattr(candidate, "evaluate", None)
    if not callable(method):
        raise ExternalEvaluatorError(
            "Evaluator evaluate must be callable: evaluate(report, context)."
        )
    if inspect.iscoroutinefunction(method):
        raise ExternalEvaluatorError("Evaluator evaluate must be synchronous, not async.")
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        pass  # some extension callables have no inspectable signature
    else:
        try:
            signature.bind(object(), object())
        except TypeError as exc:
            raise ExternalEvaluatorError(
                "Evaluator evaluate must accept (report, context)."
            ) from exc
    if base.evaluator_requires_labels(candidate):
        raise ExternalEvaluatorError(
            "External evaluators cannot request benchmark ground-truth labels. "
            "Remove requires_labels=True."
        )
    return cast(Evaluator, candidate)


class _ExternalEvaluator:
    """Keep the external capability false and check the existing result contract.

    The wrapper protects the harness boundary, not the process: trusted Python can
    still read disk or modify global state. No sandbox/security isolation is claimed.
    """

    requires_labels = False

    def __init__(self, evaluator: Evaluator) -> None:
        self.name, self.version = evaluator.name, evaluator.version
        self._evaluator = evaluator

    def evaluate(self, report: ReportDocument, context: EvaluationContext) -> EvaluationResult:
        try:
            _validate(self._evaluator)
            # Also safe when a caller invokes this adapter outside the normal harness.
            result = self._evaluator.evaluate(report, context.model_copy(update={"labels": {}}))
            if not isinstance(result, EvaluationResult):
                raise ExternalEvaluatorError("Evaluator evaluate must return EvaluationResult.")
            result = EvaluationResult.model_validate(result.model_dump(mode="python"))
            if (result.evaluator_name, result.evaluator_version) != (self.name, self.version):
                raise ExternalEvaluatorError(
                    "EvaluationResult evaluator_name/version must match the loaded evaluator."
                )
            if result.case_id != context.case_id:
                raise ExternalEvaluatorError("EvaluationResult must echo context.case_id.")
            return result
        except (EvaluationFailure, ExternalEvaluatorError):
            raise
        except ValidationError as exc:
            # Pydantic dumps may include raw model output: don't copy them to logs.
            raise ExternalEvaluatorError("Evaluator returned an invalid EvaluationResult.") from exc
        except Exception as exc:
            raise ExternalEvaluatorError(
                f"External evaluate raised {type(exc).__name__}; inspect your local evaluator. "
                "Use EvaluationFailure for typed operational failures."
            ) from exc


def load_external_evaluator(spec: str) -> Evaluator:
    """Resolve ``FILE.py:ATTR`` or ``MODULE:ATTR`` without registering the result."""
    source, separator, attribute = spec.rpartition(":")
    if not separator or not source or not attribute or not attribute.isidentifier():
        raise ExternalEvaluatorError(
            "Evaluator spec requires :ATTR: use FILE.py:make or package.module:evaluator."
        )
    with _loaded_source(source) as module:
        if not hasattr(module, attribute):
            raise ExternalEvaluatorError(
                f"Evaluator attribute '{attribute}' not found in '{source}'."
            )
        candidate = getattr(module, attribute)
        if inspect.isclass(candidate) or (
            callable(candidate) and not hasattr(candidate, "evaluate")
        ):
            try:
                candidate = candidate()
            except Exception as exc:
                raise ExternalEvaluatorError(
                    f"Evaluator factory '{attribute}' failed ({type(exc).__name__}); "
                    "it must take no arguments and return an evaluator."
                ) from exc
        try:
            evaluator = _validate(candidate)
        except ExternalEvaluatorError:
            raise
        except Exception as exc:
            raise ExternalEvaluatorError(
                f"Cannot inspect evaluator fields ({type(exc).__name__}); "
                "provide name, version and callable evaluate."
            ) from exc
        return _ExternalEvaluator(evaluator)


def resolve_evaluators(names: Sequence[str], modules: Sequence[str] = ()) -> list[Evaluator]:
    """Combine built-ins and external objects; reject every name collision."""
    if not names and not modules:
        raise ExternalEvaluatorError("Select at least one --evaluator or --evaluator-module.")
    reserved = set(base.list_evaluators())
    resolved: list[Evaluator] = []
    seen: set[str] = set()
    for name in names:
        try:
            evaluator = base.get_evaluator(name)
        except KeyError as exc:
            raise ExternalEvaluatorError(str(exc)) from exc
        if evaluator.name in seen:
            raise ExternalEvaluatorError(f"Duplicate evaluator name: {evaluator.name}")
        seen.add(evaluator.name)
        resolved.append(evaluator)
    for spec in modules:
        evaluator = load_external_evaluator(spec)
        if evaluator.name in reserved or evaluator.name in seen:
            raise ExternalEvaluatorError(
                f"Evaluator name collision: {evaluator.name}; choose a unique external name."
            )
        seen.add(evaluator.name)
        resolved.append(evaluator)
    return resolved
