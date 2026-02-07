"""
Skill manifest models.

Defines Pydantic models for skill discovery and manifest generation.
These models represent the metadata extracted from SKILL.md files
and the complete manifest of available skills.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SkillInfo(BaseModel):
	"""
	Information about a single skill.

	Contains metadata extracted from skill SKILL.md frontmatter.

	Attributes:
		name: The skill name.
		description: A brief description of the skill.
		path: Absolute path to the SKILL.md file.
		phase: The workflow phase this skill belongs to.
		secret_type: The secret type this skill applies to.
		required: Whether this skill must be loaded (vs optional).
	"""

	name: str = Field(description="Skill name")
	description: str = Field(default="", description="Skill description")
	path: str = Field(description="Absolute path to SKILL.md")
	phase: Optional[str] = Field(default=None,
	                             description="Phase this skill belongs to")
	secret_type: Optional[str] = Field(
	    default=None, description="Secret type this skill applies to")
	required: bool = Field(default=False,
	                       description="Whether this skill must be loaded")

	def to_dict(self) -> dict[str, Any]:
		"""
		Convert to dictionary representation.

		Returns:
			Dictionary with skill metadata, excluding None values.
		"""
		result: dict[str, Any] = {
		    "name": self.name,
		    "description": self.description,
		    "path": self.path,
		}
		if self.phase:
			result["phase"] = self.phase
		if self.secret_type:
			result["secret_type"] = self.secret_type
		if self.required:
			result["required"] = self.required
		return result


class SkillManifest(BaseModel):
	"""
	Manifest of all discovered skills.

	Contains the complete list of skills organized by phase.

	Attributes:
		skills: List of discovered skill information.
		phases: Sorted list of unique phase names.
		generated_at: ISO timestamp of when the manifest was generated.
	"""

	skills: List[SkillInfo] = Field(default_factory=list)
	phases: List[str] = Field(default_factory=list)
	generated_at: str = Field(
	    default_factory=lambda: datetime.now(timezone.utc).isoformat())

	def to_dict(self) -> dict[str, Any]:
		"""
		Convert to dictionary representation.

		Returns:
			Dictionary with all manifest data.
		"""
		return {
		    "skills": [s.to_dict() for s in self.skills],
		    "phases": self.phases,
		    "generated_at": self.generated_at,
		}


__all__ = ["SkillInfo", "SkillManifest"]
