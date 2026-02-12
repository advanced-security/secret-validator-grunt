"""
Analysis runner for Copilot validation sessions.

Executes single analysis sessions with streaming support, progress
callbacks, and structured report parsing.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

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
)
from secret_validator_grunt.integrations.custom_agents import to_custom_agent
from secret_validator_grunt.integrations.copilot_tools import get_session_tools
from secret_validator_grunt.loaders.templates import load_report_template
from secret_validator_grunt.utils.paths import ensure_within
from secret_validator_grunt.loaders.prompts import load_prompt
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.protocols import CopilotClientProtocol
from secret_validator_grunt.core.skills import (
    discover_skill_directories,
    build_skill_manifest,
    format_manifest_for_context,
)
from secret_validator_grunt.core.session import (
    resolve_run_params,
    load_and_validate_template,
    discover_all_disabled_skills,
    send_and_collect,
    destroy_session_safe,
)

logger = get_logger(__name__)


def _build_analysis_prompt(
        base_prompt: str, context_block: str, report_template: str | None,
        skill_manifest_context: str | None = None) -> str:
	"""Compose the full prompt for analysis with optional template and skill manifest."""
	parts = [base_prompt, context_block]

	if skill_manifest_context:
		parts.append(skill_manifest_context)

	if report_template:
		parts.append(
		    f"Report template you must use:\n```markdown\n{report_template}\n```"
		)

	return "\n\n".join(parts)


def _setup_workspace(
	config: Config,
	rp: RunParams,
	run_uuid: str,
) -> tuple[Path, str, str]:
	"""Create the run workspace and build the context block.

	Parameters:
		config: Application configuration.
		rp: Validated run parameters.
		run_uuid: Unique identifier for this run.

	Returns:
		Tuple of (workspace path, context block string, stream log path).
	"""
	workspace = ensure_within(
		config.output_path,
		config.output_path / rp.org_repo_slug / rp.alert_id_slug / run_uuid,
	)
	workspace.mkdir(parents=True, exist_ok=True)
	stream_log_path = workspace / "stream.log"
	context_block = (
		f"## Context\n\n- Repository: {rp.org_repo}\n- Alert ID: {rp.alert_id}\n"
		f"- Workspace: {workspace} !!! DO EVERYTHING HERE, ALWAYS !!!\n"
	)
	return workspace, context_block, stream_log_path


def _build_session_config(
	config: Config,
	agent: AgentConfig,
	workspace: Path,
	skill_dirs: list[str],
	disabled_skills: list[str],
	session_tools: list,
	rp: RunParams,
	run_id: str,
	run_uuid: str,
) -> dict:
	"""Build the session configuration dict for create_session().

	Parameters:
		config: Application configuration.
		agent: Agent definition.
		workspace: Run workspace path.
		skill_dirs: Discovered skill directories.
		disabled_skills: Skills to disable.
		session_tools: Tool definitions for the session.
		rp: Validated run parameters.
		run_id: Analysis run identifier.
		run_uuid: Unique run UUID.

	Returns:
		Session configuration dictionary.
	"""
	chosen_model = agent.model or config.model
	return {
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
	}


def _persist_diagnostics(
	run_id: str,
	collector: StreamCollector,
	skill_usage: object,
	workspace: Path,
) -> None:
	"""Write diagnostics JSON to the workspace directory.

	Parameters:
		run_id: Analysis run identifier.
		collector: Stream collector with usage data.
		skill_usage: Finalized skill usage stats.
		workspace: Run workspace path.
	"""
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
		diag_path.write_text(json.dumps(diagnostics, indent=2))
	except Exception:
		logger.debug(
			"failed to write diagnostics.json for run %s",
			run_id, exc_info=True,
		)


async def run_analysis(
    run_id: str,
    client: CopilotClientProtocol,
    config: Config,
    agent: AgentConfig,
    run_params: RunParams | None = None,
    org_repo: str | None = None,
    alert_id: str | None = None,
    progress_cb: ProgressCallback | None = None,
) -> AgentRunResult:
	"""
	Run a single analysis session.

	- Streams deltas to a log file and optional progress callback.
	- Parses the report markdown into a structured Report model.
	"""
	progress = AgentRunProgress(run_id=str(run_id), status=RunStatus.RUNNING)
	workspace: Path | None = None
	session = None
	logger.info("analysis %s start org_repo=%s alert_id=%s", run_id, org_repo,
	            alert_id)
	progress.log("analysis_started")
	if progress_cb:
		progress_cb(run_id, "analysis_started")

	try:
		prompt_template = load_prompt("analysis_task.md")
		rp = resolve_run_params(run_params, org_repo, alert_id)

		run_uuid = uuid.uuid4().hex
		workspace, context_block, stream_log_path = _setup_workspace(
			config, rp, run_uuid,
		)
		if progress_cb:
			progress_cb(run_id, f"workspace: {workspace}")

		report_template = load_and_validate_template(config.report_template_file)

		# Build skill directories from phase-based structure + config overrides
		skill_dirs = discover_skill_directories(config.skill_directories or [])
		skill_manifest = build_skill_manifest(skill_dirs)
		skill_manifest_context = format_manifest_for_context(skill_manifest)

		# Discover hidden skills (underscore-prefixed) to disable at runtime
		disabled_skills = discover_all_disabled_skills(config)

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

		session_tools = get_session_tools(config, org_repo, alert_id)
		session_config = _build_session_config(
			config, agent, workspace, skill_dirs, disabled_skills,
			session_tools, rp, run_id, run_uuid,
		)
		session = await client.create_session(session_config)
		session.on(collector.handler)

		raw = await send_and_collect(
			session, agent_prompt, config.analysis_timeout_seconds,
			collector, run_id, progress_cb, reraise=True,
		)

		progress.log("analysis_completed")
		if progress_cb:
			progress_cb(run_id, "analysis_completed")
		report = Report.from_markdown(raw or "")
		progress.status = RunStatus.COMPLETED

		# Finalize skill usage tracking
		skill_usage = collector.finalize_skill_usage()

		# Persist diagnostics JSON when --show-usage is active
		if config.show_usage and workspace:
			_persist_diagnostics(run_id, collector, skill_usage, workspace)

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
		await destroy_session_safe(session, f"analysis {run_id}")


__all__ = ["run_analysis"]
