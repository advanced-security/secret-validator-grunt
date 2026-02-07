from __future__ import annotations

import subprocess
import sys
from typing import List


def _run(args: List[str]) -> int:
	"""
	Execute yapf with the provided arguments.

	Parameters:
		args: Command-line arguments to pass to yapf.

	Returns:
		Exit code from the yapf subprocess.
	"""
	return subprocess.call(["yapf", *args])


def fmt_main() -> None:
	"""Format code with yapf recursively in src and tests.

	Usage: uv run fmt [-- yapf args...]
	"""
	args = sys.argv[1:] or ["--recursive", "--in-place", "src", "tests"]
	sys.exit(_run(args))


def fmt_check_main() -> None:
	"""Check formatting with yapf (diff).

	Usage: uv run fmt-check [-- yapf args...]
	"""
	args = sys.argv[1:] or ["--recursive", "--diff", "src", "tests"]
	sys.exit(_run(args))


__all__ = ["fmt_main", "fmt_check_main"]
