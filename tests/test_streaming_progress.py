import pytest
import asyncio

from secret_validator_grunt.core.analysis import run_analysis
from secret_validator_grunt.models.agent_config import AgentConfig
from secret_validator_grunt.models.config import Config
from copilot.generated.session_events import SessionEventType


class DummyEvent:

	def __init__(self, type_, data=None):
		self.type = type_
		self.data = data or type('D', (), {})


class DummySession:

	def __init__(self):
		self._handler = None
		self.aborted = False
		self.destroyed = False

	def on(self, handler):
		self._handler = handler
		return lambda: None

	async def send_and_wait(self, options, timeout=None):
		# simulate streaming
		if self._handler:
			self._handler(
			    DummyEvent(
			        SessionEventType.TOOL_EXECUTION_START,
			        type('D', (), {'tool_name': 'bash'}),
			    ))
			self._handler(
			    DummyEvent(
			        SessionEventType.ASSISTANT_MESSAGE_DELTA,
			        type('D', (), {'delta_content': 'hello '}),
			    ))
			self._handler(
			    DummyEvent(
			        SessionEventType.TOOL_EXECUTION_COMPLETE,
			        type('D', (), {'tool_name': 'bash'}),
			    ))
			self._handler(
			    DummyEvent(
			        SessionEventType.ASSISTANT_MESSAGE_DELTA,
			        type('D', (), {'delta_content': 'world'}),
			    ))
			self._handler(
			    DummyEvent(
			        SessionEventType.ASSISTANT_MESSAGE,
			        type('D', (), {'content': 'hello world'}),
			    ))

		class DummyData:
			content = "hello world"

		class DummyResp:
			data = DummyData()

		return DummyResp()

	async def abort(self):
		self.aborted = True

	async def destroy(self):
		self.destroyed = True

	async def get_messages(self):
		return []


class DummyClient:

	def __init__(self, session=None):
		self.session = session or DummySession()

	async def create_session(self, *args, **kwargs):
		return self.session


@pytest.mark.asyncio
async def test_streaming_progress_default_concise():
	cfg = Config(COPILOT_CLI_URL="http://x")
	agent = AgentConfig(name="a", prompt="p")
	client = DummyClient()
	seen = []

	def progress_cb(run_id, msg):
		seen.append((run_id, msg))

	res = await run_analysis(
	    "0",
	    client,
	    cfg,
	    agent,
	    org_repo="org/repo",
	    alert_id="1",
	    progress_cb=progress_cb,
	)
	assert not any('delta' in m for _, m in seen)
	assert any('assistant' in m for _, m in seen)
	assert res.raw_markdown == "hello world"


@pytest.mark.asyncio
async def test_streaming_progress_verbose():
	cfg = Config(COPILOT_CLI_URL="http://x", STREAM_VERBOSE=True)
	agent = AgentConfig(name="a", prompt="p")
	client = DummyClient()
	seen = []

	def progress_cb(run_id, msg):
		seen.append((run_id, msg))

	res = await run_analysis(
	    "0",
	    client,
	    cfg,
	    agent,
	    org_repo="org/repo",
	    alert_id="1",
	    progress_cb=progress_cb,
	)
	assert any('delta' in m for _, m in seen)
	assert any('assistant' in m for _, m in seen)
	assert res.raw_markdown == "hello world"


@pytest.mark.asyncio
async def test_streaming_usage_accumulates(tmp_path):
	from secret_validator_grunt.ui.streaming import StreamCollector
	from copilot.generated.session_events import QuotaSnapshot
	msgs = []
	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    progress_cb=lambda rid, msg: msgs.append(msg),
	    show_usage=True,
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	collector.handler(
	    ev(SessionEventType.ASSISTANT_USAGE, input_tokens=10, output_tokens=5,
	       cost=0.1))
	assert collector.usage.input_tokens == 10
	assert collector.usage.output_tokens == 5
	assert collector.usage.cost == 0.1
	assert msgs == []

	q1 = QuotaSnapshot(
	    entitlement_requests=100,
	    is_unlimited_entitlement=False,
	    overage=0,
	    overage_allowed_with_exhausted_quota=False,
	    remaining_percentage=100,
	    usage_allowed_with_exhausted_quota=True,
	    used_requests=10,
	)
	collector.handler(
	    ev(SessionEventType.SESSION_USAGE_INFO, current_tokens=200,
	       token_limit=1000, quota_snapshots={"premier": q1}))

	q2 = QuotaSnapshot(
	    entitlement_requests=100,
	    is_unlimited_entitlement=False,
	    overage=0,
	    overage_allowed_with_exhausted_quota=False,
	    remaining_percentage=90,
	    usage_allowed_with_exhausted_quota=True,
	    used_requests=12,
	)
	collector.handler(
	    ev(SessionEventType.SESSION_USAGE_INFO, current_tokens=300,
	       token_limit=1000, quota_snapshots={"premier": q2}))

	reqs = collector.usage.requests_consumed()
	assert reqs.get("premier") == 2
	assert collector.usage.current_tokens == 300
	assert collector.usage.token_limit == 1000


