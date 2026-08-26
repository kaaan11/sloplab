"""Impact-related mutation operators.

These operators distort calibrated impact claims without changing the underlying
finding, testing whether evaluators separate *severity of the bug* from *quality of
the claim*.
"""

from __future__ import annotations

import random
import re
from typing import Any

from sloplab.corpus.parser import parse_report
from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    EVIDENCE_COMPLETENESS,
    IMPACT_CALIBRATION,
    SCOPE_CONSISTENCY,
    Decision,
    MutationCategory,
    ReportClass,
)
from sloplab.models.report import ReportDocument
from sloplab.mutations.base import MutationSpec, register
from sloplab.mutations.textops import first_matching_section, replace_section_body

_IMPACT_PATTERN = r"impact"
_COMPONENT_PATTERN = r"affected\s+components?"
_VERSIONS_PATTERN = r"affected\s+versions?"

_INFLATION_SENTENCES: tuple[str, ...] = (
    "This vulnerability exposes every customer record in the deployment and must be "
    "treated as a critical, actively exploited data breach.",
    "An unauthenticated attacker can fully compromise the entire platform, all tenant "
    "data, and underlying infrastructure through this flaw.",
    "This is a critical remotely exploitable issue with confirmed mass scanning in the "
    "wild; immediate emergency response is required.",
)

#: Word-boundary-anchored calibration replacements. The first matching pattern
#: wins; only standalone severity words are replaced so that unrelated words such
#: as "flow", "allow", or "below" can never be corrupted (v0.2.2 remediation R02).
_CALIBRATION_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\blow\s+to\s+medium\b", re.IGNORECASE), "critical"),
    (re.compile(r"\bmedium\b", re.IGNORECASE), "critical"),
    (re.compile(r"\bmoderate\b", re.IGNORECASE), "critical"),
    (re.compile(r"\blow\b", re.IGNORECASE), "critical"),
    (re.compile(r"\blimited\b", re.IGNORECASE), "severe"),
)

_EXPANSION_COMPONENT_SENTENCES: tuple[str, ...] = (
    "The same flaw is also present in the administrative API and the public marketing "
    "site of this product.",
    "All services sharing this codebase, including batch jobs and internal tooling, "
    "are affected as well.",
)

_EXPANSION_VERSION_SUFFIXES: tuple[str, ...] = (
    " All earlier releases since 0.1.0 and all future releases, including the upcoming "
    "9.x line, are equally affected.",
    " Every version ever released is affected, including builds distributed through "
    "unofficial mirrors.",
)


class ImpactInflation:
    spec = MutationSpec(
        name="impact_inflation",
        category=MutationCategory.IMPACT,
        description=(
            "Replaces calibrated severity language with critical-breach rhetoric and "
            "appends an unsubstantiated escalation sentence inside the impact section."
        ),
        dimension_deltas={
            IMPACT_CALIBRATION: -0.55,
            CLAIM_EVIDENCE_CONSISTENCY: -0.3,
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
        section = first_matching_section(document, _IMPACT_PATTERN)
        if section is None:
            return document.raw_text, {"note": "no impact section found"}

        body = "\n".join(section.text.splitlines()[1:])  # drop heading line
        replacements_made: list[str] = []
        for pattern, new in _CALIBRATION_REPLACEMENTS:
            match = pattern.search(body)
            if match:
                body = body[: match.start()] + new + body[match.end() :]
                replacements_made.append(f"{match.group(0)}->{new}")
                break

        sentence = _INFLATION_SENTENCES[rng.randrange(len(_INFLATION_SENTENCES))]
        mutated_text = replace_section_body(document, section, body.rstrip() + "\n\n" + sentence)
        rng.getrandbits(1)
        return mutated_text, {
            "calibration_replacements": replacements_made,
            "appended_sentence": sentence,
        }


class ScopeExpansion:
    spec = MutationSpec(
        name="scope_expansion",
        category=MutationCategory.IMPACT,
        description=(
            "Claims additional affected components or an unbounded version range without evidence."
        ),
        dimension_deltas={
            SCOPE_CONSISTENCY: -0.5,
            EVIDENCE_COMPLETENESS: -0.2,
            CLAIM_EVIDENCE_CONSISTENCY: -0.15,
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
        params: dict[str, Any] = {}
        current_text = document.raw_text

        component_section = first_matching_section(document, _COMPONENT_PATTERN)
        if component_section is None:
            return current_text, {"note": "no affected component section found"}
        sentence = _EXPANSION_COMPONENT_SENTENCES[
            rng.randrange(len(_EXPANSION_COMPONENT_SENTENCES))
        ]
        body = "\n".join(component_section.text.splitlines()[1:])
        current_text = replace_section_body(
            document, component_section, body.rstrip() + "\n\n" + sentence
        )
        params["expanded_component_claim"] = sentence

        reparsed = parse_report(current_text, fixture_id=document.fixture_id, path=document.path)
        versions_section = first_matching_section(reparsed, _VERSIONS_PATTERN)
        if versions_section is not None:
            suffix = _EXPANSION_VERSION_SUFFIXES[rng.randrange(len(_EXPANSION_VERSION_SUFFIXES))]
            version_body = "\n".join(versions_section.text.splitlines()[1:])
            current_text = replace_section_body(
                reparsed, versions_section, version_body.rstrip() + suffix
            )
            params["expanded_version_claim"] = suffix.strip()

        rng.getrandbits(1)
        return current_text, params


register(ImpactInflation())
register(ScopeExpansion())
