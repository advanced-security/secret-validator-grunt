"""
Path safety utilities.

Provides functions for ensuring paths stay within allowed directories
to prevent path traversal attacks.
"""

from __future__ import annotations

from pathlib import Path


def ensure_within(base: Path, path: Path) -> Path:
	"""
	Ensure a path is within the specified base directory.

	Parameters:
		base: The allowed base directory.
		path: The path to validate.

	Returns:
		The original path if valid.

	Raises:
		ValueError: If path escapes the base directory.
	"""
	resolved_base = base.resolve()
	resolved_path = path.resolve()
	try:
		if resolved_path == resolved_base or resolved_path.is_relative_to(
		    resolved_base):
			return path
	except AttributeError:
		# Py<3.9 fallback
		if str(resolved_path).startswith(str(resolved_base)):
			return path
	raise ValueError(f"Path {resolved_path} escapes base {resolved_base}")


__all__ = ["ensure_within"]
