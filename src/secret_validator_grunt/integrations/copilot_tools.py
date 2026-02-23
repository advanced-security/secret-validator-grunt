"""
Copilot session tools.

Defines custom tools for Copilot sessions that interact with
GitHub's Secret Scanning API and the validate-secrets library.
"""

from __future__ import annotations

import json
import functools
from typing import Any

from copilot.types import Tool, ToolInvocation, ToolResult

from secret_validator_grunt.models.config import Config
from secret_validator_grunt.integrations.github import (
    get_github_client,
    get_alert,
    list_alert_locations,
    DEFAULT_UA,
)


def _parse_repo(repo: str) -> tuple[str, str]:
	"""Split an 'owner/repo' string into (owner, name) tuple."""
	owner, name = repo.split("/", 1)
	return owner, name


def _success(text: str, data: dict) -> ToolResult:
	"""Build a successful ToolResult dict."""
	return {
	    "textResultForLlm": text,
	    "resultType": "success",
	    "toolTelemetry": {},
	    "sessionLog": "",
	    "binaryResultsForLlm": [],
	    "data": data,
	}


def _failure(msg: str) -> ToolResult:
	"""Build a failure ToolResult dict with an error message."""
	return {
	    "textResultForLlm": msg,
	    "resultType": "failure",
	    "toolTelemetry": {},
	    "sessionLog": "",
	    "binaryResultsForLlm": [],
	    "data": {
	        "error": msg
	    },
	}


def secret_scanning_alert_tool(config: Config, context_repo: str | None,
                               context_alert_id: str | None) -> Tool:
	"""Define a tool that fetches secret scanning alert details via GitHub API."""

	def handler(invocation: ToolInvocation) -> ToolResult:
		params: dict[str, Any] = invocation.get("arguments") or {}
		repo = params.get("repo") or context_repo
		alert_number = params.get("alert_number") or context_alert_id
		token = config.github_token
		if not repo or not alert_number:
			raise ValueError("repo and alert_number are required")
		if not token:
			return _failure("GitHub token required. Set GITHUB_TOKEN in .env")
		try:
			alert_num_int = int(alert_number)
		except Exception as e:  # noqa: BLE001
			raise ValueError("alert_number must be an integer") from e
		owner, name = _parse_repo(str(repo))
		api = get_github_client(token, user_agent=DEFAULT_UA)
		data = get_alert(api, owner, name, alert_num_int)
		alert = data
		text = json.dumps(
		    {
		        "repo":
		        repo,
		        "alert_number":
		        alert_num_int,
		        "state":
		        alert.get("state") if isinstance(alert, dict) else None,
		        "secret_type":
		        alert.get("secret_type") if isinstance(alert, dict) else None,
		        "locations_url":
		        alert.get("locations_url")
		        if isinstance(alert, dict) else None,
		    }, ensure_ascii=False)
		return _success(text, {"alert": data})

	return Tool(
	    name="gh_secret_scanning_alert",
	    description="Fetch GitHub secret scanning alert details",
	    parameters={
	        "type": "object",
	        "properties": {
	            "repo": {
	                "type": "string",
	                "description": "owner/repo (defaults to current org_repo)",
	            },
	            "alert_number": {
	                "type": "integer",
	                "description": "Secret scanning alert number",
	            },
	        },
	    },
	    handler=handler,
	)


def secret_scanning_alert_locations_tool(config: Config,
                                         context_repo: str | None,
                                         context_alert_id: str | None) -> Tool:
	"""Fetch secret scanning alert locations via GitHub API."""

	def handler(invocation: ToolInvocation) -> ToolResult:
		params: dict[str, Any] = invocation.get("arguments") or {}
		repo = params.get("repo") or context_repo
		alert_number = params.get("alert_number") or context_alert_id
		token = config.github_token
		if not repo or not alert_number:
			raise ValueError("repo and alert_number are required")
		if not token:
			return _failure("GitHub token required. Set GITHUB_TOKEN in .env")
		try:
			alert_num_int = int(alert_number)
		except Exception as e:  # noqa: BLE001
			raise ValueError("alert_number must be an integer") from e
		owner, name = _parse_repo(str(repo))
		api = get_github_client(token, user_agent=DEFAULT_UA)
		locations = list_alert_locations(api, owner, name, alert_num_int)
		locations_count = len(locations) if isinstance(locations, list) else 0
		text = json.dumps(
		    {
		        "repo": repo,
		        "alert_number": alert_num_int,
		        "locations_count": locations_count,
		    }, ensure_ascii=False)
		return _success(text, {"locations": locations})

	return Tool(
	    name="gh_secret_scanning_alert_locations",
	    description="List GitHub secret scanning alert locations",
	    parameters={
	        "type": "object",
	        "properties": {
	            "repo": {
	                "type": "string",
	                "description": "owner/repo (defaults to current org_repo)",
	            },
	            "alert_number": {
	                "type":
	                "integer",
	                "description":
	                "Secret scanning alert number (defaults to current alert_id)",
	            },
	        },
	    },
	    handler=handler,
	)


