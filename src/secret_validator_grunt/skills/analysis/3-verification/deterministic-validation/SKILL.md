---
name: deterministic-validation
agent: analysis
description: Use the validate-secrets tool for deterministic secret validation when a matching validator is available.
phase: 3-verification
required: true
---

# Deterministic Secret Validation

This skill guides the use of the `validate_secret` and `list_secret_validators` tools to perform deterministic (non-LLM) validation of secrets when a matching validator exists.

## When to Use

During **Phase 3 — Verification**, after you have gathered the secret value and identified its `secret_type` from the alert metadata:

1. Call `list_secret_validators` to see which validators are available.
2. If the alert's `secret_type` matches an available validator, call `validate_secret` with the secret value and type.
3. Incorporate the deterministic result into your analysis alongside other verification evidence.

## Tool: `list_secret_validators`

Returns the currently registered validators and their descriptions.

**Parameters:** none required.

**Example response:**

```json
{
  "validators": [
    {"name": "google_api_key", "description": "Validates Google API keys"},
    {"name": "snyk_api_token", "description": "Validates Snyk API tokens"}
  ],
  "count": 2
}
```

## Tool: `validate_secret`

Validates a secret value against its registered validator.

**Parameters:**

| Parameter | Required | Description |
| --------- | -------- | ----------- |
| `secret` | Yes | The secret value to validate |
| `secret_type` | Yes | The secret type identifier from the alert |
| `timeout` | No | Timeout in seconds (default: 30) |

**Possible `status` values:**

| Status | Meaning |
| ------ | ------- |
| `valid` | The secret is confirmed active / working |
| `invalid` | The secret is confirmed inactive / revoked |
| `error` | Validation encountered an error |
| `no_validator` | No validator registered for this secret type |

## Interpreting Results

- **`valid`**: Strong evidence the secret is active. Weight this heavily in scoring.
- **`invalid`**: Strong evidence the secret is revoked or inactive. Weight this heavily in scoring.
- **`error`**: The validator encountered a problem (e.g. network timeout). Do **not** treat this as conclusive — fall back to manual verification techniques.
- **`no_validator`**: Expected for most secret types. Proceed with standard manual verification techniques described in other skills.

## Important Notes

- Deterministic validation is **supplementary** — it does not replace the full analysis methodology.
- Most secret types will return `no_validator`. This is normal.
- Never skip other verification steps just because a validator exists.
- The validator set may grow over time as the open-source `validate-secrets` project adds support for more secret types.
