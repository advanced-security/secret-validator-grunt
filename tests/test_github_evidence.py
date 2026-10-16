"""Tests for run-scoped, concurrent GitHub evidence reuse."""

from __future__ import annotations

import asyncio
import json
import threading

import pytest

from secret_validator_grunt.integrations import github_evidence
from secret_validator_grunt.models.alert_locations import AlertLocationsPage
from secret_validator_grunt.models.github_tool_params import GitHubToolParams


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Prevent network calls and unnecessary GhApi construction."""
	monkeypatch.setattr(github_evidence, "get_github_client",
	                    lambda token: token)


def request(**overrides: object) -> GitHubToolParams:
	"""Build an evidence request with overridable identity and pagination."""
	return GitHubToolParams.model_validate({
	    "repo": "org/repo",
	    "alert_number": 1,
	    **overrides,
	})


@pytest.mark.asyncio
async def test_concurrent_reads_and_refresh(monkeypatch: pytest.MonkeyPatch,
                                            fake_client: None) -> None:
	"""Concurrent requests share a fetch; a completed snapshot can refresh."""
	calls: list[int] = []
	main_thread = threading.get_ident()

	def fetch(*args: object) -> dict:
		"""Record a real worker-thread invocation."""
		assert threading.get_ident() != main_thread
		calls.append(len(calls) + 1)
		return {"state": "open", "version": calls[-1]}

	monkeypatch.setattr(github_evidence, "get_alert", fetch)
	source = github_evidence.GitHubEvidence("test")
	results = await asyncio.gather(*(source.fetch(request())
	                                 for _ in range(6)))
	assert len(set(results)) == 1
	assert len(calls) == 1
	assert json.loads(results[0])["fetched_at"]
	assert await source.fetch(request()) == results[0]
	refreshed = await asyncio.gather(*(source.fetch(request(refresh=True))
	                                   for _ in range(3)))
	assert len(set(refreshed)) == 1
	assert len(calls) == 2
	assert json.loads(refreshed[0])["version"] == 2
	await source.close()


@pytest.mark.asyncio
async def test_runs_alerts_and_pages_are_isolated(
        monkeypatch: pytest.MonkeyPatch, fake_client: None) -> None:
	"""No cache crosses runs, credentials, alert IDs, or page boundaries."""
	calls: list[tuple] = []

	def fetch(api: str, owner: str, repo: str, alert: int, *, page: int,
	          per_page: int) -> AlertLocationsPage:
		"""Return page-specific evidence."""
		calls.append((api, owner, repo, alert, page, per_page))
		return AlertLocationsPage(
		    locations=[{
		        "type": "commit",
		        "details": {
		            "path": str(page)
		        }
		    }], page=page, per_page=per_page)

	monkeypatch.setattr(github_evidence, "list_alert_locations", fetch)
	first = github_evidence.GitHubEvidence("first")
	second = github_evidence.GitHubEvidence("second")
	for source, params in [
	    (first, request()),
	    (first, request()),
	    (first, request(page=2)),
	    (first, request(per_page=10)),
	    (first, request(alert_number=2)),
	    (first, request(repo="other/repo")),
	    (second, request()),
	]:
		body = json.loads(await source.fetch(params, locations=True))
		assert body["locations"][0]["details"]["path"] == str(params.page)
	assert len(calls) == 6
	await first.close()
	await second.close()


@pytest.mark.asyncio
async def test_failed_refresh_does_not_return_stale_success(
        monkeypatch: pytest.MonkeyPatch, fake_client: None) -> None:
	"""Failures are retryable and do not revive old snapshots."""
	attempt = 0

	def fetch(*args: object) -> dict:
		"""Fail only the refresh request."""
		nonlocal attempt
		attempt += 1
		if attempt == 2:
			raise RuntimeError("GitHub API error 503")
		return {"attempt": attempt}

	monkeypatch.setattr(github_evidence, "get_alert", fetch)
	source = github_evidence.GitHubEvidence("test")
	await source.fetch(request())
	with pytest.raises(RuntimeError, match="503"):
		await source.fetch(request(refresh=True))
	body = json.loads(await source.fetch(request()))
	assert body["attempt"] == 3
	await source.close()


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_request(
        monkeypatch: pytest.MonkeyPatch, fake_client: None) -> None:
	"""Cancelling one analysis must not invalidate another's evidence."""
	started = threading.Event()
	release = threading.Event()
	calls = 0

	def fetch(*args: object) -> dict:
		"""Block until the test releases the worker."""
		nonlocal calls
		calls += 1
		started.set()
		assert release.wait(timeout=5)
		return {"state": "open"}

	monkeypatch.setattr(github_evidence, "get_alert", fetch)
	source = github_evidence.GitHubEvidence("test")
	first = asyncio.create_task(source.fetch(request()))
	try:
		assert await asyncio.to_thread(started.wait, 5)
		second = asyncio.create_task(source.fetch(request()))
		first.cancel()
		with pytest.raises(asyncio.CancelledError):
			await first
	finally:
		release.set()
	assert json.loads(await second)["state"] == "open"
	assert calls == 1
	await source.close()
