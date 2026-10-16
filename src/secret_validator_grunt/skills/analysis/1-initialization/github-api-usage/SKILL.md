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
| `gh_secret_scanning_alert_locations` | Fetch one page of complete location details |

## Workflow

### Step 1: Fetch Alert Details

First, call `gh_secret_scanning_alert` to fetch the complete alert information:

```
gh_secret_scanning_alert(repo="owner/repo", alert_number=1)
```

This returns:
- `secret` - The actual value to verify; do not substitute a guessed value
- `secret_type` - The type of secret detected
- `state` - Current alert state (open/resolved)
- `validity` - GitHub's validity assessment (unknown/valid/invalid)
- `created_at` - When the alert was created
- `updated_at` - Last update timestamp
- `push_protection_bypassed` - If push protection was bypassed
- `resolution` and related fields - Resolution evidence, not proof of validity
- `fetched_at` - UTC time this snapshot was fetched

All alert fields are returned. Successful responses are shared across agents
within this run; do not fetch the same facts again through shell commands.
Use `refresh=true` when you need current state, such as checking a change in
resolution or rotation. A cached snapshot is not a fresh provider validation.

### Step 2: Fetch Location Details

Fetch location pages as needed for context, retaining the same `per_page`:

```
gh_secret_scanning_alert_locations(repo="owner/repo", alert_number=1, page=1, per_page=50)
```

This returns `locations`, `locations_count` (this page only), `page`,
`per_page`, `next_page`, and `fetched_at`. Each location preserves its `type`
and complete `details`, including paths, lines, and commit SHAs where present.
Issue, pull request, discussion, and wiki locations need not have file paths;
use their specific details instead of assuming every location is a commit.

Follow `next_page` until it is null before claiming complete coverage.
Inspect relevant context incrementally instead of fetching every file in
the repository. If you stop early, state which location pages or sources
remain unexamined. An error is missing evidence, not an empty location set.
To refresh the entire set, restart at page 1 with `refresh=true` and repeat
that flag on subsequent pages. Pages are independent snapshots, not an
atomic snapshot of GitHub.

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

1. Proceed to Phase 2 (Context Gathering) to inspect the provided repository copy
2. Use the location data to identify files to analyze
3. Check the secret type to determine verification approach
