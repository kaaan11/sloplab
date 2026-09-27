"""Issue #60: suite-index header corpus_root must be relative, reader stays compatible.

Contract:
- Materialization writes the corpus location in the suite-index header relative
  to the materialization output root (the suite directory). The two committed
  CLI writers (``materialize``/``benchmark``, src/sloplab/cli/main.py:149,417)
  already resolve the corpus root, so they hand over the resolved path; the
  header writer relocates it against the output root.
- ``_resolve_suite_index`` (src/sloplab/cli/main.py) resolves a relative corpus
  root against the index location and its ancestors first, then falls back to
  the current working directory as a last resort, so a header written relative
  to the materialized root is consumed by exactly the writer's inverse anchor
  and legacy relative-to-cwd bundles keep evaluating (backward compatibility).
  Old bundles with absolute paths keep evaluating too.
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


def test_committed_results_contain_no_machine_paths() -> None:
    """Acceptance 3 (revision F2): no committed result file ships a machine path.

    Every tracked file under ``experiments/results/`` and ``benchmarks/results/``
    must be free of ``/tmp/``, ``/home/``, ``.scratch`` and Windows drive-letter
    paths; the two bundle headers must additionally carry a relative corpus root.
    """
    import re

    drive_letter = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
    roots = [REPO_ROOT / "experiments/results", REPO_ROOT / "benchmarks/results"]
    checked = 0
    for root in roots:
        assert root.is_dir(), f"missing committed results root {root}"
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in ("/tmp/", "/home/", ".scratch"):
                assert needle not in text, f"{path}: machine path marker {needle!r}"
            assert drive_letter.search(text) is None, f"{path}: drive-letter path"
            checked += 1
    assert checked > 0
    for index in (
        REPO_ROOT / "experiments/results/deterministic/study-v02/suite-index.jsonl",
        REPO_ROOT / "benchmarks/results/v1-core-example/suite-index.jsonl",
    ):
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


def test_legacy_relative_to_cwd_header_still_resolves(tmp_path: Path, monkeypatch: Any) -> None:
    """F5: a legacy bundle whose relative header only resolves from the cwd.

    Pre-#60 direct-API bundles could carry a corpus_root relative to the
    working directory. The reader must keep resolving those: index anchors
    first, then the cwd as a last resort.
    """
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    workspace = tmp_path / "workdir"
    workspace.mkdir()
    _build_corpus(workspace / CORPUS_DIRNAME)
    corpus_root = (workspace / CORPUS_DIRNAME).resolve()

    config = load_suite_config(_suite_yaml(workspace))
    canonical, _derived = discover_fixtures(corpus_root)
    bundle = tmp_path / "bundle"
    materialize_suite(config, canonical, bundle, corpus_root_resolved=corpus_root)

    # Rewrite the header to the legacy cwd-relative shape: no index ancestor
    # contains this corpus, only the working directory does.
    lines = (bundle / SUITE_INDEX_NAME).read_text(encoding="utf-8").splitlines()
    legacy = json.loads(lines[0])
    legacy["corpus_root"] = CORPUS_DIRNAME
    lines[0] = json.dumps(legacy, sort_keys=True)
    (bundle / SUITE_INDEX_NAME).write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    assert _read_header(bundle / SUITE_INDEX_NAME)["corpus_root"] == CORPUS_DIRNAME

    monkeypatch.chdir(workspace)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["evaluate", str(bundle), "--evaluator", "rules-baseline", "--out", str(workspace / "o")],
    )
    monkeypatch.chdir(tmp_path)
    assert result.exit_code == 0, result.output
    assert (workspace / "o" / "run.jsonl").is_file()


def test_cwd_is_last_resort_after_index_anchor(tmp_path: Path, monkeypatch: Any) -> None:
    """F5 guard: a same-named directory under cwd must not shadow the bundle's corpus."""
    from sloplab.cli.main import _resolve_suite_index
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    workspace = tmp_path / "proj"
    _build_corpus(workspace / CORPUS_DIRNAME)
    _suite_yaml(workspace)
    corpus_root = (workspace / CORPUS_DIRNAME).resolve()
    config = load_suite_config(workspace / "suite.yaml")
    canonical, _derived = discover_fixtures(corpus_root)
    bundle = workspace / "bundle"
    materialize_suite(config, canonical, bundle, corpus_root_resolved=corpus_root)

    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "bait.txt").write_text("shadow corpus", encoding="utf-8")
    monkeypatch.chdir(decoy)
    _index, resolved, _materialized = _resolve_suite_index(str(bundle))
    monkeypatch.chdir(tmp_path)
    assert resolved.resolve() == corpus_root


def test_relative_config_corpus_root_resolved_before_header(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """F4: a relative config.corpus_root is made absolute before the header math.

    Direct-API callers (corpus_root_resolved=None) with a relative suite-config
    string must still get a resolvable header, not one anchored to whatever cwd
    happened to be active.
    """
    from sloplab.corpus.loader import discover_fixtures
    from sloplab.mutations.materialize import materialize_suite

    workspace = tmp_path / "proj"
    _build_corpus(workspace / CORPUS_DIRNAME)
    _suite_yaml(workspace)
    monkeypatch.chdir(workspace)
    config = load_suite_config(workspace / "suite.yaml")
    canonical, _derived = discover_fixtures(Path(CORPUS_DIRNAME))
    bundle = workspace / "bundle"
    materialize_suite(config, canonical, bundle, corpus_root_resolved=None)
    header = _read_header(bundle / SUITE_INDEX_NAME)
    assert header["corpus_root"] == f"../{CORPUS_DIRNAME}"
    assert (bundle / header["corpus_root"]).is_dir()


def test_run_jsonl_index_provenance_is_bundle_relative(tmp_path: Path) -> None:
    """F2: benchmark records suite_config.index relative to the output bundle."""
    workspace = _workspace(tmp_path, "proj")
    out = tmp_path / "bench-out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "benchmark",
            str(workspace / "suite.yaml"),
            "--evaluator",
            "rules-baseline",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    header = json.loads((out / "run.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert header["suite_config"]["index"] == "suite-index.jsonl"


def test_execution_recipe_locations_are_portable(tmp_path: Path, monkeypatch: Any) -> None:
    """F2: execution-recipe locations stay machine-portable (cwd-relative)."""
    import yaml

    from sloplab.experiments.runner import load_study_config
    from sloplab.experiments.study import run_deterministic_study

    workspace = _workspace(tmp_path, "proj")
    study = {
        "name": "recipe-portability",
        "suite": {"config_path": "suite.yaml", "corpus_root": CORPUS_DIRNAME},
        "base_seed": 7,
        "evaluators": [{"name": "rules-baseline"}],
        "analysis": {"bootstrap_resamples": 100, "bootstrap_ci": 0.9},
    }
    (workspace / "study.yaml").write_text(yaml.safe_dump(study), encoding="utf-8")
    monkeypatch.chdir(workspace)
    config = load_study_config(workspace / "study.yaml")
    result = run_deterministic_study(config, workspace / "study.yaml", workspace / "study-out")
    recipe = json.loads(
        (workspace / "study-out" / "execution-recipe.json").read_text(encoding="utf-8")
    )
    assert recipe["locations"]["suite_config_path"] == "suite.yaml"
    assert recipe["locations"]["corpus_root"] == CORPUS_DIRNAME
    assert result.recipe.locations is not None
    assert result.recipe.locations.suite_config_path == "suite.yaml"
