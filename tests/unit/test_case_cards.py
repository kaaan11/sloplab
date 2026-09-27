"""Case-card v0.1 infrastructure tests: schema, leak, determinism, safety."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from sloplab.mutations.base import list_operators
from sloplab.safety.policy import is_reserved_host, validate_content_safety

REPO_ROOT = Path(__file__).resolve().parents[2]
CARDS_DIR = REPO_ROOT / "cards"
SEALED_DIR = REPO_ROOT / ".scratch" / "sealed"
SCHEMA_PATH = CARDS_DIR / "schema" / "case-card-v0.1.schema.json"

COMMITTED_INPUTS = sorted((CARDS_DIR / "v0.1").glob("c*/input.json"))
COMMITTED_INPUT_MDS = sorted((CARDS_DIR / "v0.1").glob("c*/input.md"))
SEALED_CARD_PATHS = sorted(SEALED_DIR.glob("*/card.yaml")) if SEALED_DIR.is_dir() else []

ANSWER_BEARING_KEYS = frozenset(
    {
        "review",
        "claim_evidence_map",
        "status",
        "next_action",
        "primary",
        "failure_mode_ids",
        "finding_refs",
        "confidence",
        "counterconditions",
        "provenance",
        "card_id",
        "scenario_id",
        "title",
    }
)

TOKEN_PATTERNS = (
    re.compile(r"FM\d{2}"),
    re.compile(r"R1-\d{3}"),
    re.compile(r"R2-\d{3}"),
    re.compile(r"request_specific_information"),
    re.compile(r"likely_out_of_scope"),
    re.compile(r"\bverify\b"),
)


def _card_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return dict(schema)


def _input_subschema() -> dict[str, Any]:
    schema = _card_schema()
    return {"$defs": schema["$defs"], "$ref": "#/$defs/visible_input"}


def _iter_keys(value: Any) -> Any:
    if isinstance(value, dict):
        for key, sub in value.items():
            yield key
            yield from _iter_keys(sub)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_keys(item)


def _text_blob(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def leak_violations(input_data: dict[str, Any]) -> list[str]:
    """Return every leak found in an annotator-visible input view (empty = clean)."""
    violations: list[str] = []
    for key in _iter_keys(input_data):
        if key in ANSWER_BEARING_KEYS:
            violations.append(f"answer-bearing key: {key}")
    blob = _text_blob(input_data)
    for pattern in TOKEN_PATTERNS:
        if pattern.search(blob):
            violations.append(f"leak token: {pattern.pattern}")
    for operator_name in list_operators():
        if operator_name in blob:
            violations.append(f"leak operator name: {operator_name}")
    return violations


class TestSchema:
    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(_card_schema())

    def _owner_judgment_schema_path(self) -> Path:
        return CARDS_DIR / "schema" / "owner-judgment-v0.1.schema.json"

    def test_owner_judgment_schema_is_valid(self) -> None:
        schema = json.loads(self._owner_judgment_schema_path().read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

    def test_owner_judgment_template_is_empty_and_unhinting(self) -> None:
        for input_path in COMMITTED_INPUTS:
            card_id = input_path.parent.name
            template_path = input_path.parent / "owner-judgment.template.yaml"
            assert template_path.exists(), template_path
            template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
            assert template["schema_version"] == "owner-judgment-v0.1", card_id
            assert template["card_id"] == card_id, card_id
            assert template["judge"] == ""
            assert template["judged_date"] == ""
            for field in ("action", "confidence", "rationale"):
                assert template[field] == "", (card_id, field)
            assert template["action_claim_ids"] == [], card_id
            expected_ids = [
                claim["id"]
                for claim in json.loads(input_path.read_text(encoding="utf-8"))["claims"]
            ]
            assert [claim["claim_id"] for claim in template["claims"]] == expected_ids, card_id
            for claim in template["claims"]:
                assert set(claim) <= {"claim_id", "status", "note"}, (card_id, claim)
                assert claim["status"] == "", (card_id, claim)
            blob = _text_blob(template)
            for pattern in TOKEN_PATTERNS:
                assert not pattern.search(blob), (card_id, pattern.pattern)
            for operator_name in list_operators():
                assert operator_name not in blob, (card_id, operator_name)
            header_text = template_path.read_text(encoding="utf-8")
            assert not header_text.lstrip().startswith(" "), card_id
            for pattern_name in (r"FM\d{2}", r"R1-\d{3}", r"R2-\d{3}"):
                assert not re.search(pattern_name, header_text), (card_id, pattern_name)
            for operator_name in list_operators():
                assert operator_name not in header_text, (card_id, operator_name)

    def test_owner_judgment_template_headers_are_neutral_and_identical(self) -> None:
        """Every card template shares one neutral header; enum order fixed, no defaults."""
        headers: list[str] = []
        for input_path in COMMITTED_INPUTS:
            text = (input_path.parent / "owner-judgment.template.yaml").read_text(encoding="utf-8")
            header_lines = [line for line in text.splitlines() if line.startswith("#")]
            assert header_lines, input_path
            headers.append("\n".join(header_lines))
        assert len(set(headers)) == 1, "template headers differ between cards"
        header_blob = json.dumps(headers[0])
        for operator_name in list_operators():
            assert operator_name not in header_blob, operator_name
        for pattern_name in (r"FM\d{2}", r"R1-\d{3}", r"R2-\d{3}"):
            assert not re.search(pattern_name, header_blob), pattern_name

    def test_filled_owner_judgment_template_validates(self) -> None:
        """Filling a template with arbitrary schema-valid values validates."""
        validator = Draft202012Validator(
            json.loads(self._owner_judgment_schema_path().read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )
        statuses = ["supported", "missing", "contradictory"]
        actions = ["verify", "request_specific_information", "likely_out_of_scope"]
        confidences = ["low", "medium", "high"]
        for input_path in COMMITTED_INPUTS:
            card_id = input_path.parent.name
            template = yaml.safe_load(
                (input_path.parent / "owner-judgment.template.yaml").read_text(encoding="utf-8")
            )
            for index, claim in enumerate(template["claims"]):
                claim["status"] = statuses[index % len(statuses)]
            template["judge"] = "Test Filler"
            template["judged_date"] = "2099-01-01"
            template["action"] = actions[len(template["claims"]) % len(actions)]
            template["action_claim_ids"] = [template["claims"][0]["claim_id"]]
            template["confidence"] = confidences[len(template["claims"]) % len(confidences)]
            template["rationale"] = "Filled line for validation only."
            errors = sorted(validator.iter_errors(template), key=lambda e: e.message)
            assert not errors, f"{card_id}: {[e.message for e in errors]}"

    def test_multiline_rationale_fails_validation(self) -> None:
        """The card-level rationale must be a single line."""
        schema = json.loads(self._owner_judgment_schema_path().read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        input_path = COMMITTED_INPUTS[0]
        template = yaml.safe_load(
            (input_path.parent / "owner-judgment.template.yaml").read_text(encoding="utf-8")
        )
        template["judge"] = "Test Filler"
        template["judged_date"] = "2099-01-01"
        template["action"] = "verify"
        template["action_claim_ids"] = []
        template["confidence"] = "medium"
        template["rationale"] = "First line\nSecond line"
        for claim in template["claims"]:
            claim["status"] = "supported"
        errors = sorted(validator.iter_errors(template), key=lambda e: e.message)
        assert errors, "multi-line rationale must fail validation"
        template["rationale"] = "Single line now."
        errors = sorted(validator.iter_errors(template), key=lambda e: e.message)
        assert not errors, f"only the newline should fail: {[e.message for e in errors]}"

    def test_per_claim_action_field_is_rejected(self) -> None:
        """Claims carry only claim_id/status/note; an action key is rejected."""
        schema = json.loads(self._owner_judgment_schema_path().read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        input_path = COMMITTED_INPUTS[0]
        template = yaml.safe_load(
            (input_path.parent / "owner-judgment.template.yaml").read_text(encoding="utf-8")
        )
        template["judge"] = "Test Filler"
        template["judged_date"] = "2099-01-01"
        template["action"] = "verify"
        template["action_claim_ids"] = []
        template["confidence"] = "medium"
        template["rationale"] = "Filled line for validation only."
        for claim in template["claims"]:
            claim["status"] = "supported"
        template["claims"][0]["action"] = "verify"
        errors = sorted(validator.iter_errors(template), key=lambda e: e.message)
        assert errors, "per-claim action field must fail validation"
        assert any("action" in e.message for e in errors), [e.message for e in errors]

    def test_committed_inputs_validate_against_input_subschema(self) -> None:
        validator = Draft202012Validator(_input_subschema())
        assert COMMITTED_INPUTS, "expected committed input.json views"
        for path in COMMITTED_INPUTS:
            data = json.loads(path.read_text(encoding="utf-8"))
            errors = sorted(validator.iter_errors(data), key=lambda e: e.message)
            assert not errors, f"{path}: {[e.message for e in errors]}"

    def test_sealed_cards_validate_against_full_schema(self) -> None:
        """Validates the sealed card.yaml files in .scratch/sealed (not tracked).

        Skipped only when the sealed directory is absent (e.g. CI).
        """
        if not SEALED_CARD_PATHS:
            pytest.skip(
                "sealed card directory .scratch/sealed is absent in this checkout (e.g. CI); "
                "the sealed card.yaml files are untracked orchestrator inputs"
            )
        validator = Draft202012Validator(_card_schema(), format_checker=FormatChecker())
        for path in SEALED_CARD_PATHS:
            card = yaml.safe_load(path.read_text(encoding="utf-8"))
            errors = sorted(validator.iter_errors(card), key=lambda e: e.message)
            assert not errors, f"{path}: {[e.message for e in errors]}"


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda data: data.update({"review": {"status": "supported"}}),
            id="review-key-injected",
        ),
        pytest.param(
            lambda data: data["context"].append(
                {"id": "P99", "kind": "program_policy", "text": "This should route to verify."}
            ),
            id="verify-token-injected",
        ),
        pytest.param(
            lambda data: data["claims"][0].update({"statement": "FM07 finding"}),
            id="failure-mode-id-injected",
        ),
        pytest.param(
            lambda data: data["claims"][0].update({"statement": "see R1-001"}),
            id="finding-ref-injected",
        ),
        pytest.param(
            lambda data: data["claims"][0].update({"statement": "Action: likely_out_of_scope"}),
            id="action-identifier-injected",
        ),
        pytest.param(
            lambda data: data["artifacts"][0].update(
                {"text": data["artifacts"][0]["text"] + " mutation: impact_inflation"}
            ),
            id="operator-name-injected",
        ),
        pytest.param(
            lambda data: data.update({"provenance": {"authoring_model_family": "X"}}),
            id="provenance-key-injected",
        ),
    ],
)
def test_injected_fixture_is_red(
    mutation: Callable[[dict[str, Any]], None], tmp_path: Path
) -> None:
    """The leak check must catch every injected answer field or token."""
    source = COMMITTED_INPUTS[0]
    data: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    mutation(data)
    injected_path = tmp_path / source.name
    injected_path.write_text(_text_blob(data), encoding="utf-8")
    violations = leak_violations(json.loads(injected_path.read_text(encoding="utf-8")))
    assert violations, f"injection was not detected: {source.name}"


def test_committed_inputs_have_no_leaks() -> None:
    assert COMMITTED_INPUTS, "expected committed input.json views"
    for path in COMMITTED_INPUTS:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert leak_violations(data) == [], f"{path}: {leak_violations(data)}"


def _split_markdown_footer(text: str) -> tuple[str, str]:
    """Split an input.md into (input view, judgment footer) at the footer heading."""
    marker = "## How to record your judgment"
    assert marker in text, "footer heading missing"
    head, _, footer = text.partition(marker)
    return head, footer


def _markdown_leak_violations(text: str) -> list[str]:
    """Return every leak found in an exported input.md (empty = clean).

    The fixed judgment footer legitimately names the neutral action/status
    enums (in schema order, identical on every card); the *input view* above
    the footer must never contain them. The footer is checked separately for
    neutrality (enum order, no per-card hints).
    """
    head, footer = _split_markdown_footer(text)
    violations: list[str] = []
    for pattern in TOKEN_PATTERNS:
        if pattern.search(head):
            violations.append(f"leak token in input view: {pattern.pattern}")
    for operator_name in list_operators():
        if operator_name in head:
            violations.append(f"leak operator name in input view: {operator_name}")
    for key in sorted(ANSWER_BEARING_KEYS):
        if re.search(rf"(?m)^#+ {re.escape(key)}\b", head) or re.search(
            rf"(?m)^#+ {re.escape(key)}\b", footer
        ):
            violations.append(f"answer-bearing heading: {key}")
    return violations


def test_committed_input_md_have_no_leaks() -> None:
    """input.md is derived only from input.json; it must carry no answer material."""
    assert COMMITTED_INPUT_MDS, "expected committed input.md views"
    for path in COMMITTED_INPUT_MDS:
        text = path.read_text(encoding="utf-8")
        assert _markdown_leak_violations(text) == [], f"{path}: {_markdown_leak_violations(text)}"


def test_committed_input_md_title_is_opaque_id_only() -> None:
    """The heading is 'Case <opaque_id>'; never the sealed card title or scenario id."""
    for path in COMMITTED_INPUT_MDS:
        text = path.read_text(encoding="utf-8")
        opaque_id = json.loads((path.parent / "input.json").read_text(encoding="utf-8"))[
            "opaque_id"
        ]
        assert f"# Case {opaque_id}" in text, path
        if SEALED_CARD_PATHS:
            sealed = {
                line.split(": ", 1)[1]
                for card_path in SEALED_CARD_PATHS
                for line in card_path.read_text(encoding="utf-8").splitlines()
                if line.startswith(("title: ", "scenario_id: "))
            }
            for forbidden in sealed:
                assert forbidden not in text, f"{path}: sealed identity leaked: {forbidden!r}"


@pytest.mark.parametrize(
    "injected_snippet",
    [
        pytest.param("Action: likely_out_of_scope", id="action-identifier-injected"),
        pytest.param("finding ref R1-001", id="finding-ref-injected"),
        pytest.param("failure mode FM07", id="failure-mode-id-injected"),
        pytest.param("mutation: impact_inflation", id="operator-name-injected"),
        pytest.param("## review", id="review-heading-injected"),
        pytest.param("## provenance", id="provenance-heading-injected"),
        pytest.param("## next_action", id="next-action-heading-injected"),
        pytest.param("## counterconditions", id="counterconditions-heading-injected"),
        pytest.param("## claim_evidence_map", id="claim-evidence-map-heading-injected"),
        pytest.param(
            "R2-100: synthetic attack line with finding_refs to R2",
            id="r2-ref-injected",
        ),
        pytest.param("verify the FM07 finding via R1-001", id="verify-token-injected"),
        pytest.param(
            "Escalate to request_specific_information with FM03",
            id="footer-token-in-view-injected",
        ),
        pytest.param("## title", id="title-heading-injected"),
        pytest.param("## scenario_id", id="scenario-id-heading-injected"),
        pytest.param("## card_id", id="card-id-heading-injected"),
    ],
)
def test_injected_input_md_is_red(injected_snippet: str, tmp_path: Path) -> None:
    """The markdown leak check must catch every injected answer token or heading."""
    assert COMMITTED_INPUT_MDS, "expected committed input.md views"
    committed_text = COMMITTED_INPUT_MDS[0].read_text(encoding="utf-8")
    marker = "## How to record your judgment"
    head, _, footer = committed_text.partition(marker)
    tampered_head = head + f"\n{injected_snippet}\n"
    tampered_text = tampered_head + marker + footer
    violations = _markdown_leak_violations(tampered_text)
    assert violations, f"injection was not detected: {injected_snippet!r}"


def test_input_md_judgment_footer_is_neutral_and_identical() -> None:
    """Every card's footer lists the allowed values neutrally, in fixed order."""
    footers: list[str] = []
    for path in COMMITTED_INPUT_MDS:
        text = path.read_text(encoding="utf-8")
        _, footer = _split_markdown_footer(text)
        footers.append(footer)
    assert len(set(footers)) == 1, "judgment footers differ between cards"
    footer = footers[0]
    order = [
        footer.index("verify"),
        footer.index("request_specific_information"),
        footer.index("likely_out_of_scope"),
        footer.index("low / medium / high"),
        footer.index("supported / missing / contradictory"),
    ]
    assert order == sorted(order), f"footer enum order not fixed: {footer}"
    for operator_name in list_operators():
        assert operator_name not in footer, operator_name


