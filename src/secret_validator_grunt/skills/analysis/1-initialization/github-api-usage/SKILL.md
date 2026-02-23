---
name: github-api-usage
agent: analysis
description: Effective usage of GitHub API tools for fetching secret scanning alerts and locations.
phase: 1-initialization
required: true
---

# GitHub API Usage for Secret Validation

This skill provides guidance on using the available GitHub API tools effectively during the initialization phase of secret validation.

## Available Tools

You have access to these custom tools for GitHub Secret Scanning:

| Tool | Purpose |
|------|---------|
| `gh_secret_scanning_alert` | Fetch complete alert details including state, type, validity |
| `gh_secret_scanning_alert_locations` | Fetch all locations where the secret was found |

## Workflow

### Step 1: Fetch Alert Details

First, call `gh_secret_scanning_alert` to fetch the complete alert information:

```
gh_secret_scanning_alert(repo="owner/repo", alert_number=1)
```

This returns:
- `secret_type` - The type of secret detected
- `state` - Current alert state (open/resolved)
- `validity` - GitHub's validity assessment (unknown/valid/invalid)
- `created_at` - When the alert was created
- `updated_at` - Last update timestamp
- `push_protection_bypassed` - If push protection was bypassed

### Step 2: Fetch Location Details

Then call `gh_secret_scanning_alert_locations` to get all locations:

```
gh_secret_scanning_alert_locations(repo="owner/repo", alert_number=1)
```

This returns an array of locations with:
- `path` - File path where secret was found
- `start_line` / `end_line` - Line numbers
- `commit_sha` - The commit containing the secret
- `details` - Additional context about the location

## Key Information to Extract

From the alert response, capture:

1. **Secret Type** - Critical for choosing verification approach
2. **Validity Status** - GitHub's out of the box validity assessment
3. **Creation Date** - How long the secret has been exposed
4. **All Locations** - Every place the secret appears

## Common Patterns

### Multiple Locations

A single secret may appear in multiple files or commits. Always fetch ALL locations to understand the full scope of exposure.

### Historical Commits

Secrets may exist in commits that are no longer on the default branch. The location data includes commit SHAs for historical analysis.

## Next Steps

After gathering this information:

1. Proceed to Phase 2 (Context Gathering) to clone the repository
2. Use the location data to identify files to analyze
3. Check the secret type to determine verification approach

