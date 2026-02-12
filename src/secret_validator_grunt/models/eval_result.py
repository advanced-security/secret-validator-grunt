"""
Eval result models.

Defines EvalCheck and EvalResult Pydantic models for
representing the outcome of evaluation checks on reports.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class EvalCheck(BaseModel):
	"""Result of a single evaluation check on a report."""

	name: str = Field(description="Check function name")
	passed: bool = Field(description="Whether the check passed")
	message: str | None = Field(
	    default=None,
	    description="Human-readable explanation of the result",
	)
	severity: Literal["error", "warning", "info"] = Field(
	    default="error",
	    description="Severity level: error, warning, or info",
	)


class EvalResult(BaseModel):
	"""Aggregate result of all eval checks on a report."""

	report_id: str = Field(
	    description="Identifier for the report being evaluated", )
	checks: list[EvalCheck] = Field(
	    default_factory=list,
	    description="Individual check results",
	)

	@property
	def passed(self) -> bool:
		"""Return True if all error-severity checks passed."""
		return all(c.passed for c in self.checks if c.severity == "error")

	@property
	def score(self) -> float:
		"""Return fraction of checks that passed (0.0–1.0)."""
		total = len(self.checks)
		if total == 0:
			return 0.0
		passed_count = sum(1 for c in self.checks if c.passed)
		return passed_count / total


__all__ = ["EvalCheck", "EvalResult"]
