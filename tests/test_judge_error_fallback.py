import pytest
import asyncio

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

	async def send_and_wait(self, options, timeout=None):
		raise Exception("Execution failed: missing finish_reason for choice 0")

	async def abort(self):
		return None

	async def destroy(self):
		return None

	async def get_messages(self):
		return []


class DummyClient:

	def __init__(self, session=None):
		self.session = session or DummySession()

	async def create_session(self, *args, **kwargs):
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
	    client, cfg, agent, results,
	    run_params=RunParams(org_repo="org/repo", alert_id="1"),
	)
	assert jr.winner_index == -1
	assert "ERROR" in (jr.raw_response or "")
