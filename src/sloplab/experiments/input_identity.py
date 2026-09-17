"""Path-independent input identity for deterministic studies (E1d).

Derives stable identities from the in-memory snapshots built by
:func:`sloplab.scoring.harness.build_cases` — never from disk paths, timestamps,
or evaluation outputs. The written ``input-identity.json`` lets later runs tell
"same case_id, different text/targets" apart across experiments without changing
case_id, seeds, records, or analysis behavior.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sloplab.scoring.harness import SuiteCase

SCHEMA_VERSION = 1
IDENTITY_FILE_NAME = "input-identity.json"
_IDENTITY_DOMAIN = "sloplab.input"


class InputIdentityError(ValueError):
    """A case cannot contribute to the input identity (no snapshot, bad target)."""


def _canonical_bytes(payload: Any) -> bytes:
    return canonical_json_bytes(payload)


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    """Deterministic JSON encoding for hashing (see schema-contract.md).

    ``sort_keys`` makes dict key order irrelevant; array order (case order)
    still matters. ``allow_nan=False`` rejects NaN/Infinity loudly instead of
    silently emitting non-standard tokens. Shared by input and recipe identities.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def tagged_digest(
    identity_type: str, fields: dict[str, Any], *, domain: str = _IDENTITY_DOMAIN
) -> str:
    """SHA-256 over a domain/type/version-enveloped object with canonical encoding."""
    return hashlib.sha256(
        canonical_json_bytes(_tagged_object(identity_type, fields, domain=domain))
    ).hexdigest()


def _tagged_object(
    identity_type: str, fields: dict[str, Any], *, domain: str = _IDENTITY_DOMAIN
) -> dict[str, Any]:
    """Wrap hash inputs with an explicit domain/type/version envelope.

    Distinct object types can never collapse into the same identity field by
    accident, even if their inner fields coincided.
    """
    return {
        "domain": domain,
        "type": identity_type,
        "version": 1,
        **fields,
    }


def report_hash(raw_text: str) -> str:
    """SHA-256 of the versioned report object encoded as deterministic UTF-8 JSON.

    This binds snapshot ``raw_text``; it is not the plain text or disk-file hash.
    """
    return _digest(_tagged_object("report", {"text": raw_text}))


def target_hash(expected_decision: str | None, expected_dimensions: dict[str, float]) -> str:
    """SHA-256 binding a versioned target object.

    ``None`` and decision strings stay distinct (JSON null vs string); a missing
    dimension and an explicit ``0.5`` stay distinct (absent key vs value). The
    input mapping is copied first so later in-process mutation cannot move the
    hash; non-finite floats fail loudly via ``allow_nan=False``.
    """
    dims = dict(expected_dimensions)
    try:
        return _digest(
            _tagged_object(
                "target",
                {"expected_decision": expected_decision, "expected_dimensions": dims},
            )
        )
    except ValueError as exc:
        raise InputIdentityError(f"target is not JSON-serializable: {exc}") from exc


def input_hash(report_digest: str, target_digest: str) -> str:
    """SHA-256 binding one case's report and target identities."""
    return _digest(
        _tagged_object("input", {"report_hash": report_digest, "target_hash": target_digest})
    )


def case_row(case: SuiteCase) -> dict[str, Any]:
    """One ordered identity row for ``case``; rejects snapshot-less cases."""
    if case.report is None:
        raise InputIdentityError(
            f"case '{case.case_id}' has no snapshot report; "
            "legacy disk reload is not used for identity"
        )
    report_digest = report_hash(case.report.raw_text)
    target_digest = target_hash(case.expected_decision, case.expected_dimensions)
    return {
        "case_id": case.case_id,
        "case_kind": case.kind,
        "parent_id": case.parent_id,
        "operator": case.operator,
        "report_class": case.report_class,
        "seed": case.seed,
        "report_hash": report_digest,
        "target_hash": target_digest,
        "input_hash": input_hash(report_digest, target_digest),
    }


def selection_hash(case_ids: list[str]) -> str:
    """SHA-256 binding the ordered case_id selection (order matters)."""
    return _digest(_tagged_object("selection", {"case_ids": list(case_ids)}))


def inputs_hash(rows: list[dict[str, Any]]) -> str:
    """SHA-256 binding the ordered identity rows."""
    return _digest(_tagged_object("inputs", {"inputs": [dict(row) for row in rows]}))


def build_input_identity(cases: list[SuiteCase]) -> dict[str, Any]:
    """Build the identity object for ``cases`` in their given order.

    One row per case (never duplicated per evaluator). Reads only the snapshots
    and copied target dicts; touches no loader and no disk.
    """
    rows = [case_row(case) for case in cases]
    case_ids = [row["case_id"] for row in rows]
    return {
        "schema_version": SCHEMA_VERSION,
        "cases": rows,
        "selection_hash": selection_hash(case_ids),
        "inputs_hash": inputs_hash(rows),
    }


def write_input_identity(out_dir: Path, identity: dict[str, Any]) -> Path:
    """Write ``input-identity.json`` for a successful study run."""
    path = out_dir / IDENTITY_FILE_NAME
    path.write_bytes(_canonical_bytes(identity) + b"\n")
    return path
