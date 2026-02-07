"""Tests for copilot_client module."""
from unittest.mock import patch, MagicMock

import pytest

from secret_validator_grunt.copilot_client import create_client
from secret_validator_grunt.models.config import Config


class TestCreateClient:
	"""Tests for create_client factory function."""

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_external_server_mode(self, mock_client_class: MagicMock):
		"""Client uses cli_url when set (external server mode)."""
		cfg = Config(COPILOT_CLI_URL="localhost:8080", LOG_LEVEL="debug")

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "cli_url": "localhost:8080",
		    "log_level": "debug",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_native_stdio_mode_no_token(self, mock_client_class: MagicMock):
		"""Client uses stdio mode when cli_url is unset."""
		cfg = Config(LOG_LEVEL="info")

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "log_level": "info",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_native_stdio_mode_with_token(self, mock_client_class: MagicMock):
		"""Client passes github_token in native mode for auth."""
		cfg = Config(GITHUB_TOKEN="ghp_test123", LOG_LEVEL="warning")

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "log_level":
		    "warning",
		    "github_token":
		    "ghp_test123",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_external_mode_ignores_token(self, mock_client_class: MagicMock):
		"""External server mode does not pass github_token (server manages auth)."""
		cfg = Config(
		    COPILOT_CLI_URL="localhost:8080",
		    GITHUB_TOKEN="ghp_test123",
		    LOG_LEVEL="info",
		)

		create_client(cfg)

		# Token should NOT be in the options for external server mode
		call_args = mock_client_class.call_args[0][0]
		assert "github_token" not in call_args
		assert call_args["cli_url"] == "localhost:8080"
