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

If scripts exist and appear safe to run:

```bash
cd {{workspace_path}}/scripts
source venv/bin/activate  # if venv exists
python verify_secret.py
```

Compare the new results against the report's claims.

### 5. Cross-check Repository Evidence

If the report cites specific code:

```bash
grep -r "pattern" {{workspace_path}}/repo/
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

## Common Problems to Detect

1. **Phantom verification** — Report claims tests were run but `scripts/`
   is empty or `logs/` has no output
2. **Network-only tests** — Script checks if host responds but doesn't
   test authentication
3. **Wrong secret** — Script uses a different secret value than the alert
4. **Stale results** — Logs are from a previous run; report describes
   different outcomes
5. **Interpretation errors** — 401 logged but report says "access granted"
