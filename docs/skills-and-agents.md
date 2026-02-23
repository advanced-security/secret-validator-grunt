# Skills & Agents

## Skills System

### What Are Skills

Skills are markdown files (`SKILL.md`) containing structured methodology instructions. They are not code — they are expert guidance documents that the agent loads on-demand during a session via the Copilot SDK's built-in `skill` tool. Each skill covers a specific aspect of the validation methodology.

### Per-Agent Skill Organization

Skills are organized **per-agent** under `skills/`. Each agent type has its own skill directory:

```
skills/
  analysis/              # Analysis agent — workflow phases
    1-initialization/
    2-context-gathering/
    3-verification/
    4-scoring-and-reporting/
    custom/              # User-extensible analysis skill directory
  challenger/            # Challenger agent skills
    false-indicator-recognition/
    rotation-and-revocation-analysis/
    secret-verification-methodology/
  judge/                 # Judge agent skills (empty — .gitkeep)
```

#### Analysis Agent Skills (by Phase)

| Phase | Purpose | Skills |
|-------|---------|--------|
| `1-initialization` | Set up workspace and prerequisites | `testing-environment` (required), `github-api-usage` |
| `2-context-gathering` | Understand the codebase and secret context | `repository-acquisition` (required), `code-analysis` (required) |
| `3-verification` | Verify whether the secret is active | `deterministic-validation` (required), `http-basic-auth`, `internal-systems`, `_secret-type-template` |
| `4-scoring-and-reporting` | Score confidence and write report | `confidence-methodology` (required) |

#### Challenger Agent Skills

| Skill | Purpose |
|-------|---------|
| `false-indicator-recognition` | Patterns that indicate secrets are test/dummy/deactivated |
| `rotation-and-revocation-analysis` | Evaluating whether secrets have been rotated or revoked |
| `secret-verification-methodology` | Proper secret verification approaches |

Skill discovery is agent-aware: `discover_skill_directories_for_agent(agent_type)` returns only the skills for the requested agent type. Valid agent types: `analysis`, `challenger`, `judge`.

### Required vs Optional Skills

Skills can be marked `required: true` in their frontmatter. Required skills define the core methodology — the agent must load them for a complete analysis. Optional skills provide additional context that may not apply to every alert (e.g., `http-basic-auth` is only relevant for HTTP Basic Auth secrets).

This distinction drives the **compliance score**: `(required skills loaded / total required skills) × 100%`. The judge receives this metric when evaluating reports.

### Skill Discovery

At runtime, `core/skills.py` scans per-agent skill directory trees:
1. `discover_skill_directories_for_agent(agent_type)` finds the subdirectory for the given agent type (e.g., `skills/analysis/`)
2. Finds all `SKILL.md` files recursively within that directory
3. Extracts YAML frontmatter (name, description, phase, required, secret-type)
4. Skips directories starting with `_` (these are templates/internal)
5. Builds a `SkillManifest` with all discovered skills
6. Formats the manifest as markdown context injected into the agent prompt
7. Includes any additional skill directories configured per-agent (e.g., `SKILL_DIRECTORIES`, `CHALLENGER_SKILL_DIRECTORIES`)

Convenience wrappers: `discover_skill_directories()` for analysis, `discover_challenger_skill_directories()` for challenger.

### Hidden/Disabled Skills

- Directories prefixed with `_` (e.g., `_secret-type-template/`) are discovered separately as "hidden skills" and added to the session's `disabled_skills` list
- Users can also disable skills via `config.disabled_skills`
- Hidden skills serve as templates for creating new secret-type-specific skills

### Adding New Skills

**Analysis skills:**
1. Create a directory under the appropriate phase: `skills/analysis/<phase>/<skill-name>/SKILL.md`
2. Add YAML frontmatter with at minimum `name`, `description`, and `phase`
3. Set `required: true` if the skill is mandatory for methodology compliance
4. Set `secret-type: <type>` if the skill is specific to a secret type
5. The skill will be auto-discovered on next run — no code changes needed

**Challenger or judge skills:**
1. Create a directory: `skills/<agent-type>/<skill-name>/SKILL.md`
2. Add YAML frontmatter with `name`, `description`, and `agent: <agent-type>`
3. Auto-discovered — no code changes needed

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
- **Workspace**: Receives a copy of the pre-cloned repository; agent instructions say "DO NOT clone again"

### Challenger Agent

- **File**: `agents/challenger.agent.md`
- **Model**: GPT-5.2 Codex
- **Role**: Adversarial validator that independently challenges each analysis report by inspecting the workspace, re-running scripts, and cross-checking evidence claims
- **Tools**: bash, file I/O, GitHub API tools, validate_secret, skill
- **Output**: JSON with `verdict` (CONFIRMED / REFUTED / INSUFFICIENT_EVIDENCE), `reasoning`, `evidence_gaps`, `verification_reproduced`, `verification_result`, `contradicting_evidence`
- **Workspace**: Has read access to the analysis workspace (scripts, logs, cloned repo)
- **Skills**: 3 challenger-specific skills (false-indicator-recognition, rotation-and-revocation-analysis, secret-verification-methodology)

### Judge Agent

- **File**: `agents/judge.agent.md`
- **Model**: Gemini 3 Pro Preview
- **Role**: Evaluator that compares multiple reports and selects the best one
- **Tools**: None (judge operates solely on the formatted reports it receives)
- **Output**: JSON with `winner_index`, per-report scores, rationale, and verdict
- **Note**: Receives skill compliance summaries and challenge annotations (verdict, reasoning, evidence gaps, contradicting evidence) when present

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

Four prompt templates in `prompts/`:
- `analysis_task.md` — Base analysis prompt composed with context block + report template + skill manifest
- `challenge_task.md` — Challenge prompt with `{{report_markdown}}` and `{{workspace_path}}` placeholders; defines the 6-step challenge protocol and JSON output format
- `continuation_task.md` — Short prompt sent when an agent's response is too short; asks the agent to continue from where it left off within the same session
- `judge_task.md` — Judge evaluation prompt with scoring criteria

The final prompt sent to the session is assembled in `_build_analysis_prompt()` (analysis), `build_challenge_prompt()` (challenge), or `_build_judge_prompt()` (judge).
