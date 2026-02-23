"""
Challenge result model.

Defines the ChallengeResult Pydantic model representing
the outcome of an adversarial challenge on a single
secret validation report.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .usage import UsageStats
from .skill_usage import SkillUsageStats
from .tool_usage import ToolUsageStats

VALID_CHALLENGE_VERDICTS = frozenset({
    "CONFIRMED",  # Challenger agrees the verdict is correct
    "REFUTED",  # Challenger found evidence contradicting verdict
    "INSUFFICIENT_EVIDENCE",  # Cannot determine — not enough info to challenge
})


class ChallengeResult(BaseModel):
	"""
	Result of adversarial challenge on a secret validation report.

	The challenger inspects the analysis workspace, re-runs verification
	scripts, and independently tests claims to determine if the report's
	verdict should be trusted.
	"""

	verdict: str = Field(
	    description=("Challenge outcome: CONFIRMED (agrees with report's "
	                 "verdict), REFUTED (disagrees — evidence contradicts), "
	                 "or INSUFFICIENT_EVIDENCE (cannot determine)"), )
	reasoning: str = Field(
	    default="",
	    description="Detailed explanation of the challenge verdict",
	)
	evidence_gaps: list[str] = Field(
	    default_factory=list,
	    description=("Gaps in the report's evidence that the challenger "
	                 "identified (e.g., 'no verification script executed', "
	                 "'rotation status not checked', 'accepted alert "
	                 "validity at face value')"),
	)
	verification_reproduced: bool | None = Field(
	    default=None,
	    description=("Whether the challenger independently reproduced "
	                 "the report's verification results. None if not "
	                 "attempted."),
	)
	verification_result: str | None = Field(
	    default=None,
	    description=("The challenger's own verification result when "
	                 "they independently tested the secret. E.g., "
	                 "'connection refused', 'authentication succeeded', "
	                 "'401 Unauthorized'."),
	)
	contradicting_evidence: list[str] = Field(
	    default_factory=list,
	    description=("Specific evidence found that contradicts the "
	                 "report's conclusion. Empty if verdict is "
	                 "CONFIRMED."),
	)

	# Usage tracking fields (populated when --show-usage is active)
	usage: UsageStats | None = Field(
	    default=None,
	    description=("Token usage and cost metrics for the challenge "
	                 "session. None if usage tracking is disabled."),
	)
	skill_usage: SkillUsageStats | None = Field(
	    default=None,
	    description=("Skill invocation statistics for the challenge "
	                 "session. None if not tracked."),
	)
	tool_usage: ToolUsageStats | None = Field(
	    default=None,
	    description=("Tool invocation statistics for the challenge "
	                 "session. None if not tracked."),
	)

	@field_validator("verdict")
	@classmethod
	def validate_verdict(cls, v: str) -> str:
		"""Normalize and validate challenge verdict."""
		upper = v.upper().strip()
		if upper not in VALID_CHALLENGE_VERDICTS:
			raise ValueError(f"verdict must be one of "
			                 f"{sorted(VALID_CHALLENGE_VERDICTS)}, "
			                 f"got '{v}'")
		return upper


__all__ = ["ChallengeResult", "VALID_CHALLENGE_VERDICTS"]
