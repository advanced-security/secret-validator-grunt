"""
GitHub API utilities.

Provides functions for interacting with GitHub's Secret Scanning API
to fetch alert details and locations.
"""

from __future__ import annotations

from typing import Any, List

from ghapi.core import GhApi
from ghapi.page import paged

try:
	from fastcore.net import HTTPError  # type: ignore
except Exception:  # pragma: no cover
	HTTPError = Exception  # fallback

DEFAULT_UA = "secret-validator-grunt"


def get_github_client(token: str, user_agent: str = DEFAULT_UA) -> GhApi:
	"""Construct a GhApi client with token and user_agent."""
	return GhApi(token=token, user_agent=user_agent)


def _wrap_error(exc: Exception) -> RuntimeError:
	status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
	msg = str(exc)
	if status:
		return RuntimeError(f"GitHub API error {status}: {msg}")
	return RuntimeError(f"GitHub API error: {msg}")


def get_alert(api: GhApi, owner: str, repo: str, alert_number: int) -> Any:
	"""Fetch a single secret scanning alert."""
	try:
		if hasattr(api, "secret_scanning") and hasattr(api.secret_scanning,
		                                               "get_alert"):
			return api.secret_scanning.get_alert(owner=owner, repo=repo,
			                                     alert_number=alert_number)
		return api(
		    "GET",
		    f"/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}")
	except Exception as exc:  # noqa: BLE001
		raise _wrap_error(exc)


def list_alert_locations(api: GhApi, owner: str, repo: str, alert_number: int,
                         per_page: int = 100,
                         max_pages: int = 50) -> List[Any]:
	"""List all locations for a secret scanning alert (paginated)."""
	try:
		if hasattr(api, "secret_scanning") and hasattr(
		    api.secret_scanning, "list_locations_for_alert"):
			# paged() yields pages (L lists), flatten to individual locations
			return [
			    dict(loc) for page in paged(
			        api.secret_scanning.list_locations_for_alert, owner=owner,
			        repo=repo, alert_number=alert_number, per_page=per_page,
			        _pages=max_pages) for loc in page
			]
		# paged() yields pages (L lists), flatten to individual locations
		return [
		    dict(loc) for page in paged(
		        api, "GET",
		        f"/repos/{owner}/{repo}/secret-scanning/alerts/{alert_number}/locations",
		        per_page=per_page, _pages=max_pages) for loc in page
		]
	except Exception as exc:  # noqa: BLE001
		raise _wrap_error(exc)


__all__ = [
    "get_github_client", "get_alert", "list_alert_locations", "DEFAULT_UA"
]
