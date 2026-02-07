"""
Agent definition loader.

Provides functions for loading agent configurations from markdown files
with YAML frontmatter containing agent metadata and prompts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re

from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.loaders.frontmatter import split_frontmatter

CODE_FENCE_RE = re.compile(r"```(?:markdown)?\s*(.*?)```", re.S)


def _extract_report_template(body: str) -> Optional[str]:
	"""
	Extract the report template from a fenced markdown block.

	Prefers the first fenced block after the marker
	'Report template you must use:' (case-insensitive),
	else returns the first fenced markdown/code block.

	Parameters:
		body: The markdown body content.

	Returns:
		Extracted template content or None.
	"""
	marker = "report template you must use:"
	lower_body = body.lower()
	idx = lower_body.find(marker)
	search_text = body[idx:] if idx != -1 else body
	m = CODE_FENCE_RE.search(search_text)
	if m:
		return m.group(1).strip()
	return None


def load_agent(path: str | Path) -> AgentConfig:
	"""
	Load an agent definition from a markdown file with frontmatter.

	Parameters:
		path: Path to the agent markdown file.

	Returns:
		AgentConfig with parsed metadata and prompt body.
	"""
	path = Path(path)
	raw = path.read_text(encoding="utf-8")
	meta, body = split_frontmatter(raw)

	# Normalize keys (YAML uses hyphens, Python uses underscores)
	if "argument-hint" in meta and "argument_hint" not in meta:
		meta["argument_hint"] = meta.pop("argument-hint")
	report_template = _extract_report_template(body)
	return AgentConfig(prompt=body, report_template=report_template, **meta)


__all__ = ["load_agent"]
