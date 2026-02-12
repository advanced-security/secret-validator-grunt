# Development & Testing Guide

## Setup

```bash
uv venv
uv sync --extra dev
cp .env.example .env   # Set COPILOT_CLI_URL, GITHUB_TOKEN, etc.
```

## Running

```bash
# Basic run (3 analyses + judge)
uv run secret-validator-grunt org/repo alert_id

# Custom analysis count with diagnostics
uv run secret-validator-grunt org/repo alert_id --analyses 2 --show-usage

# Override timeouts
uv run secret-validator-grunt org/repo alert_id --timeout 900 --judge-timeout 120

# Stream verbose (shows raw deltas)
uv run secret-validator-grunt org/repo alert_id --stream-verbose
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_skill_usage.py -v

# Run specific test class/function
uv run pytest tests/test_tool_usage.py::TestToolUsageStats::test_success_rate_mixed -v
```

### Test Organization

Tests mirror the source structure. Each source module has a corresponding test file:

| Test File | Coverage |
|-----------|----------|
| `test_config.py` | Config model, env loading, validation, field defaults |
| `test_cli.py` | CLI entry point, argument parsing |
| `test_skill_usage.py` | SkillUsageStats, compliance score, phase tracking |
| `test_tool_usage.py` | ToolUsageStats, add_start/complete, success rates |
| `test_streaming_progress.py` | StreamCollector event handling, skill/tool tracking integration |
| `test_ui.py` | TUI rendering, table structure, show_usage gating |
| `test_tools.py` | Custom Copilot tools (GitHub API, validate_secret) |
| `test_skills.py` | Skill discovery, manifest building, hidden skill detection |
| `test_runner.py` | Orchestration integration (run_all) |
| `test_judge_prompt.py` | Judge prompt formatting, skill usage summaries |
| `test_judge_error_fallback.py` | Judge error handling and fallback behavior |
| `test_report_parser.py` | Report.from_markdown parsing |
| `test_report_parsing_tables.py` | Report table extraction edge cases |
| `test_agent_loader.py` | Agent definition loading from markdown frontmatter |
| `test_agent_loader_template.py` | Agent template loading |
| `test_templates_loader.py` | Report template loading |
| `test_run_params.py` | RunParams validation, slugification |
| `test_paths.py` | Path traversal guards |
| `test_copilot_client.py` | Client factory modes |
| `test_custom_agents.py` | AgentConfig → CustomAgentConfig conversion |
| `test_parsing.py` | JSON extraction from fenced blocks |
| `test_timeouts.py` | Analysis and judge timeout behavior |
| `test_reporting.py` | Report rendering and file persistence |
| `test_evals.py` | Eval checks, models, fixtures, orchestrator |

### Test Patterns

- **Async tests**: Use `@pytest.mark.asyncio` with `pytest-asyncio` in strict mode
- **Dummy objects**: Tests create inline dummy classes for `DummySession`, `DummyClient`, etc. — no shared fixtures for session mocks
- **Config construction**: Use `Config(SHOW_USAGE=True)` (the alias), not `Config(show_usage=True)` — pydantic-settings requires the alias for constructor kwargs
- **tmp_path**: Pytest's built-in `tmp_path` fixture for workspace isolation
- **No external calls**: All tests are offline; Copilot SDK sessions and GitHub API calls are mocked

### Test Conventions

- Tab indentation (matching project style)
- Test classes grouped by functionality (`TestToolCallEvent`, `TestToolUsageStats`, etc.)
- Descriptive docstrings on each test method explaining what is being verified
- Type hints on test methods (`def test_foo(self) -> None`)

## Formatting

```bash
uv run fmt          # Format code with yapf
uv run fmt-check    # Check formatting without modifying
```

The project uses tabs for indentation, consistent with `python.instructions.md`.

## Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COPILOT_CLI_URL` | None | External Copilot CLI server URL (omit for native stdio) |
| `COPILOT_MODEL` | Claude Sonnet 4.5 | Default model for sessions |
| `GITHUB_TOKEN` | None | GitHub PAT for secret scanning API |
| `ANALYSIS_COUNT` | 3 | Number of concurrent analyses |
| `ANALYSIS_TIMEOUT_SECONDS` | 1800 | Per-analysis timeout (seconds) |
| `JUDGE_TIMEOUT_SECONDS` | 300 | Judge session timeout (seconds) |
| `SHOW_USAGE` | False | Enable diagnostics tables and diagnostics.json |
| `STREAM_VERBOSE` | False | Stream raw deltas to console |
| `OUTPUT_DIR` | analysis | Base output directory |
| `LOG_LEVEL` | info | Log level for application |
| `AGENT_FILE` | (built-in path) | Path to analysis agent definition |
| `JUDGE_AGENT_FILE` | (built-in path) | Path to judge agent definition |
| `REPORT_TEMPLATE_FILE` | (built-in path) | Path to report template |
| `POLL_INTERVAL_SECONDS` | 5 | Polling interval (seconds) |
| `MAX_PARALLEL_SESSIONS` | None (=analysis_count) | Maximum parallel sessions |
| `VALIDATE_SECRET_TIMEOUT_SECONDS` | 30 | Timeout for secret validators |
| `SKILL_DIRECTORIES` | [] | Additional skill root directories |
| `DISABLED_SKILLS` | [] | Skills to disable at runtime |

## Dependencies

| Package | Purpose |
|---------|---------|
| `github-copilot-sdk` | Copilot SDK for agent sessions (JSON-RPC to Copilot CLI) |
| `pydantic` + `pydantic-settings` | Data models and env-based configuration |
| `typer` | CLI framework |
| `rich` | Terminal UI (Live display, tables) |
| `ghapi` | GitHub REST API client |
| `validate-secrets` | Deterministic secret validators (from `advanced-security`) |
| `pyyaml` | YAML frontmatter parsing |
| `python-dotenv` | `.env` file loading |
