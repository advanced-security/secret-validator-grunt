import json
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

import pytest

from secret_validator_grunt.core.runner import (
    run_all,
    _persist_eval_results,
    _run_eval_checks,
)
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.eval_result import EvalCheck, EvalResult
from secret_validator_grunt.models.judge_result import JudgeResult, JudgeScore
from secret_validator_grunt.models.run_params import RunParams
from secret_validator_grunt.models.run_result import AgentRunResult


@pytest.fixture(autouse=True)
def stub_pre_clone(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Keep orchestration tests offline; cloning has its own test module."""

	async def unavailable(*args: object, **kwargs: object) -> None:
		"""Use agent fallback without accessing GitHub."""
		return None

	monkeypatch.setattr("secret_validator_grunt.core.runner.pre_clone_repo",
	                    unavailable)


class DummySession:

	def __init__(self, response_content: str):
		self.response_content = response_content
		self._handler = None
		self.last_prompt = None

	def on(self, handler):
		self._handler = handler
		return lambda: None

	async def send_and_wait(self, prompt, *, timeout=60.0):
		# simulate minimal response structure
		self.last_prompt = prompt

		class DummyData:
			content = self.response_content

		class DummyResp:
			data = DummyData()

		return DummyResp()

	async def disconnect(self):
		return None

	async def get_events(self):
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

	async def create_session(self, **kwargs):
		if self.calls < len(self.analysis_contents):
			content = self.analysis_contents[self.calls]
		else:
			content = self.judge_content
		self.calls += 1
		self.session_configs.append(kwargs)
		session = DummySession(content)
		if kwargs.get("on_event"):
			session.on(kwargs["on_event"])
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
	    cfg,
	    RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert outcome.judge_result.winner_index == 0
	alert_dir = tmp_path / "org" / "repo" / "1"
	assert (alert_dir / "final-report.md").exists()
	assert (alert_dir / "report-0.md").exists()
	winner = Path(outcome.analysis_results[0].workspace)
	assert (winner / "final-report.md").read_text() == analysis_md
	assert not (winner / "report.md").stat().st_mode & 0o222


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
	analysis_md = ("# Secret Validation Report: Alert ID 1\n\n"
	               "## Executive Summary\n\n"
	               "| Item | Value |\n| --- | --- |\n"
	               "| Repository | org/repo |\n| Alert ID | 1 |\n"
	               "| Secret Type | type |\n| Verdict | TRUE_POSITIVE |\n"
	               "| Confidence Score | 5/10 (Medium) |\n"
	               "| Risk Level | Medium |\n| Status | Open |\n"
	               "| Analyst | test |\n| Report Date | 2026-01-28 |\n\n"
	               "> **Key Finding:** test\n")
	judge_json = ('```json\n{"winner_index": 0, "scores": '
	              '[{"report_index": 0, "score": 1}]}\n```')
	client = DummyClient([analysis_md], judge_json)
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)
	outcome = await run_all(
	    cfg,
	    RunParams(org_repo="org/repo", alert_id="1"),
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

	async def dummy_judge(client, config, agent, results, run_params=None,
	                      progress_cb=None, evidence=None):
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
	    cfg,
	    RunParams(org_repo="org/repo", alert_id="1"),
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
	(skill1 / "test-skill-a" / "SKILL.md").write_text(
	    "---\nname: test-skill-a\ndescription: Optional A\n---\nGuide A")
	(skill2 / "test-skill-b").mkdir()
	(skill2 / "test-skill-b" / "SKILL.md").write_text(
	    "---\nname: test-skill-b\ndescription: Optional B\n---\nGuide B")
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
	    cfg,
	    RunParams(org_repo="org/repo", alert_id="1"),
	)

	assert client.session_configs, "Expected at least one session config"
	assert client.session_configs[0]["custom_agents"][0]["name"] == "a"
	assert client.session_configs[0]["available_tools"] == ["tool1"]
	# sessions[1] = challenger, sessions[2] = judge
	for idx in (0, 1, 2):
		session_cfg = client.session_configs[idx]
		# Agent is pre-selected rather than mentioned in the prompt
		assert session_cfg["agent"] == "a"
		assert callable(session_cfg["on_permission_request"])
		assert session_cfg["working_directory"].startswith(str(tmp_path))
		assert not client.sessions[idx].last_prompt.startswith("@a")

	skills = client.session_configs[0]["skill_directories"]
	# Workspace is the working directory, not a skill root
	assert client.session_configs[0]["working_directory"] not in skills
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
			    (tmp_path / f"ws-{i}" / "diagnostics.json").read_text())
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


class TestRunEvalChecks:
	"""Tests for _run_eval_checks."""

	def test_malformed_markdown_does_not_crash(
	    self,
	    monkeypatch,
	):
		"""Malformed markdown that raises during parsing
		is caught gracefully — eval_result stays None.
		"""

		def _boom(md):
			raise ValueError("bad markdown")

		monkeypatch.setattr(
		    "secret_validator_grunt.core.runner"
		    ".Report.from_markdown",
		    _boom,
		)
		res = AgentRunResult(
		    run_id="run-0",
		    raw_markdown="# garbage",
		    report=None,
		)
		results = _run_eval_checks([res])
		assert len(results) == 1
		assert results[0].eval_result is None


async def _run_minimal(tmp_path, monkeypatch, **cfg_overrides):
	"""Run the pipeline once with dummy sessions; return the client."""
	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path),
	             ANALYSIS_COUNT=1, MAX_CONTINUATION_ATTEMPTS=0,
	             **cfg_overrides)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)
	client = DummyClient(["analysis"], "{}")
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)
	await run_all(cfg, RunParams(org_repo="org/repo", alert_id="1"))
	return client


@pytest.mark.asyncio
async def test_run_all_supplies_required_skills(tmp_path, monkeypatch):
	"""Both stages receive required bodies without SDK skill preloading."""
	client = await _run_minimal(tmp_path, monkeypatch)
	analysis_agent = client.session_configs[0]["custom_agents"][0]
	challenger_agent = client.session_configs[1]["custom_agents"][0]
	judge_agent = client.session_configs[2]["custom_agents"][0]
	for agent in (analysis_agent, challenger_agent, judge_agent):
		assert "skills" not in agent
	assert "confidence-methodology" in client.sessions[0].last_prompt
	assert "secret-verification-methodology" in client.sessions[1].last_prompt
	assert "supplied in prompt" in client.sessions[0].last_prompt
	assert 'skill("http-basic-auth")' in client.sessions[0].last_prompt


@pytest.mark.asyncio
async def test_run_all_disabled_skills_are_not_advertised(
        tmp_path, monkeypatch):
	"""Intentional exclusions apply to required content and optional guides."""
	client = await _run_minimal(
	    tmp_path, monkeypatch, DISABLED_SKILLS="code-analysis,http-basic-auth")
	assert "### code-analysis" not in client.sessions[0].last_prompt
	assert 'skill("http-basic-auth")' not in client.sessions[0].last_prompt
	assert "supplied in prompt" in client.sessions[0].last_prompt


@pytest.mark.asyncio
async def test_run_all_reports_unavailable_runtime_skills(
        tmp_path, monkeypatch):
	"""Skills missing from the runtime catalog are surfaced, not fatal."""
	from types import SimpleNamespace

	class CatalogClient(DummyClient):

		async def create_session(self, **kwargs):
			session = await super().create_session(**kwargs)

			async def _list():
				return SimpleNamespace(skills=[
				    SimpleNamespace(name="code-analysis", enabled=True)
				])

			session.rpc = SimpleNamespace(skills=SimpleNamespace(list=_list))
			return session

	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path),
	             ANALYSIS_COUNT=1, MAX_CONTINUATION_ATTEMPTS=0)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	cfg.challenger_agent_file = str(agent_file)
	client = CatalogClient(["analysis"], "{}")
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)
	progress = []
	outcome = await run_all(
	    cfg,
	    RunParams(org_repo="org/repo", alert_id="1"),
	    progress_cb=lambda rid, msg: progress.append(msg),
	)
	su = outcome.analysis_results[0].skill_usage
	assert "http-basic-auth" in su.unavailable_skills
	assert "confidence-methodology" not in su.unavailable_skills
	assert "confidence-methodology" in su.supplied_skills
	assert "code-analysis" not in su.unavailable_skills
	assert any(m.startswith("skills_unavailable:") for m in progress)


@pytest.mark.asyncio
async def test_pipeline_reuses_evidence_and_captures_creation_events(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Three analysts, three challengers, and a custom judge share one fetch."""
	from copilot import ToolInvocation
	from copilot.generated.session_events import (
	    AssistantUsageData,
	    SessionEvent,
	    SessionEventType,
	)
	from secret_validator_grunt.integrations import github_evidence

	calls: list[int] = []
	payloads: list[str] = []

	def fetch(*args: object) -> dict:
		"""Return synthetic alert evidence without network access."""
		calls.append(1)
		return {"secret": "synthetic", "validity": "unknown"}

	class EvidenceClient(DummyClient):
		"""Exercise the real tool handlers registered for every stage."""

		async def create_session(self, **kwargs: Any) -> DummySession:
			"""Simulate a tool request and event before creation returns."""
			session = await super().create_session(**kwargs)
			tool = next(t for t in kwargs["tools"]
			            if t.name == "gh_secret_scanning_alert")
			result = await tool.handler(
			    ToolInvocation(session_id="test", tool_call_id="t",
			                   tool_name=tool.name, arguments={}))
			assert result.result_type == "success"
			payloads.append(result.text_result_for_llm)
			kwargs["on_event"](SessionEvent(
			    id=uuid4(), timestamp=datetime.now(timezone.utc),
			    type=SessionEventType.ASSISTANT_USAGE,
			    data=AssistantUsageData(model="test", input_tokens=17)))
			return session

	agent_file = tmp_path / "agent.md"
	agent_file.write_text("---\nname: a\n---\nTest agent")
	config = Config(OUTPUT_DIR=str(tmp_path / "output"), ANALYSIS_COUNT=3,
	                GITHUB_TOKEN="test", AGENT_FILE=str(agent_file),
	                CHALLENGER_AGENT_FILE=str(agent_file),
	                JUDGE_AGENT_FILE=str(agent_file),
	                MAX_CONTINUATION_ATTEMPTS=0, SHOW_USAGE=True)
	client = EvidenceClient(
	    ["analysis"] * 3,
	    '{"winner_index":-1,"scores":[],"rationale":"test","verdict":""}')
	monkeypatch.setattr(github_evidence, "get_github_client",
	                    lambda token: token)
	monkeypatch.setattr(github_evidence, "get_alert", fetch)
	monkeypatch.setattr("secret_validator_grunt.core.runner.create_client",
	                    lambda cfg: client)
	outcome = await run_all(config, RunParams(org_repo="org/repo",
	                                          alert_id="1"))
	assert len(payloads) == 7
	assert len(set(payloads)) == 1
	assert len(calls) == 1
	assert all(r.usage.input_tokens == 17 for r in outcome.analysis_results)
	assert all(r.usage.input_tokens == 17 for r in outcome.challenge_results)
	assert outcome.judge_result.usage.input_tokens == 17
	assert all(r.skill_usage.supplied_skills for r in outcome.analysis_results)
	client = EvidenceClient(
	    ["analysis"] * 3,
	    '{"winner_index":-1,"scores":[],"rationale":"test","verdict":""}')
	await run_all(config, RunParams(org_repo="org/repo", alert_id="1"))
	assert len(payloads) == 14
	assert len(set(payloads[7:])) == 1
	assert len(calls) == 2


@pytest.mark.asyncio
async def test_relative_output_uses_absolute_workspace_everywhere(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""The pre-cloned repo remains reachable from the new session cwd."""
	monkeypatch.chdir(tmp_path)
	repository = tmp_path / "shared"
	repository.mkdir()
	(repository / "proof.txt").write_text("repository context")

	async def pre_clone(*args: object) -> Path:
		"""Return a local repository fixture."""
		return repository

	agent_file = tmp_path / "agent.md"
	agent_file.write_text("---\nname: a\n---\nTest agent")
	config = Config(OUTPUT_DIR="analysis", ANALYSIS_COUNT=1,
	                AGENT_FILE=str(agent_file),
	                CHALLENGER_AGENT_FILE=str(agent_file),
	                JUDGE_AGENT_FILE=str(agent_file),
	                MAX_CONTINUATION_ATTEMPTS=0)
	client = DummyClient(["analysis"], "{}")
	monkeypatch.setattr("secret_validator_grunt.core.runner.pre_clone_repo",
	                    pre_clone)
	monkeypatch.setattr("secret_validator_grunt.core.runner.create_client",
	                    lambda cfg: client)
	outcome = await run_all(config, RunParams(org_repo="org/repo",
	                                          alert_id="1"))
	workspace = Path(outcome.analysis_results[0].workspace)
	assert workspace.is_absolute()
	assert (workspace / "repo" /
	        "proof.txt").read_text() == "repository context"
	assert client.session_configs[0]["working_directory"] == str(workspace)
	challenge = Path(outcome.challenge_results[0].workspace)
	assert client.session_configs[1]["working_directory"] == str(challenge /
	                                                             "work")
	assert (challenge / "work" / "repo" /
	        "proof.txt").read_text() == "repository context"
	assert str(workspace) in client.sessions[1].last_prompt
	assert str(challenge / "work") in client.sessions[1].last_prompt
	assert "{{workspace_path}}" not in client.sessions[1].last_prompt
	assert "{{challenge_workspace_path}}" not in client.sessions[1].last_prompt
	assert Path(outcome.judge_result.workspace).is_absolute()
