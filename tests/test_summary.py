"""Tests for SummaryData model and build_summary_data extraction."""

from pathlib import Path

from secret_validator_grunt.models.summary import (
    build_summary_data,
    SummaryData,
    WinnerInfo,
    JudgeInfo,
    WorkspaceEntry,
)
from secret_validator_grunt.models.run_result import AgentRunResult
from secret_validator_grunt.models.report import Report
from secret_validator_grunt.models.skill_usage import SkillUsageStats
from secret_validator_grunt.models.tool_usage import ToolUsageStats
from secret_validator_grunt.models.challenge_result import ChallengeResult


def _make_result(
        run_id: str, verdict: str | None = None, workspace: str | None = None,
        confidence_score: float | None = None,
        skill_usage: SkillUsageStats | None = None,
        tool_usage: ToolUsageStats | None = None,
        challenge_result: ChallengeResult | None = None) -> AgentRunResult:
	"""Helper to build a minimal AgentRunResult."""
	report = None
	if verdict:
		report = Report(
		    raw_markdown="test",
		    verdict=verdict,
		    confidence_score=confidence_score,
		    confidence_label="High"
		    if confidence_score and confidence_score >= 7 else None,
		)
	return AgentRunResult(
	    run_id=run_id,
	    progress_log=[],
	    workspace=workspace,
	    report=report,
	    skill_usage=skill_usage,
	    tool_usage=tool_usage,
	    challenge_result=challenge_result,
	)


class _FakeJudge:
	"""Minimal judge result stub."""

	def __init__(self, rationale=None, verdict=None, workspace=None):
		self.rationale = rationale
		self.verdict = verdict
		self.workspace = workspace


def test_build_summary_data_with_winner():
	"""Extracts winner info from analysis results."""
	results = [
	    _make_result("0", verdict="FALSE_POSITIVE", workspace="/tmp/ws0",
	                 confidence_score=8.5),
	]
	data = build_summary_data(0, results, Path("/out"))
	assert data.winner is not None
	assert data.winner.verdict == "FALSE_POSITIVE"
	assert data.winner.confidence == "8.5/10 (High)"
	assert data.winner.workspace == "/tmp/ws0"
	assert data.winner.final_report_path == "/out/final-report.md"


def test_build_summary_data_invalid_winner_index():
	"""Returns None winner when index is out of range."""
	results = [_make_result("0")]
	data = build_summary_data(5, results, Path("/out"))
	assert data.winner is None


def test_build_summary_data_negative_winner_index():
	"""Returns None winner for negative index."""
	results = [_make_result("0")]
	data = build_summary_data(-1, results, Path("/out"))
	assert data.winner is None


def test_build_summary_data_with_judge():
	"""Extracts judge info when judge_result is provided."""
	results = [_make_result("0")]
	judge = _FakeJudge(rationale="Best analysis", verdict="VALID",
	                   workspace="/tmp/judge")
	data = build_summary_data(0, results, Path("/out"), judge_result=judge)
	assert data.judge is not None
	assert data.judge.winner_index == 0
	assert data.judge.rationale == "Best analysis"
	assert data.judge.verdict == "VALID"
	assert data.judge.workspace == "/tmp/judge"


def test_build_summary_data_no_judge():
	"""Judge info is None when no judge_result."""
	results = [_make_result("0")]
	data = build_summary_data(0, results, Path("/out"))
	assert data.judge is None


def test_build_summary_data_workspaces():
	"""Collects all workspaces from results and judge."""
	results = [
	    _make_result("0", workspace="/tmp/ws0"),
	    _make_result("1", workspace="/tmp/ws1"),
	    _make_result("2"),  # no workspace
	]
	judge = _FakeJudge(workspace="/tmp/judge")
	data = build_summary_data(0, results, Path("/out"), judge_result=judge)
	assert len(data.workspaces) == 3  # 2 analysis + 1 judge
	assert data.workspaces[0].run_id == "0"
	assert data.workspaces[1].run_id == "1"
	assert data.workspaces[2].run_id == "judge"


def test_build_summary_data_usage_flags():
	"""Usage flags are set only when show_usage=True."""
	results = [
	    _make_result(
	        "0",
	        skill_usage=SkillUsageStats(available_skills=["a"],
	                                    loaded_skills=["a"]),
	        tool_usage=ToolUsageStats(),
	    ),
	]
	# show_usage=False — flags remain False
	data_off = build_summary_data(0, results, Path("/out"), show_usage=False)
	assert data_off.has_skill_usage is False
	assert data_off.has_tool_usage is False

	# show_usage=True — flags reflect actual data
	data_on = build_summary_data(0, results, Path("/out"), show_usage=True)
	assert data_on.has_skill_usage is True
	assert data_on.has_tool_usage is True  # ToolUsageStats() is truthy


def test_build_summary_data_winner_no_report():
	"""Winner with no report still has workspace and final_report_path."""
	results = [_make_result("0", workspace="/tmp/ws")]
	data = build_summary_data(0, results, Path("/out"))
	assert data.winner is not None
	assert data.winner.verdict is None
	assert data.winner.workspace == "/tmp/ws"
	assert data.winner.final_report_path == "/out/final-report.md"


def test_build_summary_data_challenger_skill_usage_flag():
	"""has_skill_usage is True when only challenger has skill_usage."""
	cr = ChallengeResult(
	    verdict="CONFIRMED",
	    skill_usage=SkillUsageStats(
	        available_skills=["x"],
	        loaded_skills=["x"],
	    ),
	)
	results = [
	    _make_result(
	        "0",
	        skill_usage=None,
	        challenge_result=cr,
	    ),
	]
	data = build_summary_data(0, results, Path("/out"), show_usage=True)
	assert data.has_skill_usage is True


def test_build_summary_data_challenger_tool_usage_flag():
	"""has_tool_usage is True when only challenger has tool_usage."""
	tools = ToolUsageStats()
	tools.add_start("c1", "bash")
	tools.add_complete("c1", success=True)
	cr = ChallengeResult(
	    verdict="CONFIRMED",
	    tool_usage=tools,
	)
	results = [
	    _make_result(
	        "0",
	        tool_usage=None,
	        challenge_result=cr,
	    ),
	]
	data = build_summary_data(0, results, Path("/out"), show_usage=True)
	assert data.has_tool_usage is True


def test_build_summary_data_no_challenger_usage_flags():
	"""Usage flags are False when neither analysis nor challenger have data."""
	cr = ChallengeResult(
	    verdict="CONFIRMED",
	    skill_usage=None,
	    tool_usage=None,
	)
	results = [
	    _make_result(
	        "0",
	        skill_usage=None,
	        tool_usage=None,
	        challenge_result=cr,
	    ),
	]
	data = build_summary_data(0, results, Path("/out"), show_usage=True)
	assert data.has_skill_usage is False
	assert data.has_tool_usage is False
