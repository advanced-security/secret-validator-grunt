"""Run-scoped reuse of GitHub evidence, never of live validation results."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import partial

from secret_validator_grunt.integrations.github import (
    get_alert,
    get_github_client,
    list_alert_locations,
)
from secret_validator_grunt.models.github_tool_params import GitHubToolParams

EvidenceKey = tuple[bool, str, int, int, int]


class GitHubEvidence:
	"""Share in-flight and successful reads across agents in one run."""

	def __init__(self, token: str | None) -> None:
		"""Bind the cache to one run's API credentials."""
		self._token = token
		self._requests: dict[EvidenceKey, asyncio.Task[str]] = {}

	async def fetch(self, params: GitHubToolParams, *,
	                locations: bool = False) -> str:
		"""Return timestamped JSON; refresh replaces completed snapshots."""
		if not self._token:
			raise RuntimeError(
			    "GitHub token required. Set GITHUB_TOKEN in .env")
		key = (locations, params.repo.lower(), params.alert_number,
		       params.page if locations else 0,
		       params.per_page if locations else 0)
		task = self._requests.get(key)
		if task is None or (params.refresh and task.done()):
			task = asyncio.create_task(
			    asyncio.to_thread(self._fetch, params, self._token,
			                      locations=locations))
			self._requests[key] = task
			task.add_done_callback(partial(self._discard_failed, key))
		# A cancelled agent must not cancel another agent's shared request.
		return await asyncio.shield(task)

	def _discard_failed(self, key: EvidenceKey,
	                    task: asyncio.Task[str]) -> None:
		"""Observe and evict errors so subsequent calls can retry."""
		failed = task.cancelled() or task.exception() is not None
		if failed and self._requests.get(key) is task:
			del self._requests[key]

	def _fetch(self, params: GitHubToolParams, token: str, *,
	           locations: bool) -> str:
		"""Perform blocking API work off the event loop and serialize once."""
		api = get_github_client(token)
		owner, repo = params.repo.split("/")
		if locations:
			result = list_alert_locations(api, owner, repo,
			                              params.alert_number,
			                              page=params.page,
			                              per_page=params.per_page)
			data = {
			    **result.model_dump(),
			    "locations_count": len(result.locations),
			}
		else:
			data = get_alert(api, owner, repo, params.alert_number)
		return json.dumps(
		    {
		        **data,
		        "repo": params.repo,
		        "alert_number": params.alert_number,
		        "fetched_at": datetime.now(timezone.utc).isoformat(),
		    }, ensure_ascii=False, separators=(",", ":"))

	async def close(self) -> None:
		"""Finish bounded in-flight reads and release all cached evidence."""
		await asyncio.gather(*self._requests.values(), return_exceptions=True)
		self._requests.clear()
