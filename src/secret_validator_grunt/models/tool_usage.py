"""
Tool usage tracking models.

Defines Pydantic models for tracking tool call events and
computing success rate metrics during agent sessions.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCallEvent(BaseModel):
	"""
	Record of a single tool call.

	Attributes:
		tool_call_id: Unique identifier for this call.
		tool_name: Name of the tool invoked.
		status: Outcome of the call (success or failure).
		started_at: ISO timestamp of when the call started.
		completed_at: ISO timestamp of when the call completed.
		duration_ms: Time taken in milliseconds.
		error_message: Error details if the call failed.
	"""

	tool_call_id: str = Field(description="Unique call identifier")
	tool_name: str = Field(description="Name of the tool invoked")
	status: str = Field(
	    default="success",
	    description="Outcome: 'success' or 'failure'",
	)
	started_at: Optional[str] = Field(
	    default=None,
	    description="ISO timestamp of call start",
	)
	completed_at: Optional[str] = Field(
	    default=None,
	    description="ISO timestamp of call completion",
	)
	duration_ms: Optional[float] = Field(
	    default=None,
	    description="Duration in milliseconds",
	)
	error_message: Optional[str] = Field(
	    default=None,
	    description="Error details if failed",
	)


class ToolCallSummary(BaseModel):
	"""
	Per-tool aggregated statistics.

	Attributes:
		tool_name: Name of the tool.
		total: Total number of calls.
		successful: Number of successful calls.
		failed: Number of failed calls.
	"""

	tool_name: str = Field(description="Tool name")
	total: int = Field(default=0, description="Total calls")
	successful: int = Field(default=0, description="Successful calls")
	failed: int = Field(default=0, description="Failed calls")


class ToolUsageStats(BaseModel):
	"""
	Aggregated tool usage statistics for a session.

	Tracks all tool calls made during an agent session, recording
	start/complete times, success/failure, and per-tool breakdowns.

	Attributes:
		tool_calls: List of completed tool call events.
	"""

	tool_calls: List[ToolCallEvent] = Field(
	    default_factory=list,
	    description="Completed tool call events",
	)

	# Internal pending calls (not serialized)
	_pending: Dict[str, Dict[str, Any]] = {}

	def model_post_init(self, __context: Any) -> None:
		"""Initialize internal pending calls dict."""
		self._pending = {}

	@property
	def total_calls(self) -> int:
		"""Return total number of completed tool calls."""
		return len(self.tool_calls)

	@property
	def successful_calls(self) -> int:
		"""Return number of successful tool calls."""
		return sum(
		    1 for c in self.tool_calls if c.status == "success"
		)

	@property
	def failed_calls(self) -> int:
		"""Return number of failed tool calls."""
		return sum(
		    1 for c in self.tool_calls if c.status == "failure"
		)

	@property
	def success_rate(self) -> float:
		"""
		Calculate success rate as a percentage.

		Returns:
			100.0 if no calls, otherwise percentage of
			successful calls.
		"""
		if not self.tool_calls:
			return 100.0
		return (self.successful_calls / len(self.tool_calls)) * 100

	def calls_by_tool(self) -> Dict[str, ToolCallSummary]:
		"""
		Aggregate call counts per tool name.

		Returns:
			Dict mapping tool names to ToolCallSummary objects.
		"""
		result: Dict[str, ToolCallSummary] = {}
		for call in self.tool_calls:
			if call.tool_name not in result:
				result[call.tool_name] = ToolCallSummary(
				    tool_name=call.tool_name,
				)
			summary = result[call.tool_name]
			summary.total += 1
			if call.status == "success":
				summary.successful += 1
			else:
				summary.failed += 1
		return result

	def top_tools(self, limit: int = 5) -> List[ToolCallSummary]:
		"""
		Return the most-called tools sorted by total calls.

		Parameters:
			limit: Maximum number of tools to return.

		Returns:
			List of ToolCallSummary sorted descending by total.
		"""
		by_tool = self.calls_by_tool()
		sorted_tools = sorted(
		    by_tool.values(),
		    key=lambda s: s.total,
		    reverse=True,
		)
		return sorted_tools[:limit]

	def add_start(
	    self,
	    tool_call_id: str,
	    tool_name: str,
	) -> None:
		"""
		Record the start of a tool call.

		Parameters:
			tool_call_id: Unique identifier for this call.
			tool_name: Name of the tool being invoked.
		"""
		self._pending[tool_call_id] = {
		    "tool_name": tool_name,
		    "start_time": time.time(),
		    "started_at": datetime.now(timezone.utc).isoformat(),
		}

	def add_complete(
	    self,
	    tool_call_id: str,
	    success: bool,
	    error: Optional[str] = None,
	) -> None:
		"""
		Record the completion of a tool call.

		Parameters:
			tool_call_id: Unique identifier matching a prior add_start.
			success: Whether the call succeeded.
			error: Error message if the call failed.
		"""
		pending = self._pending.pop(tool_call_id, None)
		if not pending:
			return

		start_time = pending.get("start_time")
		duration_ms = None
		if start_time:
			duration_ms = (time.time() - start_time) * 1000

		event = ToolCallEvent(
		    tool_call_id=tool_call_id,
		    tool_name=pending["tool_name"],
		    status="success" if success else "failure",
		    started_at=pending.get("started_at"),
		    completed_at=datetime.now(timezone.utc).isoformat(),
		    duration_ms=duration_ms,
		    error_message=str(error) if error else None,
		)
		self.tool_calls.append(event)


__all__ = [
    "ToolCallEvent",
    "ToolCallSummary",
    "ToolUsageStats",
]
