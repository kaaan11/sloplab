"""Evidence-removal mutation operators.

These operators delete required evidence from an otherwise intact report, testing
whether evaluators notice incomplete evidence rather than trusting confident prose.
"""

from __future__ import annotations

import random
from typing import Any

from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    EVIDENCE_COMPLETENESS,
    REPRODUCIBILITY,
    SCOPE_CONSISTENCY,
    Decision,
    MutationCategory,
    ReportClass,
)
from sloplab.models.report import ReportDocument
from sloplab.mutations.base import MutationSpec, register
from sloplab.mutations.textops import (
    document_identity,
    first_matching_section,
    full_step_span,
    has_fence_marker,
    numbered_steps,
    remove_section,
    replace_section_body,
)

_REPRODUCTION_PATTERN = r"reproduction\s+steps?|steps\s+to\s+reproduce"
_VERSIONS_PATTERN = r"affected\s+versions?"


class RemoveReproductionStep:
    spec = MutationSpec(
        name="remove_reproduction_step",
        category=MutationCategory.EVIDENCE_REMOVAL,
        description=(
            "Deletes one ordered reproduction step (or the section body if fewer than "
            "two steps remain), degrading reproducibility."
        ),
        dimension_deltas={
            REPRODUCIBILITY: -0.6,
            EVIDENCE_COMPLETENESS: -0.25,
        },
        decision_by_parent_class={ReportClass.VALID: Decision.NEEDS_MANUAL_REVIEW},
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        section = first_matching_section(document, _REPRODUCTION_PATTERN)
        if section is None:
            return document.raw_text, {"note": "no reproduction steps section found"}
        # Provenance bind: the source identity travels with the span from here.
        source_identity = document_identity(document)

        lines = section.text.splitlines()
        steps = numbered_steps(section)
        if len(steps) >= 2:
            pick_index, step_number = steps[rng.randrange(len(steps))]
            if has_fence_marker(lines):
                rng.getrandbits(1)
                return document.raw_text, {"note": "fenced content in section"}
            drop = full_step_span(lines, steps, pick_index)
            if drop is None:
                # Out-of-profile item (ambiguous/non-indented continuation):
                # controlled no-op with RNG parity, never a partial edit. The
                # draw above keeps the downstream stream identical to the
                # pre-fix path on the same input.
                rng.getrandbits(1)
                return document.raw_text, {
                    "note": f"ambiguous continuation after step {step_number}"
                }
            body = "\n".join(
                line for offset, line in enumerate(lines) if offset not in drop and offset != 0
            )
            mutated = replace_section_body(
                document, section, body, expected_document_identity=source_identity
            )
            params: dict[str, Any] = {
                "removed_step_number": step_number,
                "removed_step_text": lines[pick_index].strip(),
                "mode": "single_step",
            }
            if len(drop) > 1:
                # Production version identity lives where behavior diverged:
                # the full item span (step line plus continuations) replaced
                # the old first-line-only drop. Unaffected cases stay
                # byte-identical to older production versions; the run-level
                # ledger header carries the version for the whole run.
                params["span_model"] = "full-item-v1"
                params["removed_extra_lines"] = len(drop) - 1
        else:
            mutated = remove_section(document, section, expected_document_identity=source_identity)
            params = {"mode": "whole_section", "removed_section_heading": section.heading}

        rng.getrandbits(1)  # keep RNG stream identical across code paths
        return mutated, params


class RemoveAffectedVersion:
    spec = MutationSpec(
        name="remove_affected_version",
        category=MutationCategory.EVIDENCE_REMOVAL,
        description=(
            "Removes the affected-versions scope statement entirely, leaving impact "
            "unbounded and unverifiable."
        ),
        dimension_deltas={
            SCOPE_CONSISTENCY: -0.35,
            EVIDENCE_COMPLETENESS: -0.15,
            CLAIM_EVIDENCE_CONSISTENCY: -0.1,
        },
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        section = first_matching_section(document, _VERSIONS_PATTERN)
        if section is None:
            return document.raw_text, {"note": "no affected versions section found"}
        # Provenance bind: the source identity travels with the span from here.
        source_identity = document_identity(document)
        mutated = remove_section(document, section, expected_document_identity=source_identity)
        rng.getrandbits(1)
        return mutated, {"removed_section_heading": section.heading}


register(RemoveReproductionStep())
register(RemoveAffectedVersion())
