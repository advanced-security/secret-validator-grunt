# Skills & Agents

## Skills System

### What Are Skills

Skills are markdown files (`SKILL.md`) containing structured methodology instructions. They are not code — they are expert guidance documents that the agent loads on-demand during a session via the Copilot SDK's built-in `skill` tool. Each skill covers a specific aspect of the validation methodology.

### Phase-Based Organization

Skills are organized into workflow phases that mirror the expected analysis sequence:

| Phase | Purpose | Skills |
|-------|---------|--------|
| `1-initialization` | Set up workspace and prerequisites | `testing-environment` (required), `github-api-usage` |
| `2-context-gathering` | Understand the codebase and secret context | `repository-acquisition` (required), `code-analysis` (required) |
| `3-verification` | Verify whether the secret is active | `deterministic-validation` (required), `http-basic-auth`, `internal-systems`, `_secret-type-template` |
| `4-scoring-and-reporting` | Score confidence and write report | `confidence-methodology` (required) |

### Required vs Optional Skills

Skills can be marked `required: true` in their frontmatter. Required skills define the core methodology — the agent must load them for a complete analysis. Optional skills provide additional context that may not apply to every alert (e.g., `http-basic-auth` is only relevant for HTTP Basic Auth secrets).

This distinction drives the **compliance score**: `(required skills loaded / total required skills) × 100%`. The judge receives this metric when evaluating reports.

### Skill Discovery

At runtime, `core/skills.py` scans the skills directory tree:
1. Finds all `SKILL.md` files (recursively)
2. Extracts YAML frontmatter (name, description, phase, required, secret-type)
3. Skips directories starting with `_` (these are templates/internal)
4. Builds a `SkillManifest` with all discovered skills
5. Formats the manifest as markdown context injected into the agent prompt

### Hidden/Disabled Skills

- Directories prefixed with `_` (e.g., `_secret-type-template/`) are discovered separately as "hidden skills" and added to the session's `disabled_skills` list
- Users can also disable skills via `config.disabled_skills`
- Hidden skills serve as templates for creating new secret-type-specific skills

### Adding New Skills

1. Create a directory under the appropriate phase: `skills/<phase>/<skill-name>/SKILL.md`
2. Add YAML frontmatter with at minimum `name`, `description`, and `phase`
3. Set `required: true` if the skill is mandatory for methodology compliance
4. Set `secret-type: <type>` if the skill is specific to a secret type
5. The skill will be auto-discovered on next run — no code changes needed

### How Skills Are Passed to Sessions

Skills are registered via `skill_directories` in the Copilot SDK session config. The SDK makes them available to the agent through its built-in `skill` tool. The agent calls `skill("skill-name")` to load the content. The manifest is also formatted as markdown and injected into the prompt so the agent knows what skills exist and which are required.

## Agents

### Agent Definition Format

Agents are defined in markdown files with YAML frontmatter:

```yaml
---
name: agent-name
description: What this agent does
tools: [list, of, allowed, tools]
model: model-name
---

# Agent prompt content goes here
The body is the agent's system prompt.
```

The `loaders/agents.py` module parses these files using `split_frontmatter()`, constructing an `AgentConfig` model. The config is then converted to a Copilot SDK `CustomAgentConfig` via `to_custom_agent()`.

### Analysis Agent

- **File**: `agents/secret_validator.agent.md`
- **Model**: Claude Opus 4.5
- **Role**: Security expert that researches the secret, writes verification scripts, and produces a structured report
- **Tools**: Full set — bash, file I/O, web search, GitHub API tools, validate_secret, skill
- **Methodology**: Defined by skills, not hardcoded in the prompt

### Judge Agent

- **File**: `agents/judge.agent.md`
- **Model**: Gemini 3 Pro Preview
- **Role**: Evaluator that compares multiple reports and selects the best one
- **Tools**: None (judge operates solely on the formatted reports it receives)
- **Output**: JSON with `winner_index`, per-report scores, rationale, and verdict
- **Note**: Also receives skill compliance summaries to penalize methodology-non-compliant agents

### Why Different Models

Using different models for analysis vs judging reduces correlation bias. If both used the same model, systematic blind spots would persist across evaluation. The judge model (Gemini) provides an independent perspective on the analysis model's (Claude) work.

## Custom Tools

Four custom tools are registered with each analysis session:

| Tool | Purpose |
|------|---------|
| `gh_secret_scanning_alert` | Fetches alert details (state, secret_type, locations_url) via GitHub API |
| `gh_secret_scanning_alert_locations` | Fetches where the secret appears in the repository |
| `validate_secret` | Runs deterministic validators from the `validate-secrets` library |
| `list_secret_validators` | Lists available secret type validators |

Tools follow a standard pattern: accept invocation params, validate inputs, call the underlying service, and return `ToolResult` with `textResultForLlm` for the agent and structured `data` for programmatic access. Failures return `resultType: "failure"` with a helpful error message.

## Prompts

Two prompt templates in `prompts/`:
- `analysis_task.md` — Base analysis prompt composed with context block + report template + skill manifest
- `judge_task.md` — Judge evaluation prompt with scoring criteria

The final prompt sent to the session is assembled in `_build_analysis_prompt()` (analysis) or `_build_judge_prompt()` (judge).
