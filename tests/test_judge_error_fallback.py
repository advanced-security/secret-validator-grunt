import pytest

from secret_validator_grunt.core.judge import run_judge
from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.run_params import RunParams


class DummySession:

	def __init__(self):
		self._handler = None

	def on(self, handler):
		self._handler = handler
		return lambda: None

	async def send_and_wait(self, prompt, *, timeout=60.0):
		raise Exception("Execution failed: missing finish_reason for choice 0")

	async def abort(self):
		return None

	async def disconnect(self):
		return None

	async def get_events(self):
		return []


class DummyClient:

	def __init__(self, session=None):
		self.session = session or DummySession()

	async def create_session(self, **kwargs):
		return self.session


@pytest.mark.asyncio
async def test_judge_fallback_on_error():
	cfg = Config(COPILOT_CLI_URL="http://x")
	agent = AgentConfig(name="j", prompt="p")
	client = DummyClient()
	results = [
	    AgentRunResult(run_id="0", raw_markdown="report0"),
	    AgentRunResult(run_id="1", raw_markdown="report1"),
	]
	jr = await run_judge(
	    client,
	    cfg,
	    agent,
	    results,
	    run_params=RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert jr.winner_index == -1
	assert "ERROR" in (jr.raw_response or "")


class RecordingClient(DummyClient):
	"""Client that records create_session kwargs."""

	def __init__(self):
		super().__init__()
		self.kwargs = None

	async def create_session(self, **kwargs):
		self.kwargs = kwargs
		return self.session


@pytest.mark.asyncio
async def test_judge_with_empty_tools_is_tool_free(tmp_path):
	"""tools: [] registers no SDK tools, skills, or session tools."""
	cfg = Config(COPILOT_CLI_URL="http://x", OUTPUT_DIR=str(tmp_path))
	agent = AgentConfig(name="j", prompt="p", tools=[])
	client = RecordingClient()
	await run_judge(
	    client,
	    cfg,
	    agent,
	    [AgentRunResult(run_id="0", raw_markdown="r")],
	    run_params=RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert client.kwargs["available_tools"] == []
	assert client.kwargs["tools"] == []
	assert client.kwargs["skill_directories"] == []


@pytest.mark.asyncio
async def test_judge_does_not_load_analysis_skills(tmp_path):
	"""Judge never registers analysis skill directories."""
	extra = tmp_path / "extra-skills"
	extra.mkdir()
	cfg = Config(
	    COPILOT_CLI_URL="http://x",
	    OUTPUT_DIR=str(tmp_path),
	    SKILL_DIRECTORIES=str(extra),
	)
	agent = AgentConfig(name="j", prompt="p", tools=["view"])
	client = RecordingClient()
	await run_judge(
	    client,
	    cfg,
	    agent,
	    [AgentRunResult(run_id="0", raw_markdown="r")],
	    run_params=RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert client.kwargs["available_tools"] == ["view"]
	assert len(client.kwargs["tools"]) == 4
	assert str(extra) not in client.kwargs["skill_directories"]
	assert not any("/skills/analysis" in d
	               for d in client.kwargs["skill_directories"])
