"""
Analysis runner for Copilot validation sessions.

Executes single analysis sessions with streaming support, progress
callbacks, and structured report parsing.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional

from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.run_progress import (
    AgentRunProgress,
    RunStatus,
)
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.report import Report
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
    fetch_last_assistant_message,
)
from secret_validator_grunt.integrations.custom_agents import to_custom_agent
from secret_validator_grunt.utils.paths import ensure_within
from secret_validator_grunt.loaders.prompts import load_prompt
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.protocols import CopilotClientProtocol
from secret_validator_grunt.core.skills import (
    discover_skill_directories,
    discover_hidden_skills,
    build_skill_manifest,
    format_manifest_for_context,
    DEFAULT_SKILLS_DIRECTORY,
)

logger = get_logger(__name__)


def _build_analysis_prompt(
        base_prompt: str, context_block: str, report_template: Optional[str],
        skill_manifest_context: Optional[str] = None) -> str:
	"""Compose the full prompt for analysis with optional template and skill manifest."""
	parts = [base_prompt, context_block]

	if skill_manifest_context:
		parts.append(skill_manifest_context)

	if report_template:
		parts.append(
		    f"Report template you must use:\n```markdown\n{report_template}\n```"
		)

	return "\n\n".join(parts)


async def run_analysis(
    run_id: str,
    client: CopilotClientProtocol,
    config: Config,
    agent: AgentConfig,
    run_params: Optional[RunParams] = None,
    org_repo: Optional[str] = None,
    alert_id: Optional[str] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> AgentRunResult:
	"""
	Run a single analysis session.

	- Streams deltas to a log file and optional progress callback.
	- Parses the report markdown into a structured Report model.
	"""
	progress = AgentRunProgress(run_id=str(run_id), status=RunStatus.RUNNING)
	workspace: Optional[Path] = None
	session = None
	logger.info("analysis %s start org_repo=%s alert_id=%s", run_id, org_repo,
	            alert_id)
	progress.log("analysis_started")
	if progress_cb:
		progress_cb(run_id, "analysis_started")

	try:
		prompt_template = load_prompt("analysis_task.md")
		rp = run_params
		if rp is None:
			if not org_repo or not alert_id:
				raise ValueError("org_repo and alert_id are required")
			rp = RunParams(org_repo=org_repo, alert_id=alert_id)

		run_uuid = uuid.uuid4().hex
		workspace = ensure_within(
		    config.output_path,
		    config.output_path / rp.org_repo_slug / rp.alert_id_slug /
		    run_uuid,
		)
		workspace.mkdir(parents=True, exist_ok=True)
		stream_log_path = workspace / "stream.log"
		if progress_cb:
			progress_cb(run_id, f"workspace: {workspace}")
		context_block = (
		    f"## Context\n\n- Repository: {rp.org_repo}\n- Alert ID: {rp.alert_id}\n"
		    f"- Workspace: {workspace} !!! DO EVERYTHING HERE, ALWAYS !!!\n")

		from secret_validator_grunt.loaders.templates import load_report_template

		report_template = load_report_template(config.report_template_file)
		if not report_template:
			raise RuntimeError(
			    f"Report template not found at {config.report_template_file}")

		# Build skill directories from phase-based structure + config overrides
		skill_dirs = discover_skill_directories(config.skill_directories or [])
		skill_manifest = build_skill_manifest(skill_dirs)
		skill_manifest_context = format_manifest_for_context(skill_manifest)

		# Discover hidden skills (underscore-prefixed) to disable at runtime
		hidden_skills = discover_hidden_skills(DEFAULT_SKILLS_DIRECTORY)
		disabled_skills = list(set(hidden_skills + (config.disabled_skills or [])))

		prompt = _build_analysis_prompt(prompt_template, context_block,
		                                report_template,
		                                skill_manifest_context)
		agent_prompt = f"@{agent.name}\n{prompt}"
		collector = StreamCollector(
		    run_id=run_id,
		    stream_log_path=stream_log_path,
		    stream_verbose=config.stream_verbose,
		    progress_cb=progress_cb,
		    show_usage=config.show_usage,
		    skill_manifest=skill_manifest,
		    disabled_skills=disabled_skills,
		)

		from secret_validator_grunt.integrations.copilot_tools import get_session_tools
		session_tools = get_session_tools(config, org_repo, alert_id)
		chosen_model = agent.model or config.model
		session = await client.create_session(
		    {
		        "model": chosen_model,
		        "streaming": True,
		        "custom_agents": [to_custom_agent(agent)],
		        "tools": session_tools,
		        "available_tools": agent.tools or None,
		        "skill_directories": [
		            str(workspace.resolve()),
		            *skill_dirs,
		        ],
		        "disabled_skills": disabled_skills or None,
		        "session_id": f"{rp.session_id_prefix}-{run_id}-{run_uuid}",
		    }, )
		session.on(collector.handler)

		raw: Optional[str] = None
		try:
			response = await session.send_and_wait(
			    {"prompt": agent_prompt},
			    timeout=config.analysis_timeout_seconds)
			if response and getattr(response, "data", None):
				raw = response.data.content
		except asyncio.TimeoutError as te:
			progress.log(f"timeout_waiting_for_idle: {te}")
			if progress_cb:
				progress_cb(run_id, f"timeout_waiting_for_idle: {te}")
			try:
				await session.abort()
			except Exception:
				pass
		except Exception as exc:  # let outer handler log
			raise exc

		if not raw:
			raw = collector.text or (
			    await fetch_last_assistant_message(session) or "")

		progress.log("analysis_completed")
		if progress_cb:
			progress_cb(run_id, "analysis_completed")
		report = Report.from_markdown(raw or "")
		progress.status = RunStatus.COMPLETED

		# Finalize skill usage tracking
		skill_usage = collector.finalize_skill_usage()

		# Persist diagnostics JSON when --show-usage is active
		if config.show_usage and workspace:
			diagnostics = {
			    "run_id": str(run_id),
			    "skill_usage": skill_usage.model_dump(),
			    "tool_usage": (
			        collector.tool_usage.model_dump()
			        if collector.tool_usage
			        else None
			    ),
			    "usage": collector.usage.model_dump(),
			}
			try:
				diag_path = workspace / "diagnostics.json"
				diag_path.write_text(
				    json.dumps(diagnostics, indent=2),
				)
			except Exception:
				logger.debug(
				    "failed to write diagnostics.json for run %s",
				    run_id,
				)

		return AgentRunResult(
		    run_id=str(run_id),
		    workspace=str(workspace),
		    report=report,
		    raw_markdown=raw,
		    progress_log=progress.messages,
		    usage=collector.usage,
		    skill_usage=skill_usage,
		    tool_usage=collector.tool_usage,
		)
	except Exception as exc:
		logger.exception("analysis %s failed", run_id)
		progress.log(f"error: {exc}")
		if progress_cb:
			progress_cb(run_id, f"error: {exc}")
		progress.status = RunStatus.FAILED
		return AgentRunResult(
		    run_id=str(run_id),
		    workspace=str(workspace) if workspace else None,
		    error=str(exc),
		    progress_log=progress.messages,
		)
	finally:
		try:
			if session:
				await session.destroy()
		except Exception:
			pass


__all__ = ["run_analysis"]
