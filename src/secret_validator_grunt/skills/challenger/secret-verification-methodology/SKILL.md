---
name: secret-verification-methodology
description: Workspace inspection and independent verification workflow for adversarial challenges.
agent: challenger
required: true
---

# Secret Verification Methodology

This skill guides the challenger through systematic workspace inspection
and independent verification of analysis claims.

## Workspace Structure

Analysis agents create workspaces with a predictable structure:

```
workspace/
├── scripts/          # Verification scripts written by analysis agent
│   ├── venv/         # Python virtual environment (if used)
│   ├── verify_*.py   # Verification scripts
│   └── requirements.txt
├── logs/             # Test output and results
│   └── test_results.json
├── artifacts/        # Generated evidence
│   └── evidence/
├── repo/             # Cloned repository
├── stream.log        # Agent streaming log
└── report.md         # The analysis report
```

The original workspace is read-only evidence. Your separate working copy is
`{{challenge_workspace_path}}`; it starts with copies of these inputs, except
virtual environments and caches. Only run scripts from the working copy.
Never write to or unlock originals. Distinguish copied inputs from actual
challenger-produced evidence.

## Inspection Protocol

### 1. List Workspace Contents

Always start by listing the workspace root:

```bash
ls -la {{workspace_path}}
```

Then check subdirectories:

```bash
ls -la {{workspace_path}}/scripts/
ls -la {{workspace_path}}/logs/
```

### 2. Read Verification Scripts

If scripts exist, read them to understand what verification was attempted:

```bash
cat {{workspace_path}}/scripts/verify_secret.py
```

Look for:
- What endpoints/APIs are being tested
- What authentication method is used
- What success/failure criteria are defined
- Whether the actual secret value is used correctly
- Whether companion credentials, scope, and region are correct
- Whether alternative explanations could produce the same response

### 3. Read Test Output Logs

Check the actual output of any verification scripts:

```bash
cat {{workspace_path}}/logs/test_results.json
```

Compare the log content against what the report claims. Key questions:
- Do the timestamps match the report's timeline?
- Do HTTP status codes match the claimed results?
- Are there error messages not mentioned in the report?

### 4. Re-execute Verification

If a safe rerun resolves a concrete question:

```bash
cd "{{challenge_workspace_path}}"
set -o pipefail
python3 scripts/verify_secret.py 2>&1 | tee logs/challenger-verify-1.log
```

Choose an interpreter with the required dependencies. You may use an existing
analyst environment's interpreter read-only, or create an environment in your
working copy. Do not install into an analyst environment.

Inspect output paths first. Scripts with original absolute paths must be
adapted only in the copy, with changes explained, or left unexecuted with a
clear limitation. Preserve each attempt's stdout/stderr under a distinct log
name; do not claim copied logs as your own execution.

Compare the new results against the report's claims. Reproducibility alone
does not establish that the method or inference is correct. Prefer the
smallest relevant check over repeating every test.

### 5. Cross-check Repository Evidence

If the report cites specific code:

```bash
grep -r "pattern" "{{challenge_workspace_path}}/repo/"
```

Verify the cited code exists and says what the report claims.

## Verification Quality Assessment

Rate the analysis based on:

| Criterion | Strong | Weak |
| --------- | ------ | ---- |
| Scripts present | Yes, clear verification logic | None or trivial |
| Logs present | Detailed output with timestamps | None or empty |
| Secret tested | Actually hit external API | Only checked syntax |
| Error handling | Distinguishes auth fail vs network | Generic errors |
| Output matches | Logs match report claims | Discrepancies |
| Inference | Appropriate endpoint and provider-specific interpretation | Generic status code treated as proof |

CONFIRMED requires genuine evidence and a supported conclusion without
unresolved material gaps. A reproducible test against an inappropriate or
scope-restricted endpoint can still warrant INSUFFICIENT_EVIDENCE. Use
REFUTED for demonstrated contradictions, not mere uncertainty.

## Common Problems to Detect

1. **Phantom verification** — Report claims tests were run but `scripts/`
   is empty or `logs/` has no output
2. **Network-only tests** — Script checks if host responds but doesn't
   test authentication
3. **Wrong secret** — Script uses a different secret value than the alert
4. **Stale results** — Logs are from a previous run; report describes
   different outcomes
5. **Interpretation errors** — 401 logged but report says "access granted"
6. **Unsupported inference** — Generic 403 treated as valid credentials,
   a public 200 treated as authentication, or restricted endpoint rejection
   treated as proof that the credential cannot work anywhere
