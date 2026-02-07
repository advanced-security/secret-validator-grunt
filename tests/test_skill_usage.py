"""Tests for skill usage tracking models."""

import pytest

from secret_validator_grunt.models.skill_usage import (
	SkillLoadEvent,
	SkillLoadStatus,
	SkillUsageStats,
)


class TestSkillLoadEvent:
	"""Tests for SkillLoadEvent model."""

	def test_create_load_event_with_defaults(self) -> None:
		"""SkillLoadEvent should create with minimal required fields."""
		event = SkillLoadEvent(
		    skill_name="test-skill",
		    status=SkillLoadStatus.LOADED,
		)
		assert event.skill_name == "test-skill"
		assert event.status == SkillLoadStatus.LOADED
		assert event.timestamp is not None
		assert event.phase is None
		assert event.is_required is False
		assert event.error_message is None
		assert event.duration_ms is None

	def test_create_load_event_with_all_fields(self) -> None:
		"""SkillLoadEvent should accept all optional fields."""
		event = SkillLoadEvent(
		    skill_name="github-api-usage",
		    status=SkillLoadStatus.LOADED,
		    timestamp="2026-02-05T10:00:00Z",
		    phase="1-initialization",
		    is_required=True,
		    error_message=None,
		    duration_ms=150.5,
		)
		assert event.skill_name == "github-api-usage"
		assert event.phase == "1-initialization"
		assert event.is_required is True
		assert event.duration_ms == 150.5

	def test_create_failed_event_with_error(self) -> None:
		"""SkillLoadEvent should store error message for failed loads."""
		event = SkillLoadEvent(
		    skill_name="nonexistent-skill",
		    status=SkillLoadStatus.NOT_FOUND,
		    error_message="Skill not found in any registered directory",
		)
		assert event.status == SkillLoadStatus.NOT_FOUND
		assert event.error_message == "Skill not found in any registered directory"


class TestSkillUsageStats:
	"""Tests for SkillUsageStats model."""

	def test_create_empty_stats(self) -> None:
		"""SkillUsageStats should create with empty lists by default."""
		stats = SkillUsageStats()
		assert stats.available_skills == []
		assert stats.required_skills == []
		assert stats.disabled_skills == []
		assert stats.loaded_skills == []
		assert stats.failed_skills == []
		assert stats.skipped_required == []
		assert stats.load_events == []

	def test_add_load_event_updates_loaded_skills(self) -> None:
		"""Adding a successful load event updates loaded_skills list."""
		stats = SkillUsageStats(
		    available_skills=["a", "b"],
		    required_skills=["a"],
		)
		stats.add_load_event("a", SkillLoadStatus.LOADED, is_required=True)

		assert "a" in stats.loaded_skills
		assert len(stats.load_events) == 1
		assert stats.load_events[0].skill_name == "a"
		assert stats.load_events[0].status == SkillLoadStatus.LOADED

	def test_add_load_event_failed_updates_failed_skills(self) -> None:
		"""Adding a failed load event updates failed_skills list."""
		stats = SkillUsageStats(available_skills=["a", "b"])
		stats.add_load_event(
		    "a",
		    SkillLoadStatus.FAILED,
		    error_message="Connection timeout",
		)

		assert "a" in stats.failed_skills
		assert "a" not in stats.loaded_skills
		assert stats.load_events[0].error_message == "Connection timeout"

	def test_add_load_event_deduplicates_loaded(self) -> None:
		"""Adding same skill multiple times should not duplicate in loaded_skills."""
		stats = SkillUsageStats()
		stats.add_load_event("a", SkillLoadStatus.LOADED)
		stats.add_load_event("a", SkillLoadStatus.LOADED)

		assert stats.loaded_skills == ["a"]
		# But events should still be recorded
		assert len(stats.load_events) == 2

	def test_compliance_score_with_no_required(self) -> None:
		"""Compliance score is 100% when no skills are required."""
		stats = SkillUsageStats(
		    available_skills=["a", "b", "c"],
		    required_skills=[],
		    loaded_skills=["a"],
		)
		assert stats.compliance_score == 100.0

	def test_compliance_score_with_all_required_loaded(self) -> None:
		"""Compliance score is 100% when all required skills are loaded."""
		stats = SkillUsageStats(
		    available_skills=["a", "b", "c"],
		    required_skills=["a", "b"],
		    loaded_skills=["a", "b", "c"],
		)
		assert stats.compliance_score == 100.0

	def test_compliance_score_with_partial_required(self) -> None:
		"""Compliance score reflects percentage of required skills loaded."""
		stats = SkillUsageStats(
		    available_skills=["a", "b", "c", "d"],
		    required_skills=["a", "b"],
		    loaded_skills=["a"],
		)
		assert stats.compliance_score == 50.0

	def test_compliance_score_with_none_required_loaded(self) -> None:
		"""Compliance score is 0% when no required skills are loaded."""
		stats = SkillUsageStats(
		    available_skills=["a", "b", "c"],
		    required_skills=["a", "b"],
		    loaded_skills=["c"],
		)
		assert stats.compliance_score == 0.0

	def test_finalize_populates_skipped_required(self) -> None:
		"""Finalize computes which required skills were not loaded."""
		stats = SkillUsageStats(
		    available_skills=["a", "b", "c"],
		    required_skills=["a", "b"],
		    loaded_skills=["a"],
		)
		stats.finalize()

		assert stats.skipped_required == ["b"]

	def test_finalize_empty_when_all_loaded(self) -> None:
		"""Finalize results in empty skipped_required when all required loaded."""
		stats = SkillUsageStats(
		    required_skills=["a", "b"],
		    loaded_skills=["a", "b", "c"],
		)
		stats.finalize()

		assert stats.skipped_required == []

	def test_add_event_with_phase(self) -> None:
		"""add_load_event should record phase information."""
		stats = SkillUsageStats()
		stats.add_load_event(
		    "github-api-usage",
		    SkillLoadStatus.LOADED,
		    phase="1-initialization",
		    is_required=True,
		)

		assert len(stats.load_events) == 1
		assert stats.load_events[0].phase == "1-initialization"
		assert stats.load_events[0].is_required is True

	def test_add_event_with_duration(self) -> None:
		"""add_load_event should record duration information."""
		stats = SkillUsageStats()
		stats.add_load_event(
		    "code-analysis",
		    SkillLoadStatus.LOADED,
		    duration_ms=250.5,
		)

		assert stats.load_events[0].duration_ms == 250.5


