"""Paginated secret scanning location evidence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AlertLocationsPage(BaseModel):
	"""One complete API page, not the alert's total location set."""

	locations: list[dict[str, Any]] = Field(
	    description="Locations with their original type and details")
	page: int = Field(ge=1, description="Returned page number")
	per_page: int = Field(ge=1, le=100, description="Requested page size")
	next_page: int | None = Field(
	    default=None, description="Next page from GitHub, or None at the end")
