"""
Adversarial challenge runner for validating analysis verdicts.

Challenges each analysis report by having an adversarial agent
attempt to disprove the verdict using workspace inspection and
active verification.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.challenge_result import (
    ChallengeResult,
    VALID_CHALLENGE_VERDICTS,
)
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.utils.parsing import extract_json
from secret_validator_grunt.ui.streaming import (
    StreamCollector,
    ProgressCallback,
)
from secret_validator_grunt.core.session import (
    send_and_collect,
    destroy_session_safe,
    discover_all_disabled_skills,
    build_session_config,
)
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.utils.protocols import CopilotClientProtocol
from secret_validator_grunt.core.skills import (
    discover_challenger_skill_directories,
    build_skill_manifest,
    format_manifest_for_context,
    CHALLENGER_SKILLS_DIRECTORY,
)
from secret_validator_grunt.loaders.prompts import load_prompt
from secret_validator_grunt.integrations.copilot_tools import get_session_tools

logger = get_logger(__name__)


def build_challenge_prompt(
    report_markdown: str,
    workspace_path: str | None,
    prompt_template: str,
    run_params: RunParams,
    skill_manifest_context: str | None = None,
) -> str:
	"""Compose challenge prompt with report and workspace.

	Replaces template placeholders with the report markdown
	and the analysis workspace path so the challenger knows
	where to inspect scripts, logs, and artifacts.

	Parameters:
		report_markdown: Raw markdown of the report.
		workspace_path: Path to the analysis workspace.
		prompt_template: Loaded challenge prompt template.
		run_params: Run parameters for context.
		skill_manifest_context: Formatted skill manifest.

	Returns:
		Composed prompt string.
	"""
	prompt = prompt_template.replace("{{report_markdown}}", report_markdown
	                                 or "")
	prompt = prompt.replace(
	    "{{workspace_path}}",
	    workspace_path or "(no workspace available)",
	)

	parts = [prompt]
	if skill_manifest_context:
		parts.append(skill_manifest_context)
	return "\n\n".join(parts)


def parse_challenge_result(raw: str) -> ChallengeResult:
	"""Parse ChallengeResult from raw LLM response.

	Uses the shared extract_json utility for JSON extraction.
	On parse failure returns INSUFFICIENT_EVIDENCE with the
	raw text as reasoning.

	Parameters:
		raw: Raw LLM response string.

	Returns:
		Parsed ChallengeResult.
	"""
	data = extract_json(raw or "")
	if data is None or not isinstance(data, dict):
		logger.warning("challenge: no JSON found in response")
		return ChallengeResult(
		    verdict="INSUFFICIENT_EVIDENCE",
		    reasoning=("Failed to parse challenge response: "
		               f"{(raw or '')[:200]}"),
		)

	verdict = data.get("verdict", "INSUFFICIENT_EVIDENCE")
	verdict_upper = str(verdict).upper().strip()
	if verdict_upper not in VALID_CHALLENGE_VERDICTS:
		verdict_upper = "INSUFFICIENT_EVIDENCE"

	return ChallengeResult(
	    verdict=verdict_upper,
	    reasoning=data.get("reasoning", ""),
	    evidence_gaps=data.get("evidence_gaps", []),
	    verification_reproduced=data.get(
	        "verification_reproduced",
	        None,
	    ),
	    verification_result=data.get(
	        "verification_result",
	        None,
	    ),
	    contradicting_evidence=data.get(
	        "contradicting_evidence",
	        [],
	    ),
	)


async def run_single_challenge(
    client: CopilotClientProtocol,
    config: Config,
    agent: AgentConfig,
    result: AgentRunResult,
    run_params: RunParams,
    challenge_index: int,
    progress_cb: ProgressCallback | None = None,
    alert_dir: Path | None = None,
) -> ChallengeResult:
	"""Challenge a single analysis report.

	Creates a Copilot session with access to the analysis
	workspace and GitHub API tools, sends the challenge
	prompt, and parses the response.

	Parameters:
		client: Copilot client instance.
		config: Application configuration.
		agent: Challenger agent configuration.
		result: The analysis result to challenge.
		run_params: Run parameters for context.
		challenge_index: Index of this challenge (for logging).
		progress_cb: Optional progress callback.
		alert_dir: Alert output directory for stream logs.

	Returns:
		Parsed ChallengeResult.
	"""
	run_id = f"challenge-{challenge_index}"
	logger.info("challenge %d start", challenge_index)
	if progress_cb:
		progress_cb(run_id, "challenge_started")

	prompt_template = load_prompt("challenge_task.md")
	report_md = (result.raw_markdown
	             or (result.report.raw_markdown if result.report else "")
	             or "")
	workspace_path = result.workspace

	# Build skill manifest for challenger skills
	skill_dirs = discover_challenger_skill_directories(
	    config.challenger_skill_directories or [], )
	skill_manifest = build_skill_manifest(skill_dirs)
	skill_manifest_context = format_manifest_for_context(skill_manifest)

	# Discover hidden skills (underscore-prefixed) to disable
	disabled_skills = discover_all_disabled_skills(
	    config,
	    CHALLENGER_SKILLS_DIRECTORY,
	)

	prompt = build_challenge_prompt(
	    report_md,
	    workspace_path,
	    prompt_template,
	    run_params,
	    skill_manifest_context=skill_manifest_context,
	)
	agent_prompt = f"@{agent.name}\n{prompt}"
	session_tools = get_session_tools(
	    config,
	    run_params.org_repo,
	    run_params.alert_id,
	)
	chosen_model = agent.model or config.model

	# Include analysis workspace in skill_directories so
	# the Copilot SDK indexes its contents
	session_skill_dirs = [
	    *([str(Path(workspace_path).resolve())] if workspace_path else []),
	    *skill_dirs,
	]

	stream_log_path: Path | None = None
	if alert_dir:
		slug = run_params.org_repo.replace("/", "_")
		log_name = (f"challenge-{challenge_index}"
		            f"-{slug}-{run_params.alert_id}"
		            f".stream.log")
		stream_log_path = alert_dir / log_name
	elif workspace_path:
		stream_log_path = (Path(workspace_path) / "challenge.stream.log")

	collector = StreamCollector(
	    run_id=run_id,
	    stream_log_path=stream_log_path,
	    stream_verbose=config.stream_verbose,
	    progress_cb=progress_cb,
	    show_usage=config.show_usage,
	    skill_manifest=skill_manifest,
	    disabled_skills=disabled_skills,
	)

	session = None
	try:
		session = await client.create_session(
		    build_session_config(
		        model=chosen_model,
		        streaming=False,
		        agent=agent,
		        tools=session_tools,
		        skill_directories=session_skill_dirs,
		        disabled_skills=disabled_skills,
		        system_message=("Respond ONLY with JSON in a fenced "
		                        "```json``` block, no prose."),
		        session_id=(f"{run_params.session_id_prefix}"
		                    f"-{run_id}"),
		    ))
		session.on(collector.handler)

		raw = await send_and_collect(
		    session,
		    agent_prompt,
		    config.challenger_timeout_seconds,
		    collector,
		    run_id,
		    progress_cb,
		    reraise=False,
		)
		cr = parse_challenge_result(raw or "")

		# Capture usage from collector when --show-usage is active
		if config.show_usage:
			cr.usage = collector.usage
			cr.skill_usage = collector.finalize_skill_usage()
			cr.tool_usage = collector.tool_usage
	except Exception as exc:
		logger.warning(
		    "challenge %d failed: %s",
		    challenge_index,
		    exc,
		)
		cr = ChallengeResult(
		    verdict="INSUFFICIENT_EVIDENCE",
		    reasoning=f"Challenge error: {exc}",
		)
	finally:
		await destroy_session_safe(session, run_id)

	if progress_cb:
		progress_cb(run_id, f"verdict={cr.verdict}")
	logger.info(
	    "challenge %d done verdict=%s",
	    challenge_index,
	    cr.verdict,
	)
	return cr


async def run_challenges(
    client: CopilotClientProtocol,
    config: Config,
    agent: AgentConfig,
    results: list[AgentRunResult],
    run_params: RunParams,
    progress_cb: ProgressCallback | None = None,
    alert_dir: Path | None = None,
) -> list[ChallengeResult]:
	"""Challenge all analysis reports in parallel.

	Creates one session per analysis report and challenges
	each verdict concurrently using the same semaphore
	pattern as runner.run_all().

	Parameters:
		client: Copilot client instance.
		config: Application configuration.
		agent: Challenger agent configuration.
		results: Analysis results to challenge.
		run_params: Run parameters for context.
		progress_cb: Optional progress callback.
		alert_dir: Alert output directory for stream logs.

	Returns:
		List of ChallengeResult aligned by index with the
		input results list.
	"""
	logger.info("challenges start: %d reports", len(results))
	max_parallel = (config.max_parallel_sessions or config.analysis_count)
	sem = asyncio.Semaphore(max_parallel)

	async def challenge_one(idx: int) -> ChallengeResult:
		async with sem:
			return await run_single_challenge(
			    client,
			    config,
			    agent,
			    results[idx],
			    run_params,
			    idx,
			    progress_cb,
			    alert_dir=alert_dir,
			)

	tasks = [challenge_one(i) for i in range(len(results))]
	raw_results = await asyncio.gather(
	    *tasks,
	    return_exceptions=True,
	)

	challenge_results: list[ChallengeResult] = []
	for idx, res in enumerate(raw_results):
		if isinstance(res, Exception):
			logger.warning(
			    "challenge %d exception: %s",
			    idx,
			    res,
			)
			challenge_results.append(
			    ChallengeResult(
			        verdict="INSUFFICIENT_EVIDENCE",
			        reasoning=f"Challenge exception: {res}",
			    ))
		else:
			challenge_results.append(res)

	logger.info("challenges done: %d results", len(results))
	return challenge_results


__all__ = [
    "build_challenge_prompt",
    "parse_challenge_result",
    "run_single_challenge",
    "run_challenges",
]
