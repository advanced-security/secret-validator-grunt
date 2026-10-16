import json
import threading
from types import SimpleNamespace
import pytest
from copilot import ToolInvocation
from secret_validator_grunt.models.alert_locations import AlertLocationsPage

from secret_validator_grunt.integrations.copilot_tools import (
    secret_scanning_alert_tool,
    secret_scanning_alert_locations_tool,
    validate_secret_tool,
    list_secret_validators_tool,
    _import_registry,
)


def _make_invocation(tool, **arguments):
	"""Build a minimal ToolInvocation for testing."""
	return ToolInvocation(
	    session_id="s",
	    tool_call_id="t",
	    tool_name=tool.name,
	    arguments=arguments,
	)


@pytest.mark.asyncio
async def test_secret_scanning_alert_tool_invokes_handler(monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.get_github_client",
	    lambda *args, **kwargs: object())
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.get_alert",
	    lambda api, owner, repo, alert_number: {
	        "number":
	        alert_number,
	        "state":
	        "open",
	        "secret_type":
	        "mailchimp_api_key",
	        "secret":
	        "synthetic-test-secret",
	        "validity":
	        "unknown",
	        "resolution":
	        None,
	        "created_at":
	        "2026-01-01T00:00:00Z",
	        "locations_url":
	        "https://api.github.com/repos/org/repo/secret-scanning/alerts/1/locations",
	    },
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "1")
	handler = tool.handler
	result = await handler(_make_invocation(tool))
	text = json.loads(result.text_result_for_llm)
	assert text["alert_number"] == 1
	assert text["state"] == "open"
	assert text["secret_type"] == "mailchimp_api_key"
	assert "locations_url" in text
	assert text["secret"] == "synthetic-test-secret"
	assert text["validity"] == "unknown"
	assert text["resolution"] is None
	assert text["created_at"] == "2026-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_secret_scanning_alert_locations_tool_invokes_handler(
        monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.get_github_client",
	    lambda *args, **kwargs: object())
	locations = [{
	    "type": "commit",
	    "details": {
	        "path": "connections-config.txt",
	        "start_line": 12,
	        "end_line": 13,
	        "commit_sha": "test-sha",
	    },
	}]
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.list_alert_locations",
	    lambda api, owner, repo, alert_number, **kwargs: AlertLocationsPage(
	        locations=locations, page=1, per_page=50),
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "2")
	handler = tool.handler
	result = await handler(_make_invocation(tool))
	body = json.loads(result.text_result_for_llm)
	assert body["locations_count"] == 1
	assert body["locations"] == locations
	assert body["next_page"] is None


@pytest.mark.asyncio
async def test_secret_scanning_alert_locations_tool_paginates(monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.get_github_client",
	    lambda *args, **kwargs: object())
	calls = []

	def locations_page(api, owner, repo, alert_number, **kwargs):
		calls.append(kwargs)
		return AlertLocationsPage(
		    locations=[{
		        "type": "issue_body",
		        "details": {
		            "issue_number": 9
		        }
		    }], page=kwargs["page"], per_page=kwargs["per_page"], next_page=3)

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.list_alert_locations",
	    locations_page,
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "2")
	handler = tool.handler
	result = await handler(_make_invocation(tool, page=2, per_page=1))
	body = json.loads(result.text_result_for_llm)
	assert calls == [{"page": 2, "per_page": 1}]
	assert body["locations_count"] == 1
	assert body["locations"][0]["details"] == {"issue_number": 9}
	assert body["page"] == 2
	assert body["next_page"] == 3


@pytest.mark.asyncio
async def test_secret_scanning_alert_tool_requires_params():
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_tool(Config(GITHUB_TOKEN="test"), None, None)
	handler = tool.handler
	assert (await handler(_make_invocation(tool))).result_type == "failure"


@pytest.mark.asyncio
async def test_secret_scanning_alert_locations_tool_requires_params():
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(Config(GITHUB_TOKEN="test"),
	                                            None, None)
	handler = tool.handler
	assert (await handler(_make_invocation(tool))).result_type == "failure"


@pytest.mark.parametrize("arguments", [
    {
        "alert_number": 0
    },
    {
        "alert_number": -1
    },
    {
        "alert_number": True
    },
    {
        "alert_number": 1.5
    },
    {
        "repo": "org/repo/extra"
    },
    {
        "repo": ""
    },
    {
        "page": 0
    },
    {
        "per_page": 101
    },
    {
        "per_page": True
    },
    {
        "refresh": "yes"
    },
])
@pytest.mark.asyncio
async def test_github_tool_rejects_invalid_inputs(arguments: dict) -> None:
	"""Explicit invalid input must not fall back to the current alert."""
	tool = secret_scanning_alert_locations_tool(_cfg(GITHUB_TOKEN="test"),
	                                            "org/repo", "1")
	result = await tool.handler(_make_invocation(tool, **arguments))
	assert result.result_type == "failure"


