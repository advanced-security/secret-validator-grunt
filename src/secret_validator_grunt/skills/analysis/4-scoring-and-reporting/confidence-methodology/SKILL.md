---
name: confidence-methodology
agent: analysis
description: Methodology for scoring confidence in secret validation findings.
phase: 4-scoring-and-reporting
required: true
---

# Confidence Scoring Methodology

This skill provides the established methodology for scoring confidence in your secret validation findings.

## Scoring Framework

The overall confidence score is calculated from seven factors, each scored 0-10:

| Factor | Description | Weight |
| ------ | ----------- | ------ |
| Recency | How recent is the information (commits, sources) | Equal |
| Directness | Direct evidence vs. inferred/indirect | Equal |
| Completeness | Full context vs. partial understanding | Equal |
| Source Reliability | Official docs vs. unofficial sources | Equal |
| Verification Confidence | Confidence in your test methodology | Equal |
| Test Results | Actual results from validation tests | Equal |
| Findings Review | First-principles review of conclusions | Equal |

## Scoring Guidelines

### Recency (0-10)

How recent is the evidence you're evaluating?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Data from last 7 days |
| 7-8 | Data from last 30 days |
| 5-6 | Data from last 90 days |
| 3-4 | Data from last year |
| 1-2 | Data older than 1 year |
| 0 | Cannot determine age |

### Directness (0-10)

Is your evidence direct or inferred?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Direct observation (e.g., auth test succeeded) |
| 7-8 | Strong direct evidence (e.g., code shows active use) |
| 5-6 | Indirect but clear evidence |
| 3-4 | Mostly inferred from context |
| 1-2 | Speculation based on patterns |
| 0 | No direct evidence available |

### Completeness (0-10)

How complete is your understanding of the context?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Full context: all files, all branches, all history |
| 7-8 | Most context gathered, minor gaps |
| 5-6 | Key context present, some areas unexplored |
| 3-4 | Partial context, significant gaps |
| 1-2 | Minimal context, mostly unknown |
| 0 | No context available |

### Source Reliability (0-10)

How reliable are your information sources?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Official documentation, verified APIs |
| 7-8 | Reputable sources, official examples |
| 5-6 | Community sources, Stack Overflow answers |
| 3-4 | Unofficial sources, blog posts |
| 1-2 | Unverified sources |
| 0 | No external sources consulted |

### Verification Confidence (0-10)

How confident are you in your verification approach?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Standard verification method, well-documented |
| 7-8 | Solid approach with minor uncertainties |
| 5-6 | Reasonable approach, some assumptions |
| 3-4 | Approach has significant limitations |
| 1-2 | Verification method questionable |
| 0 | Could not verify at all |

### Test Results (0-10)

What did your actual tests show?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Clear positive/negative result from tests |
| 7-8 | Strong test results with minor ambiguity |
| 5-6 | Tests ran but results ambiguous |
| 3-4 | Limited testing possible |
| 1-2 | Tests failed/inconclusive |
| 0 | Could not run tests |

### Findings Review (0-10)

Did first-principles review confirm your findings?

| Score | Criteria |
| ----- | -------- |
| 9-10 | Review confirms all findings, no contradictions |
| 7-8 | Review mostly confirms, minor concerns addressed |
| 5-6 | Review shows some gaps, conclusions still hold |
| 3-4 | Review reveals significant issues |
| 1-2 | Review contradicts initial findings |
| 0 | No review conducted |

## Calculating Overall Score

### Simple Average

```
Overall Score = (Recency + Directness + Completeness + Source Reliability 
                + Verification Confidence + Test Results + Findings Review) / 7
```

### Confidence Level Mapping

| Average Score | Confidence Level |
| ------------- | ---------------- |
| 8.0 - 10.0 | High |
| 5.0 - 7.9 | Medium |
| 0.0 - 4.9 | Low |

## Report Format

Include this table in Section 7 of your report:

```markdown
## 7. Confidence Scoring (0–10 each)

| Factor                  | Score | Rationale                                        |
| ----------------------- | ----- | ------------------------------------------------ |
| Recency                 | 8     | Alert detected within last 7 days                |
| Directness              | 9     | Credential directly present in source code       |
| Completeness            | 7     | Full context gathered, minor gaps in history     |
| Source Reliability      | 8     | Official GitHub API and documentation used       |
| Verification Confidence | 5     | Cannot test internal endpoint                    |
| Test Results            | 6     | Format valid; endpoint unreachable               |
| Findings Review         | 7     | Review confirms exposure, password strength low  |

**Average:** **7.1/10** → **Medium**
```

## Evidence Requirements

For each score, document:

1. **What evidence supports this score?**
2. **What would increase/decrease this score?**
3. **Any caveats or uncertainties?**

### Strong Evidence Examples

- API response confirming authentication
- Code showing active use of secret
- Documentation confirming secret format
- Test results with clear pass/fail

### Weak Evidence Examples

- Assumptions about code behavior
- Inferences from naming conventions
- Undocumented or unclear patterns
- Inconclusive test results

## Verdict Decision Matrix

Combine confidence score with risk level for final verdict:

| Confidence | Risk Evidence | Recommended Verdict |
| ---------- | ------------- | ------------------- |
| High | Strong risk indicators | TRUE_POSITIVE |
| High | No risk indicators | FALSE_POSITIVE |
| Medium | Strong risk indicators | TRUE_POSITIVE |
| Medium | No risk indicators | INCONCLUSIVE |
| Low | Any | INCONCLUSIVE |

## Quality Checklist

Before finalizing your confidence score:

- [ ] All seven factors scored with rationale
- [ ] Evidence documented for each score
- [ ] Average calculated correctly
- [ ] Confidence level mapped appropriately
- [ ] Verdict consistent with confidence level
