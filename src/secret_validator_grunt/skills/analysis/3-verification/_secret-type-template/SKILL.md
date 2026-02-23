---
name: secret-type-template
agent: analysis
description: Template for creating new secret-type-specific verification guides.
phase: 3-verification
secret-type: _template
---

# [Secret Type Name] Verification

> **Note:** This is a template. Copy this file and customize for a specific secret type.

## Secret Format

Describe the format of this secret type:

| Format | Example |
| ------ | ------- |
| Pattern | `prefix_xxxxxxxxxx` |
| Length | 32 characters |
| Charset | alphanumeric |

## Identification Patterns

How this secret type appears in code:

### Common Patterns

```
# Pattern 1
SECRET_KEY = "..."

# Pattern 2
export SECRET_KEY="..."
```

## Provider Information

| Attribute | Value |
| --------- | ----- |
| Provider | [Provider name] |
| Documentation | [URL to docs] |
| Rotation URL | [URL to rotate] |
| Validity Check API | [If available] |

## Verification Steps

### Step 1: [First Step]

Description of first verification step.

```bash
# Command or code
```

### Step 2: [Second Step]

Description of second verification step.

```bash
# Command or code
```

### Step 3: Test Authentication

```bash
# Test command
```

## Python Validation Script

```python
#!/usr/bin/env python3
"""Validate [Secret Type] credentials."""

import sys
import json

def validate_secret(secret: str) -> dict:
    """
    Validate the secret.
    
    Returns:
        dict with validation results
    """
    result = {
        "secret_type": "[secret_type]",
        "secret_preview": secret[:8] + "..." if len(secret) > 8 else secret,
        "valid": False,
    }
    
    # TODO: Implement validation logic
    # Example:
    # - Check format
    # - Test against API
    # - Verify scope/permissions
    
    return result

if __name__ == "__main__":
    SECRET = "your-secret-here"
    
    result = validate_secret(SECRET)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result.get("valid") else 1)
```

## Result Interpretation

| Result | Meaning | Verdict |
| ------ | ------- | ------- |
| [Result 1] | [Meaning] | [TRUE/FALSE_POSITIVE] |
| [Result 2] | [Meaning] | [TRUE/FALSE_POSITIVE] |
| [Result 3] | [Meaning] | [INCONCLUSIVE] |

## Common False Positive Indicators

- [Indicator 1]
- [Indicator 2]
- [Indicator 3]

## Evidence for Report

Include in your report:

1. **Secret format**: Description of detected format
2. **Provider**: Who issued this secret
3. **Test method**: How you validated it
4. **Response/Result**: What the validation returned
5. **Verdict justification**: Why this is TRUE/FALSE positive

## Additional Resources

- [Link to provider documentation]
- [Link to related tools]
- [Link to example code]
