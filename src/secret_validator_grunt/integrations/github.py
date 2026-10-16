"""
GitHub API utilities.

Provides functions for interacting with GitHub's Secret Scanning API
to fetch alert details and locations.
"""

from __future__ import annotations

from typing import Any

from fastcore.xtras import obj2dict
from ghapi.core import GhApi
from secret_validator_grunt.models.alert_locations import AlertLocationsPage

DEFAULT_UA = "secret-validator-grunt"
HTTP_TIMEOUT_SECONDS = 30


def get_github_client(token: str, user_agent: str = DEFAULT_UA) -> GhApi:
	"""Construct a blocking GhApi client with token and user_agent.

	ghapi 2.x returns awaitables by default; ``sync=True`` keeps the
	synchronous call semantics the tool handlers rely on.
	"""
	return GhApi(token=token, user_agent=user_agent, sync=True,
	             timeout=HTTP_TIMEOUT_SECONDS)


def _wrap_error(exc: Exception) -> RuntimeError:
	"""Preserve HTTP status without copying response bodies into agent logs."""
	status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
	if status is None and getattr(exc, "response", None) is not None:
		status = exc.response.status_code
	if status:
		return RuntimeError(f"GitHub API error {status}")
	return RuntimeError(f"GitHub API request failed ({type(exc).__name__})")


def get_alert(api: GhApi, owner: str, repo: str,
              alert_number: int) -> dict[str, Any]:
	"""Fetch a single secret scanning alert."""
	try:
		return obj2dict(
		    dict(
		        api.secret_scanning.get_alert(owner=owner, repo=repo,
		                                      alert_number=alert_number)))
	except Exception as exc:  # noqa: BLE001
		raise _wrap_error(exc) from exc


def list_alert_locations(api: GhApi, owner: str, repo: str, alert_number: int,
                         *, page: int = 1,
                         per_page: int = 50) -> AlertLocationsPage:
	"""Fetch one page and use GitHub's Link header to identify continuation."""
	if page < 1 or not 1 <= per_page <= 100:
		raise ValueError(
		    "page must be positive and per_page between 1 and 100")
	try:
		locations = api.secret_scanning.list_locations_for_alert(
		    owner=owner, repo=repo, alert_number=alert_number, page=page,
		    per_page=per_page)
		has_next = 'rel="next"' in api.recv_hdrs.get("link", "")
		return AlertLocationsPage(
		    locations=[obj2dict(dict(location)) for location in locations],
		    page=page,
		    per_page=per_page,
		    next_page=page + 1 if has_next else None,
		)
	except Exception as exc:  # noqa: BLE001
		raise _wrap_error(exc) from exc


__all__ = [
    "get_github_client", "get_alert", "list_alert_locations", "DEFAULT_UA"
]
