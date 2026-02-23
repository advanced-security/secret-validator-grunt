"""
Analysis runner for Copilot validation sessions.

Executes single analysis sessions with streaming support, progress
callbacks, and structured report parsing.
"""

from __future__ import annotations

import json
import shutil
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
from secret_validator_grunt.models.skill_usage import SkillUsageStats
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
)
from secret_validator_grunt.integrations.copilot_tools import get_session_tools
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
    load_and_validate_template,
    discover_all_disabled_skills,
    build_session_config,
    send_and_collect,
    destroy_session_safe,
)

logger = get_logger(__name__)


def build_analysis_prompt(
    prompt_template: str,
    workspace_path: str,
    org_repo: str,
    alert_id: str,
    report_template: str | None = None,
    skill_manifest_context: str | None = None,
    repo_pre_cloned: bool = False,
) -> str:
	"""Compose analysis prompt with template variable substitution.

	Replaces template placeholders in the prompt with actual values,
	following the same pattern as build_challenge_prompt for consistency.

	Parameters:
		prompt_template: Loaded prompt template text with placeholders.
		workspace_path: Path to the analysis workspace directory.
		org_repo: Repository in org/repo format.
		alert_id: Secret scanning alert identifier.
		report_template: Report template markdown, or None.
		skill_manifest_context: Formatted skill manifest.
		repo_pre_cloned: Whether the repo was pre-cloned into workspace.

	Returns:
		Composed prompt string with all placeholders substituted.
	"""
	# Substitute template variables
	prompt = prompt_template.replace("{{workspace_path}}", workspace_path)
	prompt = prompt.replace("{{org_repo}}", org_repo)
	prompt = prompt.replace("{{alert_id}}", alert_id)

	parts = [prompt]

	if repo_pre_cloned:
		parts.append("## Pre-cloned Repository\n\n"
		             f"The repository has already been cloned for you at "
		             f"`{workspace_path}/repo/`. "
		             "Do NOT clone the repository again — it is ready to use. "
		             "Skip the repository-acquisition step and proceed "
		             "directly to analyzing the code.")

	if skill_manifest_context:
		parts.append(skill_manifest_context)

	if report_template:
		parts.append(f"Report template you must use:\n"
		             f"```markdown\n{report_template}\n```")

	return "\n\n".join(parts)


def _setup_workspace(
    config: Config,
    rp: RunParams,
    run_uuid: str,
) -> tuple[Path, Path]:
	"""Create the run workspace directory.

	Parameters:
		config: Application configuration.
		rp: Validated run parameters.
		run_uuid: Unique identifier for this run.

	Returns:
		Tuple of (workspace path, stream log path).
	"""
	workspace = ensure_within(
	    config.output_path,
	    config.output_path / rp.org_repo_slug / rp.alert_id_slug / run_uuid,
	)
	workspace.mkdir(parents=True, exist_ok=True)
	stream_log_path = workspace / "stream.log"
	return workspace, stream_log_path


def _persist_diagnostics(
    run_id: str,
    collector: StreamCollector,
    skill_usage: SkillUsageStats,
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
	    "run_id":
	    str(run_id),
	    "skill_usage":
	    skill_usage.model_dump(),
	    "tool_usage":
	    (collector.tool_usage.model_dump() if collector.tool_usage else None),
	    "usage":
	    collector.usage.model_dump(),
	}
	try:
		diag_path = workspace / "diagnostics.json"
		diag_path.write_text(json.dumps(diagnostics, indent=2))
	except Exception:
		logger.debug(
		    "failed to write diagnostics.json for run %s",
		    run_id,
		    exc_info=True,
		)


async def run_analysis(
    run_id: str,
    client: CopilotClientProtocol,
    config: Config,
    agent: AgentConfig,
    run_params: RunParams,
    progress_cb: ProgressCallback | None = None,
    pre_cloned_repo: Path | None = None,
) -> AgentRunResult:
	"""
	Run a single analysis session.

	Parameters:
		run_id: Identifier for this analysis run.
		client: Copilot client instance.
		config: Application configuration.
		agent: Agent configuration.
		run_params: Validated run parameters.
		progress_cb: Optional progress callback.
		pre_cloned_repo: Path to pre-cloned repository.

	Returns:
		AgentRunResult with analysis output.
	"""
	rp = run_params
	progress = AgentRunProgress(run_id=str(run_id), status=RunStatus.RUNNING)
	workspace: Path | None = None
	session = None
	logger.info(
	    "analysis %s start org_repo=%s alert_id=%s",
	    run_id,
	    rp.org_repo,
	    rp.alert_id,
	)
	progress.log("analysis_started")
	if progress_cb:
		progress_cb(run_id, "analysis_started")

	try:
		prompt_template = load_prompt("analysis_task.md")
		continuation_prompt = load_prompt("continuation_task.md", )

		run_uuid = uuid.uuid4().hex
		workspace, stream_log_path = _setup_workspace(
		    config,
		    rp,
		    run_uuid,
		)

		# Copy pre-cloned repo into workspace if available
		repo_pre_cloned = False
		if pre_cloned_repo and pre_cloned_repo.exists():
			dest = workspace / "repo"
			if not dest.exists():
				try:
					shutil.copytree(
					    str(pre_cloned_repo),
					    str(dest),
					)
					repo_pre_cloned = True
					logger.debug(
					    "analysis %s: repo copied from pre-clone",
					    run_id,
					)
				except Exception as exc:
					logger.warning(
					    "analysis %s: repo copy failed: %s",
					    run_id,
					    exc,
					)

		if progress_cb:
			progress_cb(run_id, f"workspace: {workspace}")

		report_template = load_and_validate_template(
		    config.report_template_file)

		# Build skill directories from phase-based structure + config overrides
		skill_dirs = discover_skill_directories(
		    config.analysis_skill_directories or [])
		skill_manifest = build_skill_manifest(skill_dirs)
		skill_manifest_context = format_manifest_for_context(skill_manifest)

		# Discover hidden skills (underscore-prefixed) to disable at runtime
		disabled_skills = discover_all_disabled_skills(config)

		prompt = build_analysis_prompt(
		    prompt_template,
		    workspace_path=str(workspace),
		    org_repo=rp.org_repo,
		    alert_id=rp.alert_id,
		    report_template=report_template,
		    skill_manifest_context=skill_manifest_context,
		    repo_pre_cloned=repo_pre_cloned,
		)
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

		session_tools = get_session_tools(
		    config,
		    rp.org_repo,
		    rp.alert_id,
		)
		session_config = build_session_config(
		    model=agent.model or config.model,
		    streaming=True,
		    agent=agent,
		    tools=session_tools,
		    skill_directories=[
		        str(workspace.resolve()),
		        *skill_dirs,
		    ],
		    disabled_skills=disabled_skills,
		    session_id=(f"{rp.session_id_prefix}-{run_id}-{run_uuid}"),
		)
		session = await client.create_session(session_config)
		session.on(collector.handler)

		raw = await send_and_collect(
		    session,
		    agent_prompt,
		    config.analysis_timeout_seconds,
		    collector,
		    run_id,
		    progress_cb,
		    reraise=True,
		    continuation_prompt=continuation_prompt,
		    max_continuations=config.max_continuation_attempts,
		    min_response_length=config.min_response_length,
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


__all__ = ["run_analysis", "build_analysis_prompt"]
