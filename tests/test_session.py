"""Tests for shared session utilities in core/session.py."""

import pytest
import asyncio

from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.core.session import (
    build_session_config,
    load_and_validate_template,
    discover_all_disabled_skills,
    send_and_collect,
    destroy_session_safe,
    is_response_empty,
    verify_runtime_skills,
)

# ── build_session_config ───────────────────────────────────────────────


def test_build_session_config_preselects_agent():
	"""Agent is pre-selected and permissions are auto-approved."""
	agent = AgentConfig(name="validator", prompt="p", tools=["bash"])
	cfg = build_session_config(
	    model="m",
	    streaming=True,
	    agent=agent,
	    tools=[],
	    skill_directories=["/skills"],
	    system_message="extra",
	    session_id="sid",
	    working_directory="/work",
	)
	assert cfg["agent"] == "validator"
	assert cfg["custom_agents"][0]["name"] == "validator"
	assert cfg["available_tools"] == ["bash"]
	assert cfg["skill_directories"] == ["/skills"]
	assert cfg["system_message"] == {"mode": "append", "content": "extra"}
	assert cfg["session_id"] == "sid"
	assert cfg["working_directory"] == "/work"
	assert callable(cfg["on_permission_request"])
	# Host repo instructions (AGENTS.md, .github/instructions) are not
	# rendered into stage agents' context
	assert cfg["skip_custom_instructions"] is True


def test_build_session_config_omits_optional_keys():
	"""Optional keys are omitted so SDK defaults apply."""
	agent = AgentConfig(name="a", prompt="p")
	cfg = build_session_config(
	    model="m",
	    streaming=False,
	    agent=agent,
	    tools=[],
	    skill_directories=[],
	)
	for key in ("system_message", "session_id", "working_directory"):
		assert key not in cfg
	assert cfg["disabled_skills"] is None
	# Agent without a tools list leaves the session unrestricted
	assert cfg["available_tools"] is None


def test_build_session_config_preserves_empty_tools():
	"""An explicit empty tool list yields a tool-free session."""
	agent = AgentConfig(name="j", prompt="p", tools=[])
	cfg = build_session_config(
	    model="m",
	    streaming=False,
	    agent=agent,
	    tools=[],
	    skill_directories=[],
	)
	assert cfg["available_tools"] == []
	assert cfg["custom_agents"][0]["tools"] == []


def test_session_config_accepts_creation_time_handler() -> None:
	"""The current SDK accepts the supplied collector callback directly."""
	import inspect
	from copilot import CopilotClient
	from copilot.generated.session_events import SessionEvent

	def collect(event: SessionEvent) -> None:
		"""Stand in for a stream collector."""

	config = build_session_config(model="test", streaming=True,
	                              agent=AgentConfig(name="a",
	                                                prompt="p"), tools=[],
	                              skill_directories=[], on_event=collect)
	inspect.signature(CopilotClient.create_session).bind(None, **config)
	assert config["on_event"] is collect


# ── load_and_validate_template ─────────────────────────────────────────


def test_load_and_validate_template_missing():
	"""Raises RuntimeError for nonexistent template."""
	with pytest.raises(RuntimeError, match="not found"):
		load_and_validate_template("/nonexistent/template.md")


def test_load_and_validate_template_success():
	"""Returns template content for valid path."""
	# Use the actual report template
	content = load_and_validate_template(
	    "src/secret_validator_grunt/templates/report.md")
	assert len(content) > 0
	assert "Report" in content or "report" in content


# ── discover_all_disabled_skills ───────────────────────────────────────


def test_discover_all_disabled_skills_merges():
	"""Merges hidden skills with config disabled_skills."""
	cfg = Config(DISABLED_SKILLS="custom_one,custom_two")
	disabled = discover_all_disabled_skills(cfg)
	# Should include config-specified skills
	assert "custom_one" in disabled
	assert "custom_two" in disabled


def test_discover_all_disabled_skills_deduplicates():
	"""Deduplicates hidden and config disabled skills."""
	cfg = Config()
	disabled = discover_all_disabled_skills(cfg)
	# No duplicates
	assert len(disabled) == len(set(disabled))


# ── send_and_collect ──────────────────────────────────────────────────


class _FakeCollector:
	"""Minimal collector stub."""

	def __init__(self, text=""):
		self.text = text


