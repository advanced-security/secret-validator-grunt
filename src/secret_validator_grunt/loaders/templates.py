"""
Report template loading utilities.

Provides functions for loading report template content from file paths.
"""

from __future__ import annotations

from pathlib import Path


def load_report_template(path: str | Path) -> str | None:
	"""
	Load report template content from a path if it exists.

	Supports absolute, cwd-relative, or package-relative paths.

	Parameters:
		path: Path to the template file.

	Returns:
		Template content if file exists, None otherwise.
	"""
	from secret_validator_grunt.utils.paths import resolve_asset_path

	p = resolve_asset_path(str(path))
	if p.exists():
		return p.read_text(encoding="utf-8")
	return None


__all__ = ["load_report_template"]
