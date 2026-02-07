"""
Run progress tracking models.

Defines models for tracking the lifecycle state and progress
of individual agent runs during execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
	"""
	Lifecycle states for a run.

	PENDING: Run not yet started.
	RUNNING: Run currently executing.
	COMPLETED: Run finished successfully.
	FAILED: Run terminated with an error.
	"""

	PENDING = "pending"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"


class AgentRunProgress(BaseModel):
	"""Progress tracker for a single agent run."""

	run_id: str
	status: RunStatus = RunStatus.PENDING
	last_event: Optional[str] = None
	messages: List[str] = Field(default_factory=list)
	started_at: datetime = Field(
	    default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = Field(
	    default_factory=lambda: datetime.now(timezone.utc))

	def log(self, msg: str) -> None:
		self.messages.append(msg)
		self.updated_at = datetime.now(timezone.utc)
		self.last_event = msg


__all__ = ["RunStatus", "AgentRunProgress"]
