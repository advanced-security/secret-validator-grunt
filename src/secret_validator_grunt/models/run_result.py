"""
Agent run result model.

Defines the AgentRunResult Pydantic model representing
the output of a single agent analysis session.
"""

from __future__ import annotations

from typing import List, Optional
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
	workspace: Optional[str] = None
	report: Optional[Report] = None
	raw_markdown: Optional[str] = None
	progress_log: List[str] = Field(default_factory=list)
	error: Optional[str] = None
	usage: Optional[UsageStats] = None
	skill_usage: Optional[SkillUsageStats] = None
	tool_usage: Optional[ToolUsageStats] = None


__all__ = ["AgentRunResult"]
