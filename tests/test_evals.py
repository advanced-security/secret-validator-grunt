"""Tests for the report evaluation framework."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from secret_validator_grunt.models.report import Report
from secret_validator_grunt.models.eval_result import EvalCheck, EvalResult
from secret_validator_grunt.evals.checks import (
    run_all_checks,
    has_required_sections,
    valid_verdict,
    valid_confidence_score,
    confidence_label_matches_score,
    metadata_complete,
    has_key_finding,
    has_verification_tests,
    has_code_evidence,
    verdict_confidence_coherent,
    score_to_label,
    VALID_VERDICTS,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "reports"


def _load_fixture(name: str, ) -> tuple[str, dict[str, Any]]:
	"""Load a fixture markdown + metadata JSON by base name."""
	md_path = FIXTURES_DIR / f"{name}.md"
	json_path = FIXTURES_DIR / f"{name}.json"
	md = md_path.read_text(encoding="utf-8")
	meta = json.loads(json_path.read_text(encoding="utf-8"))
	return md, meta


def _list_good_fixtures() -> list[str]:
	"""Return base names of fixtures expected to pass all checks."""
	return [
	    p.stem for p in FIXTURES_DIR.glob("*.json")
	    if not p.stem.startswith("bad-")
	    and json.loads(p.read_text()).get("expect_pass") is not False
	]


# Minimal valid report markdown for unit tests.
GOOD_MD = """\
# Secret Validation Report

## Executive Summary

| Item             | Value                       |
| ---------------- | --------------------------- |
| Repository       | org/repo                    |
| Alert ID         | 42                          |
| Secret Type      | github_token                |
| Verdict          | TRUE_POSITIVE               |
| Confidence Score | 8.5/10 (High)               |
| Risk Level       | High                        |
| Status           | Open                        |
| Analyst          | Test                        |
| Report Date      | 2026-02-10                  |

> **Key Finding:** This is a real credential.

## 1. Secret Alert Details

- **Secret Type:** github_token
- **Detection Date:** 2026-02-10

## 2. Locations

| Path      | Line | Commit  | Notes |
| --------- | ---- | ------- | ----- |
| `config.py` | 10   | abc1234 | Found |

## 3. Context and Intent

Some context about the secret.

## 4. Verification Testing

| # | Test   | Method | Result  | Evidence   |
| - | ------ | ------ | ------- | ---------- |
| 1 | Check  | curl   | Success | 200 OK     |

## 5. Documentary Evidence

- `config.py` line 10

## 6. Evidence Analysis

| Dimension | Finding     | Confidence |
| --------- | ----------- | ---------- |
| Technical | Real token  | 90%        |

## 7. Confidence Scoring

| Factor   | Score | Rationale    |
| -------- | ----- | ------------ |
| Recency  | 9     | Very recent  |

## 8. Risk Assessment

| Risk Factor    | Assessment |
| -------------- | ---------- |
| Exploitability | High       |

## 9. Verdict

