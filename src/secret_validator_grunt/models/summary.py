"""
Summary data model for TUI rendering.

Pure data extraction for the final summary display,
separating data logic from Rich rendering.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class WinnerInfo(BaseModel):
	"""Extracted winner report fields for display."""

	verdict: str | None = None
	confidence: str | None = None
	risk_level: str | None = None
	secret_type: str | None = None
	key_finding: str | None = None
	workspace: str | None = None
	final_report_path: str | None = None


class JudgeInfo(BaseModel):
	"""Extracted judge decision fields for display."""

	winner_index: int
	rationale: str | None = None
	verdict: str | None = None
	workspace: str | None = None


class WorkspaceEntry(BaseModel):
	"""A run_id → workspace mapping."""

	run_id: str
	workspace: str


class SummaryData(BaseModel):
	"""All data needed to render the final summary.

	This model is populated by `build_summary_data()` and consumed
	by `_render_summary()`, separating data extraction from rendering.
	"""

	winner: WinnerInfo | None = None
	judge: JudgeInfo | None = None
	workspaces: list[WorkspaceEntry] = Field(default_factory=list)
	show_usage: bool = False
	has_skill_usage: bool = False
	has_tool_usage: bool = False


def build_summary_data(
    winner_index: int,
    analysis_results: list,
    output_dir: Path,
    judge_result: object | None = None,
    show_usage: bool = False,
) -> SummaryData:
	"""Extract display data from analysis results and judge result.

	Pure function with no rendering side effects — returns a SummaryData
	model that can be unit tested independently.

	Parameters:
		winner_index: Index of the winning analysis.
		analysis_results: List of AgentRunResult objects.
		output_dir: Base output directory path.
		judge_result: Optional JudgeResult object.
		show_usage: Whether usage metrics should be displayed.

	Returns:
		Populated SummaryData model.
	"""
	data = SummaryData(show_usage=show_usage)

	# Winner info
	if 0 <= winner_index < len(analysis_results):
		win = analysis_results[winner_index]
		report = win.report
		winner = WinnerInfo(
		    workspace=win.workspace,
		    final_report_path=str(output_dir / "final-report.md"),
		)
		if report:
			winner.verdict = report.verdict
			if report.confidence_score:
				label = report.confidence_label or ""
				winner.confidence = f"{report.confidence_score}/10 ({label})"
			winner.risk_level = report.risk_level
			winner.secret_type = report.secret_type
			winner.key_finding = report.key_finding
		data.winner = winner

	# Judge info
	if judge_result:
		data.judge = JudgeInfo(
		    winner_index=winner_index,
		    rationale=getattr(judge_result, "rationale", None),
		    verdict=getattr(judge_result, "verdict", None),
		    workspace=getattr(judge_result, "workspace", None),
		)

	# Workspace list
	for res in analysis_results:
		if res.workspace:
			data.workspaces.append(
			    WorkspaceEntry(run_id=str(res.run_id),
			                   workspace=res.workspace))
	if judge_result and getattr(judge_result, "workspace", None):
		data.workspaces.append(
		    WorkspaceEntry(run_id="judge", workspace=judge_result.workspace))

	# Usage flags
	if show_usage:
		data.has_skill_usage = any(res.skill_usage for res in analysis_results)
		data.has_tool_usage = any(res.tool_usage for res in analysis_results)

	return data


__all__ = [
    "SummaryData",
    "WinnerInfo",
    "JudgeInfo",
    "WorkspaceEntry",
    "build_summary_data",
]
