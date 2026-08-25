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
    first_matching_section,
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

        lines = section.text.splitlines()
        steps = numbered_steps(section)
        if len(steps) >= 2:
            pick_index, step_number = steps[rng.randrange(len(steps))]
            body = "\n".join(
                line for offset, line in enumerate(lines) if offset != pick_index and offset != 0
            )
            mutated = replace_section_body(document, section, body)
            params: dict[str, Any] = {
                "removed_step_number": step_number,
                "removed_step_text": lines[pick_index].strip(),
                "mode": "single_step",
            }
        else:
            mutated = remove_section(document, section)
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
        mutated = remove_section(document, section)
        rng.getrandbits(1)
        return mutated, {"removed_section_heading": section.heading}


register(RemoveReproductionStep())
register(RemoveAffectedVersion())