@pytest.mark.asyncio
async def test_skill_tracking_basic(tmp_path):
	"""StreamCollector should track skill load events."""
	from secret_validator_grunt.ui.streaming import StreamCollector
	from secret_validator_grunt.models.skill import SkillManifest, SkillInfo
	from secret_validator_grunt.models.skill_usage import SkillLoadStatus

	# Create a manifest with some skills
	manifest = SkillManifest(
	    skills=[
	        SkillInfo(name="skill-a", description="A",
	                  path="/a", phase="1-init", required=True),
	        SkillInfo(name="skill-b", description="B",
	                  path="/b", phase="2-gather", required=False),
	    ],
	    phases=["1-init", "2-gather"],
	)

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    skill_manifest=manifest,
	    disabled_skills=["disabled-skill"],
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Simulate skill tool execution start (has tool_call_id, tool_name, arguments)
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="call-001",
	       tool_name="skill",
	       arguments={"skill": "skill-a"}))

	# Simulate skill tool execution complete (only has tool_call_id, success, error - NO tool_name/arguments)
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="call-001",
	       success=True,
	       error=None))

	# Verify skill was tracked
	stats = collector.skill_usage
	assert "skill-a" in stats.loaded_skills
	assert len(stats.load_events) == 1
	assert stats.load_events[0].skill_name == "skill-a"
	assert stats.load_events[0].status == SkillLoadStatus.LOADED
	assert stats.load_events[0].phase == "1-init"
	assert stats.load_events[0].is_required is True


@pytest.mark.asyncio
async def test_skill_tracking_failed_load(tmp_path):
	"""StreamCollector should track failed skill loads."""
	from secret_validator_grunt.ui.streaming import StreamCollector
	from secret_validator_grunt.models.skill_usage import SkillLoadStatus

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Simulate failed skill load (not 'not found', but a generic failure)
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="call-002",
	       tool_name="skill",
	       arguments={"skill": "broken-skill"}))

	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="call-002",
	       success=False,
	       error="Connection timeout"))

	stats = collector.skill_usage
	assert "broken-skill" not in stats.loaded_skills
	assert "broken-skill" in stats.failed_skills
	assert stats.load_events[0].status == SkillLoadStatus.FAILED
	assert stats.load_events[0].error_message == "Connection timeout"


@pytest.mark.asyncio
async def test_skill_tracking_not_found(tmp_path):
	"""StreamCollector should track skills that are not found."""
	from secret_validator_grunt.ui.streaming import StreamCollector
	from secret_validator_grunt.models.skill_usage import SkillLoadStatus

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Simulate skill not found
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="call-003",
	       tool_name="skill",
	       arguments={"skill": "nonexistent"}))

	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="call-003",
	       success=False,
	       error="Skill not found"))

	stats = collector.skill_usage
	assert "nonexistent" not in stats.loaded_skills
	# NOT_FOUND is also tracked as failed
	assert "nonexistent" in stats.failed_skills
	assert stats.load_events[0].status == SkillLoadStatus.NOT_FOUND
	assert stats.load_events[0].error_message == "Skill not found"


@pytest.mark.asyncio
async def test_skill_tracking_finalize(tmp_path):
	"""StreamCollector.finalize_skill_usage should compute skipped required."""
	from secret_validator_grunt.ui.streaming import StreamCollector
	from secret_validator_grunt.models.skill import SkillManifest, SkillInfo

	manifest = SkillManifest(
	    skills=[
	        SkillInfo(name="required-a", description="A",
	                  path="/a", required=True),
	        SkillInfo(name="required-b", description="B",
	                  path="/b", required=True),
	    ],
	    phases=[],
	)

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    skill_manifest=manifest,
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Only load one of two required skills
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="call-004",
	       tool_name="skill",
	       arguments={"skill": "required-a"}))
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="call-004",
	       success=True))

	stats = collector.finalize_skill_usage()
	assert "required-a" in stats.loaded_skills
	assert "required-b" in stats.skipped_required
	assert stats.compliance_score == 50.0


@pytest.mark.asyncio
async def test_skill_tracking_duration(tmp_path):
	"""StreamCollector should track skill load duration."""
	import time
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Start event
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="call-005",
	       tool_name="skill",
	       arguments={"skill": "test-skill"}))

	# Small delay to ensure measurable duration
	time.sleep(0.01)

	# Complete event
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="call-005",
	       success=True))

	stats = collector.skill_usage
	assert len(stats.load_events) == 1
	assert stats.load_events[0].duration_ms is not None
	assert stats.load_events[0].duration_ms >= 10  # At least 10ms


@pytest.mark.asyncio
async def test_tool_tracking_disabled_by_default(tmp_path):
	"""Tool tracking is None when show_usage is False."""
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    show_usage=False,
	)
	assert collector.tool_usage is None


