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
	assert len(table.columns
	           ) == 5  # Run, Skills Loaded, By Phase, Required, Compliance


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
	    phase_map={
	        "a": "1-init",
	        "b": "1-init",
	        "c": "2-ctx"
	    },
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
	assert len(
	    table.columns) == 6  # Run, Total, Success, Failed, Rate, Top Tools


def test_tui_render_tool_usage_table_no_data():
	"""TUI tool usage table handles missing tool_usage."""
	ui = TUI(analysis_count=1)

	results = [
	    AgentRunResult(run_id="0", progress_log=[], tool_usage=None),
	]

	table = ui._render_tool_usage_table(results)
	assert len(table.columns) == 6


def test_tui_usage_table_includes_challenger_rows():
	"""Usage table includes challenger rows when present."""
	from secret_validator_grunt.models.usage import UsageStats
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=2)
	cr = ChallengeResult(
		verdict="CONFIRMED",
		usage=UsageStats(
			input_tokens=1000,
			output_tokens=200,
			cost=5,
			duration=10.0,
		),
	)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			usage=UsageStats(
				input_tokens=5000,
				output_tokens=500,
				cost=10,
				duration=30.0,
			),
			challenge_result=cr,
		),
	]
	table = ui._render_usage_table(results, None)
	# Should have: run 0, challenge 0, total = 3 rows
	assert table.row_count == 3
	# First row is the analysis, second is challenger
	row_labels = [
		str(table.columns[0]._cells[i])
		for i in range(table.row_count)
	]
	assert "run 0" in row_labels
	assert "challenge 0" in row_labels
	assert "total" in row_labels


def test_tui_usage_table_no_challenger_when_absent():
	"""Usage table has no challenger rows when no challenge."""
	from secret_validator_grunt.models.usage import UsageStats

	ui = TUI(analysis_count=1)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			usage=UsageStats(
				input_tokens=100,
				output_tokens=10,
				cost=1,
				duration=5.0,
			),
		),
	]
	table = ui._render_usage_table(results, None)
	# Only run 0 + total = 2 rows
	assert table.row_count == 2
	row_labels = [
		str(table.columns[0]._cells[i])
		for i in range(table.row_count)
	]
	assert "challenge 0" not in row_labels


def test_tui_usage_table_challenger_in_totals():
	"""Challenger usage is included in the total row."""
	from secret_validator_grunt.models.usage import UsageStats
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=1)
	cr = ChallengeResult(
		verdict="CONFIRMED",
		usage=UsageStats(
			input_tokens=1000,
			output_tokens=200,
		),
	)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			usage=UsageStats(
				input_tokens=2000,
				output_tokens=400,
			),
			challenge_result=cr,
		),
	]
	table = ui._render_usage_table(results, None)
	# Total row should sum analysis + challenger
	total_in = str(table.columns[1]._cells[-1])
	assert total_in == "3000"


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


# =============================================================================
# Challenger TUI Table Tests
# =============================================================================


class TestTUIChallengerTable:
	"""Tests for the challenger table in the TUI pipeline display."""

	def test_challenger_states_created(self):
		"""TUI creates challenge-{i} states for each analysis."""
		ui = TUI(analysis_count=3)
		assert "challenge-0" in ui.states
		assert "challenge-1" in ui.states
		assert "challenge-2" in ui.states
		# All start as pending
		for i in range(3):
			assert ui.states[f"challenge-{i}"].status == "pending"

	def test_challenger_states_count_matches_analysis(self):
		"""Number of challenger states matches analysis_count."""
		for count in [1, 2, 5]:
			ui = TUI(analysis_count=count)
			challenger_states = [
			    k for k in ui.states if k.startswith("challenge-")
			]
			assert len(challenger_states) == count

	def test_challenger_update_challenge_started(self):
		"""TUI.update handles challenge_started message."""
		ui = TUI(analysis_count=2)
		ui.update("challenge-0", "challenge_started")
		assert ui.states["challenge-0"].status == "running"
		# Other challenger still pending
		assert ui.states["challenge-1"].status == "pending"

	def test_challenger_update_challenge_completed(self):
		"""TUI.update handles challenge_completed message."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "challenge_started")
		ui.update("challenge-0", "challenge_completed")
		assert ui.states["challenge-0"].status == "completed"

	def test_challenger_update_verdict(self):
		"""TUI.update handles verdict= message on challenger state."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "verdict=CONFIRMED")
		state = ui.states["challenge-0"]
		assert state.status == "completed"
		assert state.challenge_verdict == "CONFIRMED"

	def test_challenger_update_verdict_refuted(self):
		"""TUI.update parses REFUTED verdict correctly."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "verdict=REFUTED")
		state = ui.states["challenge-0"]
		assert state.challenge_verdict == "REFUTED"

	def test_challenger_update_verdict_insufficient(self):
		"""TUI.update parses INSUFFICIENT_EVIDENCE verdict."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "verdict=INSUFFICIENT_EVIDENCE")
		state = ui.states["challenge-0"]
		assert state.challenge_verdict == "INSUFFICIENT_EVIDENCE"

	def test_challenger_messages_accumulate(self):
		"""Challenger states accumulate messages like other states."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "challenge_started")
		ui.update("challenge-0", "assistant: examining report")
		ui.update("challenge-0", "assistant: checking workspace")
		state = ui.states["challenge-0"]
		assert len(state.messages) == 3

	def test_build_table_includes_challenger(self):
		"""_build_table includes challenger table in output."""
		ui = TUI(analysis_count=2, org_repo="org/repo", alert_id="1")
		group = ui._build_table()
		# Group should contain 3 renderables: analysis, challenger, judge
		assert len(group.renderables) == 3

	def test_build_table_challenger_columns(self):
		"""Challenger table has correct number of columns."""
		ui = TUI(analysis_count=3, org_repo="org/repo", alert_id="1")
		group = ui._build_table()
		challenger_table = group.renderables[1]  # Second table
		assert len(challenger_table.columns) == 3
		assert challenger_table.columns[0].header == "Challenger 0"
		assert challenger_table.columns[1].header == "Challenger 1"
		assert challenger_table.columns[2].header == "Challenger 2"

	def test_update_outcome_on_challenger_state(self):
		"""update_outcome works for challenger states."""
		ui = TUI(analysis_count=1)
		ui.update_outcome(
		    "challenge-0",
		    verdict="CONFIRMED",
		    key_finding="Verdict holds under scrutiny",
		)
		state = ui.states["challenge-0"]
		assert state.verdict == "CONFIRMED"
		assert state.key_finding == "Verdict holds under scrutiny"

	def test_challenger_workspace_capture(self):
		"""Challenger state captures workspace from workspace: message."""
		ui = TUI(analysis_count=1)
		ui.update("challenge-0", "workspace: /tmp/challenge-ws")
		state = ui.states["challenge-0"]
		assert state.workspace == "/tmp/challenge-ws"


def test_tui_skill_usage_table_includes_challenger_rows():
	"""Skill usage table includes challenger rows when present."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=1)
	cr = ChallengeResult(
		verdict="CONFIRMED",
		skill_usage=SkillUsageStats(
			available_skills=["x", "y"],
			required_skills=["x"],
			loaded_skills=["x", "y"],
		),
	)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			skill_usage=SkillUsageStats(
				available_skills=["a", "b"],
				required_skills=["a"],
				loaded_skills=["a"],
			),
			challenge_result=cr,
		),
	]
	table = ui._render_skill_usage_table(results)
	# Should have: run 0 + challenge 0 = 2 rows
	assert table.row_count == 2
	row_labels = [
		str(table.columns[0]._cells[i])
		for i in range(table.row_count)
	]
	assert "run 0" in row_labels
	assert "challenge 0" in row_labels


