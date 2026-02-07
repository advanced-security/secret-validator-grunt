"""
Run parameters model.

Defines validated run parameters for CLI invocation and runner orchestration.
Provides sanitized slugs and session ID prefixes for safe filesystem paths.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

ORG_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALERT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class RunParams(BaseModel):
	"""Validated run parameters for CLI/runner.

	Provides sanitized slugs and session_id prefix for safe filesystem paths
	and session identifiers.
	"""

	org_repo: str = Field(description="owner/repo")
	alert_id: str = Field(description="Secret scanning alert id")
	analyses: Optional[int] = Field(default=None,
	                                description="Override analyses")
	timeout: Optional[int] = Field(default=None,
	                               description="Analysis timeout")
	judge_timeout: Optional[int] = Field(default=None,
	                                     description="Judge timeout")
	stream_verbose: Optional[bool] = Field(default=None,
	                                       description="Stream deltas")
	show_usage: Optional[bool] = Field(default=None,
	                                   description="Show usage metrics")

	@field_validator('org_repo')
	@classmethod
	def validate_org_repo(cls, v: str) -> str:
		if not ORG_REPO_RE.match(v):
			raise ValueError(
			    "org_repo must be owner/repo with safe characters")
		return v

	@field_validator('alert_id')
	@classmethod
	def validate_alert_id(cls, v: str) -> str:
		if not ALERT_ID_RE.match(v):
			raise ValueError("alert_id must be alnum/_.- only")
		return v

	@field_validator('analyses', 'timeout', 'judge_timeout')
	@classmethod
	def validate_positive(cls, v: Optional[int],
	                      info: ValidationInfo) -> Optional[int]:
		if v is None:
			return v
		if v <= 0:
			raise ValueError(f"{info.field_name} must be > 0")
		return v

	@property
	def owner(self) -> str:
		return self.org_repo.split('/')[0]

	@property
	def repo(self) -> str:
		return self.org_repo.split('/')[1]

	@staticmethod
	def _slugify(v: str) -> str:
		slug = SAFE_SLUG_RE.sub('_', v).strip('_')
		return slug or "default"

	@property
	def org_repo_slug(self) -> Path:
		"""Return sanitized org/repo path for filesystem use."""
		return Path(self._slugify(self.owner)) / self._slugify(self.repo)

	@property
	def alert_id_slug(self) -> str:
		return self._slugify(self.alert_id)

	@property
	def session_id_prefix(self) -> str:
		base = f"{self.owner}_{self.repo}_{self.alert_id_slug}"
		safe = self._slugify(base)
		return safe[:64]


__all__ = ["RunParams"]
