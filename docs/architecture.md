# Architecture

Secret Validator Grunt investigates GitHub secret scanning alerts and produces
reports for review. It combines repository context, live credential checks, and
independent agent assessments. It uses the GitHub Copilot SDK to run the agents.

## Workflow

1. **Prepare.** Read the configuration and prepare a shared repository clone.
   Each analyst gets its own workspace and repository copy.
2. **Analyze.** Analysts investigate the alert, run verification checks, and
   write reports with supporting evidence. Automated checks assess report
   structure and consistency.
3. **Challenge.** A challenger reviews each report's evidence and reasoning.
   It inspects originals read-only and runs relevant checks in a separate copy.
4. **Judge.** The judge compares the reports, report checks, and challenge
   findings, then selects a report. By default, it has no tools and does not
   independently contact the provider.

The default run uses three analysts, three challengers, and one judge.
Increasing the agent count adds independent assessments, but also cost and
provider requests. It does not guarantee a correct result.

The runner returns a `RunOutcome`: analyst `AgentRunResult` objects, their
attached `ChallengeResult` objects, and the `JudgeResult`. The TUI consumes these
results; it does not make validation decisions. See the
[code map](code-structure.md) for the source and test boundaries.

## Facts and guidance

GitHub alert details and location pages are shared within a run to avoid
duplicate reads. Agents can request fresh facts when needed. Live credential
checks are not cached, and location pages must still be followed to completion.

Required guidance is supplied in workflow order: initialization, context,
verification, then scoring and reporting. Optional guides are loaded when
relevant to the secret or proposed check. Supplying guidance does not prove
that the agent followed it.

## What a challenge means

| Result | Meaning |
| --- | --- |
| `CONFIRMED` | The evidence is credible, the method is appropriate, and the conclusion is supported |
| `REFUTED` | Evidence contradicts an important claim or the conclusion |
| `INSUFFICIENT_EVIDENCE` | An important question remains unresolved |

Reproducing a script's output does not prove that its endpoint or interpretation
is correct. Challengers should examine those choices, not just repeat the test.
Their findings inform the judge; they are not an automatic veto.

## Preserving evidence

Before a challenge, the analyst's `scripts/`, `logs/`, `artifacts/`, and
`report.md` are made read-only. The app checks their contents and permissions
after the session.
Changed or unverifiable originals force an `INSUFFICIENT_EVIDENCE` challenge
result.

Reruns use a separate working copy with its own outputs. Copies of old logs are
not proof of a new execution. Scripts with hardcoded original output paths must
be adapted in the copy or left unexecuted with the limitation explained.

These controls protect against accidental overwrites. They are not an OS
sandbox, and the original repository and runtime environments are outside the
locked evidence set.

## Failure and retry behavior

An analysis that returns a short or empty answer can receive bounded continuation
prompts in the same session. This is not a retry of the whole pipeline, and
challenger/judge calls currently do not use continuations. See
[core/session.py](../src/secret_validator_grunt/core/session.py) for collection
and timeout behavior.

A failed analysis carries an error in its result. A failed or unparseable
challenge produces `INSUFFICIENT_EVIDENCE`; preparation failure does not start
an unprotected challenger session. An unparseable judge response produces no
winner. The runner writes a final report only when a valid winner points to
nonempty report text. Existing files are not proof of success; see
[output reuse](diagnostics.md#output-reuse).

## Reading the result

A report describes the tested credential, operation, and time. A rejected
request alone does not establish why it failed or whether the credential was
previously usable. Confidence scores and automated report checks help review;
they are not measured accuracy guarantees.

Use [Diagnostics](diagnostics.md) to locate reports and evidence,
[Code map](code-structure.md) to follow the implementation, and
[Operational risks](operational-risks.md) before live testing.
