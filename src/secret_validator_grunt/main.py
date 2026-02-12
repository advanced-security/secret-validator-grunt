from __future__ import annotations

import asyncio
import sys

import typer
from typer.main import get_command

from secret_validator_grunt.models.config import Config, load_env
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.core.runner import run_all
from secret_validator_grunt.ui.tui import TUI
from secret_validator_grunt.utils.logging import configure_logging

cli = typer.Typer(add_completion=False, no_args_is_help=True)


@cli.callback()
def root() -> None:
	"""
	Root callback for the secret-validator CLI.

	Sets up the Typer application with no-args-is-help behavior.
	"""
	return None


def run_impl(
    org_repo: str,
    alert_id: str,
    analyses: int | None = None,
    timeout: int | None = None,
    judge_timeout: int | None = None,
    stream_verbose: bool | None = None,
    show_usage: bool | None = None,
) -> None:
	"""
	Run N parallel analyses and judge to select the best report.

	Orchestrates the full validation workflow: loads configuration,
	spins up concurrent analysis sessions, runs a judge to pick
	the winner, and displays results in the TUI.

	Parameters:
		org_repo: GitHub repository in 'owner/repo' format.
		alert_id: Secret scanning alert ID to validate.
		analyses: Override for number of parallel analyses.
		timeout: Override for analysis timeout in seconds.
		judge_timeout: Override for judge timeout in seconds.
		stream_verbose: Whether to stream deltas to console.
		show_usage: Whether to show token/cost metrics.
	"""
	load_env()
	configure_logging()
	params = RunParams(
	    org_repo=org_repo,
	    alert_id=alert_id,
	    analyses=analyses,
	    timeout=timeout,
	    judge_timeout=judge_timeout,
	    stream_verbose=stream_verbose,
	    show_usage=show_usage,
	)
	config = Config()
	config.apply_overrides(params)
	typer.echo(
	    f"Running with model={config.model}, analyses={config.analysis_count}, "
	    f"repo={org_repo}, alert={alert_id}, "
	    f"analysis_timeout={config.analysis_timeout_seconds}s, "
	    f"judge_timeout={config.judge_timeout_seconds}s, "
	    f"stream_verbose={config.stream_verbose}")

	with TUI(
	    config.analysis_count,
	    show_usage=config.show_usage,
	    org_repo=params.org_repo,
	    alert_id=params.alert_id,
	) as ui:

		def progress_cb(run_id: str, msg: str) -> None:
			ui.update(str(run_id), msg)

		outcome = asyncio.run(
		    run_all(
		        config,
		        run_params=params,
		        progress_cb=progress_cb,
		    ))
		# Update TUI with outcome data from analysis results
		for res in outcome.analysis_results:
			report = res.report
			if report:
				ui.update_outcome(
				    str(res.run_id),
				    verdict=report.verdict,
				    confidence=
				    (f"{report.confidence_score}/10 ({report.confidence_label})"
				     if report.confidence_score else None),
				    risk_level=report.risk_level,
				    key_finding=report.key_finding,
				)
		# Update judge outcome
		if outcome.judge_result:
			jr = outcome.judge_result
			ui.update_outcome(
			    "judge",
			    verdict=jr.verdict,
			    key_finding=jr.rationale,
			)
		ui.print_summary(
		    outcome.judge_result.winner_index,
		    outcome.analysis_results,
		    config.output_path,
		    judge_result=outcome.judge_result,
		)


@cli.command()
def run(
    org_repo: str,
    alert_id: str,
    analyses: int = typer.Option(None, "--analyses",
                                 help="Override analysis count"),
    timeout: int = typer.Option(None, "--timeout",
                                help="Override analysis timeout seconds"),
    judge_timeout: int = typer.Option(None, "--judge-timeout",
                                      help="Override judge timeout seconds"),
    stream_verbose: bool = typer.Option(
        None,
        "--stream-verbose/--no-stream-verbose",
        help="Stream deltas to console",
    ),
    show_usage: bool = typer.Option(
        False,
        "--show-usage/--no-show-usage",
        help="Show token/cost usage metrics",
    ),
) -> None:
	"""
	Run N analyses and judge for a given org/repo and alert_id.

	This is the main CLI command that orchestrates secret validation.
	"""
	run_impl(org_repo, alert_id, analyses, timeout, judge_timeout,
	         stream_verbose, show_usage)


def entrypoint(argv=None, *, standalone_mode: bool = True):
	"""
	Typer entrypoint that defaults to `run` when appropriate.

	Allows calling 'secret-validator-grunt org/repo alert_id' without
	explicitly specifying the 'run' subcommand.

	Parameters:
		argv: Command-line arguments. Defaults to sys.argv[1:].
		standalone_mode: If True, Click handles exit codes.

	Returns:
		Result of the Click application main invocation.
	"""
	args = sys.argv[1:] if argv is None else list(argv)

	_click_app = get_command(cli)
	commands = getattr(_click_app, "commands", {}).keys()
	# allow optional `run` prefix; default to run when first arg is not a command/option
	if args and args[0] == "run":
		args = args[1:]
	if args and not args[0].startswith("-") and args[0] not in commands:
		args = ["run"] + args
	return _click_app.main(
	    args=args,
	    prog_name="secret-validator-grunt",
	    standalone_mode=standalone_mode,
	)


if __name__ == "__main__":
	entrypoint()
