"""
Judge result models.

Defines models for judge scoring and selection of the best report.
"""

from __future__ import annotations

from pydantic import BaseModel
from .usage import UsageStats


class JudgeScore(BaseModel):
	"""
	Score for a single report from the judge.

	Contains the report index, numeric score, methodology compliance,
	and optional rationale.
	"""

	report_index: int
	score: float
	methodology_compliance: float | None = None
	rationale: str | None = None


class JudgeResult(BaseModel):
	"""Judge outcome with winner index and optional rationale/verdict."""

	winner_index: int
	scores: list[JudgeScore]
	rationale: str | None = None
	verdict: str | None = None
	raw_response: str | None = None
	usage: UsageStats | None = None
	workspace: str | None = None


__all__ = ["JudgeResult", "JudgeScore"]
