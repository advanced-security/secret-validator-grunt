from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field, ConfigDict
from copilot.generated.session_events import QuotaSnapshot


class UsageStats(BaseModel):
	"""Aggregated usage statistics for a session.

	Tracks tokens, cost, duration, and quota snapshots across events.
	"""

	model_config = ConfigDict(arbitrary_types_allowed=True)

	input_tokens: float = Field(0, description="Total input tokens")
	output_tokens: float = Field(0, description="Total output tokens")
	cache_read_tokens: float = Field(0, description="Total cache read tokens")
	cache_write_tokens: float = Field(0,
	                                  description="Total cache write tokens")
	cost: float = Field(0, description="Accumulated cost")
	duration: float = Field(0, description="Accumulated duration in seconds")
	current_tokens: float | None = Field(
	    default=None, description="Current tokens in session context")
	token_limit: float | None = Field(default=None,
	                                  description="Session token limit")
	quota_snapshots_start: dict[str, QuotaSnapshot] | None = Field(
	    default=None, description="Initial quota snapshots")
	quota_snapshots_end: dict[str, QuotaSnapshot] | None = Field(
	    default=None, description="Final quota snapshots")

	@property
	def total_tokens(self) -> float:
		"""Return total tokens including cache reads/writes."""
		return (self.input_tokens + self.output_tokens +
		        self.cache_read_tokens + self.cache_write_tokens)

	def requests_consumed(self) -> dict[str, float]:
		"""Compute per-quota used requests delta if snapshots are available."""
		if not self.quota_snapshots_end:
			return {}
		res: dict[str, float] = {}
		for key, end in self.quota_snapshots_end.items():
			start = None
			if self.quota_snapshots_start:
				start = self.quota_snapshots_start.get(key)
			delta = end.used_requests - (start.used_requests if start else 0)
			res[key] = delta
		return res

	def merge_turn(self, *, input_tokens: float = 0, output_tokens: float = 0,
	               cache_read_tokens: float = 0, cache_write_tokens: float = 0,
	               cost: float = 0, duration: float = 0) -> None:
		"""Accumulate turn-level usage."""
		self.input_tokens += input_tokens or 0
		self.output_tokens += output_tokens or 0
		self.cache_read_tokens += cache_read_tokens or 0
		self.cache_write_tokens += cache_write_tokens or 0
		self.cost += cost or 0
		self.duration += duration or 0

	def update_snapshot(
	        self, *, current_tokens: float | None, token_limit: float | None,
	        quota_snapshots: dict[str, QuotaSnapshot] | None) -> None:
		"""Update snapshot state and preserve first/last quota snapshots."""
		if current_tokens is not None:
			self.current_tokens = current_tokens
		if token_limit is not None:
			self.token_limit = token_limit
		if quota_snapshots:
			if self.quota_snapshots_start is None:
				self.quota_snapshots_start = quota_snapshots
			self.quota_snapshots_end = quota_snapshots


def aggregate(usages: Iterable[UsageStats]) -> UsageStats:
	"""Aggregate multiple UsageStats into one combined summary.

	- Sums tokens, cost, duration
	- Picks first non-empty quota_snapshots_start, last quota_snapshots_end
	"""
	agg = UsageStats()
	first_snap = None
	last_snap = None
	for u in usages:
		agg.merge_turn(
		    input_tokens=u.input_tokens,
		    output_tokens=u.output_tokens,
		    cache_read_tokens=u.cache_read_tokens,
		    cache_write_tokens=u.cache_write_tokens,
		    cost=u.cost,
		    duration=u.duration,
		)
		if u.quota_snapshots_start and first_snap is None:
			first_snap = u.quota_snapshots_start
		if u.quota_snapshots_end:
			last_snap = u.quota_snapshots_end
	if first_snap:
		agg.quota_snapshots_start = first_snap
	if last_snap:
		agg.quota_snapshots_end = last_snap
	return agg


def format_duration(seconds: float) -> str:
	"""Format duration in seconds to a human-readable string.

	Returns a string like "1m 23s" or "45s" or "2h 5m".

	Parameters:
		seconds: Duration in seconds.

	Returns:
		Formatted duration string.
	"""
	if seconds < 0:
		return "0s"
	total_seconds = int(seconds)
	hours = total_seconds // 3600
	minutes = (total_seconds % 3600) // 60
	secs = total_seconds % 60
	if hours > 0:
		return f"{hours}h {minutes}m"
	elif minutes > 0:
		return f"{minutes}m {secs}s"
	else:
		return f"{secs}s"


__all__ = ["UsageStats", "aggregate", "format_duration"]
