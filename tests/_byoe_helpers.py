"""Small offline inputs for BYOE/reporting integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from sloplab.models.run import EvaluatorInfo, RunMetadata
from tests._helpers import write_canonical_fixture

EVALUATOR_SOURCE = """\
from dataclasses import dataclass
from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import EvaluationResult, DimensionScores
from sloplab.evaluators.llm.failures import EvaluationFailure

@dataclass
class Example:
    name: str = "byoe-test"
    version: str = "1.2"
    requires_labels: bool = False

    def evaluate(self, report, context):
        assert context.labels == {}
        assert context.case_id.startswith("case-")
        assert report.fixture_id == report.path == context.case_id
        return EvaluationResult(
            evaluator_name=self.name, evaluator_version=self.version,
            case_id=context.case_id, decision=Decision.ACCEPT, confidence=0.6,
            dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, 0.5)),
        )

evaluator = Example()
def make():
    return Example()
"""


def evaluator_file(root: Path, extra: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "custom_eval.py"
    path.write_text(EVALUATOR_SOURCE + extra, encoding="utf-8")
    return path


def tiny_suite(root: Path) -> Path:
    corpus = root / "corpus"
    for index in range(2):
        write_canonical_fixture(
            corpus,
            f"case-{index}",
            fixture_id=f"canonical-case-{index}",
            title=f"Test case {index}",
        )
    suite = root / "suite.yaml"
    suite.write_text(
        yaml.safe_dump(
            {
                "name": "byoe-test-suite",
                "base_seed": 7,
                "corpus_root": str(corpus),
                "include_canonical_cases": True,
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}
                },
            }
        ),
        encoding="utf-8",
    )
    return suite


def metadata(*names: str) -> RunMetadata:
    return RunMetadata(
        run_id="fixed-run",
        sloplab_version="0.2.2",
        python_version="3.11",
        suite_name="Test suite",
        suite_hash="abc123",
        base_seed=42,
        evaluators=[EvaluatorInfo(name=name, version="0.1.0") for name in names],
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
