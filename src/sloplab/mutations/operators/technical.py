"""Technical-consistency mutation operators.

These operators insert fabricated technical identifiers, degrading verifiability
while keeping the surrounding prose intact.
"""

from __future__ import annotations

import random
from typing import Any

from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    REPRODUCIBILITY,
    Decision,
    MutationCategory,
    ReportClass,
)
from sloplab.models.report import ReportDocument
from sloplab.mutations.base import MutationSpec, register
from sloplab.mutations.textops import first_matching_section, replace_section_body
from sloplab.safety.policy import FAKE_CVE_YEAR

_SUMMARY_PATTERN = r"summary|description|overview"
_FALLBACK_PATTERNS: tuple[str, ...] = (
    _SUMMARY_PATTERN,
    r"observed\s+results?",
    r"impact",
)

_INVENTION_TEMPLATES: tuple[str, ...] = (
    "Internal tracking assigns this issue advisory CVE-{year}-{number}.",
    "This matches the vendor advisory identifier VND-{number} referenced in the "
    "component changelog.",
    "The affected route is `/api/v{version}/{segment}` according to the deployment "
    "manifest used during testing.",
)

_SEGMENTS: tuple[str, ...] = (
    "internal-audit",
    "session-bridge",
    "token-vault",
    "legacy-export",
)


class InventApiIdentifier:
    spec = MutationSpec(
        name="invent_api_identifier",
        category=MutationCategory.TECHNICAL_CONSISTENCY,
        description=(
            "Inserts a fabricated advisory or endpoint identifier that cannot be "
            "verified against the report's own content."
        ),
        dimension_deltas={
            CLAIM_EVIDENCE_CONSISTENCY: -0.45,
            REPRODUCIBILITY: -0.15,
        },
        decision_by_parent_class={ReportClass.VALID: Decision.NEEDS_MANUAL_REVIEW},
        claim_quality="degraded",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        template = _INVENTION_TEMPLATES[rng.randrange(len(_INVENTION_TEMPLATES))]
        invented = template.format(
            year=FAKE_CVE_YEAR,
            number=f"{rng.randrange(10000):04d}",
            version=rng.randrange(2, 10),
            segment=rng.choice(_SEGMENTS),
        )

        for pattern in _FALLBACK_PATTERNS:
            section = first_matching_section(document, pattern)
            if section is not None:
                body_lines = section.text.splitlines()
                body = "\n".join(body_lines[1:])
                mutated_text = replace_section_body(
                    document, section, body.rstrip() + "\n\n" + invented
                )
                rng.getrandbits(1)
                return mutated_text, {
                    "inserted_identifier_claim": invented,
                    "target_section_heading": section.heading,
                }

        rng.getrandbits(1)
        return document.raw_text, {"note": "no suitable section found"}


register(InventApiIdentifier())
