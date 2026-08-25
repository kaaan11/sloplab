"""End-to-end integration tests: corpus -> materialize -> evaluate -> score -> report.

These run the real CLI in-process and must complete fully offline.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner

from sloplab.cli.main import cli


def build_workspace(tmp_path: Path, make_fixture: Any) -> Path:
    for i in range(3):
        make_fixture(
            tmp_path,
            f"val-{i:03d}",
            fixture_id=f"canonical-val-{i:03d}",
            title=f"Valid integration report {i}",
            report_class="valid",
        )
    make_fixture(
        tmp_path,
        "inv-000",
        fixture_id="canonical-inv-000",
        title="Invalid integration report",
        report_class="invalid",
    )
    make_fixture(
        tmp_path,
        "rev-000",
        fixture_id="canonical-rev-000",
        title="Review integration report",
        report_class="review",
    )
    suite = {
        "name": "integration-suite",
        "base_seed": 11,
        "corpus_root": str(tmp_path),
        "include_canonical_cases": True,
        "policies": {
            "valid": {
                "variants_per_fixture": 3,
                "operators": [
                    "remove_reproduction_step",
                    "impact_inflation",
                    "professionalize_language",
                    "invent_api_identifier",
                    "scope_expansion",
                ],
            },
            "invalid": {"variants_per_fixture": 2, "operators": ["confidence_overstatement"]},
            "review": {"variants_per_fixture": 1, "operators": ["remove_affected_version"]},
        },
    }
    (tmp_path / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")
    return tmp_path


def test_full_benchmark_pipeline(tmp_path: Path, make_fixture: Any) -> None:
    workspace = build_workspace(tmp_path, make_fixture)
    out_dir = workspace / "results"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "benchmark",
            str(workspace / "suite.yaml"),
            "--evaluator",
            "oracle",
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    # Outputs exist.
    assert (out_dir / "run.jsonl").is_file()
    assert (out_dir / "results.csv").is_file()
    assert (out_dir / "report.md").is_file()
    assert (out_dir / "metrics-oracle.json").is_file()
    assert (out_dir / "metrics-rules-baseline.json").is_file()
    assert (out_dir / "suite-index.jsonl").is_file()

    # Run log structure: first line metadata, rest case records.
    lines = [json.loads(line) for line in (out_dir / "run.jsonl").read_text().splitlines()]
    assert lines[0]["record_type"] == "run_metadata"
    case_lines = [line for line in lines if line["record_type"] == "case"]
    derived_expected = 3 * 3 + 1 * 2 + 1 * 1  # per policy variants x fixtures
    assert len(case_lines) == (5 + derived_expected) * 2  # canonicals + mutants, two evaluators

    # Oracle must be perfect - that validates the scoring plumbing end to end.
    oracle_metrics = json.loads((out_dir / "metrics-oracle.json").read_text())
    assert oracle_metrics["decision_accuracy"] == 1.0
    assert oracle_metrics["false_reassurance_rate"] == 0.0
    assert oracle_metrics["mutation_detection_rate"] == 1.0

    # CSV row count matches case records.
    with (out_dir / "results.csv").open() as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(case_lines)

    # Report contains evaluator sections.
    report_text = (out_dir / "report.md").read_text()
    assert "`oracle`" in report_text
    assert "`rules-baseline`" in report_text


def test_rerun_is_byte_identical(tmp_path: Path, make_fixture: Any) -> None:
    workspace = build_workspace(tmp_path, make_fixture)
    out_a, out_b = workspace / "a", workspace / "b"
    runner = CliRunner()
    args = ["--evaluator", "rules-baseline"]
    for out in (out_a, out_b):
        result = runner.invoke(
            cli, ["benchmark", str(workspace / "suite.yaml"), *args, "--out", str(out)]
        )
        assert result.exit_code == 0, result.output

    def snapshot(root: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
        }

    sa, sb = snapshot(out_a), snapshot(out_b)
    # run metadata embeds a timestamp; compare everything except run.jsonl's first line.
    assert set(sa) == set(sb)
    for key in sa:
        if key.endswith("run.jsonl"):
            la, lb = sa[key].splitlines(), sb[key].splitlines()
            assert la[1:] == lb[1:]
            assert json.loads(la[0])["suite_hash"] == json.loads(lb[0])["suite_hash"]
        else:
            assert sa[key] == sb[key], key


def test_evaluate_reuses_materialized_suite(tmp_path: Path, make_fixture: Any) -> None:
    workspace = build_workspace(tmp_path, make_fixture)
    mat_dir = workspace / "materialized"
    eval_out = workspace / "eval-out"
    runner = CliRunner()

    r1 = runner.invoke(cli, ["materialize", str(workspace / "suite.yaml"), "--out", str(mat_dir)])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(
        cli,
        [
            "evaluate",
            str(mat_dir),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(eval_out),
        ],
    )
    assert r2.exit_code == 0, r2.output
    assert (eval_out / "run.jsonl").is_file()


def test_validate_passes_on_generated_corpus(tmp_path: Path, make_fixture: Any) -> None:
    workspace = build_workspace(tmp_path, make_fixture)
    result = CliRunner().invoke(cli, ["validate", str(workspace)])
    assert result.exit_code == 0, result.output


def test_compare_prints_table(tmp_path: Path, make_fixture: Any) -> None:
    workspace = build_workspace(tmp_path, make_fixture)
    out_dir = workspace / "results"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            str(workspace / "suite.yaml"),
            "--evaluator",
            "oracle",
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output

    cmp_result = runner.invoke(cli, ["compare", str(out_dir)])
    assert cmp_result.exit_code == 0, cmp_result.output
    assert "accuracy" in cmp_result.output
    assert "oracle" in cmp_result.output
