# Diagnostics & Observability

## Usage Tracking

### Token & Cost Tracking (`UsageStats`)

Every session accumulates token usage through `StreamCollector`. The SDK emits `ASSISTANT_USAGE` and `SESSION_USAGE_INFO` events which are merged into a `UsageStats` model tracking:
- Input/output tokens per turn and total
- Cache read/write tokens
- Cost (if reported by the SDK)
- Duration
- Quota snapshots (requests consumed per tier)

This data is always collected but only displayed with the `--show-usage` flag.

### Skill Usage Tracking (`SkillUsageStats`)

Tracks which skills the agent loaded during a session. Always active (not gated by `--show-usage`), because the judge needs compliance data regardless.

**How it works**: `StreamCollector` intercepts `TOOL_EXECUTION_START` events where `tool_name == "skill"`, extracts the skill name from `arguments.skill`, stores the pending call ID, then matches it to the corresponding `TOOL_EXECUTION_COMPLETE` event. Each completed call becomes a `SkillLoadEvent` recording: skill name, status, phase, whether it was required, duration, and any error message.

**Key metrics**:
- `compliance_score` — Percentage of required skills loaded (0–100%)
- `loaded_by_phase()` — Skills grouped by their workflow phase
- `available_by_phase()` — All available skills grouped by phase (uses `phase_map`)
- `skipped_required` — Required skills the agent did not load (populated by `finalize()`)

### Tool Usage Tracking (`ToolUsageStats`)

Tracks all tool calls (not just skills) with success/failure and duration. **Gated by `--show-usage`** — when the flag is off, `_tool_usage` is `None` and no tool call data is recorded.

**How it works**: For every `TOOL_EXECUTION_START`, `add_start(tool_call_id, tool_name)` stores the call in `_pending` with a timestamp. On `TOOL_EXECUTION_COMPLETE`, `add_complete(tool_call_id, success, error)` pops the pending entry, computes duration, and appends a `ToolCallEvent`.

**Key metrics**:
- `total_calls`, `successful_calls`, `failed_calls`, `success_rate`
- `calls_by_tool()` — Per-tool breakdown with `ToolCallSummary`
- `top_tools(limit=5)` — Most-called tools sorted by count

## The `--show-usage` Flag

This flag gates enhanced diagnostics output. When active:

1. **Tool tracking** is enabled in `StreamCollector`
2. **TUI tables** for skill usage, tool usage, and token usage are displayed in `print_summary()`
3. **`diagnostics.json`** is written per run in the workspace directory

When off (the default), only skill tracking runs (because the judge needs it), and the TUI shows only the winner report and judge decision.

## Diagnostics File

When `--show-usage` is active, each analysis run writes `diagnostics.json` to its workspace:

```json
{
  "run_id": "0",
  "skill_usage": { ... },   // SkillUsageStats.model_dump()
  "tool_usage": { ... },    // ToolUsageStats.model_dump() or null
  "usage": { ... }          // UsageStats.model_dump()
}
```

This file lives alongside the report and stream log in the per-run UUID directory. Challenger sessions also write diagnostics to `challenge-{i}/diagnostics.json`. It replaces the need to parse raw `events.jsonl` from the Copilot session state directory.

## TUI Display

The `TUI` class uses Rich `Live` display with auto-refresh during execution:

**During runs**: Grid of three tables showing real-time status:
- **Analysis table** — N analysis cells with workspace path, latest messages, and outcome data (verdict, confidence, risk level) as they become available
- **Challenger table** — N challenge cells showing challenge verdict (CONFIRMED / REFUTED / INSUFFICIENT_EVIDENCE) as each completes
- **Judge table** — Judge cell with winner selection and rationale

**After completion** (`print_summary()`):
- Winner report table (verdict, confidence, risk, key finding)
- Judge decision table (winner, rationale)
- All workspace paths
- With `--show-usage`:
  - Usage table (tokens, requests, duration per run + challenger runs + judge + totals)
  - Skill usage table (skills loaded, by phase breakdown, required count, compliance %)
  - Tool usage table (total, success, failed, rate, top tools per run)

## Logging

Module-level loggers via `utils/logging.py`. `configure_logging()` sets up the root logger with a standard format and installs a `TokenSanitizingFilter` that automatically redacts credentials embedded in git-style URLs (e.g., `https://user:TOKEN@host` → `https://user:***@host`). This filter runs on all log records transparently — no call-site awareness is required. A standalone `sanitize_text()` function is also exported for non-logging use cases.

### Key log points

- Analysis start/complete with org_repo and alert_id
- Skill tracking events (debug level)
- Tool execution events (when verbose)
- Parse errors for reports and agent definitions
- Diagnostics file write failures (debug level, non-fatal)

Stream logs are written per-run to `<workspace>/stream.log` capturing the raw streaming output.
