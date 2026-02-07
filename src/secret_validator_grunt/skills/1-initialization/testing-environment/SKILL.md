---
name: testing-environment
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

## Logging Test Results

Save test results for evidence:

```python
import json
from pathlib import Path

def save_test_result(result: dict, log_dir: str = "logs"):
    """Save test result to log file."""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    timestamp = result.get("timestamp", "unknown")
    log_file = log_path / f"test_{timestamp.replace(':', '-')}.json"
    
    with open(log_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    return str(log_file)
```

## Running Tests Safely

1. **Limit attempts** - Don't hammer endpoints with repeated requests
2. **Use timeouts** - Always set connection and read timeouts
3. **Handle errors gracefully** - Catch and log all exceptions
4. **Document everything** - Log all test attempts for your report
5. **Clean up** - Remove sensitive data from logs before committing

## Next Phase

After running verification tests, proceed to **Phase 4: Scoring and Reporting** to evaluate your findings and produce the final report.
