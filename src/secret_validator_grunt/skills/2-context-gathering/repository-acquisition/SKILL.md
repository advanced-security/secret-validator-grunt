---
name: repository-acquisition
description: Strategies for cloning repositories with full history into the workspace for analysis.
phase: 2-context-gathering
required: true
---

# Repository Acquisition

This skill provides guidance on properly cloning and accessing repository content for secret validation analysis.

## Cloning Strategy

Always clone the repository into your designated workspace directory to ensure isolation and proper cleanup.

### Basic Clone Command

```bash
cd /path/to/workspace
git clone https://github.com/owner/repo.git repo
cd repo
```

### Clone with Full History

For complete analysis, you need access to all branches and the full commit history:

```bash
git clone --mirror https://github.com/owner/repo.git repo.git
cd repo.git
git worktree add ../repo HEAD
```

Or for a standard clone with all branches:

```bash
git clone https://github.com/owner/repo.git repo
cd repo
git fetch --all
```

## Accessing Historical Commits

Secrets may exist in commits that are no longer on any branch. Use the commit SHA from the alert location:

```bash
# Show the commit containing the secret
git show <commit_sha>

# Check out the specific commit
git checkout <commit_sha>

# View the file at that specific commit
git show <commit_sha>:path/to/file
```

## Branch Analysis

List all branches to understand where secrets may exist:

```bash
# List all branches (including remote)
git branch -a

# Check if a commit exists on specific branches
git branch --contains <commit_sha>
```

## Important Considerations

1. **Workspace Isolation**: Always clone into your designated workspace folder
2. **Full History**: Ensure you have complete git history for thorough analysis
3. **Branch Coverage**: Check all branches, not just the default
4. **Orphaned Commits**: Some commits may not be on any branch but still contain secrets

## Next Steps

After acquiring the repository:

1. Navigate to the locations identified in Phase 1
2. Read the file contents at those locations
3. Understand the surrounding code context
4. Proceed to Phase 3 for verification testing
