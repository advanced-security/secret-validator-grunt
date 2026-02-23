---
name: testing-environment
agent: analysis
description: Guidelines for setting up isolated testing environments for secret validation scripts.
phase: 1-initialization
required: true
---

# Testing Environment Guidelines

This skill provides guidance on setting up proper testing environments for validating secrets. **You MUST follow these guidelines before writing any verification scripts.**

## Workspace Isolation

### CRITICAL: Work Only in Your Workspace

- **DO** all testing in a subdirectory within your workspace
- **DO NOT** use `/tmp` or ANY other system directories
- **DO NOT** access files outside the provided workspace

### Required Directory Structure

**BEFORE running any verification tests, create this structure in your workspace:**

```bash
# Create the standard directory structure
mkdir -p scripts logs artifacts
```

Your workspace MUST be organized as:

```text
workspace/
├── repo/              # Cloned repository (from repository-acquisition)
├── scripts/           # Your validation scripts
│   ├── venv/          # Python virtual environment
│   ├── verify_secret.py   # Main verification script
│   └── requirements.txt
├── logs/              # Test output logs
│   └── test_results.json
└── artifacts/         # Generated artifacts
    └── evidence/
```

## Python Environment Setup

### Always Use Virtual Environments

**Create a venv BEFORE installing any packages:**

```bash
# Navigate to scripts directory in YOUR workspace
cd workspace/scripts

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install requests httpx
```

### Check Existing Tools First

Before installing, check if tools are available:

```bash
# Check Python
python3 --version

# Check pip
pip --version

# Check if package is installed
pip show requests

# Check available commands
which curl nc nslookup
```

## Language Preference

### Prefer Python for Validation Scripts

Python is preferred because:

- Rich ecosystem for API testing (requests, httpx)
- Easy credential handling
- Cross-platform compatibility
- Good error handling

### When to Use Other Languages

Use alternatives when:

- Testing requires specific SDK (e.g., AWS CLI for AWS keys)
- Target system requires specific tooling
- Existing code in repo demonstrates usage

## Executing and Logging Test Results

### CRITICAL: You MUST Execute Scripts — Never Hand-Write Results

Every verification script you create **MUST be executed via `bash`** and the real output captured. The log files in `logs/` must contain **actual stdout/stderr** from script execution, not hand-written summaries.

**Correct workflow:**

```bash
# 1. Write your verification script to scripts/
# 2. Execute it and capture real output
cd workspace/scripts
source venv/bin/activate
python verify_secret.py 2>&1 | tee ../logs/verify_secret.log

# The log file now contains the ACTUAL output
```

**What is FORBIDDEN:**

- Writing `test_results.json` or any results file by hand
- Creating log files with assumed/expected output
- Claiming tests passed without executing the script
- Writing a script and a separate results file independently

**The ONLY acceptable evidence** is stdout/stderr captured from actual script execution. If a script fails or produces unexpected output, report that honestly — fabricated results will be caught by the challenger agent.

### Logging Multiple Tests

If you run multiple verification steps, capture each one:

```bash
# Run each test and capture output
python test_auth.py 2>&1 | tee ../logs/test_auth.log
python test_connection.py 2>&1 | tee ../logs/test_connection.log
```

The `logs/` directory should contain only files produced by actual command execution.

## Running Tests Safely

1. **Limit attempts** - Don't hammer endpoints with repeated requests
2. **Use timeouts** - Always set connection and read timeouts
3. **Handle errors gracefully** - Catch and log all exceptions
4. **Document everything** - Log all test attempts for your report
5. **Clean up** - Remove sensitive data from logs before committing

## Next Phase

After running verification tests, proceed to **Phase 4: Scoring and Reporting** to evaluate your findings and produce the final report.