class TestExportDeterminism:
    def test_export_check_mode_matches_committed_bytes(self) -> None:
        card_paths: list[Path] = []
        if SEALED_DIR.is_dir():
            for path in COMMITTED_INPUTS:
                card = SEALED_DIR / path.parent.name / "card.yaml"
                if card.exists():
                    card_paths.append(card)
        if not card_paths:
            pytest.skip(
                "sealed card directory .scratch/sealed is absent in this checkout (e.g. CI)"
            )
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                *[str(p) for p in card_paths],
                "--out",
                str(CARDS_DIR / "v0.1"),
                "--check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "CHECK FAIL" not in proc.stdout + proc.stderr
        assert proc.stdout.count("CHECK OK") == 3 * len(card_paths)
        assert proc.stdout.count("owner-judgment.template.yaml") == len(card_paths)
        assert proc.stdout.count("input.md") == len(card_paths)

    def test_check_mode_detects_tampered_input_md(self, tmp_path: Path) -> None:
        """--check must also fail when a committed input.md was edited."""
        card = SEALED_DIR / "c01" / "card.yaml"
        if not card.exists():
            pytest.skip("sealed card directory .scratch/sealed is absent in this checkout")
        out = tmp_path / "out"
        first = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(card),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert first.returncode == 0, first.stdout + first.stderr
        tampered = out / "c01" / "input.md"
        assert tampered.exists(), tampered
        tampered.write_text(tampered.read_text(encoding="utf-8") + "\n<!-- stray -->\n", "utf-8")
        second = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(card),
                "--out",
                str(out),
                "--check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode == 1, second.stdout + second.stderr
        assert "input.md" in second.stderr
        assert "CHECK FAIL" in second.stderr

    def test_input_md_content_is_derived_only_from_input_json(self, tmp_path: Path) -> None:
        """input.md regenerates byte-identically; the export never rewrites input.json."""
        card = SEALED_DIR / "c01" / "card.yaml"
        if not card.exists():
            pytest.skip("sealed card directory .scratch/sealed is absent in this checkout")
        out = tmp_path / "out"
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(card),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        generated = (out / "c01" / "input.md").read_bytes()
        committed = (CARDS_DIR / "v0.1" / "c01" / "input.md").read_bytes()
        assert generated == committed, "committed input.md does not match regeneration"

    def test_input_md_structure_matches_spec(self) -> None:
        """input.md renders exactly the sections the blind-review contract requires."""
        assert COMMITTED_INPUT_MDS, "expected committed input.md views"
        for path in COMMITTED_INPUT_MDS:
            text = path.read_text(encoding="utf-8")
            view = json.loads((path.parent / "input.json").read_text(encoding="utf-8"))
            assert text.startswith(f"# Case {view['opaque_id']}\n\n"), path
            for heading in ("## Context", "## Report", "## Artifacts", "## Claims"):
                assert f"\n{heading}\n" in text, (path, heading)
            for item in view["context"]:
                assert f"- {item['id']} (" in text, (path, item["id"])
            for line in view["report"]:
                assert f"{line['id']}: " in text, (path, line["id"])
            for artifact in view["artifacts"]:
                assert f"{artifact['id']}: ({artifact['origin']}) " in text, (
                    path,
                    artifact["id"],
                )
            for claim in view["claims"]:
                assert f"{claim['id']}:" in text, (path, claim["id"])
                for ref in claim["report_refs"]:
                    assert f"`{ref}`" in text, (path, ref)
            assert "owner-judgment.yaml" in text, path
            assert text.endswith("\n"), path

    def test_input_md_kind_words_are_fixed(self) -> None:
        """Context kinds render as fixed plain words, identically for every card."""
        word_for_kind = {
            "setting": "setting",
            "stipulated_fact": "stipulated fact",
            "program_policy": "program policy",
            "assistant_role": "assistant role",
        }
        for path in COMMITTED_INPUT_MDS:
            view = json.loads((path.parent / "input.json").read_text(encoding="utf-8"))
            text = path.read_text(encoding="utf-8")
            for item in view["context"]:
                assert f"- {item['id']} ({word_for_kind[item['kind']]}): " in text, (
                    path,
                    item["id"],
                )

    def test_input_md_is_deterministic(self, tmp_path: Path) -> None:
        """Two export runs produce byte-identical input.md files."""
        card = SEALED_DIR / "c01" / "card.yaml"
        if not card.exists():
            pytest.skip("sealed card directory .scratch/sealed is absent in this checkout")
        out_a, out_b = tmp_path / "a", tmp_path / "b"
        for out in (out_a, out_b):
            proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                    str(card),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode == 0, proc.stdout + proc.stderr
        assert (out_a / "c01" / "input.md").read_bytes() == (
            out_b / "c01" / "input.md"
        ).read_bytes()

    def test_check_mode_detects_tampered_template(self, tmp_path: Path) -> None:
        """--check must also fail when a committed template was edited."""
        card = SEALED_DIR / "c01" / "card.yaml"
        if not card.exists():
            pytest.skip("sealed card directory .scratch/sealed is absent in this checkout")
        out = tmp_path / "out"
        first = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(card),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert first.returncode == 0, first.stdout + first.stderr
        tampered = out / "c01" / "owner-judgment.template.yaml"
        tampered.write_text(
            tampered.read_text(encoding="utf-8") + "# stray edit\n", encoding="utf-8"
        )
        second = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(card),
                "--out",
                str(out),
                "--check",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode == 1, second.stdout + second.stderr
        assert "CHECK FAIL" in second.stderr


