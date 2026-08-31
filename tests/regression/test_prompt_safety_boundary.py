"""The delimiting helper stays inside the LLM evaluator's prompt construction.

Arm B's neutralizer rewrites report content. Applied anywhere else - in the
harness, the materializer, another evaluator - it would silently change what the
benchmark measures for every arm, including the control. The boundary is
therefore structural, checked the same way as the D-0014 history boundary.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "sloplab"
LLM_PACKAGE = PACKAGE_ROOT / "evaluators" / "llm"

MODULE = "sloplab.evaluators.llm.prompt_safety"


def _module_name(path: Path) -> str:
    dotted = ".".join(path.relative_to(PACKAGE_ROOT).with_suffix("").parts)
    return ("sloplab." + dotted).removesuffix(".__init__")


def _imports(source: str, module_name: str) -> set[str]:
    package = module_name.rsplit(".", 1)[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                found.add(f"{base}.{node.module}" if node.module else base)
            elif node.module:
                found.add(node.module)
    return found


def _package_sources() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def test_scan_is_not_vacuous() -> None:
    assert len(_package_sources()) >= 25


def test_only_the_llm_adapter_imports_prompt_safety() -> None:
    importers = {
        str(path.relative_to(REPO_ROOT))
        for path in _package_sources()
        if MODULE in _imports(path.read_text(encoding="utf-8"), _module_name(path))
    }
    assert importers == {"src/sloplab/evaluators/llm/adapter.py"}, importers


def test_no_other_evaluator_reaches_the_helper() -> None:
    outside = [
        path
        for path in (PACKAGE_ROOT / "evaluators").rglob("*.py")
        if LLM_PACKAGE not in path.parents
        and MODULE in _imports(path.read_text(encoding="utf-8"), _module_name(path))
    ]
    assert outside == []


def test_detection_logic_actually_fires() -> None:
    """Guard the guard: the scan must catch the import it exists to forbid."""
    source = "from sloplab.evaluators.llm.prompt_safety import wrap_untrusted\n"
    assert MODULE in _imports(source, "sloplab.scoring.harness")

    relative = "from .llm.prompt_safety import wrap_untrusted\n"
    assert MODULE in _imports(relative, "sloplab.evaluators.oracle")

    innocent = "from sloplab.models.report import ReportDocument\n"
    assert MODULE not in _imports(innocent, "sloplab.evaluators.oracle")
