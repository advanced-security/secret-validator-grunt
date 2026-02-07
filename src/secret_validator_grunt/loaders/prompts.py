"""
Prompt loading utilities.

Provides functions for loading prompt templates from the prompts directory.
"""

from __future__ import annotations

from pathlib import Path

# Prompts directory relative to this module
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str) -> str:
	"""
	Load a prompt file from the prompts directory.

	Parameters:
		name: Filename of the prompt to load.

	Returns:
		Contents of the prompt file.
	"""
	return (PROMPTS_DIR / name).read_text(encoding="utf-8")


__all__ = ["load_prompt"]
