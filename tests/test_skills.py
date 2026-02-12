"""Tests for the skill discovery and manifest functions."""

from pathlib import Path

import pytest

from secret_validator_grunt.core.skills import (
    discover_skills,
    discover_hidden_skills,
    build_skill_manifest,
    format_manifest_for_context,
)


def test_discover_skills_ignores_underscore_prefixed(tmp_path: Path) -> None:
	"""Skills in underscore-prefixed directories should not be discovered."""
	# Create a visible skill
	visible = tmp_path / "visible-skill"
	visible.mkdir()
	(visible / "SKILL.md").write_text(
	    "---\nname: visible-skill\ndescription: A visible skill\n---\nContent")

	# Create a hidden skill (underscore prefix)
	hidden = tmp_path / "_hidden-skill"
	hidden.mkdir()
	(hidden / "SKILL.md").write_text(
	    "---\nname: hidden-skill\ndescription: A hidden skill\n---\nContent")

	skills = discover_skills(tmp_path)

	assert len(skills) == 1
	assert skills[0].name == "visible-skill"


def test_discover_hidden_skills_finds_underscore_prefixed(
        tmp_path: Path) -> None:
	"""discover_hidden_skills should find skills in underscore-prefixed directories."""
	# Create a visible skill
	visible = tmp_path / "visible-skill"
	visible.mkdir()
	(visible / "SKILL.md").write_text(
	    "---\nname: visible-skill\ndescription: A visible skill\n---\nContent")

	# Create hidden skills
	hidden1 = tmp_path / "_hidden-skill"
	hidden1.mkdir()
	(hidden1 / "SKILL.md").write_text(
	    "---\nname: hidden-skill\ndescription: A hidden skill\n---\nContent")

	hidden2 = tmp_path / "phase" / "_another-hidden"
	hidden2.mkdir(parents=True)
	(hidden2 / "SKILL.md").write_text(
	    "---\nname: another-hidden\ndescription: Another hidden\n---\nContent")

	hidden_names = discover_hidden_skills(tmp_path)

	assert len(hidden_names) == 2
	assert "hidden-skill" in hidden_names
	assert "another-hidden" in hidden_names


def test_discover_hidden_skills_returns_empty_for_no_hidden(
        tmp_path: Path) -> None:
	"""discover_hidden_skills returns empty list when no hidden skills exist."""
	visible = tmp_path / "visible-skill"
	visible.mkdir()
	(visible / "SKILL.md").write_text("---\nname: visible-skill\n---\nContent")

	hidden_names = discover_hidden_skills(tmp_path)

	assert hidden_names == []


def test_discover_hidden_skills_handles_missing_dir() -> None:
	"""discover_hidden_skills handles non-existent directories gracefully."""
	hidden_names = discover_hidden_skills(Path("/nonexistent/path"))

	assert hidden_names == []


def test_manifest_excludes_hidden_skills(tmp_path: Path) -> None:
	"""build_skill_manifest should exclude underscore-prefixed skills."""
	visible = tmp_path / "visible"
	visible.mkdir()
	(visible / "SKILL.md").write_text(
	    "---\nname: visible\ndescription: Visible\nphase: 1-init\n---\n")

	hidden = tmp_path / "_hidden"
	hidden.mkdir()
	(hidden / "SKILL.md").write_text(
	    "---\nname: hidden\ndescription: Hidden\nphase: 1-init\n---\n")

	manifest = build_skill_manifest(tmp_path)

	assert len(manifest.skills) == 1
	assert manifest.skills[0].name == "visible"


def test_format_manifest_shows_required_markers(tmp_path: Path) -> None:
	"""Required skills should have the required marker in formatted output."""
	skill = tmp_path / "required-skill"
	skill.mkdir()
	(skill / "SKILL.md").write_text(
	    "---\nname: required-skill\ndescription: Must load\nphase: 1-init\nrequired: true\n---\n"
	)

	manifest = build_skill_manifest(tmp_path)
	output = format_manifest_for_context(manifest)

	assert "**⚠️ REQUIRED**" in output
	assert "required-skill" in output
