"""Tests for corpus loading and validation."""

from pathlib import Path

import pytest
import yaml

from sloplab.corpus.loader import FixtureError, discover_fixtures, load_canonical_fixture
from sloplab.corpus.validation import validate_corpus
from sloplab.safety.policy import validate_content_safety


def write_canonical_fixture(
    root: Path,
    short_name: str,
    *,
    fixture_id: str,
    title: str,
    report_class: str = "valid",
    required_evidence: list[str] | None = None,
    report_body: str | None = None,
) -> Path:
    fixture_dir = root / "canonical" / short_name
    fixture_dir.mkdir(parents=True, exist_ok=True)
    body = (
        report_body
        if report_body is not None
        else f"""\
# {title}

## Affected Component

DemoVault object lookup endpoint.

## Preconditions

Valid low-privilege account on the demo instance at https://demo.example.org.

## Reproduction Steps

1. Sign in as user A (tenant 1).
2. Send `GET /objects/42` with tenant 2 context.

## Observed Result

The object of tenant 2 is returned; reference CVE-2099-0001 tracks none of this.

## Expected Security Boundary

Cross-tenant object reads must require tenant-scoped authorization.
"""
    )
    (fixture_dir / "report.md").write_text(body, encoding="utf-8")
    manifest: dict[str, object] = {
        "id": fixture_id,
        "title": title,
        "report_class": report_class,
        "ground_truth": {
            "reproducible": True,
            "impact_class": "medium",
            "required_evidence": required_evidence
            if required_evidence is not None
            else [
                "affected_component",
                "preconditions",
                "reproduction_steps",
                "observed_result",
                "expected_security_boundary",
            ],
            "expected_dimensions": {"reproducibility": 0.9},
        },
        "report": {"path": f"canonical/{short_name}/report.md"},
    }
    (fixture_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return fixture_dir


class TestLoader:
    def test_load_valid_fixture(self, tmp_path: Path) -> None:
        write_canonical_fixture(
            tmp_path,
            "authz-001",
            fixture_id="canonical-authz-001",
            title="Missing authorization in DemoVault",
        )
        fixture = load_canonical_fixture(tmp_path / "canonical" / "authz-001", tmp_path)
        assert fixture.manifest.id == "canonical-authz-001"
        assert fixture.report.title == "Missing authorization in DemoVault"

    def test_missing_manifest_gives_actionable_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "canonical" / "empty-001"
        empty.mkdir(parents=True)
        with pytest.raises(FixtureError, match="missing manifest.yaml"):
            load_canonical_fixture(empty, tmp_path)

    def test_unknown_manifest_field_is_reported(self, tmp_path: Path) -> None:
        fixture_dir = write_canonical_fixture(
            tmp_path, "authz-002", fixture_id="canonical-authz-002", title="T"
        )
        mpath = fixture_dir / "manifest.yaml"
        data = yaml.safe_load(mpath.read_text())
        data["valdity"] = "typo"  # intentionally misspelled field
        mpath.write_text(yaml.safe_dump(data))
        with pytest.raises(FixtureError, match="valdity"):
            load_canonical_fixture(fixture_dir, tmp_path)

    def test_title_mismatch_flagged(self, tmp_path: Path) -> None:
        fixture_dir = write_canonical_fixture(
            tmp_path, "authz-003", fixture_id="canonical-authz-003", title="Correct Title"
        )
        mpath = fixture_dir / "manifest.yaml"
        data = yaml.safe_load(mpath.read_text())
        data["title"] = "Different Title"
        mpath.write_text(yaml.safe_dump(data))
        with pytest.raises(FixtureError, match="does not match report"):
            load_canonical_fixture(fixture_dir, tmp_path)

    def test_discover_finds_all_fixtures(self, tmp_path: Path) -> None:
        for i in range(3):
            write_canonical_fixture(
                tmp_path,
                f"case-{i:03d}",
                fixture_id=f"canonical-case-{i:03d}",
                title=f"Report {i}",
            )
        canonical, derived = discover_fixtures(tmp_path)
        assert len(canonical) == 3
        assert derived == []
        assert [f.fixture_id for f in canonical] == sorted(f.fixture_id for f in canonical)


class TestValidation:
    def test_missing_required_section_is_error(self, tmp_path: Path) -> None:
        body = "# Title X\n\n## Affected Component\n\nDemoVault.\n"
        write_canonical_fixture(
            tmp_path,
            "authz-004",
            fixture_id="canonical-authz-004",
            title="Title X",
            required_evidence=["affected_component", "reproduction_steps"],
            report_body=body,
        )
        canonical, _ = discover_fixtures(tmp_path)
        result = validate_corpus(canonical, [])
        assert not result.ok
        assert any("reproduction_steps" in i.message for i in result.errors)

    def test_clean_corpus_passes(self, tmp_path: Path) -> None:
        write_canonical_fixture(
            tmp_path, "authz-005", fixture_id="canonical-authz-005", title="Clean Report Five"
        )
        canonical, _ = discover_fixtures(tmp_path)
        result = validate_corpus(canonical, [])
        assert result.ok, result.render()


class TestSafetyPolicy:
    def test_real_year_cve_detected(self) -> None:
        violations = validate_content_safety("See CVE-2021-44228 for details.")
        assert len(violations) == 1
        assert "CVE-2021-44228" in violations[0]

    def test_fake_year_cve_allowed(self) -> None:
        assert validate_content_safety("Reference CVE-2099-12345.") == []

    def test_unsafe_url_detected(self) -> None:
        violations = validate_content_safety("Visit https://evil.attacker.com/payload now.")
        assert len(violations) == 1

    def test_loopback_and_localhost_allowed(self) -> None:
        text = "Probe http://127.0.0.1:7001/health and http://localhost:9000/attack-page."
        assert validate_content_safety(text) == []

    def test_private_ip_allowed_public_ip_rejected(self) -> None:
        assert validate_content_safety("POST http://10.0.0.5/admin") == []
        violations = validate_content_safety("GET https://93.184.216.34/path")
        assert len(violations) == 1

    def test_reserved_urls_allowed(self) -> None:
        text = (
            "Try https://demo.example.org/login or http://api.demo.example.com/v1 "
            "and https://example.edu/page."
        )
        assert validate_content_safety(text) == []

    def test_subdomain_of_reserved_allowed(self) -> None:
        assert validate_content_safety("https://deep.sub.example.net/x") == []

    def test_url_userinfo_does_not_hide_external_hostname(self) -> None:
        violations = validate_content_safety("GET http://localhost@attacker.com/private")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]

    def test_localhost_suffix_requires_hostname_boundary(self) -> None:
        violations = validate_content_safety(
            "GET http://fakelocalhost/path and http://notreally.localhost.evil.example/path"
        )
        assert len(violations) == 2

    def test_local_hostname_variants_and_ipv6_loopback_allowed(self) -> None:
        text = (
            "GET http://api.localhost:8080/x and http://device.local/y "
            "and http://user@localhost/z and http://[::1]:9000/health"
        )
        assert validate_content_safety(text) == []

    def test_lowercase_real_year_cve_detected(self) -> None:
        violations = validate_content_safety("See cve-2021-44228 for details.")
        assert len(violations) == 1
        assert "cve-2021-44228" in violations[0]

    def test_lowercase_fake_year_cve_allowed(self) -> None:
        assert validate_content_safety("Reference cve-2099-12345.") == []

    def test_reserved_url_with_trailing_prose_punctuation_allowed(self) -> None:
        text = "See http://example.com, then 'http://localhost' and http://api.localhost."
        assert validate_content_safety(text) == []

    def test_reserved_url_with_markdown_emphasis_allowed(self) -> None:
        text = "**http://localhost** and __https://demo.example.org__"
        assert validate_content_safety(text) == []

    def test_external_url_with_trailing_prose_punctuation_still_rejected(self) -> None:
        violations = validate_content_safety("See http://attacker.com, then continue.")
        assert len(violations) == 1
        assert "http://attacker.com" in violations[0]

    def test_backslash_authority_cannot_disguise_external_host(self) -> None:
        violations = validate_content_safety(r"GET http://attacker.com\@localhost/x")
        assert len(violations) == 1
        assert r"http://attacker.com\@localhost/x" in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_control_whitespace_cannot_disguise_external_host(self, control: str) -> None:
        violations = validate_content_safety(f"GET http://localhost{control}@attacker.com/x")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]
        assert "\t" not in violations[0]
        assert "\r" not in violations[0]
        assert "\n" not in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_nonadjacent_control_in_userinfo_cannot_hide_external_host(self, control: str) -> None:
        violations = validate_content_safety(f"GET http://localhost{control}user@attacker.com/x")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]
        assert control not in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_control_whitespace_cannot_extend_localhost(self, control: str) -> None:
        violations = validate_content_safety(f"GET http://localhost{control}.attacker.com/x")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]
        assert control not in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_encoded_dot_after_control_cannot_extend_localhost(self, control: str) -> None:
        violations = validate_content_safety(f"GET http://localhost{control}%2eattacker%2ecom/x")
        assert len(violations) == 1
        assert "%2eattacker%2ecom" in violations[0]
        assert control not in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_plain_control_authority_continuation_is_validated(self, control: str) -> None:
        violations = validate_content_safety(f"GET http://example.com{control}pany/x")
        assert len(violations) == 1
        assert "example.com" in violations[0]
        assert control not in violations[0]

    def test_blank_line_after_reserved_url_is_text_boundary(self) -> None:
        text = "Visit https://demo.example.org.\n\nAll demo systems use reserved targets."
        assert validate_content_safety(text) == []

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_control_inside_url_scheme_cannot_hide_external_host(self, control: str) -> None:
        violations = validate_content_safety(f"GET htt{control}p://attacker.com/x")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]
        assert control not in violations[0]

    @pytest.mark.parametrize("control", ["\t", "\r", "\n"])
    def test_control_inside_url_separators_cannot_hide_external_host(self, control: str) -> None:
        samples = (
            f"http:{control}//attacker.com/x",
            f"http:/{control}/attacker.com/x",
        )
        for sample in samples:
            violations = validate_content_safety(f"GET {sample}")
            assert len(violations) == 1
            assert "attacker.com" in violations[0]
            assert control not in violations[0]

    def test_control_obfuscated_scheme_to_reserved_host_remains_allowed(self) -> None:
        assert validate_content_safety("GET htt\np://localhost/x") == []

    def test_control_and_backslash_combination_is_rejected(self) -> None:
        violations = validate_content_safety("GET http://localhost\tattacker.com\\@localhost/x")
        assert len(violations) == 1
        assert "attacker.com" in violations[0]
        assert "\t" not in violations[0]