class TestExportErrorHandling:
    def test_malformed_card_fails_cleanly(self, tmp_path: Path) -> None:
        """A malformed card yields one clean stderr line and exit code 2."""
        malformed = tmp_path / "bad-card.yaml"
        malformed.write_text("schema_version: case-card-v0.1\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(malformed),
                "--out",
                str(tmp_path / "out"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 2, proc.stdout + proc.stderr
        err_lines = [line for line in proc.stderr.splitlines() if line.strip()]
        assert len(err_lines) == 1, proc.stderr
        assert "Traceback" not in proc.stderr
        assert "bad-card.yaml" in err_lines[0]

    def test_malformed_cards_run_together_fails_at_first(self, tmp_path: Path) -> None:
        """A valid card exports, then one malformed card aborts with exit code 2."""
        valid = tmp_path / "first-card.yaml"
        valid.write_text(
            "schema_version: case-card-v0.1\n"
            "card_id: first-card\n"
            "input:\n"
            "  opaque_id: case-test-001\n"
            "  context:\n"
            "  - id: P1\n"
            "    kind: setting\n"
            "    text: Setting.\n"
            "  report:\n"
            "  - id: R01\n"
            "    text: Line one.\n"
            "  artifacts: []\n"
            "  claims:\n"
            "  - id: C1\n"
            "    statement: A claim.\n"
            "    report_refs: [R01]\n",
            encoding="utf-8",
        )
        second = tmp_path / "second-card.yaml"
        second.write_text("- just\n- a list\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_card_inputs.py"),
                str(valid),
                str(second),
                "--out",
                str(tmp_path / "out"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "Traceback" not in proc.stderr
        err_lines = [line for line in proc.stderr.splitlines() if line.strip()]
        assert len(err_lines) == 1, proc.stderr
        assert "second-card.yaml" in err_lines[0]


class TestSafety:
    def test_all_input_text_passes_content_safety(self) -> None:
        for path in COMMITTED_INPUTS:
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry in data["context"] + data["report"]:
                assert validate_content_safety(entry["text"]) == [], path
            for artifact in data["artifacts"]:
                assert validate_content_safety(artifact["text"]) == [], path
            for claim in data["claims"]:
                assert validate_content_safety(claim["statement"]) == [], path

    def test_all_url_hosts_are_reserved(self) -> None:
        from urllib.parse import urlsplit

        for path in COMMITTED_INPUTS:
            data = json.loads(path.read_text(encoding="utf-8"))
            blob = _text_blob(data)
            for token in re.findall(r"https?://[^\s\"<>\)\]]+", blob):
                token = token.rstrip(".,;:!?'\"")
                host = urlsplit(token).hostname
                assert host is not None and is_reserved_host(host), f"{path}: {token}"

    def test_setting_names_are_synthetic_products(self) -> None:
        from sloplab.safety.policy import SYNTHETIC_PRODUCTS

        for path in COMMITTED_INPUTS:
            data = json.loads(path.read_text(encoding="utf-8"))
            blob = _text_blob(data)
            products = set(re.findall(r"fictional exercise about (\w+)", blob))
            assert products, f"{path}: no fictional setting found"
            assert products <= set(SYNTHETIC_PRODUCTS), (
                f"{path}: {products - set(SYNTHETIC_PRODUCTS)}"
            )

    def test_no_real_year_cves(self) -> None:
        from sloplab.safety.policy import find_real_year_cves

        for path in COMMITTED_INPUTS:
            data = json.loads(path.read_text(encoding="utf-8"))
            assert find_real_year_cves(_text_blob(data)) == [], path
