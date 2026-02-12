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
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.loaders.templates import load_report_template
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
    fetch_last_assistant_message,
)
from secret_validator_grunt.integrations.copilot_tools import get_session_tools
from secret_validator_grunt.core.skills import (
    discover_skill_directories,
    discover_hidden_skills,
    DEFAULT_SKILLS_DIRECTORY,
)
from secret_validator_grunt.utils.logging import get_logger

logger = get_logger(__name__)


def resolve_run_params(
    run_params: RunParams | None,
    org_repo: str | None,
    alert_id: str | None,
) -> RunParams:
	"""Resolve RunParams from explicit params or org_repo/alert_id fallback.

	Parameters:
		run_params: Pre-built run params, or None.
		org_repo: Fallback org/repo string.
		alert_id: Fallback alert ID string.

	Returns:
		Validated RunParams instance.

	Raises:
		ValueError: If run_params is None and org_repo/alert_id are missing.
	"""
	if run_params is not None:
		return run_params
	if not org_repo or not alert_id:
		raise ValueError("org_repo and alert_id are required")
	return RunParams(org_repo=org_repo, alert_id=alert_id)


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


def discover_all_disabled_skills(config: Config) -> list[str]:
	"""Discover hidden skills and merge with config-disabled skills.

	Parameters:
		config: Application configuration.

	Returns:
		Deduplicated list of skill names to disable.
	"""
	hidden = discover_hidden_skills(DEFAULT_SKILLS_DIRECTORY)
	return list(set(hidden + (config.disabled_skills or [])))


async def send_and_collect(
    session: object,
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
		while attempts < max_continuations and _is_empty(
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

		if _is_empty(raw, min_response_length):
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


def _is_empty(raw: str | None, min_length: int) -> bool:
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
    session: object,
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


async def destroy_session_safe(session: object | None, label: str) -> None:
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
    "resolve_run_params",
    "load_and_validate_template",
    "discover_all_disabled_skills",
    "send_and_collect",
    "destroy_session_safe",
    "_is_empty",
]
