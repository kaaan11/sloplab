"""Descriptive paired audits that retain the parent, child, and repeat units.

These diagnostics do not turn an authored target into a mutation-detection claim.
They report the observed decisions and coverage alongside the legacy target
accuracy, including pairs whose parent result is missing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from sloplab.models.enums import Decision, ReportClass, canonical_expected_decision
from sloplab.models.run import CaseRecord
from sloplab.scoring.metrics import decision_correct, validate_metric_records


@dataclass(frozen=True)
class DecisionChangeAudit:
    eligible_children: int
    paired: int
    missing_parent: int
    child_correct: int
    parent_correct: int
    both_correct: int
    actual_decision_change: int
    child_correct_given_parent_correct: int
    child_deferrals: int

    def as_dict(self) -> dict[str, int | float | None]:
        return {
            "eligible_children": self.eligible_children,
            "paired": self.paired,
            "missing_parent": self.missing_parent,
            "child_target_accuracy": self.child_correct / self.eligible_children
            if self.eligible_children
            else None,
            "both_correct_rate": self.both_correct / self.paired if self.paired else None,
            "actual_decision_change_rate": self.actual_decision_change / self.paired
            if self.paired
            else None,
            "child_correct_given_parent_correct": (
                self.child_correct_given_parent_correct / self.parent_correct
                if self.parent_correct
                else None
            ),
            "deferral_rate": self.child_deferrals / self.eligible_children
            if self.eligible_children
            else None,
            "parent_correct": self.parent_correct,
            "both_correct": self.both_correct,
            "actual_decision_change": self.actual_decision_change,
            "child_deferrals": self.child_deferrals,
        }


def audit_decision_changing_mutations(records: list[CaseRecord]) -> DecisionChangeAudit:
    """Audit target-changing children against their canonical parent in one repeat."""
    validate_metric_records(records)
    parents = {
        (r.case_id, r.evaluator_name, r.evaluation_metadata.get("repeat_index", 0)): r
        for r in records
        if r.case_kind == "canonical"
    }
    counts: Counter[str] = Counter()
    for child in records:
        if (
            child.case_kind != "mutated"
            or child.expected_decision is None
            or child.parent_id is None
            or child.expected_decision
            == canonical_expected_decision(ReportClass(child.report_class))
        ):
            continue
        counts["eligible_children"] += 1
        counts["child_correct"] += int(decision_correct(child))
        counts["child_deferrals"] += int(child.decision == Decision.NEEDS_MANUAL_REVIEW)
        key = (
            child.parent_id,
            child.evaluator_name,
            child.evaluation_metadata.get("repeat_index", 0),
        )
        parent = parents.get(key)
        if parent is None:
            counts["missing_parent"] += 1
            continue
        counts["paired"] += 1
        parent_ok = decision_correct(parent)
        child_ok = decision_correct(child)
        counts["parent_correct"] += int(parent_ok)
        counts["both_correct"] += int(parent_ok and child_ok)
        counts["actual_decision_change"] += int(parent.decision != child.decision)
        counts["child_correct_given_parent_correct"] += int(parent_ok and child_ok)
    return DecisionChangeAudit(
        eligible_children=counts["eligible_children"],
        paired=counts["paired"],
        missing_parent=counts["missing_parent"],
        child_correct=counts["child_correct"],
        parent_correct=counts["parent_correct"],
        both_correct=counts["both_correct"],
        actual_decision_change=counts["actual_decision_change"],
        child_correct_given_parent_correct=counts["child_correct_given_parent_correct"],
        child_deferrals=counts["child_deferrals"],
    )


@dataclass(frozen=True)
class AuthoredPairAudit:
    paired: int
    changed: int
    both_correct: int
    plain_accept: int
    polished_accept: int
    accept_gain: int
    accept_loss: int
    transitions: dict[str, int]

    def as_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "paired": self.paired,
            "changed": self.changed,
            "both_correct": self.both_correct,
            "plain_accept": self.plain_accept,
            "polished_accept": self.polished_accept,
            "accept_gain": self.accept_gain,
            "accept_loss": self.accept_loss,
            "transitions": self.transitions,
        }


def audit_authored_pairs(
    records: list[CaseRecord], pair_roles: dict[str, tuple[str, str]]
) -> dict[str, AuthoredPairAudit]:
    """Analyze authored plain/polished pairs separately from mutation operators.

    ``pair_roles`` maps canonical case id to ``(pair_id, role)``. Results are
    grouped by evaluator and bind the same repeat; incomplete pairs raise so
    published denominators cannot silently shrink.
    """
    validate_metric_records(records)
    groups: dict[tuple[str, str, object], dict[str, CaseRecord]] = defaultdict(dict)
    for record in records:
        if record.case_kind != "canonical" or record.case_id not in pair_roles:
            continue
        pair_id, role = pair_roles[record.case_id]
        if role not in {"plain", "polished"}:
            raise ValueError(f"invalid pair role {role!r} for {record.case_id}")
        key = (record.evaluator_name, pair_id, record.evaluation_metadata.get("repeat_index", 0))
        if role in groups[key]:
            raise ValueError(f"duplicate {role} member for {key}")
        groups[key][role] = record
    by_evaluator: dict[str, list[tuple[CaseRecord, CaseRecord]]] = defaultdict(list)
    for (evaluator, pair_id, repeat), members in groups.items():
        if set(members) != {"plain", "polished"}:
            raise ValueError(f"incomplete pair {pair_id!r} for {evaluator!r} repeat {repeat!r}")
        plain, polished = members["plain"], members["polished"]
        if plain.expected_decision != polished.expected_decision:
            raise ValueError(f"pair {pair_id!r} has different expected decisions")
        by_evaluator[evaluator].append((plain, polished))
    results: dict[str, AuthoredPairAudit] = {}
    for evaluator, pairs in sorted(by_evaluator.items()):
        counts: Counter[str] = Counter()
        transitions: Counter[str] = Counter()
        for plain, polished in pairs:
            counts["paired"] += 1
            counts["changed"] += int(plain.decision != polished.decision)
            counts["both_correct"] += int(decision_correct(plain) and decision_correct(polished))
            plain_accept = plain.decision == Decision.ACCEPT
            polished_accept = polished.decision == Decision.ACCEPT
            counts["plain_accept"] += int(plain_accept)
            counts["polished_accept"] += int(polished_accept)
            counts["accept_gain"] += int(not plain_accept and polished_accept)
            counts["accept_loss"] += int(plain_accept and not polished_accept)
            transitions[f"{plain.decision.value} -> {polished.decision.value}"] += 1
        results[evaluator] = AuthoredPairAudit(
            paired=counts["paired"],
            changed=counts["changed"],
            both_correct=counts["both_correct"],
            plain_accept=counts["plain_accept"],
            polished_accept=counts["polished_accept"],
            accept_gain=counts["accept_gain"],
            accept_loss=counts["accept_loss"],
            transitions=dict(sorted(transitions.items())),
        )
    return results
