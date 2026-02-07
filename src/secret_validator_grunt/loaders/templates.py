"""
Report template loading utilities.

Provides functions for loading report template content from file paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def load_report_template(path: str | Path) -> Optional[str]:
	"""
	Load report template content from a path if it exists.

	Parameters:
		path: Path to the template file.

	Returns:
		Template content if file exists, None otherwise.
	"""
	p = Path(path)
	if p.exists():
		return p.read_text(encoding="utf-8")
	return None


__all__ = ["load_report_template"]
