import json

import pytest

from secret_validator_grunt.core.runner import (
	run_all,
	_persist_eval_results,
)
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.eval_result import EvalCheck, EvalResult
from secret_validator_grunt.models.judge_result import JudgeResult, JudgeScore
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.models.run_result import AgentRunResult


class DummySession:

	def __init__(self, response_content: str):
		self.response_content = response_content
		self._handler = None
		self.last_prompt = None

	def on(self, handler):
		self._handler = handler
		return lambda: None

	async def send_and_wait(self, options, timeout=None):
		# simulate minimal response structure
		prompt = options.get("prompt") if isinstance(options, dict) else None
		if prompt is not None:
			self.last_prompt = prompt

		class DummyData:
			content = self.response_content

		class DummyResp:
			data = DummyData()

		return DummyResp()

	async def destroy(self):
		return None

	async def get_messages(self):
		return []


class DummyClient:

	def __init__(self, analysis_contents, judge_content):
		self.analysis_contents = analysis_contents
		self.judge_content = judge_content
		self.calls = 0
		self.session_configs = []
		self.sessions = []

	async def start(self):
		return None

	async def stop(self):
		return None

	async def create_session(self, *args, **kwargs):
		if self.calls < len(self.analysis_contents):
			content = self.analysis_contents[self.calls]
		else:
			content = self.judge_content
		self.calls += 1
		if args and isinstance(args[0], dict):
			self.session_configs.append(args[0])
		session = DummySession(content)
		self.sessions.append(session)
		return session


@pytest.mark.asyncio
async def test_run_all_saves_final_report(tmp_path, monkeypatch):
	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path),
	             ANALYSIS_COUNT=1, MAX_CONTINUATION_ATTEMPTS=0)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)
	analysis_md = """# Secret Validation Report: Alert ID 1\n\n## Executive Summary\n\n| Item | Value |\n| --- | --- |\n| Repository | org/repo |\n| Alert ID | 1 |\n| Secret Type | type |\n| Verdict | OK |\n| Confidence Score | 5/10 (Medium) |\n| Risk Level | Medium |\n| Status | Open |\n| Analyst | test |\n| Report Date | 2026-01-28 |\n\n> **Key Finding:** test\n"""
	judge_json = """Now I'll judge.Now I'll judge.```json\n{\n  \"winner_index\": 0,\n  \"scores\": [{\n    \"report_index\": 0,\n    \"score\": 1\n  }]\n}\n```"""
	client = DummyClient([analysis_md], judge_json)
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)

	outcome = await run_all(
	    cfg, RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert outcome.judge_result.winner_index == 0
	alert_dir = tmp_path / "org" / "repo" / "1"
	assert (alert_dir / "final-report.md").exists()
	assert (alert_dir / "report-0.md").exists()


@pytest.mark.asyncio
async def test_run_all_attaches_eval_results(tmp_path, monkeypatch):
	"""Eval checks are always run and attached to analysis results."""
	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path),
	             ANALYSIS_COUNT=1, MAX_CONTINUATION_ATTEMPTS=0)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)
	# Minimal report missing several required sections — evals should flag it
	analysis_md = (
	    "# Secret Validation Report: Alert ID 1\n\n"
	    "## Executive Summary\n\n"
	    "| Item | Value |\n| --- | --- |\n"
	    "| Repository | org/repo |\n| Alert ID | 1 |\n"
	    "| Secret Type | type |\n| Verdict | TRUE_POSITIVE |\n"
	    "| Confidence Score | 5/10 (Medium) |\n"
	    "| Risk Level | Medium |\n| Status | Open |\n"
	    "| Analyst | test |\n| Report Date | 2026-01-28 |\n\n"
	    "> **Key Finding:** test\n"
	)
	judge_json = (
	    '```json\n{"winner_index": 0, "scores": '
	    '[{"report_index": 0, "score": 1}]}\n```'
	)
	client = DummyClient([analysis_md], judge_json)
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)
	outcome = await run_all(
	    cfg, RunParams(org_repo="org/repo", alert_id="1"),
	)
	# Eval result should be attached
	res = outcome.analysis_results[0]
	assert res.eval_result is not None
	assert len(res.eval_result.checks) > 0
	# This minimal report is missing most sections, so evals should fail
	assert res.eval_result.passed is False
	failed_names = {c.name for c in res.eval_result.checks if not c.passed}
	assert "has_required_sections" in failed_names


