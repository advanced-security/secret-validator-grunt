"""
Streaming helpers for Copilot sessions.

Provides a `StreamCollector` that handles session events, writes streaming
content to disk, emits progress callbacks, and accumulates message deltas
for final content assembly. Use for both analysis and judge sessions to
avoid duplicated event handling logic.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

from copilot.generated.session_events import SessionEventType

from secret_validator_grunt.models.skill import SkillManifest
from secret_validator_grunt.models.skill_usage import (
    SkillLoadStatus,
    SkillUsageStats,
)
from secret_validator_grunt.models.tool_usage import ToolUsageStats

ProgressCallback = Callable[[str, str], None]


class StreamCollector:
	"""Collect streaming events, write to log, and emit progress updates."""

	def __init__(
	    self,
	    run_id: str,
	    stream_log_path: Path,
	    stream_verbose: bool = False,
	    progress_cb: Optional[ProgressCallback] = None,
	    show_usage: bool = False,
	    skill_manifest: Optional[SkillManifest] = None,
	    disabled_skills: Optional[List[str]] = None,
	) -> None:
		"""
		Initialize the stream collector.

		Parameters:
			run_id: Identifier for this run.
			stream_log_path: Path to write streaming content.
			stream_verbose: Whether to emit verbose delta callbacks.
			progress_cb: Callback for progress updates.
			show_usage: Whether to track usage statistics.
			skill_manifest: Manifest of available skills for tracking.
			disabled_skills: List of disabled skill names.
		"""
		self.run_id = run_id
		self.stream_log_path = stream_log_path
		self.stream_verbose = stream_verbose
		self.progress_cb = progress_cb
		self.chunks: List[str] = []
		self.show_usage = show_usage
		from secret_validator_grunt.models import UsageStats

		self.usage = UsageStats()

		# Skill tracking state
		self._skill_manifest = skill_manifest
		self._disabled_skills = set(disabled_skills or [])
		# Track pending skill tool calls by toolCallId -> {skill_name, start_time}
		self._pending_skill_calls: Dict[str, Dict[str, Any]] = {}
		self._skill_usage = self._init_skill_usage()

		# Tool usage tracking (all tools, not just skills)
		self._tool_usage: Optional[ToolUsageStats] = (
		    ToolUsageStats() if show_usage else None
		)

	def _init_skill_usage(self) -> SkillUsageStats:
		"""
		Initialize skill usage stats from manifest.

		Returns:
			SkillUsageStats populated with available/required/disabled skills.
		"""
		if not self._skill_manifest:
			return SkillUsageStats(
			    disabled_skills=list(self._disabled_skills),
			)

		available = [s.name for s in self._skill_manifest.skills]
		required = [
		    s.name for s in self._skill_manifest.skills if s.required
		]
		phase_map = {
		    s.name: s.phase
		    for s in self._skill_manifest.skills
		    if s.phase
		}
		return SkillUsageStats(
		    available_skills=available,
		    required_skills=required,
		    disabled_skills=list(self._disabled_skills),
		    phase_map=phase_map,
		)

	@property
	def skill_usage(self) -> SkillUsageStats:
		"""Return the skill usage statistics."""
		return self._skill_usage

	def finalize_skill_usage(self) -> SkillUsageStats:
		"""
		Finalize and return skill usage stats.

		Computes derived fields like skipped_required.

		Returns:
			Finalized SkillUsageStats.
		"""
		self._skill_usage.finalize()
		return self._skill_usage

	@property
	def tool_usage(self) -> Optional[ToolUsageStats]:
		"""Return the tool usage statistics, or None if not tracking."""
		return self._tool_usage

	def _handle_skill_event(self, event_type: SessionEventType,
	                        data: Any) -> None:
		"""
		Handle a skill tool execution event.

		Parameters:
			event_type: The type of tool event.
			data: The event data containing tool arguments and results.
		"""
		tool_call_id = getattr(data, "tool_call_id", None)
		if not tool_call_id:
			return

		if event_type == SessionEventType.TOOL_EXECUTION_START:
			# Extract skill name from arguments (only available on START)
			arguments = getattr(data, "arguments", None) or {}
			if isinstance(arguments, str):
				try:
					import json
					arguments = json.loads(arguments)
				except (json.JSONDecodeError, TypeError):
					arguments = {}

			skill_name = arguments.get("skill", "") if isinstance(
			    arguments, dict) else ""
			if not skill_name:
				return

			# Store pending call info for lookup on COMPLETE
			self._pending_skill_calls[tool_call_id] = {
			    "skill_name": skill_name,
			    "start_time": time.time(),
			}

		elif event_type == SessionEventType.TOOL_EXECUTION_COMPLETE:
			# Look up the pending call by toolCallId
			pending = self._pending_skill_calls.pop(tool_call_id, None)
			if not pending:
				return

			skill_name = pending["skill_name"]
			start_time = pending.get("start_time")

			# Calculate duration
			duration_ms = None
			if start_time:
				duration_ms = (time.time() - start_time) * 1000

			# Determine status from result
			success = getattr(data, "success", True)
			error_msg = getattr(data, "error", None)

			# Look up skill info from manifest
			phase = None
			is_required = False
			if self._skill_manifest:
				for skill_info in self._skill_manifest.skills:
					if skill_info.name == skill_name:
						phase = skill_info.phase
						is_required = skill_info.required
						break

			# Determine status
			if skill_name in self._disabled_skills:
				status = SkillLoadStatus.DISABLED
			elif success:
				status = SkillLoadStatus.LOADED
			elif error_msg and "not found" in str(error_msg).lower():
				status = SkillLoadStatus.NOT_FOUND
			else:
				status = SkillLoadStatus.FAILED

			# Record the event
			self._skill_usage.add_load_event(
			    skill_name,
			    status,
			    phase=phase,
			    is_required=is_required,
			    error_message=str(error_msg) if error_msg else None,
			    duration_ms=duration_ms,
			)

	def _write_stream(self, msg: str) -> None:
		"""Write message to the stream log file."""
		try:
			self.stream_log_path.parent.mkdir(parents=True, exist_ok=True)
			with self.stream_log_path.open("a", encoding="utf-8") as fp:
				fp.write(msg)
		except Exception:
			# avoid crashing on log write errors
			pass

	def handler(self, event: Any) -> None:
		"""Handle a session event."""
		et = getattr(event, "type", None)
		data = getattr(event, "data", None)
		if et == SessionEventType.ASSISTANT_MESSAGE_DELTA:
			delta = (getattr(data, "delta_content", "") or "")
			self.chunks.append(delta)
			self._write_stream(delta)
			if self.stream_verbose and self.progress_cb:
				snippet = delta.replace("\n", " ")[:200]
				if snippet:
					self.progress_cb(self.run_id, f"delta: {snippet}")
		elif et == SessionEventType.ASSISTANT_MESSAGE:
			content = (getattr(data, "content", "") or "")
			self._write_stream(content)
			if self.progress_cb:
				# Clean up and truncate for display
				snippet = content.replace("\n", " ").strip()
				# Skip if it looks like a raw markdown report
				if snippet.startswith("# ") or snippet.startswith("| "):
					return
				# Truncate long messages
				if len(snippet) > 200:
					snippet = snippet[:200] + "..."
				if snippet:
					self.progress_cb(self.run_id, f"assistant: {snippet}")
		elif et == SessionEventType.ASSISTANT_USAGE:
			self.usage.merge_turn(
			    input_tokens=getattr(data, "input_tokens", 0) or 0,
			    output_tokens=getattr(data, "output_tokens", 0) or 0,
			    cache_read_tokens=getattr(data, "cache_read_tokens", 0) or 0,
			    cache_write_tokens=getattr(data, "cache_write_tokens", 0) or 0,
			    cost=getattr(data, "cost", 0) or 0,
			    # SDK reports duration in milliseconds, convert to seconds
			    duration=(getattr(data, "duration", 0) or 0) / 1000.0,
			)
		elif et == SessionEventType.SESSION_USAGE_INFO:
			self.usage.update_snapshot(
			    current_tokens=getattr(data, "current_tokens", None),
			    token_limit=getattr(data, "token_limit", None),
			    quota_snapshots=getattr(data, "quota_snapshots", None),
			)
			# Also merge tokens if provided on usage_info
			self.usage.merge_turn(
			    input_tokens=getattr(data, "input_tokens", 0) or 0,
			    output_tokens=getattr(data, "output_tokens", 0) or 0,
			    cache_read_tokens=getattr(data, "cache_read_tokens", 0) or 0,
			    cache_write_tokens=getattr(data, "cache_write_tokens", 0) or 0,
			    cost=getattr(data, "cost", 0) or 0,
			    # SDK reports duration in milliseconds, convert to seconds
			    duration=(getattr(data, "duration", 0) or 0) / 1000.0,
			)
		elif et in (
		    SessionEventType.TOOL_EXECUTION_START,
		    SessionEventType.TOOL_EXECUTION_PROGRESS,
		    SessionEventType.TOOL_EXECUTION_PARTIAL_RESULT,
		    SessionEventType.TOOL_EXECUTION_COMPLETE,
		    SessionEventType.TOOL_USER_REQUESTED,
		):
			tool_name = getattr(data, "tool_name", None) or getattr(
			    data, "name", "")
			tool_call_id = getattr(data, "tool_call_id", None)

			# Track all tool calls when usage tracking is active
			if self._tool_usage and tool_call_id:
				if et == SessionEventType.TOOL_EXECUTION_START:
					self._tool_usage.add_start(
					    tool_call_id, tool_name,
					)
				elif et == SessionEventType.TOOL_EXECUTION_COMPLETE:
					success = getattr(data, "success", True)
					error = getattr(data, "error", None)
					self._tool_usage.add_complete(
					    tool_call_id,
					    success=success,
					    error=str(error) if error else None,
					)

			# Track skill tool events
			if tool_name == "skill" or (
			    et == SessionEventType.TOOL_EXECUTION_COMPLETE and
			    tool_call_id in self._pending_skill_calls
			):
				self._handle_skill_event(et, data)
			if self.stream_verbose and self.progress_cb:
				self.progress_cb(self.run_id, f"{et.value}: {tool_name}")
		elif et == SessionEventType.SESSION_ERROR:
			msg = getattr(data, "message", None) or str(data)
			if self.progress_cb:
				self.progress_cb(self.run_id, f"session_error: {msg}")

	@property
	def text(self) -> str:
		"""Concatenate collected deltas into a single string."""
		return "".join(self.chunks)


async def fetch_last_assistant_message(session: Any) -> Optional[str]:
	"""
	Fallback to retrieve the last assistant message from session messages.

	Parameters:
		session: The Copilot session object.

	Returns:
		Content of the last assistant message, or None.
	"""
	try:
		messages = await session.get_messages()
		for ev in reversed(messages):
			if getattr(ev, "type", None) == SessionEventType.ASSISTANT_MESSAGE:
				return getattr(getattr(ev, "data", None), "content", None)
	except Exception:
		return None
	return None


__all__ = [
    "StreamCollector",
    "ProgressCallback",
    "fetch_last_assistant_message",
]
