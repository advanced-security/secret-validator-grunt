"""Validated inputs shared by the GitHub evidence tools."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from secret_validator_grunt.models.run_params import ORG_REPO_RE


class GitHubToolParams(BaseModel):
	"""Resolve context defaults before validating a tool request."""

	repo: str = Field(pattern=ORG_REPO_RE, description="owner/repo")
	alert_number: int = Field(gt=0, description="Secret scanning alert number")
	page: int = Field(default=1, ge=1, strict=True,
	                  description="Location page")
	per_page: int = Field(default=50, ge=1, le=100, strict=True,
	                      description="Locations per page")
	refresh: bool = Field(default=False, strict=True,
	                      description="Fetch current evidence again")

	@field_validator("alert_number", mode="before")
	@classmethod
	def validate_alert_number(cls, value: object) -> object:
		"""Accept numeric CLI defaults but not booleans or fractional IDs."""
		if isinstance(value, (bool, float)):
			raise ValueError("alert_number must be a positive integer")
		return value
