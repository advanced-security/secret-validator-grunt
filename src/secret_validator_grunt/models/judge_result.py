"""
Judge result models.

Defines models for judge scoring and selection of the best report.
"""

from __future__ import annotations

from typing import List, Optional
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
	methodology_compliance: Optional[float] = None
	rationale: Optional[str] = None


class JudgeResult(BaseModel):
	"""Judge outcome with winner index and optional rationale/verdict."""

	winner_index: int
	scores: List[JudgeScore]
	rationale: Optional[str] = None
	verdict: Optional[str] = None
	raw_response: Optional[str] = None
	usage: Optional[UsageStats] = None
	workspace: Optional[str] = None


__all__ = ["JudgeResult", "JudgeScore"]
