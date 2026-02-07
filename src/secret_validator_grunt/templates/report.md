# Secret Validation Report: Alert ID {{alert_id}}

## Executive Summary

| Item             | Value                                             |
| ---------------- | ------------------------------------------------- |
| Repository       | {{org/repo}}                                      |
| Alert ID         | {{alert_id}}                                      |
| Secret Type      | {{type}}                                          |
| Verdict          | {{TRUE_POSITIVE / FALSE_POSITIVE / INCONCLUSIVE}} |
| Confidence Score | {{X/10}} ({{High/Medium/Low}})                    |
| Risk Level       | {{High/Medium/Low/None}}                          |
| Status           | {{Open/Closed}}                                   |
| Analyst          | {{name}}                                          |
| Report Date      | {{YYYY-MM-DD}}                                    |

> **Key Finding:** {{1–2 sentence decisive statement}}

---

## 1. Secret Alert Details

- **Secret Type:** {{type}}
- **Detection Date:** {{date}}
- **Alert State:** {{open/closed}}
- **Validity (per GH):** {{unknown/valid/invalid}}
- **First Location:** `{{path}}` (line {{n}})
- **Commit SHA/Date/Author:** {{sha}} / {{date}} / {{author}}
- **Secret Value Summary:** {{format description; omit raw value unless necessary for crypto}}

---

## 2. Locations

| Path     | Line     | Commit  | Notes       |
| -------- | -------- | ------- | ----------- |
| {{path}} | {{line}} | {{sha}} | {{context}} |
| ...      | ...      | ...     | ...         |

---

## 3. Context and Intent

- **Repository Purpose:** {{training/production/etc}}
- **Application/Service Context:** {{summary}}
- **Integration Points:** {{files, functions, services}}
- **Intent Indicators:** {{comments, naming, docs}}
- **Tech Stack:** {{lang, frameworks, services}}

---

## 4. Verification Testing

| #   | Test          | Method             | Result       | Evidence     |
| --- | ------------- | ------------------ | ------------ | ------------ |
| 1   | {{test name}} | {{CLI/SDK/script}} | {{ result }} | {{link/log}} |
| ... | ...           | ...                | ...          | ...          |

**Scripts/Commands:**

```bash
# key commands here
```

```python
# key snippets here
```

### Artifacts

| Artifact   | Path/Link |
| ---------- | --------- |
| {{ name }} | {{path}}  |

---

## 5. Documentary Evidence

- **Docs:** {{provider docs URLs}}
- **Code Snippets:** {{paths/line refs}}
- **Log Files:** {{paths}}
- **Artifacts:** {{files produced}}

---

## 6. Evidence Analysis

| Dimension   | Finding     | Confidence |
| ----------- | ----------- | ---------- |
| Technical   | {{summary}} | {{%}}      |
| Documentary | {{summary}} | {{%}}      |
| Contextual  | {{summary}} | {{%}}      |
| Historical  | {{summary}} | {{%}}      |

---

## 7. Confidence Scoring (0–10 each)

| Factor                  | Score | Rationale |
| ----------------------- | ----- | --------- |
| Recency                 | {{}}  | {{}}      |
| Directness              | {{}}  | {{}}      |
| Completeness            | {{}}  | {{}}      |
| Source Reliability      | {{}}  | {{}}      |
| Verification Confidence | {{}}  | {{}}      |
| Test Results            | {{}}  | {{}}      |
| Findings Review         | {{}}  | {{}}      |

**Average:** **{{X/10}}** → **{{High/Medium/Low}}**

---

## 8. Risk Assessment

| Risk Factor       | Assessment |
| ----------------- | ---------- |
| Exploitability    | {{}}       |
| Service Exposure  | {{}}       |
| Rotation Evidence | {{}}       |
| Mitigations       | {{}}       |

---

## 9. Verdict

- **Verdict:** {{TRUE_POSITIVE / FALSE_POSITIVE / INCONCLUSIVE}}
- **Immediate Actions:** {{rotate/close alert/update docs}}
- **Follow-ups:** {{git history cleanup, rules, training}}
- **Config Suggestions:** {{secret scanning ignores, rules}}

---

## Appendix

### A Methodology Checklist

- {{ steps followed }}
