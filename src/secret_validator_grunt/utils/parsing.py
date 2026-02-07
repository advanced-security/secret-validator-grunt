"""
Markdown and JSON parsing utilities.

Provides functions for extracting JSON from fenced code blocks,
parsing markdown sections, and extracting tables from markdown.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Dict, List

CODE_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.S)
ANY_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
JSON_RE = re.compile(r"\{.*\}", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")


def strip_code_fences(text: str) -> str:
	"""
	Return content inside first json fence if present; else original text.

	Parameters:
		text: Input text potentially containing fenced code blocks.

	Returns:
		Content of the first JSON fence, or original text if none found.
	"""
	m = CODE_FENCE_RE.search(text)
	if m:
		return m.group(1).strip()
	return text


def _extract_last_fenced_json(text: str) -> Optional[str]:
	"""Return the last fenced block (json preferred) if any."""
	matches = list(ANY_FENCE_RE.finditer(text))
	if not matches:
		return None
	return matches[-1].group(1).strip()


def _extract_balanced_json(text: str) -> Optional[str]:
	"""Heuristic: extract minimal balanced JSON object from text."""
	stack = 0
	start = None
	for i, ch in enumerate(text):
		if ch == '{':
			if stack == 0:
				start = i
			stack += 1
		elif ch == '}':
			if stack > 0:
				stack -= 1
				if stack == 0 and start is not None:
					return text[start:i + 1]
	return None


def extract_json(text: str) -> Optional[Any]:
	"""
	Extract JSON from fenced block (last) or balanced braces in text.

	Parameters:
		text: Input text containing JSON.

	Returns:
		Parsed JSON object, or None if extraction/parsing fails.
	"""
	fenced = _extract_last_fenced_json(text)
	candidates = []
	if fenced:
		candidates.append(fenced)
	# fallback: balanced braces
	balanced = _extract_balanced_json(text)
	if balanced:
		candidates.append(balanced)
	for cand in candidates:
		try:
			return json.loads(cand)
		except Exception:
			continue
	return None


def normalize_heading(h: str) -> str:
	"""
	Normalize headings for case-insensitive matching.

	Parameters:
		h: Heading text to normalize.

	Returns:
		Lowercase heading with non-alphanumeric chars replaced by spaces.
	"""
	return re.sub(r"[^a-z0-9]+", " ", h.lower()).strip()


def parse_sections(md: str) -> Dict[str, str]:
	"""
	Parse markdown into sections keyed by heading text.

	Parameters:
		md: Markdown content to parse.

	Returns:
		Dictionary mapping heading text to section body.
	"""
	sections: Dict[str, str] = {}
	matches = list(HEADING_RE.finditer(md))
	for i, m in enumerate(matches):
		heading = m.group(2).strip()
		start = m.end()
		end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
		body = md[start:end].strip("\n")
		sections[heading] = body
	return sections


def extract_section(md: str, heading: str) -> Optional[str]:
	"""
	Find a section whose normalized heading starts with the target.

	Parameters:
		md: Markdown content to search.
		heading: Target heading prefix to match.

	Returns:
		Section body if found, None otherwise.
	"""
	target = normalize_heading(heading)
	for h, body in parse_sections(md).items():
		if normalize_heading(h).startswith(target):
			return body.strip()
	return None


def parse_table(table_md: str) -> List[Dict[str, str]]:
	"""
	Parse a markdown table into a list of dict rows.

	Parameters:
		table_md: Markdown table content.

	Returns:
		List of dictionaries with header keys and cell values.
	"""
	lines = [ln.strip() for ln in table_md.strip().splitlines() if ln.strip()]
	if len(lines) < 2:
		return []
	header = lines[0]
	sep = lines[1]
	if not TABLE_SEPARATOR_RE.match(sep):
		return []
	headers = [h.strip() for h in header.strip("|").split("|")]
	rows: List[Dict[str, str]] = []
	for ln in lines[2:]:
		cells = [c.strip() for c in ln.strip("|").split("|")]
		if len(cells) != len(headers):
			continue
		rows.append(dict(zip(headers, cells)))
	return rows


def extract_table_from_section(md: str,
                               heading: str) -> Optional[List[Dict[str, str]]]:
	"""
	Extract the first table found inside a section by heading.

	Parameters:
		md: Markdown content to search.
		heading: Section heading to look for.

	Returns:
		List of row dictionaries if table found, None otherwise.
	"""
	section = extract_section(md, heading)
	if not section:
		return None
	lines = section.splitlines()
	# find first table-looking segment
	buf: List[str] = []
	collecting = False
	for ln in lines:
		if "|" in ln:
			buf.append(ln)
			collecting = True
		elif collecting:
			break
	if buf:
		return parse_table("\n".join(buf))
	return None


def extract_bullets(section_md: str) -> List[str]:
	"""
	Extract bullet list items from a markdown section.

	Parameters:
		section_md: Markdown section content.

	Returns:
		List of bullet item texts without the bullet markers.
	"""
	bullets = []
	for ln in section_md.splitlines():
		if ln.strip().startswith(("-", "*")):
			bullets.append(ln.strip().lstrip("-*").strip())
	return bullets


__all__ = [
    "extract_json",
    "strip_code_fences",
    "parse_sections",
    "extract_section",
    "parse_table",
    "extract_table_from_section",
    "extract_bullets",
    "normalize_heading",
]
