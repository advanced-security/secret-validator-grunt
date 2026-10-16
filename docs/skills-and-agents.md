# Skills and agents

Agent definitions set a role, model, and tools. Task prompts describe the work
for a stage. Skills provide reusable guidance. All three live under
`src/secret_validator_grunt/`.

The repository's `.github/instructions/` files guide developers working on this
app, not the analyst/challenger/judge sessions it creates. Those sessions set
`skip_custom_instructions=True`; change the stage definition, task prompt, and
skills together to change investigation behavior.

## Agent roles

| Role | Definition | Responsibility |
| --- | --- | --- |
| Analyst | `agents/secret_validator.agent.md` | Investigate the alert, verify the secret, and write an evidence-backed report |
| Challenger | `agents/challenger.agent.md` | Question the evidence and conclusion; perform relevant checks in a separate working copy |
| Judge | `agents/judge.agent.md` | Compare reports and challenge findings, then select a report |

Read the definition files for current models and tools. An agent's model
overrides `COPILOT_MODEL`. In a definition, `tools: []` means no tools; omitting
`tools` leaves runtime tools unrestricted. The default judge has no tools.

Agents can run shell commands with the host user's access. Tool lists and
working directories are not a sandbox. See [operational risks](operational-risks.md).

## Required and optional guidance

Analysis skills follow four phases:

1. Initialization.
2. Context gathering.
3. Verification.
4. Scoring and reporting.

For analysis and challenger sessions, required skills are included in the task
prompt in phase order. Optional skills are listed with descriptions and loaded
when relevant to the secret, context, or proposed test. A secret-type hint helps
selection; it is not the only reason to use a skill. There is no
`PRELOAD_REQUIRED_SKILLS` setting: enabled required bodies are supplied during
setup. The default judge has no tools or skill directories.

Skills are organized under `skills/analysis/`, `skills/challenger/`, and
`skills/judge/`. Analysis and challenger manifests reject invalid metadata and
duplicate names. Disabled skills are excluded; entries under `_` or `.`
directories within scanned skill roots are omitted from the manifest.

Use `DISABLED_SKILLS` to exclude named guides, including required ones.
`hidden: true` alone is not an app-level disabling switch; keep templates under
an excluded directory instead.

Guidance coverage records what was supplied or loaded, not what was followed.
Review the resulting evidence. Missing optional guides are reported without
blocking delivery of the required guidance.

## Add or change a skill

Place an analysis skill at
`skills/analysis/<phase>/<skill-name>/SKILL.md`. For another agent, use
`skills/<agent-type>/<skill-name>/SKILL.md`.

A minimal optional analysis guide looks like this:

```markdown
---
name: provider-check
description: How to interpret this provider's authentication responses.
agent: analysis
phase: 3-verification
required: false
---

# Provider check

Explain which checks are appropriate, what the responses establish,
and when the result must remain inconclusive.
```

Set `required: true` only for guidance needed on every applicable run, not for a
provider-specific check. An optional `secret-type` field can identify a relevant
secret type. New guides are discovered on the next run without manual registration.

Keep instructions focused and consistent across the agent definition, task
prompt, and required skills. Do not present a production write or delete
operation as an authentication test.

## Tools and prompts

The custom tools provide alert details, location pages, supported-validator
discovery, and credential validation. Call `validate_secret` with the alerted
value and type; it selects the matching checker. Use `list_secret_validators`
only when investigating alternative supported types, not on every analysis.

`validate_secret` can return `valid`, `invalid`, `error`, or `no_validator`.
`no_validator` means the installed registry has no checker for that secret
type, not that the secret is invalid. An error is not a negative validation
either. Use an authorized, appropriate alternative check or leave the result
inconclusive.

`gh_secret_scanning_alert` and `gh_secret_scanning_alert_locations` share a
run-scoped `GitHubEvidence` instance. Set `refresh=true` to request fresh facts.
Location results are paginated: follow `next_page` until `null`, and do not
treat `locations_count` as the alert's total. Refresh each page when refreshing
the whole location set. Responses include `fetched_at`; live credential checks
are not cached.

Stage tasks live in `prompts/`. Report formatting lives in `templates/`.
Change the relevant instructions together, then check prompt and skill tests.
For implementation details, start with `core/skills.py`, `core/session.py`, and
`integrations/copilot_tools.py`; see the [code map](code-structure.md).
