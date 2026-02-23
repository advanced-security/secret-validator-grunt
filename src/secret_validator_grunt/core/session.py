"""
Shared session utilities for analysis and judge runners.

Provides common helpers to eliminate duplication between run_analysis()
and run_judge(), including parameter resolution, skill discovery,
template loading, and session lifecycle management.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.loaders.templates import load_report_template
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
    fetch_last_assistant_message,
)
from secret_validator_grunt.integrations.custom_agents import to_custom_agent
from secret_validator_grunt.core.skills import (
    discover_hidden_skills,
    DEFAULT_SKILLS_DIRECTORY,
)
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.protocols import SessionProtocol

logger = get_logger(__name__)


def build_session_config(
    *,
    model: str,
    streaming: bool,
    agent: AgentConfig,
    tools: list,
    skill_directories: list[str],
    disabled_skills: list[str] | None = None,
    system_message: str | None = None,
    session_id: str | None = None,
) -> dict:
	"""Build a session configuration dict for create_session().

	Centralizes the common session config structure used by
	analysis, judge, and challenger stages.

	Parameters:
		model: Model identifier string.
		streaming: Whether to enable streaming.
		agent: Agent configuration.
		tools: Tool definitions for the session.
		skill_directories: Skill directory paths.
		disabled_skills: Skills to disable, or None.
		system_message: Optional system message text.
		session_id: Optional session identifier.

	Returns:
		Session configuration dictionary.
	"""
	config: dict = {
	    "model": model,
	    "streaming": streaming,
	    "custom_agents": [to_custom_agent(agent)],
	    "tools": tools,
	    "available_tools": agent.tools or None,
	    "skill_directories": skill_directories,
	    "disabled_skills": disabled_skills or None,
	}
	if system_message is not None:
		config["system_message"] = {"text": system_message}
	if session_id is not None:
		config["session_id"] = session_id
	return config


def load_and_validate_template(template_path: str) -> str:
	"""Load and validate a report template file.

	Parameters:
		template_path: Path to the report template.

	Returns:
		Template content string.

	Raises:
		RuntimeError: If template file is not found.
	"""
	template = load_report_template(template_path)
	if not template:
		raise RuntimeError(f"Report template not found at {template_path}")
	return template


def discover_all_disabled_skills(
    config: Config,
    skills_directory: Path | None = None,
) -> list[str]:
	"""Discover hidden skills and merge with config-disabled.

	Parameters:
		config: Application configuration.
		skills_directory: Root directory for skill discovery.
			Defaults to DEFAULT_SKILLS_DIRECTORY.

	Returns:
		Deduplicated list of skill names to disable.
	"""
	base = skills_directory or DEFAULT_SKILLS_DIRECTORY
	hidden = discover_hidden_skills(base)
	return list(set(hidden + (config.disabled_skills or [])))


async def send_and_collect(
    session: SessionProtocol,
    prompt: str,
    timeout: int,
    collector: StreamCollector,
    run_id: str,
    progress_cb: ProgressCallback | None = None,
    *,
    reraise: bool = True,
    continuation_prompt: str | None = None,
    max_continuations: int = 0,
    min_response_length: int = 500,
) -> str | None:
	"""Send a prompt and collect the response.

	When continuation_prompt is set, checks whether the
	response is shorter than min_response_length chars.
	If so, sends the continuation prompt in the same
	session (retaining all prior context) up to
	max_continuations times. This mitigates the
	non-deterministic early-termination pattern where
	the model emits an empty assistant.message with no
	tool requests, causing session.idle.

	Parameters:
		session: Active Copilot session.
		prompt: Full prompt to send.
		timeout: Timeout in seconds.
		collector: Stream collector for events.
		run_id: Run identifier for progress callbacks.
		progress_cb: Optional progress callback.
		reraise: If True, re-raise non-timeout errors.
			If False, append error to raw text.
		continuation_prompt: Prompt to send on early
			termination. None disables continuation.
		max_continuations: Max continuation attempts.
		min_response_length: Minimum char count for a
			valid response.

	Returns:
		Raw response text, or empty string on failure.
	"""
	raw = await _send_once(
	    session,
	    prompt,
	    timeout,
	    collector,
	    run_id,
	    progress_cb,
	    reraise=reraise,
	)

	# --- continuation loop ---
	if continuation_prompt and max_continuations > 0:
		attempts = 0
		while attempts < max_continuations and is_response_empty(
		    raw,
		    min_response_length,
		):
			attempts += 1
			msg = (f"empty_response_continuation "
			       f"attempt={attempts}/{max_continuations}")
			logger.warning(
			    "analysis %s: %s (len=%d, min=%d)",
			    run_id,
			    msg,
			    len(raw or ""),
			    min_response_length,
			)
			if progress_cb:
				progress_cb(run_id, msg)

			raw = await _send_once(
			    session,
			    continuation_prompt,
			    timeout,
			    collector,
			    run_id,
			    progress_cb,
			    reraise=reraise,
			)

		if is_response_empty(raw, min_response_length):
			logger.error(
			    "analysis %s: still empty after %d continuations",
			    run_id,
			    attempts,
			)
			if progress_cb:
				progress_cb(
				    run_id,
				    f"empty_after_{attempts}_continuations",
				)

	return raw


def is_response_empty(raw: str | None, min_length: int) -> bool:
	"""Return True when the response is too short.

	Parameters:
		raw: Response text.
		min_length: Minimum acceptable length.

	Returns:
		True if raw is None, empty, or shorter than
		min_length after stripping whitespace.
	"""
	return not raw or len(raw.strip()) < min_length


async def _send_once(
    session: SessionProtocol,
    prompt: str,
    timeout: int,
    collector: StreamCollector,
    run_id: str,
    progress_cb: ProgressCallback | None = None,
    *,
    reraise: bool = True,
) -> str | None:
	"""Send a single prompt and return the raw response.

	Core send logic extracted from send_and_collect so
	it can be called in a loop for continuations.

	Parameters:
		session: Active Copilot session.
		prompt: Prompt to send.
		timeout: Timeout in seconds.
		collector: Stream collector for events.
		run_id: Run identifier for progress callbacks.
		progress_cb: Optional progress callback.
		reraise: If True, re-raise non-timeout errors.

	Returns:
		Raw response text, or empty string on failure.
	"""
	raw: str | None = None
	try:
		response = await session.send_and_wait({"prompt": prompt},
		                                       timeout=timeout)
		if response and getattr(response, "data", None):
			raw = response.data.content
	except asyncio.TimeoutError as te:
		if progress_cb:
			progress_cb(run_id, f"timeout_waiting_for_idle: {te}")
		try:
			await session.abort()
		except Exception:
			logger.debug("failed to abort session %s", run_id, exc_info=True)
	except Exception as exc:
		if reraise:
			raise
		if progress_cb:
			progress_cb(run_id, f"session_error: {exc}")
		raw = (raw or "") + (f"\nERROR: {exc}" if raw else f"ERROR: {exc}")

	if not raw:
		raw = collector.text or (await fetch_last_assistant_message(session)
		                         or "")

	return raw


async def destroy_session_safe(
    session: SessionProtocol | None,
    label: str,
) -> None:
	"""Destroy a session, logging but not raising on failure.

	Parameters:
		session: Session to destroy, or None.
		label: Label for log messages (e.g., "analysis 0", "judge").
	"""
	if not session:
		return
	try:
		await session.destroy()
	except Exception:
		logger.debug("failed to destroy %s session", label, exc_info=True)


__all__ = [
    "build_session_config",
    "load_and_validate_template",
    "discover_all_disabled_skills",
    "send_and_collect",
    "destroy_session_safe",
    "is_response_empty",
]
