---
description: "Project-specific conventions, architecture context, and implementation workflow for secret-validator-grunt"
applyTo: "**"
---

# Secret-Validator-Grunt — Agent Instructions

## Project Identity

This is a Python CLI tool that investigates GitHub secret scanning alerts using independent analyses, adversarial challenges, and judge selection, not a majority vote. It uses the **GitHub Copilot SDK** (`github-copilot-sdk`) to run Copilot sessions over JSON-RPC.

Entry point: `main.py:entrypoint()` → Typer CLI → `core/runner.py:run_all()`.

## Quick Onboarding

Paths such as `core/` and `models/` below are relative to `src/secret_validator_grunt/`.

1. Read `README.md`, then `docs/architecture.md` for the workflow and its limits.
2. Use `docs/code-structure.md` to find the owning module and companion tests; follow only the path relevant to the task.
3. Read `models/config.py` for recognized settings and `agents/*.agent.md` for effective models/tools. Agent model overrides take precedence over `COPILOT_MODEL`; `.env.example` values are examples, not defaults.
4. Use `docs/development.md` for setup and checks. Run `uv run --extra dev pytest tests/ -q`; format with `uv run fmt` and check with `uv run fmt-check`.

These are developer instructions. Application-created stage sessions skip repository custom instructions; change `agents/`, `prompts/`, and `skills/` to change their methodology. Read `docs/operational-risks.md` before any live validation.

## Architecture at a Glance

- **Pre-clone**: Prepare `_shared_repo/`; each analysis workspace receives a copy. An existing shared clone is reused, not automatically refreshed
- **N parallel analysis agents** examine a secret alert independently (default 3)
- **N parallel challenger agents** inspect original evidence read-only and rerun checks in separate working copies
- A **judge agent** reviews all analysis reports with challenge annotations and selects the best one
- Each stage gets its own Copilot session and agent definition; the default judge has `tools: []` and no skill directories
- Analysis sessions use bounded continuation prompts for short or empty responses; challenger and judge calls currently do not
- One `integrations/github_evidence.py:GitHubEvidence` instance shares GitHub reads within a run; live provider checks are never cached
- `core/challenge_workspace.py` protects `scripts/`, `logs/`, `artifacts/`, and `report.md`; integrity failures force `INSUFFICIENT_EVIDENCE`. The repository and runtime environments are outside that protection, which is not a sandbox
- Results flow through `StreamCollector` which captures events, usage, and tool calls
- The TUI (Rich Live) renders real-time progress (3 tables: analysis, challenger, judge) and a final summary; logging must use the same Rich console to avoid corrupting redraws

Key data flow: `CLI → Config → runner.run_all → pre_clone → analysis × N → challenge × N → judge → RunOutcome → TUI`

## Directory Structure Convention

```
src/secret_validator_grunt/
  core/        # Orchestration: runner, analysis, challenge, judge, session, skills
  evals/       # Deterministic report evaluation checks
  integrations/# External tools: copilot_tools, custom_agents, github
  loaders/     # File loaders: agents, prompts, templates, frontmatter
  models/      # Pydantic models, one class per file
  skills/      # Per-agent skill directories (analysis/, challenger/, judge/)
  agents/      # Agent definition markdown files (3 agents)
  prompts/     # Prompt template markdown files (4 prompts)
  templates/   # Report template files
  ui/          # TUI display (3 tables), streaming event handler, reporting
  utils/       # Parsing, paths, logging, protocols
```

This structure was migrated from a flat `services/` directory. The `services/` directory has been fully removed — do NOT recreate it.

## Critical Config Gotcha

`Config` uses `pydantic_settings.BaseSettings` with **alias-based env var names**. Use the aliases when constructing Config in new code or tests so settings match their documented environment names:

```python
# ✅ Correct — alias name
Config(SHOW_USAGE=True, ANALYSIS_COUNT=5)

# Avoid — field names obscure the environment-variable mapping.
Config(show_usage=True, analysis_count=5)
```

Current dependency versions accept field names too; the former warning that they are silently ignored is outdated. Alias-based construction remains the project convention. Use `models/config.py` as the source of truth rather than guessing setting names.

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

These project-specific rules take precedence over generic Python examples. They apply to new or changed code; existing legacy code is not proof of a different convention.

- **Indentation**: 1 tab per level (NOT spaces). The project uses tabs throughout.
- **Type hints**: Required on all function signatures.
- **Docstrings**: PEP 257, immediately after `def`/`class`.
- **One class per file** in `models/` unless classes are tightly coupled.
- **Pydantic**: New data models inherit `BaseModel`. Use `Field(description=...)` for documentation.
- **Async**: Keep blocking I/O off the event loop. Follow the existing async session calls and `asyncio.to_thread` boundaries for blocking GitHub reads and evidence copying.
- **Imports**: Use absolute imports from `secret_validator_grunt.*`. No relative imports.

## Testing Conventions

- Framework: `pytest` + `pytest-asyncio` (strict mode — must mark async tests with `@pytest.mark.asyncio`)
- Test files: `tests/test_<module>.py`
- Run: `uv run --extra dev pytest tests/ -q`
- **Inline dummy objects** preferred over complex mock hierarchies
- Use `tmp_path` fixture for file system tests
- Config in tests: always use alias names (see Config Gotcha above)
- Last verified baseline: **576 passed (2026-10-16)**. Measure a fresh baseline before implementation; this count is not an invariant.
- For selected files, use `uv run fmt --in-place <files>` and `uv run fmt-check --diff <files>`; explicit arguments replace the formatter wrapper's defaults.

