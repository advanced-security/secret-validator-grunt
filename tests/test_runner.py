import pytest

from secret_validator_grunt.core.runner import run_all
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.judge_result import JudgeResult, JudgeScore


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
	cfg = Config(
	    COPILOT_CLI_URL="http://x",
	    OUTPUT_DIR=str(tmp_path),
	    ANALYSIS_COUNT=1,
	    MAX_CONTINUATION_ATTEMPTS=0,
	)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)
	analysis_md = """# Secret Validation Report: Alert ID 1\n\n## Executive Summary\n\n| Item | Value |\n| --- | --- |\n| Repository | org/repo |\n| Alert ID | 1 |\n| Secret Type | type |\n| Verdict | OK |\n| Confidence Score | 5/10 (Medium) |\n| Risk Level | Medium |\n| Status | Open |\n| Analyst | test |\n| Report Date | 2026-01-28 |\n\n> **Key Finding:** test\n"""
	judge_json = """Now I'll judge.Now I'll judge.```json\n{\n  \"winner_index\": 0,\n  \"scores\": [{\n    \"report_index\": 0,\n    \"score\": 1\n  }]\n}\n```"""
	client = DummyClient([analysis_md], judge_json)
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)

	outcome = await run_all(cfg, org_repo="org/repo", alert_id="1")
	assert outcome.judge_result.winner_index == 0
	alert_dir = tmp_path / "org" / "repo" / "1"
	assert (alert_dir / "final-report.md").exists()
	assert (alert_dir / "report-0.md").exists()


@pytest.mark.asyncio
async def test_run_all_handles_analysis_exception(tmp_path, monkeypatch):
	cfg = Config(
	    COPILOT_CLI_URL="http://x",
	    OUTPUT_DIR=str(tmp_path),
	    ANALYSIS_COUNT=1,
	    MAX_CONTINUATION_ATTEMPTS=0,
	)
	agent_file = tmp_path / "agent.md"
	agent_file.write_text("""---\nname: a\n---\nprompt""", encoding="utf-8")
	cfg.agent_file = str(agent_file)
	cfg.judge_agent_file = str(agent_file)

	async def boom(*args, **kwargs):
		raise RuntimeError("boom")

	async def dummy_judge(client, config, agent, results, org_repo=None,
	                      alert_id=None, run_params=None, progress_cb=None):
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

	outcome = await run_all(cfg, org_repo="org/repo", alert_id="1")
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

	client = DummyClient(["analysis"], "{}")
	monkeypatch.setattr(
	    "secret_validator_grunt.core.runner.create_client",
	    lambda cfg: client,
	)

	await run_all(cfg, org_repo="org/repo", alert_id="1")

	assert client.session_configs, "Expected at least one session config"
	assert client.session_configs[0]["custom_agents"][0]["name"] == "a"
	assert client.session_configs[0]["available_tools"] == ["tool1"]
	assert client.sessions[0].last_prompt is not None
	assert client.sessions[0].last_prompt.startswith("@a")
	assert client.sessions[1].last_prompt.startswith("@a")

	skills = client.session_configs[0]["skill_directories"]
	assert skills[0].startswith(str(tmp_path))
	assert skills[-2:] == [str(skill1), str(skill2)]
	# Config disabled_skills + hidden skills (underscore-prefixed) are combined
	assert "skill2" in client.session_configs[0]["disabled_skills"]
	assert "skill2" in client.session_configs[1]["disabled_skills"]

	# judge session config should include system_message and no streaming
	judge_cfg = client.session_configs[1]
	assert judge_cfg["streaming"] is False
	assert "system_message" in judge_cfg