@pytest.mark.asyncio
async def test_tool_tracking_enabled_with_show_usage(tmp_path):
	"""Tool tracking is active when show_usage is True."""
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    show_usage=True,
	)
	assert collector.tool_usage is not None
	assert collector.tool_usage.total_calls == 0


@pytest.mark.asyncio
async def test_tool_tracking_records_all_tools(tmp_path):
	"""Tool tracking captures all tool call start/complete pairs."""
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    show_usage=True,
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	# Simulate bash tool call
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="c1",
	       tool_name="bash"))
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="c1",
	       tool_name="bash",
	       success=True,
	       error=None))

	# Simulate view tool call
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="c2",
	       tool_name="view"))
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="c2",
	       tool_name="view",
	       success=True,
	       error=None))

	stats = collector.tool_usage
	assert stats.total_calls == 2
	assert stats.successful_calls == 2
	assert stats.success_rate == 100.0

	by_tool = stats.calls_by_tool()
	assert "bash" in by_tool
	assert "view" in by_tool


@pytest.mark.asyncio
async def test_tool_tracking_records_failures(tmp_path):
	"""Tool tracking captures failed tool calls."""
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    show_usage=True,
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="c1",
	       tool_name="bash"))
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="c1",
	       tool_name="bash",
	       success=False,
	       error="Command failed"))

	stats = collector.tool_usage
	assert stats.total_calls == 1
	assert stats.failed_calls == 1
	assert stats.success_rate == 0.0
	assert stats.tool_calls[0].error_message == "Command failed"


@pytest.mark.asyncio
async def test_tool_tracking_not_recorded_without_show_usage(tmp_path):
	"""Tool calls are not tracked when show_usage is False."""
	from secret_validator_grunt.ui.streaming import StreamCollector

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    show_usage=False,
	)

	def ev(et, **kwargs):
		return type("E", (), {
		    "type": et,
		    "data": type("D", (), kwargs),
		})

	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_START,
	       tool_call_id="c1",
	       tool_name="bash"))
	collector.handler(
	    ev(SessionEventType.TOOL_EXECUTION_COMPLETE,
	       tool_call_id="c1",
	       tool_name="bash",
	       success=True,
	       error=None))

	assert collector.tool_usage is None


@pytest.mark.asyncio
async def test_tool_tracking_phase_map_populated(tmp_path):
	"""Skill usage phase_map is populated from manifest."""
	from secret_validator_grunt.ui.streaming import StreamCollector
	from secret_validator_grunt.models.skill import SkillManifest, SkillInfo

	manifest = SkillManifest(
	    skills=[
	        SkillInfo(name="skill-a", description="A",
	                  path="/a", phase="1-init", required=True),
	        SkillInfo(name="skill-b", description="B",
	                  path="/b", phase="2-gather", required=False),
	    ],
	    phases=["1-init", "2-gather"],
	)

	collector = StreamCollector(
	    run_id="1",
	    stream_log_path=tmp_path / "s.log",
	    skill_manifest=manifest,
	)

	stats = collector.skill_usage
	assert stats.phase_map == {
	    "skill-a": "1-init",
	    "skill-b": "2-gather",
	}
	assert stats.available_by_phase() == {
	    "1-init": ["skill-a"],
	    "2-gather": ["skill-b"],
	}


@pytest.mark.asyncio
async def test_diagnostics_json_written_with_show_usage():
	"""run_analysis writes diagnostics.json when show_usage is True."""
	import json

	cfg = Config(COPILOT_CLI_URL="http://x", SHOW_USAGE=True)
	agent = AgentConfig(name="a", prompt="p")
	client = DummyClient()

	res = await run_analysis(
	    "0",
	    client,
	    cfg,
	    agent,
	    org_repo="org/repo",
	    alert_id="1",
	)

	assert res.workspace is not None
	diag_path = __import__("pathlib").Path(res.workspace) / "diagnostics.json"
	assert diag_path.exists(), "diagnostics.json should be written"

	data = json.loads(diag_path.read_text())
	assert data["run_id"] == "0"
	assert "skill_usage" in data
	assert "tool_usage" in data
	assert "usage" in data


@pytest.mark.asyncio
async def test_diagnostics_json_not_written_without_show_usage():
	"""run_analysis does NOT write diagnostics.json when show_usage is False."""
	cfg = Config(COPILOT_CLI_URL="http://x", SHOW_USAGE=False)
	agent = AgentConfig(name="a", prompt="p")
	client = DummyClient()

	res = await run_analysis(
	    "0",
	    client,
	    cfg,
	    agent,
	    org_repo="org/repo",
	    alert_id="1",
	)

	assert res.workspace is not None
	diag_path = __import__("pathlib").Path(res.workspace) / "diagnostics.json"
	assert not diag_path.exists(), "diagnostics.json should NOT be written"