- **Verdict:** TRUE_POSITIVE
- **Immediate Actions:** Rotate credential
"""

EMPTY_REPORT = Report()

# ---------------------------------------------------------------------------
# EvalCheck / EvalResult model tests
# ---------------------------------------------------------------------------


class TestEvalCheckModel:
	"""Test the EvalCheck Pydantic model."""

	def test_defaults(self):
		"""Default severity is error."""
		c = EvalCheck(name="test", passed=True)
		assert c.severity == "error"
		assert c.message is None

	def test_all_fields(self):
		"""All fields round-trip correctly."""
		c = EvalCheck(
		    name="x",
		    passed=False,
		    message="bad",
		    severity="warning",
		)
		assert c.name == "x"
		assert c.passed is False
		assert c.message == "bad"
		assert c.severity == "warning"

	def test_invalid_severity_rejected(self):
		"""Invalid severity value is rejected by Pydantic."""
		with pytest.raises(ValidationError):
			EvalCheck(
			    name="x",
			    passed=True,
			    severity="critical",
			)


class TestEvalResultModel:
	"""Test the EvalResult Pydantic model."""

	def test_passed_all_ok(self):
		"""Passed is True when all error-severity checks pass."""
		result = EvalResult(
		    report_id="r1",
		    checks=[
		        EvalCheck(name="a", passed=True),
		        EvalCheck(name="b", passed=True),
		    ],
		)
		assert result.passed is True

	def test_passed_ignores_warnings(self):
		"""Passed ignores failed warning-severity checks."""
		result = EvalResult(
		    report_id="r1",
		    checks=[
		        EvalCheck(name="a", passed=True),
		        EvalCheck(
		            name="b",
		            passed=False,
		            severity="warning",
		        ),
		    ],
		)
		assert result.passed is True

	def test_passed_fails_on_error(self):
		"""Passed is False when any error-severity check fails."""
		result = EvalResult(
		    report_id="r1",
		    checks=[
		        EvalCheck(name="a", passed=True),
		        EvalCheck(name="b", passed=False),
		    ],
		)
		assert result.passed is False

	def test_score_all_pass(self):
		"""Score is 1.0 when all checks pass."""
		result = EvalResult(
		    report_id="r1",
		    checks=[
		        EvalCheck(name="a", passed=True),
		        EvalCheck(name="b", passed=True),
		    ],
		)
		assert result.score == 1.0

	def test_score_half_pass(self):
		"""Score is 0.5 when half the checks pass."""
		result = EvalResult(
		    report_id="r1",
		    checks=[
		        EvalCheck(name="a", passed=True),
		        EvalCheck(name="b", passed=False),
		    ],
		)
		assert result.score == 0.5

	def test_score_empty(self):
		"""Score is 0.0 when there are no checks."""
		result = EvalResult(report_id="r1", checks=[])
		assert result.score == 0.0


# ---------------------------------------------------------------------------
# Individual check function tests
# ---------------------------------------------------------------------------


class TestHasRequiredSections:
	"""Test has_required_sections check."""

	def test_good_report(self):
		"""Report with all sections passes."""
		report = Report.from_markdown(GOOD_MD)
		c = has_required_sections(report)
		assert c.passed is True

	def test_empty_report(self):
		"""Empty report fails with missing sections."""
		c = has_required_sections(EMPTY_REPORT)
		assert c.passed is False
		assert "Missing sections" in (c.message or "")

	def test_partial_sections(self):
		"""Report with some sections lists the missing ones."""
		md = "## Executive Summary\n\n## Verdict\n"
		report = Report.from_markdown(md)
		c = has_required_sections(report)
		assert c.passed is False
		assert "Locations" in (c.message or "")


class TestValidVerdict:
	"""Test valid_verdict check."""

	@pytest.mark.parametrize("verdict", sorted(VALID_VERDICTS))
	def test_valid_verdicts(self, verdict):
		"""All valid verdicts pass."""
		report = Report(verdict=verdict)
		c = valid_verdict(report)
		assert c.passed is True

	def test_case_insensitive(self):
		"""Verdict check is case-insensitive."""
		report = Report(verdict="false_positive")
		c = valid_verdict(report)
		assert c.passed is True

	def test_invalid_verdict(self):
		"""Invalid verdict fails."""
		report = Report(verdict="MAYBE")
		c = valid_verdict(report)
		assert c.passed is False
		assert "MAYBE" in (c.message or "")

	def test_missing_verdict(self):
		"""Missing verdict fails."""
		c = valid_verdict(EMPTY_REPORT)
		assert c.passed is False


class TestValidConfidenceScore:
	"""Test valid_confidence_score check."""

	def test_valid_score(self):
		"""Score in range passes."""
		report = Report(confidence_score=7.5)
		c = valid_confidence_score(report)
		assert c.passed is True

	def test_zero_score(self):
		"""Score of 0 is valid."""
		report = Report(confidence_score=0.0)
		c = valid_confidence_score(report)
		assert c.passed is True

	def test_ten_score(self):
		"""Score of 10 is valid."""
		report = Report(confidence_score=10.0)
		c = valid_confidence_score(report)
		assert c.passed is True

	def test_negative_score(self):
		"""Negative score fails."""
		report = Report(confidence_score=-1.0)
		c = valid_confidence_score(report)
		assert c.passed is False

	def test_over_ten(self):
		"""Score > 10 fails."""
		report = Report(confidence_score=11.0)
		c = valid_confidence_score(report)
		assert c.passed is False

	def test_missing_score(self):
		"""Missing score fails."""
		c = valid_confidence_score(EMPTY_REPORT)
		assert c.passed is False


class TestConfidenceLabelMatchesScore:
	"""Test confidence_label_matches_score check."""

	def test_high_match(self):
		"""High label with score >= 7 passes."""
		report = Report(confidence_score=8.0, confidence_label="High")
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_medium_match(self):
		"""Medium label with score 4-6.9 passes."""
		report = Report(
		    confidence_score=5.5,
		    confidence_label="Medium",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_low_match(self):
		"""Low label with score < 4 passes."""
		report = Report(confidence_score=2.0, confidence_label="Low")
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_mismatch(self):
		"""Wrong label for score fails."""
		report = Report(
		    confidence_score=8.0,
		    confidence_label="Low",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is False

	def test_missing_label(self):
		"""Missing label fails."""
		report = Report(confidence_score=5.0)
		c = confidence_label_matches_score(report)
		assert c.passed is False

	def test_boundary_7(self):
		"""Score exactly 7.0 should be High."""
		report = Report(
		    confidence_score=7.0,
		    confidence_label="High",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_boundary_4(self):
		"""Score exactly 4.0 should be Medium."""
		report = Report(
		    confidence_score=4.0,
		    confidence_label="Medium",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_boundary_6_99_is_medium(self):
		"""Score 6.99 should be Medium, not High."""
		report = Report(
		    confidence_score=6.99,
		    confidence_label="Medium",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is True

	def test_boundary_6_99_not_high(self):
		"""Score 6.99 labelled High should fail."""
		report = Report(
		    confidence_score=6.99,
		    confidence_label="High",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is False

	def test_boundary_3_99_is_low(self):
		"""Score 3.99 should be Low, not Medium."""
		report = Report(
		    confidence_score=3.99,
		    confidence_label="Low",
		)
		c = confidence_label_matches_score(report)
		assert c.passed is True


class TestScoreToLabel:
	"""Test the score_to_label helper directly."""

	@pytest.mark.parametrize("score,expected", [
	    (0.0, "low"),
	    (3.99, "low"),
	    (4.0, "medium"),
	    (6.99, "medium"),
	    (7.0, "high"),
	    (10.0, "high"),
	])
	def test_boundary_mapping(self, score, expected):
		"""Boundary scores map to the correct label."""
		assert score_to_label(score) == expected

	def test_negative_returns_none(self):
		"""Negative score returns None."""
		assert score_to_label(-0.1) is None

	def test_over_ten_returns_none(self):
		"""Score > 10 returns None."""
		assert score_to_label(10.1) is None


class TestMetadataComplete:
	"""Test metadata_complete check."""

	def test_complete(self):
		"""Report with all metadata passes."""
		report = Report(
		    repository="org/repo",
		    alert_id="1",
		    secret_type="token",
		    report_date="2026-01-01",
		)
		c = metadata_complete(report)
		assert c.passed is True

	def test_missing_all(self):
		"""Empty report fails with all fields missing."""
		c = metadata_complete(EMPTY_REPORT)
		assert c.passed is False
		assert "repository" in (c.message or "")

	def test_partial(self):
		"""Report with some fields missing lists them."""
		report = Report(repository="org/repo", alert_id="1")
		c = metadata_complete(report)
		assert c.passed is False
		assert "secret_type" in (c.message or "")


class TestHasKeyFinding:
	"""Test has_key_finding check."""

	def test_present(self):
		"""Report with key finding passes."""
		report = Report(key_finding="Important stuff")
		c = has_key_finding(report)
		assert c.passed is True

	def test_missing(self):
		"""Empty key finding fails."""
		c = has_key_finding(EMPTY_REPORT)
		assert c.passed is False

	def test_whitespace_only(self):
		"""Whitespace-only key finding fails."""
		report = Report(key_finding="   ")
		c = has_key_finding(report)
		assert c.passed is False


class TestHasVerificationTests:
	"""Test has_verification_tests check."""

	def test_with_table(self):
		"""Report with verification_tests table passes."""
		report = Report(verification_tests=[{
		    "test": "check",
		    "result": "ok"
		}], )
		c = has_verification_tests(report)
		assert c.passed is True
		assert c.severity == "warning"

	def test_with_section_text(self):
		"""Report with verification_testing text passes."""
		report = Report(verification_testing="Some test content")
		c = has_verification_tests(report)
		assert c.passed is True

	def test_missing(self):
		"""Report without verification content fails."""
		c = has_verification_tests(EMPTY_REPORT)
		assert c.passed is False
		assert c.severity == "warning"


class TestHasCodeEvidence:
	"""Test has_code_evidence check."""

	def test_with_file_paths(self):
		"""Report markdown containing file paths passes."""
		report = Report(raw_markdown="Found in `config.py` line 10")
		c = has_code_evidence(report)
		assert c.passed is True
		assert c.severity == "warning"

	def test_with_code_blocks(self):
		"""Report markdown with fenced code blocks passes."""
		report = Report(raw_markdown="```python\nprint('hi')\n```", )
		c = has_code_evidence(report)
		assert c.passed is True

	def test_bare_file_path(self):
		"""Bare file path like src/main.py is detected."""
		report = Report(raw_markdown="Located at src/main.py")
		c = has_code_evidence(report)
		assert c.passed is True

	def test_no_evidence(self):
		"""Plain text without file refs or code fails."""
		report = Report(raw_markdown="No evidence here whatsoever")
		c = has_code_evidence(report)
		assert c.passed is False
		assert c.severity == "warning"

	def test_empty_markdown(self):
		"""Empty markdown fails."""
		c = has_code_evidence(EMPTY_REPORT)
		assert c.passed is False

	def test_bare_numbers_not_matched(self):
		"""Bare numbers like 6.7 or 10.0 are not file paths."""
		md = "Confidence score is 6.7/10 (Medium)"
		report = Report(raw_markdown=md)
		c = has_code_evidence(report)
		assert c.passed is False


class TestVerdictConfidenceCoherent:
	"""Test verdict_confidence_coherent check."""

	def test_true_positive_high_confidence(self):
		"""TRUE_POSITIVE with high confidence is coherent."""
		report = Report(
		    verdict="TRUE_POSITIVE",
		    confidence_score=9.0,
		)
		c = verdict_confidence_coherent(report)
		assert c.passed is True

	def test_false_positive_high_confidence(self):
		"""FALSE_POSITIVE with high confidence is coherent."""
		report = Report(
		    verdict="FALSE_POSITIVE",
		    confidence_score=8.5,
		)
		c = verdict_confidence_coherent(report)
		assert c.passed is True

	def test_inconclusive_low_confidence(self):
		"""INCONCLUSIVE with low confidence is coherent."""
		report = Report(
		    verdict="INCONCLUSIVE",
		    confidence_score=3.0,
		)
		c = verdict_confidence_coherent(report)
		assert c.passed is True

	def test_inconclusive_medium_confidence(self):
		"""INCONCLUSIVE with medium confidence is coherent."""
		report = Report(
		    verdict="INCONCLUSIVE",
		    confidence_score=5.0,
		)
		c = verdict_confidence_coherent(report)
		assert c.passed is True

	def test_inconclusive_high_confidence(self):
		"""INCONCLUSIVE with high confidence is incoherent."""
		report = Report(
		    verdict="INCONCLUSIVE",
		    confidence_score=8.0,
		)
		c = verdict_confidence_coherent(report)
		assert c.passed is False
		assert "incoherent" in (c.message or "").lower()

	def test_missing_verdict(self):
		"""Missing verdict passes (no assertion to make)."""
		c = verdict_confidence_coherent(EMPTY_REPORT)
		assert c.passed is True


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------


class TestRunAllChecks:
	"""Test the run_all_checks orchestrator."""

	def test_good_report_passes(self):
		"""Synthetic good report passes all checks."""
		report = Report.from_markdown(GOOD_MD)
		result = run_all_checks(report, report_id="good")
		assert result.report_id == "good"
		assert result.passed is True
		assert len(result.checks) == 9
		# All error-severity checks should pass
		errors = [
		    c for c in result.checks if c.severity == "error" and not c.passed
		]
		assert errors == [], (f"Failed error checks: "
		                      f"{[c.name for c in errors]}")

	def test_empty_report_fails(self):
		"""Empty report fails multiple checks."""
		result = run_all_checks(EMPTY_REPORT, report_id="empty")
		assert result.passed is False
		failed = [c.name for c in result.checks if not c.passed]
		assert "valid_verdict" in failed
		assert "valid_confidence_score" in failed
		assert "metadata_complete" in failed
		assert "has_key_finding" in failed

	def test_check_count(self):
		"""Run_all_checks produces exactly 9 checks."""
		result = run_all_checks(EMPTY_REPORT)
		assert len(result.checks) == 9

	def test_default_report_id(self):
		"""Default report_id is 'unknown'."""
		result = run_all_checks(EMPTY_REPORT)
		assert result.report_id == "unknown"


# ---------------------------------------------------------------------------
# Fixture-based integration tests
# ---------------------------------------------------------------------------


class TestFixtureReports:
	"""Test eval checks against real captured report fixtures."""

	@pytest.mark.parametrize("fixture_name", _list_good_fixtures())
	def test_good_fixture_passes(self, fixture_name):
		"""Good fixture reports pass all eval checks."""
		md, meta = _load_fixture(fixture_name)
		report = Report.from_markdown(md)
		result = run_all_checks(report, report_id=fixture_name)
		# All error-severity checks should pass
		errors = [
		    c for c in result.checks if c.severity == "error" and not c.passed
		]
		assert errors == [], (f"Fixture {fixture_name} failed error checks: "
		                      f"{[(c.name, c.message) for c in errors]}")

	@pytest.mark.parametrize("fixture_name", _list_good_fixtures())
	def test_good_fixture_verdict_matches(self, fixture_name):
		"""Good fixture verdict matches expected metadata."""
		md, meta = _load_fixture(fixture_name)
		report = Report.from_markdown(md)
		expected_verdict = meta.get("verdict")
		if expected_verdict:
			assert report.verdict == expected_verdict, (
			    f"Expected verdict {expected_verdict}, "
			    f"got {report.verdict}")

	@pytest.mark.parametrize("fixture_name", _list_good_fixtures())
	def test_good_fixture_score_in_range(self, fixture_name):
		"""Good fixture score is within expected range."""
		md, meta = _load_fixture(fixture_name)
		report = Report.from_markdown(md)
		score_range = meta.get("score_range")
		if score_range and report.confidence_score is not None:
			lo, hi = score_range
			assert lo <= report.confidence_score <= hi, (
			    f"Score {report.confidence_score} outside "
			    f"range [{lo}, {hi}]")

	def test_bad_report_fails(self):
		"""Bad report fixture fails expected checks."""
		md, meta = _load_fixture("bad-report")
		report = Report.from_markdown(md)
		result = run_all_checks(report, report_id="bad-report")
		assert result.passed is False
		failed_names = {c.name for c in result.checks if not c.passed}
		for expected_fail in meta.get("expected_failures", []):
			assert expected_fail in failed_names, (
			    f"Expected {expected_fail} to fail, "
			    f"but it passed")
