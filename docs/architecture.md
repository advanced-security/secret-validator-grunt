# Architecture & Design

## What Is This Project

Secret Validator Grunt is an agentic framework that validates GitHub Secret Scanning alerts. It determines whether a detected secret is a **true positive** (real, active secret) or a **false positive** (inactive, test data, or non-secret). It does this by orchestrating multiple concurrent Copilot SDK agent sessions, each independently analyzing the alert, then using an LLM judge to select the best report.

## High-Level Flow

```
CLI invocation
  └─ main.py (Typer CLI) ─ parses args, loads Config
       └─ runner.py (run_all) ─ orchestrates everything
            ├─ pre_clone_repo() ─ clone repository once (shared)
            ├─ N × analysis.py (run_analysis) ─ concurrent agent sessions
            │     ├─ Copies pre-cloned repo into workspace
            │     ├─ Copilot SDK session with streaming
            │     ├─ Skills manifest injected as context
            │     ├─ Custom tools (GitHub API, validate_secret)
            │     ├─ StreamCollector captures events + tracks usage
            │     ├─ Continuation prompts on early termination
            │     └─ Report parsed from agent markdown output
            ├─ N × challenge.py (run_single_challenge) ─ adversarial validation
            │     ├─ Inspects analysis workspace (scripts, logs, artifacts)
            │     ├─ Re-runs verification scripts to confirm evidence
            │     ├─ Returns CONFIRMED / REFUTED / INSUFFICIENT_EVIDENCE
            │     └─ Challenge results annotated on each AgentRunResult
            ├─ judge.py (run_judge) ─ evaluates all reports + challenge results
            │     ├─ Reports + skill compliance + challenge annotations
            │     └─ Returns JSON with winner_index + scores
            └─ RunOutcome ─ final result passed to TUI for display
```

## Core Concepts

### Multi-Agent Consensus

Rather than trusting a single agent run, the system runs N analyses (default 3) concurrently. Each agent independently researches the secret, writes verification scripts, and produces a structured report. After analysis, an adversarial challenger agent independently challenges each report by inspecting the workspace, re-running verification scripts, and cross-checking evidence claims. Finally, a judge agent compares all reports — along with their challenge results — and selects the most complete and well-evidenced one. This three-stage pipeline (analysis → challenge → judge) reduces variance and catches both individual agent mistakes and fabricated evidence.

### Pre-Clone Repository Strategy

The repository under analysis is cloned once to a shared location (`_shared_repo/`) before any analyses begin. Each analysis agent receives a `shutil.copytree` copy in its workspace, avoiding N redundant git clones. Agent instructions explicitly state "DO NOT clone the repository again — it is ready to use." If the pre-clone fails, agents fall back to cloning individually.

### Adversarial Challenge

After all analyses complete, each report is independently challenged by an adversarial agent. The challenger inspects the analysis workspace (scripts, logs, artifacts, cloned repo), re-runs verification scripts, and cross-checks evidence claims against actual workspace contents. Challenge verdicts are:
- **CONFIRMED** — Evidence is genuine and consistent with the report's claims
- **REFUTED** — Key evidence is demonstrably wrong or fabricated
- **INSUFFICIENT_EVIDENCE** — Cannot determine; not enough information to challenge

Challenge results are annotated on each `AgentRunResult` and included in the judge's input.

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
4. **Skill Manifest**: Auto-discovered from `skills/<agent-type>/` directory tree, formatted as markdown context
5. **Pre-clone**: Repository cloned once to `_shared_repo/`; each analysis workspace receives a `shutil.copytree` copy
6. **Session**: Copilot SDK session created with custom tools, skill directories, and agent config
7. **Analysis**: Agent streams events; `StreamCollector` captures them; continuation prompts sent if response is too short; raw markdown parsed into `Report`
8. **Challenge**: Each analysis report is challenged by an adversarial agent that inspects the workspace, re-runs scripts, and returns a `ChallengeResult` (CONFIRMED / REFUTED / INSUFFICIENT_EVIDENCE)
9. **Judging**: All reports + methodology compliance summaries + challenge annotations sent to judge agent
10. **Evaluation**: Reports can be run through deterministic eval checks (`evals/`) to validate structural and semantic quality
11. **Output**: Winner report saved to `analysis/<org>/<repo>/<alert_id>/final-report.md`

## Connection Modes

The Copilot SDK client supports two modes configured via `COPILOT_CLI_URL`:
- **Native stdio** (default): Spawns the Copilot CLI as a subprocess, communicates via JSON-RPC over stdio
- **External server**: Connects to a running Copilot CLI server at the given URL (useful for development/debugging)

### Token Configuration

Two separate tokens can be configured for different concerns:
- **`GITHUB_TOKEN`** — Used for GitHub REST API calls (secret scanning alerts, locations) and authenticated git clones. Required for all modes.
- **`COPILOT_TOKEN`** — Used for Copilot CLI authentication in native stdio mode. If unset, falls back to `GITHUB_TOKEN`. Ignored in external server mode (the server manages its own auth).

## Output Structure

Each run creates a workspace directory per analysis:

```
analysis/
  _shared_repo/              # Pre-cloned repository (shared source)
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
      repo/                  # Copied from _shared_repo/
    <uuid>/                  # Per-run workspace (run 1)
      ...
    challenge-0/             # Challenge workspace (run 0)
      stream.log
      diagnostics.json       # Only with --show-usage
    challenge-1/             # Challenge workspace (run 1)
      ...
```

## Security

### Credential Masking

All log output is automatically sanitized by a `TokenSanitizingFilter` installed on the root logger during `configure_logging()`. The filter redacts credentials embedded in git-style URLs (e.g., `https://user:TOKEN@host`) by replacing the token portion with `***`. This runs transparently — no call-site awareness is required. A standalone `sanitize_text()` function is also available for non-logging use cases.

## Key Design Decisions

- **Pydantic everywhere**: All data models use Pydantic `BaseModel` with `Field` descriptions for validation and serialization
- **Config via pydantic-settings**: `Config` extends `BaseSettings`, loading from env vars with aliases
- **Optional fields for extensibility**: New tracking fields (skill_usage, tool_usage) are `Optional` to maintain backward compatibility
- **`--show-usage` gating**: Enhanced diagnostics (tool tracking, diagnostics.json, TUI tables) are gated behind a CLI flag to keep the default path lightweight
- **Skills as Copilot SDK skill directories**: Skills are registered as `skill_directories` in the session config, making them available via the SDK's built-in `skill` tool rather than implementing custom loading
- **Deterministic evals**: Report quality checks (`evals/`) are pure functions that validate structure, metadata, verdict coherence, and evidence quality without LLM involvement — enabling fast, repeatable quality gates
- **Pre-clone repository**: The repo is cloned once and copied to each workspace, avoiding N redundant `git clone` operations and reducing API pressure
- **Continuation prompts**: When an agent's response is shorter than `MIN_RESPONSE_LENGTH`, the session sends a continuation prompt (up to `MAX_CONTINUATION_ATTEMPTS` times) to recover from early model termination — all within the same session to preserve context
- **Adversarial challenge stage**: An independent challenger agent validates each report's evidence by inspecting the analysis workspace, re-running scripts, and cross-checking claims. Challenge results are annotations, not vetos — the judge makes the final call
- **Per-agent skill directories**: Skills are organized by agent type (`skills/analysis/`, `skills/challenger/`, `skills/judge/`) and auto-discovered via `discover_skill_directories_for_agent()`. Adding skills for a new agent type requires only a directory and SKILL.md — no code changes
