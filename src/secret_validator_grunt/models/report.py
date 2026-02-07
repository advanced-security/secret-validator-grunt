from __future__ import annotations

from typing import Optional, List, Any
from pydantic import BaseModel, Field
import re

from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.parsing import (
    parse_sections,
    extract_section,
    extract_table_from_section,
    extract_bullets,
)

logger = get_logger(__name__)

SUMMARY_ROW_RE = re.compile(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.M)
CONFIDENCE_RE = re.compile(
    r"(?P<score>[0-9]+(?:\.[0-9]+)?)\s*/\s*10\s*\((?P<label>[^)]+)\)")
KEY_FINDING_RE = re.compile(r">\s*\*\*Key Finding\:\*\*\s*(.*)")


class ReportScore(BaseModel):
	"""Score for an individual factor in the confidence scoring table."""

	factor: str = Field(description="Scoring factor")
	score: float = Field(description="Score value")
	rationale: Optional[str] = Field(default=None,
	                                 description="Score rationale")


class Report(BaseModel):
	"""Structured representation of a secret validation report."""

	alert_id: Optional[str] = None
	repository: Optional[str] = None
	secret_type: Optional[str] = None
	verdict: Optional[str] = None
	confidence_score: Optional[float] = None
	confidence_label: Optional[str] = None
	risk_level: Optional[str] = None
	status: Optional[str] = None
	analyst: Optional[str] = None
	report_date: Optional[str] = None
	key_finding: Optional[str] = None

	# Raw markdown representation
	raw_markdown: Optional[str] = None

	# Optional detail sections
	locations: Optional[str] = None
	locations_table: Optional[List[dict]] = None
	context: Optional[str] = None
	verification_testing: Optional[str] = None
	verification_tests: Optional[List[dict]] = None
	documentary_evidence: Optional[str] = None
	evidence_analysis: Optional[str] = None
	evidence_analysis_table: Optional[List[dict]] = None
	confidence_scoring: Optional[List[ReportScore]] = None
	confidence_scoring_table: Optional[List[dict]] = None
	risk_assessment: Optional[str] = None
	risk_assessment_table: Optional[List[dict]] = None
	verdict_details: Optional[str] = None

	@classmethod
	def from_markdown(cls, md: str) -> "Report":
		"""Parse canonical report markdown into a Report model."""
		data = {}
		# Executive Summary table
		for key, val in SUMMARY_ROW_RE.findall(md):
			k = key.strip().lower()
			v = val.strip()
			if k == "repository":
				data["repository"] = v
			elif k == "alert id":
				data["alert_id"] = v
			elif k == "secret type":
				data["secret_type"] = v
			elif k == "verdict":
				data["verdict"] = v
			elif k == "confidence score":
				m = CONFIDENCE_RE.search(v)
				if m:
					data["confidence_score"] = float(m.group("score"))
					data["confidence_label"] = m.group("label")
				else:
					data["confidence_score"] = None
					data["confidence_label"] = v
			elif k == "risk level":
				data["risk_level"] = v
			elif k == "status":
				data["status"] = v
			elif k == "analyst":
				data["analyst"] = v
			elif k == "report date":
				data["report_date"] = v
		key_finding_match = KEY_FINDING_RE.search(md)
		if key_finding_match:
			data["key_finding"] = key_finding_match.group(1).strip()

		# Sections
		# Locations
		loc_table = extract_table_from_section(md, "Locations")
		if loc_table:
			data["locations_table"] = loc_table
		loc_section = extract_section(md, "Locations")
		if loc_section:
			data["locations"] = loc_section

		# Context and Intent
		ctx = extract_section(md, "Context and Intent")
		if ctx:
			data["context"] = ctx

		# Verification Testing
		ver_table = extract_table_from_section(md, "Verification Testing")
		if ver_table:
			data["verification_tests"] = ver_table
		else:
			# also try singular heading
			alt_ver_table = extract_table_from_section(md, "Verification Test")
			if alt_ver_table:
				data["verification_tests"] = alt_ver_table
		ver = extract_section(md, "Verification Testing")
		if ver:
			data["verification_testing"] = ver

		# Documentary Evidence
		doc = extract_section(md, "Documentary Evidence")
		if doc:
			bullets = extract_bullets(doc)
			data["documentary_evidence"] = ("\n".join(bullets)
			                                if bullets else doc)

		# Evidence Analysis
		ea_table = extract_table_from_section(md, "Evidence Analysis")
		if ea_table:
			data["evidence_analysis_table"] = ea_table
		ea = extract_section(md, "Evidence Analysis")
		if ea:
			data["evidence_analysis"] = ea

		# Confidence Scoring
		cs_table = extract_table_from_section(md, "Confidence Scoring")
		if cs_table:
			data["confidence_scoring_table"] = cs_table
			try:

				def _score(v: Any) -> float:
					s = float(v or 0)
					return max(0.0, min(10.0, s))

				data["confidence_scoring"] = [
				    ReportScore(
				        factor=row.get("Factor", row.get("factor", "")) or "",
				        score=_score(row.get("Score", row.get("score", 0))),
				        rationale=row.get("Rationale", row.get("rationale")),
				    ) for row in cs_table
				]
			except Exception as exc:
				logger.debug("confidence scoring parse failed: %s", exc)
		cs = extract_section(md, "Confidence Scoring")
		if cs:
			data["confidence_scoring"] = data.get("confidence_scoring") or None

		# Risk Assessment
		ra_table = extract_table_from_section(md, "Risk Assessment")
		if ra_table:
			data["risk_assessment_table"] = ra_table
		ra = extract_section(md, "Risk Assessment")
		if ra:
			data["risk_assessment"] = ra

		# Verdict
		vd = extract_section(md, "Verdict")
		if vd:
			data["verdict_details"] = vd

		return cls(raw_markdown=md, **data)


__all__ = ["Report", "ReportScore"]
