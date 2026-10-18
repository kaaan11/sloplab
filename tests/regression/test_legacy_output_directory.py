"""Legacy CLI writers must preserve marked study/pilot output directories."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.bundle import COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME
from tests._helpers import write_canonical_fixture


@pytest.mark.parametrize("command", ["benchmark", "evaluate", "materialize"])
@pytest.mark.parametrize("marker", [COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME])
@pytest.mark.parametrize("subdir", [".", "rerun", "rerun/nested"])
def test_legacy_writer_refuses_marked_output_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str, marker: str, subdir: str
) -> None:
    import sloplab.cli.main as main

    out = tmp_path / "out"
    out.mkdir()
    # Even malformed markers establish ownership; no expensive evaluation or
    # materialization should be needed to discover this incompatible directory.
    (out / marker).write_text("existing marker", encoding="utf-8")
    (out / "run.jsonl").write_text("previous run", encoding="utf-8")
    (out / "metrics-oracle.json").write_text("previous metrics", encoding="utf-8")
    (out / "suite-index.jsonl").write_text("previous index", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    def unexpected_work(*args: Any, **kwargs: Any) -> None:
        pytest.fail("marked destination must be rejected before running evaluators/materialization")

    monkeypatch.setattr(main, "_run_evaluators_over_suite", unexpected_work)
    monkeypatch.setattr("sloplab.mutations.materialize.materialize_suite", unexpected_work)
    if command in ("benchmark", "materialize"):
        source = tmp_path / "suite.yaml"
        source.write_text("name: test\ncorpus_root: missing\npolicies: {}\n", encoding="utf-8")
    else:
        source = tmp_path / "cases"
        source.mkdir()
        (source / "suite-index.jsonl").write_text("", encoding="utf-8")

    destination = out / subdir
    args = [command, str(source), "--out", str(destination)]
    if command != "materialize":
        args.extend(["--evaluator", "oracle"])
    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 1, result.output
    assert marker in result.output
    assert f"{out}: contains {marker}" in result.output
    assert "Choose a different output directory" in result.output
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    if subdir != ".":
        assert not destination.exists()


@pytest.mark.parametrize("command", ["benchmark", "evaluate", "materialize"])
@pytest.mark.parametrize("marker", [COMPLETION_FILE_NAME, IN_PROGRESS_FILE_NAME])
def test_legacy_writer_allows_sibling_of_marked_output(
    tmp_path: Path, command: str, marker: str
) -> None:
    marked = tmp_path / "out"
    marked.mkdir()
    (marked / marker).write_text("existing marker", encoding="utf-8")
    out = tmp_path / "out-sibling"
    corpus = tmp_path / "corpus"
    write_canonical_fixture(
        corpus, "demo", fixture_id="canonical-demo", title="Synthetic demo report"
    )
    source = tmp_path / "suite.yaml"
    source.write_text(
        f"name: test\nbase_seed: 0\ncorpus_root: {corpus}\n"
        "policies:\n  valid:\n    variants_per_fixture: 0\n    operators: [duplicate_sections]\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    if command == "evaluate":
        cases = tmp_path / "cases"
        prepared = runner.invoke(cli, ["materialize", str(source), "--out", str(cases)])
        assert prepared.exit_code == 0, prepared.output
        source = cases
    args = [command, str(source), "--out", str(out)]
    if command != "materialize":
        args.extend(["--evaluator", "oracle"])

    result = runner.invoke(cli, args)

    assert result.exit_code == 0, result.output
    assert out.is_dir()
    assert (marked / marker).read_text(encoding="utf-8") == "existing marker"
