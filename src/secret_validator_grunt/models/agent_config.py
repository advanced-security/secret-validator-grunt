from __future__ import annotations
"""
Agent configuration model.

Defines the AgentConfig Pydantic model for agent definitions
loaded from markdown frontmatter.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
	"""Agent configuration loaded from markdown frontmatter."""

	name: str = Field(description="Agent name")
	description: Optional[str] = Field(
	    default=None, description="Short description of the agent")
	argument_hint: Optional[str] = Field(
	    default=None, description="Argument hint for display")
	tools: List[str] = Field(default_factory=list,
	                         description="Available tools")
	model: Optional[str] = Field(default=None,
	                             description="Override model name")
	report_template: Optional[str] = Field(
	    default=None, description="Optional report template body")
	prompt: str = Field(description="Agent prompt body content")


__all__ = ["AgentConfig"]
