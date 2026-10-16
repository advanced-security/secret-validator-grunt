"""Tests for GitHub API helpers."""

import json

import pytest
from fastcore.xtras import dict2obj

from secret_validator_grunt.integrations import github


class _FakeOp:
	"""Records calls and returns canned pages."""

	def __init__(self, pages: list[list[dict]]):
		self.pages = pages
		self.calls: list[dict] = []

	def __call__(self, **kwargs):
		self.calls.append(kwargs)
		page = kwargs["page"]
		return self.pages[page - 1] if page <= len(self.pages) else []


class _FakeApi:
	"""Minimal stand-in exposing the secret_scanning group."""

	def __init__(self, locations_op=None, alert=None, error=None, link=""):
		self._alert = alert
		self._error = error
		self.secret_scanning = type("SS", (), {})()
		self.secret_scanning.list_locations_for_alert = locations_op
		self.secret_scanning.get_alert = self._get_alert
		self.recv_hdrs = {"link": link}

	def _get_alert(self, **kwargs):
		if self._error:
			raise self._error
		return self._alert


def test_get_github_client_is_sync():
	"""Client must block (ghapi 2.x defaults to returning awaitables)."""
	api = github.get_github_client("t")
	assert api.transport.__class__.__name__ == "GhSyncTransport"
	assert api.transport.timeout == 30


def test_list_alert_locations_fetches_only_requested_page():
	"""A tool request must not drain all GitHub pages."""
	pages = [[{"type": t}] for t in ("commit", "wiki_commit", "issue_title")]
	op = _FakeOp(pages)
	api = _FakeApi(
	    locations_op=op,
	    link='<https://api.github.com/locations?page=3>; rel="next"')
	result = github.list_alert_locations(api, "o", "r", 1, per_page=1, page=2)
	assert result.locations == [{"type": "wiki_commit"}]
	assert result.next_page == 3
	assert result.page == 2
	assert [c["page"] for c in op.calls] == [2]


@pytest.mark.parametrize("locations", [[], [{"type": "commit"}]])
def test_locations_last_page_uses_link_header(locations: list[dict]) -> None:
	"""Even an exactly full last page has no next page without a next link."""
	result = github.list_alert_locations(
	    _FakeApi(locations_op=_FakeOp([locations])), "o", "r", 1, per_page=1)
	assert result.locations == locations
	assert result.next_page is None


@pytest.mark.parametrize("page,per_page", [(0, 50), (1, 0), (1, 101)])
def test_locations_rejects_invalid_pagination(page: int,
                                              per_page: int) -> None:
	"""Bounds are enforced before making an API call."""
	with pytest.raises(ValueError):
		github.list_alert_locations(None, "o", "r", 1, page=page,
		                            per_page=per_page)


def test_get_alert_wraps_errors_with_status():
	err = Exception("No alert found")
	err.status_code = 404
	with pytest.raises(RuntimeError, match="GitHub API error 404"):
		github.get_alert(_FakeApi(error=err), "o", "r", 1)


@pytest.mark.parametrize("metadata", [[], [{
    "label": "test",
    "values": ["x"]
}]])
def test_alert_nested_ghapi_lists_are_json_serializable(
        metadata: list) -> None:
	"""ghapi wraps even empty JSON arrays in fastcore L objects."""
	payload = {"number": 3, "secret": "synthetic", "metadata": metadata}
	result = github.get_alert(_FakeApi(alert=dict2obj(payload)), "o", "r", 3)
	assert json.loads(json.dumps(result)) == payload


def test_location_nested_ghapi_lists_are_json_serializable() -> None:
	"""Normalize nested location values without dropping evidence."""
	payload = {"type": "commit", "details": {"metadata": [{"values": ["x"]}]}}
	api = _FakeApi(locations_op=_FakeOp([[dict2obj(payload)]]))
	result = github.list_alert_locations(api, "o", "r", 3)
	assert json.loads(result.model_dump_json())["locations"] == [payload]
