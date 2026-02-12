"""
Deterministic evaluation checks for secret validation reports.

Each check is a pure function: (Report) -> EvalCheck.
Checks can be composed via run_all_checks() which returns
an EvalResult with all check outcomes.
"""

from __future__ import annotations

import re

from secret_validator_grunt.models.eval_result import EvalCheck, EvalResult
from secret_validator_grunt.models.report import Report

# Valid verdict values the system may produce.
VALID_VERDICTS = frozenset({
	"TRUE_POSITIVE",
	"FALSE_POSITIVE",
	"SUSPICIOUS",
	"INCONCLUSIVE",
})

# Required section headings (checked against raw markdown).
REQUIRED_SECTIONS = [
	"Executive Summary",
	"Locations",
	"Context and Intent",
	"Verification Testing",
	"Documentary Evidence",
	"Evidence Analysis",
	"Confidence Scoring",
	"Risk Assessment",
	"Verdict",
]

# Confidence label boundaries (exclusive upper for lower tiers).
# High: score >= 7.0, Medium: 4.0 <= score < 7.0, Low: score < 4.0
#
# Boundary ownership is explicit in _score_to_label() below;
# do NOT rely on dict ordering or overlapping ranges.

# Regex for detecting file path references in markdown.
# Requires an alphabetic lead-in to avoid matching bare numbers
# like confidence scores (e.g. "6.7").
FILE_PATH_RE = re.compile(
	r"(?:`[^`]*\.[a-zA-Z]{1,10}`"     # backtick-wrapped filenames
	r"|[a-zA-Z][\w/\\.-]*\.\w{2,10})"  # bare paths: alpha start
)

# Regex for fenced code blocks.
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")


def has_required_sections(report: Report) -> EvalCheck:
	"""Check that the report contains all required section headings."""
	md = report.raw_markdown or ""
	missing = []
	for section in REQUIRED_SECTIONS:
		# Match markdown headings at any level: ## Section, ### Section
		pattern = re.compile(
			rf"^#+\s+(?:\d+\.\s+)?{re.escape(section)}",
			re.MULTILINE | re.IGNORECASE,
		)
		if not pattern.search(md):
			missing.append(section)
	if missing:
		return EvalCheck(
			name="has_required_sections",
			passed=False,
			message=f"Missing sections: {', '.join(missing)}",
		)
	return EvalCheck(
		name="has_required_sections",
		passed=True,
		message="All required sections present",
	)


def valid_verdict(report: Report) -> EvalCheck:
	"""Check that the verdict is one of the allowed values."""
	verdict = (report.verdict or "").strip().upper()
	if verdict in VALID_VERDICTS:
		return EvalCheck(
			name="valid_verdict",
			passed=True,
			message=f"Verdict: {verdict}",
		)
	return EvalCheck(
		name="valid_verdict",
		passed=False,
		message=(
			f"Invalid verdict '{report.verdict}'; "
			f"expected one of: {', '.join(sorted(VALID_VERDICTS))}"
		),
	)


def valid_confidence_score(report: Report) -> EvalCheck:
	"""Check that the confidence score is a number between 0 and 10."""
	score = report.confidence_score
	if score is None:
		return EvalCheck(
			name="valid_confidence_score",
			passed=False,
			message="Confidence score is missing",
		)
	if not isinstance(score, (int, float)):
		return EvalCheck(
			name="valid_confidence_score",
			passed=False,
			message=f"Confidence score is not numeric: {score}",
		)
	if 0.0 <= score <= 10.0:
		return EvalCheck(
			name="valid_confidence_score",
			passed=True,
			message=f"Score: {score}/10",
		)
	return EvalCheck(
		name="valid_confidence_score",
		passed=False,
		message=f"Score {score} outside valid range 0–10",
	)


def _score_to_label(score: float) -> str | None:
	"""Map a confidence score to its expected label.

	Boundaries are exclusive on the upper end for lower tiers:
	  High:   score >= 7.0
	  Medium: 4.0 <= score < 7.0
	  Low:    0.0 <= score < 4.0

	Returns None if the score is outside [0, 10].
	"""
	if score < 0.0 or score > 10.0:
		return None
	if score >= 7.0:
		return "high"
	if score >= 4.0:
		return "medium"
	return "low"


