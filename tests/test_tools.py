import json
import pytest

from secret_validator_grunt.integrations.copilot_tools import (
    secret_scanning_alert_tool,
    secret_scanning_alert_locations_tool,
    validate_secret_tool,
    list_secret_validators_tool,
    _import_registry,
)


def test_secret_scanning_alert_tool_invokes_handler(monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools.get_alert",
	    lambda api, owner, repo, alert_number: {
	        "number":
	        alert_number,
	        "state":
	        "open",
	        "secret_type":
	        "mailchimp_api_key",
	        "locations_url":
	        "https://api.github.com/repos/org/repo/secret-scanning/alerts/1/locations",
	    },
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "1")
	handler = tool.handler
	result = handler({
	    "session_id": "s",
	    "tool_call_id": "t",
	    "tool_name": tool.name,
	    "arguments": {}
	})
	assert result["data"]["alert"]["number"] == 1
	text = json.loads(result["textResultForLlm"])
	assert text["state"] == "open"
	assert text["secret_type"] == "mailchimp_api_key"
	assert "locations_url" in text


def test_secret_scanning_alert_locations_tool_invokes_handler(monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools.list_alert_locations",
	    lambda api, owner, repo, alert_number: [{
	        "type": "commit",
	        "details": {
	            "path": "connections-config.txt"
	        }
	    }],
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "2")
	handler = tool.handler
	result = handler({
	    "session_id": "s",
	    "tool_call_id": "t",
	    "tool_name": tool.name,
	    "arguments": {}
	})
	assert result["data"]["locations"][0]["type"] == "commit"
	assert json.loads(result["textResultForLlm"])["locations_count"] == 1


def test_secret_scanning_alert_locations_tool_paginates(monkeypatch):
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools.list_alert_locations",
	    lambda api, owner, repo, alert_number: [
	        {
	            "type": "commit",
	            "details": {
	                "path": "a.txt"
	            }
	        },
	        {
	            "type": "wiki_commit",
	            "details": {
	                "path": "b.md"
	            }
	        },
	    ],
	)
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(
	    Config(COPILOT_CLI_URL="http://x", GITHUB_TOKEN="test"), "org/repo",
	    "2")
	handler = tool.handler
	result = handler({
	    "session_id": "s",
	    "tool_call_id": "t",
	    "tool_name": tool.name,
	    "arguments": {}
	})
	locations = result["data"]["locations"]
	assert len(locations) == 2
	assert locations[0]["type"] == "commit"
	assert locations[1]["type"] == "wiki_commit"
	assert json.loads(result["textResultForLlm"])["locations_count"] == 2


def test_secret_scanning_alert_tool_requires_params():
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_tool(Config(COPILOT_CLI_URL="http://x"), None,
	                                  None)
	handler = tool.handler
	with pytest.raises(ValueError):
		handler({
		    "session_id": "s",
		    "tool_call_id": "t",
		    "tool_name": tool.name,
		    "arguments": {}
		})


def test_secret_scanning_alert_locations_tool_requires_params():
	from secret_validator_grunt.models.config import Config
	tool = secret_scanning_alert_locations_tool(
	    Config(COPILOT_CLI_URL="http://x"), None, None)
	handler = tool.handler
	with pytest.raises(ValueError):
		handler({
		    "session_id": "s",
		    "tool_call_id": "t",
		    "tool_name": tool.name,
		    "arguments": {}
		})


# ── validate_secret tool tests ──────────────────────────────


def _make_invocation(tool, **arguments):
	"""Build a minimal ToolInvocation dict for testing."""
	return {
	    "session_id": "s",
	    "tool_call_id": "t",
	    "tool_name": tool.name,
	    "arguments": arguments,
	}


def _cfg(**overrides):
	"""Create a Config with sensible defaults for tool tests."""
	from secret_validator_grunt.models.config import Config
	defaults = {"COPILOT_CLI_URL": "http://x"}
	defaults.update(overrides)
	return Config(**defaults)


def test_validate_secret_requires_secret_and_type():
	"""Handler raises ValueError when both are missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		tool.handler(_make_invocation(tool))


def test_validate_secret_requires_secret():
	"""Handler raises ValueError when secret is missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		tool.handler(_make_invocation(tool, secret_type="some_type"))


def test_validate_secret_requires_secret_type():
	"""Handler raises ValueError when secret_type is missing."""
	tool = validate_secret_tool(_cfg())
	with pytest.raises(ValueError, match="required"):
		tool.handler(_make_invocation(tool, secret="some_secret"))


def test_validate_secret_no_validator(monkeypatch):
	"""Returns no_validator for unregistered secret_type."""
	tool = validate_secret_tool(_cfg())
	result = tool.handler(
	    _make_invocation(
	        tool,
	        secret="abc123",
	        secret_type="unknown_type_xyz",
	    ))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "no_validator"
	assert "unknown_type_xyz" in body["message"]
	assert result["data"]["status"] == "no_validator"


def test_validate_secret_valid(monkeypatch):
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
	result = tool.handler(
	    _make_invocation(tool, secret="s3cr3t", secret_type="fake"))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "valid"
	assert body["validator_name"] == "fake"
	assert result["data"]["status"] == "valid"


def test_validate_secret_invalid(monkeypatch):
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
	result = tool.handler(
	    _make_invocation(tool, secret="bad", secret_type="fake"))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "invalid"


def test_validate_secret_error_in_check(monkeypatch):
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
	result = tool.handler(
	    _make_invocation(tool, secret="x", secret_type="fake"))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "error"
	assert "network timeout" in body["message"]


def test_validate_secret_check_returns_none(monkeypatch):
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
	result = tool.handler(
	    _make_invocation(tool, secret="x", secret_type="fake"))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "error"
	assert result["data"]["status"] == "error"


def test_validate_secret_registry_not_installed(monkeypatch):
	"""Returns failure when validate-secrets not installed."""
	monkeypatch.setattr(
	    "secret_validator_grunt.integrations.copilot_tools"
	    "._import_registry",
	    lambda: None,
	)
	tool = validate_secret_tool(_cfg())
	result = tool.handler(_make_invocation(tool, secret="x", secret_type="t"))
	assert result["resultType"] == "failure"
	assert "not installed" in result["textResultForLlm"]


def test_validate_secret_uses_config_timeout(monkeypatch):
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
	tool.handler(_make_invocation(tool, secret="x", secret_type="fake"))
	assert captured["timeout"] == 42


def test_validate_secret_override_timeout(monkeypatch):
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
	tool.handler(
	    _make_invocation(
	        tool,
	        secret="x",
	        secret_type="fake",
	        timeout=99,
	    ))
	assert captured["timeout"] == 99


def test_validate_secret_metadata_failure_preserves_result(monkeypatch, ):
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
	result = tool.handler(
	    _make_invocation(tool, secret="x", secret_type="my_type"))
	body = json.loads(result["textResultForLlm"])
	assert body["status"] == "valid"
	assert body["validator_name"] == "my_type"


# ── list_secret_validators tool tests ───────────────────────


def test_list_validators_returns_validators():
	"""Lists all registered validators."""
	tool = list_secret_validators_tool()
	result = tool.handler(_make_invocation(tool))
	body = json.loads(result["textResultForLlm"])
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
	assert result["resultType"] == "failure"
	assert "not installed" in result["textResultForLlm"]


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
