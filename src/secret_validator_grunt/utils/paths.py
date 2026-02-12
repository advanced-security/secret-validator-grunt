"""
Path safety utilities.

Provides functions for ensuring paths stay within allowed directories
to prevent path traversal attacks, and for resolving package-relative
asset paths.
"""

from __future__ import annotations

from pathlib import Path


# Root of the secret_validator_grunt package directory.
PACKAGE_DIR: Path = Path(__file__).resolve().parent.parent


def resolve_asset_path(relative_path: str) -> Path:
	"""Resolve a path that may be relative to the package directory.

	Resolution order:
	1. If the path exists as-is (absolute or cwd-relative), return it.
	2. Otherwise, resolve against the package directory.

	This allows pip-installed packages to locate bundled assets
	(agents, templates, prompts) without hardcoding repo-root paths.

	Parameters:
		relative_path: Path string (may be absolute, cwd-relative, or
			package-relative like ``agents/secret_validator.agent.md``).

	Returns:
		Resolved Path to the asset.
	"""
	p = Path(relative_path)
	if p.exists():
		return p
	return PACKAGE_DIR / relative_path


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


__all__ = ["ensure_within", "resolve_asset_path", "PACKAGE_DIR"]
