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


def test_pilot_records_the_real_case_kind(tmp_path: Path) -> None:
    """A pilot that labels every record canonical hides the cases it evaluated.

    The delimited arm exists to be measured against injected cases; those are
    mutated, and a hardcoded case_kind made them invisible to every metric that
    selects on it.
    """
    from sloplab.experiments.pilot import run_llm_pilot
    from sloplab.experiments.runner import load_pilot_config
    from sloplab.scoring.harness import build_cases
    from tests.unit.test_llm_pilot import VALID_PAYLOAD, StaticResponder, make_evaluator

    example = REPO_ROOT / "benchmarks/results/v1-core-example"
    cases = build_cases(example / "suite-index.jsonl", REPO_ROOT / "corpus", example)
    mutated = [c for c in cases if c.kind == "mutated"][:1]
    assert mutated, "the reference bundle should hold mutated cases"

    config = load_pilot_config(REPO_ROOT / "experiments/configs/llm-pilot-v0.2.yaml")
    config.max_cases = 1
    config.repeats = 1
    evaluator, _client = make_evaluator(StaticResponder(VALID_PAYLOAD))

    result = run_llm_pilot(config, evaluator, mutated, REPO_ROOT, tmp_path / "out")
    records = [json.loads(line) for line in result.records_path.read_text().splitlines()]
    assert records
    assert all(r["case_kind"] == "mutated" for r in records), records
    assert all(r["operator"] for r in records)


def test_benchmark_history_reports_the_write(tmp_path: Path) -> None:
    """record_runs signals failure only by warning, which may be suppressed."""
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(SUITE),
            "--evaluator",
            "oracle",
            "--out",
            str(tmp_path / "out"),
            "--history",
            str(tmp_path / "h.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "decision history: recorded" in result.output


def test_duplicate_evaluator_writes_one_history_entry(tmp_path: Path) -> None:
    """Click accepts a repeated --evaluator; two entries would let two runs
    satisfy stable_cases(threshold=3)."""
    from sloplab.experiments.history import DecisionHistory

    history = tmp_path / "h.json"
    result = CliRunner().invoke(
        cli,
        [
            "benchmark",
            str(SUITE),
            "--evaluator",
            "rules-baseline",
            "--evaluator",
            "rules-baseline",
            "--out",
            str(tmp_path / "out"),
            "--history",
            str(history),
        ],
    )
    assert result.exit_code == 0, result.output

    loaded = DecisionHistory.load(history)
    case_id = loaded.case_ids()[0]
    assert len(loaded.entries(case_id)) == 1


class TestMeteredDispatchEndToEnd:
    """The delimited arm, driven through the real runner with a fake transport.

    Two rounds of review found defects that only appear when the path is
    executed rather than read: code that exists but can never run. This drives
    scripts/llm_bench.py end to end offline.
    """

    @staticmethod
    def _suite_index(tmp_path: Path) -> Path:
        out = tmp_path / "suite"
        result = CliRunner().invoke(
            cli, ["benchmark", str(SUITE), "--evaluator", "oracle", "--out", str(out)]
        )
        assert result.exit_code == 0, result.output
        return out / "suite-index.jsonl"

    @staticmethod
    def _run(index: Path, out: Path, monkeypatch: Any, **flags: str) -> list[dict[str, Any]]:
        import importlib.util
        import os

        from sloplab.evaluators.llm.adapter import LLMResponse

        spec = importlib.util.spec_from_file_location(
            "llm_bench_e2e", REPO_ROOT / "scripts" / "llm_bench.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        payload = json.dumps(
            {
                "decision": "accept",
                "confidence": 0.8,
                "dimensions": dict.fromkeys(
                    (
                        "reproducibility",
                        "evidence_completeness",
                        "claim_evidence_consistency",
                        "impact_calibration",
                        "scope_consistency",
                    ),
                    0.7,
                ),
                "findings": [],
                "rationale": "ok",
            }
        )

        class FakeHttp:
            prompts: list[str] = []

            def __init__(self, **_kwargs: Any) -> None:
                pass

            def complete(self, prompt: str) -> LLMResponse:
                FakeHttp.prompts.append(prompt)
                return LLMResponse(text=payload, latency_ms=1)

        monkeypatch.setattr(module, "HttpLLMClient", FakeHttp)
        for name, value in {
            "SLOPLAB_LLM_API_KEY": "k",
            "SLOPLAB_LLM_MODEL": "fake-model",
            "SLOPLAB_LLM_ENDPOINT": "http://localhost/none",
        }.items():
            monkeypatch.setenv(name, value)

        args = ["--suite-index", str(index), "--out", str(out)]
        for flag, value in flags.items():
            args += [f"--{flag.replace('_', '-')}", value]
        assert module.main(args) == 0
        assert FakeHttp.prompts, "no request was dispatched"
        assert "--- BEGIN UNTRUSTED REPORT ---" in FakeHttp.prompts[0]
        _ = os
        return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    def test_delimited_arm_produces_injected_records(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        records = self._run(
            self._suite_index(tmp_path),
            tmp_path / "res.jsonl",
            monkeypatch,
            case_kind="mutated",
            defense="delimited",
            max_cases="6",
            repeats="1",
        )
        assert records
        assert {r["case_kind"] for r in records} == {"mutated"}
        assert all(r["operator"] for r in records)
        assert {r["evaluation_metadata"]["defense"] for r in records} == {"delimited"}

    def test_metric_reports_a_delimited_arm(self, tmp_path: Path, monkeypatch: Any) -> None:
        """No committed path could produce this key before the case-kind flag."""
        from sloplab.models.run import CaseRecord
        from sloplab.scoring.comparison import injection_success_by_arm, injection_targets

        records = self._run(
            self._suite_index(tmp_path),
            tmp_path / "res.jsonl",
            monkeypatch,
            case_kind="mutated",
            defense="delimited",
            max_cases="6",
            repeats="1",
        )
        outcomes = injection_success_by_arm(
            [CaseRecord.model_validate(r) for r in records], injection_targets()
        )
        assert set(outcomes) == {"delimited"}
