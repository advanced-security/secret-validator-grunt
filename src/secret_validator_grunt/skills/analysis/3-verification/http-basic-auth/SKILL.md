---
name: http-basic-auth
agent: analysis
description: Verification guide specific to HTTP Basic Authentication credentials.
phase: 3-verification
secret-type: http_basic_authentication_header
---

# HTTP Basic Authentication Verification

This skill provides specific guidance for validating HTTP Basic Authentication credentials.

## Secret Format

HTTP Basic Auth credentials appear as:

| Format | Example |
| ------ | ------- |
| Base64 encoded | `YmlsbHk6c2VjcmV0cGFzc3dvcmQ=` |
| Decoded | `username:password` |
| In header | `Authorization: Basic YmlsbHk6c2VjcmV0cGFzc3dvcmQ=` |

## Quick Decode

```bash
# Decode base64 to see username:password
echo "YmlsbHk6c2VjcmV0cGFzc3dvcmQ=" | base64 -d
# Output: billy:secretpassword
```

## Identification Patterns

HTTP Basic Auth appears in code as:

### JavaScript/jQuery

```javascript
xhr.setRequestHeader('Authorization', 'Basic YmlsbHk6c2VjcmV0cGFzc3dvcmQ=');

// or
$.ajax({
  beforeSend: function(xhr) {
    xhr.setRequestHeader('Authorization', 'Basic ' + btoa(user + ':' + pass));
  }
});
```

### Python (requests)

```python
import requests
response = requests.get(url, auth=('username', 'password'))

# or explicit header
headers = {'Authorization': 'Basic YmlsbHk6c2VjcmV0cGFzc3dvcmQ='}
response = requests.get(url, headers=headers)
```

### cURL

```bash
curl -u username:password https://api.example.com/
# or
curl -H "Authorization: Basic YmlsbHk6c2VjcmV0cGFzc3dvcmQ=" https://api.example.com/
```

## Verification Steps

### Step 1: Decode the Credential

```bash
# Decode and parse
ENCODED="YmlsbHk6c2VjcmV0cGFzc3dvcmQ="
DECODED=$(echo "$ENCODED" | base64 -d)
USERNAME=$(echo "$DECODED" | cut -d: -f1)
PASSWORD=$(echo "$DECODED" | cut -d: -f2-)

echo "Username: $USERNAME"
echo "Password: $PASSWORD"
```

### Step 2: Identify Target Endpoint

Look in the surrounding code for:

- URL being called with this header
- API endpoint patterns
- Configuration files with host/port

### Step 3: Test Authentication

```bash
# Using curl
curl -u "$USERNAME:$PASSWORD" "$TARGET_URL" -v

# Check response codes:
# 200-299: Auth successful (TRUE_POSITIVE)
# 401: Unauthorized (likely invalid/rotated)
# 403: Forbidden (valid user, no access)
```

## Python Validation Script

```python
#!/usr/bin/env python3
"""Validate HTTP Basic Authentication credentials."""

import base64
import requests
import json
import sys

def decode_basic_auth(encoded: str) -> tuple[str, str]:
    """Decode base64 Basic Auth to (username, password)."""
    decoded = base64.b64decode(encoded).decode('utf-8')
    username, password = decoded.split(':', 1)
    return username, password

def test_basic_auth(url: str, username: str, password: str) -> dict:
    """
    Test HTTP Basic Auth credentials against target URL.
    
    Returns:
        dict with test results
    """
    result = {
        "url": url,
        "username": username,
        "password_length": len(password),
        "valid": False,
    }
    
    try:
        response = requests.get(
            url,
            auth=(username, password),
            timeout=10,
            allow_redirects=False
        )
        
        result["status_code"] = response.status_code
        
        if response.status_code in [200, 201, 202, 204]:
            result["valid"] = True
            result["verdict"] = "TRUE_POSITIVE - Authentication successful"
        elif response.status_code == 401:
            result["valid"] = False
            result["verdict"] = "Likely FALSE_POSITIVE - Authentication failed (401)"
        elif response.status_code == 403:
            result["valid"] = True  # User exists but no permission
            result["verdict"] = "TRUE_POSITIVE - User authenticated but forbidden (403)"
        else:
            result["verdict"] = f"INCONCLUSIVE - Unexpected status {response.status_code}"
            
    except requests.exceptions.Timeout:
        result["error"] = "Connection timeout"
        result["verdict"] = "INCONCLUSIVE - Cannot reach endpoint"
    except requests.exceptions.ConnectionError as e:
        result["error"] = str(e)
        result["verdict"] = "INCONCLUSIVE - Connection failed"
    except Exception as e:
        result["error"] = str(e)
        result["verdict"] = f"ERROR - {e}"
    
    return result

if __name__ == "__main__":
    # Configuration
    ENCODED_CRED = "YmlsbHk6c2VjcmV0cGFzc3dvcmQ="
    TARGET_URL = "http://app1.internal.github.com/api/v1/method/"
    
    # Decode credential
    username, password = decode_basic_auth(ENCODED_CRED)
    print(f"Testing: {username}:{'*' * len(password)}")
    
    # Test
    result = test_basic_auth(TARGET_URL, username, password)
    
    # Output
    print(json.dumps(result, indent=2))
    
    # Exit code
    sys.exit(0 if result.get("valid") else 1)
```

## Result Interpretation

| Status Code | Meaning | Verdict |
| ----------- | ------- | ------- |
| 200-204 | Request successful | TRUE_POSITIVE |
| 401 | Unauthorized | Likely FALSE_POSITIVE (invalid/rotated) |
| 403 | Forbidden | TRUE_POSITIVE (valid user, no access) |
| 404 | Not Found | Check if endpoint exists |
| 5xx | Server Error | INCONCLUSIVE |
| Timeout | Connection timeout | INCONCLUSIVE (may be internal) |

## Common False Positive Indicators

- Username like `test`, `example`, `demo`, `admin`
- Password like `password`, `123456`, `changeme`
- Target URL is `localhost`, `127.0.0.1`, `example.com`
- Found in test files or documentation
- Commented out or in example code blocks

## Evidence for Report

Include in your report:

1. **Decoded credential format**: `username:password` (mask password in report)
2. **Target endpoint**: URL being authenticated against
3. **Test method**: curl/Python script/etc.
4. **Response codes**: What did the endpoint return?
5. **Verdict justification**: Why this is TRUE/FALSE positive

## Related Secret Types

Similar verification approach applies to:

- `http_bearer_token`
- `http_digest_auth`
- Custom header authentication
