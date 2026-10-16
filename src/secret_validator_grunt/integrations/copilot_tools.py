"""
Copilot session tools.

Defines custom tools for Copilot sessions that interact with
GitHub's Secret Scanning API and the validate-secrets library.
"""

from __future__ import annotations

import asyncio
import json
import functools
from typing import Any

from copilot import Tool, ToolInvocation, ToolResult
from pydantic import ValidationError

from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.github_tool_params import GitHubToolParams
from secret_validator_grunt.integrations.github_evidence import GitHubEvidence


def _github_params(invocation: ToolInvocation, context_repo: str | None,
                   context_alert_id: str | None) -> GitHubToolParams:
	"""Apply only omitted defaults; explicit invalid arguments must fail."""
	return GitHubToolParams.model_validate({
	    "repo": context_repo,
	    "alert_number": context_alert_id,
	    **(invocation.arguments or {}),
	})


def _success(text: str) -> ToolResult:
	"""Build a successful ToolResult; only the text is shown to the LLM."""
	return ToolResult(
	    text_result_for_llm=text,
	    result_type="success",
	    tool_telemetry={},
	)


def _failure(msg: str) -> ToolResult:
	"""Build a failure ToolResult with an error message."""
	return ToolResult(
	    text_result_for_llm=msg,
	    result_type="failure",
	    error=msg,
	    tool_telemetry={},
	)


def secret_scanning_alert_tool(config: Config, context_repo: str | None,
                               context_alert_id: str | None,
                               evidence: GitHubEvidence | None = None) -> Tool:
	"""Define a tool that fetches secret scanning alert details via GitHub API."""
	source = evidence or GitHubEvidence(config.github_token)

	async def handler(invocation: ToolInvocation) -> ToolResult:
		"""Return real evidence or an explicit tool failure."""
		try:
			params = _github_params(invocation, context_repo, context_alert_id)
			return _success(await source.fetch(params))
		except (ValidationError, RuntimeError) as exc:
			return _failure(str(exc))

	return Tool(
	    name="gh_secret_scanning_alert",
	    description=(
	        "Fetch full alert facts including the secret and validity. "
	        "Reuses this run's timestamped snapshot; set refresh=true "
	        "to check current rotation/resolution state."),
	    parameters={
	        "type": "object",
	        "properties": {
	            "refresh": {
	                "type": "boolean",
	                "default": False,
	                "description":
	                "Fetch current facts instead of the snapshot",
	            },
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


def secret_scanning_alert_locations_tool(
        config: Config, context_repo: str | None, context_alert_id: str | None,
        evidence: GitHubEvidence | None = None) -> Tool:
	"""Fetch secret scanning alert locations via GitHub API."""
	source = evidence or GitHubEvidence(config.github_token)

	async def handler(invocation: ToolInvocation) -> ToolResult:
		"""Return a reusable page without blocking other agents."""
		try:
			params = _github_params(invocation, context_repo, context_alert_id)
			return _success(await source.fetch(params, locations=True))
		except (ValidationError, RuntimeError) as exc:
			return _failure(str(exc))

	return Tool(
	    name="gh_secret_scanning_alert_locations",
	    description=(
	        "Fetch one page of full secret scanning locations. "
	        "Follow next_page until null; locations_count is only "
	        "the count on this page, not the alert total. Pages are "
	        "cached for this run; refresh=true re-fetches this page."),
	    parameters={
	        "type": "object",
	        "properties": {
	            "refresh": {
	                "type":
	                "boolean",
	                "default":
	                False,
	                "description":
	                "Re-fetch this page; repeat on each page "
	                "when refreshing the entire location set",
	            },
	            "page": {
	                "type": "integer",
	                "minimum": 1,
	                "default": 1,
	            },
	            "per_page": {
	                "type": "integer",
	                "minimum": 1,
	                "maximum": 100,
	                "default": 50,
	            },
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

	def validate(invocation: ToolInvocation) -> ToolResult:
		"""Run an uncached provider check on a worker thread."""
		params: dict[str, Any] = (invocation.arguments or {})
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
			    }))

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
			    }))

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
		    }))

	async def handler(invocation: ToolInvocation) -> ToolResult:
		"""Keep provider network calls off the session event loop."""
		return await asyncio.to_thread(validate, invocation)

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
			    }))
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
                      alert_id: str | None,
                      evidence: GitHubEvidence | None = None) -> list[Tool]:
	"""Return tools to register for a session."""
	source = evidence or GitHubEvidence(config.github_token)
	return [
	    secret_scanning_alert_tool(config, org_repo, alert_id, source),
	    secret_scanning_alert_locations_tool(config, org_repo, alert_id,
	                                         source),
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
