"""Cross-run decision history: format, stability, robustness, and wiring.

History is run provenance, never evaluator input. These tests pin the on-disk
format, the one-entry-per-run aggregation, deterministic ordering, and the
"never crash a run" guarantees on both the read and the write path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sloplab.experiments.history import (
    DecisionHistory,
    HistoryEntry,
    entries_from_records,
    record_run,
)
from sloplab.models.enums import DIMENSIONS, Decision
from sloplab.models.evaluation import DimensionScores, EvaluationResult
from sloplab.models.run import CaseRecord

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_entry(
    *,
    ts: str = "2026-08-31T12:00:00Z",
    decision: str = "accept",
    model: str = "model-a",
    corpus_version: str = "0.2.2",
    run_id: str = "run-000000000001",
) -> HistoryEntry:
    return HistoryEntry(
        ts=ts,
        decision=decision,
        model=model,
        corpus_version=corpus_version,
        run_id=run_id,
    )


def make_record(
    case_id: str,
    decision: Decision,
    *,
    repeat: int = 0,
    failed: bool = False,
) -> CaseRecord:
    result = EvaluationResult(
        evaluator_name="spy",
        evaluator_version="0.0.0",
        case_id="case-deadbeefdeadbeef",
        decision=decision,
        confidence=0.5,
        dimensions=DimensionScores.from_dict(dict.fromkeys(DIMENSIONS, 0.5)),
        findings=[],
        rationale="",
        metadata={"failed": True} if failed else {},
    )
    record = CaseRecord.from_result(
        result,
        case_id=case_id,
        case_kind="canonical",
        report_class="valid",
        expected_decision=Decision.ACCEPT,
    )
    record.evaluation_metadata["repeat_index"] = repeat
    return record


# ---------------------------------------------------------------------------
# On-disk format and round-tripping
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_two_consecutive_runs_keep_both_entries(self, tmp_path: Path) -> None:
        path = tmp_path / "history.json"

        assert record_run(path, {"c-1": make_entry(run_id="run-1", ts="2026-08-31T12:00:00Z")})
        assert record_run(path, {"c-1": make_entry(run_id="run-2", ts="2026-08-31T13:00:00Z")})

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        assert [e["run_id"] for e in payload["cases"]["c-1"]] == ["run-1", "run-2"]
        assert set(payload["cases"]["c-1"][0]) == {
            "ts",
            "decision",
            "model",
            "corpus_version",
            "run_id",
        }

    def test_missing_file_loads_empty_without_warning(self, tmp_path: Path) -> None:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            history = DecisionHistory.load(tmp_path / "nope.json")
        assert history.case_ids() == []

    def test_save_is_atomic_and_leaves_no_temp_files(self, tmp_path: Path) -> None:
        path = tmp_path / "history.json"
        history = DecisionHistory()
        history.append("c-1", make_entry())
        history.save(path)
        assert [p.name for p in tmp_path.iterdir()] == ["history.json"]

    def test_true_case_id_is_the_key_not_the_opaque_handle(self, tmp_path: Path) -> None:
        from sloplab.scoring.harness import opaque_case_handle

        record = make_record("canonical-crypto-011", Decision.ACCEPT)
        entries = entries_from_records(
            [record],
            model="m",
            corpus_version="0.2.2",
            run_id="run-1",
            ts="2026-08-31T12:00:00Z",
        )
        assert set(entries) == {"canonical-crypto-011"}
        assert opaque_case_handle("canonical-crypto-011") not in entries


# ---------------------------------------------------------------------------
# Corruption and write failures never crash a run
# ---------------------------------------------------------------------------


class TestRobustness:
    @pytest.mark.parametrize(
        "content",
        [
            "{not json at all",
            "[]",
            '{"schema_version": 1}',
            '{"schema_version": 1, "cases": {"c-1": "not-a-list"}}',
            '{"schema_version": 1, "cases": {"c-1": [{"ts": "x"}]}}',
            '{"schema_version": 99, "cases": {}}',
        ],
    )
    def test_corrupt_file_warns_and_starts_fresh(self, tmp_path: Path, content: str) -> None:
        path = tmp_path / "history.json"
        path.write_text(content, encoding="utf-8")

        with pytest.warns(UserWarning, match="decision history"):
            history = DecisionHistory.load(path)
        assert history.case_ids() == []

    def test_corrupt_file_is_replaced_not_propagated(self, tmp_path: Path) -> None:
        path = tmp_path / "history.json"
        path.write_text("{broken", encoding="utf-8")

        with pytest.warns(UserWarning):
            assert record_run(path, {"c-1": make_entry()}) is True

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert list(payload["cases"]) == ["c-1"]

    def test_unwritable_path_warns_and_returns_false(self, tmp_path: Path) -> None:
        # A directory where the file should be: open() fails, the run must not.
        path = tmp_path / "history.json"
        path.mkdir()

        with pytest.warns(UserWarning, match="decision history"):
            assert record_run(path, {"c-1": make_entry()}) is False


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_timestamp_ties_order_deterministically(self, tmp_path: Path) -> None:
        ts = "2026-08-31T12:00:00Z"
        forward = DecisionHistory()
        for run_id in ("run-c", "run-a", "run-b"):
            forward.append("c-1", make_entry(ts=ts, run_id=run_id))

        backward = DecisionHistory()
        for run_id in ("run-b", "run-a", "run-c"):
            backward.append("c-1", make_entry(ts=ts, run_id=run_id))

        order = [e.run_id for e in forward.entries("c-1")]
        assert order == ["run-a", "run-b", "run-c"]
        assert [e.run_id for e in backward.entries("c-1")] == order

    def test_saved_bytes_are_insertion_order_independent(self, tmp_path: Path) -> None:
        ts = "2026-08-31T12:00:00Z"
        a, b = tmp_path / "a.json", tmp_path / "b.json"

        first = DecisionHistory()
        first.append("z-case", make_entry(ts=ts, run_id="run-2"))
        first.append("a-case", make_entry(ts=ts, run_id="run-1"))
        first.save(a)

        second = DecisionHistory()
        second.append("a-case", make_entry(ts=ts, run_id="run-1"))
        second.append("z-case", make_entry(ts=ts, run_id="run-2"))
        second.save(b)

        assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# stable_cases
# ---------------------------------------------------------------------------


class TestStableCases:
    def _hand_built(self) -> DecisionHistory:
        history = DecisionHistory()
        # stable: three consecutive accepts
        for i, run in enumerate(("run-1", "run-2", "run-3")):
            history.append("stable-case", make_entry(ts=f"2026-08-3{i + 1}T12:00:00Z", run_id=run))
        # drifted: two accepts then a reject
        for i, (run, decision) in enumerate(
            (("run-1", "accept"), ("run-2", "accept"), ("run-3", "reject"))
        ):
            history.append(
                "drifted-case",
                make_entry(ts=f"2026-08-3{i + 1}T12:00:00Z", run_id=run, decision=decision),
            )
        # settled: an early reject followed by three accepts -> stable at 3, not at 4
        for i, (run, decision) in enumerate(
            (
                ("run-0", "reject"),
                ("run-1", "accept"),
                ("run-2", "accept"),
                ("run-3", "accept"),
            )
        ):
            history.append(
                "settled-case",
                make_entry(ts=f"2026-08-2{i + 5}T12:00:00Z", run_id=run, decision=decision),
            )
        # too short: only two entries
        for i, run in enumerate(("run-1", "run-2")):
            history.append("short-case", make_entry(ts=f"2026-08-3{i + 1}T12:00:00Z", run_id=run))
        return history

    def test_expected_set_for_hand_built_history(self) -> None:
        history = self._hand_built()
        assert history.stable_cases() == {"stable-case", "settled-case"}

    def test_threshold_is_configurable(self) -> None:
        history = self._hand_built()
        assert history.stable_cases(threshold=2) == {
            "stable-case",
            "settled-case",
            "short-case",
        }
        assert history.stable_cases(threshold=4) == set()

    def test_model_filter_separates_evaluators_sharing_one_file(self) -> None:
        history = DecisionHistory()
        for i, run in enumerate(("run-1", "run-2", "run-3")):
            ts = f"2026-08-3{i + 1}T12:00:00Z"
            history.append("c-1", make_entry(ts=ts, run_id=run, model="a", decision="accept"))
            history.append("c-1", make_entry(ts=ts, run_id=run, model="b", decision="reject"))

        # Interleaved, the case looks unstable; per model it is perfectly stable.
        assert history.stable_cases() == set()
        assert history.stable_cases(model="a") == {"c-1"}
        assert history.stable_cases(model="b") == {"c-1"}

    def test_corpus_version_filter(self) -> None:
        history = DecisionHistory()
        for i, (run, version, decision) in enumerate(
            (
                ("run-1", "0.2.1", "accept"),
                ("run-2", "0.2.2", "reject"),
                ("run-3", "0.2.2", "reject"),
                ("run-4", "0.2.2", "reject"),
            )
        ):
            history.append(
                "c-1",
                make_entry(
                    ts=f"2026-08-2{i + 5}T12:00:00Z",
                    run_id=run,
                    corpus_version=version,
                    decision=decision,
                ),
            )
        assert history.stable_cases(corpus_version="0.2.2") == {"c-1"}
        assert history.stable_cases(corpus_version="0.2.1") == set()

    def test_invalid_threshold_rejected(self) -> None:
        with pytest.raises(ValueError):
            DecisionHistory().stable_cases(threshold=0)


# ---------------------------------------------------------------------------
# Aggregation: one entry per (case, run)
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_repeats_collapse_to_one_entry_per_case(self) -> None:
        records = [
            make_record("c-1", Decision.ACCEPT, repeat=0),
            make_record("c-1", Decision.ACCEPT, repeat=1),
            make_record("c-1", Decision.REJECT, repeat=2),
            make_record("c-2", Decision.REJECT, repeat=0),
        ]
        entries = entries_from_records(
            records,
            model="m",
            corpus_version="0.2.2",
            run_id="run-1",
            ts="2026-08-31T12:00:00Z",
        )
        assert set(entries) == {"c-1", "c-2"}
        assert entries["c-1"].decision == "accept"  # majority over repeats
        assert entries["c-2"].decision == "reject"

    def test_failed_evaluations_are_excluded(self) -> None:
        records = [
            make_record("c-1", Decision.ACCEPT, repeat=0, failed=True),
            make_record("c-1", Decision.REJECT, repeat=1),
            make_record("c-2", Decision.ACCEPT, repeat=0, failed=True),
        ]
        entries = entries_from_records(
            records,
            model="m",
            corpus_version="0.2.2",
            run_id="run-1",
            ts="2026-08-31T12:00:00Z",
        )
        assert set(entries) == {"c-1"}
        assert entries["c-1"].decision == "reject"

    def test_majority_ties_break_deterministically(self) -> None:
        records = [
            make_record("c-1", Decision.REJECT, repeat=0),
            make_record("c-1", Decision.ACCEPT, repeat=1),
        ]
        reversed_records = list(reversed(records))
        kwargs: dict[str, Any] = {
            "model": "m",
            "corpus_version": "0.2.2",
            "run_id": "run-1",
            "ts": "2026-08-31T12:00:00Z",
        }
        first = entries_from_records(records, **kwargs)["c-1"].decision
        second = entries_from_records(reversed_records, **kwargs)["c-1"].decision
        assert first == second == "accept"  # sorted decision value wins the tie