class _FakeResponse:
	"""Minimal response stub."""

	def __init__(self, content):
		self.data = type("Data", (), {"content": content})()


class _FakeSession:
	"""Minimal session stub for send_and_collect tests."""

	def __init__(self, response=None, error=None):
		self._response = response
		self._error = error
		self.aborted = False
		self.destroyed = False

	async def send_and_wait(self, prompt, *, timeout=60.0):
		if self._error:
			raise self._error
		return self._response

	async def abort(self):
		self.aborted = True

	async def disconnect(self):
		self.destroyed = True


@pytest.mark.asyncio
async def test_send_and_collect_success():
	"""Returns response content on success."""
	session = _FakeSession(response=_FakeResponse("hello"))
	collector = _FakeCollector()
	result = await send_and_collect(session, "prompt", 10, collector, "0")
	assert result == "hello"


@pytest.mark.asyncio
async def test_send_and_collect_timeout_fallback():
	"""Falls back to collector text on timeout."""
	session = _FakeSession(error=asyncio.TimeoutError())
	collector = _FakeCollector(text="fallback text")
	result = await send_and_collect(session, "prompt", 10, collector, "0")
	assert result == "fallback text"
	assert session.aborted is True


@pytest.mark.asyncio
async def test_send_and_collect_reraise_true():
	"""Re-raises non-timeout exceptions when reraise=True."""
	session = _FakeSession(error=RuntimeError("boom"))
	collector = _FakeCollector()
	with pytest.raises(RuntimeError, match="boom"):
		await send_and_collect(session, "prompt", 10, collector, "0",
		                       reraise=True)


@pytest.mark.asyncio
async def test_send_and_collect_reraise_false():
	"""Appends error to raw when reraise=False (judge behavior)."""
	session = _FakeSession(error=RuntimeError("boom"))
	collector = _FakeCollector()
	result = await send_and_collect(session, "prompt", 10, collector, "0",
	                                reraise=False)
	assert "ERROR: boom" in result


# ── destroy_session_safe ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_destroy_session_safe_none():
	"""No-op for None session."""
	await destroy_session_safe(None, "test")  # should not raise


@pytest.mark.asyncio
async def test_destroy_session_safe_success():
	"""Destroys session successfully."""
	session = _FakeSession()
	await destroy_session_safe(session, "test")
	assert session.destroyed is True


@pytest.mark.asyncio
async def test_destroy_session_safe_error():
	"""Logs but does not raise on disconnect error."""

	class _FailSession:

		async def disconnect(self):
			raise RuntimeError("disconnect failed")

	await destroy_session_safe(_FailSession(), "test")  # should not raise


# ── is_response_empty ─────────────────────────────────────────────────


class TestIsEmpty:
	"""Tests for the is_response_empty helper."""

	def test_none(self):
		"""None is empty."""
		assert is_response_empty(None, 500) is True

	def test_empty_string(self):
		"""Empty string is empty."""
		assert is_response_empty("", 500) is True

	def test_whitespace_only(self):
		"""Whitespace-only string is empty."""
		assert is_response_empty("   \n\t  ", 500) is True

	def test_short_string(self):
		"""String shorter than min_length is empty."""
		assert is_response_empty("short response", 500) is True

	def test_long_enough(self):
		"""String at or above min_length is not empty."""
		assert is_response_empty("x" * 500, 500) is False

	def test_above_min(self):
		"""String well above min_length is not empty."""
		assert is_response_empty("x" * 1000, 500) is False

	def test_zero_min_length(self):
		"""With min_length=0, any non-empty string passes."""
		assert is_response_empty("hi", 0) is False

	def test_zero_min_length_empty(self):
		"""With min_length=0, empty string is still empty."""
		assert is_response_empty("", 0) is True


# ── send_and_collect continuation ─────────────────────────────────────


class _ContinuationSession:
	"""Session stub that returns different responses per call."""

	def __init__(self, responses: list):
		"""Initialize with ordered responses.

		Parameters:
			responses: List of _FakeResponse, None, or Exception.
		"""
		self._responses = list(responses)
		self._call_count = 0
		self.prompts_received: list[str] = []
		self.aborted = False

	async def send_and_wait(self, prompt, *, timeout=60.0):
		self.prompts_received.append(prompt)
		idx = self._call_count
		self._call_count += 1
		if idx < len(self._responses):
			val = self._responses[idx]
			if isinstance(val, Exception):
				raise val
			return val
		return None

	async def abort(self):
		self.aborted = True

	async def disconnect(self):
		pass


