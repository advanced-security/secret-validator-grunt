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

When rotation affects the conclusion, inspect relevant history in the
challenger's repository copy:

```bash
# Search for rotation commits
git -C "{{challenge_workspace_path}}/repo" log --oneline --all --grep="rotate"
git -C "{{challenge_workspace_path}}/repo" log --oneline --all --grep="revoke"
git -C "{{challenge_workspace_path}}/repo" log --oneline --all --grep="invalidate"

# Check if the secret-containing file was modified recently
git -C "{{challenge_workspace_path}}/repo" log -p --follow -- path/to/secret/file
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

Did the analysis test the exact alerted value?

- Alert locations may span multiple commits
- The current file may contain a replacement instead of the alerted value
- A working replacement does not establish the alerted value's validity
- Removal or replacement in Git does not prove provider-side revocation

```bash
# Find all versions of the secret
git -C "{{challenge_workspace_path}}/repo" log -p --all -S 'secret_pattern'
```

## Challenge Questions

When reviewing a report, ask:

1. Did the analysis check current alert state, or assume it's active?
2. If rotation affects the conclusion, did the analysis check relevant history?
3. Did the analysis distinguish between "invalid credential" and
   "network unreachable"?
4. Did the analysis check for expiration if applicable?
5. Did the analysis verify the correct version of the secret?

If the answer to any is "no," document it as an evidence gap.

## Refutation Criteria

Refute a TRUE_POSITIVE if:
- Alert state shows `resolution: "revoked"` AND testing confirms
  the secret no longer works
- Direct testing contradicts the claim that the exact alerted value works;
  replacement credentials in Git alone are not sufficient
- Secret is demonstrably expired (JWT `exp` in past, cert expired)

Refute a FALSE_POSITIVE if:
- Direct testing shows the exact alerted value still works
- Secret appears test-like but actually works against production
- New credential was created with same value after rotation
