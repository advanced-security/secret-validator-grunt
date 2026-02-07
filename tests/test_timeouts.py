import pytest
import asyncio

from secret_validator_grunt.core.analysis import run_analysis
from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config


class DummySession:

	def __init__(self):
		self.timeout = None

	def on(self, handler):
		# ignore handlers
		return lambda: None

	async def send_and_wait(self, options, timeout=None):
		self.timeout = timeout

		class DummyData:
			content = """# Secret Validation Report: Alert ID 1

## Executive Summary

| Item | Value |
| --- | --- |
| Repository | org/repo |
| Alert ID | 1 |
| Secret Type | type |
| Verdict | INCONCLUSIVE |
| Confidence Score | 5/10 (Medium) |
| Risk Level | Medium |
| Status | Open |
| Analyst | test |
| Report Date | 2026-01-28 |

> **Key Finding:** test
"""

		class DummyEvent:
			data = DummyData()

		return DummyEvent()

	async def destroy(self):
		return None

	async def get_messages(self):
		return []


class DummyClient:

	def __init__(self):
		self.session = DummySession()

	async def create_session(self, *args, **kwargs):
		return self.session


@pytest.mark.asyncio
async def test_run_analysis_uses_config_timeout():
	cfg = Config(COPILOT_CLI_URL="http://x", ANALYSIS_TIMEOUT_SECONDS=123)
	agent = AgentConfig(name="a", prompt="p")
	client = DummyClient()

	res = await run_analysis("0", client, cfg, agent, org_repo="org/repo",
	                         alert_id="1")
	assert client.session.timeout == 123
	assert res is not None
	assert res.raw_markdown is not None
