"""Tests for shared session utilities in core/session.py."""

import pytest
import asyncio

from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.core.session import (
	resolve_run_params,
	load_and_validate_template,
	discover_all_disabled_skills,
	send_and_collect,
	destroy_session_safe,
)


# ── resolve_run_params ────────────────────────────────────────────────


def test_resolve_run_params_passthrough():
	"""Returns existing RunParams unchanged."""
	rp = RunParams(org_repo="o/r", alert_id="1")
	assert resolve_run_params(rp, None, None) is rp


def test_resolve_run_params_from_strings():
	"""Creates RunParams from org_repo and alert_id when None."""
	rp = resolve_run_params(None, "owner/repo", "42")
	assert rp.org_repo == "owner/repo"
	assert rp.alert_id == "42"


def test_resolve_run_params_missing_raises():
	"""Raises ValueError when all params are None."""
	with pytest.raises(ValueError, match="org_repo and alert_id are required"):
		resolve_run_params(None, None, None)


def test_resolve_run_params_missing_alert_raises():
	"""Raises ValueError when alert_id is missing."""
	with pytest.raises(ValueError):
		resolve_run_params(None, "o/r", None)


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

	async def send_and_wait(self, prompt_dict, timeout=None):
		if self._error:
			raise self._error
		return self._response

	async def abort(self):
		self.aborted = True

	async def destroy(self):
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
		await send_and_collect(
			session, "prompt", 10, collector, "0", reraise=True)


@pytest.mark.asyncio
async def test_send_and_collect_reraise_false():
	"""Appends error to raw when reraise=False (judge behavior)."""
	session = _FakeSession(error=RuntimeError("boom"))
	collector = _FakeCollector()
	result = await send_and_collect(
		session, "prompt", 10, collector, "0", reraise=False)
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
	"""Logs but does not raise on destroy error."""

	class _FailSession:
		async def destroy(self):
			raise RuntimeError("destroy failed")

	await destroy_session_safe(_FailSession(), "test")  # should not raise
