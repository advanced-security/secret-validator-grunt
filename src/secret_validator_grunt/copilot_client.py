"""
Copilot client factory module.

Provides factory functions for creating configured CopilotClient instances
based on runtime configuration (external server mode vs native stdio mode).
"""

from __future__ import annotations

from typing import Any

from copilot import CopilotClient
from secret_validator_grunt.models.config import Config


def create_client(config: Config) -> CopilotClient:
	"""Factory for CopilotClient with configured connection mode."""
	if config.cli_url:
		# External server mode
		return CopilotClient({
		    "cli_url": config.cli_url,
		    "log_level": config.log_level,
		})

	# Native stdio mode
	opts: dict[str, Any] = {"log_level": config.log_level}
	if config.github_token:
		opts["github_token"] = config.github_token
	return CopilotClient(opts)


__all__ = ["create_client"]
