"""
Main orchestrator for running validation sessions.

Coordinates parallel analysis runs and judge evaluation to produce
final validation outcomes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

from secret_validator_grunt.models.config import Config, load_env
from secret_validator_grunt.loaders.agents import load_agent
from secret_validator_grunt.core.analysis import run_analysis
from secret_validator_grunt.core.judge import run_judge
from secret_validator_grunt.ui.reporting import save_report_md
from secret_validator_grunt.ui.streaming import ProgressCallback
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.judge_result import JudgeResult
from secret_validator_grunt.models.run_outcome import RunOutcome
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.utils.paths import ensure_within
from secret_validator_grunt.utils.logging import get_logger
from secret_validator_grunt.copilot_client import create_client

logger = get_logger(__name__)


async def run_all(
    config: Config,
    org_repo: Optional[str] = None,
    alert_id: Optional[str] = None,
    run_params: Optional["RunParams"] = None,
    progress_cb: Optional[ProgressCallback] = None,
) -> RunOutcome:
	"""
	Run all analyses concurrently and judge the best report.

	Ensures client lifecycle is handled safely and exceptions from analyses
	are captured into AgentRunResult instances.
	"""
	logger.info("run_all start org_repo=%s alert_id=%s", org_repo, alert_id)
	validator_agent = load_agent(config.agent_file)
	judge_agent = load_agent(config.judge_agent_file)

	rp = run_params
	if rp is None:
		if not org_repo or not alert_id:
			raise ValueError("org_repo and alert_id are required")
		rp = RunParams(org_repo=org_repo, alert_id=alert_id)

	alert_dir = ensure_within(
	    config.output_path,
	    config.output_path / rp.org_repo_slug / rp.alert_id_slug)
	alert_dir.mkdir(parents=True, exist_ok=True)

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
				    org_repo=rp.org_repo,
				    alert_id=rp.alert_id,
				    progress_cb=progress_cb,
				)

		tasks = [run_one(i) for i in range(config.analysis_count)]
		results_raw = await asyncio.gather(*tasks, return_exceptions=True)
		logger.debug("analysis tasks completed")
		results: List[AgentRunResult] = []
		for idx, res in enumerate(results_raw):
			if isinstance(res, Exception):
				results.append(
				    AgentRunResult(run_id=str(idx), error=str(res),
				                   progress_log=[]))
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

		# judge
		judge_result = await run_judge(
		    client,
		    config,
		    judge_agent,
		    results,
		    run_params=rp,
		    org_repo=rp.org_repo,
		    alert_id=rp.alert_id,
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
	return RunOutcome(judge_result=judge_result, analysis_results=results)


def main() -> None:
	"""Entrypoint for manual execution."""
	load_env()
	config = Config()
	asyncio.run(run_all(config))


if __name__ == "__main__":
	main()

__all__ = ["run_all", "main"]
