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
		"""Client passes github_token (fallback) in native mode for auth."""
		cfg = Config(GITHUB_TOKEN="ghp_test123", LOG_LEVEL="warning")

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "log_level":
		    "warning",
		    "github_token":
		    "ghp_test123",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_native_mode_copilot_token(self, mock_client_class: MagicMock):
		"""Client uses COPILOT_TOKEN for SDK auth in native mode."""
		cfg = Config(COPILOT_TOKEN="gho_copilot_abc", LOG_LEVEL="info")

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "log_level":
		    "info",
		    "github_token":
		    "gho_copilot_abc",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_native_mode_copilot_token_precedence(
	        self, mock_client_class: MagicMock):
		"""COPILOT_TOKEN takes precedence over GITHUB_TOKEN for SDK auth."""
		cfg = Config(
		    GITHUB_TOKEN="ghp_api_token",
		    COPILOT_TOKEN="gho_copilot_token",
		    LOG_LEVEL="info",
		)

		create_client(cfg)

		mock_client_class.assert_called_once_with({
		    "log_level":
		    "info",
		    "github_token":
		    "gho_copilot_token",
		})

	@patch("secret_validator_grunt.copilot_client.CopilotClient")
	def test_external_mode_ignores_token(self, mock_client_class: MagicMock):
		"""External server mode does not pass any token (server manages auth)."""
		cfg = Config(
		    COPILOT_CLI_URL="localhost:8080",
		    GITHUB_TOKEN="ghp_test123",
		    COPILOT_TOKEN="gho_copilot",
		    LOG_LEVEL="info",
		)

		create_client(cfg)

		# Neither token should be in the options for external server mode
		call_args = mock_client_class.call_args[0][0]
		assert "github_token" not in call_args
		assert call_args["cli_url"] == "localhost:8080"
