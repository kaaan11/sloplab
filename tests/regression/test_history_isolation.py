"""Import-boundary guard: evaluators can never reach run history.

Cross-run decision history records what an evaluator decided last time. An
evaluator able to read it could echo its own prior decision, which is benchmark
gaming of exactly the kind docs/evaluator-contract.md rule 4 forbids. The
boundary is enforced structurally rather than by convention: nothing under
``src/sloplab/evaluators/`` may import ``sloplab.scoring`` or
``sloplab.experiments`` - the packages that own scoring state and run provenance.

Companion to the R04 identity-hygiene tests in test_remediation_v022.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "sloplab"
EVALUATORS_ROOT = PACKAGE_ROOT / "evaluators"

FORBIDDEN_ROOTS = ("sloplab.scoring", "sloplab.experiments")


def _module_name(path: Path) -> str:
    dotted = ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)
    return ("sloplab." + dotted).removesuffix(".__init__")


def _imported_modules(source: str, module_name: str) -> set[str]:
    """Every absolute module name imported by ``source``; relatives resolved."""
    package = module_name.rsplit(".", 1)[0]
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                imported.add(f"{base}.{node.module}" if node.module else base)
            elif node.module:
                imported.add(node.module)
    return imported


def _violations(sources: list[tuple[str, str, str]]) -> list[str]:
    """``(label, source, module_name)`` triples -> sorted violation descriptions."""
    found: list[str] = []
    for label, source, module_name in sources:
        for imported in sorted(_imported_modules(source, module_name)):
            if any(imported == root or imported.startswith(f"{root}.") for root in FORBIDDEN_ROOTS):
                found.append(f"{label} imports {imported}")
    return sorted(found)


def _evaluator_sources() -> list[tuple[str, str, str]]:
    return sorted(
        (
            str(path.relative_to(REPO_ROOT)),
            path.read_text(encoding="utf-8"),
            _module_name(path),
        )
        for path in EVALUATORS_ROOT.rglob("*.py")
    )


def test_evaluator_package_is_non_empty() -> None:
    """Guard the guard: an empty scan would pass vacuously."""
    sources = _evaluator_sources()
    assert len(sources) >= 6, [label for label, _, _ in sources]


def test_evaluators_never_import_scoring_or_experiments() -> None:
    assert _violations(_evaluator_sources()) == []


def test_boundary_check_detects_an_injected_import() -> None:
    """The scan must fail when the forbidden import is actually present.

    The guard above would pass vacuously if the detection logic broke, so this
    injects the violation the guard exists to catch - including via a relative
    import, which must not be a loophole around the absolute-name check.
    """
    module = "sloplab.evaluators.rules.baseline"

    absolute_from = "from sloplab.experiments.history import DecisionHistory\n"
    assert _violations([("probe.py", absolute_from, module)]) == [
        "probe.py imports sloplab.experiments.history"
    ]

    plain_import = "import sloplab.scoring.comparison\n"
    assert _violations([("probe.py", plain_import, module)]) == [
        "probe.py imports sloplab.scoring.comparison"
    ]

    relative = "from ...experiments.history import DecisionHistory\n"
    assert _violations([("probe.py", relative, module)]) == [
        "probe.py imports sloplab.experiments.history"
    ]

    innocent = "from sloplab.models.report import ReportDocument\n"
    assert _violations([("probe.py", innocent, module)]) == []


def test_history_filename_never_appears_in_evaluator_sources() -> None:
    """Blocking the import is not enough if the filename leaks into an evaluator."""
    from sloplab.experiments.history import DEFAULT_HISTORY_FILENAME

    assert DEFAULT_HISTORY_FILENAME
    for label, source, _ in _evaluator_sources():
        assert DEFAULT_HISTORY_FILENAME not in source, label
