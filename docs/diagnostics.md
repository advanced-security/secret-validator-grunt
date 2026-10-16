# Diagnostics

Use `--show-usage` to display token usage, guidance coverage, and tool activity,
and to save additional diagnostics:

```bash
uv run secret-validator-grunt org/repo alert_id --show-usage
```

The terminal shows analysis, challenger, and judge progress. The final summary
lists the report and workspace paths.

## Find the evidence

By default, output is under `analysis/<org>/<repo>/<alert_id>/`.

| Location | Contents |
| --- | --- |
| `final-report.md` | The selected analysis report |
| `report-<n>.md` | An individual analyst's report |
| `<analysis-id>/` | Original scripts, logs, artifacts, repository copy, and stream log |
| `<analysis-id>/diagnostics.json` | Analyst usage, guidance, tool activity, and report checks when `--show-usage` is enabled |
| `judge-<org>_<repo>-<alert_id>.stream.log` | Judge session output in the alert directory |
| `challenges/<unique-id>/result.json` | Challenge verdict, reasoning, gaps, and workspace path; usage is included with `--show-usage` |
| `challenges/<unique-id>/evidence-manifest.json` | Original evidence fingerprints used to detect changes |
| `challenges/<unique-id>/work/` | Copies of analyst inputs and the challenger's rerun outputs |
| `challenges/<unique-id>/stream.log` | That challenger's session output |

Copied logs are not proof that the challenger ran a check. Compare the original
logs with the separately recorded rerun output. Do not treat a leftover report
from an earlier run as evidence that a new run completed.

## Output reuse

Using the same alert/output directory again reuses `_shared_repo/` without
automatically fetching newer commits. Analysts and challengers get new unique
workspace directories, while named reports such as `report-0.md` and
`final-report.md` are overwritten only when new content is produced. The judge
stream log is appended. Old workspaces and reports are not automatically
removed.

For comparisons, choose a fresh `OUTPUT_DIR`. If no usable winner is produced,
an old `final-report.md` may remain. The current TUI can also show the wrong
final-report path by omitting the repository/alert directories; look under
`<OUTPUT_DIR>/<org>/<repo>/<alert_id>/` and in the winning analyst's workspace,
then confirm the file belongs to this run.

## Interpret the indicators

- **Guidance coverage** means required guidance was supplied or loaded. It does
  not prove the agent followed it.
- **Tool success** means the tool call completed successfully. Read command exit
  codes and stdout/stderr to confirm that a verification script actually worked.
- **Report checks** assess structure and consistency, not credential validity.
- **Usage figures** come from the SDK. The current `Requests` column displays
  its cost value, not a literal call count. Summed session durations include
  parallel work and are not elapsed run time.

## Investigate a problem

Start with the report's evidence references and the relevant workspace logs.
For a challenge, read `result.json` for unresolved questions or an original
evidence integrity failure. Missing optional guides are reported as warnings.

Use `--stream-verbose` when live session output would help. Reports, scripts,
and logs may contain secrets even when usage diagnostics are disabled. Restrict
access and redact them before sharing; see [operational risks](operational-risks.md).
