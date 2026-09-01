"""The injection arm is reachable from a committed path, and its number is honest.

Without a committed suite naming the injection operators, `injection_success_by_arm`
could never produce a number outside a test fixture: `study` always wrote an empty
section. This exercises the real suite end to end.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITE = REPO_ROOT / "benchmarks" / "suites" / "injection-v1.yaml"

INJECTION_OPERATORS = {"instruction_override", "forged_boundary", "fabricated_triage_note"}


def test_committed_suite_lists_every_injection_operator() -> None:
    config = yaml.safe_load(SUITE.read_text(encoding="utf-8"))
    for report_class, policy in config["policies"].items():
        assert set(policy["operators"]) == INJECTION_OPERATORS, report_class


def test_v1_core_still_excludes_injection_operators() -> None:
    """Adding them there would move every published SlopLab number."""
    core = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "suites" / "v1-core.yaml").read_text(encoding="utf-8")
    )
    for policy in core["policies"].values():
        assert not INJECTION_OPERATORS & set(policy["operators"])


def test_study_over_the_committed_suite_reports_a_zero_lift(tmp_path: Path) -> None:
    """The negative control, corpus-wide.

    `rules-baseline` has no instructions to hijack, so the payload must move
    nothing. Its raw success rate is NOT zero - it answers `accept` on some cases
    regardless - which is exactly why the reported number is the lift over the
    un-injected parents rather than the raw rate.
    """
    study_config = {
        "name": "injection-arm-study",
        "suite": {"config_path": str(SUITE), "corpus_root": str(REPO_ROOT / "corpus")},
        "base_seed": 20260901,
        "evaluators": [{"name": "rules-baseline"}],
    }
    config_path = tmp_path / "study.yaml"
    config_path.write_text(yaml.safe_dump(study_config), encoding="utf-8")

    out_dir = tmp_path / "out"
    result = CliRunner().invoke(cli, ["study", str(config_path), "--out", str(out_dir)])
    assert result.exit_code == 0, result.output

    analysis: dict[str, Any] = json.loads((out_dir / "analysis.json").read_text())
    control = analysis["injection_success"]["rules-baseline"]["none"]

    assert control["injected_cases"] > 100, control
    assert control["baseline_cases"] > 0, control
    assert control["success_rate"] > 0.0, "a raw rate of zero would make the point vacuous"
    assert control["success_lift"] == 0.0, control


def test_payload_moves_no_deterministic_decision(tmp_path: Path) -> None:
    """The property the lift measures, asserted directly on the records."""
    out_dir = tmp_path / "bench"
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(SUITE),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    from sloplab.reporting.writers import read_run_jsonl

    _meta, records = read_run_jsonl(out_dir / "run.jsonl")
    canonical = {r.case_id: r for r in records if r.case_kind == "canonical"}
    moved = [
        r.case_id
        for r in records
        if r.operator and r.parent_id in canonical and r.decision != canonical[r.parent_id].decision
    ]
    assert moved == [], moved
