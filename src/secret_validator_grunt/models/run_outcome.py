"""
Run outcome model.

Defines the aggregate outcome containing analysis results plus judge result.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .run_result import AgentRunResult
from .judge_result import JudgeResult
from .challenge_result import ChallengeResult


class RunOutcome(BaseModel):
	"""
	Aggregate outcome of a validation run.

	Combines the list of analysis results from parallel runs
	with the judge's final selection.
	"""

	judge_result: JudgeResult
	analysis_results: list[AgentRunResult]
	challenge_results: list[ChallengeResult] = Field(
	    default_factory=list,
	    description="Adversarial challenge results, one per analysis.",
	)


__all__ = ["RunOutcome"]
