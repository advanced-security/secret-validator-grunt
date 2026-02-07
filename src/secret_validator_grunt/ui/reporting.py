"""
Report rendering and persistence utilities.

Provides functions for rendering Report models to markdown
and saving report content to disk.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

from secret_validator_grunt.models.report import Report

REPORT_TEMPLATE = Template("""# Secret Validation Report: Alert ID ${alert_id}

## Executive Summary

| Item             | Value                                             |
| ---------------- | ------------------------------------------------- |
| Repository       | ${repository}                                     |
| Alert ID         | ${alert_id}                                      |
| Secret Type      | ${secret_type}                                    |
| Verdict          | ${verdict}                                        |
| Confidence Score | ${confidence_score} (${confidence_label})         |
| Risk Level       | ${risk_level}                                     |
| Status           | ${status}                                         |
| Analyst          | ${analyst}                                        |
| Report Date      | ${report_date}                                    |

> **Key Finding:** ${key_finding}
""")


def render_report_md(report: Report) -> str:
	"""
	Render a markdown report from a Report model.

	Parameters:
		report: The Report model to render.

	Returns:
		Rendered markdown string.
	"""
	data = {
	    "alert_id": report.alert_id or "",
	    "repository": report.repository or "",
	    "secret_type": report.secret_type or "",
	    "verdict": report.verdict or "",
	    "confidence_score": report.confidence_score or "",
	    "confidence_label": report.confidence_label or "",
	    "risk_level": report.risk_level or "",
	    "status": report.status or "",
	    "analyst": report.analyst or "",
	    "report_date": report.report_date or "",
	    "key_finding": report.key_finding or "",
	}
	return REPORT_TEMPLATE.safe_substitute(**data)


def save_report_md(path: Path | str, content: str) -> None:
	"""
	Persist markdown content to disk, ensuring parent directories.

	Parameters:
		path: Destination file path.
		content: Markdown content to write.
	"""
	Path(path).parent.mkdir(parents=True, exist_ok=True)
	Path(path).write_text(content, encoding="utf-8")


__all__ = ["render_report_md", "save_report_md"]
