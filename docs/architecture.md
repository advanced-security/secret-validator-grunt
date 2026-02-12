# Architecture & Design

## What Is This Project

Secret Validator Grunt is an agentic framework that validates GitHub Secret Scanning alerts. It determines whether a detected secret is a **true positive** (real, active secret) or a **false positive** (inactive, test data, or non-secret). It does this by orchestrating multiple concurrent Copilot SDK agent sessions, each independently analyzing the alert, then using an LLM judge to select the best report.

## High-Level Flow

```
CLI invocation
  └─ main.py (Typer CLI) ─ parses args, loads Config
       └─ runner.py (run_all) ─ orchestrates everything
            ├─ N × analysis.py (run_analysis) ─ concurrent agent sessions
            │     ├─ Copilot SDK session with streaming
            │     ├─ Skills manifest injected as context
            │     ├─ Custom tools (GitHub API, validate_secret)
            │     ├─ StreamCollector captures events + tracks usage
            │     └─ Report parsed from agent markdown output
            ├─ judge.py (run_judge) ─ evaluates all reports
            │     ├─ Reports + skill compliance formatted together
            │     └─ Returns JSON with winner_index + scores
            └─ RunOutcome ─ final result passed to TUI for display
```

## Core Concepts

### Multi-Agent Consensus

Rather than trusting a single agent run, the system runs N analyses (default 3) concurrently. Each agent independently researches the secret, writes verification scripts, and produces a structured report. A separate judge agent then compares all reports and selects the most complete and well-evidenced one. This reduces variance and catches individual agent mistakes.

### Skills as Methodology

Skills are markdown files (`SKILL.md`) organized by workflow phase. They act as structured instructions injected into the agent's context. The agent loads them on-demand via the `skill` tool during its session. Skills define the validation methodology — from setting up a testing environment, to cloning the repo, to writing verification scripts, to scoring confidence. Required skills enforce methodology compliance.

### Streaming Event Collection

All Copilot SDK session events flow through `StreamCollector`, which handles:
- Assembling the final response from message deltas
- Tracking skill load events (which skills the agent invoked)
- Tracking tool call events (when `--show-usage` is active)
- Accumulating token/cost usage statistics

### Structured Reporting

The agent's raw markdown output is parsed into a `Report` model that extracts the executive summary table (verdict, confidence score, risk level, secret type, key finding). This enables programmatic access to results and structured display in the TUI.

## Data Flow

1. **Input**: `org/repo` + `alert_id` from CLI
2. **Config**: Environment variables and `.env` file loaded into `Config` (pydantic-settings)
3. **Agent Definition**: Loaded from markdown frontmatter files (name, model, tools list, prompt)
4. **Skill Manifest**: Auto-discovered from `skills/` directory tree, formatted as markdown context
5. **Session**: Copilot SDK session created with custom tools, skill directories, and agent config
6. **Analysis**: Agent streams events; `StreamCollector` captures them; raw markdown parsed into `Report`
7. **Judging**: All reports + methodology compliance summaries sent to judge agent
8. **Evaluation**: Reports can be run through deterministic eval checks (`evals/`) to validate structural and semantic quality
9. **Output**: Winner report saved to `analysis/<org>/<repo>/<alert_id>/final-report.md`

## Connection Modes

The Copilot SDK client supports two modes configured via `COPILOT_CLI_URL`:
- **Native stdio** (default): Spawns the Copilot CLI as a subprocess, communicates via JSON-RPC over stdio
- **External server**: Connects to a running Copilot CLI server at the given URL (useful for development/debugging)

## Output Structure

Each run creates a workspace directory per analysis:

```
analysis/
  <org>/<repo>/<alert_id>/
    report-0.md              # Analysis 0 report
    report-1.md              # Analysis 1 report
    final-report.md          # Winner (copied from best)
    <uuid>/                  # Per-run workspace (run 0)
      report.md
      stream.log
      diagnostics.json       # Only with --show-usage
      scripts/               # Agent-created verification scripts
      logs/                  # Agent-created test output
      repo/                  # Cloned repository
    <uuid>/                  # Per-run workspace (run 1)
      ...
```

## Key Design Decisions

- **Pydantic everywhere**: All data models use Pydantic `BaseModel` with `Field` descriptions for validation and serialization
- **Config via pydantic-settings**: `Config` extends `BaseSettings`, loading from env vars with aliases
- **Optional fields for extensibility**: New tracking fields (skill_usage, tool_usage) are `Optional` to maintain backward compatibility
- **`--show-usage` gating**: Enhanced diagnostics (tool tracking, diagnostics.json, TUI tables) are gated behind a CLI flag to keep the default path lightweight
- **Skills as Copilot SDK skill directories**: Skills are registered as `skill_directories` in the session config, making them available via the SDK's built-in `skill` tool rather than implementing custom loading
- **Deterministic evals**: Report quality checks (`evals/`) are pure functions that validate structure, metadata, verdict coherence, and evidence quality without LLM involvement — enabling fast, repeatable quality gates
