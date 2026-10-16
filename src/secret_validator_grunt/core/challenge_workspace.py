"""Read-only analyst evidence and independent challenger working copies."""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import shutil
import stat
from uuid import uuid4

from secret_validator_grunt.models.challenge_workspace import ChallengeWorkspace

EVIDENCE_PATHS = ("scripts", "logs", "artifacts", "report.md")


def _is_runtime_directory(path: Path) -> bool:
	"""Exclude caches and virtual environments, without following links."""
	return path.name == "__pycache__" or (not path.is_symlink()
	                                      and path.is_dir() and
	                                      (path / "pyvenv.cfg").is_file())


def _evidence_entries(source: Path) -> dict[str, Path]:
	"""Enumerate regular evidence files and directories without following links."""
	entries: dict[str, Path] = {}

	def visit(path: Path) -> None:
		"""Inspect one entry before descending into its children."""
		info = path.lstat()
		mode = info.st_mode
		if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
			raise ValueError(f"Unsupported evidence entry: {path}")
		if stat.S_ISREG(mode) and info.st_nlink > 1:
			raise ValueError(f"Hard-linked evidence cannot be locked: {path}")
		entries[str(path.relative_to(source))] = path
		if stat.S_ISDIR(mode):
			for child in sorted(path.iterdir()):
				if not _is_runtime_directory(child):
					visit(child)

	for name in EVIDENCE_PATHS:
		path = source / name
		if path.exists() or path.is_symlink():
			visit(path)
	return entries


def _fingerprints(source: Path, *, lock: bool = False) -> dict[str, str]:
	"""Fingerprint evidence contents and modes, optionally making it read-only."""
	if source.is_symlink() or not source.is_dir():
		raise ValueError(
		    f"Analysis workspace is not a real directory: {source}")
	fingerprints: dict[str, str] = {}
	for name, path in _evidence_entries(source).items():
		mode = stat.S_IMODE(path.stat().st_mode)
		if lock:
			mode &= ~0o222
			path.chmod(mode)
			if path.stat().st_mode & 0o222:
				raise PermissionError(f"Evidence is not read-only: {path}")
		if path.is_dir():
			digest = "directory"
		else:
			with path.open("rb") as handle:
				digest = hashlib.file_digest(handle, "sha256").hexdigest()
		fingerprints[name] = f"{mode:o}:{digest}"
	return fingerprints


def _ignore_runtime_directories(directory: str, names: list[str]) -> set[str]:
	"""Omit generated environments from a writable copy."""
	return {
	    name
	    for name in names if _is_runtime_directory(Path(directory) / name)
	}


def _make_copy_writable(source: Path, working: Path) -> None:
	"""Make copied files writable and rebase repository-local symlinks."""
	for directory, dirs, files in os.walk(working, followlinks=False):
		parent = Path(directory)
		parent.chmod(stat.S_IMODE(parent.stat().st_mode) | stat.S_IWUSR)
		for name in dirs + files:
			path = parent / name
			if path.is_symlink():
				original = source / path.relative_to(working)
				target = original.resolve()
				if not target.is_relative_to(source):
					raise ValueError(
					    f"Workspace symlink escapes analysis: {original}")
				destination = working / target.relative_to(source)
				path.unlink()
				path.symlink_to(os.path.relpath(destination, path.parent))
			else:
				path.chmod(stat.S_IMODE(path.stat().st_mode) | stat.S_IWUSR)


def _prepare_workspace(source: Path, output: Path) -> ChallengeWorkspace:
	"""Lock originals, copy their contents, and persist the initial manifest."""
	if source.is_symlink() or not source.is_dir():
		raise ValueError(
		    f"Analysis workspace is not a real directory: {source}")
	source = source.resolve()
	output = output.resolve()
	if output.is_relative_to(source):
		raise ValueError(
		    "Challenger output must be outside the analysis workspace")

	fingerprints = _fingerprints(source, lock=True)
	root = output / "challenges" / f"{source.name}-{uuid4().hex}"
	workspace = ChallengeWorkspace(analysis=source, root=root,
	                               fingerprints=fingerprints)
	working = workspace.working_directory
	working.mkdir(parents=True)
	(root / "evidence-manifest.json").write_text(
	    workspace.model_dump_json(indent=2), encoding="utf-8")

	for name in (*EVIDENCE_PATHS, "repo"):
		original = source / name
		if original.is_symlink():
			raise ValueError(f"Workspace root entry is a symlink: {original}")
		if original.is_dir():
			shutil.copytree(original, working / name, symlinks=True,
			                ignore=_ignore_runtime_directories)
		elif original.is_file():
			shutil.copy2(original, working / name)
	for name in ("scripts", "logs", "artifacts"):
		(working / name).mkdir(exist_ok=True)
	_make_copy_writable(source, working)
	return workspace


async def prepare_challenge_workspace(
    source: Path,
    output: Path,
) -> ChallengeWorkspace:
	"""Prepare one isolated working copy without blocking the event loop."""
	return await asyncio.to_thread(_prepare_workspace, source, output)


async def changed_evidence(workspace: ChallengeWorkspace) -> list[str]:
	"""Return evidence paths whose contents, presence, or permissions changed."""
	current = await asyncio.to_thread(_fingerprints, workspace.analysis)
	return [
	    name for name in sorted(workspace.fingerprints.keys() | current.keys())
	    if workspace.fingerprints.get(name) != current.get(name)
	]
