---
name: rotation-and-revocation-analysis
description: How to determine if a secret has been rotated, revoked, expired, or replaced.
agent: challenger
required: true
---

# Rotation and Revocation Analysis

This skill helps identify when a secret has been invalidated through
rotation, revocation, expiration, or replacement — even when the
analysis report missed these signals.

## Why This Matters

A common failure mode: the analysis concludes TRUE_POSITIVE when the
secret was already rotated. The security team wastes time on a fixed
issue. Conversely, FALSE_POSITIVE when the secret was rotated but
then recreated.

## Check 1: GitHub Alert State

Use `gh_secret_scanning_alert` to get current alert metadata:

- `state: "resolved"` with `resolution: "revoked"` strongly suggests
  the secret was invalidated
- `push_protection_bypassed: true` may indicate intentional commit of
  a test/non-production secret
- Multiple `locations` across branches may indicate historical exposure

Compare the alert state against the report's claims.

## Check 2: Repository History

Look for rotation evidence in the repository:

```bash
# Search for rotation commits
git log --oneline --all --grep="rotate" {{workspace_path}}/repo/
git log --oneline --all --grep="revoke" {{workspace_path}}/repo/
git log --oneline --all --grep="invalidate" {{workspace_path}}/repo/

# Check if the secret-containing file was modified recently
git log -p --follow -- path/to/secret/file {{workspace_path}}/repo/
```

Key signals:
- Commits titled "rotate API key", "regenerate credentials"
- File modifications that removed or replaced the secret value
- New commits adding different credentials with same purpose

## Check 3: Secret Provider Hints

Different secret types have rotation indicators:

| Secret Type | Rotation Signal |
| ----------- | --------------- |
| AWS Access Key | Key ID format shows age (older keys start with 'AKIA', newer with 'AKID') |
| GitHub Token | `ghp_` prefix is classic, `github_pat_` is fine-grained (newer) |
| Slack Token | Check `/auth.test` endpoint for `ok: false, error: "invalid_auth"` |
| Database | Connection refused vs auth failed distinguishes network vs credential |
| API Keys | 401 with "expired" or "revoked" in body |

## Check 4: Expiration Signals

Some secrets have built-in expiration:

- **JWT tokens** — decode and check `exp` claim
- **OAuth tokens** — check `expires_in` or `expires_at` in response
- **Certificates** — check validity period
- **Temporary credentials** — STS tokens, Azure managed identities

If the analysis didn't check expiration, this is an evidence gap.

## Check 5: Multiple Values

Did the analysis test the CURRENT secret or a historical one?

- Alert locations may span multiple commits
- The secret value may differ between locations
- The "live" secret might be in the most recent commit only

```bash
# Find all versions of the secret
git log -p --all -S 'secret_pattern' {{workspace_path}}/repo/
```

## Challenge Questions

When reviewing a report, ask:

1. Did the analysis check current alert state, or assume it's active?
2. Did the analysis check repository history for rotation evidence?
3. Did the analysis distinguish between "invalid credential" and
   "network unreachable"?
4. Did the analysis check for expiration if applicable?
5. Did the analysis verify the correct version of the secret?

If the answer to any is "no," document it as an evidence gap.

## Refutation Criteria

Refute a TRUE_POSITIVE if:
- Alert state shows `resolution: "revoked"` AND testing confirms
  the secret no longer works
- Repository history shows clear rotation AND new credentials exist
- Secret is demonstrably expired (JWT `exp` in past, cert expired)

Refute a FALSE_POSITIVE if:
- Secret was rotated but report based conclusion on old version
- Secret appears test-like but actually works against production
- New credential was created with same value after rotation
