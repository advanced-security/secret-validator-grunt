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
	    "---\nname: required-skill\ndescription: Must load\nphase: 1-init\nrequired: true\n---\nRequired instructions"
	)

	manifest = build_skill_manifest(tmp_path)
	output = format_manifest_for_context(manifest)

	assert "**⚠️ REQUIRED**" in output
	assert "required-skill" in output


def _bundled_markdown_files() -> list[Path]:
	"""Return all bundled SKILL.md and agent definition files."""
	from secret_validator_grunt.core.skills import SKILLS_BASE
	agents_dir = SKILLS_BASE.parent / "agents"
	return (sorted(SKILLS_BASE.rglob("SKILL.md")) +
	        sorted(agents_dir.glob("*.agent.md")))


@pytest.mark.parametrize(
    "path",
    _bundled_markdown_files(),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_bundled_frontmatter_is_valid_yaml(path: Path) -> None:
	"""Bundled frontmatter must be strict YAML.

	The Copilot runtime rejects skills whose frontmatter fails to
	parse, while our lenient loader would silently fall back to
	defaults and still advertise the skill in the manifest.
	"""
	import yaml

	text = path.read_text(encoding="utf-8")
	assert text.startswith("---\n")
	fm_text = text.split("---\n", 2)[1]
	meta = yaml.safe_load(fm_text)
	assert isinstance(meta, dict)
	assert meta.get("name")
	assert meta.get("description")


def _manifest_with_required(tmp_path: Path):
	for name, required in (("req-a", True), ("opt-b", False), ("req-c", True)):
		d = tmp_path / name
		d.mkdir()
		(d / "SKILL.md").write_text(
		    f"---\nname: {name}\ndescription: {name}\n"
		    f"required: {str(required).lower()}\n---\nBody for {name}")
	return build_skill_manifest(tmp_path)


def test_required_skill_names_excludes_disabled(tmp_path: Path) -> None:
	"""Only required, enabled skills are selected for preload."""
	from secret_validator_grunt.core.skills import required_skill_names

	manifest = _manifest_with_required(tmp_path)
	assert required_skill_names(manifest) == ["req-a", "req-c"]
	assert required_skill_names(manifest, ["req-a"]) == ["req-c"]


def test_manifest_supplies_required_bodies_once(tmp_path: Path) -> None:
	"""Required content is explicit; optional content stays on demand."""
	manifest = _manifest_with_required(tmp_path)
	text = format_manifest_for_context(manifest)
	assert text.count("Body for req-a") == 1
	assert text.count("Body for req-c") == 1
	assert "Body for opt-b" not in text
	assert 'skill("opt-b")' in text
	assert 'skill("req-a")' not in text
	assert "supplied in prompt" in text


def test_manifest_excludes_disabled_guidance(tmp_path: Path) -> None:
	"""Disabled skills appear neither as guidance nor as callable guides."""
	manifest = _manifest_with_required(tmp_path)
	text = format_manifest_for_context(manifest, disabled=["req-a", "opt-b"])
	assert "req-a" not in text
	assert "opt-b" not in text
	assert "Body for req-c" in text


def test_bundled_methodology_preserves_phases_and_optional_triggers() -> None:
	"""The shipped prompt retains four phases and conditional discovery."""
	from secret_validator_grunt.core.skills import discover_skill_directories

	manifest = build_skill_manifest(discover_skill_directories())
	text = format_manifest_for_context(manifest)
	headings = [
	    "## Phase 1: Initialization",
	    "## Phase 2: Context Gathering",
	    "## Phase 3: Verification",
	    "## Phase 4: Scoring And Reporting",
	]
	positions = [text.index(heading) for heading in headings]
	assert positions == sorted(positions)
	for skill in manifest.skills:
		if skill.required:
			assert text.count(skill.content) == 1
		else:
			assert f'skill("{skill.name}")' in text
			assert skill.description in text
			assert skill.content not in text
	assert "[secret type: http_basic_authentication_header]" in text


@pytest.mark.parametrize("metadata", [
    'name: bad\ndescription: broken: YAML',
    'name: bad\ndescription: d\nrequired: "false"',
    'description: missing name',
])
def test_invalid_skill_metadata_fails_explicitly(tmp_path: Path,
                                                 metadata: str) -> None:
	"""Invalid metadata cannot silently remove required methodology."""
	(tmp_path / "SKILL.md").write_text(f"---\n{metadata}\n---\nBody")
	with pytest.raises(ValueError, match="Invalid skill"):
		build_skill_manifest(tmp_path)


def test_empty_required_body_fails_explicitly(tmp_path: Path) -> None:
	"""An empty required guide cannot be represented as supplied."""
	(tmp_path / "SKILL.md"
	 ).write_text("---\nname: empty\ndescription: d\nrequired: true\n---\n")
	with pytest.raises(ValueError, match="has no content"):
		format_manifest_for_context(build_skill_manifest(tmp_path))


def test_manifest_deduplicates_roots_but_rejects_name_collisions(
        tmp_path: Path) -> None:
	"""Repeated paths are harmless; ambiguous skill names are not."""
	root = tmp_path / "first"
	root.mkdir()
	(root / "SKILL.md").write_text("---\nname: a\ndescription: d\n---\nBody")
	assert len(build_skill_manifest([root, root]).skills) == 1
	other = tmp_path / "second"
	other.mkdir()
	(other / "SKILL.md").write_text("---\nname: a\ndescription: d\n---\nOther")
	with pytest.raises(ValueError, match="Duplicate skill a"):
		build_skill_manifest([root, other])


def test_supplied_confidence_guidance_matches_eval_boundaries() -> None:
	"""Injected methodology must agree with deterministic confidence checks."""
	from secret_validator_grunt.core.skills import discover_skill_directories

	manifest = build_skill_manifest(discover_skill_directories())
	skill = next(s for s in manifest.skills
	             if s.name == "confidence-methodology")
	assert "| 7.0 <= score <= 10.0 | High |" in skill.content
	assert "| 4.0 <= score < 7.0 | Medium |" in skill.content
	assert "| 0.0 <= score < 4.0 | Low |" in skill.content
