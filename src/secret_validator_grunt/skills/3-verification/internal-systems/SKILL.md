---
name: internal-systems
description: Guidelines for testing secrets that provide access to internal systems and networks.
phase: 3-verification
---

# Internal Systems Verification

This skill provides guidance for validating secrets that target internal systems, networks, or services that may not be accessible from the analysis environment.

## Identifying Internal Systems

Common indicators of internal systems:

| Pattern | Example | Indicates |
|---------|---------|-----------|
| Internal domain | `*.internal.company.com` | Private DNS |
| Private IP ranges | `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x` | Internal network |
| Non-standard ports | `:8080`, `:3000`, `:9200` | Internal services |
| VPN-only hosts | `vpn.company.com` | Restricted access |
| Cloud internal | `*.svc.cluster.local` | Kubernetes internal |

## Testing Approach

### Step 1: DNS Resolution Test

First, check if the hostname resolves:

```bash
# Check DNS resolution
host target-hostname.internal.company.com

# Or with more detail
nslookup target-hostname.internal.company.com

# Python alternative
python3 -c "import socket; print(socket.gethostbyname('target-hostname'))"
```

### Step 2: Network Connectivity Test

If DNS resolves, test network connectivity:

```bash
# Test TCP connectivity
nc -zv hostname port

# Or with timeout
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/hostname/port' && echo "Open" || echo "Closed"

# Python alternative
python3 -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('hostname', port)); print('Connected')"
```

### Step 3: Interpret Results

| DNS Result | Network Result | Interpretation |
|------------|----------------|----------------|
| Resolves | Connects | External/accessible - proceed with auth test |
| Resolves | Timeout | Internal/firewalled - INCONCLUSIVE |
| Resolves | Refused | Service down or wrong port - INCONCLUSIVE |
| No resolve | N/A | Internal DNS or non-existent - INCONCLUSIVE |

## Handling Unreachable Systems

When you cannot reach the target system:

1. **Document the limitation** - Note that verification was not possible due to network restrictions
2. **Analyze credential format** - Validate the credential format matches expected patterns
3. **Context-based assessment** - Use code context to assess likelihood of validity
4. **Mark as INCONCLUSIVE** - Unless other evidence strongly suggests validity

## Evidence to Collect

Even when systems are unreachable, document:

- DNS resolution attempts and results
- Network connectivity test results
- Error messages and timeouts
- Any partial connectivity information

## Confidence Impact

Unreachable internal systems typically reduce confidence scores:

| Factor | Impact |
|--------|--------|
| Verification Confidence | Lower (cannot directly test) |
| Test Results | Lower (no test possible) |
| Directness | Lower (inferring from context) |

## Report Guidance

In your report, clearly state:

- The target was identified as an internal system
- What tests were attempted and their results
- Why verification could not be completed
- Recommendation based on available evidence

## Common Internal Secret Types

| Secret Type | Typical Target |
|-------------|----------------|
| Database credentials | Internal databases, data warehouses |
| API keys | Internal microservices |
| SSH keys | Internal servers, jump hosts |
| Basic auth | Internal dashboards, admin panels |
