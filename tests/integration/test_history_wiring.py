"""Cross-run history wiring: the pilot and the benchmark CLI both record it.

History is written only after a run's own artifacts are on disk, and never from
an evaluation path. These tests pin that ordering, the accumulation across two
runs, and the fact that enabling history changes no existing output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from sloplab.cli.main import cli
from sloplab.experiments.config import LLMPilotConfig
from sloplab.experiments.history import DecisionHistory
from sloplab.experiments.pilot import run_llm_pilot
from sloplab.experiments.runner import load_pilot_config
from tests.integration.test_pipeline import build_workspace
from tests.unit.test_llm_pilot import (
    PILOT_CONFIG,
    VALID_PAYLOAD,
    StaticResponder,
    canonical_cases,
    make_evaluator,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pilot_config(max_cases: int = 2, repeats: int = 3) -> LLMPilotConfig:
    config: LLMPilotConfig = load_pilot_config(PILOT_CONFIG)
    config.max_cases = max_cases
    config.repeats = repeats
    return config


class TestPilotWiring:
    def test_two_consecutive_pilot_runs_accumulate(self, tmp_path: Path, monkeypatch: Any) -> None:
        config = _pilot_config()
        monkeypatch.setenv(config.model_env, "test-model-x")
        history_path = tmp_path / "decision-history.json"
        cases = canonical_cases(2)

        run_ids = []
        for index in range(2):
            evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))
            result = run_llm_pilot(
                config,
                evaluator,
                cases,
                REPO_ROOT,
                tmp_path / f"out-{index}",
                history_path=history_path,
            )
            run_ids.append(json.loads(result.manifest_path.read_text())["run_id"])

        history = DecisionHistory.load(history_path)
        assert len(history.case_ids()) == 2
        for case_id in history.case_ids():
            entries = history.entries(case_id)
            # Three repeats per run collapse to one entry per run, not three.
            assert len(entries) == 2, entries
            assert {e.model for e in entries} == {"test-model-x"}
            assert all(e.run_id for e in entries)

    def test_repeats_do_not_satisfy_stability_within_one_run(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        config = _pilot_config(max_cases=1, repeats=3)
        monkeypatch.setenv(config.model_env, "test-model-x")
        history_path = tmp_path / "decision-history.json"

        evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        run_llm_pilot(
            config,
            evaluator,
            canonical_cases(1),
            REPO_ROOT,
            tmp_path / "out",
            history_path=history_path,
        )
        history = DecisionHistory.load(history_path)
        assert history.stable_cases(threshold=3) == set()

    def test_history_is_opt_in_and_changes_no_existing_output(self, tmp_path: Path) -> None:
        config = _pilot_config(max_cases=1, repeats=2)
        cases = canonical_cases(1)

        evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        without = run_llm_pilot(config, evaluator, cases, REPO_ROOT, tmp_path / "a")

        evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        with_history = run_llm_pilot(
            config,
            evaluator,
            cases,
            REPO_ROOT,
            tmp_path / "b",
            history_path=tmp_path / "decision-history.json",
        )

        assert without.records_path.read_bytes() == with_history.records_path.read_bytes()
        assert not (tmp_path / "a" / "decision-history.json").exists()
        assert (tmp_path / "decision-history.json").exists()

    def test_unwritable_history_does_not_fail_the_run(self, tmp_path: Path) -> None:
        config = _pilot_config(max_cases=1, repeats=1)
        blocked = tmp_path / "decision-history.json"
        blocked.mkdir()

        evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))
        result = run_llm_pilot(
            config,
            evaluator,
            canonical_cases(1),
            REPO_ROOT,
            tmp_path / "out",
            history_path=blocked,
        )
        assert result.evaluations_attempted == 1
        assert result.records_path.exists() and result.manifest_path.exists()


class TestBenchmarkCliWiring:
    def test_benchmark_history_flag_records_per_evaluator(
        self, tmp_path: Path, make_fixture: Any
    ) -> None:
        workspace = build_workspace(tmp_path, make_fixture)
        history_path = workspace / "decision-history.json"

        for index in range(2):
            result = CliRunner().invoke(
                cli,
                [
                    "benchmark",
                    str(workspace / "suite.yaml"),
                    "--evaluator",
                    "oracle",
                    "--evaluator",
                    "rules-baseline",
                    "--out",
                    str(workspace / f"results-{index}"),
                    "--history",
                    str(history_path),
                ],
            )
            assert result.exit_code == 0, result.output

        history = DecisionHistory.load(history_path)
        assert history.case_ids()

        # Every entry is traceable to the run.jsonl that produced it.
        recorded_run_ids = {
            entry.run_id for cid in history.case_ids() for entry in history.entries(cid)
        }
        metadata_run_ids = {
            json.loads(path.read_text(encoding="utf-8").splitlines()[0])["run_id"]
            for path in sorted(workspace.glob("results-*/run.jsonl"))
        }
        assert recorded_run_ids <= metadata_run_ids

        models = {entry.model for cid in history.case_ids() for entry in history.entries(cid)}
        assert {m.split("@", 1)[0] for m in models} == {"oracle", "rules-baseline"}

        # Deterministic evaluators repeat themselves, so every case is stable per
        # model at threshold 2 - but only once the model filter is applied.
        oracle_model = next(m for m in models if m.startswith("oracle@"))
        assert history.stable_cases(threshold=2, model=oracle_model) == set(history.case_ids())

    def test_benchmark_without_flag_writes_no_history(
        self, tmp_path: Path, make_fixture: Any
    ) -> None:
        workspace = build_workspace(tmp_path, make_fixture)
        result = CliRunner().invoke(
            cli,
            [
                "benchmark",
                str(workspace / "suite.yaml"),
                "--evaluator",
                "oracle",
                "--out",
                str(workspace / "results"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert not list(workspace.rglob("decision-history.json"))
