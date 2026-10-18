"""Regression tests for suite path resolution (found during release audit)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from sloplab.cli.main import cli


def test_materialize_and_evaluate_from_foreign_cwd(tmp_path: Path, make_fixture: Any) -> None:
    """Bug: relative corpus_root silently produced an empty suite when the CLI ran
    outside the repository directory; evaluation then failed with 'contains no
    cases'. Resolution must anchor to the suite file location."""
    workspace = tmp_path / "proj"
    for i in range(2):
        make_fixture(
            workspace,
            f"v-{i:03d}",
            fixture_id=f"canonical-v-{i:03d}",
            title=f"Foreign cwd report {i}",
            report_class="valid",
        )
    import yaml

    suite = {
        "name": "foreign",
        "base_seed": 3,
        "corpus_root": str(workspace),
        "policies": {"valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}},
    }
    (workspace / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")
    out_dir = tmp_path / "results"

    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(workspace / "suite.yaml"),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out_dir / "run.jsonl").is_file()


def test_missing_corpus_root_fails_loudly(tmp_path: Path) -> None:
    """A corpus_root pointing nowhere must error instead of materializing nothing."""
    import yaml

    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        yaml.safe_dump(
            {
                "name": "ghost",
                "base_seed": 1,
                "corpus_root": str(tmp_path / "does-not-exist"),
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]}
                },
            }
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(suite_path),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0
    assert "no canonical fixtures" in result.output


def test_console_script_works_from_any_directory(tmp_path: Path, make_fixture: Any) -> None:
    """Resolve a relative corpus root from suite ancestors in a foreign cwd."""
    import yaml

    workspace = tmp_path / "project"
    make_fixture(workspace / "corpus", "cwd-001", fixture_id="canonical-cwd-001", title="Cwd check")
    suite = workspace / "benchmarks" / "suites" / "smoke-config-check.yaml"
    suite.parent.mkdir(parents=True)
    suite.write_text(
        yaml.safe_dump(
            {
                "name": "cwd-check",
                "base_seed": 9,
                "corpus_root": "corpus",
                "include_canonical_cases": True,
                "policies": {
                    "valid": {"variants_per_fixture": 1, "operators": ["impact_inflation"]},
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sloplab.cli.main",
            "benchmark",
            str(suite),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(tmp_path / "missing-index"),
            "--no-materialize",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert proc.returncode != 0
    assert "suite-index.jsonl" in proc.stdout + proc.stderr
    assert "Traceback" not in proc.stdout + proc.stderr

    out_dir = tmp_path / "materialized"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sloplab.cli.main",
            "materialize",
            str(suite),
            "--out",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (out_dir / "suite-index.jsonl").is_file()
