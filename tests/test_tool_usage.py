"""Tests for tool usage tracking models."""

import time

import pytest

from secret_validator_grunt.models.tool_usage import (
    ToolCallEvent,
    ToolCallSummary,
    ToolUsageStats,
)


class TestToolCallEvent:
	"""Tests for ToolCallEvent model."""

	def test_create_with_defaults(self) -> None:
		"""ToolCallEvent creates with minimal required fields."""
		event = ToolCallEvent(
		    tool_call_id="call-001",
		    tool_name="bash",
		)
		assert event.tool_call_id == "call-001"
		assert event.tool_name == "bash"
		assert event.status == "success"
		assert event.started_at is None
		assert event.completed_at is None
		assert event.duration_ms is None
		assert event.error_message is None

	def test_create_failed_event(self) -> None:
		"""ToolCallEvent stores error message for failures."""
		event = ToolCallEvent(
		    tool_call_id="call-002",
		    tool_name="view",
		    status="failure",
		    error_message="File not found",
		)
		assert event.status == "failure"
		assert event.error_message == "File not found"

	def test_create_with_all_fields(self) -> None:
		"""ToolCallEvent accepts all optional fields."""
		event = ToolCallEvent(
		    tool_call_id="call-003",
		    tool_name="bash",
		    status="success",
		    started_at="2026-02-06T10:00:00Z",
		    completed_at="2026-02-06T10:00:01Z",
		    duration_ms=1000.0,
		    error_message=None,
		)
		assert event.duration_ms == 1000.0
		assert event.started_at == "2026-02-06T10:00:00Z"


class TestToolCallSummary:
	"""Tests for ToolCallSummary model."""

	def test_create_with_defaults(self) -> None:
		"""ToolCallSummary creates with zero counters."""
		summary = ToolCallSummary(tool_name="bash")
		assert summary.tool_name == "bash"
		assert summary.total == 0
		assert summary.successful == 0
		assert summary.failed == 0


class TestToolUsageStats:
	"""Tests for ToolUsageStats model."""

	def test_create_empty(self) -> None:
		"""ToolUsageStats creates with empty tool_calls."""
		stats = ToolUsageStats()
		assert stats.tool_calls == []
		assert stats.total_calls == 0
		assert stats.successful_calls == 0
		assert stats.failed_calls == 0
		assert stats.success_rate == 100.0

	def test_add_start_and_complete_success(self) -> None:
		"""Adding start+complete records a successful ToolCallEvent."""
		stats = ToolUsageStats()
		stats.add_start("call-001", "bash")
		stats.add_complete("call-001", success=True)

		assert stats.total_calls == 1
		assert stats.successful_calls == 1
		assert stats.failed_calls == 0
		assert stats.success_rate == 100.0
		assert stats.tool_calls[0].tool_name == "bash"
		assert stats.tool_calls[0].status == "success"

	def test_add_start_and_complete_failure(self) -> None:
		"""Adding start+complete with failure records a failed event."""
		stats = ToolUsageStats()
		stats.add_start("call-001", "view")
		stats.add_complete("call-001", success=False, error="Timeout")

		assert stats.total_calls == 1
		assert stats.successful_calls == 0
		assert stats.failed_calls == 1
		assert stats.success_rate == 0.0
		assert stats.tool_calls[0].status == "failure"
		assert stats.tool_calls[0].error_message == "Timeout"

	def test_add_complete_without_start_is_ignored(self) -> None:
		"""Completing an unknown tool_call_id is silently ignored."""
		stats = ToolUsageStats()
		stats.add_complete("unknown-id", success=True)
		assert stats.total_calls == 0

	def test_success_rate_mixed(self) -> None:
		"""Success rate computes correctly with mixed results."""
		stats = ToolUsageStats()
		for i in range(3):
			stats.add_start(f"ok-{i}", "bash")
			stats.add_complete(f"ok-{i}", success=True)
		stats.add_start("fail-0", "view")
		stats.add_complete("fail-0", success=False, error="err")

		assert stats.total_calls == 4
		assert stats.successful_calls == 3
		assert stats.failed_calls == 1
		assert stats.success_rate == 75.0

	def test_calls_by_tool(self) -> None:
		"""calls_by_tool groups counts by tool name."""
		stats = ToolUsageStats()
		for i in range(3):
			stats.add_start(f"bash-{i}", "bash")
			stats.add_complete(f"bash-{i}", success=True)
		stats.add_start("view-0", "view")
		stats.add_complete("view-0", success=True)
		stats.add_start("view-1", "view")
		stats.add_complete("view-1", success=False, error="err")

		by_tool = stats.calls_by_tool()
		assert "bash" in by_tool
		assert by_tool["bash"].total == 3
		assert by_tool["bash"].successful == 3
		assert by_tool["bash"].failed == 0
		assert "view" in by_tool
		assert by_tool["view"].total == 2
		assert by_tool["view"].successful == 1
		assert by_tool["view"].failed == 1

	def test_top_tools(self) -> None:
		"""top_tools returns most-called tools in descending order."""
		stats = ToolUsageStats()
		# bash: 5 calls, skill: 3 calls, view: 1 call
		for i in range(5):
			stats.add_start(f"bash-{i}", "bash")
			stats.add_complete(f"bash-{i}", success=True)
		for i in range(3):
			stats.add_start(f"skill-{i}", "skill")
			stats.add_complete(f"skill-{i}", success=True)
		stats.add_start("view-0", "view")
		stats.add_complete("view-0", success=True)

		top = stats.top_tools(limit=2)
		assert len(top) == 2
		assert top[0].tool_name == "bash"
		assert top[0].total == 5
		assert top[1].tool_name == "skill"
		assert top[1].total == 3

	def test_top_tools_default_limit(self) -> None:
		"""top_tools default limit is 5."""
		stats = ToolUsageStats()
		for i in range(7):
			name = f"tool-{i}"
			stats.add_start(f"call-{i}", name)
			stats.add_complete(f"call-{i}", success=True)

		top = stats.top_tools()
		assert len(top) == 5

	def test_duration_tracked(self) -> None:
		"""Duration is computed between start and complete."""
		stats = ToolUsageStats()
		stats.add_start("call-001", "bash")
		time.sleep(0.01)
		stats.add_complete("call-001", success=True)

		assert stats.tool_calls[0].duration_ms is not None
		assert stats.tool_calls[0].duration_ms >= 10

	def test_timestamps_recorded(self) -> None:
		"""Started and completed timestamps are ISO strings."""
		stats = ToolUsageStats()
		stats.add_start("call-001", "bash")
		stats.add_complete("call-001", success=True)

		event = stats.tool_calls[0]
		assert event.started_at is not None
		assert event.completed_at is not None
		assert "T" in event.started_at
		assert "T" in event.completed_at

	def test_model_dump_serializable(self) -> None:
		"""ToolUsageStats can be serialized via model_dump."""
		stats = ToolUsageStats()
		stats.add_start("call-001", "bash")
		stats.add_complete("call-001", success=True)

		dump = stats.model_dump()
		assert "tool_calls" in dump
		assert len(dump["tool_calls"]) == 1
		assert dump["tool_calls"][0]["tool_name"] == "bash"

	def test_multiple_tools_interleaved(self) -> None:
		"""Interleaved start/complete across tools are tracked."""
		stats = ToolUsageStats()
		stats.add_start("a", "bash")
		stats.add_start("b", "view")
		stats.add_complete("b", success=True)
		stats.add_complete("a", success=True)

		assert stats.total_calls == 2
		# b completed first
		assert stats.tool_calls[0].tool_name == "view"
		assert stats.tool_calls[1].tool_name == "bash"
