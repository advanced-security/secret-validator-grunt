---
description: "Project-specific conventions, architecture context, and implementation workflow for secret-validator-grunt"
applyTo: "**"
---

# Secret-Validator-Grunt — Agent Instructions

## Project Identity

This is a Python CLI tool that validates GitHub secret scanning alerts using AI-driven multi-agent consensus. It uses the **GitHub Copilot SDK** (`github-copilot-sdk`) to run Copilot sessions over JSON-RPC.

Entry point: `main.py:entrypoint()` → Typer CLI → `core/runner.py:run_all()`.

## Architecture at a Glance

- **N parallel analysis agents** examine a secret alert independently (default 3)
- A **judge agent** reviews all analysis reports and selects the best one
- Each analysis runs in its own Copilot session with tools and skills injected
- Results flow through `StreamCollector` which captures events, usage, and tool calls
- The TUI (Rich Live) renders real-time progress and a final summary

Key data flow: `CLI → Config → runner.run_all → analysis × N + judge → RunOutcome → TUI`

## Directory Structure Convention

```
src/secret_validator_grunt/
  core/        # Orchestration: runner, analysis, judge, skills
  evals/       # Deterministic report evaluation checks
  integrations/# External tools: copilot_tools, custom_agents, github
  loaders/     # File loaders: agents, prompts, templates, frontmatter
  models/      # Pydantic models, one class per file
  skills/      # Phase-organized markdown skill files
  agents/      # Agent definition markdown files
  prompts/     # Prompt template markdown files
  templates/   # Report template files
  ui/          # TUI display, streaming event handler, reporting
  utils/       # Parsing, paths, logging, protocols
```

This structure was migrated from a flat `services/` directory. The `services/` directory has been fully removed — do NOT recreate it.

## Critical Config Gotcha

`Config` uses `pydantic_settings.BaseSettings` with **alias-based env var names**. When constructing Config in code or tests, you MUST use the alias (the env var name), NOT the field name:

```python
# ✅ Correct — alias name
Config(SHOW_USAGE=True, ANALYSIS_COUNT=5)

# ❌ Wrong — field name. Silently ignored, keeps default.
Config(show_usage=True, analysis_count=5)
```

This is the single most common source of subtle test bugs in this project.

## Implementation Workflow

Every non-trivial feature follows this proven workflow (derived from `.logs/` learnings):

1. **Proposal first** — Write a proposal document describing the problem, design, integration points, and testing strategy. Get approval before coding.
2. **Pre-flight checks** — Run the existing test suite to establish a baseline count. Record it.
3. **Phased implementation** — Break work into 4–6 phases, low-risk first. Each phase should be independently testable.
4. **Test after each phase** — Run the full test suite after completing each phase. Record the new count. Never proceed to the next phase with failures.
5. **Post-implementation review** — Re-read all modified files from first principles. Look for: mutation of third-party objects, missing edge-case tests, error handling that swallows valid results.
6. **Final summary** — Document what was done, files changed, test counts before/after.

### Why This Workflow Matters

The post-implementation review step has caught real bugs:
- `_import_registry()` was mutating a third-party module's namespace (validate-secrets). Refactored to a clean wrapper.
- Error handling in `validate_secret_tool` swallowed a valid `check()` result when `get_metadata()` failed. Separated the try/except blocks.
- Missing test for `Checker.check()` returning `None` (the third possible return value).

## Code Conventions

- **Indentation**: 1 tab per level (NOT spaces). The project uses tabs throughout.
- **Type hints**: Required on all function signatures.
- **Docstrings**: PEP 257, immediately after `def`/`class`.
- **One class per file** in `models/` unless classes are tightly coupled.
- **Pydantic**: All data models inherit `BaseModel`. Use `Field(description=...)` for documentation.
- **Async**: All I/O-bound operations (Copilot sessions, file writes in analysis) are async.
- **Imports**: Use absolute imports from `secret_validator_grunt.*`. No relative imports.

## Testing Conventions

- Framework: `pytest` + `pytest-asyncio` (strict mode — must mark async tests with `@pytest.mark.asyncio`)
- Test files: `tests/test_<module>.py`
- Run: `uv run pytest tests/ -q`
- **Inline dummy objects** preferred over complex mock hierarchies
- Use `tmp_path` fixture for file system tests
- Config in tests: always use alias names (see Config Gotcha above)
- Current baseline: **214 tests**

## Skills System

Skills are markdown files organized into workflow phases under `skills/`:

```
1-initialization/      # API setup, authentication
2-context-gathering/   # Repository cloning, code scanning
3-verification/        # Testing, validation, deterministic checks
4-scoring-and-reporting/ # Confidence scoring methodology
custom/                # Organization-specific extensions
```

Each skill has a `SKILL.md` with YAML frontmatter (`required: true/false`, `hidden: true`). The manifest generator (`core/skills.py`) auto-discovers all skills at startup.

To add a new skill: create `skills/<phase>/<name>/SKILL.md` with frontmatter and content. It is automatically discovered — no code changes needed.

