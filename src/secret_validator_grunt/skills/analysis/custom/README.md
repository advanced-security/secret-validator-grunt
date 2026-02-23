# Custom Skills

This directory is for organization-specific or user-defined skills that extend the validation capabilities.

## Adding Custom Skills

To add a custom skill:

1. Create a new directory under `custom/` with your skill name
2. Add a `SKILL.md` file with the required frontmatter

### Directory Structure

```
custom/
├── README.md              # This file
├── my-custom-skill/
│   └── SKILL.md           # Your skill definition
└── org-internal-systems/
    └── SKILL.md           # Another custom skill
```

### SKILL.md Format

Every skill must have this frontmatter format:

```markdown
---
name: my-custom-skill
description: Brief description of what this skill provides
phase: 3-verification          # Optional: which phase this skill applies to
secret-type: custom_type       # Optional: specific secret type
---

# Skill Title

Your skill content goes here...
```

### Required Fields

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique skill identifier (lowercase, hyphens) |
| `description` | Yes | Brief description (shown in manifest) |
| `phase` | No | Which validation phase (1-4) this applies to |
| `secret-type` | No | Specific secret type this skill handles |

## Example: Organization-Specific Internal Domains

```markdown
---
name: org-internal-domains
description: Organization-specific internal domain patterns and testing guidance
phase: 3-verification
---

# Organization Internal Domains

## Recognized Internal Patterns

These domains are internal to our organization:

| Pattern | Purpose |
| ------- | ------- |
| `*.internal.myorg.com` | Internal services |
| `*.corp.myorg.com` | Corporate network |
| `10.50.x.x` | VPN range |

## Testing Guidelines

When testing secrets targeting these domains:

1. Ensure you're connected to VPN
2. Use the internal DNS servers
3. Contact SecOps if access is needed

## Contact

For questions about internal systems access, contact: security@myorg.com
```

## Example: Custom Secret Type

```markdown
---
name: myorg-api-key
description: Verification guide for MyOrg proprietary API keys
phase: 3-verification
secret-type: myorg_api_key
---

# MyOrg API Key Verification

## Key Format

MyOrg API keys follow this format:
- Prefix: `myorg_`
- Length: 40 characters
- Pattern: `myorg_[a-zA-Z0-9]{36}`

## Verification Endpoint

Test keys against:
```
https://api.myorg.com/v1/auth/validate
```

## Required Headers

```
X-API-Key: <your-key>
X-Client-ID: validator
```
```

## Skill Discovery

Custom skills are automatically discovered when:

1. They are in a subdirectory of `custom/`
2. They contain a valid `SKILL.md` file
3. The SKILL.md has required frontmatter

The skill manifest generator scans this directory at runtime and includes all valid skills.

## Best Practices

1. **Keep skills focused** - One skill per specific topic
2. **Include examples** - Show code/commands that work
3. **Document edge cases** - What to do when things fail
4. **Version your changes** - Track updates to custom skills
5. **Test before deploying** - Verify skills work as expected

## Sharing Skills

To share custom skills with your team:

1. Add skills to version control (if not containing secrets)
2. Set `SKILL_DIRECTORIES` environment variable to include paths
3. Document any prerequisites or dependencies
