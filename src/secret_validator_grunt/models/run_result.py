"""
Agent run result model.

Defines the AgentRunResult Pydantic model representing
the output of a single agent analysis session.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .report import Report
from .usage import UsageStats
from .skill_usage import SkillUsageStats
from .tool_usage import ToolUsageStats


class AgentRunResult(BaseModel):
	"""
	Result of a single agent run.

	Contains the parsed report, raw markdown output,
	workspace path, and any error information.
	"""

	run_id: str
	workspace: str | None = None
	report: Report | None = None
	raw_markdown: str | None = None
	progress_log: list[str] = Field(default_factory=list)
	error: str | None = None
	usage: UsageStats | None = None
	skill_usage: SkillUsageStats | None = None
	tool_usage: ToolUsageStats | None = None


__all__ = ["AgentRunResult"]
