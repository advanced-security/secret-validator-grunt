---
name: code-analysis
description: Techniques for analyzing code context around secret locations to understand usage and intent.
phase: 2-context-gathering
required: true
---

# Code Analysis for Secret Validation

This skill provides guidance on analyzing the code context around secret locations to understand how secrets are used and determine their validity.

## Context Analysis Strategy

### 1. Read the Immediate Context

Start by reading the file where the secret was found, focusing on the surrounding code:

```bash
# View the file with line numbers
cat -n path/to/file

# Or use git show for a specific commit
git show <commit_sha>:path/to/file
```

### 2. Identify Usage Patterns

Look for how the secret is being used:

- **Configuration files**: Is it setting up a connection?
- **Source code**: Is it being passed to an API or SDK?
- **Test files**: Is it used in test fixtures or mocks?
- **Documentation**: Is it an example in docs or comments?

### 3. Trace Dependencies

Follow the code to understand the full context:

- What service or API does this secret authenticate against?
- What hostname/URL is the secret used with?
- Are there related configuration files that provide more context?

## Key Questions to Answer

| Question | Where to Look |
|----------|---------------|
| What type of secret is this? | Alert details, code patterns |
| What service does it connect to? | URL patterns, import statements |
| Is it hardcoded or templated? | Variable substitution patterns |
| Is it used in production code? | File path, branch analysis |
| Is it a test/example value? | File location, naming patterns |

## False Positive Indicators

Watch for these patterns that suggest false positives:

- Placeholder values like `password`, `secret`, `changeme`
- Example usernames like `test`, `demo`, `example`
- Localhost or example.com URLs
- Location in test directories or documentation
- Comments indicating example usage
- Clearly fake values in tutorials

## True Positive Indicators

Watch for these patterns that suggest real secrets:

- High entropy strings
- Production hostnames
- Multiple uses across codebase
- No comments indicating examples
- Located in configuration that gets deployed

## Technology Stack Awareness

Understanding the tech stack helps interpret the context:

| Stack | Common Secret Patterns |
|-------|----------------------|
| Python | `.env` files, `settings.py`, `config.yaml` |
| Node.js | `.env`, `config.json`, environment variables |
| Java | `application.properties`, `application.yml` |
| Terraform | `.tfvars`, `variables.tf` |

## Next Steps

After analyzing the code context:

1. Determine the target endpoint for the secret
2. Identify the verification approach based on secret type
3. Proceed to Phase 3 for active verification testing