@pytest.mark.asyncio
async def test_github_tool_surfaces_api_failure(monkeypatch) -> None:
	"""API errors are tool failures, not successful empty evidence."""

	def fail(*args, **kwargs):
		raise RuntimeError("GitHub API error 403")

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.github_evidence.get_github_client",
	    fail)
	tool = secret_scanning_alert_tool(_cfg(GITHUB_TOKEN="test"), "org/repo",
	                                  "1")
	result = await tool.handler(_make_invocation(tool))
	assert result.result_type == "failure"
	assert "403" in result.text_result_for_llm


# ── validate_secret tool tests ──────────────────────────────


def _cfg(**overrides):
	"""Create a Config with sensible defaults for tool tests."""
	from secret_validator_grunt.models.config import Config
	defaults = {"COPILOT_CLI_URL": "http://x"}
	defaults.update(overrides)
	return Config(**defaults)


@pytest.mark.asyncio
async def test_validate_secret_requires_secret_and_type():
	"""Handler raises ValueError when both are missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		await tool.handler(_make_invocation(tool))


@pytest.mark.asyncio
async def test_validate_secret_requires_secret():
	"""Handler raises ValueError when secret is missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		await tool.handler(_make_invocation(tool, secret_type="some_type"))


@pytest.mark.asyncio
async def test_validate_secret_requires_secret_type():
	"""Handler raises ValueError when secret_type is missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		await tool.handler(_make_invocation(tool, secret="some_secret"))


@pytest.mark.asyncio
async def test_validate_secret_no_validator(monkeypatch):
	"""Returns no_validator for unregistered secret_type."""
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(
	        tool,
	        secret="abc123",
	        secret_type="unknown_type_xyz",
	    ))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "no_validator"
	assert "unknown_type_xyz" in body["message"]


@pytest.mark.asyncio
async def test_validate_secret_valid(monkeypatch):
	"""Returns valid when checker.check returns True."""

	class FakeChecker:
		"""Stub validator returning True."""

		def __init__(self, **kw):
			pass

		def check(self, secret):
			return True

		def get_metadata(self):
			return {"name": "fake", "description": "Fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="s3cr3t", secret_type="fake"))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "valid"
	assert body["validator_name"] == "fake"


@pytest.mark.asyncio
async def test_live_validation_is_threaded_and_uncached(
        monkeypatch: pytest.MonkeyPatch) -> None:
	"""Repeated provider checks can observe rotation and never block the loop."""
	main_thread = threading.get_ident()
	checks: list[str] = []

	class Checker:
		"""Return a different live result for each verification."""

		def __init__(self, **kwargs: object) -> None:
			"""Accept the normal provider configuration."""

		def check(self, secret: str) -> bool:
			"""Record execution and simulate a revoked credential."""
			assert threading.get_ident() != main_thread
			checks.append(secret)
			return len(checks) == 1

		def get_metadata(self) -> dict[str, str]:
			"""Return minimal provider metadata."""
			return {"name": "test"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools._import_registry",
	    lambda: SimpleNamespace(get_validator=lambda name: Checker,
	                            ValidatorError=ValueError))
	tool = validate_secret_tool(_cfg())
	invocation = _make_invocation(tool, secret="synthetic", secret_type="test")
	first = await tool.handler(invocation)
	second = await tool.handler(invocation)
	assert json.loads(first.text_result_for_llm)["status"] == "valid"
	assert json.loads(second.text_result_for_llm)["status"] == "invalid"
	assert checks == ["synthetic", "synthetic"]


@pytest.mark.asyncio
async def test_validate_secret_invalid(monkeypatch):
	"""Returns invalid when checker.check returns False."""

	class FakeChecker:
		"""Stub validator returning False."""

		def __init__(self, **kw):
			pass

		def check(self, secret):
			return False

		def get_metadata(self):
			return {"name": "fake", "description": "Fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="bad", secret_type="fake"))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "invalid"


@pytest.mark.asyncio
async def test_validate_secret_error_in_check(monkeypatch):
	"""Returns error when checker.check raises an exception."""

	class FakeChecker:
		"""Stub validator that raises on check."""

		def __init__(self, **kw):
			pass

		def check(self, secret):
			raise RuntimeError("network timeout")

		def get_metadata(self):
			return {"name": "fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="x", secret_type="fake"))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "error"
	assert "network timeout" in body["message"]


@pytest.mark.asyncio
async def test_validate_secret_check_returns_none(monkeypatch):
	"""Returns error when checker.check returns None."""

	class FakeChecker:
		"""Stub validator returning None (indeterminate)."""

		def __init__(self, **kw):
			pass

		def check(self, secret):
			return None

		def get_metadata(self):
			return {"name": "fake", "description": "Fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="x", secret_type="fake"))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "error"


@pytest.mark.asyncio
async def test_validate_secret_registry_not_installed(monkeypatch):
	"""Returns failure when validate-secrets not installed."""
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: None,
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="x", secret_type="t"))
	assert result.result_type == "failure"
	assert "not installed" in result.text_result_for_llm


@pytest.mark.asyncio
async def test_validate_secret_uses_config_timeout(monkeypatch):
	"""Validator receives timeout from config default."""
	captured = {}

	class FakeChecker:
		"""Stub that captures init kwargs."""

		def __init__(self, **kw):
			captured.update(kw)

		def check(self, secret):
			return True

		def get_metadata(self):
			return {"name": "fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	cfg = _cfg(VALIDATE_SECRET_TIMEOUT_SECONDS=42)
	tool = validate_secret_tool(cfg)
	await tool.handler(_make_invocation(tool, secret="x", secret_type="fake"))
	assert captured["timeout"] == 42


@pytest.mark.asyncio
async def test_validate_secret_override_timeout(monkeypatch):
	"""Explicit timeout in arguments overrides config."""
	captured = {}

	class FakeChecker:
		"""Stub that captures init kwargs."""

		def __init__(self, **kw):
			captured.update(kw)

		def check(self, secret):
			return True

		def get_metadata(self):
			return {"name": "fake"}

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	await tool.handler(
	    _make_invocation(
	        tool,
	        secret="x",
	        secret_type="fake",
	        timeout=99,
	    ))
	assert captured["timeout"] == 99


@pytest.mark.asyncio
async def test_validate_secret_metadata_failure_preserves_result(
    monkeypatch, ):
	"""Valid check result preserved even if get_metadata fails."""

	class FakeChecker:
		"""Stub where get_metadata raises."""

		def __init__(self, **kw):
			pass

		def check(self, secret):
			return True

		def get_metadata(self):
			raise RuntimeError("metadata broken")

	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: type(
	        "R", (), {
	            "get_validator": staticmethod(lambda t: FakeChecker),
	            "ValidatorError": Exception,
	        })(),
	)
	tool = validate_secret_tool(_cfg())
	result = await tool.handler(
	    _make_invocation(tool, secret="x", secret_type="my_type"))
	body = json.loads(result.text_result_for_llm)
	assert body["status"] == "valid"
	assert body["validator_name"] == "my_type"


# ── list_secret_validators tool tests ───────────────────────


def test_list_validators_returns_validators():
	"""Lists all registered validators."""
	tool = list_secret_validators_tool()
	result = tool.handler(_make_invocation(tool))
	body = json.loads(result.text_result_for_llm)
	assert body["count"] >= 1
	names = [v["name"] for v in body["validators"]]
	assert "google_api_key" in names


def test_list_validators_not_installed(monkeypatch):
	"""Returns failure when validate-secrets not installed."""
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: None,
	)
	tool = list_secret_validators_tool()
	result = tool.handler(_make_invocation(tool))
	assert result.result_type == "failure"
	assert "not installed" in result.text_result_for_llm


# ── _import_registry helper tests ──────────────────────────


def test_import_registry_returns_module():
	"""_import_registry returns module with expected attrs."""
	reg = _import_registry()
	assert reg is not None
	assert hasattr(reg, "get_validator")
	assert hasattr(reg, "get_validator_info")
	assert hasattr(reg, "ValidatorError")


# ── get_session_tools tests ─────────────────────────────────


def test_get_session_tools_returns_four_tools():
	"""get_session_tools now returns 4 tools."""
	from secret_validator_grunt.integrations.copilot_tools import (
	    get_session_tools, )
	tools = get_session_tools(_cfg(), "org/repo", "1")
	assert len(tools) == 4
	names = {t.name for t in tools}
	assert names == {
	    "gh_secret_scanning_alert",
	    "gh_secret_scanning_alert_locations",
	    "validate_secret",
	    "list_secret_validators",
	}
