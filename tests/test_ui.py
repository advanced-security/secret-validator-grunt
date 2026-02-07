import pytest

from secret_validator_grunt.ui.tui import TUI, RunDisplayState
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.skill_usage import SkillUsageStats
from secret_validator_grunt.models.tool_usage import ToolUsageStats


def test_tui_workspace_dedup_and_pinned_context():
	ui = TUI(analysis_count=1, org_repo="org/repo", alert_id="1")
	ui.update("0", "workspace: /tmp/ws1")
	ui.update("0", "workspace: /tmp/ws1")  # duplicate
	ui.update("0", "assistant: hello")
	state = ui.states["0"]
	assert state.workspace == "/tmp/ws1"
	assert all(not msg.startswith("workspace:") for msg in state.messages)
	text = state.render_cell(org_repo=ui.org_repo, alert_id=ui.alert_id)
	plain = text.plain
	assert "repo: org/repo" in plain
	assert "alert: 1" in plain
	assert "ws: /tmp/ws1" in plain


def test_tui_message_limit():
	ui = TUI(analysis_count=1)
	for i in range(15):
		ui.update("0", f"assistant: message {i}")
	state = ui.states["0"]
	assert len(state.messages) <= 8  # deque maxlen
	text = state.render_cell()
	bullet_lines = [
	    ln for ln in text.plain.splitlines() if ln.startswith("• ")
	]
	assert len(bullet_lines) == 8  # rendered limit


def test_tui_judge_cell_includes_context():
	ui = TUI(analysis_count=1, org_repo="org/repo", alert_id="1")
	ui.update("judge", "assistant: hi")
	text = ui.states["judge"].render_cell(org_repo="org/repo", alert_id="1")
	plain = text.plain
	assert "repo: org/repo" in plain
	assert "alert: 1" in plain
	assert "assistant: hi" in plain


def test_tui_render_skill_usage_table():
	"""TUI should render skill usage table with compliance info."""
	ui = TUI(analysis_count=2)

	results = [
	    AgentRunResult(
	        run_id="0",
	        progress_log=[],
	        skill_usage=SkillUsageStats(
	            available_skills=["a", "b", "c"],
	            required_skills=["a", "b"],
	            loaded_skills=["a", "b"],  # 100% compliance
	        ),
	    ),
	    AgentRunResult(
	        run_id="1",
	        progress_log=[],
	        skill_usage=SkillUsageStats(
	            available_skills=["a", "b", "c"],
	            required_skills=["a", "b"],
	            loaded_skills=["a"],  # 50% compliance
	        ),
	    ),
	]

	table = ui._render_skill_usage_table(results)

	# The table should have the correct structure
	assert len(table.columns) == 5  # Run, Skills Loaded, By Phase, Required, Compliance


def test_tui_render_skill_usage_table_no_data():
	"""TUI skill usage table should handle missing skill_usage gracefully."""
	ui = TUI(analysis_count=1)

	results = [
	    AgentRunResult(
	        run_id="0",
	        progress_log=[],
	        skill_usage=None,  # No skill tracking
	    ),
	]

	table = ui._render_skill_usage_table(results)
	assert len(table.columns) == 5


def test_tui_render_skill_usage_with_phases():
	"""TUI skill table should show phase breakdown."""
	from secret_validator_grunt.models.skill_usage import SkillLoadStatus

	ui = TUI(analysis_count=1)

	stats = SkillUsageStats(
	    available_skills=["a", "b", "c"],
	    required_skills=["a"],
	    loaded_skills=["a", "b"],
	    phase_map={"a": "1-init", "b": "1-init", "c": "2-ctx"},
	)
	stats.add_load_event("a", SkillLoadStatus.LOADED, phase="1-init")
	stats.add_load_event("b", SkillLoadStatus.LOADED, phase="1-init")

	results = [
	    AgentRunResult(run_id="0", progress_log=[], skill_usage=stats),
	]

	table = ui._render_skill_usage_table(results)
	assert len(table.columns) == 5


def test_tui_render_tool_usage_table():
	"""TUI should render tool usage table with stats."""
	ui = TUI(analysis_count=1)

	stats = ToolUsageStats()
	stats.add_start("c1", "bash")
	stats.add_complete("c1", success=True)
	stats.add_start("c2", "bash")
	stats.add_complete("c2", success=True)
	stats.add_start("c3", "view")
	stats.add_complete("c3", success=False, error="timeout")

	results = [
	    AgentRunResult(
	        run_id="0",
	        progress_log=[],
	        tool_usage=stats,
	    ),
	]

	table = ui._render_tool_usage_table(results)
	assert len(table.columns) == 6  # Run, Total, Success, Failed, Rate, Top Tools


def test_tui_render_tool_usage_table_no_data():
	"""TUI tool usage table handles missing tool_usage."""
	ui = TUI(analysis_count=1)

	results = [
	    AgentRunResult(run_id="0", progress_log=[], tool_usage=None),
	]

	table = ui._render_tool_usage_table(results)
	assert len(table.columns) == 6


def test_tui_skill_table_gated_by_show_usage():
	"""Skill and tool tables only print when show_usage is True."""
	from io import StringIO
	from rich.console import Console

	# With show_usage=False, no tables should appear
	buf = StringIO()
	console = Console(file=buf, force_terminal=True, width=120)
	ui = TUI(analysis_count=1, show_usage=False, console=console)

	results = [
	    AgentRunResult(
	        run_id="0",
	        progress_log=[],
	        skill_usage=SkillUsageStats(
	            available_skills=["a"],
	            loaded_skills=["a"],
	        ),
	        tool_usage=ToolUsageStats(),
	    ),
	]

	ui.print_summary(
	    winner_index=0,
	    analysis_results=results,
	    output_dir=__import__('pathlib').Path('/tmp'),
	    judge_result=None,
	)
	output = buf.getvalue()
	assert "Skill Usage" not in output
	assert "Tool Usage" not in output