@pytest.mark.asyncio
async def test_run_all_handles_analysis_exception(tmp_path, monkeypatch):
	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path),
	             ANALYSIS_COUNT=1, MAX_CONTINUATION_ATTEMPTS=0)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)

	async def boom(*args, **kwargs):
		raise RuntimeError("boom")

	async def dummy_judge(client, config, agent, results,
	                      run_params=None, progress_cb=None):
		return JudgeResult(
		    winner_index=-1,
		    scores=[JudgeScore(report_index=0, score=0)],
		    raw_response="",
		)

	client = DummyClient([], "{}")
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)
	monkeypatch.setattr("secret_validator_grunt.core.runner.run_analysis",
	                    boom)
	monkeypatch.setattr("secret_validator_grunt.core.runner.run_judge",
	                    dummy_judge)

	outcome = await run_all(
	    cfg, RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert len(outcome.analysis_results) == 1
	assert outcome.analysis_results[0].error == "boom"


@pytest.mark.asyncio
async def test_run_all_uses_custom_agents_and_prompts(tmp_path, monkeypatch):
	# Create skill directories with actual skill subdirectories
	skill1 = tmp_path / "skill1"
	skill2 = tmp_path / "skill2"
	skill1.mkdir()
	skill2.mkdir()
	# Add skill subdirectories with SKILL.md so they're recognized
	(skill1 / "test-skill-a").mkdir()
	(skill1 / "test-skill-a" /
	 "SKILL.md").write_text("---\nname: test-skill-a\n---\n")
	(skill2 / "test-skill-b").mkdir()
	(skill2 / "test-skill-b" /
	 "SKILL.md").write_text("---\nname: test-skill-b\n---\n")
	cfg = Config(
	    COPILOT_CLI_URL="http://x",
	    OUTPUT_DIR=str(tmp_path),
	    ANALYSIS_COUNT=1,
	    SKILL_DIRECTORIES=f"{skill1},{skill2}",
	    DISABLED_SKILLS="skill2",
	    MAX_CONTINUATION_ATTEMPTS=0,
	)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text(
	    """---\nname: a\ntools: [\"tool1\"]\n---\nprompt""",
	    encoding="utf-8",
	)
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)

	client = DummyClient(["analysis"], "{}")
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)

	await run_all(
	    cfg, RunParams(org_repo="org/repo", alert_id="1"),
	)

	assert client.session_configs, "Expected at least one session config"
	assert client.session_configs[0]["custom_agents"][0]["name"] == "a"
	assert client.session_configs[0]["available_tools"] == ["tool1"]
	assert client.sessions[0].last_prompt is not None
	assert client.sessions[0].last_prompt.startswith("@a")
	# sessions[1] = challenger, sessions[2] = judge
	assert client.sessions[2].last_prompt.startswith("@a")

	skills = client.session_configs[0]["skill_directories"]
	assert skills[0].startswith(str(tmp_path))
	assert skills[-2:] == [str(skill1), str(skill2)]
	# Config disabled_skills + hidden skills (underscore-prefixed) are combined
	assert "skill2" in client.session_configs[0]["disabled_skills"]
	assert "skill2" in client.session_configs[2]["disabled_skills"]

	# judge session config should include system_message and no streaming
	judge_cfg = client.session_configs[2]
	assert judge_cfg["streaming"] is False
	assert "system_message" in judge_cfg


# -------------------------------------------------------------------
# _persist_eval_results unit tests
# -------------------------------------------------------------------

def _make_eval_result(report_id: str = "run-0") -> EvalResult:
	"""Build a minimal EvalResult for testing."""
	return EvalResult(
		report_id=report_id,
		checks=[
			EvalCheck(
				name="has_verdict",
				passed=True,
				message="Verdict present",
			),
			EvalCheck(
				name="has_required_sections",
				passed=False,
				message="Missing sections",
			),
		],
	)


def _make_result(
    workspace: str | None,
    eval_result: EvalResult | None = None,
) -> AgentRunResult:
	"""Build a minimal AgentRunResult for persistence tests."""
	return AgentRunResult(
		run_id="run-0",
		workspace=workspace,
		eval_result=eval_result,
	)


class TestPersistEvalResults:
	"""Tests for _persist_eval_results."""

	def test_writes_eval_result_to_diagnostics(self, tmp_path):
		"""Eval result is appended to existing diagnostics.json."""
		ws = tmp_path / "ws"
		ws.mkdir()
		diag = ws / "diagnostics.json"
		diag.write_text(json.dumps({"run_id": "run-0"}))

		ev = _make_eval_result()
		res = _make_result(str(ws), ev)
		_persist_eval_results([res])

		data = json.loads(diag.read_text())
		assert "eval_result" in data
		assert data["eval_result"]["report_id"] == "run-0"
		assert len(data["eval_result"]["checks"]) == 2
		# Original keys preserved
		assert data["run_id"] == "run-0"

	def test_skips_when_no_workspace(self, tmp_path):
		"""Results without a workspace are silently skipped."""
		res = _make_result(workspace=None, eval_result=_make_eval_result())
		# Should not raise
		_persist_eval_results([res])

	def test_skips_when_no_eval_result(self, tmp_path):
		"""Results without an eval_result are silently skipped."""
		ws = tmp_path / "ws"
		ws.mkdir()
		diag = ws / "diagnostics.json"
		diag.write_text(json.dumps({"run_id": "run-0"}))

		res = _make_result(str(ws), eval_result=None)
		_persist_eval_results([res])

		data = json.loads(diag.read_text())
		assert "eval_result" not in data

	def test_skips_when_diagnostics_missing(self, tmp_path):
		"""No-op when diagnostics.json does not exist."""
		ws = tmp_path / "ws"
		ws.mkdir()
		# No diagnostics.json created
		res = _make_result(str(ws), eval_result=_make_eval_result())
		_persist_eval_results([res])
		assert not (ws / "diagnostics.json").exists()

	def test_handles_multiple_results(self, tmp_path):
		"""All qualifying results are persisted independently."""
		results = []
		for i in range(3):
			ws = tmp_path / f"ws-{i}"
			ws.mkdir()
			diag = ws / "diagnostics.json"
			diag.write_text(json.dumps({"run_id": f"run-{i}"}))
			ev = _make_eval_result(report_id=f"run-{i}")
			results.append(_make_result(str(ws), ev))

		_persist_eval_results(results)

		for i in range(3):
			data = json.loads(
			    (tmp_path / f"ws-{i}" / "diagnostics.json").read_text()
			)
			assert data["eval_result"]["report_id"] == f"run-{i}"

	def test_handles_corrupt_diagnostics_gracefully(self, tmp_path):
		"""Corrupt diagnostics.json does not raise."""
		ws = tmp_path / "ws"
		ws.mkdir()
		diag = ws / "diagnostics.json"
		diag.write_text("not valid json!!!")

		res = _make_result(str(ws), eval_result=_make_eval_result())
		# Should not raise — logs a debug message instead
		_persist_eval_results([res])
