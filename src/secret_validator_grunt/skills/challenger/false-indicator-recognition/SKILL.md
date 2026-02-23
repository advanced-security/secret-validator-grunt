---
name: false-indicator-recognition
description: Patterns that look like real secrets but aren't: test keys, placeholders, environment-specific tokens.
agent: challenger
required: false
---

# False Indicator Recognition

This skill helps identify common patterns where values look like
real secrets but are actually test data, placeholders, examples,
or environment-specific tokens that pose no risk.

## Category 1: Well-Known Test Values

### AWS

| Pattern | Description |
| ------- | ----------- |
| `AKIAIOSFODNN7EXAMPLE` | AWS documentation example |
| `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | AWS doc secret key |
| Access keys starting with `ASIA` | Temporary STS credentials (expire quickly) |

### GitHub

| Pattern | Description |
| ------- | ----------- |
| `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` | All x's = placeholder |
| Values in `GITHUB_TOKEN_EXAMPLE` context | Environment variable examples |

### Generic

| Pattern | Description |
| ------- | ----------- |
| `your_api_key_here` | Placeholder text |
| `<API_KEY>`, `${API_KEY}` | Template variables |
| `sk_test_*`, `pk_test_*` | Stripe test keys |
| `sandbox-*`, `demo-*` | Sandbox/demo prefixes |
| Strings of repeated characters | `xxxxxxxx`, `00000000` |

## Category 2: Documentation Examples

Secrets appearing in:
- Files named `example.*`, `sample.*`, `demo.*`
- Directories named `docs/`, `examples/`, `samples/`
- Markdown files (`.md`) in documentation context
- Comments explaining how to use credentials
- README files showing configuration format

These are often intentional examples, not leaks.

## Category 3: Test Fixtures

Secrets in:
- Files named `*_test.*`, `test_*.*`, `*_spec.*`
- Directories named `tests/`, `test/`, `__tests__/`, `spec/`
- Mock files with `mock` or `fake` in the name
- Files with `fixture` in the path

Test fixtures often contain fake credentials that look real but
don't authenticate anywhere.

## Category 4: Environment-Specific

Secrets that are valid but low-risk:

- **Local development** — `localhost`, `127.0.0.1`, `.local` domains
- **CI/CD** — `github.actions`, `circleci`, `travis` in endpoints
- **Staging** — `staging`, `dev`, `sandbox` in URLs or comments
- **Containers** — Docker compose default passwords (`root`, `admin`)

These may be "real" but don't expose production systems.

## Category 5: Public/Intentional

Some credentials are meant to be public:

- **Public API keys** — Read-only, rate-limited, no auth required
- **Client IDs** — OAuth client IDs without secrets

Check the documentation for the service to understand the key's scope.

## How to Apply

When challenging a TRUE_POSITIVE verdict:

1. **Check the secret format** — Does it match known test patterns?
2. **Check the file context** — Is it in docs, tests, or examples?
3. **Check the variable name** — Does it say `example`, `test`, `fake`?
4. **Check the URL/endpoint** — Is it targeting localhost or sandbox?
5. **Check service documentation** — Is this key type public by design?

If any of these apply, the verdict may be incorrect.

## Caution

These patterns suggest false positives but don't guarantee them:

- Real secrets can accidentally be named `example`
- Test directories can contain real credentials
- Sandbox credentials can sometimes access production
- Environment variables with `TEST` can still be valid

Use these as evidence gaps, not definitive refutation. The challenger
should note the pattern and request independent verification.

## Evidence Gap Example

If the report says TRUE_POSITIVE but:
- Secret value is `AKIAIOSFODNN7EXAMPLE`
- File is in `docs/examples/aws-setup.md`
- Variable is named `AWS_ACCESS_KEY_EXAMPLE`

Add to `evidence_gaps`:
- "Secret matches AWS documentation example pattern"
- "Located in documentation examples directory"
- "Variable name explicitly indicates example"

This doesn't automatically mean REFUTED, but it questions the verdict.