## Adding New Features — Checklist

1. Does it need a new model? → Create in `models/`, export from `__init__.py`
2. Does it need gating? → Follow the `--show-usage` pattern: add a Config field with alias, gate all new behavior behind it
3. Does it touch streaming? → Update `StreamCollector` handler in `ui/streaming.py`
4. Does it need TUI output? → Add a render method in `ui/tui.py`, gate behind the appropriate flag
5. Does it persist data? → Write to the per-run workspace dir (see `utils/paths.py:ensure_within`)
6. Does it touch report format? → Update eval fixtures (see Eval System below)
7. Write tests as you go, not after

## What Works Well (Lessons Learned)

- **Phased implementation with test checkpoints** catches integration issues early
- **Pre-flight baseline** makes regressions immediately visible
- **`--show-usage` gating pattern** keeps new diagnostic features from affecting default behavior
- **Dynamic skill manifest** eliminated the need to manually register skills
- **Phase-based skill organization** made skill discovery intuitive for agents
- **Post-implementation first-principles review** catches bugs that unit tests miss

## Eval System

The `evals/` module provides deterministic checks that validate the structural and semantic quality of agent-generated reports. Checks are pure functions `(Report) -> EvalCheck`, composed via `run_all_checks()`.

### Eval Fixture Maintenance

Eval tests run against sample report fixtures in `tests/fixtures/reports/`. Each fixture is a pair:
- `<name>.md` — a real or synthetic report markdown
- `<name>.json` — expected metadata (verdict, score range, expected failures)

**If you change the report template (`templates/`) or the `Report.from_markdown()` parser, you MUST update the eval fixtures to match.** Fixtures prefixed with `bad-` are intentionally malformed. All other fixtures are expected to pass all error-severity checks.

To add a new fixture: create both the `.md` and `.json` files. It is automatically discovered by parameterized tests — no code changes needed.

### Adding a New Eval Check

1. Write the check function in `evals/checks.py`: `(Report) -> EvalCheck`
2. Add it to the `ALL_CHECKS` list (order does not matter)
3. Export it from `evals/__init__.py`
4. Add a test class in `tests/test_evals.py`
5. Verify existing fixtures still pass — new checks may need fixture updates

### Confidence Label Boundaries

Label boundaries are defined in `_score_to_label()` with exclusive upper bounds for lower tiers:
- **High:** score >= 7.0
- **Medium:** 4.0 <= score < 7.0
- **Low:** score < 4.0

Do NOT use overlapping ranges or dict-based lookups for boundaries — use explicit `if/elif` chains to avoid ordering ambiguity.

## What to Avoid

- Do NOT mutate third-party module namespaces (monkey-patching attributes onto imported modules)
- Do NOT put models in the wrong directory (e.g., don't put data models in `core/` or `integrations/`)
- Do NOT use field names when constructing Config — always use aliases
- Do NOT add code to `services/` — it was removed during refactoring
- Do NOT skip the test-after-each-phase step. This is how regressions are caught early.
- Do NOT use `dataclass` for new models — use Pydantic `BaseModel` exclusively
- Do NOT use `typing.List`, `typing.Dict`, `typing.Tuple` etc. when `from __future__ import annotations` is present — use built-in generics (`list`, `dict`, `tuple`) and `X | None` instead of `Optional[X]`
- Do NOT use overlapping numeric ranges in dicts for boundary logic — use explicit `if/elif` chains
- Do NOT use unanchored regex for file path detection that matches bare numbers (e.g. `6.7`) — require alphabetic lead-in or backtick quoting

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `github-copilot-sdk` | Copilot session management via JSON-RPC |
| `ghapi` | GitHub REST API client |
| `validate-secrets` | Deterministic secret validators (optional) |
| `rich` | Terminal UI rendering |
| `typer` | CLI framework |
| `pydantic` / `pydantic-settings` | Data models and config |
| `python-dotenv` | `.env` file loading |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `COPILOT_CLI_URL` | None | External Copilot CLI server URL |
| `COPILOT_MODEL` | Claude Sonnet 4.5 | Model for analysis sessions |
| `ANALYSIS_COUNT` | 3 | Parallel analysis count |
| `ANALYSIS_TIMEOUT_SECONDS` | 1800 | Per-analysis timeout (seconds) |
| `JUDGE_TIMEOUT_SECONDS` | 300 | Judge session timeout (seconds) |
| `SHOW_USAGE` | false | Enable diagnostics display and persistence |
| `GITHUB_TOKEN` | None | GitHub API authentication |
| `STREAM_VERBOSE` | false | Stream raw deltas to console |
| `OUTPUT_DIR` | analysis | Base output directory |

## Reference

Deeper documentation lives in `docs/`:
- `docs/architecture.md` — Design philosophy and data flow
- `docs/code-structure.md` — Module-by-module breakdown
- `docs/skills-and-agents.md` — Skills, agents, tools, prompts
- `docs/diagnostics.md` — Usage/skill/tool tracking and `--show-usage`
- `docs/development.md` — Setup, running, testing, formatting
