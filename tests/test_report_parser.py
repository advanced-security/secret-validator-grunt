from secret_validator_grunt.models.report import Report

SAMPLE_MD = """
## Executive Summary

| Item             | Value                                             |
| ---------------- | ------------------------------------------------- |
| Repository       | org/repo                                         |
| Alert ID         | 123                                              |
| Secret Type      | github_token                                     |
| Verdict          | TRUE_POSITIVE                                    |
| Confidence Score | 9/10 (High)                                      |
| Risk Level       | High                                             |
| Status           | Open                                             |
| Analyst          | Alice                                            |
| Report Date      | 2025-01-01                                       |

> **Key Finding:** Something important
"""


def test_report_from_markdown_parses_summary():
	r = Report.from_markdown(SAMPLE_MD)
	assert r.alert_id == "123"
	assert r.repository == "org/repo"
	assert r.verdict == "TRUE_POSITIVE"
	assert r.confidence_score == 9
	assert r.confidence_label == "High"
	assert r.risk_level == "High"
	assert r.key_finding == "Something important"
