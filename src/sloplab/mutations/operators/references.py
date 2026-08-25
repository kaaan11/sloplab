"""Reference-manipulation mutation operators.

These operators corrupt citation/attribution integrity - fabricated references,
misattributed advisory identifiers - while leaving the technical narrative intact.
"""

from __future__ import annotations

import random
from typing import Any

from sloplab.corpus.parser import parse_report
from sloplab.models.enums import (
    CLAIM_EVIDENCE_CONSISTENCY,
    EVIDENCE_COMPLETENESS,
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
_IMPACT_PATTERN = r"impact"

_FABRICATED_REFERENCE_BLOCKS: tuple[str, ...] = (
    "\n\n### References\n\n"
    "- Vendor advisory: https://security.example.org/advisories/SA-{number}\n"
    "- Related write-up: https://blog.example.org/posts/{slug}\n"
    "- Internal tracker: https://issues.example.org/browse/DEMO-{number2}",
    "\n\n### References\n\n"
    "- Conference talk covering this flaw: https://talks.example.edu/events/{number}\n"
    "- Patch announcement: https://releases.example.org/{slug}/notes",
)

_SLUGS: tuple[str, ...] = (
    "auth-bypass-deep-dive",
    "tenant-isolation-failures",
    "session-handling-gone-wrong",
)


class FabricateReference:
    spec = MutationSpec(
        name="fabricate_reference",
        category=MutationCategory.REFERENCE,
        description=(
            "Appends a credible-looking references block pointing at documents that "
            "do not exist (reserved documentation domains only)."
        ),
        dimension_deltas={
            CLAIM_EVIDENCE_CONSISTENCY: -0.35,
            EVIDENCE_COMPLETENESS: -0.15,
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
        block_template = _FABRICATED_REFERENCE_BLOCKS[
            rng.randrange(len(_FABRICATED_REFERENCE_BLOCKS))
        ]
        block = block_template.format(
            number=f"{rng.randrange(1000, 9999)}",
            number2=f"{rng.randrange(10000)}",
            slug=rng.choice(_SLUGS),
        )

        target = first_matching_section(document, _IMPACT_PATTERN)
        params: dict[str, Any]
        if target is not None:
            body_lines = target.text.splitlines()
            body = "\n".join(body_lines[1:])
            mutated_text = replace_section_body(document, target, body.rstrip() + block)
            params = {"appended_reference_block": block.strip(), "target_heading": target.heading}
        else:
            mutated_text = document.raw_text.rstrip() + block
            params = {"appended_reference_block": block.strip(), "target_heading": None}

        rng.getrandbits(1)
        return mutated_text, params


_MISATTRIBUTION_TEMPLATES: tuple[str, ...] = (
    "The vendor has confirmed this issue as {cve}.",
    "This finding was previously disclosed and tracked as {cve}; see the advisory "
    "published under that identifier.",
    "Upstream tracking lists this defect as {cve} with fix status confirmed.",
)


class MisattributeCve:
    spec = MutationSpec(
        name="misattribute_cve",
        category=MutationCategory.REFERENCE,
        description=(
            "Inserts an authoritative-sounding claim binding the finding to a "
            "specific (fictional) advisory identifier that the report never "
            "substantiated."
        ),
        dimension_deltas={
            CLAIM_EVIDENCE_CONSISTENCY: -0.4,
            EVIDENCE_COMPLETENESS: -0.1,
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
        template = _MISATTRIBUTION_TEMPLATES[rng.randrange(len(_MISATTRIBUTION_TEMPLATES))]
        cve = f"CVE-{FAKE_CVE_YEAR}-{rng.randrange(10000):04d}"
        sentence = template.format(cve=cve)

        section = first_matching_section(document, _SUMMARY_PATTERN)
        params: dict[str, Any]
        if section is not None:
            body_lines = section.text.splitlines()
            body = "\n".join(body_lines[1:])
            mutated_text = replace_section_body(
                document, section, body.rstrip() + "\n\n" + sentence
            )
            params = {"inserted_attribution": sentence}
        else:
            mutated_text = document.raw_text.rstrip() + f"\n\n{sentence}\n"
            params = {"inserted_attribution": sentence}

        rng.getrandbits(1)
        return mutated_text, params


class ImpossiblePrecondition:
    spec = MutationSpec(
        name="impossible_precondition",
        category=MutationCategory.TECHNICAL_CONSISTENCY,
        description=(
            "Inserts a self-contradictory precondition that cannot hold, breaking "
            "the logical chain required to reproduce the issue."
        ),
        dimension_deltas={
            REPRODUCIBILITY: -0.55,
            CLAIM_EVIDENCE_CONSISTENCY: -0.4,
        },
        decision_by_parent_class={ReportClass.VALID: Decision.REJECT},
        claim_quality="degraded",
    )

    _SENTENCES: tuple[str, ...] = (
        "Requires an authenticated administrator session established with read-only "
        "guest credentials.",
        "Requires the target service to be offline and actively serving requests at "
        "the same moment.",
        "Requires an unauthenticated user who is already signed in.",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        section = first_matching_section(document, r"preconditions?")
        if section is None:
            return document.raw_text, {"note": "no preconditions section found"}
        sentence = self._SENTENCES[rng.randrange(len(self._SENTENCES))]
        body = "\n".join(section.text.splitlines()[1:])
        mutated_text = replace_section_body(document, section, body.rstrip() + "\n" + sentence)
        rng.getrandbits(1)
        return mutated_text, {
            "inserted_precondition": sentence,
            "target_heading": section.heading,
        }


class ContradictObservedResult:
    spec = MutationSpec(
        name="contradict_observed_result",
        category=MutationCategory.EVIDENCE_CONTRADICTION,
        description=(
            "Appends a statement to the observed-result section that negates the "
            "claimed vulnerability outcome."
        ),
        dimension_deltas={
            CLAIM_EVIDENCE_CONSISTENCY: -0.7,
        },
        decision_by_parent_class={ReportClass.VALID: Decision.REJECT},
        claim_quality="degraded",
    )

    _NEGATIONS: tuple[str, ...] = (
        "On repeated verification, however, the endpoint returned 403 Forbidden and "
        "no cross-tenant data was returned.",
        "Subsequent attempts could not reproduce any anomalous response; the control "
        "behaved identically with and without the manipulated input.",
        "A later re-test showed the boundary held in every configuration examined, "
        "contradicting the summary above.",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        section = first_matching_section(document, r"observed\s+results?")
        if section is None:
            return document.raw_text, {"note": "no observed result section found"}
        sentence = self._NEGATIONS[rng.randrange(len(self._NEGATIONS))]
        body = "\n".join(section.text.splitlines()[1:])
        mutated_text = replace_section_body(document, section, body.rstrip() + "\n\n" + sentence)
        rng.getrandbits(1)
        return mutated_text, {
            "inserted_negation": sentence,
            "target_heading": section.heading,
        }


class AddIrrelevantDetail:
    spec = MutationSpec(
        name="add_irrelevant_detail",
        category=MutationCategory.NOISE,
        description=(
            "Injects tangential background content that dilutes the signal without "
            "changing any claim; tests noise tolerance."
        ),
        dimension_deltas={
            EVIDENCE_COMPLETENESS: -0.1,
            REPRODUCIBILITY: -0.05,
        },
    )

    _BLOCKS: tuple[str, ...] = (
        "\n\n## Additional Context\n\n"
        "The application was originally built as a weekend project and later grew "
        "into the bundled demo. Its color scheme changed twice during development, "
        "and the mascot illustration was redrawn in 2019. The maintainers also ship "
        "a screensaver module unrelated to the web tier.\n",
        "\n\n## Background Information\n\n"
        "Version control history shows over four hundred commits touching the "
        "documentation alone. Several contributors prefer tabs over spaces, a topic "
        "of recurring discussion. The project README once won a community award for "
        "accessibility formatting.\n",
    )

    def apply(
        self,
        document: ReportDocument,
        rng: random.Random,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        _ = parameters
        block = self._BLOCKS[rng.randrange(len(self._BLOCKS))]
        mutated_text = document.raw_text.rstrip() + "\n" + block
        reparsed = parse_report(mutated_text, fixture_id=document.fixture_id, path=document.path)
        _ = reparsed
        rng.getrandbits(1)
        return mutated_text, {"appended_noise_block_heading": "Additional Context"}


_ = parse_report
register(FabricateReference())
register(MisattributeCve())
register(ImpossiblePrecondition())
register(ContradictObservedResult())
register(AddIrrelevantDetail())
