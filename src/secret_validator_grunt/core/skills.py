"""
Dynamic skill manifest generator.

Scans the skills directory and builds a manifest of all available skills
with their metadata (name, description, phase). The manifest can be
regenerated on each run or cached for performance.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from secret_validator_grunt.models.skill import SkillInfo, SkillManifest
from secret_validator_grunt.loaders.frontmatter import split_frontmatter

logger = logging.getLogger(__name__)

# Default skills directory relative to this module
DEFAULT_SKILLS_DIRECTORY = Path(__file__).parent.parent / "skills"


def _discover_phase_dirs(skills_root: Path) -> list[str]:
	"""
	Discover phase directories within a skills root.

	Parameters:
		skills_root: Root directory containing phase subdirectories.

	Returns:
		List of absolute paths to phase directories.
	"""
	dirs: list[str] = []
	if skills_root.exists() and skills_root.is_dir():
		for child in sorted(skills_root.iterdir()):
			# Include directories that look like phases
			# (e.g., "1-initialization") or are named "custom"
			if child.is_dir() and not child.name.startswith("_"):
				dirs.append(str(child.resolve()))
	return dirs


def discover_skill_directories(
        additional_dirs: list[str] | None = None) -> list[str]:
	"""
	Discover all skill directories to register with Copilot.

	Returns absolute paths to all phase directories from the default
	location plus phase directories from any additional skill roots.

	Parameters:
		additional_dirs: Additional skill root directories from config.

	Returns:
		List of absolute directory paths as strings.
	"""
	seen: set[str] = set()
	dirs: list[str] = []

	def add_unique(path: str) -> None:
		if path not in seen:
			seen.add(path)
			dirs.append(path)

	# Add phase-based skill directories from default location
	for d in _discover_phase_dirs(DEFAULT_SKILLS_DIRECTORY):
		add_unique(d)

	# Add phase directories from additional skill roots
	if additional_dirs:
		for d in additional_dirs:
			path = Path(d).resolve()
			if not path.exists() or not path.is_dir():
				continue

			# Skip if this is the default skills dir (already processed)
			if path == DEFAULT_SKILLS_DIRECTORY.resolve():
				continue

			# Check if this directory contains skill subdirectories
			has_skill_children = any((child / "SKILL.md").exists()
			                         for child in path.iterdir()
			                         if child.is_dir())

			if has_skill_children:
				# This is a skill container, add it directly
				add_unique(str(path))
			else:
				# This might be a skills root, discover phase children
				for phase_dir in _discover_phase_dirs(path):
					add_unique(phase_dir)

	return dirs


def _infer_phase_from_path(skill_path: Path, skills_root: Path) -> str | None:
	"""
	Infer the phase from the skill's directory path.

	Parameters:
		skill_path: Path to the SKILL.md file.
		skills_root: Root skills directory.

	Returns:
		Phase string if inferrable (e.g., "1-initialization").
	"""
	try:
		relative = skill_path.parent.relative_to(skills_root)
		parts = relative.parts
		if parts and re.match(r"^\d+-", parts[0]):
			return parts[0]
	except ValueError:
		pass
	return None


def discover_skills(skills_dir: Path) -> list[SkillInfo]:
	"""
	Discover all skills in a directory tree.

	Scans for SKILL.md files and extracts metadata from frontmatter.

	Parameters:
		skills_dir: Root directory to scan for skills.

	Returns:
		List of SkillInfo objects for discovered skills.
	"""
	skills: list[SkillInfo] = []
	skills_dir = Path(skills_dir).resolve()

	if not skills_dir.exists():
		return skills

	for skill_file in skills_dir.rglob("SKILL.md"):
		# Skip skills in underscore-prefixed directories (templates)
		if any(
		    part.startswith("_")
		    for part in skill_file.relative_to(skills_dir).parts):
			continue

		try:
			content = skill_file.read_text(encoding="utf-8")
			meta, _ = split_frontmatter(content)

			name = meta.get("name", skill_file.parent.name)
			description = meta.get("description", "")
			phase = (meta.get("phase")
			         or _infer_phase_from_path(skill_file, skills_dir))
			secret_type = (meta.get("secret-type") or meta.get("secret_type"))
			required = meta.get("required", False)

			skills.append(
			    SkillInfo(
			        name=name,
			        description=description,
			        path=str(skill_file),
			        phase=phase,
			        secret_type=secret_type,
			        required=bool(required),
			    ))
		except Exception as exc:
			logger.debug("Failed to parse skill %s: %s", skill_file, exc)
			continue

	# Sort by phase (if present) then by name
	skills.sort(key=lambda s: (s.phase or "z", s.name))
	return skills


def build_skill_manifest(
        skills_dirs: list[Path] | Path | list[str] | str) -> SkillManifest:
	"""
	Build a complete skill manifest from one or more skill directories.

	Parameters:
		skills_dirs: Single path or list of paths to skill directories.

	Returns:
		SkillManifest with all discovered skills.
	"""
	if isinstance(skills_dirs, (str, Path)):
		skills_dirs = [Path(skills_dirs)]
	else:
		skills_dirs = [Path(d) for d in skills_dirs]

	all_skills: list[SkillInfo] = []
	for skills_dir in skills_dirs:
		all_skills.extend(discover_skills(skills_dir))

	# Extract unique phases
	phases = sorted(set(s.phase for s in all_skills if s.phase))

	return SkillManifest(
	    skills=all_skills,
	    phases=phases,
	    generated_at=datetime.now(timezone.utc).isoformat(),
	)


def _format_phase_header(phase: str) -> str:
	"""
	Format a phase directory name into a display header.

	Parameters:
		phase: Phase directory name (e.g., "1-initialization").

	Returns:
		Formatted display string (e.g., "Phase 1: Initialization").
	"""
	phase_display = phase.replace("-", " ").title()
	if phase[0].isdigit():
		num, rest = phase.split("-", 1)
		phase_display = f"Phase {num}: {rest.replace('-', ' ').title()}"
	return phase_display


def discover_hidden_skills(skills_dir: Path) -> list[str]:
	"""
	Discover skills in underscore-prefixed directories.

	These are internal/template skills that should be hidden from agents
	via the disabled_skills configuration.

	Parameters:
		skills_dir: Root directory to scan for skills.

	Returns:
		List of skill names that should be disabled.
	"""
	hidden: list[str] = []
	skills_dir = Path(skills_dir).resolve()

	if not skills_dir.exists():
		return hidden

	for skill_file in skills_dir.rglob("SKILL.md"):
		# Only include skills in underscore-prefixed directories
		relative_parts = skill_file.relative_to(skills_dir).parts
		if any(part.startswith("_") for part in relative_parts):
			try:
				content = skill_file.read_text(encoding="utf-8")
				meta, _ = split_frontmatter(content)
				name = meta.get("name", skill_file.parent.name)
				hidden.append(name)
			except Exception as exc:
				logger.debug("Failed to parse hidden skill %s: %s", skill_file,
				             exc)
				continue

	return hidden


def format_manifest_for_context(manifest: SkillManifest) -> str:
	"""
	Format the manifest as markdown for inclusion in agent context.

	Parameters:
		manifest: The skill manifest to format.

	Returns:
		Markdown string describing available skills.
	"""
	lines = [
	    "# Available Skills",
	    "",
	    "Use the `skill` tool to load guidance as needed. Skills marked "
	    "**⚠️ REQUIRED** must be loaded before proceeding with that phase.",
	    "",
	]

	# Add phase-organized skills
	if manifest.phases:
		for phase in manifest.phases:
			phase_skills = [s for s in manifest.skills if s.phase == phase]
			if phase_skills:
				header = _format_phase_header(phase)
				lines.append(f"## {header}")
				lines.append("")
				for skill in phase_skills:
					req_marker = " **⚠️ REQUIRED**" if skill.required else ""
					lines.append(
					    f"- `skill(\"{skill.name}\")`: {skill.description}{req_marker}"
					)
				lines.append("")

	# Add skills without phase
	phaseless = [s for s in manifest.skills if not s.phase]
	if phaseless:
		lines.append("## Other Skills")
		lines.append("")
		for skill in phaseless:
			req_marker = " **⚠️ REQUIRED**" if skill.required else ""
			lines.append(
			    f"- `skill(\"{skill.name}\")`: {skill.description}{req_marker}"
			)
		lines.append("")

	# Add secret-type specific skills summary
	secret_type_skills = [
	    s for s in manifest.skills
	    if s.secret_type and s.secret_type != "_template"
	]
	if secret_type_skills:
		lines.append("## Secret Type Specific Guides")
		lines.append("")
		for skill in secret_type_skills:
			lines.append(
			    f"- **{skill.secret_type}** → `skill(\"{skill.name}\")`")
		lines.append("")

	return "\n".join(lines)


__all__ = [
    "DEFAULT_SKILLS_DIRECTORY",
    "discover_skill_directories",
    "discover_skills",
    "discover_hidden_skills",
    "build_skill_manifest",
    "format_manifest_for_context",
]