def confidence_label_matches_score(report: Report) -> EvalCheck:
	"""Check that the confidence label matches the score."""
	score = report.confidence_score
	label = (report.confidence_label or "").strip().lower()
	if score is None or not label:
		return EvalCheck(
			name="confidence_label_matches_score",
			passed=False,
			message="Score or label missing; cannot validate",
		)
	expected = _score_to_label(score)
	if expected is None:
		return EvalCheck(
			name="confidence_label_matches_score",
			passed=False,
			message=f"Score {score} outside valid range",
		)
	if label == expected:
		return EvalCheck(
			name="confidence_label_matches_score",
			passed=True,
			message=f"Label '{label}' matches score {score}",
		)
	return EvalCheck(
		name="confidence_label_matches_score",
		passed=False,
		message=(
			f"Label '{label}' does not match score "
			f"{score}; expected '{expected}'"
		),
	)


def metadata_complete(report: Report) -> EvalCheck:
	"""Check that key metadata fields are populated."""
	missing = []
	for field in ("repository", "alert_id", "secret_type", "report_date"):
		val = getattr(report, field, None)
		if not val or not str(val).strip():
			missing.append(field)
	if missing:
		return EvalCheck(
			name="metadata_complete",
			passed=False,
			message=f"Missing metadata: {', '.join(missing)}",
		)
	return EvalCheck(
		name="metadata_complete",
		passed=True,
		message="All metadata fields populated",
	)


def has_key_finding(report: Report) -> EvalCheck:
	"""Check that the Key Finding block exists and is non-empty."""
	kf = (report.key_finding or "").strip()
	if kf:
		return EvalCheck(
			name="has_key_finding",
			passed=True,
			message="Key finding present",
		)
	return EvalCheck(
		name="has_key_finding",
		passed=False,
		message="Key finding is missing or empty",
	)


def has_verification_tests(report: Report) -> EvalCheck:
	"""Check that the Verification Testing section has content.

	Severity: warning — not all analyses produce explicit tests.
	"""
	has_table = bool(report.verification_tests)
	has_section = bool(
		(report.verification_testing or "").strip()
	)
	if has_table or has_section:
		return EvalCheck(
			name="has_verification_tests",
			passed=True,
			message="Verification testing content present",
			severity="warning",
		)
	return EvalCheck(
		name="has_verification_tests",
		passed=False,
		message="No verification testing content found",
		severity="warning",
	)


def has_code_evidence(report: Report) -> EvalCheck:
	"""Check that the report references file paths or code snippets.

	Severity: warning — indicates tool usage quality.
	"""
	md = report.raw_markdown or ""
	has_paths = bool(FILE_PATH_RE.search(md))
	has_code = bool(CODE_BLOCK_RE.search(md))
	if has_paths or has_code:
		return EvalCheck(
			name="has_code_evidence",
			passed=True,
			message="Report contains code evidence",
			severity="warning",
		)
	return EvalCheck(
		name="has_code_evidence",
		passed=False,
		message="No file paths or code snippets found",
		severity="warning",
	)


def verdict_confidence_coherent(report: Report) -> EvalCheck:
	"""Check verdict-confidence coherence.

	An INCONCLUSIVE verdict with high confidence (>= 7) is
	incoherent — if you're highly confident, you should be
	able to reach a definitive conclusion.
	"""
	verdict = (report.verdict or "").strip().upper()
	score = report.confidence_score
	if verdict != "INCONCLUSIVE" or score is None:
		return EvalCheck(
			name="verdict_confidence_coherent",
			passed=True,
			message="Verdict-confidence coherence OK",
		)
	if score >= 7.0:
		return EvalCheck(
			name="verdict_confidence_coherent",
			passed=False,
			message=(
				f"INCONCLUSIVE verdict with high confidence "
				f"({score}/10) is incoherent"
			),
		)
	return EvalCheck(
		name="verdict_confidence_coherent",
		passed=True,
		message=(
			f"INCONCLUSIVE with score {score}/10 is coherent"
		),
	)


# --- Orchestrator ---

ALL_CHECKS = [
	has_required_sections,
	valid_verdict,
	valid_confidence_score,
	confidence_label_matches_score,
	metadata_complete,
	has_key_finding,
	has_verification_tests,
	has_code_evidence,
	verdict_confidence_coherent,
]


def run_all_checks(
	report: Report,
	report_id: str = "unknown",
) -> EvalResult:
	"""Run all eval checks on a report and return results.

	Parameters:
		report: The parsed Report to evaluate.
		report_id: An identifier for this report.

	Returns:
		EvalResult with all check outcomes.
	"""
	checks: list[EvalCheck] = []
	for check_fn in ALL_CHECKS:
		checks.append(check_fn(report))
	return EvalResult(report_id=report_id, checks=checks)
