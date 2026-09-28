"""Issue #53: evidence-graph/rules ``overall=`` rationale must round identically
on every supported Python version.

Boundary case from deterministic-study-v0.2: canonical-pair5b-health and
canonical-robots-022 (plus three robots-022 derivatives) score the dimension
vector (1.0, 0.95, 0.35, 0.875, 0.8), whose exact mean is 0.795. Builtin
sum() adds naively on 3.11 (0.7949999999999999 -> "overall=0.79") but with
compensation on 3.12+ (0.795 -> "overall=0.80"). The shared
mean_dimension_score() helper uses math.fsum, which is correctly rounded on
every version, so the rationale text is identical everywhere.
"""

from __future__ import annotations

import math
from pathlib import Path

from sloplab.corpus.loader import load_canonical_fixture
from sloplab.evaluators.rules.evidence_graph import EvidenceGraphBaselineEvaluator
from sloplab.models.enums import DIMENSIONS
from sloplab.models.evaluation import EvaluationContext, mean_dimension_score

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Dimension vector of the issue-#53 boundary cases (evidence-graph evaluation
#: of canonical-pair5b-health / canonical-robots-022).
BOUNDARY_DIMS = {
    "reproducibility": 1.0,
    "evidence_completeness": 0.95,
    "claim_evidence_consistency": 0.35,
    "impact_calibration": 0.875,
    "scope_consistency": 0.8,
}


class TestBoundaryRounding:
    def test_helper_covers_all_dimensions(self) -> None:
        assert set(BOUNDARY_DIMS) == set(DIMENSIONS)

    def test_exact_mean_at_halfway_boundary(self) -> None:
        assert mean_dimension_score(BOUNDARY_DIMS) == 0.795

    def test_boundary_formats_up(self) -> None:
        assert f"{mean_dimension_score(BOUNDARY_DIMS):.2f}" == "0.80"

    def test_matches_correctly_rounded_fsum(self) -> None:
        expected = math.fsum(BOUNDARY_DIMS[d] for d in DIMENSIONS) / len(DIMENSIONS)
        assert mean_dimension_score(BOUNDARY_DIMS) == expected


class TestBoundaryRationale:
    """End-to-end pin on the real issue-#53 fixtures."""

    def _rationale(self, fixture_dir: str, case_id: str) -> str:
        corpus_root = REPO_ROOT / "corpus"
        fixture = load_canonical_fixture(corpus_root / "canonical" / fixture_dir, corpus_root)
        ctx = EvaluationContext(report=fixture.report, case_id=case_id, labels={})
        return EvidenceGraphBaselineEvaluator().evaluate(fixture.report, ctx).rationale

    def test_pair5b_health_overall_formats_up(self) -> None:
        assert "overall=0.80" in self._rationale("pair5b-health", "canonical-pair5b-health")

    def test_robots_022_overall_formats_up(self) -> None:
        assert "overall=0.80" in self._rationale("robots-022", "canonical-robots-022")
