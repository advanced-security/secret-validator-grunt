"""
Protocol definitions for dependency injection.

Defines Protocol classes for the Copilot client and session interfaces
to enable testing with mock implementations.
"""

from __future__ import annotations

from typing import Protocol, Any


class SessionProtocol(Protocol):
	"""
	Protocol for Copilot session interface.

	Defines the expected methods for interacting with a Copilot session.
	"""

	async def send_and_wait(self, options: dict,
	                        timeout: int | None = None) -> Any:
		"""Send a prompt and wait for response."""
		...

	async def abort(self) -> Any:
		"""Abort the current session operation."""
		...

	async def destroy(self) -> Any:
		"""Destroy the session and release resources."""
		...

	def on(self, handler: Any) -> Any:
		"""Register an event handler."""
		...

	async def get_messages(self) -> Any:
		"""Get all messages from the session."""
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

	async def create_session(self, config: dict) -> SessionProtocol:
		"""Create a new session with the given configuration."""
		...


__all__ = ["SessionProtocol", "CopilotClientProtocol"]
