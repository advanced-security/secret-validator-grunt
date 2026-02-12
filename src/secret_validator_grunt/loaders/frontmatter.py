"""
YAML frontmatter parsing utilities.

Provides shared functions for extracting YAML frontmatter from
markdown files, used by agent loader and skill manifest modules.
"""

from __future__ import annotations

from typing import Any

import yaml


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
	"""
	Split YAML frontmatter from markdown body.

	Extracts the YAML block between `---` delimiters at the start
	of the document and returns it along with the remaining body.

	Parameters:
		text: The full markdown file content.

	Returns:
		Tuple of (frontmatter dict, body text). Returns empty dict
		if no valid frontmatter is found.
	"""
	lines = text.splitlines()

	# Need at least 3 lines: ---, content, ---
	if len(lines) < 3 or lines[0].strip() != "---":
		return {}, text

	# Find closing delimiter
	end_idx = -1
	for i, ln in enumerate(lines[1:], start=1):
		if ln.strip() == "---":
			end_idx = i
			break

	if end_idx < 0:
		return {}, text

	fm_text = "\n".join(lines[1:end_idx])
	body = "\n".join(lines[end_idx + 1:])

	try:
		meta = yaml.safe_load(fm_text) or {}
	except yaml.YAMLError:
		meta = {}

	return meta, body.lstrip("\n")


__all__ = ["split_frontmatter"]
