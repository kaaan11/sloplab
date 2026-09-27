"""Issue #60: suite-index header corpus_root must be relative, reader stays compatible.

Contract:
- Materialization writes the corpus location in the suite-index header relative
  to the materialization output root (the suite directory). The two committed
  CLI writers (``materialize``/``benchmark``, src/sloplab/cli/main.py:149,417)
  already resolve the corpus root, so they hand over the resolved path; the
  header writer relocates it against the output root.
- ``_resolve_suite_index`` (src/sloplab/cli/main.py) resolves a relative corpus
  root against the current working directory and then the index location and
  its ancestors, so a header written relative to the materialized root is
  consumed by exactly the writer's inverse anchor. Old bundles with absolute
  paths keep evaluating (backward compatibility).
- No committed bundle may carry a machine-specific absolute corpus path.
- Hash analysis: the header corpus_root enters no hash. Input identity hashes
  report/target text only (src/sloplab/experiments/input_identity.py), the
  execution recipe carries ``locations`` openly and "never hashed into
  identities" (src/sloplab/experiments/resolved_recipe.py:69,322-325), and the
  run manifest's ``suite_hash`` is a file digest that a header change merely
  re-computes -- no committed test pins its value (grep tests/ for
  "suite_hash": counts and equality in reruns only).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.mutations.materialize import SUITE_INDEX_NAME, load_suite_config
from tests._helpers import write_canonical_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]

CORPUS_DIRNAME = "synthetic-corpus"


def _build_corpus(corpus_dir: Path) -> None:
    """Two valid + one review fixture: deterministic, fully synthetic corpus."""
    write_canonical_fixture(
        corpus_dir, "a", fixture_id="canonical-a", title="Alpha report", report_class="valid"
    )
    write_canonical_fixture(
        corpus_dir, "b", fixture_id="canonical-b", title="Bravo report", report_class="valid"
    )
    write_canonical_fixture(
        corpus_dir, "c", fixture_id="canonical-c", title="Charlie report", report_class="review"
    )


def _suite_yaml(workspace: Path) -> Path:
    """Suite YAML at ``workspace/suite.yaml`` with a relative corpus_root."""
    import yaml

    suite = {
        "name": "rel-root-suite",
        "base_seed": 7,
        "corpus_root": CORPUS_DIRNAME,
        "include_canonical_cases": True,
        "policies": {
            "valid": {"variants_per_fixture": 1, "operators": ["professionalize_language"]},
            "review": {"variants_per_fixture": 1, "operators": ["add_irrelevant_detail"]},
            "invalid": {"variants_per_fixture": 0, "operators": ["impact_inflation"]},
            "presentation_pair": {"variants_per_fixture": 0, "operators": ["impact_inflation"]},
        },
    }
    path = workspace / "suite.yaml"
    path.write_text(yaml.safe_dump(suite), encoding="utf-8")
    return path


def _workspace(root: Path, name: str) -> Path:
    """One portable workspace: <root>/synthetic-corpus + suite.yaml."""
    workspace = root / name
    _build_corpus(workspace / CORPUS_DIRNAME)
    _suite_yaml(workspace)
    return workspace


def _read_header(path: Path) -> dict[str, Any]:
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert isinstance(header, dict)
    return header


def test_same_suite_in_two_directories_byte_identical_headers(tmp_path: Path) -> None:
    """Acceptance 1: identical relative layout -> byte-identical suite-index
    headers regardless of the machine directories they live under."""
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    ws_a = _workspace(tmp_path, "workspace-1")
    ws_b = _workspace(tmp_path, "workspace-2")
    out_a, out_b = ws_a / "suite-out", ws_b / "suite-out"
    for workspace, out in ((ws_a, out_a), (ws_b, out_b)):
        config = load_suite_config(workspace / "suite.yaml")
        canonical, _derived = discover_fixtures(workspace / CORPUS_DIRNAME)
        materialize_suite(config, canonical, out, corpus_root_resolved=workspace / CORPUS_DIRNAME)
    assert (out_a / SUITE_INDEX_NAME).read_bytes() == (out_b / SUITE_INDEX_NAME).read_bytes()
    header = _read_header(out_a / SUITE_INDEX_NAME)
    assert header["corpus_root"] == f"../{CORPUS_DIRNAME}"
    assert not Path(header["corpus_root"]).is_absolute()


def test_both_relative_and_absolute_header_bundles_readable_by_evaluate(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Acceptance 2: a relative-header bundle and a hand-built legacy
    absolute-header bundle both evaluate end-to-end."""
    workspace = tmp_path / "proj"
    _build_corpus(workspace / CORPUS_DIRNAME)
    _suite_yaml(workspace)
    corpus_root = (workspace / CORPUS_DIRNAME).resolve()
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    config = load_suite_config(workspace / "suite.yaml")
    canonical, _derived = discover_fixtures(corpus_root)

    bundle_rel = tmp_path / "bundle-relative"
    materialize_suite(config, canonical, bundle_rel, corpus_root_resolved=corpus_root)
    header = _read_header(bundle_rel / SUITE_INDEX_NAME)
    assert not Path(header["corpus_root"]).is_absolute()
    assert (bundle_rel / header["corpus_root"]).is_dir()

    # Legacy shape (#60 regression guard for backward compatibility): copy the
    # fresh bundle and overwrite the header with the pre-#60 absolute form.
    bundle_abs = tmp_path / "bundle-absolute"
    shutil.copytree(bundle_rel, bundle_abs)
    lines = (bundle_abs / SUITE_INDEX_NAME).read_text(encoding="utf-8").splitlines()
    legacy = json.loads(lines[0])
    legacy["corpus_root"] = str(corpus_root)
    lines[0] = json.dumps(legacy, sort_keys=True)
    (bundle_abs / SUITE_INDEX_NAME).write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )
    assert _read_header(bundle_abs / SUITE_INDEX_NAME)["corpus_root"] == str(corpus_root)

    runner = CliRunner()
    for bundle in (bundle_rel, bundle_abs):
        eval_out = tmp_path / f"eval-{bundle.name}"
        result = runner.invoke(
            cli,
            [
                "evaluate",
                str(bundle),
                "--evaluator",
                "rules-baseline",
                "--out",
                str(eval_out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert (eval_out / "run.jsonl").is_file()


def test_committed_bundles_contain_no_absolute_corpus_root() -> None:
    """Acceptance 3: no committed bundle ships a machine-specific path."""
    committed = [
        REPO_ROOT / "experiments/results/deterministic/study-v02/suite-index.jsonl",
        REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl",
    ]
    for index in committed:
        header = _read_header(index)
        value = header["corpus_root"]
        assert not Path(value).is_absolute(), f"{index}: absolute corpus_root {value!r}"


def test_relative_header_resolves_from_neighbouring_cwd(tmp_path: Path, monkeypatch: Any) -> None:
    """The relative header resolves against the index location, not only cwd.

    ``evaluate`` invoked from an unrelated cwd must find the corpus next to the
    bundle (the index-anchor arm of ``_resolve_suite_index``).
    """
    workspace = tmp_path / "proj"
    _build_corpus(workspace / CORPUS_DIRNAME)
    _suite_yaml(workspace)
    corpus_root = (workspace / CORPUS_DIRNAME).resolve()
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    config = load_suite_config(workspace / "suite.yaml")
    canonical, _derived = discover_fixtures(corpus_root)
    bundle = tmp_path / "bundle"
    materialize_suite(config, canonical, bundle, corpus_root_resolved=corpus_root)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["evaluate", str(bundle), "--evaluator", "rules-baseline", "--out", str(elsewhere / "o")],
    )
    monkeypatch.chdir(tmp_path)
    assert result.exit_code == 0, result.output
    assert (elsewhere / "o" / "run.jsonl").is_file()


def test_missing_relative_corpus_root_still_fails_loudly(tmp_path: Path) -> None:
    """A relative header pointing nowhere must keep the actionable error (#53)."""
    header_text = (
        json.dumps(
            {
                "record_type": "suite_header",
                "suite_name": "ghost",
                "corpus_root": "corpus/does-not-exist",
                "base_seed": 1,
                "generator_version": "0.2.2",
            },
            sort_keys=True,
        )
        + "\n"
        + json.dumps(
            {
                "record_type": "suite_case",
                "case_id": "canonical-a",
                "kind": "canonical",
                "parent_id": None,
                "operator": None,
                "expected_decision": "accept",
                "report_class": "valid",
                "manifest_path": None,
            },
            sort_keys=True,
        )
        + "\n"
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / SUITE_INDEX_NAME).write_text(header_text, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["evaluate", str(bundle), "--evaluator", "rules-baseline", "--out", str(tmp_path / "o")],
    )
    assert result.exit_code != 0
    assert "corpus_root" in result.output