@pytest.mark.asyncio
async def test_continuation_not_triggered_for_good_response():
	"""No continuation sent when response exceeds min_response_length."""
	good_content = "x" * 600
	session = _ContinuationSession([_FakeResponse(good_content)])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue",
	    max_continuations=2,
	    min_response_length=500,
	)
	assert result == good_content
	assert len(session.prompts_received) == 1


@pytest.mark.asyncio
async def test_continuation_triggered_on_empty_response():
	"""Continuation prompt sent when first response is empty."""
	good_content = "y" * 600
	session = _ContinuationSession([
	    _FakeResponse(""),  # empty first response
	    _FakeResponse(good_content),  # good continuation
	])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue please",
	    max_continuations=2,
	    min_response_length=500,
	)
	assert result == good_content
	assert len(session.prompts_received) == 2
	assert session.prompts_received[0] == "initial"
	assert session.prompts_received[1] == "continue please"


@pytest.mark.asyncio
async def test_continuation_triggered_on_short_response():
	"""Continuation prompt sent when first response is too short."""
	good_content = "z" * 600
	session = _ContinuationSession([
	    _FakeResponse("too short"),
	    _FakeResponse(good_content),
	])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue",
	    max_continuations=2,
	    min_response_length=500,
	)
	assert result == good_content
	assert len(session.prompts_received) == 2


@pytest.mark.asyncio
async def test_continuation_multiple_retries():
	"""Multiple continuation attempts before success."""
	good_content = "w" * 600
	session = _ContinuationSession([
	    _FakeResponse(""),  # empty
	    _FakeResponse("tiny"),  # still too short
	    _FakeResponse(good_content),  # success on 3rd
	])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue",
	    max_continuations=3,
	    min_response_length=500,
	)
	assert result == good_content
	assert len(session.prompts_received) == 3


@pytest.mark.asyncio
async def test_continuation_exhausted():
	"""Returns last response when max continuations exhausted."""
	session = _ContinuationSession([
	    _FakeResponse(""),
	    _FakeResponse(""),
	    _FakeResponse("short"),
	])
	collector = _FakeCollector()
	cb_messages = []

	def track_cb(run_id, msg):
		cb_messages.append(msg)

	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    progress_cb=track_cb,
	    continuation_prompt="continue",
	    max_continuations=2,
	    min_response_length=500,
	)
	# Returns whatever the last attempt produced
	assert result == "short"
	# 3 total calls: 1 initial + 2 continuations
	assert len(session.prompts_received) == 3
	# Progress callback should report continuation attempts
	continuation_msgs = [m for m in cb_messages if "continuation" in m.lower()]
	assert len(continuation_msgs) >= 2


@pytest.mark.asyncio
async def test_continuation_none_response():
	"""Continuation handles None responses (send_and_wait returns None)."""
	good_content = "a" * 600
	session = _ContinuationSession([
	    None,  # None response
	    _FakeResponse(good_content),
	])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue",
	    max_continuations=2,
	    min_response_length=500,
	)
	assert result == good_content
	assert len(session.prompts_received) == 2


@pytest.mark.asyncio
async def test_no_continuation_when_prompt_is_none():
	"""No continuation when continuation_prompt is None."""
	session = _ContinuationSession([_FakeResponse("")])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt=None,
	    max_continuations=2,
	    min_response_length=500,
	)
	# Empty response, no continuation -- original behavior
	assert result == ""
	assert len(session.prompts_received) == 1


@pytest.mark.asyncio
async def test_no_continuation_when_max_is_zero():
	"""No continuation when max_continuations is 0."""
	session = _ContinuationSession([_FakeResponse("")])
	collector = _FakeCollector()
	result = await send_and_collect(
	    session,
	    "initial",
	    10,
	    collector,
	    "0",
	    continuation_prompt="continue",
	    max_continuations=0,
	    min_response_length=500,
	)
	assert result == ""
	assert len(session.prompts_received) == 1


