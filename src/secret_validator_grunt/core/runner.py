"""
Main orchestrator for running validation sessions.

Coordinates parallel analysis runs and judge evaluation to produce
final validation outcomes.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

from secret_validator_grunt.models.config import Config
from secret_validator_grunt.loaders.agents import load_agent
from secret_validator_grunt.core.analysis import run_analysis
from secret_validator_grunt.core.judge import run_judge
from secret_validator_grunt.core.challenge import run_challenges
from secret_validator_grunt.ui.reporting import save_report_md
from secret_validator_grunt.ui.streaming import ProgressCallback
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.run_outcome import RunOutcome
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.models.report import Report
from secret_validator_grunt.evals.checks import run_all_checks
from secret_validator_grunt.utils.paths import ensure_within
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.copilot_client import create_client

logger = get_logger(__name__)


async def pre_clone_repo(
    org_repo: str,
    target_dir: Path,
    github_token: str | None = None,
) -> Path | None:
	"""Clone the repository once to a shared location.

	Uses git clone with token authentication for private repos.
	Returns the clone path on success, None on failure (letting
	agents fall back to cloning themselves).

	Parameters:
		org_repo: Repository in org/repo format.
		target_dir: Parent directory for the clone.
		github_token: Optional GitHub token for auth.

	Returns:
		Path to the cloned repo, or None if clone failed.
	"""
	repo_dir = target_dir / "_shared_repo"
	if repo_dir.exists():
		logger.debug("shared repo already exists at %s", repo_dir)
		return repo_dir

	repo_dir.mkdir(parents=True, exist_ok=True)

	# Build clone URL with token auth for private repos
	if github_token:
		clone_url = (f"https://x-access-token:{github_token}"
		             f"@github.com/{org_repo}.git")
	else:
		clone_url = f"https://github.com/{org_repo}.git"

	logger.info("pre-cloning %s to %s", org_repo, repo_dir)
	try:
		proc = await asyncio.create_subprocess_exec(
		    "git",
		    "clone",
		    "--depth=1",
		    clone_url,
		    ".",
		    cwd=str(repo_dir),
		    stdout=asyncio.subprocess.PIPE,
		    stderr=asyncio.subprocess.PIPE,
		    env={
		        **os.environ, "GIT_TERMINAL_PROMPT": "0"
		    },
		)
		_, stderr = await proc.communicate()
		if proc.returncode != 0:
			logger.warning(
			    "pre-clone failed (rc=%d): %s",
			    proc.returncode,
			    stderr.decode(errors="replace")[:500],
			)
			shutil.rmtree(repo_dir, ignore_errors=True)
			return None
		logger.info("pre-clone completed for %s", org_repo)
		return repo_dir
	except Exception as exc:
		logger.warning(
		    "pre-clone error: %s",
		    str(exc),
		)
		shutil.rmtree(repo_dir, ignore_errors=True)
		return None


def _run_eval_checks(
    results: list[AgentRunResult],
) -> list[AgentRunResult]:
	"""Run deterministic eval checks on each parsed report.

	Attaches an EvalResult to each AgentRunResult that has
	a parseable report. Logs warnings for failed checks and
	info for passed checks.

	Parameters:
		results: List of analysis results to evaluate.

	Returns:
		Updated list with eval_result attached to each
		result that has a parsed report.
	"""
	evaluated: list[AgentRunResult] = []
	for res in results:
		# Prefer pre-parsed report; fall back to re-parsing
		# raw markdown (defensive — run_analysis normally sets
		# res.report, but errors may leave it None).
		report = res.report
		if not report and res.raw_markdown:
			try:
				report = Report.from_markdown(
				    res.raw_markdown)
			except Exception:
				logger.warning(
				    "report %s: markdown parsing failed, "
				    "skipping eval checks",
				    res.run_id,
				    exc_info=True,
				)
		if report:
			eval_result = run_all_checks(
			    report, report_id=res.run_id)
			res = res.model_copy(
			    update={"eval_result": eval_result})
			if not eval_result.passed:
				failed = [
				    c.name for c in eval_result.checks
				    if c.severity == "error"
				    and not c.passed
				]
				logger.warning(
				    "report %s failed eval checks: %s",
				    res.run_id,
				    ", ".join(failed),
				)
			else:
				logger.info(
				    "report %s passed all eval checks",
				    res.run_id,
				)
		evaluated.append(res)
	return evaluated


def _persist_eval_results(
    results: list[AgentRunResult],
) -> None:
	"""Append eval_result to each run's diagnostics.json.

	Updates the existing diagnostics.json (written by
	``_persist_diagnostics`` in ``analysis.py``) with the
	``eval_result`` key.  Skipped silently when the file
	does not exist (i.e. ``show_usage`` was off during
	analysis) or the result has no workspace.

	Parameters:
		results: Analysis results with eval_result attached.
	"""
	for res in results:
		if not res.workspace or not res.eval_result:
			continue
		diag_path = Path(res.workspace) / "diagnostics.json"
		if not diag_path.exists():
			continue
		try:
			data = json.loads(diag_path.read_text())
			data["eval_result"] = res.eval_result.model_dump()
			diag_path.write_text(json.dumps(data, indent=2))
		except Exception:
			logger.debug(
			    "failed to update diagnostics.json with "
			    "eval_result for run %s",
			    res.run_id,
			    exc_info=True,
			)


async def run_all(
    config: Config,
    run_params: RunParams,
    progress_cb: ProgressCallback | None = None,
) -> RunOutcome:
	"""
	Run all analyses concurrently and judge the best report.

	Ensures client lifecycle is handled safely and exceptions
	from analyses are captured into AgentRunResult instances.

	Parameters:
		config: Application configuration.
		run_params: Validated run parameters.
		progress_cb: Optional progress callback.

	Returns:
		RunOutcome with judge result, analysis results,
		and challenge results.
	"""
	rp = run_params
	logger.info(
	    "run_all start org_repo=%s alert_id=%s",
	    rp.org_repo,
	    rp.alert_id,
	)
	validator_agent = load_agent(config.agent_file)
	judge_agent = load_agent(config.judge_agent_file)
	challenger_agent = load_agent(config.challenger_agent_file)

	alert_dir = ensure_within(
	    config.output_path,
	    config.output_path / rp.org_repo_slug / rp.alert_id_slug)
	alert_dir.mkdir(parents=True, exist_ok=True)

	# Pre-clone repository once to avoid N redundant git clones
	shared_repo = await pre_clone_repo(
	    rp.org_repo,
	    alert_dir,
	    config.github_token,
	)
	if shared_repo:
		logger.info("shared repo ready at %s", shared_repo)
	else:
		logger.info("pre-clone unavailable, agents will clone individually", )

	client = create_client(config)
	await client.start()
	try:
		# run analyses concurrently with optional semaphore
		max_parallel = config.max_parallel_sessions or config.analysis_count
		sem = asyncio.Semaphore(max_parallel)

		async def run_one(i: int):
			async with sem:
				return await run_analysis(
				    str(i),
				    client,
				    config,
				    validator_agent,
				    run_params=rp,
				    progress_cb=progress_cb,
				    pre_cloned_repo=shared_repo,
				)

		tasks = [run_one(i) for i in range(config.analysis_count)]
		results_raw = await asyncio.gather(*tasks, return_exceptions=True)
		logger.debug("analysis tasks completed")
		results: list[AgentRunResult] = []
		for idx, res in enumerate(results_raw):
			if isinstance(res, Exception):
				results.append(
				    AgentRunResult(
				        run_id=str(idx),
				        error=str(res),
				        progress_log=[],
				    ))
			else:
				results.append(res)

		# save individual reports
		for res in results:
			if res.raw_markdown:
				save_report_md(
				    alert_dir / f"report-{res.run_id}.md",
				    res.raw_markdown,
				)
				if res.workspace:
					save_report_md(
					    Path(res.workspace) / "report.md", res.raw_markdown)

		# run eval checks on each parsed report
		results = _run_eval_checks(results)

		# persist eval results into existing diagnostics.json
		if config.show_usage:
			_persist_eval_results(results)

		# challenge stage
		challenge_results = await run_challenges(
		    client,
		    config,
		    challenger_agent,
		    results,
		    rp,
		    progress_cb=progress_cb,
		    alert_dir=alert_dir,
		)
		# Annotate each result with its challenge
		for idx, cr in enumerate(challenge_results):
			results[idx] = results[idx].model_copy(
			    update={"challenge_result": cr})

		# judge
		judge_result = await run_judge(
		    client,
		    config,
		    judge_agent,
		    results,
		    run_params=rp,
		    progress_cb=progress_cb,
		)
		if (judge_result.winner_index >= 0
		    and 0 <= judge_result.winner_index < len(results)):
			winner = results[judge_result.winner_index]
			if winner.raw_markdown:
				save_report_md(
				    alert_dir / "final-report.md",
				    winner.raw_markdown,
				)
				if winner.workspace:
					save_report_md(
					    Path(winner.workspace) / "final-report.md",
					    winner.raw_markdown,
					)
	finally:
		await client.stop()
	logger.info("run_all done org_repo=%s alert_id=%s", rp.org_repo,
	            rp.alert_id)
	return RunOutcome(
	    judge_result=judge_result,
	    analysis_results=results,
	    challenge_results=challenge_results,
	)


__all__ = ["run_all", "pre_clone_repo"]