def test_tui_skill_usage_table_no_challenger_when_absent():
	"""Skill usage table has no challenger rows without challenge."""
	ui = TUI(analysis_count=1)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			skill_usage=SkillUsageStats(
				available_skills=["a"],
				required_skills=["a"],
				loaded_skills=["a"],
			),
		),
	]
	table = ui._render_skill_usage_table(results)
	assert table.row_count == 1
	row_labels = [
		str(table.columns[0]._cells[i])
		for i in range(table.row_count)
	]
	assert "challenge 0" not in row_labels


def test_tui_skill_usage_table_challenger_no_skill_usage():
	"""Challenger with no skill_usage doesn't add a row."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=1)
	cr = ChallengeResult(verdict="CONFIRMED", skill_usage=None)
	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			skill_usage=SkillUsageStats(
				available_skills=["a"],
				required_skills=["a"],
				loaded_skills=["a"],
			),
			challenge_result=cr,
		),
	]
	table = ui._render_skill_usage_table(results)
	assert table.row_count == 1


def test_tui_tool_usage_table_includes_challenger_rows():
	"""Tool usage table includes challenger rows when present."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=1)
	challenger_tools = ToolUsageStats()
	challenger_tools.add_start("c1", "bash")
	challenger_tools.add_complete("c1", success=True)

	cr = ChallengeResult(
		verdict="CONFIRMED",
		tool_usage=challenger_tools,
	)

	analysis_tools = ToolUsageStats()
	analysis_tools.add_start("c2", "bash")
	analysis_tools.add_complete("c2", success=True)

	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			tool_usage=analysis_tools,
			challenge_result=cr,
		),
	]
	table = ui._render_tool_usage_table(results)
	# Should have: run 0 + challenge 0 = 2 rows
	assert table.row_count == 2
	row_labels = [
		str(table.columns[0]._cells[i])
		for i in range(table.row_count)
	]
	assert "run 0" in row_labels
	assert "challenge 0" in row_labels


def test_tui_tool_usage_table_no_challenger_when_absent():
	"""Tool usage table has no challenger rows without challenge."""
	ui = TUI(analysis_count=1)
	stats = ToolUsageStats()
	stats.add_start("c1", "bash")
	stats.add_complete("c1", success=True)

	results = [
		AgentRunResult(run_id="0", progress_log=[], tool_usage=stats),
	]
	table = ui._render_tool_usage_table(results)
	assert table.row_count == 1


def test_tui_tool_usage_table_challenger_no_tool_usage():
	"""Challenger with no tool_usage doesn't add a row."""
	from secret_validator_grunt.models.challenge_result import (
		ChallengeResult,
	)

	ui = TUI(analysis_count=1)
	cr = ChallengeResult(verdict="CONFIRMED", tool_usage=None)
	stats = ToolUsageStats()
	stats.add_start("c1", "bash")
	stats.add_complete("c1", success=True)

	results = [
		AgentRunResult(
			run_id="0",
			progress_log=[],
			tool_usage=stats,
			challenge_result=cr,
		),
	]
	table = ui._render_tool_usage_table(results)
	assert table.row_count == 1
