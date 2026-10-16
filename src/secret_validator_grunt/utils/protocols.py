"""
Protocol definitions for dependency injection.

Defines Protocol classes for the Copilot client and session interfaces
to enable testing with mock implementations.
"""

from __future__ import annotations

from typing import Protocol, Any
from copilot.generated.rpc import SessionRpc


class SessionProtocol(Protocol):
	"""
	Protocol for Copilot session interface.

	Defines the expected methods for interacting with a Copilot session.
	"""

	@property
	def rpc(self) -> SessionRpc:
		"""Expose the SDK session RPC surface."""
		...

	async def send_and_wait(self, prompt: str, *,
	                        timeout: float = 60.0) -> Any:
		"""Send a prompt and wait for response."""
		...

	async def abort(self) -> Any:
		"""Abort the current session operation."""
		...

	async def disconnect(self) -> Any:
		"""Disconnect the session and release resources."""
		...

	def on(self, handler: Any) -> Any:
		"""Register an event handler."""
		...

	async def get_events(self) -> Any:
		"""Get all events from the session history."""
		...


class CopilotClientProtocol(Protocol):
	"""
	Protocol for Copilot client interface.

	Defines the expected methods for managing a Copilot client.
	"""

	async def start(self) -> Any:
		"""Start the client connection."""
		...

	async def stop(self) -> Any:
		"""Stop the client connection."""
		...

	async def create_session(self, **config: Any) -> SessionProtocol:
		"""Create a new session with the given keyword configuration."""
		...


__all__ = ["SessionProtocol", "CopilotClientProtocol"]
