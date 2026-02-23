"""
Judge runner for selecting the best analysis report.

Executes a judge session to evaluate multiple analysis reports
and select the winning report based on quality metrics.
"""

from __future__ import annotations

from pathlib import Path

from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.judge_result import JudgeResult, JudgeScore
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.utils.parsing import extract_json
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
)
from secret_validator_grunt.integrations.copilot_tools import get_session_tools
from secret_validator_grunt.utils.paths import ensure_within
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.protocols import CopilotClientProtocol
from secret_validator_grunt.core.skills import discover_skill_directories
from secret_validator_grunt.loaders.prompts import load_prompt
from secret_validator_grunt.core.session import (
    load_and_validate_template,
    discover_all_disabled_skills,
    build_session_config,
    send_and_collect,
    destroy_session_safe,
)

logger = get_logger(__name__)


def _format_skill_usage_summary(result: AgentRunResult) -> str:
	"""
	Format skill usage summary for a single report.

	Parameters:
		result: The agent run result containing skill usage data.

	Returns:
		Markdown formatted skill usage summary, or empty string if no data.
	"""
	su = result.skill_usage
	if not su:
		return ""

	loaded_required = set(su.loaded_skills) & set(su.required_skills)
	skipped_required = set(su.required_skills) - set(su.loaded_skills)

	lines = [
	    "\n### Methodology Compliance",
	    "",
	    "| Metric | Value |",
	    "|--------|-------|",
	    f"| Skills Loaded | {len(su.loaded_skills)}/{len(su.available_skills)} |",
	    f"| Required Skills Loaded "
	    f"| {len(loaded_required)}/{len(su.required_skills)} |",
	    f"| Compliance Score | {su.compliance_score:.0f}% |",
	    "",
	]

	if loaded_required:
		lines.append(
		    f"**Required Skills Loaded:** {', '.join(sorted(loaded_required))}"
		)
	if skipped_required:
		lines.append(
		    f"**Required Skills Skipped:** {', '.join(sorted(skipped_required))}"
		)
	if su.loaded_skills:
		lines.append(
		    f"**All Skills Loaded:** {', '.join(sorted(su.loaded_skills))}")

	return "\n".join(lines)


def _format_reports(results: list[AgentRunResult]) -> str:
	"""
	Combine reports into a single markdown blob for judging.

	Includes skill usage summary when available to help judge
	assess methodology compliance. Also includes challenge annotations
	when challenger stage results are present.

	Parameters:
		results: List of agent run results to format.

	Returns:
		Combined markdown string with all reports and skill usage.
	"""
	blocks = []
	for idx, res in enumerate(results):
		body = (res.raw_markdown
		        or (res.report.raw_markdown if res.report else "") or "")
		skill_summary = _format_skill_usage_summary(res)
		block = f"REPORT {idx}:\n{body}\n{skill_summary}\n"

		# Append challenge annotation if present
		if res.challenge_result:
			cr = res.challenge_result
			block += (f"\n--- ADVERSARIAL CHALLENGE RESULT ---\n"
			          f"Challenge Verdict: {cr.verdict}\n"
			          f"Reasoning: {cr.reasoning}\n")
			if cr.evidence_gaps:
				block += (f"Evidence Gaps: "
				          f"{', '.join(cr.evidence_gaps)}\n")
			if cr.contradicting_evidence:
				block += (f"Contradicting Evidence: "
				          f"{', '.join(cr.contradicting_evidence)}\n")
			block += "--- END CHALLENGE ---\n"

		blocks.append(block)
	return "\n".join(blocks)


def _build_judge_prompt(
    prompt: str,
    report_template: str | None,
    context_block: str,
    reports_blob: str,
) -> str:
	"""Compose full judge prompt including template, context, and reports."""
	template_block = (
	    f"\n\nExpected report template:\n```markdown\n{report_template}\n```"
	    if report_template else "")
	return (f"{prompt}{template_block}\n\n"
	        f"{context_block}\n\nReports:\n{reports_blob}")


