from secret_validator_grunt.models.report import Report

SAMPLE = """
## Executive Summary

| Item             | Value                                             |
| ---------------- | ------------------------------------------------- |
| Repository       | org/repo                                         |
| Alert ID         | 123                                              |
| Secret Type      | github_token                                     |
| Verdict          | TRUE_POSITIVE                                    |
| Confidence Score | 11/10 (High)                                     |
| Risk Level       | High                                             |
| Status           | Open                                             |
| Analyst          | Alice                                            |
| Report Date      | 2025-01-01                                       |

> **Key Finding:** Something important

## Verification Testing

| #   | Test          | Method             | Result       | Evidence     |
| --- | ------------- | ------------------ | ------------ | ------------ |
| 1   | test name     | CLI                | PASS         | link         |

## Confidence Scoring

| Factor | Score | Rationale |
| ------ | ----- | --------- |
| Recency | 12 | too high |
| Directness | -1 | too low |

## Risk Assessment

| Risk Factor       | Assessment |
| ----------------- | ---------- |
| Exploitability    | High       |
| Service Exposure  | Low        |
"""


def test_report_parses_tables_and_bounds_scores():
	r = Report.from_markdown(SAMPLE)
	assert r.verification_tests is not None
	assert len(r.verification_tests) == 1
	assert r.confidence_scoring is not None
	assert len(r.confidence_scoring) == 2
	# bounded 0-10
	assert all(0.0 <= sc.score <= 10.0 for sc in r.confidence_scoring)
	assert r.confidence_scoring[0].score == 10.0
	assert r.confidence_scoring[1].score == 0.0
	assert r.risk_assessment_table is not None
	assert r.risk_assessment_table[0]["Risk Factor"] == "Exploitability"
