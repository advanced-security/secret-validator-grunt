# Code map

Application code lives in `src/secret_validator_grunt/`.

## Start here

Read [main.py](../src/secret_validator_grunt/main.py) for CLI inputs and
`RunParams`/`Config` overrides, then
[core/runner.py](../src/secret_validator_grunt/core/runner.py) for the workflow
and `RunOutcome` assembly.
Follow the stage relevant to your change: `core/analysis.py`,
`core/challenge.py`, or `core/judge.py`.

The runners use [core/session.py](../src/secret_validator_grunt/core/session.py)
to configure and collect SDK sessions, and
[copilot_client.py](../src/secret_validator_grunt/copilot_client.py) to select
native or external-server operation. Stage results are defined in
`models/run_result.py`, `models/challenge_result.py`, and `models/judge_result.py`.

## Responsibilities

| Area | Responsibility |
| --- | --- |
| `core/` | Run the stages, manage sessions, deliver skills, and protect challenger evidence |
| `integrations/` | Connect to GitHub, expose agent tools, and share alert reads |
| `models/` | Define configuration, reports, results, and diagnostics with Pydantic |
| `loaders/` | Read agent definitions, prompts, templates, and metadata |
| `agents/` | Define each agent's role, model, and tools |
| `skills/` | Provide required methodology and optional task-specific guidance |
| `prompts/` | Describe each stage's task |
| `templates/` | Define the report format |
| `evals/` | Check report structure and consistency |
| `ui/` | Collect session events and display progress and results |
| `utils/` | Share path, parsing, logging, and protocol helpers |

Keep new code in the area that owns the behavior. Do not recreate the old
`services/` directory.

## Where common changes belong

Test paths below are relative to the repository root.

| Change | Start with | Companion tests |
| --- | --- | --- |
| Agent reasoning or instructions | The agent definition, task prompt, and relevant skills; `core/skills.py` | `tests/test_skills.py`, `tests/test_session.py` |
| CLI/configuration or runtime connection | `main.py`, `models/config.py`, `copilot_client.py` | `tests/test_cli.py`, `tests/test_config.py`, `tests/test_copilot_client.py` |
| Session setup, timeouts, or continuation | [core/session.py](../src/secret_validator_grunt/core/session.py) | `tests/test_session.py` |
| Challenger outputs or evidence protection | [core/challenge_workspace.py](../src/secret_validator_grunt/core/challenge_workspace.py) and `core/challenge.py` | `tests/test_challenge_workspace.py`, `tests/test_challenge.py` |
| GitHub response normalization or pagination | [integrations/github.py](../src/secret_validator_grunt/integrations/github.py) | `tests/test_github.py` |
| Shared GitHub reads, refresh, or cancellation | [integrations/github_evidence.py](../src/secret_validator_grunt/integrations/github_evidence.py) | `tests/test_github_evidence.py` |
| Agent-facing tools | [integrations/copilot_tools.py](../src/secret_validator_grunt/integrations/copilot_tools.py) | `tests/test_tools.py` |
| Report parsing or format | `models/report.py`, `templates/`, and report fixtures | `tests/test_report_parser.py`, `tests/test_report_parsing_tables.py`, `tests/test_evals.py` |
| Report checks | `evals/checks.py`, `evals/__init__.py` | `tests/test_evals.py` |
| Event collection or diagnostic counters | `ui/streaming.py` and related models | `tests/test_streaming_progress.py`, `tests/test_skill_usage.py` |
| Log redraw or terminal rendering | `main.py`, `utils/logging.py`, `ui/tui.py` | `tests/test_logging.py`, `tests/test_ui.py` |
| Final report persistence or summary paths | `core/runner.py`, `models/summary.py` | `tests/test_runner.py`, `tests/test_summary.py` |

GitHub tools call the run-scoped `GitHubEvidence` service, which uses
`integrations/github.py` for blocking API reads and JSON-safe normalization.
Keep those boundaries: do not duplicate fetching or serialize raw ghapi
collections inside individual agents.

Tests live in `tests/`; report examples and expected results are in
`tests/fixtures/reports/`. Use the [development guide](development.md) for
conventions and commands. Read source models for current fields rather than
treating this guide as an API reference.