async def run_judge(
    client: CopilotClientProtocol,
    config: Config,
    judge_agent: AgentConfig,
    results: list[AgentRunResult],
    run_params: RunParams,
    progress_cb: ProgressCallback | None = None,
) -> JudgeResult:
	"""Run judge session to select the best report among analysis results."""
	rp = run_params
	logger.info(
	    "judge start org_repo=%s alert_id=%s",
	    rp.org_repo,
	    rp.alert_id,
	)
	prompt = load_prompt("judge_task.md")
	reports_blob = _format_reports(results)

	report_template = load_and_validate_template(config.report_template_file)
	alert_dir = ensure_within(
	    config.output_path,
	    config.output_path / rp.org_repo_slug / rp.alert_id_slug)
	alert_dir.mkdir(parents=True, exist_ok=True)
	workspace = alert_dir
	if progress_cb:
		progress_cb("judge", "judge_started")
		progress_cb("judge", f"workspace: {workspace}")
	context_block = (
	    f"## Context\n\n- Repository: {rp.org_repo}\n- Alert ID: {rp.alert_id}\n"
	    f"- Workspace: {workspace} !!! DO EVERYTHING HERE, ALWAYS !!!\n")
	full_prompt = _build_judge_prompt(prompt, report_template, context_block,
	                                  reports_blob)
	agent_prompt = f"@{judge_agent.name}\n{full_prompt}"
	stream_log_path = (
	    workspace /
	    f"judge-{rp.org_repo.replace('/', '_')}-{rp.alert_id}.stream.log")
	collector = StreamCollector(
	    run_id="judge",
	    stream_log_path=stream_log_path,
	    stream_verbose=config.stream_verbose,
	    progress_cb=progress_cb,
	    show_usage=config.show_usage,
	)

	session_tools = get_session_tools(
	    config,
	    rp.org_repo,
	    rp.alert_id,
	)
	disabled_skills = discover_all_disabled_skills(config)

	session = None
	try:
		session = await client.create_session(
		    build_session_config(
		        model=judge_agent.model or config.model,
		        streaming=False,
		        agent=judge_agent,
		        tools=session_tools,
		        skill_directories=[
		            str(workspace.resolve()),
		            *discover_skill_directories(
		                config.analysis_skill_directories or [], ),
		        ],
		        disabled_skills=disabled_skills,
		        system_message=("Respond ONLY with JSON in a fenced"
		                        " ```json``` block, no prose."
		                        " If uncertain, respond with"
		                        ' {"winner_index": -1,'
		                        ' "scores": [],'
		                        ' "rationale":'
		                        ' "Invalid reports",'
		                        ' "verdict": ""}'),
		    ))
		session.on(collector.handler)

		raw = await send_and_collect(
		    session,
		    agent_prompt,
		    config.judge_timeout_seconds,
		    collector,
		    "judge",
		    progress_cb,
		    reraise=False,
		)
	finally:
		await destroy_session_safe(session, "judge")

	parsed = extract_json(raw)
	if parsed:
		try:
			jr = JudgeResult(**parsed)
			jr.raw_response = raw
			jr.usage = collector.usage
			jr.workspace = str(workspace)
			logger.info(
			    "judge completed org_repo=%s alert_id=%s",
			    rp.org_repo,
			    rp.alert_id,
			)
			if progress_cb:
				progress_cb("judge", "judge_completed")
			return jr
		except Exception:
			logger.debug("failed to parse JudgeResult from JSON",
			             exc_info=True)
	# fallback with error
	logger.warning(
	    "judge failed parse org_repo=%s alert_id=%s",
	    rp.org_repo,
	    rp.alert_id,
	)
	if progress_cb:
		progress_cb("judge", "judge_failed_parse")
	return JudgeResult(
	    winner_index=-1,
	    scores=[
	        JudgeScore(report_index=i, score=0) for i in range(len(results))
	    ],
	    rationale=None,
	    verdict=None,
	    raw_response=raw or "",
	    workspace=str(workspace),
	)


__all__ = ["run_judge"]