@functools.lru_cache(maxsize=1)
def _import_registry():
	"""Import validate_secrets registry module.

	Returns a lightweight wrapper exposing ``get_validator``,
	``get_validator_info`` and ``ValidatorError`` without
	mutating the third-party module.

	Returns:
		Wrapper object, or None if not installed.
	"""
	try:
		from validate_secrets.core import registry as _reg
		from validate_secrets.core.exceptions import (
		    ValidatorError as _VErr, )

		class _Registry:
			"""Thin wrapper around validate_secrets."""

			get_validator = staticmethod(_reg.get_validator)
			get_validator_info = staticmethod(_reg.get_validator_info)
			ValidatorError = _VErr

		return _Registry()
	except ImportError:
		return None


def validate_secret_tool(config: Config) -> Tool:
	"""Define a tool that validates a secret using the
	validate-secrets library.

	Parameters:
		config: Application configuration.

	Returns:
		Tool instance for secret validation.
	"""

	def handler(invocation: ToolInvocation) -> ToolResult:
		params: dict[str, Any] = (invocation.get("arguments") or {})
		secret = params.get("secret")
		secret_type = params.get("secret_type")
		timeout = params.get(
		    "timeout",
		    config.validate_secret_timeout_seconds,
		)

		if not secret or not secret_type:
			raise ValueError("secret and secret_type are required")

		registry = _import_registry()
		if registry is None:
			return _failure("validate-secrets package is not installed. "
			                "Use manual verification methods instead.")

		try:
			validator_class = registry.get_validator(secret_type)
		except registry.ValidatorError:
			return _success(
			    json.dumps({
			        "secret_type":
			        secret_type,
			        "status":
			        "no_validator",
			        "message":
			        f"No validator registered for "
			        f"'{secret_type}'. Proceed with "
			        f"manual verification.",
			    }),
			    {
			        "status": "no_validator",
			        "secret_type": secret_type,
			    },
			)

		try:
			validator = validator_class(
			    notify=False,
			    debug=False,
			    timeout=timeout,
			)
			result = validator.check(secret)
		except Exception as exc:  # noqa: BLE001
			return _success(
			    json.dumps({
			        "secret_type": secret_type,
			        "status": "error",
			        "message": str(exc),
			    }),
			    {
			        "status": "error",
			        "secret_type": secret_type,
			        "error": str(exc),
			    },
			)

		status = {True: "valid", False: "invalid"}.get(result, "error")
		try:
			metadata = validator.get_metadata()
		except Exception:  # noqa: BLE001
			metadata = {"name": secret_type}

		return _success(
		    json.dumps({
		        "secret_type":
		        secret_type,
		        "status":
		        status,
		        "validator_name":
		        metadata.get("name", secret_type),
		        "validator_description":
		        metadata.get("description", ""),
		    }),
		    {
		        "status": status,
		        "secret_type": secret_type,
		        "validator": metadata,
		    },
		)

	return Tool(
	    name="validate_secret",
	    description=("Validate a secret using the validate-secrets "
	                 "library. Returns valid/invalid/error/no_validator."),
	    parameters={
	        "type": "object",
	        "properties": {
	            "secret": {
	                "type": "string",
	                "description": "The secret value to validate",
	            },
	            "secret_type": {
	                "type":
	                "string",
	                "description":
	                "The secret type identifier matching "
	                "the alert's secret_type",
	            },
	            "timeout": {
	                "type":
	                "integer",
	                "description":
	                "Timeout in seconds for network-based "
	                "validators (default: 30)",
	            },
	        },
	        "required": ["secret", "secret_type"],
	    },
	    handler=handler,
	)


def list_secret_validators_tool() -> Tool:
	"""Define a tool that lists available secret validators.

	Returns:
		Tool instance for listing validators.
	"""

	def handler(invocation: ToolInvocation) -> ToolResult:
		registry = _import_registry()
		if registry is None:
			return _failure("validate-secrets package is not installed.")

		try:
			info = registry.get_validator_info()
			validators = [{
			    "name": name,
			    "description": meta.get("description", ""),
			} for name, meta in info.items()]
			return _success(
			    json.dumps({
			        "validators": validators,
			        "count": len(validators),
			    }),
			    {"validators": validators},
			)
		except Exception as exc:  # noqa: BLE001
			return _failure(f"Failed to list validators: {exc}")

	return Tool(
	    name="list_secret_validators",
	    description=("List available secret validators from the "
	                 "validate-secrets library."),
	    parameters={
	        "type": "object",
	        "properties": {},
	    },
	    handler=handler,
	)


def get_session_tools(config: Config, org_repo: str | None,
                      alert_id: str | None) -> list[Tool]:
	"""Return tools to register for a session."""
	return [
	    secret_scanning_alert_tool(config, org_repo, alert_id),
	    secret_scanning_alert_locations_tool(config, org_repo, alert_id),
	    validate_secret_tool(config),
	    list_secret_validators_tool(),
	]


__all__ = [
    "get_session_tools",
    "secret_scanning_alert_tool",
    "secret_scanning_alert_locations_tool",
    "validate_secret_tool",
    "list_secret_validators_tool",
]
