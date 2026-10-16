# Development

## Set up

Use Python 3.11+, `uv`, Git, and access to GitHub Copilot.

```bash
uv sync --extra dev
cp .env.example .env
```

Configure authentication in `.env`. Never commit credentials or run output that
contains secrets.

## Configure and run

| Setting | Purpose |
| --- | --- |
| `GITHUB_TOKEN` | Read secret scanning alerts and clone the repository |
| `COPILOT_TOKEN` | Authenticate Copilot; falls back to `GITHUB_TOKEN` when unset |
| `COPILOT_CLI_URL` | Connect to an existing CLI server, which manages its own authentication |
| `COPILOT_MODEL` | Default model when an agent definition does not specify one |
| `ANALYSIS_COUNT` | Number of independent analyses and corresponding challenges |
| `MAX_PARALLEL_SESSIONS` | Limit concurrency within a stage |
| `OUTPUT_DIR` | Choose where reports and workspaces are saved |

See [.env.example](../.env.example) for common settings and
[Config](../src/secret_validator_grunt/models/config.py) for current defaults,
timeouts, and extension paths.

Without `COPILOT_CLI_URL`, the SDK starts its bundled CLI runtime over stdio
using the resolved Copilot token. External-server mode leaves Copilot
authentication to that server; the application's GitHub reads still need
`GITHUB_TOKEN`. See [copilot_client.py](../src/secret_validator_grunt/copilot_client.py).

The startup banner shows `COPILOT_MODEL`, not necessarily each stage's effective
model. Agent-definition overrides take precedence. Response timeouts apply to
individual waits; analysis continuations can add another wait, so they are not
a hard deadline for the whole pipeline.

The challenger stage currently always runs. `CHALLENGE_ENABLED` is not a
recognized setting in `Config`, even if present in an older example environment.

Read [operational risks](operational-risks.md) before live testing. These commands
can contact real provider systems:

```bash
uv run secret-validator-grunt org/repo alert_id
uv run secret-validator-grunt org/repo alert_id --analyses 2 --show-usage
```

The `run` subcommand is optional: `secret-validator-grunt run org/repo alert_id`
and `secret-validator-grunt org/repo alert_id` invoke the same workflow.

Use `uv run secret-validator-grunt --help` for command options. Use a separate
output directory for each comparison run so results are easy to distinguish.

## Make a change

Follow the [project instructions](../.github/instructions/project.instructions.md)
and [Python conventions](../.github/instructions/python.instructions.md).

- Keep changes small and reuse the existing structure and helpers.
- Use tabs, typed function signatures, absolute package imports, and Pydantic
  data models.
- Keep I/O off the async event loop.
- Construct `Config` with its environment aliases, for example
  `Config(SHOW_USAGE=True)`, not `Config(show_usage=True)`.
- Use `tmp_path` for filesystem tests and simple dummy sessions for offline
  tests. Mark async tests with `@pytest.mark.asyncio`.
- When changing the report template or parser, update the paired Markdown and
  JSON fixtures in `tests/fixtures/reports/`. Keep intentionally bad fixtures.

For non-trivial features, agree on a design first, establish a test baseline,
and implement in testable phases. Review the final changes for unnecessary
complexity and missing failure cases.

## Check your work

```bash
# Focused tests while developing
uv run --extra dev pytest tests/test_challenge.py -q

# Full suite at phase checkpoints
uv run --extra dev pytest tests/ -q

# Format and check formatting
uv run fmt
uv run fmt-check

# For selected files, include the underlying formatter's mode explicitly
uv run fmt --in-place src/secret_validator_grunt/main.py
uv run fmt-check --diff src/secret_validator_grunt/main.py
```

Passing explicit formatter arguments replaces the wrapper's defaults. Use the
[code map](code-structure.md#where-common-changes-belong) to select companion
tests instead of guessing which module exercises a behavior.

Unit tests should not depend on live credentials or provider access. Keep
authorized live checks separate, and review their actual evidence rather than
only the final verdict.
