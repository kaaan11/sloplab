"""Failure-only sidecars for normal evaluate/benchmark runs.

Rows reuse the study ledger's schema_version/status/case_id/evaluator_name/
repeat_index/error_kind fields. Error kinds come from EvaluationFailure, not a
second taxonomy. No unchecked detail, prompt, exception text or credentials are
serialized. Successful scoring observations remain exclusively in run.jsonl.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sloplab.evaluators.llm.failures import ERROR_KINDS
from sloplab.models.run import CaseRecord, RunMetadata
from sloplab.scoring.harness import CaseOutcome

OUTCOMES_NAME = "outcomes.jsonl"
OUTCOMES_HASH_KEY = "outcomes_sha256"


class OutcomeLedgerError(ValueError):
    """Malformed or mismatched outcome provenance must not be guessed."""


def safe_error_kind(kind: str) -> str:
    # 'unknown' is the existing failure_class fallback. Never persist arbitrary
    # external strings (they may contain secrets) as an alleged failure code.
    return kind if kind in ERROR_KINDS else "unknown"


def write_failure_outcomes(path: Path, failed: list[CaseOutcome]) -> str:
    """Always write a sidecar, even empty; return its SHA-256 to bind in metadata."""
    lines: list[str] = []
    for outcome in sorted(failed, key=lambda o: (o.evaluator_name, o.case_id)):
        if outcome.status != "failed" or outcome.failure is None:
            raise OutcomeLedgerError("Only typed failed outcomes belong in the failure sidecar.")
        lines.append(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "failed",
                    "case_id": outcome.case_id,
                    "evaluator_name": outcome.evaluator_name,
                    "repeat_index": 0,
                    "error_kind": safe_error_kind(outcome.failure.error_kind),
                },
                sort_keys=True,
            )
            + "\n"
        )
    content = "".join(lines).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class FailureRow:
    case_id: str
    evaluator_name: str
    error_kind: str
    repeat_index: int = 0


@dataclass(frozen=True)
class FailureLedger:
    available: bool
    bound: bool
    failures: tuple[FailureRow, ...] = ()


def read_failure_outcomes(
    run_path: Path, metadata: RunMetadata | None, records: list[CaseRecord]
) -> FailureLedger:
    """Read only real rows; missing legacy provenance means unknown, never zero.

    New normal runs bind sidecar bytes in their metadata. Legacy sidecars remain
    readable but are explicitly unbound. Invalid schema/duplicates/inconsistent
    success-vs-failure identities are errors, not silently dropped rows.
    """
    expected = metadata.suite_config.get(OUTCOMES_HASH_KEY) if metadata else None
    path = run_path.parent / OUTCOMES_NAME
    if not path.exists():
        if expected is not None:
            raise OutcomeLedgerError("Missing outcomes.jsonl required by run metadata; restore it.")
        return FailureLedger(available=False, bound=False)
    content = path.read_bytes()
    if expected is not None and expected != hashlib.sha256(content).hexdigest():
        raise OutcomeLedgerError("outcomes.jsonl hash mismatch; use the sidecar from this run.")
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise OutcomeLedgerError("outcomes.jsonl must be UTF-8.") from exc
    seen: set[tuple[str, str, int]] = set()
    successes = {(r.evaluator_name, r.case_id) for r in records}
    evaluator_names = {e.name for e in metadata.evaluators} if metadata else set()
    failures: list[FailureRow] = []
    for number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError as exc:
            raise OutcomeLedgerError(f"Invalid outcomes.jsonl JSON at line {number}.") from exc
        if not isinstance(row, dict) or row.get("schema_version") != 1:
            raise OutcomeLedgerError(f"Unsupported outcomes.jsonl schema at line {number}.")
        name, case = row.get("evaluator_name"), row.get("case_id")
        repeat, status = row.get("repeat_index", 0), row.get("status")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(case, str)
            or not case.strip()
            or type(repeat) is not int
            or repeat < 0
            or status not in ("success", "failed")
        ):
            raise OutcomeLedgerError(f"Invalid outcome identity/status at line {number}.")
        key = (name, case, repeat)
        if key in seen:
            raise OutcomeLedgerError(f"Duplicate outcome at line {number}.")
        seen.add(key)
        if metadata is not None and name not in evaluator_names:
            raise OutcomeLedgerError(
                f"Outcome evaluator absent from run metadata at line {number}."
            )
        if status == "failed":
            if (name, case) in successes:
                raise OutcomeLedgerError(f"Outcome conflicts with a scored case at line {number}.")
            kind = row.get("error_kind")
            if not isinstance(kind, str) or not kind:
                raise OutcomeLedgerError(f"Failed outcome missing error_kind at line {number}.")
            failures.append(FailureRow(case, name, safe_error_kind(kind), repeat))
    return FailureLedger(
        available=True,
        bound=expected is not None,
        failures=tuple(
            sorted(failures, key=lambda f: (f.evaluator_name, f.case_id, f.repeat_index))
        ),
    )