class TestSkillLoadStatus:
	"""Tests for SkillLoadStatus enum."""

	def test_status_values(self) -> None:
		"""SkillLoadStatus should have expected string values."""
		assert SkillLoadStatus.LOADED.value == "loaded"
		assert SkillLoadStatus.FAILED.value == "failed"
		assert SkillLoadStatus.DISABLED.value == "disabled"
		assert SkillLoadStatus.NOT_FOUND.value == "not_found"

	def test_status_is_str_enum(self) -> None:
		"""SkillLoadStatus should be usable as string via .value."""
		status = SkillLoadStatus.LOADED
		assert f"Status: {status.value}" == "Status: loaded"


class TestSkillUsagePhaseTracking:
	"""Tests for phase-related methods on SkillUsageStats."""

	def test_loaded_by_phase_empty(self) -> None:
		"""loaded_by_phase returns empty dict when no events."""
		stats = SkillUsageStats()
		assert stats.loaded_by_phase() == {}

	def test_loaded_by_phase_groups_correctly(self) -> None:
		"""loaded_by_phase groups loaded skills by their phase."""
		stats = SkillUsageStats()
		stats.add_load_event(
		    "testing-environment",
		    SkillLoadStatus.LOADED,
		    phase="1-initialization",
		)
		stats.add_load_event(
		    "github-api-usage",
		    SkillLoadStatus.LOADED,
		    phase="1-initialization",
		)
		stats.add_load_event(
		    "code-analysis",
		    SkillLoadStatus.LOADED,
		    phase="2-context-gathering",
		)

		by_phase = stats.loaded_by_phase()
		assert len(by_phase) == 2
		assert by_phase["1-initialization"] == [
		    "testing-environment",
		    "github-api-usage",
		]
		assert by_phase["2-context-gathering"] == ["code-analysis"]

	def test_loaded_by_phase_excludes_failures(self) -> None:
		"""loaded_by_phase excludes skills that failed to load."""
		stats = SkillUsageStats()
		stats.add_load_event(
		    "good-skill",
		    SkillLoadStatus.LOADED,
		    phase="1-init",
		)
		stats.add_load_event(
		    "bad-skill",
		    SkillLoadStatus.FAILED,
		    phase="1-init",
		    error_message="timeout",
		)

		by_phase = stats.loaded_by_phase()
		assert by_phase == {"1-init": ["good-skill"]}

	def test_loaded_by_phase_excludes_no_phase(self) -> None:
		"""loaded_by_phase excludes skills with no phase."""
		stats = SkillUsageStats()
		stats.add_load_event(
		    "orphan-skill",
		    SkillLoadStatus.LOADED,
		    phase=None,
		)

		assert stats.loaded_by_phase() == {}

	def test_available_by_phase_empty(self) -> None:
		"""available_by_phase returns empty when no phase_map."""
		stats = SkillUsageStats(available_skills=["a", "b"])
		assert stats.available_by_phase() == {}

	def test_available_by_phase_groups_correctly(self) -> None:
		"""available_by_phase uses phase_map to group skills."""
		stats = SkillUsageStats(
		    available_skills=[
		        "testing-environment",
		        "github-api-usage",
		        "code-analysis",
		    ],
		    phase_map={
		        "testing-environment": "1-initialization",
		        "github-api-usage": "1-initialization",
		        "code-analysis": "2-context-gathering",
		    },
		)

		by_phase = stats.available_by_phase()
		assert len(by_phase) == 2
		assert by_phase["1-initialization"] == [
		    "testing-environment",
		    "github-api-usage",
		]
		assert by_phase["2-context-gathering"] == ["code-analysis"]

	def test_available_by_phase_excludes_unmapped(self) -> None:
		"""available_by_phase skips skills not in phase_map."""
		stats = SkillUsageStats(
		    available_skills=["mapped", "unmapped"],
		    phase_map={"mapped": "1-init"},
		)

		by_phase = stats.available_by_phase()
		assert by_phase == {"1-init": ["mapped"]}

	def test_phase_map_persists_in_model_dump(self) -> None:
		"""phase_map is included in serialized model dump."""
		stats = SkillUsageStats(
		    phase_map={"a": "phase-1", "b": "phase-2"},
		)
		dump = stats.model_dump()
		assert dump["phase_map"] == {"a": "phase-1", "b": "phase-2"}