@pytest.mark.asyncio
async def test_continuation_prompt_file_exists():
	"""continuation_task.md prompt file loads successfully."""
	from secret_validator_grunt.loaders.prompts import load_prompt
	content = load_prompt("continuation_task.md")
	assert len(content) > 50
	assert "continue" in content.lower()


# ── verify_runtime_skills ──────────────────────────────────────────────


def _runtime_manifest():
	from secret_validator_grunt.models.skill import SkillInfo, SkillManifest

	return SkillManifest(skills=[
	    SkillInfo(name="req", description="r", path="/r", required=True),
	    SkillInfo(name="opt", description="o", path="/o"),
	    SkillInfo(name="hidden", description="h", path="/h"),
	])


class _CatalogSession:
	"""Fake session exposing ``rpc.skills.list()``."""

	def __init__(self, entries=None, error=None):
		from types import SimpleNamespace
		from copilot.generated.rpc import SkillList

		async def _list():
			if error:
				raise error
			return SkillList.from_dict({
			    "skills": [{
			        "name": n,
			        "description": n,
			        "enabled": e,
			        "source": "builtin",
			        "userInvocable": True
			    } for n, e in entries]
			})

		self.rpc = SimpleNamespace(skills=SimpleNamespace(list=_list))


def _collector(tmp_path):
	from secret_validator_grunt.ui.streaming import StreamCollector

	return StreamCollector(run_id="0", stream_log_path=tmp_path / "s.log")


@pytest.mark.asyncio
async def test_verify_runtime_skills_all_present(tmp_path):
	"""No warning when every enabled manifest skill is in the catalog."""
	collector = _collector(tmp_path)
	progress = []
	session = _CatalogSession([("req", True), ("opt", True),
	                           ("hidden", False)])
	missing = await verify_runtime_skills(
	    session, _runtime_manifest(), ["hidden"], collector, "0",
	    lambda rid, msg: progress.append(msg))
	assert missing == []
	assert collector.skill_usage.unavailable_skills == []
	assert progress == []


@pytest.mark.asyncio
async def test_verify_runtime_skills_reports_missing(tmp_path, caplog):
	"""Missing or disabled-at-runtime skills are reported, not raised."""
	collector = _collector(tmp_path)
	progress = []
	session = _CatalogSession([("opt", False)])
	with caplog.at_level("WARNING"):
		missing = await verify_runtime_skills(
		    session, _runtime_manifest(), ["hidden"], collector, "0",
		    lambda rid, msg: progress.append(msg))
	assert missing == ["opt"]
	assert collector.skill_usage.unavailable_skills == ["opt"]
	assert progress == ["skills_unavailable: opt"]
	assert "optional skill(s)" in caplog.text


@pytest.mark.asyncio
async def test_verify_runtime_skills_without_rpc(tmp_path):
	"""Sessions without a skills RPC are skipped."""
	collector = _collector(tmp_path)
	missing = await verify_runtime_skills(_FakeSession(), _runtime_manifest(),
	                                      [], collector, "0")
	assert missing is None
	assert collector.skill_usage.unavailable_skills is None


@pytest.mark.asyncio
async def test_verify_runtime_skills_rpc_error(tmp_path):
	"""Catalog errors never fail the run."""
	collector = _collector(tmp_path)
	session = _CatalogSession(error=RuntimeError("boom"))
	missing = await verify_runtime_skills(session, _runtime_manifest(), [],
	                                      collector, "0")
	assert missing is None


@pytest.mark.asyncio
async def test_verify_runtime_skills_has_a_deadline(tmp_path, monkeypatch,
                                                    caplog) -> None:
	"""A stalled catalog must not block the analysis indefinitely."""
	from types import SimpleNamespace

	async def stalled() -> None:
		"""Simulate an RPC that never answers."""
		await asyncio.Event().wait()

	monkeypatch.setattr(
	    "secret_validator_grunt.core.session.SKILL_CATALOG_TIMEOUT_SECONDS",
	    0.01)
	session = SimpleNamespace(rpc=SimpleNamespace(skills=SimpleNamespace(
	    list=stalled)))
	collector = _collector(tmp_path)
	missing = await asyncio.wait_for(
	    verify_runtime_skills(session, _runtime_manifest(), [], collector,
	                          "0"), timeout=1)
	assert missing is None
	assert collector.skill_usage.unavailable_skills is None
	assert "could not list optional runtime skills" in caplog.text
