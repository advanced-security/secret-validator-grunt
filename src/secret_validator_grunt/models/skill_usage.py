"""
Skill usage tracking models.

Defines Pydantic models for tracking skill loading events and
computing methodology compliance metrics during agent sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SkillLoadStatus(str, Enum):
	"""Status of a skill load attempt."""

	LOADED = "loaded"
	FAILED = "failed"
	DISABLED = "disabled"
	NOT_FOUND = "not_found"


class SkillLoadEvent(BaseModel):
	"""
	Record of a single skill load attempt.

	Attributes:
		skill_name: Name of the skill that was requested.
		status: Outcome of the load attempt.
		timestamp: ISO timestamp of when the event completed.
		phase: Workflow phase this skill belongs to (if known).
		is_required: Whether this skill was marked as required.
		error_message: Error details if the load failed.
		duration_ms: Time taken to load the skill in milliseconds.
	"""

	skill_name: str = Field(description="Name of the requested skill")
	status: SkillLoadStatus = Field(description="Load attempt outcome")
	timestamp: str = Field(
	    default_factory=lambda: datetime.now(timezone.utc).isoformat(),
	    description="ISO timestamp of completion",
	)
	phase: str | None = Field(default=None,
	                             description="Skill phase if known")
	is_required: bool = Field(default=False,
	                          description="Whether skill is required")
	error_message: str | None = Field(default=None,
	                                     description="Error if failed")
	duration_ms: float | None = Field(default=None,
	                                     description="Load duration in ms")


class SkillUsageStats(BaseModel):
	"""
	Aggregated skill usage statistics for a session.

	Tracks which skills were available, required, disabled, and actually
	loaded during an agent session. Provides compliance metrics.

	Attributes:
		available_skills: List of skill names in the manifest.
		required_skills: List of skill names marked as required.
		disabled_skills: List of skill names that were disabled.
		loaded_skills: List of skill names successfully loaded.
		failed_skills: List of skill names that failed to load.
		skipped_required: Required skills that were not loaded.
		load_events: Detailed log of all load attempts.
	"""

	available_skills: list[str] = Field(
	    default_factory=list,
	    description="Skills available in manifest",
	)
	required_skills: list[str] = Field(
	    default_factory=list,
	    description="Skills marked as required",
	)
	disabled_skills: list[str] = Field(
	    default_factory=list,
	    description="Skills that were disabled",
	)
	loaded_skills: list[str] = Field(
	    default_factory=list,
	    description="Skills successfully loaded",
	)
	failed_skills: list[str] = Field(
	    default_factory=list,
	    description="Skills that failed to load",
	)
	skipped_required: list[str] = Field(
	    default_factory=list,
	    description="Required skills not loaded",
	)
	load_events: list[SkillLoadEvent] = Field(
	    default_factory=list,
	    description="Detailed log of all load attempts",
	)
	phase_map: dict[str, str] = Field(
	    default_factory=dict,
	    description="Mapping of skill_name to phase from manifest",
	)

	@property
	def compliance_score(self) -> float:
		"""
		Calculate methodology compliance as percentage of required skills loaded.

		Returns:
			100.0 if no required skills, otherwise percentage loaded.
		"""
		if not self.required_skills:
			return 100.0
		loaded_required = set(self.loaded_skills) & set(self.required_skills)
		return (len(loaded_required) / len(self.required_skills)) * 100

	def loaded_by_phase(self) -> dict[str, list[str]]:
		"""
		Return loaded skills grouped by phase.

		Derives phase from load_events for skills that were loaded.

		Returns:
			Mapping of phase name to list of loaded skill names.
		"""
		result: dict[str, list[str]] = {}
		for event in self.load_events:
			if event.status == SkillLoadStatus.LOADED and event.phase:
				result.setdefault(event.phase, []).append(
				    event.skill_name,
				)
		return result

	def available_by_phase(self) -> dict[str, list[str]]:
		"""
		Return available skills grouped by phase.

		Uses phase_map to look up phases for all available skills.

		Returns:
			Mapping of phase name to list of available skill names.
		"""
		result: dict[str, list[str]] = {}
		for skill_name in self.available_skills:
			phase = self.phase_map.get(skill_name)
			if phase:
				result.setdefault(phase, []).append(skill_name)
		return result

	def add_load_event(
	    self,
	    skill_name: str,
	    status: SkillLoadStatus,
	    *,
	    phase: str | None = None,
	    is_required: bool = False,
	    error_message: str | None = None,
	    duration_ms: float | None = None,
	) -> None:
		"""
		Record a skill load event and update aggregated lists.

		Parameters:
			skill_name: Name of the skill.
			status: Outcome of the load attempt.
			phase: Workflow phase this skill belongs to.
			is_required: Whether this skill was marked as required.
			error_message: Error details if the load failed.
			duration_ms: Time taken to load the skill.
		"""
		event = SkillLoadEvent(
		    skill_name=skill_name,
		    status=status,
		    phase=phase,
		    is_required=is_required,
		    error_message=error_message,
		    duration_ms=duration_ms,
		)
		self.load_events.append(event)

		# Update aggregated lists based on status
		if status == SkillLoadStatus.LOADED:
			if skill_name not in self.loaded_skills:
				self.loaded_skills.append(skill_name)
		elif status in (SkillLoadStatus.FAILED, SkillLoadStatus.NOT_FOUND):
			if skill_name not in self.failed_skills:
				self.failed_skills.append(skill_name)

	def finalize(self) -> None:
		"""
		Compute derived fields after session completion.

		Populates skipped_required based on required_skills
		that were not successfully loaded.
		"""
		loaded_set = set(self.loaded_skills)
		required_set = set(self.required_skills)
		self.skipped_required = list(required_set - loaded_set)


__all__ = ["SkillLoadStatus", "SkillLoadEvent", "SkillUsageStats"]
