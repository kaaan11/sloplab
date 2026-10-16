"""Legacy CLI writers must preserve marked study/pilot output directories."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.bundle import COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME


@pytest.mark.parametrize("command", ["benchmark", "evaluate"])
@pytest.mark.parametrize("marker", [COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME])
def test_legacy_writer_refuses_marked_output_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, marker: str
) -> None:
    import sloplab.cli.main as main

    out = tmp_path / "out"
    out.mkdir()
    # Even malformed markers establish ownership; no expensive evaluation or
    # materialization should be needed to discover this incompatible directory.
    (out / marker).write_text("existing marker", encoding="utf-8")
    (out / "run.jsonl").write_text("previous run", encoding="utf-8")
    (out / "metrics-oracle.json").write_text("previous metrics", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    def unexpected_work(*args: Any, **kwargs: Any) -> None:
        pytest.fail("marked destination must be rejected before running evaluators/materialization")

    monkeypatch.setattr(main, "_run_evaluators_over_suite", unexpected_work)
    monkeypatch.setattr("sloplab.mutations.materialize.materialize_suite", unexpected_work)
    if command == "benchmark":
        source = tmp_path / "suite.yaml"
        source.write_text("name: test\ncorpus_root: missing\npolicies: {}\n", encoding="utf-8")
    else:
        source = tmp_path / "cases"
        source.mkdir()
        (source / "suite-index.jsonl").write_text("", encoding="utf-8")

    result = CliRunner().invoke(
        cli, [command, str(source), "--evaluator", "oracle", "--out", str(out)]
    )

    assert result.exit_code == 1, result.output
    assert marker in result.output
    assert "Choose a different output directory" in result.output
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
