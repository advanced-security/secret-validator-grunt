"""Paths and original evidence fingerprints for one challenge."""

from pathlib import Path

from pydantic import BaseModel, Field


class ChallengeWorkspace(BaseModel):
	"""Separate original evidence from a challenger's writable working copy."""

	analysis: Path = Field(description="Original analysis workspace")
	root: Path = Field(description="Directory for this challenge's outputs")
	fingerprints: dict[str, str] = Field(
	    description=
	    "Original evidence paths mapped to modes and SHA-256 hashes", )

	@property
	def working_directory(self) -> Path:
		"""Return the independent workspace used for reruns."""
		return self.root / "work"
