# Code Structure

## Directory Layout

```
src/secret_validator_grunt/
  main.py                  # CLI entry point (Typer)
  copilot_client.py        # CopilotClient factory
  cli_fmt.py               # Code formatting CLI

  core/                    # Business logic
    runner.py              # Orchestrator: run_all() — parallel analyses + judge
    analysis.py            # Single analysis session: run_analysis()
    judge.py               # Judge session: run_judge()
    skills.py              # Skill discovery, manifest building, formatting

  evals/                   # Report evaluation framework
    checks.py              # Deterministic check functions + orchestrator

  models/                  # Pydantic data models (one class per file)
    config.py              # Config (BaseSettings) — env-driven configuration
    agent_config.py        # AgentConfig — parsed from agent .md frontmatter
    run_params.py          # RunParams — validated CLI inputs (org_repo, alert_id)
    run_result.py          # AgentRunResult — output of a single analysis
    run_outcome.py         # RunOutcome — aggregate: all results + judge
    run_progress.py        # AgentRunProgress — live status tracking
    report.py              # Report — parsed markdown report with fields
    judge_result.py        # JudgeResult — winner_index, scores, rationale
    skill.py               # SkillInfo, SkillManifest — skill metadata
    skill_usage.py         # SkillUsageStats — skill load tracking + compliance
    tool_usage.py          # ToolUsageStats — tool call tracking + success rates
    usage.py               # UsageStats — token/cost/duration tracking
    eval_result.py         # EvalCheck, EvalResult — eval framework models

  ui/                      # Presentation layer
    tui.py                 # Rich-based TUI with Live display
    streaming.py           # StreamCollector — session event handler
    reporting.py           # Report rendering and file persistence

  integrations/            # External service integrations
    copilot_tools.py       # Custom Copilot session tools (GitHub API, validate_secret)
    custom_agents.py       # AgentConfig → Copilot SDK CustomAgentConfig
    github.py              # GitHub API client (ghapi wrappers)

  loaders/                 # File loading utilities
    agents.py              # Agent markdown file parser
    templates.py           # Report template loader
    prompts.py             # Prompt markdown loader
    frontmatter.py         # YAML frontmatter parser

  agents/                  # Agent definition files
    secret_validator.agent.md   # Analysis agent (Claude Opus 4.5)
    judge.agent.md              # Judge agent (Gemini 3 Pro Preview)

  skills/                  # Phase-organized methodology skills
    1-initialization/
    2-context-gathering/
    3-verification/
    4-scoring-and-reporting/
    custom/                # User-extensible skill directory

  prompts/                 # Prompt templates
    analysis_task.md       # Base prompt for analysis sessions
    judge_task.md          # Base prompt for judge sessions

  templates/               # Report templates
    report.md              # Structured report template

  utils/                   # Shared utilities
    logging.py             # Logging configuration
    parsing.py             # JSON extraction from markdown
    paths.py               # Path sanitization and traversal guards
    protocols.py           # Protocol types for client/session
```

## Module Responsibilities

### `core/runner.py` — The Orchestrator

Entry point for the full validation pipeline. Creates the Copilot client, runs N analyses concurrently (with semaphore-based concurrency control), saves individual reports, then runs the judge to pick the winner. Returns a `RunOutcome` containing all results.

### `core/analysis.py` — Single Analysis Session

Sets up one analysis session: builds the prompt (base prompt + context + report template + skill manifest), creates a `StreamCollector`, creates a Copilot session with tools and skills, sends the prompt, and waits for the response. On completion, parses the report, finalizes skill tracking, optionally writes `diagnostics.json`, and returns `AgentRunResult`.

### `core/judge.py` — Judge Session

Takes all analysis results, formats them with skill usage compliance summaries, and sends them to a judge agent that evaluates and selects the best report via structured JSON output. The judge does not need skill tracking or the full skill manifest — it focuses on report quality assessment.

### `core/skills.py` — Skill Discovery Engine

Scans the skills directory tree for `SKILL.md` files, extracts metadata from YAML frontmatter, and builds a `SkillManifest`. Also handles:
- Phase directory discovery for session registration
- Hidden skill detection (underscore-prefixed directories)
- Manifest formatting as markdown context for the agent prompt

### `ui/streaming.py` — Event Processing Hub

`StreamCollector` is the central event handler for all Copilot SDK session events. It routes events to appropriate handlers: message deltas for content assembly, tool events for skill and tool tracking, usage events for token/cost accumulation. It produces the data that feeds into `AgentRunResult`.

### `ui/tui.py` — Terminal Display

Rich-based TUI with `Live` auto-refresh showing real-time progress of parallel analyses. After completion, renders summary tables: winner report, judge decision, workspaces, and (with `--show-usage`) usage statistics, skill compliance, and tool call breakdowns.

### `integrations/copilot_tools.py` — Custom Session Tools

Defines four custom tools available to the agent during sessions:
- `gh_secret_scanning_alert` — Fetch alert details from GitHub API
- `gh_secret_scanning_alert_locations` — Fetch alert location metadata
- `validate_secret` — Run deterministic validators from the `validate-secrets` library
- `list_secret_validators` — List available secret type validators

### `models/` — Data Layer

All data structures are Pydantic models with `Field` descriptions. Key patterns:
- Mutable list fields use `Field(default_factory=list)`
- Optional fields for backward compatibility
- `from __future__ import annotations` in all files
- `__all__` exports in every module
- Use built-in generics (`list`, `dict`, `tuple`) and `X | None` instead of `typing.List`, `Optional[X]`

### `evals/checks.py` — Report Evaluation Engine

Deterministic evaluation checks that validate the structural and semantic quality of agent-generated reports. Each check is a pure function `(Report) -> EvalCheck` that examines one aspect of report quality.

**Checks implemented (9 total):**
1. `has_required_sections` — All 9 required section headings present (error)
2. `valid_verdict` — Verdict is one of: TRUE_POSITIVE, FALSE_POSITIVE, SUSPICIOUS, INCONCLUSIVE (error)
3. `valid_confidence_score` — Score is a number in [0, 10] (error)
4. `confidence_label_matches_score` — Label (High/Medium/Low) matches the score via `_score_to_label()` (error)
5. `metadata_complete` — repository, alert_id, secret_type, report_date are populated (error)
6. `has_key_finding` — Key finding is non-empty (error)
7. `has_verification_tests` — Verification testing content present (warning)
8. `has_code_evidence` — File paths or code blocks in markdown (warning)
9. `verdict_confidence_coherent` — INCONCLUSIVE + high confidence is incoherent (error)

`run_all_checks()` orchestrates all checks and returns an `EvalResult`. The `EvalResult.passed` property ignores warning-severity failures — only errors determine pass/fail.