## Skills System

Skills are markdown files organized **per-agent** under `skills/`. Each agent type has its own skill directory:

```
skills/
  analysis/              # Analysis agent — workflow phases
    1-initialization/    #   API setup, authentication
    2-context-gathering/ #   Repository cloning, code scanning
    3-verification/      #   Testing, validation, deterministic checks
    4-scoring-and-reporting/ # Confidence scoring methodology
    custom/              #   Organization-specific extensions
  challenger/            # Challenger agent skills
    false-indicator-recognition/
    rotation-and-revocation-analysis/
    secret-verification-methodology/
  judge/                 # Judge agent skills (empty — .gitkeep)
```

Each skill has a `SKILL.md` with YAML frontmatter: `name` and `description` are required; `required`, `phase`, `agent`, and `secret-type` describe its use. The manifest generator (`core/skills.py`) auto-discovers skills per-agent at startup via `discover_skill_directories_for_agent(agent_type)`.

For analysis and challenger sessions, enabled required skill bodies are embedded in the task prompt in phase order. Optional guides are listed for on-demand use. `DISABLED_SKILLS` excludes named guides; entries under `_` and `.` directories within scanned skill roots are excluded from the manifest. `hidden: true` alone is not an app-level disabling switch, and there is no `PRELOAD_REQUIRED_SKILLS` setting.

The default judge has no tools or skills; change its agent definition and task prompt for judge guidance. Guidance coverage records delivery/loading, not compliance. Use `docs/skills-and-agents.md` for a complete skill example and the custom tool contracts.

Valid agent types: `analysis`, `challenger`, `judge`.

To add a new analysis skill: create `skills/analysis/<phase>/<name>/SKILL.md` with frontmatter. Auto-discovered.

To add a new skill for another agent: create `skills/<agent-type>/<name>/SKILL.md`. Auto-discovered.

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
- **Per-agent skill directories** made skill discovery intuitive and extensible for new agent types
- **Post-implementation first-principles review** catches bugs that unit tests miss
- **Pre-cloned repo strategy** — Clone once, copy to each workspace. Agent instructions say "DO NOT clone again".
- **Continuation prompts for empty responses** — Instead of failing on early model termination, send a continuation prompt within the same session to recover context
- **Adversarial challenge stage** — An independent challenger that validates evidence catches fabricated or misleading reports that the judge alone might miss

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
- Reuse `integrations/github.py` for GitHub reads: ghapi 2.x uses `sync=True` here, and nested fastcore collections must be normalized with `obj2dict` before JSON serialization
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
| `ghapi` | GitHub REST API client (2.x, used with `sync=True`) |
| `validate-secrets` | Installed by default; deterministic validators for supported secret types, not every provider |
| `rich` | Terminal UI rendering |
| `typer` | CLI framework |
| `pydantic` / `pydantic-settings` | Data models and config |
| `python-dotenv` | `.env` file loading |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `COPILOT_CLI_URL` | None | External Copilot CLI server URL |
| `COPILOT_MODEL` | claude-sonnet-5.5 | Fallback model when the stage's agent definition does not specify one |
| `ANALYSIS_COUNT` | 3 | Parallel analysis count |
| `MAX_PARALLEL_SESSIONS` | None | Limit concurrent analysis or challenger sessions within a stage |
| `ANALYSIS_TIMEOUT_SECONDS` | 1800 | Per-analysis timeout (seconds) |
| `JUDGE_TIMEOUT_SECONDS` | 300 | Judge session timeout (seconds) |
| `CHALLENGER_TIMEOUT_SECONDS` | 300 | Per-challenge timeout (seconds) |
| `CHALLENGER_AGENT_FILE` | agents/challenger.agent.md | Challenger agent definition path |
| `CHALLENGER_SKILL_DIRECTORIES` | [] | Additional challenger skill root directories |
| `ANALYSIS_SKILL_DIRECTORIES` | [] | Additional analysis skill roots; `SKILL_DIRECTORIES` is a legacy alias |
| `DISABLED_SKILLS` | [] | Skill names excluded from guidance and runtime loading |
| `MAX_CONTINUATION_ATTEMPTS` | 2 | Max continuation prompts per analysis session |
| `MIN_RESPONSE_LENGTH` | 500 | Minimum analysis response length before triggering continuation |
| `SHOW_USAGE` | false | Enable diagnostics display and persistence |
| `GITHUB_TOKEN` | None | GitHub API authentication and git clone auth |
| `COPILOT_TOKEN` | None | Copilot CLI authentication (falls back to GITHUB_TOKEN) |
| `STREAM_VERBOSE` | false | Show detailed streaming updates in the TUI |
| `OUTPUT_DIR` | analysis | Base output directory |

## Reference

Deeper documentation lives in `docs/`:
- `docs/README.md` — Onboarding reading order and guide index
- `docs/architecture.md` — Design philosophy and data flow
- `docs/code-structure.md` — Module-by-module breakdown
- `docs/skills-and-agents.md` — Skills, agents, tools, prompts
- `docs/diagnostics.md` — Usage/skill/tool tracking and `--show-usage`
- `docs/development.md` — Setup, running, testing, formatting
