"""
Copilot client factory module.

Provides factory functions for creating configured CopilotClient instances
based on runtime configuration (external server mode vs native stdio mode).
"""

from __future__ import annotations

from copilot import CopilotClient, RuntimeConnection
from secret_validator_grunt.models.config import Config


def create_client(config: Config) -> CopilotClient:
	"""Factory for CopilotClient with configured connection mode."""
	if config.cli_url:
		# External server mode: the server manages its own auth.
		return CopilotClient(
		    connection=RuntimeConnection.for_uri(config.cli_url),
		    log_level=config.log_level,
		)

	# Native stdio mode (spawns the bundled Copilot CLI runtime)
	if config.resolved_copilot_token:
		return CopilotClient(
		    log_level=config.log_level,
		    github_token=config.resolved_copilot_token,
		)
	return CopilotClient(log_level=config.log_level)


__all__ = ["create_client"]
